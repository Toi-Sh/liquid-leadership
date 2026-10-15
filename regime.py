#!/usr/bin/env python3
"""Market regime page: cycle, T2108, breadth, and the index tape.

The cycle is a reading of breadth, not an instruction to trade.
T2108 is the share of liquid NYSE names above their 40-day average.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import pickle
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
HTML_PATH = PROJECT_DIR / "regime.html"
NY_TZ = ZoneInfo("America/New_York")
CACHE_PATH = PROJECT_DIR / "outputs" / ".regime_closes.pkl"

WASHOUT_LINE = 29.0
CLEAR_LINE = 25.0
EXTENDED_LINE = 70.0
MID_LINE = 50.0
BOUNCE_RISE = 5.0
RATIO_VOTE = 1.5
UP_VOTE = 500
AT_HIGHS = -5.0
EMA_LOW = 40.0
FAST_WINDOW = 2
FAST_CLOSE = 15.0
FAST_RATIO = 1.5
FAST_CAP = 30.0
POINT_BAND = 2.0
BATCH_SIZE = 80
MIN_NAMES = 100

STAGES = ("Washout", "Bounce", "Recovery", "Strength", "Extended", "Rolling over", "Weak")
STAGE_TONE = {
    "Extended": "up",
    "Strength": "ink",
    "Rolling over": "down",
    "Weak": "down",
    "Washout": "ink",
    "Bounce": "ink",
    "Recovery": "up",
}
STAGE_ARROW = {
    "Washout": "up",
    "Bounce": "up",
    "Recovery": "up",
    "Strength": "up",
    "Extended": "down",
    "Rolling over": "down",
    "Weak": "down",
}

TAPE = (
    ("S&P 500", "^GSPC", 20, "https://www.tradingview.com/chart/?symbol=SP:SPX&interval=D"),
    ("QQQ", "QQQ", 20, "https://www.tradingview.com/chart/?symbol=NASDAQ:QQQ&interval=D"),
    ("IWM", "IWM", 30, "https://www.tradingview.com/chart/?symbol=AMEX:IWM&interval=D"),
    ("DIA", "DIA", 20, "https://www.tradingview.com/chart/?symbol=NYSE:DIA&interval=D"),
)
HEALTH = ("SPY", "QQQ", "DIA", "IWM")
HEALTH_CHECKS = ("ema5_above_10", "ema10_above_20", "ema10_slope", "ema20_slope", "price_above_10", "price_above_20")


@dataclass
class Memory:
    stage: str
    since: str
    sessions: int
    washout_low: float | None


def finite(value: object) -> bool:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return number == number and abs(number) != math.inf


def yahoo_symbol(ticker: str) -> str:
    return str(ticker).strip().upper().replace(".", "-").replace("/", "-")


def rolling_ratio(up: pd.Series, down: pd.Series, window: int) -> pd.Series:
    """Sum of up days over the window, divided by the sum of down days."""
    ups = up.rolling(window).sum()
    downs = down.rolling(window).sum()
    ratio = ups / downs.where(downs > 0)
    return ratio.mask((downs == 0) & (ups > 0), 99.0)


def ema(series: pd.Series, span: int) -> pd.Series:
    valid = series.dropna()
    if valid.empty:
        return series * float("nan")
    return valid.ewm(span=span, adjust=False).mean().reindex(series.index)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.where(avg_loss > 0)
    return (100 - (100 / (1 + rs))).where(avg_loss > 0, 100.0)


def posture_score(t2108: float, passes: int, total: int) -> int:
    """Half the T2108 reading, half the share of index-health checks that pass."""
    share = 100.0 * passes / total if total else t2108
    return int(round(0.5 * t2108 + 0.5 * share))


def has_thrust(day: dict) -> bool:
    if (day.get("up4") or 0) >= UP_VOTE:
        return True
    ratio = day.get("ratio5")
    return finite(ratio) and float(ratio) >= RATIO_VOTE


def catching_up(day: dict) -> bool:
    """A low average rising toward T2108 is not breadth improvement."""
    ema = day.get("t2108_ema10")
    ema_delta = day.get("ema_delta")
    if not finite(ema) or float(ema) >= EMA_LOW:
        return False
    if not finite(ema_delta) or float(ema_delta) <= 0:
        return False
    rise = day.get("t2108_delta")
    ratio = day.get("ratio5")
    leads = finite(rise) and float(rise) > float(ema_delta) and finite(ratio) and float(ratio) >= 1
    return not leads


def breadth_improving(day: dict, rise_key: str = "rise_2", start_key: str = "start_2", ema_key: str = "ema_rise_2") -> bool:
    """A thrust off a depressed reading, with a two-point band around the fit."""
    rise = day.get(rise_key)
    start = day.get(start_key)
    ratio = day.get("ratio5")
    ema_rise = day.get(ema_key)
    if not all(finite(value) for value in (rise, start, ratio, ema_rise)):
        return False
    return (
        float(start) <= FAST_CAP + POINT_BAND
        and float(rise) >= FAST_CLOSE - POINT_BAND
        and float(ratio) >= FAST_RATIO
        and float(rise) > float(ema_rise)
    )


def annotate_breadth(days: list[dict]) -> None:
    for index, day in enumerate(days):
        previous = days[index - 1] if index else None
        if previous:
            day["t2108_delta"] = float(day["t2108"]) - float(previous["t2108"])
            day["ema_delta"] = float(day["t2108_ema10"]) - float(previous["t2108_ema10"])
            prior_delta = previous.get("t2108_delta")
            day["accel"] = day["t2108_delta"] - float(prior_delta) if finite(prior_delta) else None
        else:
            day["t2108_delta"] = None
            day["ema_delta"] = None
            day["accel"] = None
        if index >= FAST_WINDOW:
            earlier = days[index - FAST_WINDOW]
            day["rise_2"] = float(day["t2108"]) - float(earlier["t2108"])
            day["start_2"] = float(earlier["t2108"])
            day["ema_rise_2"] = float(day["t2108_ema10"]) - float(earlier["t2108_ema10"])
            if finite(day.get("nasdaq")) and finite(earlier.get("nasdaq")) and finite(day.get("nasdaq_ema10")) and finite(earlier.get("nasdaq_ema10")):
                day["nasdaq_rise_2"] = float(day["nasdaq"]) - float(earlier["nasdaq"])
                day["nasdaq_start_2"] = float(earlier["nasdaq"])
                day["nasdaq_ema_rise_2"] = float(day["nasdaq_ema10"]) - float(earlier["nasdaq_ema10"])
            else:
                day["nasdaq_rise_2"] = None
                day["nasdaq_start_2"] = None
                day["nasdaq_ema_rise_2"] = None
        else:
            day["rise_2"] = None
            day["start_2"] = None
            day["ema_rise_2"] = None
            day["nasdaq_rise_2"] = None
            day["nasdaq_start_2"] = None
            day["nasdaq_ema_rise_2"] = None
        day["rise_3"] = float(day["t2108"]) - float(days[index - 3]["t2108"]) if index >= 3 else None
        day["catching_up"] = catching_up(day)
        day["improving"] = breadth_improving(day)
        day["nasdaq_improving"] = breadth_improving(day, "nasdaq_rise_2", "nasdaq_start_2", "nasdaq_ema_rise_2")


def infer_stage(day: dict) -> str:
    t2108 = float(day["t2108"])
    if t2108 >= EXTENDED_LINE:
        return "Extended"
    if t2108 <= WASHOUT_LINE:
        return "Washout"
    if day.get("improving"):
        return "Recovery"
    if t2108 >= MID_LINE and day.get("spy_above_20") and not day.get("catching_up"):
        return "Strength"
    return "Weak"


def transition(stage: str, memory: Memory, day: dict) -> str:
    """Next cycle stage. Thresholds match the lines drawn on the T2108 chart."""
    t2108 = float(day["t2108"])
    ratio = float(day["ratio5"]) if finite(day.get("ratio5")) else 0.0
    ema10 = day.get("t2108_ema10")
    spy_up = bool(day.get("spy_above_20"))
    thrust = has_thrust(day)
    low = memory.washout_low

    if stage == "Washout":
        rise = 0.0 if low is None else t2108 - low
        if rise >= BOUNCE_RISE and thrust:
            return "Bounce"
        if t2108 > CLEAR_LINE and not thrust:
            return "Weak"
        return "Washout"
    if stage == "Bounce":
        if low is not None and t2108 < low:
            return "Washout"
        if t2108 <= WASHOUT_LINE and low is None:
            return "Washout"
        if day.get("improving"):
            return "Recovery"
        if day.get("catching_up") and ratio < 1:
            return "Weak"
        return "Bounce"
    if stage == "Recovery":
        if low is not None and t2108 < low:
            return "Washout"
        if t2108 >= MID_LINE and spy_up and ratio >= 1 and not day.get("catching_up"):
            return "Strength"
        if day.get("catching_up") and not day.get("improving"):
            return "Weak"
        if t2108 < 30 and ratio < 1:
            return "Weak"
        return "Recovery"
    if stage == "Strength":
        if t2108 >= EXTENDED_LINE:
            return "Extended"
        if t2108 <= WASHOUT_LINE:
            return "Washout"
        if finite(ema10) and t2108 < float(ema10) and ratio < 1:
            return "Rolling over"
        return "Strength"
    if stage == "Extended":
        if t2108 < EXTENDED_LINE:
            return "Rolling over"
        return "Extended"
    if stage == "Rolling over":
        if t2108 >= EXTENDED_LINE:
            return "Extended"
        if t2108 <= WASHOUT_LINE:
            return "Washout"
        if t2108 < MID_LINE or (not spy_up and ratio < 1):
            return "Weak"
        return "Rolling over"
    if t2108 <= WASHOUT_LINE:
        return "Washout"
    if thrust:
        return "Bounce"
    if day.get("improving"):
        return "Recovery"
    return "Weak"


def _ratio_text(day: dict) -> str:
    ratio = day.get("ratio5")
    if not finite(ratio):
        return "unavailable"
    if float(ratio) >= 99:
        return "one-sided"
    return f"{float(ratio):.2f}"


def describe(memory: Memory, day: dict) -> dict:
    """Progress line and the two rules that would change the current stage."""
    t2108 = float(day["t2108"])
    ratio_text = _ratio_text(day)
    low = memory.washout_low
    rise = None if low is None else t2108 - low
    stage = memory.stage
    if stage == "Washout" and low is not None:
        vote_rise = (rise or 0) >= BOUNCE_RISE
        votes = int(vote_rise) + int(has_thrust(day))
        hold = low + BOUNCE_RISE
        progress = f"Bounce: T2108 {rise:+.1f} of +{BOUNCE_RISE:.0f}, votes {votes} of 2"
        rules = [
            f"Bounce at once if T2108 holds {hold:.1f} and one more vote arrives "
            f"(5-day ratio ≥ {RATIO_VOTE:.1f}, now {ratio_text}, or a {UP_VOTE:,}-name up day, or a 1,000-name up day).",
            f"Weak if T2108 clears {CLEAR_LINE:.0f} without that vote.",
        ]
    elif stage == "Bounce":
        progress = "The thrust is in. Breadth has not improved yet."
        rules = [
            f"Thrust, and recovery, when T2108 rises {FAST_CLOSE:.0f} points in {FAST_WINDOW} sessions, give or take {POINT_BAND:.0f}, from a reading at or under {FAST_CAP:.0f}, give or take {POINT_BAND:.0f}. The 5-day ratio is at least {FAST_RATIO:.1f}, and the rise beats the 10-day average.",
            "A low average catching up does not count. Weak if that is all that is left and the 5-day ratio falls under 1. Washout if T2108 undercuts the low.",
        ]
    elif stage == "Recovery":
        progress = "Breadth has thrust off a depressed reading."
        rules = [
            "Strength once T2108 holds 50, the 5-day ratio stays at least 1, and the S&P 500 is above its 20-day EMA.",
            "Weak if the average is only catching up from a low base. Washout if T2108 undercuts the washout low.",
        ]
    elif stage == "Strength":
        progress = "The advance is healthy."
        rules = [
            "Extended on a T2108 close at 70 or above.",
            "Rolling over if T2108 loses its 10-day average while the 5-day ratio is under 1.",
        ]
    elif stage == "Extended":
        progress = "Participation is stretched."
        rules = [
            "Stays extended while T2108 holds 70.",
            "Rolling over on a close under 70.",
        ]
    elif stage == "Rolling over":
        progress = "The extended reading has given way."
        rules = [
            "Weak if T2108 loses 50, or the S&P 500 loses its 20-day EMA while the 5-day ratio is under 1.",
            "Extended again if T2108 reclaims 70. Washout if it closes at 29 or below.",
        ]
    else:
        if day.get("catching_up"):
            progress = "The averages are catching up because they are low. Breadth is not improving."
        else:
            progress = "The tape is damaged, and it is not washed out."
        rules = [
            f"Thrust when T2108 rises {FAST_CLOSE:.0f} points in {FAST_WINDOW} sessions, give or take {POINT_BAND:.0f}, from a reading at or under {FAST_CAP:.0f}, give or take {POINT_BAND:.0f}. The 5-day ratio is at least {FAST_RATIO:.1f}, and the rise beats the 10-day average. Nasdaq 40 uses the same band.",
            "Washout if T2108 closes at 29 or below. A 5-day ratio of 1.5, or a 500-name up day, can still mark a bounce.",
        ]
    return {"progress": progress, "rules": rules}


def walk_regime(days: list[dict]) -> list[dict]:
    """Apply the cycle from the first session forward. Each day keeps its own inputs."""
    if not days:
        return []
    annotate_breadth(days)
    first = infer_stage(days[0])
    low = float(days[0]["t2108"]) if first == "Washout" else None
    memory = Memory(first, str(days[0]["date"]), 1, low)
    walked = [{**days[0], "stage": memory.stage, "since": memory.since, "sessions": memory.sessions, "washout_low": memory.washout_low, **describe(memory, days[0])}]
    for day in days[1:]:
        if memory.stage == "Washout":
            low_now = float(day["t2108"]) if memory.washout_low is None else min(memory.washout_low, float(day["t2108"]))
            memory = Memory(memory.stage, memory.since, memory.sessions, low_now)
        stage = transition(memory.stage, memory, day)
        if stage == memory.stage:
            kept = memory.washout_low if stage in {"Washout", "Bounce", "Recovery"} else None
            memory = Memory(stage, memory.since, memory.sessions + 1, kept)
        else:
            if stage == "Washout":
                kept = float(day["t2108"])
            elif stage in {"Bounce", "Recovery"}:
                kept = memory.washout_low
            else:
                kept = None
            memory = Memory(stage, str(day["date"]), 1, kept)
        walked.append({**day, "stage": memory.stage, "since": memory.since, "sessions": memory.sessions, "washout_low": memory.washout_low, **describe(memory, day)})
    previous = None
    for day in walked:
        score = posture_score(float(day["t2108"]), int(day.get("health_passes") or 0), int(day.get("health_total") or 0))
        day["posture"] = score
        day["momentum"] = None if previous is None else score - previous
        previous = score
    return walked


def _above_share(panel: pd.DataFrame, sma40: pd.DataFrame, names: list[str]) -> tuple[pd.Series, pd.Series]:
    """Share of `names` whose close is above the 40-day average, and how many have that average."""
    if not names:
        return pd.Series(float("nan"), index=panel.index), pd.Series(0, index=panel.index)
    ready = sma40[names].notna().sum(axis=1)
    share = (panel[names].gt(sma40[names]).sum(axis=1) / ready.where(ready > 0)) * 100
    return share, ready


def compute_breadth(closes: pd.DataFrame, nyse: pd.Series, nasdaq: pd.Series | None = None) -> pd.DataFrame:
    """Daily breadth for a close panel. `nyse` and `nasdaq` are boolean series indexed by symbol."""
    panel = closes.sort_index().astype(float)
    coverage = panel.notna().sum(axis=1)
    floor = min(MIN_NAMES, max(1, panel.shape[1] // 2))
    panel = panel.loc[coverage >= floor]
    sma40 = panel.rolling(40, min_periods=40).mean()
    nyse_names = [name for name in panel.columns if bool(nyse.get(name, False))]
    nasdaq_names = [name for name in panel.columns if nasdaq is not None and bool(nasdaq.get(name, False))]
    t2108, nyse_ready = _above_share(panel, sma40, nyse_names)
    nasdaq_share, nasdaq_ready = _above_share(panel, sma40, nasdaq_names)

    pct = panel.pct_change() * 100
    up4 = pct.ge(4).sum(axis=1)
    down4 = pct.le(-4).sum(axis=1)
    ret5 = panel.pct_change(5) * 100
    ret21 = panel.pct_change(21) * 100
    ret40 = panel.pct_change(40) * 100
    ret63 = panel.pct_change(63) * 100
    ema13 = panel.ewm(span=13, adjust=False).mean()
    ema34 = panel.ewm(span=34, adjust=False).mean()
    alive = panel.notna()
    bull13 = (ema13.gt(ema34) & alive).sum(axis=1)
    bear13 = (ema13.lt(ema34) & alive).sum(axis=1)

    frame = pd.DataFrame({
        "t2108": t2108,
        "nasdaq": nasdaq_share,
        "up4": up4,
        "down4": down4,
        "ratio5": rolling_ratio(up4, down4, 5),
        "ratio10": rolling_ratio(up4, down4, 10),
        "bull13": bull13,
        "bear13": bear13,
        "balance": bull13 - bear13,
        "bull20": ret5.ge(20).sum(axis=1),
        "bear20": ret5.le(-20).sum(axis=1),
        "up25m": ret21.ge(25).sum(axis=1),
        "down25m": ret21.le(-25).sum(axis=1),
        "up25q": ret63.ge(25).sum(axis=1),
        "down25q": ret63.le(-25).sum(axis=1),
        "up50": ret40.ge(50).sum(axis=1),
        "down50": ret40.le(-50).sum(axis=1),
        "n": coverage.reindex(panel.index),
        "n_nyse": nyse_ready,
        "n_nasdaq": nasdaq_ready,
    })
    frame["t2108_ema10"] = ema(frame["t2108"], 10)
    frame["nasdaq_ema10"] = ema(frame["nasdaq"], 10)
    return frame


def health_frame(closes: pd.DataFrame) -> pd.DataFrame:
    """Pass-count of the six EMA checks across SPY, QQQ, DIA, and IWM."""
    total = pd.Series(0, index=closes.index, dtype=int)
    passes = pd.Series(0, index=closes.index, dtype=int)
    for symbol in HEALTH:
        if symbol not in closes.columns:
            continue
        close = closes[symbol].astype(float)
        ema5 = ema(close, 5)
        ema10 = ema(close, 10)
        ema20 = ema(close, 20)
        checks = pd.DataFrame({
            "ema5_above_10": ema5.gt(ema10),
            "ema10_above_20": ema10.gt(ema20),
            "ema10_slope": ema10.diff().gt(0),
            "ema20_slope": ema20.diff().gt(0),
            "price_above_10": close.gt(ema10),
            "price_above_20": close.gt(ema20),
        })
        ready = checks.notna().all(axis=1)
        total = total.add(ready.astype(int) * len(HEALTH_CHECKS), fill_value=0)
        passes = passes.add(checks.sum(axis=1).where(ready, 0), fill_value=0)
    return pd.DataFrame({"health_passes": passes.astype(int), "health_total": total.astype(int)})


def market_frame(index_closes: pd.DataFrame) -> pd.DataFrame:
    """S&P distance from its one-year high, and whether it is above the 20-day EMA."""
    price = index_closes["^GSPC"] if "^GSPC" in index_closes.columns else index_closes["SPY"]
    price = price.astype(float)
    high = price.rolling(252, min_periods=20).max()
    drawdown = (price / high - 1) * 100
    above = price.gt(ema(price, 20))
    frame = pd.DataFrame({"drawdown": drawdown, "spy_above_20": above})
    frame = frame.join(health_frame(index_closes))
    return frame


def days_from_frames(breadth: pd.DataFrame, market: pd.DataFrame) -> list[dict]:
    joined = breadth.join(market, how="inner")
    days = []
    for ts, row in joined.iterrows():
        if not finite(row.get("t2108")) or not finite(row.get("ratio5")) or not finite(row.get("t2108_ema10")):
            continue
        days.append({
            "date": pd.Timestamp(ts).date().isoformat(),
            "t2108": float(row["t2108"]),
            "t2108_ema10": float(row["t2108_ema10"]),
            "up4": int(row["up4"]),
            "down4": int(row["down4"]),
            "ratio5": float(row["ratio5"]),
            "ratio10": float(row["ratio10"]) if finite(row.get("ratio10")) else None,
            "bull13": int(row["bull13"]),
            "bear13": int(row["bear13"]),
            "balance": int(row["balance"]),
            "bull20": int(row["bull20"]),
            "bear20": int(row["bear20"]),
            "up25m": int(row["up25m"]),
            "down25m": int(row["down25m"]),
            "up25q": int(row["up25q"]),
            "down25q": int(row["down25q"]),
            "up50": int(row["up50"]),
            "down50": int(row["down50"]),
            "n": int(row["n"]),
            "n_nyse": int(row["n_nyse"]) if finite(row.get("n_nyse")) else 0,
            "nasdaq": float(row["nasdaq"]) if finite(row.get("nasdaq")) else None,
            "nasdaq_ema10": float(row["nasdaq_ema10"]) if finite(row.get("nasdaq_ema10")) else None,
            "n_nasdaq": int(row["n_nasdaq"]) if finite(row.get("n_nasdaq")) else 0,
            "drawdown": float(row["drawdown"]) if finite(row.get("drawdown")) else 0.0,
            "spy_above_20": bool(row["spy_above_20"]) if finite(row.get("spy_above_20")) else False,
            "health_passes": int(row["health_passes"]) if finite(row.get("health_passes")) else 0,
            "health_total": int(row["health_total"]) if finite(row.get("health_total")) else 0,
        })
    return walk_regime(days)


def _field(raw: pd.DataFrame, field: str) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        if field in raw.columns.get_level_values(0):
            frame = raw[field]
        else:
            frame = raw.xs(field, axis=1, level=1)
        if isinstance(frame, pd.Series):
            frame = frame.to_frame()
        return frame
    if field == "Close":
        return raw[["Close"]].rename(columns={"Close": raw.columns.name or "Close"})
    raise RuntimeError(f"No {field} column in the price download.")


def _as_dates(frame: pd.DataFrame) -> pd.DataFrame:
    idx = pd.to_datetime(frame.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(None)
    out = frame.copy()
    out.index = idx.normalize()
    return out.sort_index()


def fetch_universe(max_names: int) -> pd.DataFrame:
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error
    _count, frame = (
        Query()
        .set_markets("america")
        .select("name", "exchange", "average_volume_10d_calc")
        .where(
            col("type") == "stock",
            col("exchange").isin(["NYSE", "NASDAQ", "AMEX"]),
            col("close") > 5,
            col("average_volume_10d_calc") > 300_000,
        )
        .order_by("average_volume_10d_calc", ascending=False)
        .limit(max_names)
        .get_scanner_data()
    )
    if frame is None or frame.empty:
        raise RuntimeError("TradingView returned no names for the regime universe.")
    frame = frame.copy()
    frame["name"] = frame["name"].map(yahoo_symbol)
    frame = frame.drop_duplicates("name")
    return frame


def download_closes(tickers: list[str]) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    frames: list[pd.DataFrame] = []
    batches = [tickers[index:index + BATCH_SIZE] for index in range(0, len(tickers), BATCH_SIZE)]
    for number, batch in enumerate(batches, start=1):
        print(f"Prices {number}/{len(batches)} ({len(batch)} names)", flush=True)
        try:
            raw = yf.download(batch, period="2y", auto_adjust=True, progress=False, threads=True, group_by="column")
        except Exception as error:  # noqa: BLE001 — one bad batch should not drop the page
            print(f"  batch failed: {error}", flush=True)
            continue
        if raw is None or raw.empty:
            continue
        close = _as_dates(_field(raw, "Close"))
        close = close.loc[:, ~close.columns.duplicated()]
        frames.append(close)
    if not frames:
        raise RuntimeError("No price history returned.")
    panel = pd.concat(frames, axis=1)
    panel = panel.loc[:, ~panel.columns.duplicated()]
    panel = panel.dropna(axis=1, how="all").dropna(axis=0, how="all")
    if panel.shape[1] < MIN_NAMES:
        raise RuntimeError(f"Only {panel.shape[1]} names returned prices.")
    return panel


def download_indexes() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Index closes, the last VIX high/low, and today's SPY intraday closes."""
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    symbols = ["^GSPC", "^VIX", "^TNX", "SPY", "QQQ", "IWM", "DIA"]
    raw = yf.download(symbols, period="2y", auto_adjust=True, progress=False, threads=True, group_by="column")
    closes = _as_dates(_field(raw, "Close"))
    highs = _as_dates(_field(raw, "High"))
    lows = _as_dates(_field(raw, "Low"))
    vix_range = pd.Series({"high": float("nan"), "low": float("nan")})
    if "^VIX" in highs.columns and "^VIX" in lows.columns:
        last = highs["^VIX"].dropna().index[-1]
        vix_range = pd.Series({"high": float(highs["^VIX"].loc[last]), "low": float(lows["^VIX"].loc[last])})
    intra = yf.download("SPY", period="5d", interval="5m", auto_adjust=True, progress=False, group_by="column")
    intraday = pd.Series(dtype=float)
    if intra is not None and not intra.empty:
        points = _field(intra, "Close")
        points = points.iloc[:, 0] if isinstance(points, pd.DataFrame) else points
        points.index = pd.to_datetime(points.index)
        if getattr(points.index, "tz", None) is not None:
            points.index = points.index.tz_convert(NY_TZ)
        session = points.index[-1].date()
        intraday = points.loc[points.index.date == session].astype(float).dropna()
    return closes, vix_range, intraday


def load_closes(universe: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    names = universe["name"].tolist()
    nyse = set(universe.loc[universe["exchange"].str.upper() == "NYSE", "name"])
    if CACHE_PATH.exists() and not refresh:
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < 12 * 3600:
            cached = pickle.loads(CACHE_PATH.read_bytes())
            if cached.get("names") == names:
                print(f"Using cached prices ({int(age // 60)} min old)", flush=True)
                return cached["closes"]
    closes = download_closes(names)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_bytes(pickle.dumps({"names": names, "nyse": sorted(nyse), "closes": closes}))
    return closes


def short_date(iso: str) -> str:
    day = date.fromisoformat(str(iso)[:10])
    return f"{day.day} {day.strftime('%b')}"


def long_stamp(when: datetime, last_session: date) -> str:
    now = when.astimezone(NY_TZ)
    if last_session == now.date() and now.weekday() < 5 and (now.hour, now.minute) < (16, 15):
        return f"{now.day} {now.strftime('%b')} {now.year}, {now:%H:%M} ET"
    return f"{last_session.day} {last_session.strftime('%b')} {last_session.year}"


def _num(value: float, digits: int) -> str:
    if not finite(value):
        return "—"
    text = f"{abs(float(value)):,.{digits}f}"
    if float(value) < 0:
        return f"−{text}"
    return text


def _pair(left: float, right: float) -> str:
    return f"{_num(left, 0)} / {_num(right, 0)}"


def _delta(value: float | None, digits: int, suffix: str = "", invert: bool = False) -> str:
    if not finite(value):
        return '<span class="delta delta-flat">—</span>'
    number = float(value)
    if abs(number) < 0.5 * 10 ** (-digits):
        kind, arrow, word = "flat", "▶", "flat"
    elif number > 0:
        kind, arrow, word = "up", "▲", "up"
    else:
        kind, arrow, word = "down", "▼", "down"
    visual = kind
    if invert and kind in {"up", "down"}:
        visual = "down" if kind == "up" else "up"
    text = f"{abs(number):,.{digits}f}{suffix}"
    return (
        f'<span class="delta delta-{visual}">'
        f'<span class="arr arr-{kind}" aria-hidden="true">{arrow}</span>'
        f'<span class="visually-hidden">{word} </span>{text}</span>'
    )


def _signed(value: int | None) -> str:
    if not finite(value):
        return "—"
    number = int(value)
    if number > 0:
        return f"+{number}"
    if number < 0:
        return f"−{abs(number)}"
    return "0"


def cycle_board(stage: str, posture: int | None, momentum: int | None) -> str:
    """Status block: posture meter and the seven stages, current one marked."""
    score = "—" if posture is None else str(int(posture))
    move = _signed(momentum)
    if posture is None:
        meter = (
            '<div class="meter" role="meter" aria-valuemin="0" aria-valuemax="100" aria-label="Posture">'
            '<span class="meter-fill" style="width:0%"></span></div>'
        )
    else:
        width = max(0, min(100, int(posture)))
        meter = (
            f'<div class="meter" role="meter" aria-valuenow="{width}" aria-valuemin="0" aria-valuemax="100" '
            f'aria-label="Posture {score}">'
            f'<span class="meter-fill" style="width:{width}%"></span></div>'
        )
    steps = []
    for name in STAGES:
        current = name == stage
        tone = STAGE_TONE.get(name, "ink")
        mark = ' aria-current="step"' if current else ""
        live = " is-current" if current else ""
        steps.append(f'<li class="step step-{tone}{live}"{mark}>{html.escape(name)}</li>')
    return (
        '<div class="cycle-stats">'
        f'<div><p class="figure">{score}</p><p class="meta">Posture</p></div>'
        f'<div><p class="figure">{move}</p><p class="meta">Momentum</p></div>'
        "</div>"
        f"{meter}"
        f'<ol class="steps">{"".join(steps)}</ol>'
    )


def _chart_node(kind: str, values: list[float | None], *, guides: list[float] | None = None, signed: bool = False, label: str = "Series") -> str:
    payload = {
        "kind": kind,
        "label": label,
        "signed": signed,
        "guides": guides or [],
        "values": [round(float(value), 4) if finite(value) else None for value in values],
    }
    blob = html.escape(json.dumps(payload, separators=(",", ":")), quote=True)
    return f'<div class="spark shadcn-host" data-chart="{blob}"></div>'


def _series(values: list[float | None], width: int, height: int, floor: float | None = None, ceiling: float | None = None, label: str = "Series") -> str:
    clean = [float(value) for value in values if finite(value)]
    if len(clean) < 2:
        return ""
    guides = [float(level) for level in (floor, ceiling) if level is not None]
    return _chart_node("area", list(values), guides=guides, label=label)


def _bars(values: list[float], label: str = "Net") -> str:
    clean = [float(value) for value in values if finite(value)]
    if len(clean) < 2:
        return ""
    return _chart_node("bar", clean, signed=True, label=label)


def _change(series: list[float | None]) -> float | None:
    clean = [float(value) for value in series if finite(value)]
    if len(clean) < 2:
        return None
    return clean[-1] - clean[-2]


def build_snapshot(days: list[dict], tape: list[dict], vix: dict, yield_quote: dict, intraday: list[float], as_of: str) -> dict:
    last = days[-1]
    window = days[-126:]
    drawdown = float(last["drawdown"])
    place = "At highs" if drawdown >= AT_HIGHS else "Off the high"
    if abs(drawdown) < 0.05:
        distance = "at the high"
    else:
        distance = f"−{abs(drawdown):.1f}% from the high"
    t2108_series = [day["t2108"] for day in window]
    breadth = [
        {
            "title": "4% up / down",
            "figure": _pair(last["up4"], last["down4"]),
            "sub": f"up share {last['up4'] / max(last['up4'] + last['down4'], 1) * 100:.0f}%",
            "delta": _delta(_change([day["up4"] for day in days]), 0),
            "chart": _bars([day["up4"] - day["down4"] for day in days[-24:]], "4% up minus down"),
        },
        {
            "title": "5 / 10-day ratio",
            "figure": f"{last['ratio5']:.2f} / {last['ratio10']:.2f}" if finite(last.get("ratio10")) else f"{last['ratio5']:.2f}",
            "sub": "5d below 1" if last["ratio5"] < 1 else "5d above 1",
            "delta": _delta(_change([day["ratio5"] for day in days]), 2),
            "chart": _series([day["ratio5"] if day["ratio5"] < 99 else None for day in days[-40:]], 148, 36, label="5-day ratio"),
        },
        {
            "title": "13 / 34 balance",
            "figure": _num(last["balance"], 0),
            "sub": _pair(last["bull13"], last["bear13"]),
            "delta": _delta(_change([day["balance"] for day in days]), 0),
            "chart": _series([day["balance"] for day in days[-40:]], 148, 36, label="13/34 balance"),
        },
        {
            "title": "20% study · 5 sess",
            "figure": _pair(last["bull20"], last["bear20"]),
            "sub": "bull / bear",
            "delta": _delta(_change([day["bull20"] for day in days]), 0),
            "chart": _series([day["bull20"] - day["bear20"] for day in days[-40:]], 148, 36, label="Bull minus bear"),
        },
        {
            "title": "25% quarter / month",
            "figure": _pair(last["up25q"], last["down25q"]),
            "sub": f"month {_pair(last['up25m'], last['down25m'])}",
            "delta": _delta(_change([day["up25q"] for day in days]), 0),
            "chart": _series([day["up25q"] - day["down25q"] for day in days[-40:]], 148, 36, label="Quarter up minus down"),
        },
        {
            "title": "50% · 40 days",
            "figure": _pair(last["up50"], last["down50"]),
            "sub": "up / down",
            "delta": _delta(_change([day["up50"] for day in days]), 0),
            "chart": _series([day["up50"] - day["down50"] for day in days[-40:]], 148, 36, label="50% up minus down"),
        },
    ]
    band = last["t2108"] - last["t2108_ema10"]
    return {
        "as_of": as_of,
        "stage": last["stage"],
        "arrow": STAGE_ARROW[last["stage"]],
        "since": short_date(last["since"]),
        "sessions": int(last["sessions"]),
        "progress": last["progress"],
        "place": place,
        "distance": distance,
        "rules": last["rules"],
        "posture": last["posture"],
        "momentum": last["momentum"],
        "t2108": _num(last["t2108"], 1),
        "t2108_delta": _delta(_change(t2108_series), 1),
        "ema10": _num(last["t2108_ema10"], 1),
        "ema_side": "above" if band > 0 else "below" if band < 0 else "on",
        "ema_note": "catching up from a low base" if last.get("catching_up") else ("above" if band > 0 else "below" if band < 0 else "on it"),
        "thrust": "on" if last.get("improving") else "off",
        "nasdaq": _num(last["nasdaq"], 1) if finite(last.get("nasdaq")) else "—",
        "nasdaq_delta": _delta(_change([day.get("nasdaq") for day in window]), 1),
        "nasdaq_ema10": _num(last["nasdaq_ema10"], 1) if finite(last.get("nasdaq_ema10")) else "—",
        "nasdaq_note": _ema_note(last.get("nasdaq"), last.get("nasdaq_ema10")),
        "nasdaq_thrust": "on" if last.get("nasdaq_improving") else "off",
        "nasdaq_chart": _series([day.get("nasdaq") for day in window], 320, 96, floor=WASHOUT_LINE, ceiling=EXTENDED_LINE, label="Nasdaq 40"),
        "n_nasdaq": int(last.get("n_nasdaq") or 0),
        "low6": _num(min(t2108_series), 1),
        "high6": _num(max(t2108_series), 1),
        "t2108_chart": _series(t2108_series, 320, 96, floor=WASHOUT_LINE, ceiling=EXTENDED_LINE, label="T2108"),
        "chart_start": short_date(window[0]["date"]),
        "intraday": _series(intraday, 120, 96, label="SPY") if len(intraday) > 2 else "",
        "breadth": breadth,
        "tape": tape,
        "vix": vix,
        "yield": yield_quote,
        "n": int(last["n"]),
        "n_nyse": int(last["n_nyse"]),
    }


def _ema_note(level: object, average: object) -> str:
    if not finite(level) or not finite(average):
        return "unavailable"
    band = float(level) - float(average)
    return "above" if band > 0 else "below" if band < 0 else "on it"


def _quote_card(name: str, price: float, change_pct: float | None, relation: str, series: list[float], url: str, stroke: str) -> str:
    chart = _series(series, 148, 40, label=name)
    return f"""<article class="panel quote">
      <h3><a href="{html.escape(url, True)}">{html.escape(name)}</a></h3>
      <p class="figure">{_num(price, 2)}</p>
      <p class="sub">{_delta(change_pct, 1, "%")} <span class="muted">{html.escape(relation)}</span></p>
      <div class="chart chart-{stroke}">{chart}</div>
    </article>"""


def render_html(snapshot: dict, health_rows: list[dict]) -> str:
    stage = html.escape(str(snapshot["stage"]))
    arrow_class = "up" if snapshot["arrow"] == "up" else "down"
    note_kind = "down" if arrow_class == "down" else "up"
    note_word = "Warning" if note_kind == "down" else "Success"
    note_mark = "!" if note_kind == "down" else "✓"
    session_word = "Session" if snapshot["sessions"] == 1 else "Sessions"
    rules = "".join(f"<li>{html.escape(rule)}</li>" for rule in snapshot["rules"])
    breadth = "".join(
        f"""<article class="panel">
          <h3>{html.escape(card["title"])}</h3>
          <p class="figure">{card["figure"]}</p>
          <p class="sub">{html.escape(card["sub"])} {card["delta"]}</p>
          <div class="chart">{card["chart"]}</div>
        </article>"""
        for card in snapshot["breadth"]
    )
    tape = "".join(
        _quote_card(item["name"], item["price"], item["change"], item["relation"], item["series"], item["url"], item["stroke"])
        for item in snapshot["tape"]
    )
    health_body = []
    for row in health_rows:
        cells = [f'<th scope="row">{html.escape(row["symbol"])}</th>']
        for key in HEALTH_CHECKS:
            mark = row[key]
            if key.endswith("slope"):
                word, glyph, tone = ("rising", "↑", "up") if mark else ("falling", "↓", "down")
            else:
                word, glyph, tone = ("yes", "✓", "yes") if mark else ("no", "×", "no")
            cells.append(f'<td class="{tone}"><span class="visually-hidden">{word}</span><span aria-hidden="true">{glyph}</span></td>')
        cells.append(f'<td class="num">{row["rsi"]}</td>')
        cells.append(f'<td class="asof">{html.escape(row["as_of"])}</td>')
        health_body.append("<tr>" + "".join(cells) + "</tr>")
    vix = snapshot["vix"]
    bond = snapshot["yield"]
    intraday = (
        f'<div class="chart chart-ink intra"><p class="axis">SPY · today</p>{snapshot["intraday"]}</div>'
        if snapshot["intraday"] else ""
    )
    body = f"""
<header class="nav-edge">
  <div class="brand"><h1 class="product">GB Market Terminal</h1></div>
  <nav class="bbg-keys" aria-label="Terminal panels">
    <a class="desk-tab" href="regime.html" aria-current="page">Regime</a>
    <a class="desk-tab" href="monitor.html">Monitor</a>
    <a class="desk-tab" href="themes.html">Themes</a>
    <a class="desk-tab" href="liquid.html">Leaders</a>
    <a class="desk-tab" href="rs.html">Setups</a>
    <a class="desk-tab" href="tape.html">Tape</a>
    <a class="desk-tab" href="crowding.html">Crowding</a>
  </nav>
</header>
<p class="lede" role="note"><span class="lede-mark" aria-hidden="true">i</span><span class="visually-hidden">Information. </span>Measured regime, T2108, the day’s breadth and the tape. Every delta is against the prior session.</p>
<main id="regime">
  <div class="top">
    <section class="panel stage" aria-labelledby="stage-label">
      <p class="kicker">Market cycle</p>
      <h2 id="stage-label" class="stage-name stage-{arrow_class}">{stage}</h2>
      <dl class="stage-meta"><div><dt>Since</dt><dd>{html.escape(snapshot["since"])}</dd></div><div><dt>{session_word}</dt><dd>{snapshot["sessions"]}</dd></div></dl>
      <p class="cycle-note cycle-note-{note_kind}" role="note"><span class="lede-mark" aria-hidden="true">{note_mark}</span><span class="visually-hidden">{note_word}. </span>{html.escape(snapshot["progress"])}</p>
    </section>
    <section class="panel cycle" aria-labelledby="cycle-label">
      <h2 id="cycle-label" class="kicker">Stages</h2>
      {cycle_board(snapshot["stage"], snapshot["posture"], snapshot["momentum"])}
      <dl class="facts">
        <div><dt>Breadth thrust</dt><dd>{html.escape(snapshot["thrust"])}</dd></div>
        <div><dt>Nasdaq 40</dt><dd>{html.escape(snapshot["nasdaq_thrust"])}</dd></div>
        <div><dt>Place</dt><dd>{html.escape(snapshot["place"])} <span class="muted">{html.escape(snapshot["distance"])}</span></dd></div>
      </dl>
      <details class="call">
        <summary>How this stage is called</summary>
        <ul class="rules">{rules}</ul>
      </details>
    </section>
    <div class="rail">
    <section class="panel t2108" aria-labelledby="t2108-label">
      <h2 id="t2108-label" class="kicker">Above the 40-day average</h2>
      <div class="readings">
        <div>
          <p class="kicker">T2108 · NYSE</p>
          <p class="figure figure-xl">{snapshot["t2108"]}</p>
          <p class="sub">{snapshot["t2108_delta"]} <span class="muted">vs prior close</span></p>
          <p class="meta">10-day EMA {snapshot["ema10"]} · {snapshot["ema_note"]}</p>
          <p class="meta">6 months {snapshot["low6"]}–{snapshot["high6"]}</p>
        </div>
        <div>
          <p class="kicker">Nasdaq 40</p>
          <p class="figure figure-xl">{snapshot["nasdaq"]}</p>
          <p class="sub">{snapshot["nasdaq_delta"]} <span class="muted">vs prior close</span></p>
          <p class="meta">10-day EMA {snapshot["nasdaq_ema10"]} · {snapshot["nasdaq_note"]}</p>
          <p class="meta">thrust · {html.escape(snapshot["nasdaq_thrust"])}</p>
        </div>
      </div>
      <div class="chart-row">
        <div class="chart chart-ink grow">
          {snapshot["t2108_chart"]}
          <p class="axis"><span>NYSE · {html.escape(snapshot["chart_start"])}</span><span>today</span></p>
        </div>
        <div class="chart chart-ink grow">
          {snapshot["nasdaq_chart"]}
          <p class="axis"><span>Nasdaq</span><span>today</span></p>
        </div>
        {intraday}
      </div>
    </section>
    <section class="group" aria-labelledby="breadth-label">
      <h2 id="breadth-label" class="kicker">Breadth</h2>
      <div class="cards">{breadth}</div>
    </section>
    </div>
  </div>
  <section class="group" aria-labelledby="tape-label">
    <h2 id="tape-label" class="kicker">Tape</h2>
    <div class="cards cards-tape">
      {tape}
      <article class="panel">
        <h3><a href="https://www.tradingview.com/chart/?symbol=TVC:VIX&amp;interval=D">VIX</a></h3>
        <p class="figure">{vix["price"]}</p>
        <p class="sub">{vix["delta"]} <span class="muted">{html.escape(vix["band"])} · day {html.escape(vix["day"])}</span></p>
      </article>
      <article class="panel">
        <h3><a href="https://www.tradingview.com/chart/?symbol=TVC:US10Y&amp;interval=D">10-year yield</a></h3>
        <p class="figure">{bond["price"]}</p>
        <p class="sub">{bond["delta"]} <span class="muted">{html.escape(bond["side"])}</span></p>
      </article>
    </div>
  </section>
  <section class="panel health" aria-labelledby="health-label">
    <h2 id="health-label" class="kicker">Index health</h2>
    <p class="meta">Daily EMAs. Slopes compare with the prior session.</p>
    <div class="health-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Index</th>
            <th scope="col">5 &gt; 10</th>
            <th scope="col">10 &gt; 20</th>
            <th scope="col">10 slope</th>
            <th scope="col">20 slope</th>
            <th scope="col">Price &gt; 10</th>
            <th scope="col">Price &gt; 20</th>
            <th scope="col">RSI 14</th>
            <th scope="col">As of</th>
          </tr>
        </thead>
        <tbody>
          {"".join(health_body)}
        </tbody>
      </table>
    </div>
  </section>
</main>
<p class="foot">T2108 is the share of liquid NYSE names above their 40-day average ({snapshot["n_nyse"]:,} names). Nasdaq 40 is that share for liquid Nasdaq names ({snapshot["n_nasdaq"]:,} names). The other breadth counts use {snapshot["n"]:,} names. Not an instruction to trade.</p>
<script src="shadcn-charts.js?v=20261015g"></script>
<script>
function closeDeskMenus() {{
  document.querySelectorAll(".desk-menu__panel").forEach(panel => {{
    panel.hidden = true;
    const toggle = document.querySelector(`[aria-controls="${{panel.id}}"]`);
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }});
}}
document.addEventListener("click", event => {{
  const toggle = event.target.closest(".desk-tab[aria-haspopup]");
  if (toggle) {{
    const panel = document.getElementById(toggle.getAttribute("aria-controls"));
    const open = toggle.getAttribute("aria-expanded") === "true";
    closeDeskMenus();
    if (!open && panel) {{
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    }}
    return;
  }}
  if (!event.target.closest(".desk-menu")) closeDeskMenus();
}});
document.addEventListener("keydown", event => {{
  if (event.key === "Escape") closeDeskMenus();
  const menu = event.target.closest(".desk-menu__panel");
  if (menu && (event.key === "ArrowDown" || event.key === "ArrowUp")) {{
    const items = [...menu.querySelectorAll("a")];
    const index = items.indexOf(document.activeElement);
    const next = event.key === "ArrowDown" ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
    event.preventDefault();
    items[next]?.focus();
  }}
}});
if (window.GBCharts) GBCharts.upgradeRegime(document);
</script>
"""
    return HTML_PAGE.replace("__BODY__", body)


def tape_cards(closes: pd.DataFrame) -> list[dict]:
    cards = []
    for name, symbol, span, url in TAPE:
        series = closes[symbol].dropna().astype(float)
        price = float(series.iloc[-1])
        previous = float(series.iloc[-2])
        change = (price / previous - 1) * 100
        line = float(ema(series, span).iloc[-1])
        side = "above" if price >= line else "below"
        stroke = "up" if price >= line else "down"
        cards.append({
            "name": name,
            "price": price,
            "change": change,
            "relation": f"{side} {span} EMA",
            "series": [float(value) for value in series.iloc[-63:]],
            "url": url,
            "stroke": stroke,
        })
    return cards


def quote_side(closes: pd.DataFrame, symbol: str, vix_range: pd.Series) -> tuple[dict, dict]:
    vix = closes["^VIX"].dropna().astype(float)
    level = float(vix.iloc[-1])
    if level < 13:
        band = "low"
    elif level < 20:
        band = "normal"
    elif level < 30:
        band = "elevated"
    else:
        band = "stress"
    high = float(vix_range["high"]) if finite(vix_range.get("high")) else level
    low = float(vix_range["low"]) if finite(vix_range.get("low")) else level
    bond = closes["^TNX"].dropna().astype(float)
    yld = float(bond.iloc[-1])
    if yld > 20:
        yld = yld / 10
    gap = yld - 5
    if gap > 0.005:
        side = "above 5.0"
    elif gap < -0.005:
        side = "below 5.0"
    else:
        side = "at 5.0"
    return (
        {"price": f"{level:.2f}", "delta": _delta(level - float(vix.iloc[-2]), 2, invert=True), "band": band, "day": f"{low:.2f}–{high:.2f}"},
        {"price": f"{yld:.2f}", "delta": _delta(gap, 2), "side": side},
    )


def health_rows(closes: pd.DataFrame, as_of: str) -> list[dict]:
    rows = []
    for symbol in HEALTH:
        close = closes[symbol].dropna().astype(float)
        ema5 = ema(close, 5)
        ema10 = ema(close, 10)
        ema20 = ema(close, 20)
        last = close.index[-1]
        prev = close.index[-2]
        reading = float(rsi(close).iloc[-1])
        rows.append({
            "symbol": symbol,
            "ema5_above_10": bool(ema5.loc[last] > ema10.loc[last]),
            "ema10_above_20": bool(ema10.loc[last] > ema20.loc[last]),
            "ema10_slope": bool(ema10.loc[last] > ema10.loc[prev]),
            "ema20_slope": bool(ema20.loc[last] > ema20.loc[prev]),
            "price_above_10": bool(close.loc[last] > ema10.loc[last]),
            "price_above_20": bool(close.loc[last] > ema20.loc[last]),
            "rsi": f"{reading:.1f}",
            "as_of": as_of,
        })
    return rows


def write_csvs(days: list[dict], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(days)
    keep = [
        "date", "stage", "since", "sessions", "posture", "momentum", "t2108", "t2108_ema10",
        "up4", "down4", "ratio5", "ratio10", "balance", "bull13", "bear13", "bull20", "bear20",
        "up25q", "down25q", "up25m", "down25m", "up50", "down50", "drawdown", "n", "n_nyse",
        "nasdaq", "nasdaq_ema10", "n_nasdaq",
    ]
    history = output_dir / "regime_history.csv"
    frame.loc[:, keep].to_csv(history, index=False)
    stamp = str(days[-1]["date"])
    latest = output_dir / f"regime_{stamp}.csv"
    frame.loc[:, keep].tail(1).to_csv(latest, index=False)
    return [history, latest]


def write_regime(output_dir: Path, max_names: int = 1400, refresh: bool = False) -> list[Path]:
    """Fetch the tape, write the CSVs, and refresh regime.html."""
    universe = fetch_universe(max_names)
    exchange = universe["exchange"].str.upper()
    nyse = pd.Series({name: flag for name, flag in zip(universe["name"], exchange == "NYSE")})
    nasdaq = pd.Series({name: flag for name, flag in zip(universe["name"], exchange == "NASDAQ")})
    closes = load_closes(universe, refresh)
    nyse = nyse.reindex(closes.columns).fillna(False)
    nasdaq = nasdaq.reindex(closes.columns).fillna(False)
    print(f"Breadth panel: {closes.shape[1]} names, {int(nyse.sum())} NYSE, {int(nasdaq.sum())} Nasdaq", flush=True)
    breadth = compute_breadth(closes, nyse, nasdaq)
    index_closes, vix_range, intraday = download_indexes()
    market = market_frame(index_closes)
    days = days_from_frames(breadth, market)
    if len(days) < 30:
        raise RuntimeError("Not enough sessions to read a regime.")
    now = datetime.now(NY_TZ)
    last_session = date.fromisoformat(days[-1]["date"])
    as_of = long_stamp(now, last_session)
    snapshot = build_snapshot(
        days,
        tape_cards(index_closes),
        *quote_side(index_closes, "^VIX", vix_range),
        [float(value) for value in intraday.tolist()],
        as_of,
    )
    session_label = f"{last_session.day} {last_session.strftime('%b')}"
    rows = health_rows(index_closes, session_label)
    HTML_PATH.write_text(render_html(snapshot, rows), encoding="utf-8")
    paths = write_csvs(days, output_dir)
    paths.append(HTML_PATH)
    last = days[-1]
    print(
        f"Regime: {last['stage']} | T2108 {last['t2108']:.1f} | Nasdaq 40 {float(last['nasdaq']):.1f} | 5-day ratio {last['ratio5']:.2f} | posture {last['posture']}",
        flush=True,
    )
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "outputs")
    parser.add_argument("--max-names", type=int, default=1400, help="Most active US names in the breadth panel.")
    parser.add_argument("--refresh", action="store_true", help="Download prices again even if today's cache exists.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = write_regime(args.output_dir, args.max_names, args.refresh)
    print("Saved:\n" + "\n".join(str(path) for path in paths))


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Regime | GB Market Terminal</title>
  <meta name="description" content="Market regime, T2108, breadth, and the index tape.">
  <meta name="robots" content="index, follow">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="preload" href="assets/fonts/newsreader-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/source-sans-3-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css?v=20261015j">
  <style>
    /* Hallmark · pre-emit critique: P5 H4 E4 S5 R4 V4
     * macrostructure: existing desk · tone: austere · anchor hue: cool
     * page: regime · inherits tokens.css
     */
    html { color-scheme: dark; background: var(--color-paper); }
    html, body { overflow-x: clip; margin: 0; }
    body {
      background:
        radial-gradient(72rem 34rem at 55% 0%, oklch(38% 0.06 245 / 0.55), transparent 62%),
        radial-gradient(80rem 46rem at 72% 108%, oklch(48% 0.1 215 / 0.42), transparent 56%),
        radial-gradient(36rem 28rem at 0% 46%, oklch(28% 0.05 270 / 0.35), transparent 54%),
        #0e1116;
      color: var(--color-ink-2);
      font-family: var(--font-body);
      font-size: var(--text-base);
      line-height: 1.35;
      font-variant-numeric: tabular-nums;
    }
    body::before {
      content: "";
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      opacity: 0.28;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }
    .lede, main, .foot { position: relative; z-index: 1; }
    h1, h2, h3, button, a { font-style: normal; }
    h1, h2, h3 { overflow-wrap: anywhere; min-width: 0; }
    .visually-hidden {
      position: absolute; width: 1px; height: 1px; overflow: hidden;
      clip-path: inset(50%); white-space: nowrap;
    }
    .skip-link {
      position: absolute; left: var(--space-sm); top: var(--space-sm);
      z-index: var(--z-sticky-nav); padding: var(--space-xs) var(--space-sm);
      background: var(--color-accent); color: var(--color-accent-ink);
      text-decoration: none; transform: translateY(-200%);
    }
    .skip-link:focus-visible { transform: none; outline: 2px solid var(--color-focus); }
    .nav-edge {
      position: sticky; top: 0; z-index: var(--z-sticky-nav);
      display: flex; align-items: center; gap: var(--space-sm);
      min-height: var(--banner-height);
      padding: 0 var(--page-gutter);
      padding-left: max(var(--page-gutter), env(safe-area-inset-left));
      padding-right: max(var(--page-gutter), env(safe-area-inset-right));
      background: var(--color-paper);
      border-bottom: var(--rule) solid var(--color-rule);
    }
    .brand { display: flex; align-items: center; }
    .product {
      margin: 0; font-family: var(--font-display); font-size: var(--text-md);
      font-weight: 400; letter-spacing: -0.02em; line-height: 1; color: var(--color-ink);
    }
    .bbg-keys { display: flex; flex: 1; min-width: 0; align-items: stretch; flex-wrap: wrap; }
    .desk-menu { position: relative; display: flex; }
    .desk-tab {
      display: flex; align-items: center; gap: var(--space-4);
      margin: 0; padding: 0 var(--space-12); min-height: var(--banner-height);
      border: 0; border-bottom: 2px solid transparent; background: transparent;
      color: var(--color-ink); font-family: var(--font-body); font-size: var(--text-xs);
      text-decoration: none; white-space: nowrap; cursor: pointer;
    }
    .desk-caret {
      width: 0; height: 0;
      border-left: 0.28rem solid transparent; border-right: 0.28rem solid transparent;
      border-top: 0.32rem solid currentColor;
    }
    .desk-tab[aria-current="page"], .desk-tab[aria-expanded="true"] {
      color: var(--color-accent); border-bottom-color: var(--color-accent);
    }
    .desk-tab:hover, .desk-menu__panel a:hover { color: var(--color-accent); }
    .desk-tab:active { color: var(--color-accent); }
    .desk-tab:focus-visible, .desk-menu__panel a:focus-visible, .panel a:focus-visible {
      outline: 2px solid var(--color-focus); outline-offset: 1px;
    }
    .desk-menu__panel {
      position: absolute; top: calc(100% + 1px); left: 0; z-index: 1;
      display: flex; flex-direction: column; min-width: 13.5rem;
      padding: var(--space-4) 0; background: var(--color-paper);
      border: var(--rule) solid var(--color-rule);
    }
    .desk-menu__panel[hidden] { display: none; }
    .desk-menu__panel a {
      display: flex; align-items: center; min-height: 2.75rem; padding: 0 var(--space-sm);
      color: var(--color-ink); font-size: var(--text-xs); text-decoration: none; white-space: nowrap;
    }
    .lede, .foot {
      margin: 0; padding: var(--space-sm) var(--page-gutter) 0;
      padding-left: max(var(--page-gutter), env(safe-area-inset-left));
      padding-right: max(var(--page-gutter), env(safe-area-inset-right));
      color: var(--color-muted); font-size: var(--text-xs);
    }
    .lede {
      display: flex; align-items: center; gap: var(--space-sm);
      margin: var(--space-8) var(--page-gutter) 0;
      margin-left: max(var(--page-gutter), env(safe-area-inset-left));
      margin-right: max(var(--page-gutter), env(safe-area-inset-right));
      padding: var(--space-8) var(--space-md);
      background: color-mix(in oklch, var(--color-up) 12%, var(--color-paper-3));
      border: var(--rule) solid color-mix(in oklch, var(--color-up) 42%, var(--color-rule));
      border-radius: 12px;
      color: var(--color-ink-2); line-height: 1.4;
    }
    .lede-mark {
      flex: none; display: inline-flex; align-items: center; justify-content: center;
      width: 1rem; height: 1rem; border: var(--rule) solid var(--color-up); border-radius: 50%;
      color: var(--color-up); font-size: 11px; line-height: 1;
    }
    .foot { padding-bottom: var(--space-xl); max-width: 72rem; }
    main {
      display: flex; flex-direction: column; gap: var(--space-sm);
      padding: var(--space-sm) var(--page-gutter) var(--space-lg);
      padding-left: max(var(--page-gutter), env(safe-area-inset-left));
      padding-right: max(var(--page-gutter), env(safe-area-inset-right));
    }
    .top { display: grid; grid-template-columns: minmax(16rem, 22rem) minmax(0, 1fr); gap: var(--space-sm); align-items: start; }
    .rail { display: contents; }
    .top > .stage { grid-column: 1 / -1; grid-row: 1; }
    .top > .cycle { grid-column: 1; grid-row: 2; }
    .rail > .t2108 { grid-column: 2; grid-row: 2; }
    .rail > .group { grid-column: 1 / -1; }
    .rail .cards { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .cards, .cards-tape { display: grid; gap: var(--space-sm); }
    .cards { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .cards-tape { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .panel {
      min-width: 0;
      background: color-mix(in oklch, var(--color-paper-3) 46%, transparent);
      border: var(--rule) solid color-mix(in oklch, white 28%, transparent);
      border-radius: 12px;
      box-shadow: inset 0 1px 0 color-mix(in oklch, white 32%, transparent);
      backdrop-filter: blur(14px) saturate(1.35);
      -webkit-backdrop-filter: blur(14px) saturate(1.35);
      padding: var(--space-sm) var(--space-md) var(--space-md);
    }
    @media (prefers-reduced-transparency: reduce) {
      body { background: var(--color-paper); }
      body::before { display: none; }
      .panel {
        background: var(--color-paper-3);
        border-color: var(--color-rule);
        box-shadow: none;
        backdrop-filter: none;
      }
    }
    .kicker {
      margin: 0 0 var(--space-8); font-family: var(--font-body); font-size: var(--text-xs);
      font-weight: 400; letter-spacing: 0.04em; text-transform: uppercase; color: var(--color-muted);
    }
    /* Hallmark · component: status card · genre: editorial · theme: terminal
     * states: default · hover · focus · active
     * contrast: pass
     */
    .panel.cycle { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); column-gap: var(--space-md); align-items: start; }
    .panel.cycle > * { grid-column: 1 / -1; }
    .panel.cycle .steps { grid-column: 1; }
    .panel.cycle .facts { grid-column: 2; margin-top: var(--space-md); }
    .panel.cycle .facts div { flex-direction: column; align-items: flex-start; gap: 2px; }
    .panel.cycle .facts dd { text-align: left; }
    .stage-name {
      margin: 0;
      font-family: var(--font-display); font-size: clamp(2.5rem, 4vw + 1rem, 3.5rem);
      font-weight: 400; letter-spacing: -0.03em; line-height: 0.95; text-transform: none;
    }
    .stage-down { color: var(--color-down); }
    .stage-up { color: var(--color-up); }
    .stage-meta { display: flex; gap: var(--space-xl); margin: var(--space-sm) 0 0; padding: 0; }
    .stage-meta div { display: flex; flex-direction: column; gap: 2px; min-width: 6rem; }
    .stage-meta dt {
      margin: 0; font-family: var(--font-body); font-size: var(--text-xs); font-weight: 400;
      letter-spacing: 0.04em; text-transform: uppercase; color: var(--color-muted);
    }
    .stage-meta dd {
      margin: 0; font-family: var(--font-display); font-size: var(--text-lg); font-weight: 400;
      letter-spacing: -0.02em; line-height: 1.1; color: var(--color-ink);
    }
    .stage-meta + .cycle-note { margin-top: var(--space-sm); }
    .cycle-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); }
    .cycle-head .kicker { margin: 0; }
    .badge {
      display: inline-flex; align-items: center; gap: var(--space-4); margin: 0;
      padding: var(--space-4) var(--space-8); border: var(--rule) solid var(--color-rule);
      font-family: var(--font-body); font-size: var(--text-xs); line-height: 1;
      color: var(--color-ink); white-space: nowrap;
    }
    .badge-down { color: var(--color-down); border-color: var(--color-down); --arrow: var(--color-down); }
    .badge-up { color: var(--color-up); border-color: var(--color-up); --arrow: var(--color-up); }
    .cycle-note {
      display: flex; align-items: center; gap: var(--space-sm);
      margin: var(--space-8) 0 0; padding: var(--space-8) var(--space-md);
      border-radius: 8px; font-size: var(--text-xs); line-height: 1.45; color: var(--color-ink-2);
    }
    .cycle-note-down {
      background: color-mix(in oklch, var(--color-warn) 16%, var(--color-paper-3));
      border: var(--rule) solid color-mix(in oklch, var(--color-warn) 48%, var(--color-rule));
    }
    .cycle-note-up {
      background: color-mix(in oklch, var(--color-series-1) 16%, var(--color-paper-3));
      border: var(--rule) solid color-mix(in oklch, var(--color-series-1) 48%, var(--color-rule));
    }
    .cycle-note-down .lede-mark { border-color: var(--color-warn); color: var(--color-warn); }
    .cycle-note-up .lede-mark { border-color: var(--color-series-1); color: var(--color-series-1); }
    .cycle-stats { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-sm); margin-top: var(--space-md); }
    .cycle-stats .figure { margin: 0; }
    .cycle-stats .meta { margin: var(--space-4) 0 0; }
    .meter { height: 4px; margin-top: var(--space-sm); background: var(--color-paper); }
    .meter-fill { display: block; height: 100%; background: var(--color-accent); }
    .steps { list-style: none; display: flex; flex-direction: column; margin: var(--space-md) 0 0; padding: 0; }
    .step {
      position: relative; display: flex; align-items: center; gap: var(--space-8);
      min-height: 1.65rem; color: var(--color-muted); font-size: var(--text-xs); line-height: 1.3;
    }
    .step::before {
      content: ""; width: 7px; height: 7px; flex: 0 0 auto;
      border: var(--rule) solid var(--color-rule-2); border-radius: 50%; background: transparent;
    }
    .step:not(:last-child)::after {
      content: ""; position: absolute; left: 3px; top: 1.15rem; width: 1px; height: calc(100% - 0.55rem);
      background: var(--color-rule);
    }
    .step.is-current { color: var(--color-ink); }
    .step-down.is-current::before { background: var(--color-down); border-color: var(--color-down); }
    .step-up.is-current::before { background: var(--color-up); border-color: var(--color-up); }
    .step-ink.is-current::before { background: var(--color-accent); border-color: var(--color-accent); }
    .facts { margin: var(--space-md) 0 0; }
    .facts div {
      display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-sm);
      padding: var(--space-8) 0; border-top: var(--rule) solid var(--color-rule);
    }
    .facts dt, .facts dd { margin: 0; font-size: var(--text-xs); }
    .facts dt { color: var(--color-muted); }
    .facts dd { color: var(--color-ink); text-align: right; }
    .call { margin-top: var(--space-xs); }
    .call summary {
      cursor: pointer; color: var(--color-muted); font-size: var(--text-xs);
    }
    .call summary:hover { color: var(--color-ink); }
    .call summary:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
    .call summary:active { color: var(--color-accent); }
    .call[open] summary { color: var(--color-ink); }
    .mark-up { color: var(--color-accent); }
    .mark-down { color: var(--color-down); }
    .since, .place, .meta, .sub { margin: var(--space-8) 0 0; font-size: var(--text-xs); color: var(--color-ink-2); }
    .muted { color: var(--color-muted); }
    .figure {
      margin: var(--space-4) 0 0; font-family: var(--font-display); font-size: var(--text-lg);
      font-weight: 400; letter-spacing: -0.03em; line-height: 1; color: var(--color-ink);
    }
    .figure-xl { font-size: var(--text-display); }
    .readings .kicker {
      font-family: var(--font-body); font-size: var(--text-display); font-weight: 400;
      letter-spacing: -0.01em; text-transform: none; color: var(--color-ink); line-height: 1.1;
    }
    .readings .figure-xl { font-size: var(--text-md); }
    .readings .sub, .readings .meta { font-size: var(--text-xs); }
    .rules { margin: var(--space-sm) 0 0; padding-left: 1.1rem; font-size: var(--text-xs); color: var(--color-ink-2); }
    .rules li { margin: var(--space-4) 0; }
    .rules li::marker { color: var(--color-accent); }
    h3 {
      margin: 0; font-family: var(--font-display); font-size: var(--text-display); font-weight: 400;
      letter-spacing: -0.02em; text-transform: none; color: var(--color-ink); line-height: 1.1;
    }
    .cards .figure { font-size: var(--text-md); }
    h3 a { color: inherit; text-decoration: none; }
    h3 a:hover { color: var(--color-accent); }
    .delta { display: inline-flex; align-items: baseline; gap: 0.28em; font-variant-numeric: tabular-nums; white-space: nowrap; line-height: 1; }
    .mark, .arr {
      position: relative; display: inline-block; width: 0.55em; height: 0.42em;
      overflow: hidden; line-height: 0; color: transparent; vertical-align: middle; flex: none;
    }
    .delta .arr { transform: translateY(-0.16em); }
    .mark::before, .arr::before { content: ""; position: absolute; inset: 0; background: var(--arrow); }
    .mark-up::before, .arr-up::before { clip-path: polygon(50% 0, 0 100%, 100% 100%); }
    .mark-down::before, .arr-down::before { clip-path: polygon(50% 100%, 0 0, 100% 0); }
    .arr-flat::before { clip-path: polygon(0 0, 100% 50%, 0 100%); }
    .delta-up { color: var(--color-up); --arrow: var(--color-up); }
    .delta-down { color: var(--color-down); --arrow: var(--color-down); }
    .delta-flat { color: var(--color-muted); --arrow: var(--color-muted); }
    .chart { min-width: 0; margin-top: var(--space-8); }
    .chart svg { display: block; width: 100%; height: 2.4rem; }
    .chart polyline, .chart circle { fill: none; stroke: var(--color-ink); stroke-width: 1.4; }
    .chart circle { fill: var(--color-ink); stroke: none; }
    .chart-up polyline, .chart-up circle { stroke: var(--color-up); fill: none; }
    .chart-up circle { fill: var(--color-up); }
    .chart-down polyline, .chart-down circle { stroke: var(--color-down); }
    .chart-down circle { fill: var(--color-down); }
    .guide { stroke: var(--color-rule-2); stroke-dasharray: 2 3; stroke-width: 1; }
    .bar-up { fill: var(--color-up); }
    .bar-down { fill: var(--color-down); }
    .panel.t2108 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); column-gap: var(--space-md); row-gap: var(--space-8); }
    .panel.t2108 > .kicker { grid-column: 1 / -1; grid-row: 1; }
    .readings, .chart-row { display: contents; }
    .readings > :first-child { grid-column: 1; grid-row: 2; }
    .readings > :last-child { grid-column: 2; grid-row: 2; }
    .chart-row > .grow:nth-child(1) { grid-column: 1; grid-row: 3; }
    .chart-row > .grow:nth-child(2) { grid-column: 2; grid-row: 3; }
    .panel.t2108 .chart-row .chart .shadcn-host { height: 9rem; }
    .chart-row .chart svg { height: 8rem; }
    .chart-row .grow > .axis { display: none; }
    .chart-row > .intra {
      grid-column: 1 / -1; grid-row: 4;
      display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center;
      column-gap: var(--space-md); margin-top: var(--space-4);
      padding-top: var(--space-sm); border-top: var(--rule) solid var(--color-rule);
    }
    .panel.t2108 .chart-row .intra .shadcn-host,
    .chart-row > .intra svg { height: 4.5rem; }
    .chart-row > .intra .axis { margin: 0; justify-content: flex-start; white-space: nowrap; }
    .axis { display: flex; justify-content: space-between; margin: var(--space-4) 0 0; color: var(--color-muted); font-size: var(--text-xs); }
    .health-wrap { overflow-x: auto; margin-top: var(--space-sm); }
    table { width: 100%; border-collapse: collapse; font-size: var(--text-xs); }
    th, td { padding: var(--space-8) var(--space-sm); text-align: center; border-bottom: var(--rule) solid var(--color-rule); white-space: nowrap; font-weight: 400; }
    th { color: var(--color-muted); }
    th:first-child, td:first-child { text-align: left; position: sticky; left: 0; background: transparent; }
    td.yes, td.up { color: var(--color-up); }
    td.no, td.down { color: var(--color-down); }
    td.num, td.asof { color: var(--color-ink); }
    @media (max-width: 72rem) {
      .cards, .cards-tape { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    @media (max-width: 56rem) {
      .top { grid-template-columns: minmax(0, 1fr); }
      .top > .stage, .top > .cycle, .rail > .t2108, .rail > .group { grid-column: 1; grid-row: auto; }
      .nav-edge { flex-wrap: wrap; padding-top: var(--space-8); padding-bottom: var(--space-8); }
    }
    @media (max-width: 40rem) {
      :root { --page-gutter: var(--space-12); }
      .cards, .cards-tape, .rail .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .panel.t2108 { grid-template-columns: minmax(0, 1fr); }
      .readings > :first-child { grid-column: 1; grid-row: 2; }
      .chart-row > .grow:nth-child(1) { grid-column: 1; grid-row: 3; }
      .readings > :last-child { grid-column: 1; grid-row: 4; }
      .chart-row > .grow:nth-child(2) { grid-column: 1; grid-row: 5; }
      .chart-row > .intra { grid-column: 1; grid-row: 6; }
      .desk-tab { padding: 0 var(--space-8); min-height: 2.75rem; }
    }
    @media (max-width: 22.5rem) {
      .cards, .cards-tape { grid-template-columns: minmax(0, 1fr); }
    }
    @media (prefers-reduced-motion: reduce) {
      .desk-tab, .skip-link { transition: none; }
    }
  </style>
  <link rel="stylesheet" href="nav.css?v=20261015m">
  <link rel="stylesheet" href="charts.css?v=20261015d">
  <link rel="stylesheet" href="shadcn-chart.css?v=20261015g">
</head>
<body>
<a class="skip-link" href="#regime">Skip to regime</a>
__BODY__
</body>
</html>
"""


if __name__ == "__main__":
    main()
