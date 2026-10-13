#!/usr/bin/env python3
"""Fit the breadth-improvement signal to historical S&P bottoms.

Bottoms are labeled from the S&P 500 only, after the fact: a decline of at
least 15% from a peak, confirmed when price later rallies 8% off the low.
The signal itself uses only information available that session. The universe
is today's liquid names, so early readings miss companies that no longer trade.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pandas as pd

from regime import BATCH_SIZE, CACHE_PATH, rolling_ratio


STUDY_CACHE = CACHE_PATH.with_name(".regime_study_closes.pkl")
START = "1998-01-01"
MIN_NYSE = 80
DRAWDOWN = 0.15
CONFIRM_RALLY = 0.08
HIT_WINDOW = 20
CLUSTER = 10


def download_long(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    from regime import _as_dates, _field

    frames: list[pd.DataFrame] = []
    batches = [tickers[index:index + BATCH_SIZE] for index in range(0, len(tickers), BATCH_SIZE)]
    for number, batch in enumerate(batches, start=1):
        print(f"Prices {number}/{len(batches)}", flush=True)
        raw = yf.download(batch, start=START, auto_adjust=True, progress=False, threads=True, group_by="column")
        if raw is None or raw.empty:
            continue
        close = _as_dates(_field(raw, "Close"))
        close = close.loc[:, ~close.columns.duplicated()]
        frames.append(close)
    if not frames:
        raise RuntimeError("No price history returned.")
    panel = pd.concat(frames, axis=1)
    panel = panel.loc[:, ~panel.columns.duplicated()]
    return panel.dropna(axis=1, how="all").dropna(axis=0, how="all")


def load_panel() -> tuple[pd.DataFrame, list[str]]:
    cached = pickle.loads(CACHE_PATH.read_bytes())
    names = list(cached["names"])
    nyse = list(cached["nyse"])
    if STUDY_CACHE.exists():
        study = pickle.loads(STUDY_CACHE.read_bytes())
        if study.get("names") == names and study.get("start") == START:
            print("Using study cache", flush=True)
            return study["closes"], nyse
    closes = download_long(names + ["^GSPC"])
    STUDY_CACHE.write_bytes(pickle.dumps({"names": names, "nyse": nyse, "start": START, "closes": closes}))
    return closes, nyse


def breadth(closes: pd.DataFrame, nyse: list[str]) -> pd.DataFrame:
    nyse_names = [name for name in nyse if name in closes.columns]
    panel = closes.drop(columns=["^GSPC"], errors="ignore")
    sma40 = panel.rolling(40, min_periods=40).mean()
    above = panel[nyse_names].gt(sma40[nyse_names])
    ready = sma40[nyse_names].notna().sum(axis=1)
    t2108 = above.sum(axis=1) / ready.where(ready >= MIN_NYSE) * 100
    pct = panel.pct_change() * 100
    up4 = pct.ge(4).sum(axis=1)
    down4 = pct.le(-4).sum(axis=1)
    frame = pd.DataFrame({
        "t2108": t2108,
        "ready": ready,
        "ratio5": rolling_ratio(up4, down4, 5),
        "up4": up4,
        "down4": down4,
    })
    frame["ema10"] = frame["t2108"].ewm(span=10, adjust=False).mean()
    return frame.dropna(subset=["t2108"])


def label_bottoms(spx: pd.Series, drawdown: float = DRAWDOWN) -> list[dict]:
    """Low of each decline of `drawdown` or more from the trailing high.

    The low counts only once price has gone on to a new trailing high without
    undercutting it. A rally that fails is not a bottom.
    """
    px = spx.dropna()
    trail = px.rolling(252, min_periods=63).max()
    in_drawdown = False
    trough = 0.0
    trough_at = px.index[0]
    origin = 0.0
    events: list[dict] = []
    for stamp, value in px.items():
        price = float(value)
        high = trail.loc[stamp]
        if pd.isna(high):
            continue
        high = float(high)
        if not in_drawdown:
            if price <= high * (1 - drawdown):
                in_drawdown = True
                trough = price
                trough_at = stamp
                origin = high
            continue
        if price < trough:
            trough = price
            trough_at = stamp
            continue
        # A new trailing high, after the low, means the low held.
        if price >= high and stamp > trough_at:
            events.append({
                "date": pd.Timestamp(trough_at).strftime("%Y-%m-%d"),
                "drawdown": round(trough / origin - 1, 4),
                "low": round(trough, 2),
            })
            in_drawdown = False
    return events


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["delta"] = out["t2108"].diff()
    out["accel"] = out["delta"].diff()
    out["ema_delta"] = out["ema10"].diff()
    for window in (2, 3, 5):
        out[f"rise_{window}"] = out["t2108"].diff(window)
        out[f"ema_rise_{window}"] = out["ema10"].diff(window)
        out[f"start_{window}"] = out["t2108"].shift(window)
    return out


def signal_mask(frame: pd.DataFrame, window: int, points: float, ratio: float, cap: float, need_accel: bool, need_lead: bool) -> pd.Series:
    rise = frame[f"rise_{window}"]
    mask = rise >= points
    if cap < 100:
        mask = mask & (frame[f"start_{window}"] <= cap)
    if ratio > 0:
        mask = mask & (frame["ratio5"] >= ratio)
    if need_accel:
        mask = mask & (frame["accel"] > 0)
    if need_lead:
        mask = mask & (rise > frame[f"ema_rise_{window}"])
    return mask.fillna(False)


def clusters(dates: list[pd.Timestamp]) -> list[pd.Timestamp]:
    events: list[pd.Timestamp] = []
    last: pd.Timestamp | None = None
    for stamp in dates:
        if last is None or (stamp - last).days > CLUSTER:
            events.append(stamp)
        last = stamp
    return events


def score_rule(frame: pd.DataFrame, bottoms: list[dict], mask: pd.Series) -> dict:
    index = frame.index
    sessions = {stamp: position for position, stamp in enumerate(index)}
    hit_windows: list[tuple[int, int]] = []
    for bottom in bottoms:
        stamp = pd.Timestamp(bottom["date"])
        if stamp not in sessions:
            continue
        start = sessions[stamp]
        hit_windows.append((start, min(start + HIT_WINDOW, len(index) - 1)))
    flagged = list(index[mask.to_numpy()])
    events = clusters(flagged)
    hits = 0
    false = 0
    leads: list[int] = []
    caught: set[int] = set()
    for event in events:
        position = sessions[event]
        matched = None
        for number, (start, stop) in enumerate(hit_windows):
            if start <= position <= stop:
                matched = number
                leads.append(position - start)
                break
        if matched is None:
            false += 1
        elif matched not in caught:
            caught.add(matched)
            hits += 1
    eligible = len(hit_windows)
    years = max((index[-1] - index[0]).days / 365.25, 1)
    return {
        "bottoms": eligible,
        "hits": hits,
        "recall": round(hits / eligible, 3) if eligible else 0,
        "false": false,
        "false_per_year": round(false / years, 2),
        "median_lead": None if not leads else int(sorted(leads)[len(leads) // 2]),
    }


def grid(frame: pd.DataFrame, bottoms: list[dict]) -> list[dict]:
    rows = []
    for window in (2, 3, 5):
        for points in (5, 6, 8, 10, 12, 15):
            for ratio in (0.0, 1.0, 1.5):
                for cap in (30, 40, 50, 100):
                    for need_accel in (False, True):
                        for need_lead in (False, True):
                            stats = score_rule(
                                frame,
                                bottoms,
                                signal_mask(frame, window, points, ratio, cap, need_accel, need_lead),
                            )
                            if stats["hits"] == 0:
                                continue
                            stats.update({
                                "window": window,
                                "points": points,
                                "ratio": ratio,
                                "cap": cap,
                                "accel": need_accel,
                                "lead": need_lead,
                            })
                            precision_den = stats["hits"] + stats["false"]
                            stats["precision"] = round(stats["hits"] / precision_den, 3) if precision_den else 0
                            stats["f1"] = round(
                                2 * stats["precision"] * stats["recall"] / (stats["precision"] + stats["recall"]),
                                3,
                            ) if stats["precision"] + stats["recall"] else 0
                            rows.append(stats)
    rows.sort(key=lambda row: (row["recall"] < 0.7, row["false_per_year"], -row["recall"], -row["precision"]))
    return rows


def bottom_detail(frame: pd.DataFrame, spx: pd.Series, bottoms: list[dict]) -> list[dict]:
    index = list(frame.index)
    lookup = {stamp: position for position, stamp in enumerate(index)}
    rows = []
    for bottom in bottoms:
        stamp = pd.Timestamp(bottom["date"])
        if stamp not in lookup:
            continue
        position = lookup[stamp]
        stop = min(position + HIT_WINDOW, len(index) - 1)
        window = frame.iloc[position:stop + 1]
        prior = frame.iloc[max(0, position - HIT_WINDOW):position]
        best_at = window["rise_3"].idxmax()
        best = window.loc[best_at]
        spx_low = float(spx.loc[stamp])
        later = spx.iloc[position:min(position + 63, len(spx) - 1)]
        rows.append({
            "date": bottom["date"],
            "drawdown": bottom["drawdown"],
            "t2108": round(float(frame.iloc[position]["t2108"]), 1),
            "ema10": round(float(frame.iloc[position]["ema10"]), 1),
            "ready": int(frame.iloc[position]["ready"]),
            "max_rise_3_after": round(float(window["rise_3"].max()), 1),
            "max_rise_3_before": None if prior.empty else round(float(prior["rise_3"].max()), 1),
            "best_day": pd.Timestamp(best_at).strftime("%Y-%m-%d"),
            "lead_sessions": int(lookup[pd.Timestamp(best_at)] - position),
            "accel": round(float(best["accel"]), 2) if pd.notna(best["accel"]) else None,
            "ratio5": round(float(best["ratio5"]), 2) if pd.notna(best["ratio5"]) else None,
            "started": round(float(best["start_3"]), 1) if pd.notna(best["start_3"]) else None,
            "ema_rise_3": round(float(best["ema_rise_3"]), 1) if pd.notna(best["ema_rise_3"]) else None,
            "rally_63": round(float(later.iloc[-1]) / spx_low - 1, 3),
        })
    return rows


def aligned(frame: pd.DataFrame, spx: pd.Series, bottoms: list[dict]) -> dict:
    offsets = list(range(-10, 16))
    t_rows = []
    p_rows = []
    lookup = {stamp: position for position, stamp in enumerate(frame.index)}
    for bottom in bottoms:
        stamp = pd.Timestamp(bottom["date"])
        if stamp not in lookup:
            continue
        position = lookup[stamp]
        base = float(spx.iloc[position])
        t_vals = []
        p_vals = []
        for offset in offsets:
            spot = position + offset
            if spot < 0 or spot >= len(frame):
                t_vals.append(None)
                p_vals.append(None)
                continue
            t_vals.append(round(float(frame.iloc[spot]["t2108"]), 2))
            p_vals.append(round(float(spx.iloc[spot]) / base - 1, 4))
        t_rows.append(t_vals)
        p_rows.append(p_vals)
    def median(rows: list[list[float | None]]) -> list[float | None]:
        out = []
        for column in range(len(offsets)):
            values = sorted(row[column] for row in rows if row[column] is not None)
            out.append(None if not values else round(values[len(values) // 2], 2))
        return out
    return {"offsets": offsets, "t2108": median(t_rows), "spx": median(p_rows), "bottoms": len(t_rows)}


def main() -> None:
    closes, nyse = load_panel()
    spx = closes["^GSPC"].dropna()
    tape = breadth(closes, nyse)
    tape = tape.loc[tape.index.intersection(spx.index)]
    spx = spx.reindex(tape.index)
    frame = prepare(tape)
    bottoms = [row for row in label_bottoms(spx) if pd.Timestamp(row["date"]) in frame.index]
    details = bottom_detail(frame, spx, bottoms)
    path = aligned(frame, spx, bottoms)
    rules = grid(frame, bottoms)
    sessions = {stamp: position for position, stamp in enumerate(frame.index)}

    def missed_on(spec: dict) -> list[str]:
        mask = signal_mask(frame, spec["window"], spec["points"], spec["ratio"], spec["cap"], spec["accel"], spec["lead"])
        flagged = set(frame.index[mask.to_numpy()])
        missed = []
        for bottom in bottoms:
            start = sessions.get(pd.Timestamp(bottom["date"]))
            if start is None:
                missed.append(bottom["date"])
                continue
            window = frame.index[start:min(start + HIT_WINDOW, len(frame) - 1) + 1]
            if not any(stamp in flagged for stamp in window):
                missed.append(bottom["date"])
        return missed

    for spec in rules[:5]:
        spec["missed"] = missed_on(spec)
    current = signal_mask(frame, 3, 8, 1.0, 100, True, True)
    current_score = score_rule(frame, bottoms, current)
    current_score.update({"window": 3, "points": 8, "ratio": 1.0, "cap": 100, "accel": True, "lead": True, "name": "current"})
    train = [row for row in bottoms if row["date"] < "2019-01-01"]
    test = [row for row in bottoms if row["date"] >= "2019-01-01"]
    train_rules = grid(frame, train) if train else []
    holdout = None
    if train_rules and test:
        best = train_rules[0]
        holdout = score_rule(
            frame,
            test,
            signal_mask(frame, best["window"], best["points"], best["ratio"], best["cap"], best["accel"], best["lead"]),
        )
        holdout.update({key: best[key] for key in ("window", "points", "ratio", "cap", "accel", "lead")})
    payload = {
        "sample": {
            "start": str(frame.index[0].date()),
            "end": str(frame.index[-1].date()),
            "sessions": int(len(frame)),
            "nyse_floor": MIN_NYSE,
            "median_ready": int(frame["ready"].median()),
            "min_ready": int(frame["ready"].min()),
        },
        "bottoms": details,
        "path": path,
        "current": current_score,
        "fitted": rules[:8],
        "train_best": train_rules[0] if train_rules else None,
        "holdout": holdout,
        "train_bottoms": len(train),
        "test_bottoms": len(test),
    }
    out = Path(__file__).resolve().parent / "outputs" / "regime_bottom_study.json"
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"sample": payload["sample"], "bottoms": details, "current": current_score, "fitted": rules[:5], "holdout": holdout}, indent=2))


if __name__ == "__main__":
    main()
