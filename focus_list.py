#!/usr/bin/env python3
"""Build a daily, non-extended momentum-leader focus list from TradingView."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timezone
from math import ceil
from pathlib import Path
from typing import Iterable

import pandas as pd

from industry_flow_dashboard import write_dashboard


@dataclass(frozen=True)
class Settings:
    min_dollar_volume: float = 30_000_000
    min_adr_pct: float = 4.0
    min_avg_volume_10d: int = 350_000
    top_pct: float = 0.01
    max_atr_extension: float = 4.0


@dataclass(frozen=True)
class FocusSettings:
    """Jeff hard-rule overlays plus the planned EMA/tightness layer. Never changes NEL."""

    max_lod_atr_pct: float = 60.0
    max_day_range_atr: float = 1.0
    min_rvol: float = 1.5
    mega_cap: float = 10_000_000_000
    near_sma20_pct: float = 0.03
    earnings_days: int = 3
    large_gap_pct: float = 2.0
    near_ema_atr: float = 1.5
    adr_tight_frac: float = 0.75
    max_bb_width: float = 0.10
    rvol_expand: float = 1.2


CORE_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "SMA30",
    "SMA50",
    "ADRP",
    "ATRP",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "average_volume_10d_calc",
    "average_volume_30d_calc",
]

STRUCTURE_COLUMNS = [
    "SMA10",
    "SMA20",
    "SMA100",
    "SMA150",
    "SMA200",
    "EMA10",
    "EMA21",
    "high",
    "low",
    "ATR",
    "volume",
    "relative_volume_10d_calc",
    "gap",
    "market_cap_basic",
    "earnings_release_next_trading_date_fq",
    "earnings_release_date",
]

BB_COLUMNS = ["BB.upper", "BB.lower", "BB.basis"]
SCAN_COLUMNS = CORE_COLUMNS + STRUCTURE_COLUMNS + BB_COLUMNS
KEY_MAS = ["SMA10", "SMA20", "SMA50", "SMA100", "SMA150", "SMA200"]
TV_EXCHANGES = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "AMEX": "AMEX"}


def fetch_universe() -> pd.DataFrame:
    """Fetch a broad US stock universe; exact liquidity filtering happens locally.

    Keeping the dollar-volume expression out of the server-side query avoids
    depending on TradingView expression support and makes the output auditable.
    Extra Jeff-rule columns are requested first; if TradingView rejects a field,
    the scan retries with the core NEL columns only.
    """
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    last_error: Exception | None = None
    column_sets = (
        SCAN_COLUMNS,
        CORE_COLUMNS + STRUCTURE_COLUMNS,
        CORE_COLUMNS,
    )
    for columns in column_sets:
        query = (
            Query()
            .set_markets("america")
            .select(*columns)
            .where(
                col("type") == "stock",
                col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
                col("average_volume_10d_calc") > 0,
            )
            .limit(5_000)
        )
        try:
            _, frame = query.get_scanner_data()
            return frame
        except Exception as error:  # noqa: BLE001 — TradingView field names vary
            last_error = error
    raise SystemExit(f"TradingView scan failed: {last_error}") from last_error


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(
            "TradingView did not return required column(s): " + ", ".join(missing)
        )


def _assign_exact_top_flags(frame: pd.DataFrame, metric: str, rank_column: str, flag_column: str, cutoff: int) -> None:
    """Assign deterministic ranks and an exact-size top group for one metric."""
    ordered = frame.sort_values([metric, "name"], ascending=[False, True], kind="stable")
    ranks = pd.Series(range(1, len(ordered) + 1), index=ordered.index, dtype="int64")
    frame[rank_column] = ranks
    frame[flag_column] = frame[rank_column] <= cutoff


def _numeric(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _parse_earnings_date(value: object) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19] if "T" in text or " " in text else text[:10], fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def tradingview_url(exchange: object, symbol: object) -> str:
    ticker = str(symbol or "").strip()
    venue = TV_EXCHANGES.get(str(exchange or "").strip().upper(), str(exchange or "NASDAQ").strip().upper() or "NASDAQ")
    return f"https://www.tradingview.com/chart/?symbol={venue}:{ticker}&interval=D"


def calculate_nel(raw: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return the eligible universe, leaders, and non-extended leaders (NEL)."""
    _require_columns(raw, ["name", "industry", "close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M", "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc"])
    df = raw.copy()
    numeric = ["close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M", "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc"]
    _numeric(df, numeric)

    # ADRP and ATRP are TradingView's daily 14-period percentage indicators.
    # ADRP is used only for the initial activity filter. ATRP feeds the
    # extension calculation exactly as in your manual spreadsheet.
    df["dollar_volume_30d"] = df["close"] * df["average_volume_30d_calc"]
    df["average_dollar_volume_30d"] = df["SMA30"] * df["average_volume_30d_calc"]
    df["atr_extension_from_50d"] = (df["close"] - df["SMA50"]) / (
        df["SMA50"] * (df["ATRP"] / 100)
    )

    valid_industry = ~df["industry"].fillna("").str.contains("biotech", case=False, regex=False)
    valid_metrics = (df[["close", "SMA30", "SMA50", "ADRP", "ATRP"]] > 0).all(axis=1)
    has_performance = df[["Perf.1M", "Perf.3M", "Perf.6M"]].notna().all(axis=1)
    universe = df.loc[
        valid_industry
        & valid_metrics
        & has_performance
        & (df["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (df["ADRP"] > settings.min_adr_pct)
        & (df["average_volume_10d_calc"] > settings.min_avg_volume_10d)
    ].copy()

    if universe.empty:
        return universe, universe.copy(), universe.copy()

    cutoff = max(1, ceil(len(universe) * settings.top_pct))
    _assign_exact_top_flags(universe, "Perf.1M", "perf_1m_rank", "is_top_1m", cutoff)
    _assign_exact_top_flags(universe, "Perf.3M", "perf_3m_rank", "is_top_3m", cutoff)
    _assign_exact_top_flags(universe, "Perf.6M", "perf_6m_rank", "is_top_6m", cutoff)
    universe["momentum_score"] = universe[["Perf.1M", "Perf.3M", "Perf.6M"]].mean(axis=1)

    # Combine the three leader groups. A symbol can lead in more than one
    # timeframe but appears only once in the final leader list.
    leaders = pd.concat(
        [
            universe.loc[universe["is_top_1m"]],
            universe.loc[universe["is_top_3m"]],
            universe.loc[universe["is_top_6m"]],
        ],
        ignore_index=True,
    ).drop_duplicates(subset="name", keep="first")
    nel = leaders.loc[
        leaders["atr_extension_from_50d"] <= settings.max_atr_extension
    ].copy()
    sort_order = ["momentum_score", "Perf.1M", "Perf.3M", "Perf.6M"]
    leaders.sort_values(sort_order, ascending=False, inplace=True)
    nel.sort_values(sort_order, ascending=False, inplace=True)
    return universe.sort_values("momentum_score", ascending=False), leaders, nel


def annotate_structure(frame: pd.DataFrame, focus: FocusSettings, snapshot_date: date | None = None) -> pd.DataFrame:
    """Add Jeff hard-rule metrics. Missing TradingView columns become false/NaN, not errors."""
    result = frame.copy()
    if result.empty:
        return result
    _numeric(result, KEY_MAS + [
        "EMA10", "EMA21", "high", "low", "ATR", "volume", "relative_volume_10d_calc",
        "gap", "market_cap_basic", "BB.upper", "BB.lower", "BB.basis", "ADRP", "ATRP",
    ])
    as_of = snapshot_date or datetime.now().date()

    atr = result["ATR"] if "ATR" in result.columns else pd.Series(pd.NA, index=result.index)
    if atr.isna().all() and {"close", "ATRP"}.issubset(result.columns):
        atr = result["close"] * (result["ATRP"] / 100)
    result["atr_abs"] = atr
    high = result["high"] if "high" in result.columns else pd.Series(pd.NA, index=result.index)
    low = result["low"] if "low" in result.columns else pd.Series(pd.NA, index=result.index)
    close = result["close"]
    result["day_range_atr"] = (high - low) / atr
    result["lod_atr_pct"] = (close - low) / atr * 100
    result["rvol"] = result["relative_volume_10d_calc"] if "relative_volume_10d_calc" in result.columns else pd.NA
    result["gap_pct"] = result["gap"] if "gap" in result.columns else pd.NA
    sma20 = result["SMA20"] if "SMA20" in result.columns else pd.Series(pd.NA, index=result.index)
    result["sma20_distance_pct"] = (close - sma20) / sma20 * 100

    present_mas = [column for column in KEY_MAS if column in result.columns]
    if present_mas:
        ma_block = result[present_mas]
        aligned = pd.Series(True, index=result.index)
        for column in present_mas:
            aligned &= close >= result[column]
        result["above_all_mas"] = aligned
        result["ma_spread_pct"] = (ma_block.max(axis=1) - ma_block.min(axis=1)) / close * 100
    else:
        result["above_all_mas"] = False
        result["ma_spread_pct"] = pd.NA
    result["above_sma10"] = close >= result["SMA10"] if "SMA10" in result.columns else False
    result["above_sma20"] = close >= result["SMA20"] if "SMA20" in result.columns else False
    result["above_sma50"] = close >= result["SMA50"] if "SMA50" in result.columns else False
    result["above_sma200"] = close >= result["SMA200"] if "SMA200" in result.columns else False
    result["ma_aligned"] = result["above_sma10"] & result["above_sma20"] & result["above_sma50"]
    ema10 = result["EMA10"] if "EMA10" in result.columns else pd.Series(pd.NA, index=result.index)
    ema21 = result["EMA21"] if "EMA21" in result.columns else pd.Series(pd.NA, index=result.index)
    result["ema_aligned"] = (close >= ema10) & (ema10 >= ema21)
    result["ema21_atr_dist"] = (close - ema21).abs() / (ema21 * (result["ATRP"] / 100))
    result["near_ema"] = result["ema21_atr_dist"] <= focus.near_ema_atr
    result["adr_tight"] = ((high - low) / close) <= (focus.adr_tight_frac * result["ADRP"] / 100)
    bb_upper = result["BB.upper"] if "BB.upper" in result.columns else pd.Series(pd.NA, index=result.index)
    bb_lower = result["BB.lower"] if "BB.lower" in result.columns else pd.Series(pd.NA, index=result.index)
    bb_basis = result["BB.basis"] if "BB.basis" in result.columns else pd.Series(pd.NA, index=result.index)
    result["bb_width"] = (bb_upper - bb_lower) / bb_basis
    result["bb_tight"] = result["bb_width"] <= focus.max_bb_width
    result["rvol_expand"] = result["rvol"] >= focus.rvol_expand
    result["plan_tight"] = (
        result["near_ema"].fillna(False)
        | result["adr_tight"].fillna(False)
        | result["bb_tight"].fillna(False)
    )
    tightness = []
    for _, row in result.iterrows():
        tags = []
        if bool(row.get("ema_aligned")):
            tags.append("EMA")
        if bool(row.get("near_ema")):
            tags.append("near21")
        if bool(row.get("adr_tight")):
            tags.append("ADR")
        if bool(row.get("bb_tight")):
            tags.append("BB")
        if bool(row.get("rvol_expand")):
            tags.append("RVOL")
        tightness.append(", ".join(tags))
    result["tightness_flags"] = tightness

    earnings_col = next((column for column in ("earnings_release_next_trading_date_fq", "earnings_release_date") if column in result.columns), None)
    if earnings_col:
        earnings = result[earnings_col].map(_parse_earnings_date)
        result["earnings_date"] = earnings.map(lambda day: day.isoformat() if day else "")
        result["earnings_soon"] = earnings.map(
            lambda day: bool(day and 0 <= (day - as_of).days <= focus.earnings_days)
        )
    else:
        result["earnings_date"] = ""
        result["earnings_soon"] = False

    market_cap = result["market_cap_basic"] if "market_cap_basic" in result.columns else pd.Series(pd.NA, index=result.index)
    result["mega_cap"] = market_cap >= focus.mega_cap
    result["near_sma20"] = result["sma20_distance_pct"].abs() <= (focus.near_sma20_pct * 100)
    result["range_tight"] = result["day_range_atr"] <= focus.max_day_range_atr
    result["wide_day"] = result["day_range_atr"] > focus.max_day_range_atr
    result["lod_ok"] = result["lod_atr_pct"] <= focus.max_lod_atr_pct
    result["rvol_ok"] = result["rvol"] >= focus.min_rvol
    result["rvol_pass"] = result["rvol_ok"] | result["mega_cap"].fillna(False)
    result["ma_coiled"] = result["ma_spread_pct"] <= 5
    result["large_gap"] = result["gap_pct"].abs() >= focus.large_gap_pct
    result["rule1_lod"] = result["lod_ok"]
    result["rule2_extension"] = result["atr_extension_from_50d"] <= 4
    result["rule4_rvol"] = result["rvol_pass"]
    result["rule6_earnings"] = ~result["earnings_soon"].astype(bool)
    result["rule7_sma200"] = result["above_sma200"].astype(bool)
    result["rule8_gap"] = ~result["large_gap"].fillna(False)
    pretrade = ["rule1_lod", "rule2_extension", "rule4_rvol", "rule6_earnings", "rule7_sma200", "rule8_gap"]
    result["hard_rule_passes"] = result[pretrade].fillna(False).sum(axis=1).astype(int)
    fails = []
    labels = {
        "rule1_lod": "LoD>60% ATR",
        "rule2_extension": ">4x 50-MA",
        "rule4_rvol": "thin RVOL",
        "rule6_earnings": "earnings soon",
        "rule7_sma200": "below 200-MA",
        "rule8_gap": "large gap",
    }
    for index, row in result.iterrows():
        failed = [label for key, label in labels.items() if not bool(row.get(key))]
        fails.append(", ".join(failed))
    result["hard_rule_fails"] = fails
    result["focus_score"] = (
        result["ma_aligned"].astype(int)
        + result["above_all_mas"].astype(int)
        + result["lod_ok"].fillna(False).astype(int)
        + result["range_tight"].fillna(False).astype(int)
        + result["near_sma20"].fillna(False).astype(int)
        + result["ma_coiled"].fillna(False).astype(int)
        + result["rule6_earnings"].astype(int)
        + result["rule7_sma200"].astype(int)
        + result["ema_aligned"].fillna(False).astype(int)
        + result["near_ema"].fillna(False).astype(int)
        + result["adr_tight"].fillna(False).astype(int)
        + result["bb_tight"].fillna(False).astype(int)
    )
    result["tradingview_url"] = [
        tradingview_url(row.get("exchange"), row.get("name")) for _, row in result.iterrows()
    ]
    return result


def calculate_focus(nel: pd.DataFrame, focus: FocusSettings) -> pd.DataFrame:
    """Shortlist NEL names that pass Jeff filters and the planned EMA/tightness layer."""
    if nel.empty:
        return nel.copy()
    candidates = nel.loc[
        nel["ma_aligned"].fillna(False)
        & nel["above_sma200"].fillna(False)
        & nel["rule6_earnings"].fillna(False)
        & nel["lod_ok"].fillna(False)
        & nel["range_tight"].fillna(False)
        & nel["rule2_extension"].fillna(False)
        & nel["ema_aligned"].fillna(False)
        & nel["plan_tight"].fillna(False)
    ].copy()
    return candidates.sort_values(
        ["focus_score", "momentum_score", "Perf.1M"],
        ascending=False,
    )


def prepare_for_export(frame: pd.DataFrame) -> pd.DataFrame:
    """Order and round the columns so the daily review sheet is scan-friendly."""
    preferred = [
        "name", "description", "exchange", "industry", "close", "SMA10", "SMA20", "SMA30", "SMA50",
        "SMA100", "SMA150", "SMA200", "EMA10", "EMA21", "high", "low", "ADRP", "ATRP", "atr_abs",
        "average_volume_10d_calc", "average_volume_30d_calc", "dollar_volume_30d", "average_dollar_volume_30d",
        "rvol", "gap_pct", "market_cap_basic",
        "Perf.1M", "perf_1m_rank", "Perf.3M", "perf_3m_rank", "Perf.6M", "perf_6m_rank",
        "momentum_score", "atr_extension_from_50d", "sma20_distance_pct", "ema21_atr_dist",
        "day_range_atr", "lod_atr_pct", "bb_width", "ma_spread_pct",
        "above_all_mas", "ma_aligned", "ema_aligned", "above_sma200", "near_sma20", "near_ema",
        "range_tight", "adr_tight", "bb_tight", "plan_tight", "wide_day", "lod_ok",
        "rvol_ok", "rvol_pass", "rvol_expand", "ma_coiled", "earnings_date", "earnings_soon",
        "large_gap", "hard_rule_passes", "hard_rule_fails", "tightness_flags", "focus_score", "tradingview_url",
        "is_top_1m", "is_top_3m", "is_top_6m",
    ]
    columns = [column for column in preferred if column in frame.columns]
    result = frame.loc[:, columns].copy()
    return result.round({
        "close": 2, "SMA10": 2, "SMA20": 2, "SMA30": 2, "SMA50": 2, "SMA100": 2, "SMA150": 2, "SMA200": 2,
        "EMA10": 2, "EMA21": 2, "high": 2, "low": 2, "ADRP": 2, "ATRP": 2, "atr_abs": 2,
        "dollar_volume_30d": 0, "average_dollar_volume_30d": 0, "rvol": 2, "gap_pct": 2,
        "Perf.1M": 2, "Perf.3M": 2, "Perf.6M": 2, "momentum_score": 2, "atr_extension_from_50d": 2,
        "sma20_distance_pct": 2, "ema21_atr_dist": 2, "day_range_atr": 2, "lod_atr_pct": 1,
        "bb_width": 3, "ma_spread_pct": 2,
    })


def write_outputs(
    universe: pd.DataFrame,
    leaders: pd.DataFrame,
    nel: pd.DataFrame,
    settings: Settings,
    output_dir: Path,
    snapshot_date: date | None = None,
    focus: pd.DataFrame | None = None,
    focus_settings: FocusSettings | None = None,
) -> list[Path]:
    """Write each review view as a plain CSV file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    setting_rows = list(asdict(settings).items())
    if focus_settings is not None:
        setting_rows.extend((f"focus_{item.name}", getattr(focus_settings, item.name)) for item in fields(focus_settings))
    settings_frame = pd.DataFrame(setting_rows, columns=["setting", "value"])
    focus_frame = focus if focus is not None else nel.iloc[0:0]
    outputs = {
        "non_extended_leaders": prepare_for_export(nel),
        "nel_symbols": nel.loc[:, ["name"]].rename(columns={"name": "symbol"}),
        "momentum_leaders": prepare_for_export(leaders),
        "filtered_universe": prepare_for_export(universe),
        "focus_candidates": prepare_for_export(focus_frame),
        "settings": settings_frame,
    }
    paths = []
    for name, frame in outputs.items():
        destination = export_dir if name in {"nel_symbols"} else output_dir
        path = destination / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    if not focus_frame.empty:
        symbol_path = export_dir / f"focus_symbols_{stamp}.csv"
        focus_frame.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(symbol_path, index=False)
        paths.append(symbol_path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a non-extended leader (NEL) list.")
    parser.add_argument("--min-adr-pct", type=float, default=4.0, help="Minimum TradingView ADR%% (default: 4).")
    parser.add_argument("--top-pct", type=float, default=0.05, help="Top share from each 1-, 3-, and 6-month ranking before deduplication (default: 0.05).")
    parser.add_argument("--max-extension", type=float, default=4.0, help="Maximum ATRs extended from SMA50 (default: 4).")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="CSV output directory.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Date to use in output filenames (YYYY-MM-DD).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.top_pct <= 1:
        raise SystemExit("--top-pct must be greater than 0 and no more than 1.")
    if args.min_adr_pct < 0:
        raise SystemExit("--min-adr-pct cannot be negative.")
    settings = Settings(min_adr_pct=args.min_adr_pct, top_pct=args.top_pct, max_atr_extension=args.max_extension)
    focus_settings = FocusSettings()
    snapshot = args.snapshot_date
    raw = fetch_universe()
    universe, leaders, nel = calculate_nel(raw, settings)
    universe = annotate_structure(universe, focus_settings, snapshot)
    leaders = annotate_structure(leaders, focus_settings, snapshot)
    nel = annotate_structure(nel, focus_settings, snapshot)
    focus = calculate_focus(nel, focus_settings)
    paths = write_outputs(universe, leaders, nel, settings, args.output_dir, snapshot, focus, focus_settings)
    try:
        from rs_lead_scan import RSLeadSettings, scan_rs_leads, write_rs_outputs

        rs_settings = RSLeadSettings()
        rs_frame = scan_rs_leads(universe, rs_settings)
        paths.extend(write_rs_outputs(rs_frame, rs_settings, args.output_dir, snapshot))
        rs_leads = int(rs_frame["is_rs_lead"].sum()) if not rs_frame.empty else 0
        rs_summary = f" | RS highs: {len(rs_frame):,} | RS leads: {rs_leads:,}"
    except SystemExit as error:
        rs_summary = f" | RS scan skipped ({error})"
    except Exception as error:  # noqa: BLE001 — daily desk should still publish NEL/Focus
        rs_summary = f" | RS scan failed ({error})"
    try:
        from ema8_pullback_scan import Ema8PullbackSettings, scan_ema8_pullbacks, write_ema8_outputs

        ema_settings = Ema8PullbackSettings()
        ema_frame = scan_ema8_pullbacks(leaders, ema_settings)
        paths.extend(write_ema8_outputs(ema_frame, ema_settings, args.output_dir, snapshot))
        ema_summary = f" | EMA8 PB: {len(ema_frame):,}"
    except SystemExit as error:
        ema_summary = f" | EMA8 scan skipped ({error})"
    except Exception as error:  # noqa: BLE001
        ema_summary = f" | EMA8 scan failed ({error})"
    try:
        from ma_stack_scan import MaStackSettings, scan_ma_stack, write_ma_stack_outputs

        ma_settings = MaStackSettings()
        ma_frame = scan_ma_stack(leaders, ma_settings)
        paths.extend(write_ma_stack_outputs(ma_frame, ma_settings, args.output_dir, snapshot))
        ma_summary = f" | MA stack: {len(ma_frame):,}"
    except SystemExit as error:
        ma_summary = f" | MA stack skipped ({error})"
    except Exception as error:  # noqa: BLE001
        ma_summary = f" | MA stack failed ({error})"
    try:
        from a_plus_flag_scan import APlusFlagSettings, scan_a_plus_flags, write_a_plus_flag_outputs

        ap_settings = APlusFlagSettings()
        ap_frame = scan_a_plus_flags(leaders, ap_settings)
        paths.extend(write_a_plus_flag_outputs(ap_frame, ap_settings, args.output_dir, snapshot))
        n_bo = int((ap_frame["signal"] == "APLUS_BREAKOUT").sum()) if not ap_frame.empty else 0
        ap_summary = f" | A++ flags: {len(ap_frame):,} ({n_bo} BO)"
    except SystemExit as error:
        ap_summary = f" | A++ flag scan skipped ({error})"
    except Exception as error:  # noqa: BLE001
        ap_summary = f" | A++ flag scan failed ({error})"
    paths.append(write_dashboard(args.output_dir))
    try:
        from theme_tracker import write_theme_tracker

        paths.extend(write_theme_tracker(args.output_dir, snapshot))
        theme_summary = " | theme tape"
    except Exception as error:  # noqa: BLE001 — tape is additive; a quote outage must not drop the desk
        theme_summary = f" | theme tape failed ({error})"
    print(
        f"Scanned: {len(raw):,} | eligible: {len(universe):,} | leaders: {len(leaders):,} | "
        f"NEL: {len(nel):,} | focus: {len(focus):,}{rs_summary}{ema_summary}{ma_summary}{ap_summary}{theme_summary}"
    )
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
