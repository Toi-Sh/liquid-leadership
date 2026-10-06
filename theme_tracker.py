#!/usr/bin/env python3
"""Equal-weight theme tape. Baskets live in themes_catalog.py."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from themes_catalog import LANE_ORDER, THEMES, unique_tickers, validate_catalog


PROJECT_DIR = Path(__file__).resolve().parent
HTML_PATH = PROJECT_DIR / "theme_tracker.html"
NY_TZ = ZoneInfo("America/New_York")
MIN_PRINTS = 3
BATCH_SIZE = 80

PERIODS = (
    ("today", "Today", "change"),
    ("w1", "1W", "Perf.W"),
    ("m1", "1M", "Perf.1M"),
    ("m3", "3M", "Perf.3M"),
    ("m6", "6M", "Perf.6M"),
    ("ytd", "YTD", "Perf.YTD"),
)
PERIOD_KEYS = tuple(key for key, _label, _column in PERIODS)

TV_COLUMNS = [
    "name",
    "description",
    "exchange",
    "close",
    "change",
    "Perf.W",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "Perf.YTD",
]
TV_EXCHANGES = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "AMEX": "AMEX"}


def chart_url(exchange: object, symbol: object) -> str:
    ticker = str(symbol or "").strip()
    venue = TV_EXCHANGES.get(
        str(exchange or "").strip().upper(),
        str(exchange or "NASDAQ").strip().upper() or "NASDAQ",
    )
    return f"https://www.tradingview.com/chart/?symbol={venue}:{ticker}&interval=D"


def as_number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def average(values: list[float | None], minimum: int = MIN_PRINTS) -> float | None:
    clean = [value for value in values if value is not None]
    if len(clean) < minimum:
        return None
    return sum(clean) / len(clean)


def build_snapshot(themes: list[dict], quotes: dict[str, dict], as_of: str) -> dict:
    """Roll constituent prints into equal-weight theme returns."""
    rows = []
    for spec in themes:
        members = []
        unquoted = []
        for ticker in spec["tickers"]:
            quote = quotes.get(ticker)
            if not quote:
                unquoted.append(ticker)
                continue
            member = {
                "symbol": ticker,
                "description": quote.get("description") or "",
                "url": quote.get("url") or chart_url(quote.get("exchange"), ticker),
                "close": as_number(quote.get("close")),
            }
            for key, _label, _column in PERIODS:
                member[key] = as_number(quote.get(key))
            members.append(member)
        metrics = {
            key: average([member[key] for member in members])
            for key in PERIOD_KEYS
        }
        today_prints = [member["today"] for member in members if member["today"] is not None]
        green = sum(1 for value in today_prints if value > 0)
        leader = None
        ranked = [member for member in members if member["today"] is not None]
        if ranked:
            best = max(ranked, key=lambda member: member["today"])
            leader = {"symbol": best["symbol"], "today": best["today"], "url": best["url"]}
        rows.append({
            "id": spec["id"],
            "name": spec["name"],
            "lane": spec["lane"],
            "blurb": spec["blurb"],
            "etf": spec.get("etf"),
            "listed": len(spec["tickers"]),
            "n": len(members),
            "unquoted": unquoted,
            "breadth": (green / len(today_prints)) if today_prints else None,
            "green": green,
            "prints": len(today_prints),
            "leader": leader,
            "members": members,
            **metrics,
        })
    return {
        "as_of": as_of,
        "method": "Each theme is the average of its stocks that have a price. Each stock has the same weight. A period stays blank until at least three stocks have a price.",
        "lanes": list(LANE_ORDER),
        "themes": rows,
    }


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def fetch_quotes(tickers: list[str]) -> dict[str, dict]:
    """Pull performance for every basket member. One column set, batched."""
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for batch in _chunks(tickers, BATCH_SIZE):
        query = (
            Query()
            .set_markets("america")
            .select(*TV_COLUMNS)
            .where(
                col("name").isin(batch),
                col("type").isin(["stock", "dr"]),
            )
            .limit(len(batch) + 10)
        )
        try:
            _count, frame = query.get_scanner_data()
        except Exception as error:  # noqa: BLE001 — scanner errors are data, not crashes
            errors.append(str(error))
            continue
        if frame is not None and not frame.empty:
            frames.append(frame)
    if not frames:
        detail = "; ".join(errors) or "no rows"
        raise RuntimeError(f"TradingView returned no theme quotes ({detail})")

    combined = pd.concat(frames, ignore_index=True)
    quotes: dict[str, dict] = {}
    for record in combined.to_dict(orient="records"):
        symbol = str(record.get("name") or "").strip().upper()
        exchange = str(record.get("exchange") or "").strip().upper()
        if not symbol or symbol in quotes or exchange not in TV_EXCHANGES:
            continue
        quote = {
            "description": record.get("description") or "",
            "exchange": record.get("exchange") or "",
            "close": as_number(record.get("close")),
            "url": chart_url(record.get("exchange"), symbol),
        }
        for key, _label, column in PERIODS:
            quote[key] = as_number(record.get(column))
        quotes[symbol] = quote
    return quotes


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def write_csvs(snapshot: dict, output_dir: Path, stamp: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    theme_rows = []
    member_rows = []
    for theme in snapshot["themes"]:
        leader = theme.get("leader") or {}
        theme_rows.append({
            "theme": theme["name"],
            "lane": theme["lane"],
            "names": theme["n"],
            "listed": theme["listed"],
            "breadth": _round(None if theme["breadth"] is None else theme["breadth"] * 100),
            "today": _round(theme["today"]),
            "1w": _round(theme["w1"]),
            "1m": _round(theme["m1"]),
            "3m": _round(theme["m3"]),
            "6m": _round(theme["m6"]),
            "ytd": _round(theme["ytd"]),
            "leader": leader.get("symbol", ""),
            "unquoted": " ".join(theme["unquoted"]),
        })
        for member in theme["members"]:
            member_rows.append({
                "theme": theme["name"],
                "symbol": member["symbol"],
                "description": member["description"],
                "close": _round(member["close"]),
                "today": _round(member["today"]),
                "1w": _round(member["w1"]),
                "1m": _round(member["m1"]),
                "3m": _round(member["m3"]),
                "6m": _round(member["m6"]),
                "ytd": _round(member["ytd"]),
            })
    theme_path = output_dir / f"theme_tracker_{stamp}.csv"
    member_path = output_dir / f"theme_members_{stamp}.csv"
    pd.DataFrame(theme_rows).to_csv(theme_path, index=False)
    pd.DataFrame(member_rows).to_csv(member_path, index=False)
    return [theme_path, member_path]


def render_html(snapshot: dict) -> str:
    payload = json.dumps(snapshot, separators=(",", ":")).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__PAYLOAD__", payload)


def write_theme_tracker(output_dir: Path, snapshot_date: date | None = None) -> list[Path]:
    """Fetch prints, write the CSVs, and refresh theme_tracker.html."""
    validate_catalog()
    stamp = (snapshot_date or datetime.now(NY_TZ).date()).isoformat()
    quotes = fetch_quotes(unique_tickers())
    snapshot = build_snapshot(THEMES, quotes, stamp)
    paths = write_csvs(snapshot, output_dir, stamp)
    html = render_html(snapshot)
    HTML_PATH.write_text(html, encoding="utf-8")
    paths.append(HTML_PATH)
    quoted = sum(theme["n"] for theme in snapshot["themes"])
    missed = sum(len(theme["unquoted"]) for theme in snapshot["themes"])
    print(f"Theme tape: {len(snapshot['themes'])} themes | prints {quoted} | no print {missed}")
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "outputs")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = write_theme_tracker(args.output_dir, args.snapshot_date)
    print("Saved:\n" + "\n".join(str(path) for path in paths))


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Theme Tape | Liquid Leadership</title>
  <meta name="description" content="Equal-weight market themes: semis, AI, health, power, materials, and macro.">
  <meta name="robots" content="index, follow">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="preload" href="assets/fonts/newsreader-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/source-sans-3-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css?v=20261006">
  <script>
    try { if (localStorage.getItem("lld-tape-theme") === "dark") document.documentElement.dataset.theme = "dark"; } catch (e) {}
  </script>
  <style>
    html { color-scheme: light; background: var(--color-paper); --color-bar: oklch(52% 0.16 255); --color-bar-down: oklch(48% 0.16 25); }
    html[data-theme="dark"] {
      color-scheme: dark;
      --color-paper: oklch(17% 0.02 260);
      --color-paper-2: oklch(22% 0.022 260);
      --color-paper-3: oklch(25% 0.024 260);
      --color-rule: oklch(32% 0.02 260);
      --color-rule-2: oklch(40% 0.02 260);
      --color-muted: oklch(74% 0.02 260);
      --color-ink-2: oklch(90% 0.015 260);
      --color-ink: oklch(96% 0.01 260);
      --color-accent: oklch(78% 0.12 250);
      --color-accent-ink: oklch(17% 0.02 260);
      --color-focus: oklch(82% 0.12 250);
      --color-up: oklch(78% 0.14 155);
      --color-down: oklch(74% 0.15 25);
      --color-bar: oklch(70% 0.15 255);
      --color-bar-down: oklch(72% 0.15 25);
    }
    html, body { overflow-x: clip; margin: 0; }
    body {
      background: var(--color-paper);
      color: var(--color-ink-2);
      font-family: var(--font-body);
      font-size: var(--text-base);
      line-height: 1.35;
    }
    h1, h2, button, a { font-style: normal; }
    .skip-link {
      position: absolute;
      left: var(--space-sm);
      top: var(--space-sm);
      z-index: var(--z-sticky-nav);
      padding: var(--space-xs) var(--space-sm);
      background: var(--color-accent);
      color: var(--color-accent-ink);
      font-family: var(--font-body);
      text-decoration: none;
      transform: translateY(-200%);
    }
    .skip-link:focus-visible { transform: none; outline: 2px solid var(--color-focus); }
    .nav-edge {
      position: sticky;
      top: 0;
      z-index: var(--z-sticky-nav);
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      grid-template-areas:
        "brand keys tools"
        "lanes lanes lanes";
      align-items: center;
      gap: var(--space-xs) var(--space-sm);
      min-height: var(--banner-height);
      padding: var(--space-xs) var(--page-gutter);
      padding-left: max(var(--page-gutter), env(safe-area-inset-left));
      padding-right: max(var(--page-gutter), env(safe-area-inset-right));
      background: var(--color-paper);
      border-bottom: var(--rule) solid var(--color-rule);
    }
    .brand { grid-area: brand; }
    .bbg-keys {
      grid-area: keys;
      display: flex;
      min-width: 0;
      align-items: stretch;
      overflow: visible;
    }
    .desk-menu { position: relative; display: flex; }
    .desk-tab {
      display: flex;
      align-items: center;
      gap: var(--space-4);
      margin: 0;
      padding: 0 var(--space-12);
      min-height: 45px;
      border: 0;
      border-bottom: 2px solid transparent;
      background: transparent;
      color: var(--color-ink);
      font-family: var(--font-body);
      font-size: var(--text-xs);
      font-style: normal;
      letter-spacing: 0.01em;
      text-decoration: none;
      text-transform: none;
      white-space: nowrap;
      cursor: pointer;
    }
    .desk-caret {
      width: 0;
      height: 0;
      border-left: 0.28rem solid transparent;
      border-right: 0.28rem solid transparent;
      border-top: 0.32rem solid currentColor;
    }
    .desk-tab[aria-current="page"],
    .desk-tab[aria-expanded="true"] {
      color: var(--color-accent);
      border-bottom-color: var(--color-accent);
    }
    .desk-menu__panel {
      position: absolute;
      top: calc(100% + 1px);
      left: 0;
      z-index: 1;
      display: flex;
      flex-direction: column;
      min-width: 13.5rem;
      padding: var(--space-4) 0;
      background: var(--color-paper);
      border: var(--rule) solid var(--color-rule);
    }
    .desk-menu__panel[hidden] { display: none; }
    .desk-menu__panel a {
      display: flex;
      align-items: center;
      gap: var(--space-8);
      min-height: 2.75rem;
      padding: 0 var(--space-sm);
      color: var(--color-ink);
      font-family: var(--font-body);
      font-size: var(--text-xs);
      letter-spacing: 0.01em;
      text-decoration: none;
      text-transform: none;
      white-space: nowrap;
    }
    .desk-tab:hover, .desk-menu__panel a:hover { color: var(--color-accent); }
    .desk-tab:focus-visible, .desk-menu__panel a:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 1px; }
    .product {
      font-family: var(--font-display);
      font-size: var(--text-md);
      letter-spacing: -0.02em;
      text-transform: none;
      text-decoration: none;
      white-space: nowrap;
      line-height: 1;
      color: var(--color-ink);
    }
    .brand { display: flex; align-items: center; gap: var(--space-sm); }
    .lanes {
      grid-area: lanes;
      display: flex;
      align-items: stretch;
      min-width: 0;
      gap: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .lanes::-webkit-scrollbar { display: none; }
    #lanes .lane {
      min-height: 2.25rem;
      padding: 0 var(--space-sm);
      border: 0;
      border-bottom: 2px solid transparent;
      background: transparent;
      color: var(--color-muted);
      font-family: var(--font-body);
      letter-spacing: 0.01em;
      text-transform: none;
    }
    #lanes .lane[aria-pressed="true"] {
      background: transparent;
      color: var(--color-accent);
      border-bottom-color: var(--color-accent);
    }
    #lanes .lane[aria-pressed="true"]:hover { color: var(--color-accent); }
    .lane, .sort, .icon-btn {
      min-height: 45px;
      padding: 0 var(--space-xs);
      border: var(--rule) solid var(--color-rule);
      background: transparent;
      color: var(--color-ink);
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
      cursor: pointer;
    }
    .lane { border-top-width: var(--rule); border-bottom-width: var(--rule); }
    .lane[aria-pressed="true"] {
      background: var(--color-ink);
      color: var(--color-paper);
    }
    .lane:hover, .sort:hover, .icon-btn:hover, .ticker:hover { color: var(--color-accent); }
    .lane[aria-pressed="true"]:hover { color: var(--color-paper); }
    .lane:focus-visible, .sort:focus-visible, .icon-btn:focus-visible, .search:focus-visible, .ticker:focus-visible {
      outline: 2px solid var(--color-focus);
      outline-offset: 1px;
    }
    .tools { display: flex; align-items: center; gap: var(--space-xs); }
    .search {
      width: 9rem;
      min-height: 45px;
      padding: 0 var(--space-sm);
      border: var(--rule) solid var(--color-rule);
      background: var(--color-paper);
      color: var(--color-ink);
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      letter-spacing: 0.06em;
    }
    .clock { color: var(--color-muted); font-family: var(--font-mono); font-size: var(--text-xs); white-space: nowrap; }
    .lede, .foot {
      margin: 0;
      padding: var(--space-xs) var(--page-gutter);
      color: var(--color-muted);
      font-size: var(--text-xs);
    }
    .tape {
      display: flex;
      flex-direction: column;
      gap: var(--space-xs);
      padding: var(--space-sm) var(--page-gutter);
      border-bottom: var(--rule) solid var(--color-rule);
    }
    .tape-row {
      display: grid;
      grid-template-columns: 6.75rem minmax(0, 1fr);
      align-items: baseline;
      column-gap: var(--space-md);
    }
    .tape-label {
      font-family: var(--font-body);
      font-size: var(--text-xs);
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--color-accent);
    }
    .tape-chips {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-xs) var(--space-md);
    }
    .chip {
      display: inline-flex;
      gap: var(--space-xs);
      align-items: baseline;
      padding: 0;
      border: 0;
      background: transparent;
      color: var(--color-ink);
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      cursor: pointer;
      white-space: nowrap;
    }
    .chip:focus-visible { outline: 2px solid var(--color-focus); }
    .up { color: var(--color-up); }
    .down { color: var(--color-down); }
    .flat { color: var(--color-muted); }
    .table-scroll { overflow-x: auto; max-width: 100%; }
    table { width: 100%; min-width: 52rem; border-collapse: separate; border-spacing: 0; }
    th, td {
      padding: var(--space-xs) var(--space-sm);
      border-bottom: var(--rule) solid var(--color-rule);
      text-align: right;
      vertical-align: top;
      font-variant-numeric: tabular-nums;
    }
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align: left; }
    thead th { background: var(--color-paper); }
    .sort {
      min-height: 32px;
      padding: 0;
      border: 0;
      letter-spacing: 0.08em;
    }
    .name { font-family: var(--font-display); letter-spacing: -0.01em; text-transform: none; color: var(--color-ink); }
    .lane-tag { color: var(--color-accent); letter-spacing: 0.08em; text-transform: uppercase; font-size: var(--text-xs); }
    .ticker { color: var(--color-accent); font-family: var(--font-body); text-decoration: none; }
    .meter {
      display: inline-block;
      width: 3.2rem;
      height: 0.35rem;
      margin-right: var(--space-xs);
      background: var(--color-paper-2);
      vertical-align: middle;
    }
    .meter i {
      display: block;
      height: 100%;
      width: var(--fill);
      background: var(--color-up);
    }
    tr.detail td { background: var(--color-paper-3); text-align: left; }
    .members { width: 100%; min-width: 40rem; }
    .members th, .members td { border-bottom-color: var(--color-paper-2); }
    .blurb { margin: 0 0 var(--space-sm); max-width: 46rem; color: var(--color-ink-2); }
    .miss { color: var(--color-muted); }
    .empty { padding: var(--space-lg) var(--page-gutter); }
    .view-switch { display: flex; gap: var(--space-4); }
    .view-switch .lane { padding: 0 var(--space-xs); }
    .bars { padding: var(--space-xs) var(--page-gutter) var(--space-md); }
    .bars[hidden], .table-scroll[hidden], #tape[hidden], .tape[hidden] { display: none; }
    .bar-periods {
      display: flex;
      gap: var(--space-4);
      margin-bottom: var(--space-sm);
      overflow-x: auto;
    }
    #bar-periods .lane {
      min-height: 2.25rem;
      padding: 0 var(--space-sm);
      border: 0;
      border-bottom: 2px solid transparent;
      background: transparent;
      color: var(--color-muted);
      font-family: var(--font-body);
      letter-spacing: 0.01em;
      text-transform: none;
    }
    #bar-periods .lane[aria-pressed="true"] {
      background: transparent;
      color: var(--color-accent);
      border-bottom-color: var(--color-accent);
    }
    #bar-periods .lane[aria-pressed="true"]:hover { color: var(--color-accent); }
    .bar-item + .bar-item { border-top: var(--rule) solid var(--color-rule); }
    .bar-row {
      display: grid;
      grid-template-columns: minmax(7.5rem, 11.5rem) minmax(0, 1fr);
      align-items: center;
      gap: var(--space-sm);
      width: 100%;
      min-height: 2.15rem;
      padding: 0.35rem 0;
      border: 0;
      background: transparent;
      color: inherit;
      font: inherit;
      text-align: left;
      cursor: pointer;
    }
    .bar-row:hover .bar-name { color: var(--color-accent); }
    .bar-row:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 1px; }
    .bar-row[aria-expanded="true"] { background: var(--color-paper-3); }
    .bar-name {
      font-family: var(--font-display);
      font-size: var(--text-sm);
      letter-spacing: -0.01em;
      line-height: 1.2;
      color: var(--color-ink);
    }
    .bar-track {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 1px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
    }
    .bar-side { display: flex; align-items: center; gap: 0.45rem; min-width: 0; }
    .bar-side--neg { justify-content: flex-end; }
    .bar-side--pos { justify-content: flex-start; }
    .bar-axis { width: 1px; height: 1.35rem; background: var(--color-rule); }
    .bar-item:first-child .bar-name { font-size: var(--text-lg); font-weight: 600; }
    .bar-item:first-child .bar-pct { font-size: var(--text-md); font-weight: 600; }
    .bar-fill {
      flex: 0 0 auto;
      height: 1.15rem;
      width: max(0.35rem, calc(var(--share) * (100% - 5.5rem)));
      background: var(--color-bar);
      transform-origin: left center;
      animation: bar-grow var(--dur-long) var(--ease-out) both;
      animation-delay: calc(var(--i, 0) * 28ms);
    }
    .bar-fill.down { background: var(--color-bar-down); transform-origin: right center; }
    .bar-fill.flat { background: var(--color-rule); }
    @keyframes bar-grow {
      from { transform: scaleX(0); }
      to { transform: scaleX(1); }
    }
    .bar-pct {
      flex: 0 0 auto;
      color: var(--color-ink);
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .bar-detail { padding: 0 0 var(--space-sm); overflow-x: auto; }
    @media (max-width: 700px) {
      .nav-edge {
        grid-template-columns: minmax(0, 1fr) auto;
        grid-template-areas:
          "brand tools"
          "keys keys"
          "lanes lanes";
      }
      .search { width: 6.5rem; }
      .tape-row { grid-template-columns: 1fr; row-gap: 2px; }
      .bar-row { grid-template-columns: minmax(5.5rem, 8.5rem) minmax(0, 1fr); }
    }
    @media (prefers-reduced-motion: reduce) {
      .lane, .sort, .chip, .ticker { transition: none; }
      .bar-fill { animation: none; }
    }
  </style>
</head>
<body>
<a class="skip-link" href="#tape">Skip to tape</a>
<header class="nav-edge">
  <div class="brand">
    <span class="product">Theme Tape</span>
  </div>
  <nav class="bbg-keys" aria-label="Terminal panels">
    <a class="desk-tab" href="index.html#thematic-title">Themes</a>
    <div class="desk-menu">
      <button class="desk-tab" type="button" aria-haspopup="menu" aria-expanded="false" aria-controls="menu-leaders">Leaders <span class="desk-caret" aria-hidden="true"></span></button>
      <div id="menu-leaders" class="desk-menu__panel" role="menu" hidden>
        <a role="menuitem" href="index.html#liquid-title">Liquid Leaders</a>
        <a role="menuitem" href="index.html#focus-title">Focus</a>
        <a role="menuitem" href="index.html#nel-title">Non-extended</a>
      </div>
    </div>
    <div class="desk-menu">
      <button class="desk-tab" type="button" aria-haspopup="menu" aria-expanded="false" aria-controls="menu-setups">Setups <span class="desk-caret" aria-hidden="true"></span></button>
      <div id="menu-setups" class="desk-menu__panel" role="menu" hidden>
        <a role="menuitem" href="index.html#rs-title">Relative strength</a>
        <a role="menuitem" href="index.html#ema8-title">8-week</a>
        <a role="menuitem" href="index.html#ma-stack-title">Moving averages</a>
        <a role="menuitem" href="index.html#aplus-title">Flag breakouts</a>
      </div>
    </div>
    <a class="desk-tab" href="theme_tracker.html" aria-current="page">Tape</a>
  </nav>
  <div class="tools">
    <div class="view-switch" role="group" aria-label="How to show the tape">
      <button type="button" class="lane" data-tape-view="table" aria-pressed="true">Table</button>
      <button type="button" class="lane" data-tape-view="bars" aria-pressed="false">Bars</button>
    </div>
    <button type="button" class="lane" id="theme-toggle" aria-pressed="false">Dark</button>
    <label class="visually-hidden" for="q" style="position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)">Filter themes</label>
    <input id="q" class="search" type="search" placeholder="Filter" autocomplete="off" enterkeyhint="search">
    <span id="clock" class="clock"></span>
  </div>
  <div class="lanes" id="lanes" role="toolbar" aria-label="Theme lanes"></div>
</header>
<p class="lede" id="lede"></p>
<div id="tape" class="tape"></div>
<div class="table-scroll">
  <table>
    <thead>
      <tr id="head"></tr>
    </thead>
    <tbody id="body"></tbody>
  </table>
</div>
<div id="bars" class="bars" hidden>
  <div class="bar-periods" id="bar-periods" role="toolbar" aria-label="Bar period"></div>
  <div id="bar-list"></div>
</div>
<p class="foot" id="foot"></p>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const data = JSON.parse(document.getElementById("payload").textContent);
const PERIODS = [["today","Today"],["w1","1W"],["m1","1M"],["m3","3M"],["m6","6M"],["ytd","YTD"]];
const lanesEl = document.getElementById("lanes");
const bodyEl = document.getElementById("body");
const headEl = document.getElementById("head");
const tapeEl = document.getElementById("tape");
const tableScrollEl = document.querySelector(".table-scroll");
const barsEl = document.getElementById("bars");
const barPeriodsEl = document.getElementById("bar-periods");
const barListEl = document.getElementById("bar-list");
const ledeEl = document.getElementById("lede");
const footEl = document.getElementById("foot");
const searchEl = document.getElementById("q");
let lane = "All";
let sortKey = "today";
let sortDir = -1;
let query = "";
let symbolFilter = [];
let openId = "";
let view = "table";
try { if (localStorage.getItem("lld-tape-view") === "bars") view = "bars"; } catch (e) {}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function finite(value) { return typeof value === "number" && Number.isFinite(value); }
function tone(value) {
  if (!finite(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}
function fmt(value) {
  if (!finite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return sign + value.toFixed(2) + "%";
}
function tick() {
  const text = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"
  }).format(new Date());
  document.getElementById("clock").textContent = text + " NY";
}
function visible() {
  const needle = query.trim().toLowerCase();
  return data.themes.filter(theme => {
    if (lane !== "All" && theme.lane !== lane) return false;
    const memberSymbols = [...(theme.members || []).map(member => member.symbol), ...(theme.unquoted || [])].map(symbol => String(symbol).toUpperCase());
    if (symbolFilter.length && symbolFilter.some(symbol => memberSymbols.includes(symbol))) return true;
    if (!needle) return symbolFilter.length === 0;
    const hay = [theme.name, theme.lane, theme.blurb, ...memberSymbols].join(" ").toLowerCase();
    return hay.includes(needle);
  }).sort((a, b) => {
    if (sortKey === "name" || sortKey === "lane") {
      const av = sortKey === "name" ? a.name : a.lane;
      const bv = sortKey === "name" ? b.name : b.lane;
      const compared = av.localeCompare(bv);
      return compared * (sortDir === 1 ? 1 : -1);
    }
    const av = a[sortKey];
    const bv = b[sortKey];
    const aMissing = !finite(av);
    const bMissing = !finite(bv);
    if (aMissing && bMissing) return a.name.localeCompare(b.name);
    if (aMissing) return 1;
    if (bMissing) return -1;
    if (av === bv) return a.name.localeCompare(b.name);
    return (av - bv) * sortDir;
  });
}
function paintLanes() {
  const lanes = ["All", ...data.lanes];
  lanesEl.innerHTML = lanes.map(name => `<button type="button" class="lane" data-lane="${esc(name)}" aria-pressed="${name === lane ? "true" : "false"}">${esc(name)}</button>`).join("");
}
function paintHead() {
  const cols = [["name","Theme"], ["lane","Lane"], ...PERIODS, ["breadth","Breadth"]];
  headEl.innerHTML = cols.map(([key, label]) => {
    const active = key === sortKey;
    const arrow = !active ? "" : (sortDir < 0 ? " ▼" : " ▲");
    return `<th><button type="button" class="sort" data-sort="${key}" aria-sort="${active ? (sortDir < 0 ? "descending" : "ascending") : "none"}">${esc(label)}${arrow}</button></th>`;
  }).join("") + "<th>Leader</th>";
}
function memberTable(theme) {
  const head = `<tr><th>Symbol</th><th>Name</th>${PERIODS.map(([, label]) => `<th>${label}</th>`).join("")}</tr>`;
  const rows = theme.members.map(member => `<tr><td><a class="ticker" href="${esc(member.url)}" target="_blank" rel="noopener noreferrer">${esc(member.symbol)}</a></td><td>${esc(member.description || "—")}</td>${PERIODS.map(([key]) => `<td class="${tone(member[key])}">${fmt(member[key])}</td>`).join("")}</tr>`).join("");
  const missing = theme.unquoted.length ? `<p class="miss">These stocks have no price: ${theme.unquoted.map(esc).join(", ")}.</p>` : "";
  const proxy = theme.etf ? ` The fund ${esc(theme.etf)} is a label only. It is not part of the average.` : "";
  return `<p class="blurb">${esc(theme.blurb)}${proxy}</p>${missing}<table class="members"><thead>${head}</thead><tbody>${rows || `<tr><td colspan="8">No stocks in this theme have a price.</td></tr>`}</tbody></table>`;
}
function paintTape(rows) {
  const ranked = rows.filter(theme => finite(theme.today));
  const leaders = [...ranked].sort((a, b) => b.today - a.today).slice(0, 6);
  const laggards = [...ranked].sort((a, b) => a.today - b.today).slice(0, 4);
  const chips = (label, list) => {
    if (!list.length) return "";
    const buttons = list.map(theme => `<button type="button" class="chip" data-open="${esc(theme.id)}"><span>${esc(theme.name)}</span><span class="${tone(theme.today)}">${fmt(theme.today)}</span></button>`).join("");
    return `<div class="tape-row"><span class="tape-label">${label}</span><div class="tape-chips">${buttons}</div></div>`;
  };
  tapeEl.innerHTML = chips("Leaders", leaders) + chips("Laggards", laggards);
}
function paintBars(rows) {
  const period = PERIODS.some(([key]) => key === sortKey) ? sortKey : "today";
  const values = rows.map(theme => theme[period]).filter(finite);
  const maxAbs = values.reduce((peak, value) => Math.max(peak, Math.abs(value)), 0);
  barPeriodsEl.innerHTML = PERIODS.map(([key, label]) => `<button type="button" class="lane" data-sort="${key}" aria-pressed="${key === period ? "true" : "false"}">${esc(label)}</button>`).join("");
  barListEl.innerHTML = rows.map((theme, index) => {
    const value = theme[period];
    const share = finite(value) && maxAbs > 0 ? Math.abs(value) / maxAbs : 0;
    const open = theme.id === openId;
    const pct = `<span class="bar-pct">${fmt(value)}</span>`;
    const fill = finite(value) && value !== 0 ? `<span class="bar-fill ${tone(value)}" style="--share:${share.toFixed(4)}"></span>` : "";
    const neg = value < 0 ? `${pct}${fill}` : "";
    const pos = value < 0 ? "" : `${fill}${pct}`;
    const mark = `<span class="bar-side bar-side--neg">${neg}</span><span class="bar-axis"></span><span class="bar-side bar-side--pos">${pos}</span>`;
    return `<div class="bar-item" style="--i:${Math.min(index, 12)}"><button type="button" class="bar-row" data-open="${esc(theme.id)}" aria-expanded="${open ? "true" : "false"}"><span class="bar-name">${esc(theme.name)}</span><span class="bar-track">${mark}</span></button>${open ? `<div class="bar-detail">${memberTable(theme)}</div>` : ""}</div>`;
  }).join("") || `<p class="empty">No themes match this filter.</p>`;
}
function paint() {
  const rows = visible();
  document.querySelectorAll("[data-tape-view]").forEach(button => {
    button.setAttribute("aria-pressed", button.dataset.tapeView === view ? "true" : "false");
  });
  const themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) themeBtn.setAttribute("aria-pressed", document.documentElement.dataset.theme === "dark" ? "true" : "false");
  tableScrollEl.hidden = view !== "table";
  barsEl.hidden = view !== "bars";
  tapeEl.hidden = view === "bars";
  paintLanes();
  paintHead();
  paintTape(lane === "All" && !query ? data.themes : rows);
  paintBars(rows);
  const totalThemes = data.themes.length;
  const shownThemes = rows.length;
  const showing = shownThemes < totalThemes
    ? (shownThemes === 1 ? "1 theme is showing. " : `${shownThemes} themes are showing. `)
    : "";
  ledeEl.textContent = `${showing}The date is ${data.as_of}. Each theme is an equal-weight average.`;
  footEl.textContent = "Select a theme to see its stocks. The numbers are the percent change. Stocks with no price are listed, and they are left out of the average.";
  bodyEl.innerHTML = rows.map(theme => {
    const cells = PERIODS.map(([key]) => `<td class="${tone(theme[key])}">${fmt(theme[key])}</td>`).join("");
    const breadth = finite(theme.breadth)
      ? `<span class="meter" style="--fill:${Math.round(theme.breadth * 100)}%"><i></i></span>${theme.green}/${theme.prints}`
      : "—";
    const leader = theme.leader
      ? `<a class="ticker" href="${esc(theme.leader.url)}" target="_blank" rel="noopener noreferrer">${esc(theme.leader.symbol)}</a> <span class="${tone(theme.leader.today)}">${fmt(theme.leader.today)}</span>`
      : "—";
    const open = theme.id === openId;
    return `<tr>
      <td><button type="button" class="sort name" data-open="${esc(theme.id)}" aria-expanded="${open ? "true" : "false"}">${esc(theme.name)}</button></td>
      <td class="lane-tag">${esc(theme.lane)}</td>
      ${cells}
      <td>${breadth}</td>
      <td>${leader}</td>
    </tr>${open ? `<tr class="detail"><td colspan="10">${memberTable(theme)}</td></tr>` : ""}`;
  }).join("") || `<tr><td class="empty" colspan="10">No themes match this filter.</td></tr>`;
}
document.addEventListener("click", event => {
  const themeBtn = event.target.closest("#theme-toggle");
  if (themeBtn) {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    if (next === "dark") document.documentElement.dataset.theme = "dark";
    else delete document.documentElement.dataset.theme;
    try { localStorage.setItem("lld-tape-theme", next); } catch (e) {}
    themeBtn.setAttribute("aria-pressed", next === "dark" ? "true" : "false");
    return;
  }
  const viewBtn = event.target.closest("[data-tape-view]");
  if (viewBtn) {
    view = viewBtn.dataset.tapeView === "bars" ? "bars" : "table";
    try { localStorage.setItem("lld-tape-view", view); } catch (e) {}
    if (view === "bars" && !PERIODS.some(([key]) => key === sortKey)) {
      sortKey = "today";
      sortDir = -1;
    }
    paint();
    return;
  }
  const laneBtn = event.target.closest("[data-lane]");
  if (laneBtn) {
    lane = laneBtn.dataset.lane;
    paint();
    return;
  }
  const sortBtn = event.target.closest("[data-sort]");
  if (sortBtn) {
    const key = sortBtn.dataset.sort;
    if (sortKey === key) sortDir *= -1;
    else { sortKey = key; sortDir = key === "name" || key === "lane" ? 1 : -1; }
    paint();
    return;
  }
  const opener = event.target.closest("[data-open]");
  if (opener && opener.tagName !== "A") {
    openId = openId === opener.dataset.open ? "" : opener.dataset.open;
    paint();
    if (openId) {
      const scope = view === "bars" ? "#bar-list" : "#body";
      document.querySelector(`${scope} [data-open="${CSS.escape(openId)}"]`)?.scrollIntoView({ block: "nearest" });
    }
  }
});
searchEl.addEventListener("input", () => { query = searchEl.value; symbolFilter = []; paint(); });
function closeDeskMenus() {
  document.querySelectorAll(".desk-menu__panel").forEach(panel => {
    panel.hidden = true;
    const toggle = document.querySelector(`[aria-controls="${panel.id}"]`);
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  });
}
document.addEventListener("click", event => {
  const toggle = event.target.closest(".desk-tab[aria-haspopup]");
  if (toggle) {
    const panel = document.getElementById(toggle.getAttribute("aria-controls"));
    const open = toggle.getAttribute("aria-expanded") === "true";
    closeDeskMenus();
    if (!open && panel) {
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    }
    return;
  }
  if (!event.target.closest(".desk-menu")) closeDeskMenus();
});
document.addEventListener("keydown", event => {
  const typing = Boolean(event.target.closest("input, textarea, select"));
  const menu = event.target.closest(".desk-menu__panel");
  if (menu && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    const items = [...menu.querySelectorAll("a")];
    const index = items.indexOf(document.activeElement);
    const next = event.key === "ArrowDown" ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
    event.preventDefault();
    items[next]?.focus();
    return;
  }
  if (!typing && event.key === "/" && document.activeElement !== searchEl) {
    event.preventDefault();
    searchEl.focus();
  }
  if (event.key === "Escape") {
    if (document.querySelector(".desk-menu__panel:not([hidden])")) {
      closeDeskMenus();
      return;
    }
    openId = "";
    paint();
  }
});
tick();
setInterval(tick, 1000);
const params = new URLSearchParams(window.location.search);
const industry = params.get("industry");
if (industry) {
  searchEl.value = industry;
  query = industry;
}
symbolFilter = (params.get("symbols") || "").split(",").map(symbol => symbol.trim().toUpperCase()).filter(Boolean);
paint();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
