#!/usr/bin/env python3
"""SPY, QQQ, and IWM implied volatility, open interest, and gamma walls.

Chains are CBOE's delayed quotes. Gamma is CBOE's gamma, signed so calls
are positive and puts are negative, for a 1% move. VIX and Nasdaq volatility
history comes from Yahoo.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
HTML_PATH = PROJECT_DIR / "monitor.html"
UNDERLYINGS = ("SPY", "QQQ", "IWM")
RATE = 0.04
CONTRACT = 100
TERM_CAP = 6
TERM_DAYS = 90
STRIKE_LIMIT = 31
STRIKE_BAND = 0.035
CBOE_URL = "https://cdn-api.cboe.com/api/global/delayed_quotes/options/{symbol}.json"


def bs_gamma(spot: float, strike: float, years: float, sigma: float, rate: float = RATE) -> float:
    """Black-Scholes gamma. Zero when the inputs cannot make a price."""
    if spot <= 0 or strike <= 0 or years <= 0 or sigma <= 0:
        return 0.0
    vol_time = sigma * math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * years) / vol_time
    return math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (spot * vol_time)


def dollar_gamma(gamma: float, open_interest: int, spot: float) -> float:
    """Dollar gamma for a 1% move in the underlying."""
    return gamma * open_interest * CONTRACT * spot * spot * 0.01


def closest_strike(strikes: list[float], spot: float) -> float:
    return min(strikes, key=lambda strike: (abs(strike - spot), strike))


def atm_iv(calls: list[dict], puts: list[dict], spot: float) -> float | None:
    """Average call and put implied volatility at the strike nearest the price."""
    strikes = sorted({
        row["strike"]
        for row in calls + puts
        if row.get("iv") and row["iv"] > 0
    })
    if not strikes or spot <= 0:
        return None
    strike = closest_strike(strikes, spot)
    prints = [
        row["iv"]
        for row in calls + puts
        if row["strike"] == strike and row.get("iv") and row["iv"] > 0
    ]
    if not prints:
        return None
    return sum(prints) / len(prints)


def gamma_flip(rows: list[dict], spot: float) -> float | None:
    """Price where net gamma crosses zero, nearest the last price."""
    ordered = sorted(rows, key=lambda row: row["strike"])
    crosses: list[float] = []
    for left, right in zip(ordered, ordered[1:]):
        low = left["gamma"]
        high = right["gamma"]
        if low == 0:
            crosses.append(left["strike"])
            continue
        if low * high < 0:
            span = right["strike"] - left["strike"]
            weight = abs(low) / (abs(low) + abs(high))
            crosses.append(left["strike"] + span * weight)
    if not crosses:
        return None
    return min(crosses, key=lambda price: (abs(price - spot), price))


def _slot() -> dict:
    return {"call_oi": 0, "put_oi": 0, "call_iv": None, "put_iv": None}


def build_book(calls: list[dict], puts: list[dict], spot: float, expiry: str, as_of: str) -> dict:
    """Open interest and net gamma by strike for one expiration."""
    grouped: dict[float, dict] = {}
    for side, rows in (("call", calls), ("put", puts)):
        for row in rows:
            slot = grouped.setdefault(float(row["strike"]), _slot())
            oi = int(row.get("oi") or 0)
            iv = row.get("iv")
            if side == "call":
                slot["call_oi"] += oi
                if iv and iv > 0:
                    slot["call_iv"] = float(iv)
            else:
                slot["put_oi"] += oi
                if iv and iv > 0:
                    slot["put_iv"] = float(iv)
    days = max((date.fromisoformat(expiry) - date.fromisoformat(as_of)).days, 1)
    years = days / 365
    scored = []
    for strike, slot in grouped.items():
        if slot["call_oi"] == 0 and slot["put_oi"] == 0:
            continue
        call_g = 0.0
        put_g = 0.0
        if slot["call_iv"] and slot["call_oi"]:
            call_g = dollar_gamma(bs_gamma(spot, strike, years, slot["call_iv"]), slot["call_oi"], spot)
        if slot["put_iv"] and slot["put_oi"]:
            put_g = -dollar_gamma(bs_gamma(spot, strike, years, slot["put_iv"]), slot["put_oi"], spot)
        scored.append({
            "strike": strike,
            "call_oi": slot["call_oi"],
            "put_oi": slot["put_oi"],
            "call_gamma": call_g,
            "put_gamma": put_g,
            "gamma": call_g + put_g,
        })
    near = [row for row in scored if spot <= 0 or abs(row["strike"] - spot) / spot <= STRIKE_BAND]
    if len(near) < 8:
        near = sorted(scored, key=lambda row: abs(row["strike"] - spot))[:STRIKE_LIMIT]
    elif len(near) > STRIKE_LIMIT:
        near = sorted(near, key=lambda row: abs(row["strike"] - spot))[:STRIKE_LIMIT]
    rows = sorted(near, key=lambda row: row["strike"])
    call_wall = None
    put_wall = None
    if any(row["call_gamma"] > 0 for row in rows):
        call_wall = max(rows, key=lambda row: row["call_gamma"])["strike"]
    if any(row["put_gamma"] < 0 for row in rows):
        put_wall = min(rows, key=lambda row: row["put_gamma"])["strike"]
    return {
        "expiry": expiry,
        "days": days,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "flip": gamma_flip(rows, spot),
        "strikes": rows,
    }


def upcoming_expirations(expirations: list[str], as_of: str, limit_days: int = TERM_DAYS, cap: int = TERM_CAP) -> list[str]:
    today = date.fromisoformat(as_of)
    picked = []
    for raw in expirations:
        day = date.fromisoformat(raw)
        if day < today:
            continue
        if (day - today).days > limit_days:
            break
        picked.append(raw)
        if len(picked) >= cap:
            break
    return picked


def parse_occ(symbol: str, root: str) -> tuple[str, str, float]:
    """OCC symbol to expiry, call or put, and strike."""
    rest = symbol[len(root):]
    expiry = f"20{rest[0:2]}-{rest[2:4]}-{rest[4:6]}"
    side = "call" if rest[6] == "C" else "put"
    return expiry, side, int(rest[7:]) / 1000


def select_term(points: list[dict]) -> list[dict]:
    """Six tenors spread from a few days out to about three months."""
    targets = (2, 7, 14, 30, 60, 90)
    chosen = []
    used: set[str] = set()
    for target in targets:
        pool = [point for point in points if point["expiry"] not in used and 0 <= point["days"] <= TERM_DAYS]
        if not pool:
            break
        best = min(pool, key=lambda point: (abs(point["days"] - target), point["days"]))
        if target >= 30 and abs(best["days"] - target) > 25:
            continue
        used.add(best["expiry"])
        chosen.append(best)
    return sorted(chosen, key=lambda point: point["days"])


def _history_points(symbol: str, sessions: int = 60) -> list[dict]:
    import yfinance as yf

    hist = yf.Ticker(symbol).history(period="6mo", auto_adjust=True)
    if hist is None or hist.empty:
        return []
    points = []
    for idx, row in hist.tail(sessions).iterrows():
        close = row.get("Close")
        if close is None or (isinstance(close, float) and math.isnan(close)):
            continue
        stamp = idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10]
        points.append({"date": stamp, "close": round(float(close), 2)})
    return points


def _number(value) -> float:
    if value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number):
        return 0.0
    return number


def fetch_cboe(symbol: str) -> dict:
    import urllib.request

    request = urllib.request.Request(
        CBOE_URL.format(symbol=symbol),
        headers={"User-Agent": "liquid-leadership/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload


def contracts_from_cboe(symbol: str, options: list[dict]) -> list[dict]:
    rows = []
    for option in options:
        raw = str(option.get("option") or "")
        if not raw.startswith(symbol):
            continue
        try:
            expiry, side, strike = parse_occ(raw, symbol)
        except (ValueError, IndexError):
            continue
        iv = _number(option.get("iv"))
        rows.append({
            "expiry": expiry,
            "side": side,
            "strike": strike,
            "oi": int(_number(option.get("open_interest"))),
            "iv": iv if iv > 0.02 else None,
            "gamma": _number(option.get("gamma")),
        })
    return rows


def book_from_contracts(contracts: list[dict], spot: float, expiry: str, as_of: str) -> dict:
    """Open interest and net gamma by strike, using the chain's own gamma."""
    grouped: dict[float, dict] = {}
    for row in contracts:
        if row["expiry"] != expiry:
            continue
        slot = grouped.setdefault(row["strike"], {"call_oi": 0, "put_oi": 0, "call_gamma": 0.0, "put_gamma": 0.0})
        exposure = dollar_gamma(row["gamma"], row["oi"], spot) if row["gamma"] and row["oi"] else 0.0
        if row["side"] == "call":
            slot["call_oi"] += row["oi"]
            slot["call_gamma"] += exposure
        else:
            slot["put_oi"] += row["oi"]
            slot["put_gamma"] -= exposure
    scored = []
    for strike, slot in grouped.items():
        if slot["call_oi"] == 0 and slot["put_oi"] == 0:
            continue
        scored.append({
            "strike": strike,
            "call_oi": slot["call_oi"],
            "put_oi": slot["put_oi"],
            "call_gamma": slot["call_gamma"],
            "put_gamma": slot["put_gamma"],
            "gamma": slot["call_gamma"] + slot["put_gamma"],
        })
    near = [row for row in scored if spot <= 0 or abs(row["strike"] - spot) / spot <= STRIKE_BAND]
    if len(near) < 8:
        near = sorted(scored, key=lambda row: abs(row["strike"] - spot))[:STRIKE_LIMIT]
    elif len(near) > STRIKE_LIMIT:
        near = sorted(near, key=lambda row: abs(row["strike"] - spot))[:STRIKE_LIMIT]
    rows = sorted(near, key=lambda row: row["strike"])
    call_wall = max(rows, key=lambda row: row["call_gamma"])["strike"] if any(row["call_gamma"] > 0 for row in rows) else None
    put_wall = min(rows, key=lambda row: row["put_gamma"])["strike"] if any(row["put_gamma"] < 0 for row in rows) else None
    days = max((date.fromisoformat(expiry) - date.fromisoformat(as_of)).days, 0)
    return {
        "expiry": expiry,
        "days": days,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "flip": gamma_flip(rows, spot),
        "strikes": rows,
    }


def underlying_from_cboe(symbol: str, payload: dict, as_of: str) -> dict:
    data = payload["data"]
    spot = _number(data.get("current_price"))
    change = _number(data.get("price_change_percent"))
    iv30 = _number(data.get("iv30"))
    front_iv = iv30 / 100 if iv30 > 1 else (iv30 or None)
    contracts = contracts_from_cboe(symbol, data.get("options") or [])
    by_expiry: dict[str, list[dict]] = {}
    for row in contracts:
        by_expiry.setdefault(row["expiry"], []).append(row)
    term_points = []
    totals = []
    for expiry, rows in by_expiry.items():
        days = (date.fromisoformat(expiry) - date.fromisoformat(as_of)).days
        if days < 0 or days > TERM_DAYS:
            continue
        iv = atm_iv(
            [{"strike": row["strike"], "iv": row["iv"], "oi": row["oi"]} for row in rows if row["side"] == "call"],
            [{"strike": row["strike"], "iv": row["iv"], "oi": row["oi"]} for row in rows if row["side"] == "put"],
            spot,
        )
        if iv and iv > 0.02:
            term_points.append({"expiry": expiry, "days": days, "iv": iv})
        if days <= 45:
            totals.append((expiry, sum(row["oi"] for row in rows)))
    book = None
    if totals:
        expiry = max(totals, key=lambda item: item[1])[0]
        book = book_from_contracts(by_expiry[expiry], spot, expiry, as_of)
    return {
        "symbol": symbol,
        "spot": spot,
        "change_pct": change,
        "front_iv": front_iv,
        "front_expiry": None,
        "term": select_term(term_points),
        "book": book,
    }


def build_snapshot(as_of: str | None = None) -> dict:
    """Download CBOE chains and the two volatility indexes."""
    first = fetch_cboe("SPY")
    stamp = as_of or str(first.get("timestamp") or "")[:10]
    names = [underlying_from_cboe("SPY", first, stamp)]
    for symbol in UNDERLYINGS[1:]:
        try:
            names.append(underlying_from_cboe(symbol, fetch_cboe(symbol), stamp))
        except Exception as error:
            names.append({"symbol": symbol, "error": str(error), "term": [], "book": None})
    return {
        "as_of": stamp,
        "names": names,
        "vol": {
            "vix": _history_points("^VIX"),
            "vxn": _history_points("^VXN"),
        },
    }


def render_html(snapshot: dict) -> str:
    payload = json.dumps(snapshot, separators=(",", ":")).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__PAYLOAD__", payload)


def write_monitor(output_dir: Path, snapshot: dict | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = snapshot if snapshot is not None else build_snapshot()
    HTML_PATH.write_text(render_html(data), encoding="utf-8")
    (output_dir / "options_monitor.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Monitor: {data.get('as_of')} | {len(data.get('names') or [])} underlyings")
    return HTML_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_monitor(args.output_dir)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Monitor | GB Market Terminal</title>
  <meta name="description" content="Implied volatility, open interest, and gamma walls for SPY, QQQ, and IWM.">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="preload" href="assets/fonts/newsreader-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/source-sans-3-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css?v=20261015j">
  <style>
    /* Hallmark · monitor board · terminal tokens */
    html { color-scheme: dark; }
    html, body { overflow-x: clip; margin: 0; }
    body {
      background:
        radial-gradient(72rem 34rem at 55% 0%, oklch(38% 0.06 245 / 0.55), transparent 62%),
        radial-gradient(80rem 46rem at 72% 108%, oklch(48% 0.1 215 / 0.42), transparent 56%),
        radial-gradient(36rem 28rem at 0% 46%, oklch(28% 0.05 270 / 0.35), transparent 54%),
        #0e1116;
      color: var(--color-ink-2);
      font-family: var(--font-body);
      font-size: var(--text-sm);
      line-height: 1.4;
    }
    body::before {
      content: "";
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      opacity: 0.28;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }
    .lede, main { position: relative; z-index: 1; }
    h1, h2, button, a { font-style: normal; }
    .skip-link {
      position: absolute;
      left: var(--space-sm);
      top: var(--space-sm);
      z-index: var(--z-sticky-nav);
      padding: var(--space-xs) var(--space-sm);
      background: var(--color-accent);
      color: var(--color-accent-ink);
      text-decoration: none;
      transform: translateY(-200%);
    }
    .skip-link:focus-visible { transform: none; outline: 2px solid var(--color-focus); }
    .nav-edge {
      position: sticky;
      top: 0;
      z-index: var(--z-sticky-nav);
      display: flex;
      align-items: center;
      gap: var(--space-sm);
      min-height: var(--banner-height);
      padding: var(--space-xs) max(var(--page-gutter), env(safe-area-inset-right)) var(--space-xs) max(var(--page-gutter), env(safe-area-inset-left));
      background: var(--color-paper);
      border-bottom: var(--rule) solid var(--color-rule);
    }
    .brand { font-family: var(--font-display); color: var(--color-ink); text-decoration: none; }
    .bbg-keys { display: flex; flex-wrap: wrap; min-width: 0; }
    .desk-menu { position: relative; display: flex; }
    .desk-tab {
      display: flex;
      align-items: center;
      min-height: var(--control-height);
      padding: 0 var(--space-12);
      border: 0;
      background: transparent;
      color: var(--color-muted);
      font-family: var(--font-body);
      font-size: var(--text-xs);
      text-decoration: none;
      cursor: pointer;
    }
    .desk-tab[aria-current="page"], .desk-tab[aria-expanded="true"] { color: var(--color-accent); }
    .desk-tab:hover { color: var(--color-accent); }
    .desk-tab:focus-visible, .quote:focus-visible, .symbol:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
    .desk-menu__panel {
      position: absolute;
      top: 100%;
      left: 0;
      z-index: var(--z-raised);
      min-width: 11rem;
      padding: var(--space-xs) 0;
      background: var(--color-paper);
      border: var(--rule) solid var(--color-rule);
    }
    .desk-menu__panel[hidden] { display: none; }
    .desk-menu__panel a {
      display: block;
      padding: var(--space-xs) var(--space-sm);
      color: var(--color-ink-2);
      text-decoration: none;
    }
    .desk-menu__panel a:hover { color: var(--color-accent); }
    main {
      padding: var(--space-md) max(var(--page-gutter), env(safe-area-inset-right)) var(--space-xl) max(var(--page-gutter), env(safe-area-inset-left));
    }
    h1 {
      margin: 0 0 var(--space-2xs);
      font-family: var(--font-display);
      font-size: var(--text-xl);
      font-weight: 600;
      color: var(--color-ink);
    }
    .lede { margin: 0 0 var(--space-md); color: var(--color-muted); }
    .quotes, .split { display: grid; gap: var(--space-sm); }
    .quotes { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: var(--space-md); }
    .split { grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr); margin-bottom: var(--space-md); }
    .quote, .panel {
      min-width: 0;
      padding: var(--space-sm) var(--space-md);
      border: var(--rule) solid color-mix(in oklch, white 28%, transparent);
      border-radius: 12px;
      background: color-mix(in oklch, var(--color-paper-3) 46%, transparent);
      box-shadow: inset 0 1px 0 color-mix(in oklch, white 32%, transparent);
      backdrop-filter: blur(14px) saturate(1.35);
      -webkit-backdrop-filter: blur(14px) saturate(1.35);
      color: inherit;
      font: inherit;
      text-align: left;
    }
    .quote { cursor: pointer; }
    .quote[aria-pressed="true"] { border-color: var(--color-accent); }
    .quote-symbol, .panel h2 {
      margin: 0;
      font-family: var(--font-display);
      font-size: var(--text-lg);
      font-weight: 600;
      color: var(--color-ink);
    }
    .quote-symbol { font-size: var(--text-display); font-weight: 400; letter-spacing: -0.02em; line-height: 1.1; }
    .quote-last { margin: var(--space-2xs) 0 0; font-family: var(--font-display); font-size: var(--text-md); color: var(--color-ink); }
    .quote .muted { font-size: var(--text-xs); }
    .up { color: var(--color-up); }
    .down { color: var(--color-down); }
    .muted { color: var(--color-muted); }
    .panel h2 { font-size: var(--text-md); margin-bottom: var(--space-xs); }
    .symbols { display: flex; gap: var(--space-xs); margin: 0 0 var(--space-sm); }
    .symbol {
      min-height: var(--control-height);
      padding: 0 var(--space-sm);
      border: 0;
      border-bottom: 2px solid transparent;
      background: transparent;
      color: var(--color-muted);
      font-family: var(--font-body);
      font-size: var(--text-sm);
      cursor: pointer;
    }
    .symbol[aria-pressed="true"] { color: var(--color-ink); border-bottom-color: var(--color-accent); }
    svg { display: block; width: 100%; height: auto; }
    .swatch { display: inline-block; width: 0.7rem; height: 0.7rem; margin-right: 0.25rem; vertical-align: -0.05rem; }
    .swatch-spy { background: var(--color-accent); }
    .swatch-qqq { background: var(--color-frame-6m); }
    .swatch-iwm { background: var(--color-frame-3m); }
    .swatch-vix { background: var(--color-ink); }
    .swatch-vxn { background: var(--color-muted); }
    .swatch-call { background: var(--color-up); }
    .swatch-put { background: var(--color-down); }
    .legend, .walls, .method { margin: var(--space-xs) 0 0; }
    .walls { color: var(--color-ink); }
    .chart-call { fill: var(--color-up); }
    .chart-put { fill: var(--color-down); }
    .chart-spy { stroke: var(--color-accent); }
    .chart-qqq { stroke: var(--color-frame-6m); }
    .chart-iwm { stroke: var(--color-frame-3m); }
    .chart-vix { stroke: var(--color-ink); }
    .chart-vxn { stroke: var(--color-muted); }
    .axis { stroke: var(--color-rule); }
    .tick { fill: var(--color-muted); font-family: var(--font-body); font-size: 11px; }
    @media (max-width: 800px) {
      .quotes, .split { grid-template-columns: minmax(0, 1fr); }
    }
    @media (prefers-reduced-transparency: reduce) {
      body { background: var(--color-paper); }
      body::before { display: none; }
      .quote, .panel {
        background: var(--color-paper-3);
        border-color: var(--color-rule);
        box-shadow: none;
        backdrop-filter: none;
      }
    }
  </style>
  <link rel="stylesheet" href="nav.css?v=20261015m">
  <link rel="stylesheet" href="charts.css?v=20261015d">
  <link rel="stylesheet" href="shadcn-chart.css?v=20261015g">
</head>
<body>
<a class="skip-link" href="#monitor">Skip to monitor</a>
<header class="nav-edge">
  <a class="brand" href="themes.html">GB Market Terminal</a>
  <nav class="bbg-keys" aria-label="Terminal panels">
    <a class="desk-tab" href="regime.html">Regime</a>
    <a class="desk-tab" href="monitor.html" aria-current="page">Monitor</a>
    <a class="desk-tab" href="themes.html">Themes</a>
    <a class="desk-tab" href="liquid.html">Leaders</a>
    <a class="desk-tab" href="rs.html">Setups</a>
    <a class="desk-tab" href="tape.html">Tape</a>
    <a class="desk-tab" href="crowding.html">Crowding</a>
  </nav>
</header>
<main id="monitor">
  <h1>Monitor</h1>
  <p class="lede" id="lede"></p>
  <div class="quotes" id="quotes"></div>
  <div class="split">
    <section class="panel" aria-labelledby="iv-title">
      <h2 id="iv-title">Implied volatility</h2>
      <div id="iv-chart"></div>
      <p class="legend"><span class="swatch swatch-spy"></span>SPY <span class="swatch swatch-qqq"></span>QQQ <span class="swatch swatch-iwm"></span>IWM</p>
    </section>
    <section class="panel" aria-labelledby="index-title">
      <h2 id="index-title">Volatility indexes</h2>
      <div id="index-chart"></div>
      <p class="legend"><span class="swatch swatch-vix"></span>VIX <span class="swatch swatch-vxn"></span>Nasdaq volatility</p>
    </section>
  </div>
  <div class="symbols" id="symbols" role="group" aria-label="Underlying"></div>
  <section class="panel" aria-labelledby="oi-title">
    <h2 id="oi-title">Open interest</h2>
    <div id="oi-chart"></div>
    <p class="legend"><span class="swatch swatch-call"></span>Calls <span class="swatch swatch-put"></span>Puts</p>
  </section>
  <section class="panel" aria-labelledby="gamma-title" style="margin-top:var(--space-sm)">
    <h2 id="gamma-title">Gamma</h2>
    <div id="gamma-chart"></div>
    <p class="walls" id="walls"></p>
  </section>
  <p class="method muted" id="method"></p>
</main>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script src="shadcn-charts.js?v=20261015g"></script>
<script>
const data = JSON.parse(document.getElementById("payload").textContent);
const names = (data.names || []).filter(item => item && item.book);
let current = names[0] ? names[0].symbol : "";
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}
function pct(value, digits) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const sign = number > 0 ? "+" : "";
  return sign + number.toFixed(digits == null ? 2 : digits) + "%";
}
function ivPct(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return (number * 100).toFixed(1) + "%";
}
function money(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function strikeLabel(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}
function compact(value) {
  const number = Math.abs(Number(value) || 0);
  if (number >= 1e9) return (number / 1e9).toFixed(1) + "b";
  if (number >= 1e6) return (number / 1e6).toFixed(1) + "m";
  if (number >= 1e3) return (number / 1e3).toFixed(1) + "k";
  return String(Math.round(number));
}
function tone(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) return "";
  return number > 0 ? "up" : "down";
}
const chartColors = {
  "chart-spy": "var(--chart-1)",
  "chart-qqq": "var(--chart-2)",
  "chart-iwm": "var(--chart-4)",
  "chart-vix": "var(--chart-4)",
  "chart-vxn": "var(--chart-2)"
};
function lineChart(host, series, yFormat) {
  const points = series.flatMap(item => item.points);
  if (!host || !points.length || !window.GBCharts) {
    if (host) host.innerHTML = "<p class='muted'>No print for this chart.</p>";
    return;
  }
  const keys = series.map((_, index) => "s" + index);
  const byX = new Map();
  series.forEach((item, index) => {
    item.points.forEach(point => {
      const row = byX.get(point.x) || { x: point.x, label: point.label || "" };
      row[keys[index]] = point.y;
      if (point.label) row.label = point.label;
      byX.set(point.x, row);
    });
  });
  GBCharts.mount(host, {
    type: series.length === 1 ? "area" : "line",
    data: [...byX.values()].sort((a, b) => a.x - b.x),
    xKey: "label",
    series: series.map((item, index) => ({
      key: keys[index],
      label: item.label || item.klass,
      color: chartColors[item.klass] || "var(--chart-1)"
    })),
    yFormat,
    height: "15rem"
  });
}
function signedCompact(value) {
  const text = compact(value).replace(/\.0([kmb])$/, "$1");
  return value < 0 ? "-" + text : text;
}
function priceX(marks, spot) {
  const price = Number(spot);
  if (!marks.length || !Number.isFinite(price)) return null;
  if (price <= marks[0].strike) return marks[0].x;
  const last = marks[marks.length - 1];
  if (price >= last.strike) return last.x;
  for (let i = 0; i < marks.length - 1; i++) {
    const left = marks[i], right = marks[i + 1];
    if (price < left.strike || price > right.strike) continue;
    const span = right.strike - left.strike;
    return span ? left.x + (right.x - left.x) * ((price - left.strike) / span) : left.x;
  }
  return null;
}
function placePrice(host, spot) {
  const svg = host.querySelector(".recharts-wrapper svg");
  if (!svg) return;
  const groups = [...svg.querySelectorAll(".recharts-bar")];
  if (!groups.length) return;
  const series = groups.map(group => [...group.querySelectorAll(".recharts-bar-rectangle")]);
  const count = series[0].length;
  if (!count || series.some(list => list.length !== count)) return;
  const rows = host.__strikes || [];
  if (rows.length !== count) return;
  const marks = rows.map((row, index) => {
    const boxes = series.map(list => list[index].getBBox());
    const left = Math.min(...boxes.map(box => box.x));
    const right = Math.max(...boxes.map(box => box.x + box.width));
    return { strike: Number(row.strike), x: (left + right) / 2 };
  });
  const x = priceX(marks, spot);
  const grid = svg.querySelector(".recharts-cartesian-grid");
  if (x == null || !grid) return;
  const box = grid.getBBox();
  const label = Number(spot).toFixed(2);
  const ns = "http://www.w3.org/2000/svg";
  let line = svg.querySelector(".price-line");
  let tag = svg.querySelector(".price-tag");
  const prev = line ? Number(line.getAttribute("x1")) : NaN;
  if (line && tag && tag.textContent === label && Math.abs(prev - x) < 0.5) return;
  if (!line) {
    line = document.createElementNS(ns, "line");
    line.setAttribute("class", "price-line");
    line.setAttribute("stroke", "var(--color-accent)");
    line.setAttribute("stroke-width", "1.5");
    line.setAttribute("pointer-events", "none");
    svg.appendChild(line);
  }
  line.setAttribute("x1", x);
  line.setAttribute("x2", x);
  line.setAttribute("y1", box.y);
  line.setAttribute("y2", box.y + box.height);
  if (!tag) {
    tag = document.createElementNS(ns, "text");
    tag.setAttribute("class", "price-tag");
    tag.setAttribute("fill", "var(--color-accent)");
    tag.setAttribute("font-size", "11");
    tag.setAttribute("text-anchor", "middle");
    tag.setAttribute("pointer-events", "none");
    svg.appendChild(tag);
  }
  if (tag.textContent !== label) tag.textContent = label;
  tag.setAttribute("x", x);
  tag.setAttribute("y", box.y + 12);
}
function watchPrice(host, rows, spot) {
  host.__strikes = rows;
  if (host.__priceWatch) host.__priceWatch.disconnect();
  const draw = () => {
    watch.disconnect();
    placePrice(host, spot);
    watch.observe(host, { childList: true, subtree: true });
  };
  const watch = new MutationObserver(records => {
    const own = records.every(record => record.target.closest && record.target.closest(".price-line, .price-tag"));
    if (!own) draw();
  });
  host.__priceWatch = watch;
  watch.observe(host, { childList: true, subtree: true });
  draw();
}
function strikeChart(host, rows, mode, spot) {
  if (!host || !rows.length || !window.GBCharts) {
    if (host) host.innerHTML = "<p class='muted'>No open interest in this window.</p>";
    return;
  }
  if (mode === "oi") {
    GBCharts.mount(host, {
      type: "bar",
      data: rows.map(row => ({ label: strikeLabel(row.strike), call: row.call_oi, put: row.put_oi })),
      xKey: "label",
      series: [
        { key: "call", label: "Calls", color: "var(--color-up)" },
        { key: "put", label: "Puts", color: "var(--color-down)" }
      ],
      yFormat: compact,
      domain: [0, "auto"],
      decimals: false,
      height: "15rem"
    });
  } else {
    GBCharts.mount(host, {
      type: "bar",
      data: rows.map(row => ({ label: strikeLabel(row.strike), gamma: row.gamma })),
      xKey: "label",
      series: [{ key: "gamma", label: "Gamma", color: "var(--color-up)", signed: true }],
      yFormat: signedCompact,
      height: "15rem"
    });
  }
  watchPrice(host, rows, spot);
}
function monthDay(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!match) return iso || "";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${Number(match[3])} ${months[Number(match[2]) - 1]}`;
}
function paintQuotes() {
  document.getElementById("quotes").innerHTML = (data.names || []).map(item => {
    if (!item.book && item.error) {
      return `<article class="quote"><p class="quote-symbol">${esc(item.symbol)}</p><p class="muted">No chain.</p></article>`;
    }
    const pressed = item.symbol === current ? "true" : "false";
    return `<button type="button" class="quote" data-symbol="${esc(item.symbol)}" aria-pressed="${pressed}"><p class="quote-symbol">${esc(item.symbol)}</p><p class="quote-last">${money(item.spot)} <span class="${tone(item.change_pct)}">${pct(item.change_pct)}</span></p><p class="muted">30-day IV ${ivPct(item.front_iv)}</p></button>`;
  }).join("");
}
function paintSymbols() {
  document.getElementById("symbols").innerHTML = names.map(item => `<button type="button" class="symbol" data-symbol="${esc(item.symbol)}" aria-pressed="${item.symbol === current ? "true" : "false"}">${esc(item.symbol)}</button>`).join("");
}
function paintCharts() {
  const classes = { SPY: "chart-spy", QQQ: "chart-qqq", IWM: "chart-iwm" };
  const series = names.map(item => ({
    klass: classes[item.symbol] || "chart-spy",
    label: item.symbol,
    points: (item.term || []).map(point => ({ x: point.days, y: point.iv * 100, label: monthDay(point.expiry) }))
  })).filter(item => item.points.length);
  lineChart(document.getElementById("iv-chart"), series, value => value.toFixed(0) + "%");
  const vol = data.vol || {};
  const indexSeries = [
    { klass: "chart-vix", label: "VIX", points: (vol.vix || []).map((point, index) => ({ x: index, y: point.close, label: monthDay(point.date) })) },
    { klass: "chart-vxn", label: "Nasdaq volatility", points: (vol.vxn || []).map((point, index) => ({ x: index, y: point.close, label: monthDay(point.date) })) }
  ].filter(item => item.points.length);
  lineChart(document.getElementById("index-chart"), indexSeries, value => value.toFixed(0));
  const item = names.find(entry => entry.symbol === current) || {};
  const book = item.book;
  const rows = book ? book.strikes : [];
  strikeChart(document.getElementById("oi-chart"), rows, "oi", item.spot);
  strikeChart(document.getElementById("gamma-chart"), rows, "gamma", item.spot);
  const walls = document.getElementById("walls");
  if (!book) {
    walls.textContent = "";
    return;
  }
  const bits = [`The book is ${monthDay(book.expiry)}.`];
  if (book.call_wall != null && book.put_wall != null && book.call_wall === book.put_wall) {
    bits.push(`The wall is ${strikeLabel(book.call_wall)}.`);
  } else {
    if (book.call_wall != null) bits.push(`The call wall is ${strikeLabel(book.call_wall)}.`);
    if (book.put_wall != null) bits.push(`The put wall is ${strikeLabel(book.put_wall)}.`);
  }
  if (book.flip != null) bits.push(`Gamma flips near ${strikeLabel(book.flip)}.`);
  walls.textContent = bits.join(" ");
}
function paint() {
  document.getElementById("lede").textContent = `The date is ${data.as_of}. Quotes are delayed. The 30-day IV is the exchange number. The curve is the at-the-money average.`;
  paintQuotes();
  paintSymbols();
  paintCharts();
  document.getElementById("method").textContent = "Open interest and gamma are delayed CBOE quotes. Calls are counted positive and puts negative, for a 1% move. VIX is the S&P volatility index. The other line is Nasdaq volatility.";
}
document.addEventListener("click", event => {
  const toggle = event.target.closest(".desk-tab[aria-haspopup]");
  if (toggle) {
    const panel = document.getElementById(toggle.getAttribute("aria-controls"));
    const open = toggle.getAttribute("aria-expanded") === "true";
    document.querySelectorAll(".desk-menu__panel").forEach(item => { item.hidden = true; });
    document.querySelectorAll(".desk-tab[aria-haspopup]").forEach(item => item.setAttribute("aria-expanded", "false"));
    if (!open && panel) {
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    }
    return;
  }
  if (!event.target.closest(".desk-menu")) {
    document.querySelectorAll(".desk-menu__panel").forEach(item => { item.hidden = true; });
    document.querySelectorAll(".desk-tab[aria-haspopup]").forEach(item => item.setAttribute("aria-expanded", "false"));
  }
  const pick = event.target.closest("[data-symbol]");
  if (!pick || !names.some(item => item.symbol === pick.dataset.symbol)) return;
  current = pick.dataset.symbol;
  paint();
});
paint();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
