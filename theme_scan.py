#!/usr/bin/env python3
"""Scan the desk's top themes for the price, trend, and growth checklist.

Top themes are the 1-month industry leaders on the Themes board, plus any
1-month industry that is rising or kicking off. A name passes only when all
of these are true:

- Price above $1
- Day change from -5% to +5%
- Volume greater than 1M shares
- Close above the 10-day, the 20-day, and the weekly 10
- The 10-day and the 20-day are rising
- Quarterly earnings and revenue are both up at least 40%
- The name leads its industry group on 1-month performance
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from focus_list import tradingview_url
from industry_flow_dashboard import detect_rising_themes, rising_industry_names


@dataclass(frozen=True)
class ThemeScanSettings:
    top_theme_count: int = 5
    min_price: float = 1.0
    min_change: float = -5.0
    max_change: float = 5.0
    min_volume: float = 1_000_000
    min_growth: float = 40.0
    slope_lookback: int = 5
    history_period: str = "6mo"


SCAN_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "change",
    "volume",
    "SMA10",
    "SMA20",
    "SMA10|1W",
    "earnings_per_share_diluted_yoy_growth_fq",
    "earnings_per_share_diluted_yoy_growth_ttm",
    "total_revenue_yoy_growth_fq",
    "total_revenue_yoy_growth_ttm",
    "Perf.1M",
]


def _one_month_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "industry" not in frame.columns:
        return {}
    flagged = frame
    if "is_top_1m" in frame.columns:
        flagged = frame.loc[frame["is_top_1m"].fillna(False).astype(bool)]
    counts = flagged["industry"].fillna("").astype(str).str.strip()
    counts = counts[counts != ""].value_counts()
    return {str(name): int(count) for name, count in counts.items()}


def top_themes(leaders: pd.DataFrame, prior: pd.DataFrame | None = None, *, count: int = 5) -> list[str]:
    """Industries on the 1-month board, plus industries that just expanded."""
    current = _one_month_counts(leaders)
    ranked = sorted(current, key=lambda name: (-current[name], name))[:count]
    rising: list[str] = []
    if prior is not None:
        flags = detect_rising_themes({"1m": current}, {"1m": _one_month_counts(prior)})
        rising = sorted(rising_industry_names(flags, frame="1m"))
    ordered: list[str] = []
    for name in ranked + rising:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _growth(frame: pd.DataFrame, quarterly: str, trailing: str) -> pd.Series:
    primary = pd.to_numeric(frame[quarterly], errors="coerce") if quarterly in frame.columns else pd.Series(float("nan"), index=frame.index)
    backup = pd.to_numeric(frame[trailing], errors="coerce") if trailing in frame.columns else pd.Series(float("nan"), index=frame.index)
    return primary.where(primary.notna(), backup)


def passes_quote_rules(frame: pd.DataFrame, settings: ThemeScanSettings) -> pd.DataFrame:
    """Apply every rule that the screener snapshot can score."""
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    for column in ("close", "change", "volume", "SMA10", "SMA20", "SMA10|1W", "Perf.1M"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result["earn_yoy"] = _growth(
        result,
        "earnings_per_share_diluted_yoy_growth_fq",
        "earnings_per_share_diluted_yoy_growth_ttm",
    )
    result["sales_yoy"] = _growth(
        result,
        "total_revenue_yoy_growth_fq",
        "total_revenue_yoy_growth_ttm",
    )
    weekly = result["SMA10|1W"] if "SMA10|1W" in result.columns else pd.Series(float("nan"), index=result.index)
    mask = (
        result["close"].gt(settings.min_price)
        & result["change"].ge(settings.min_change)
        & result["change"].le(settings.max_change)
        & result["volume"].gt(settings.min_volume)
        & result["close"].gt(result["SMA10"])
        & result["close"].gt(result["SMA20"])
        & result["close"].gt(weekly)
        & result["earn_yoy"].ge(settings.min_growth)
        & result["sales_yoy"].ge(settings.min_growth)
    )
    return result.loc[mask].copy()


def ma_is_rising(closes: pd.Series, window: int, lookback: int) -> bool:
    """True when the simple average is higher than it was `lookback` sessions ago."""
    series = pd.to_numeric(closes, errors="coerce").dropna()
    if len(series) < window + lookback:
        return False
    average = series.rolling(window).mean()
    latest = average.iloc[-1]
    prior = average.iloc[-1 - lookback]
    if pd.isna(latest) or pd.isna(prior):
        return False
    return float(latest) > float(prior)


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def attach_rising(frame: pd.DataFrame, closes: pd.DataFrame, settings: ThemeScanSettings) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    rising_10: list[bool] = []
    rising_20: list[bool] = []
    for symbol in result["name"].astype(str):
        column = _normalize_symbol(symbol)
        series = closes[column] if column in closes.columns else pd.Series(dtype=float)
        rising_10.append(ma_is_rising(series, 10, settings.slope_lookback))
        rising_20.append(ma_is_rising(series, 20, settings.slope_lookback))
    result["sma10_rising"] = rising_10
    result["sma20_rising"] = rising_20
    return result.loc[result["sma10_rising"] & result["sma20_rising"]].copy()


def select_group_leaders(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the strongest 1-month name in each industry."""
    if frame.empty or "Perf.1M" not in frame.columns:
        return frame.iloc[0:0].copy()
    ranked = frame.dropna(subset=["Perf.1M"]).sort_values(["Perf.1M", "name"], ascending=[False, True])
    if ranked.empty:
        return ranked
    return ranked.groupby("industry", as_index=False, sort=False).head(1).reset_index(drop=True)


def fetch_theme_names(industries: list[str], settings: ThemeScanSettings) -> pd.DataFrame:
    if not industries:
        return pd.DataFrame()
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    query = (
        Query()
        .set_markets("america")
        .select(*SCAN_COLUMNS)
        .where(
            col("type") == "stock",
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("industry").isin(industries),
            col("close") > settings.min_price,
            col("volume") > settings.min_volume,
            col("change").between(settings.min_change, settings.max_change),
        )
        .order_by("volume", ascending=False)
        .limit(3_000)
    )
    try:
        _, frame = query.get_scanner_data()
    except Exception as error:  # noqa: BLE001 — surface the scanner failure to the daily log
        raise SystemExit(f"Theme scan quote request failed: {error}") from error
    return frame


def download_closes(symbols: list[str], settings: ThemeScanSettings) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    tickers = sorted({_normalize_symbol(symbol) for symbol in symbols if symbol})
    raw = yf.download(
        tickers=tickers,
        period=settings.history_period,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="ticker",
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    closes: dict[str, pd.Series] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in tickers:
            if symbol not in raw.columns.get_level_values(0):
                continue
            block = raw[symbol]
            if "Close" not in block.columns:
                continue
            closes[symbol] = block["Close"]
    elif "Close" in raw.columns and len(tickers) == 1:
        closes[tickers[0]] = raw["Close"]
    return pd.DataFrame(closes).dropna(how="all")


def _present(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "name",
        "description",
        "exchange",
        "industry",
        "close",
        "change",
        "volume",
        "earn_yoy",
        "sales_yoy",
        "Perf.1M",
        "sma10_rising",
        "sma20_rising",
    ]
    out = frame.loc[:, [column for column in columns if column in frame.columns]].copy()
    out["tradingview_url"] = [
        tradingview_url(exchange, symbol)
        for exchange, symbol in zip(out.get("exchange", []), out.get("name", []), strict=False)
    ]
    if "Perf.1M" in out.columns:
        out = out.sort_values(["Perf.1M", "name"], ascending=[False, True])
    return out.reset_index(drop=True)


def scan_top_themes(
    leaders: pd.DataFrame,
    output_dir: Path,
    settings: ThemeScanSettings | None = None,
    snapshot: date | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    settings = settings or ThemeScanSettings()
    themes = top_themes(leaders, _prior_leaders(output_dir, snapshot), count=settings.top_theme_count)
    if not themes:
        return pd.DataFrame(), []
    quotes = fetch_theme_names(themes, settings)
    qualified = passes_quote_rules(quotes, settings)
    if qualified.empty:
        return qualified, themes
    closes = download_closes(qualified["name"].astype(str).tolist(), settings)
    rising = attach_rising(qualified, closes, settings)
    return _present(select_group_leaders(rising)), themes


def _prior_leaders(output_dir: Path, snapshot: date | None) -> pd.DataFrame | None:
    paths = sorted(output_dir.glob("momentum_leaders_*.csv"))
    chosen: Path | None = None
    cutoff = snapshot.isoformat() if snapshot else None
    for path in paths:
        stamp = path.name.replace("momentum_leaders_", "").replace(".csv", "")
        if cutoff and stamp >= cutoff:
            break
        chosen = path
    if chosen is None:
        return None
    return pd.read_csv(chosen)


def write_theme_scan(
    frame: pd.DataFrame,
    themes: list[str],
    output_dir: Path,
    snapshot_date: date | None = None,
    settings: ThemeScanSettings | None = None,
) -> list[Path]:
    settings = settings or ThemeScanSettings()
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    full = output_dir / f"theme_scan_{stamp}.csv"
    frame.to_csv(full, index=False)
    theme_path = output_dir / f"theme_scan_themes_{stamp}.csv"
    pd.DataFrame({"industry": themes}).to_csv(theme_path, index=False)
    paths = [full, theme_path]
    if not frame.empty and "name" in frame.columns:
        symbols = export_dir / f"theme_scan_symbols_{stamp}.csv"
        frame.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(symbols, index=False)
        paths.append(symbols)
    settings_path = output_dir / f"theme_scan_settings_{stamp}.csv"
    pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"]).to_csv(settings_path, index=False)
    paths.append(settings_path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan top themes for the price, trend, and growth checklist.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--snapshot-date", type=date.fromisoformat, default=None)
    return parser.parse_args()


def main() -> None:
    from ma_stack_scan import latest_momentum_leaders

    args = parse_args()
    leaders, stamp = latest_momentum_leaders(args.output_dir)
    snapshot = args.snapshot_date or stamp
    frame, themes = scan_top_themes(leaders, args.output_dir, snapshot=snapshot)
    paths = write_theme_scan(frame, themes, args.output_dir, snapshot)
    print(f"Themes: {', '.join(themes) if themes else 'none'} | passes: {len(frame):,}")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
