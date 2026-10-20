#!/usr/bin/env python3
"""Write crowding.html from the CFTC Traders in Financial Futures report."""

from __future__ import annotations

import html
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

WINDOW = 156
EXTREME_LOW = 10
EXTREME_HIGH = 90
SOURCE = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
OUT = Path(__file__).with_name("crowding.html")

MARKETS = (
    ("13874A", "S&P 500", "SPY"),
    ("209742", "Nasdaq 100", "QQQ"),
    ("239742", "Russell 2000", "IWM"),
    ("124603", "Dow", "DIA"),
)

GROUPS = (
    ("Dealers", "dealer_positions_long_all", "dealer_positions_short_all", "dealer_positions_spread_all", "change_in_dealer_long_all", "change_in_dealer_short_all", "traders_dealer_long_all", "traders_dealer_short_all"),
    ("Asset managers", "asset_mgr_positions_long", "asset_mgr_positions_short", "asset_mgr_positions_spread", "change_in_asset_mgr_long", "change_in_asset_mgr_short", "traders_asset_mgr_long_all", "traders_asset_mgr_short_all"),
    ("Leveraged funds", "lev_money_positions_long", "lev_money_positions_short", "lev_money_positions_spread", "change_in_lev_money_long", "change_in_lev_money_short", "traders_lev_money_long_all", "traders_lev_money_short_all"),
    ("Other reportable", "other_rept_positions_long", "other_rept_positions_short", "other_rept_positions_spread", "change_in_other_rept_long", "change_in_other_rept_short", "traders_other_rept_long_all", "traders_other_rept_short"),
    ("Small traders", "nonrept_positions_long_all", "nonrept_positions_short_all", None, "change_in_nonrept_long_all", "change_in_nonrept_short_all", None, None),
)

# key, name, line color, short axis label. Same order as GROUPS.
GROUP_SERIES = (
    ("dealers", "Dealers", "var(--color-series-2)", "Dealers"),
    ("asset", "Asset managers", "var(--color-series-1)", "Managers"),
    ("lev", "Leveraged funds", "var(--color-series-3)", "Leveraged"),
    ("other", "Other reportable", "var(--color-series-4)", "Other"),
    ("small", "Small traders", "var(--color-series-5)", "Small"),
)
MARKET_COLOR = {
    "SPY": "var(--color-series-1)",
    "QQQ": "var(--color-series-3)",
    "IWM": "var(--color-series-4)",
    "DIA": "var(--color-series-2)",
}


def num(row: dict, key: str) -> int:
    return int(row[key])


def optional_num(row: dict, key: str | None) -> int | None:
    if not key or row.get(key) in (None, ""):
        return None
    return int(row[key])


def range_place(latest: int, history: list[int]) -> int:
    """0 is the most net short in the window. 100 is the most net long."""
    window = history[:WINDOW]
    if not window:
        raise ValueError("empty history")
    lo, hi = min(window), max(window)
    if hi == lo:
        return 50
    return round((latest - lo) / (hi - lo) * 100)


def place_words(name: str, place: int) -> str | None:
    if place >= EXTREME_HIGH:
        return f"{name} near the long extreme"
    if place <= EXTREME_LOW:
        return f"{name} near the short extreme"
    return None


def badge(places: list[tuple[str, int]]) -> tuple[str, str]:
    hits = [words for name, place in places if (words := place_words(name, place))]
    if not hits:
        return "No group is at an extreme", "quiet"
    return ". ".join(hits) + ".", "warn"


def signed(n: int) -> tuple[str, str]:
    if n > 0:
        return "up", f"+{n:,}"
    if n < 0:
        return "down", "−" + f"{abs(n):,}"
    return "flat", "0"


def signed_span(n: int) -> str:
    kind, text = signed(n)
    return f'<span class="n-{kind}">{text}</span>'


def long_date(iso: str) -> str:
    day = date.fromisoformat(iso[:10])
    return f"{day.day} {day.strftime('%B %Y')}"


def tick_label(iso: str) -> str:
    day = date.fromisoformat(iso[:10])
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{day.day} {months[day.month - 1]} {day.year % 100:02d}"


def history_points(rows: list[dict]) -> list[dict]:
    """Oldest first. Each value is net contracts as a percent of that week's open interest."""
    points = []
    for row in reversed(rows):
        oi = num(row, "open_interest_all") if row.get("open_interest_all") not in (None, "") else 0
        point = {"d": row["report_date_as_yyyy_mm_dd"][:10]}
        for (key, _label, _color, _short), spec in zip(GROUP_SERIES, GROUPS):
            if not oi or spec[1] not in row or spec[2] not in row:
                point[key] = None
            else:
                point[key] = round((num(row, spec[1]) - num(row, spec[2])) / oi * 100, 1)
        points.append(point)
    return points


def compare_rows(markets: list[dict]) -> list[dict]:
    rows = []
    for key, label, _color, short in GROUP_SERIES:
        row = {"label": short}
        for market in markets:
            group = next(item for item in market["groups"] if item["name"] == label)
            row[market["key"]] = round(group["net"] / market["oi"] * 100, 1)
        rows.append(row)
    return rows


def fetch(code: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "$where": f"cftc_contract_market_code='{code}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(WINDOW),
        }
    )
    with urllib.request.urlopen(SOURCE + "?" + query, timeout=60) as response:
        rows = json.load(response)
    if not rows:
        raise RuntimeError(f"no CFTC rows for {code}")
    return rows


def build_group(row: dict, history: list[dict], spec: tuple) -> dict:
    name, long_key, short_key, spread_key, chg_long, chg_short, traders_long, traders_short = spec
    nets = [num(item, long_key) - num(item, short_key) for item in history]
    net = nets[0]
    place = range_place(net, nets)
    window = nets[:WINDOW]
    return {
        "name": name,
        "net": net,
        "week": num(row, chg_long) - num(row, chg_short),
        "place": place,
        "lo": min(window),
        "hi": max(window),
        "long": num(row, long_key),
        "short": num(row, short_key),
        "spread": optional_num(row, spread_key),
        "traders_long": optional_num(row, traders_long),
        "traders_short": optional_num(row, traders_short),
        "reports": len(window),
    }


def build_market(code: str, name: str, etf: str, rows: list[dict]) -> dict:
    latest = rows[0]
    groups = [build_group(latest, rows, spec) for spec in GROUPS]
    text, kind = badge([(group["name"], group["place"]) for group in groups])
    return {
        "code": code,
        "name": name,
        "etf": etf,
        "as_of": latest["report_date_as_yyyy_mm_dd"],
        "oi": num(latest, "open_interest_all"),
        "oi_week": num(latest, "change_in_open_interest_all"),
        "badge": text,
        "badge_kind": kind,
        "key": etf.lower(),
        "color": MARKET_COLOR[etf],
        "groups": groups,
        "history": history_points(rows),
        "reports": min(group["reports"] for group in groups),
    }


def pct_span(net: int, oi: int) -> str:
    pct = net / oi * 100
    kind, _ = signed(net)
    text = "0.0" if kind == "flat" else f"{pct:+.1f}".replace("-", "−")
    return f'<span class="n-{kind}">{text}%</span>'


PAGE_SCRIPT = """
function pctFormat(value) {
  const rounded = Math.round(Number(value) * 10) / 10;
  const body = Math.abs(rounded).toFixed(1).replace(/\\.0$/, "");
  if (rounded > 0) return "+" + body + "%";
  if (rounded < 0) return "\\u2212" + body + "%";
  return "0%";
}
function draw() {
  if (!window.GBCharts) return;
  GBCharts.mount(document.getElementById("compare"), {
    type: "bar",
    data: book.compare,
    xKey: "label",
    series: book.markets.map(function (market) {
      return { key: market.key, label: market.name, color: market.color };
    }),
    yFormat: pctFormat,
    guides: [0],
    height: "18rem"
  });
  book.markets.forEach(function (market) {
    GBCharts.mount(document.getElementById("plot-" + market.key), {
      type: "line",
      data: market.history,
      xKey: "label",
      series: book.groups,
      yFormat: pctFormat,
      guides: [0],
      height: "16rem"
    });
  });
}
draw();
"""


def legend_html(items: list[tuple[str, str]]) -> str:
    rows = "".join(
        f'<li><span class="swatch" style="background:{color}"></span>{html.escape(label)}</li>'
        for label, color in items
    )
    return f'<ul class="legend">{rows}</ul>'


def group_row(group: dict, oi: int) -> str:
    extreme = group["place"] <= EXTREME_LOW or group["place"] >= EXTREME_HIGH
    place_class = " place-warn" if extreme else ""
    return (
        f"<tr><th scope=\"row\">{html.escape(group['name'])}</th>"
        f"<td>{signed_span(group['net'])}</td><td>{signed_span(group['week'])}</td>"
        f"<td>{pct_span(group['net'], oi)}</td><td class=\"{place_class.strip()}\">{group['place']}</td></tr>"
    )


def market_html(market: dict) -> str:
    slug = market["key"]
    rows = "\n".join(group_row(group, market["oi"]) for group in market["groups"])
    return f"""<section class="panel" aria-labelledby="m-{slug}">
      <div class="head">
        <div>
          <p class="kicker">{html.escape(market["etf"])}</p>
          <h2 id="m-{slug}">{html.escape(market["name"])}</h2>
        </div>
        <p class="badge badge-{market["badge_kind"]}">{html.escape(market["badge"])}</p>
      </div>
      <p class="meta">Open interest {market["oi"]:,} · week {signed_span(market["oi_week"])}</p>
      <div id="plot-{slug}" class="plot" aria-label="{html.escape(market["name"])} net share of open interest"></div>
      <div class="reads">
        <table>
          <caption class="visually-hidden">{html.escape(market["name"])} this report</caption>
          <thead><tr><th>Group</th><th>Net</th><th>Week</th><th>Share</th><th>Range</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>"""


def chart_book(markets: list[dict]) -> dict:
    return {
        "compare": compare_rows(markets),
        "groups": [{"key": key, "label": label, "color": color} for key, label, color, _short in GROUP_SERIES],
        "markets": [
            {
                "key": market["key"],
                "name": market["name"],
                "color": market["color"],
                "history": [
                    {"label": tick_label(point["d"]), **{key: point[key] for key, _label, _color, _short in GROUP_SERIES}}
                    for point in market["history"]
                ],
            }
            for market in markets
        ],
    }


def render(markets: list[dict]) -> str:
    as_of = long_date(markets[0]["as_of"])
    reports = min(market["reports"] for market in markets)
    lede = (
        f"CFTC Traders in Financial Futures, futures only. Positions as of {as_of}. "
        "The bars compare this report. The lines are each group’s net as a share of that week’s open interest. "
        f"Range runs from 0, the most net short in {reports} reports, to 100, the most net long. "
        f"An extreme is {EXTREME_LOW} or below, or {EXTREME_HIGH} or above. Price still has to confirm."
    )
    cards = "\n".join(market_html(market) for market in markets)
    market_legend = legend_html([(market["name"], market["color"]) for market in markets])
    group_legend = '<p class="kicker">On the lines</p>\n  ' + legend_html([(label, color) for _key, label, color, _short in GROUP_SERIES])
    script = (
        '<script src="shadcn-charts.js?v=20261015g"></script>\n<script>\nconst book = '
        + json.dumps(chart_book(markets), separators=(",", ":"))
        + ";\n"
        + PAGE_SCRIPT
        + "\n</script>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Crowding | GB Market Terminal</title>
  <meta name="robots" content="index, follow">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="preload" href="assets/fonts/newsreader-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/source-sans-3-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css?v=20261015j">
  <style>
    html {{ color-scheme: dark; background: var(--color-paper); }}
    html, body {{ overflow-x: clip; margin: 0; }}
    body {{
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
    }}
    body::before {{
      content: "";
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      opacity: 0.28;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }}
    .lede, main, .foot {{ position: relative; z-index: 1; }}
    h1, h2, h3, a {{ font-style: normal; }}
    .visually-hidden {{
      position: absolute; width: 1px; height: 1px; overflow: hidden;
      clip-path: inset(50%); white-space: nowrap;
    }}
    .skip-link {{
      position: absolute; left: var(--space-sm); top: var(--space-sm);
      z-index: var(--z-sticky-nav); padding: var(--space-xs) var(--space-sm);
      background: var(--color-accent); color: var(--color-accent-ink);
      text-decoration: none; transform: translateY(-200%);
    }}
    .skip-link:focus-visible {{ transform: none; outline: 2px solid var(--color-focus); }}
    .lede, .foot {{
      margin: 0; color: var(--color-muted); font-size: var(--text-xs);
    }}
    .lede {{
      display: flex; align-items: flex-start; gap: var(--space-sm);
      margin: var(--space-8) var(--page-gutter) 0;
      margin-left: max(var(--page-gutter), env(safe-area-inset-left));
      margin-right: max(var(--page-gutter), env(safe-area-inset-right));
      padding: var(--space-8) var(--space-md);
      background: color-mix(in oklch, var(--color-up) 12%, var(--color-paper-3));
      border: var(--rule) solid color-mix(in oklch, var(--color-up) 42%, var(--color-rule));
      border-radius: 12px;
      color: var(--color-ink-2); line-height: 1.45;
    }}
    .lede-mark {{
      flex: none; display: inline-flex; align-items: center; justify-content: center;
      width: 1rem; height: 1rem; margin-top: 0.15rem;
      border: var(--rule) solid var(--color-up); border-radius: 50%;
      color: var(--color-up); font-size: 11px; line-height: 1;
    }}
    .foot {{
      padding: var(--space-sm) var(--page-gutter) var(--space-xl);
      padding-left: max(var(--page-gutter), env(safe-area-inset-left));
      padding-right: max(var(--page-gutter), env(safe-area-inset-right));
      max-width: 72rem; line-height: 1.45;
    }}
    main {{
      display: flex; flex-direction: column; gap: var(--space-sm);
      padding: var(--space-sm) var(--page-gutter) var(--space-lg);
      padding-left: max(var(--page-gutter), env(safe-area-inset-left));
      padding-right: max(var(--page-gutter), env(safe-area-inset-right));
    }}
    .page-title {{
      margin: 0; font-family: var(--font-display); font-size: var(--text-display);
      font-weight: 400; letter-spacing: -0.03em; line-height: 1; color: var(--color-ink);
    }}
    .cards {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-sm); }}
    .panel {{
      min-width: 0;
      background: color-mix(in oklch, var(--color-paper-3) 46%, transparent);
      border: var(--rule) solid color-mix(in oklch, white 28%, transparent);
      border-radius: 12px;
      box-shadow: inset 0 1px 0 color-mix(in oklch, white 32%, transparent);
      backdrop-filter: blur(14px) saturate(1.35);
      -webkit-backdrop-filter: blur(14px) saturate(1.35);
      padding: var(--space-sm) var(--space-md) var(--space-md);
    }}
    .head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-sm); }}
    .kicker {{
      margin: 0 0 var(--space-4); font-size: var(--text-xs); letter-spacing: 0.04em;
      text-transform: uppercase; color: var(--color-muted);
    }}
    h2 {{
      margin: 0; font-family: var(--font-display); font-size: var(--text-lg);
      font-weight: 400; letter-spacing: -0.02em; line-height: 1.1; color: var(--color-ink);
    }}
    .badge {{
      margin: 0; max-width: 16rem; padding: var(--space-4) var(--space-8);
      border: var(--rule) solid var(--color-rule); border-radius: 999px;
      font-size: var(--text-xs); line-height: 1.35; text-align: center;
    }}
    .badge-warn {{ color: var(--color-warn); border-color: color-mix(in oklch, var(--color-warn) 55%, var(--color-rule)); }}
    .badge-quiet {{ color: var(--color-muted); }}
    .meta {{ margin: var(--space-8) 0 0; font-size: var(--text-xs); color: var(--color-ink-2); }}
    .legend {{
      display: flex; flex-wrap: wrap; gap: var(--space-8) var(--space-md);
      margin: var(--space-8) 0 0; padding: 0; list-style: none;
    }}
    .legend li {{ display: flex; align-items: center; gap: var(--space-4); font-size: var(--text-xs); color: var(--color-ink-2); }}
    .swatch {{ width: 0.7rem; height: 0.7rem; border-radius: 2px; flex: none; }}
    .plot {{ margin-top: var(--space-sm); min-width: 0; }}
    .reads {{ overflow-x: auto; margin-top: var(--space-sm); }}
    table {{ width: 100%; border-collapse: collapse; font-size: var(--text-xs); }}
    th, td {{
      padding: var(--space-4) var(--space-8); text-align: right; white-space: nowrap;
      border-bottom: var(--rule) solid var(--color-rule); font-weight: 400;
    }}
    th:first-child, td:first-child, th:first-child {{ text-align: left; color: var(--color-ink); }}
    thead th {{ color: var(--color-muted); }}
    .place-warn {{ color: var(--color-warn); }}
    .n-up {{ color: var(--color-up); }}
    .n-down {{ color: var(--color-down); }}
    .n-flat {{ color: var(--color-muted); }}
    @media (max-width: 64rem) {{
      .cards {{ grid-template-columns: minmax(0, 1fr); }}
    }}
    @media (prefers-reduced-transparency: reduce) {{
      body {{ background: var(--color-paper); }}
      body::before {{ display: none; }}
      .panel {{
        background: var(--color-paper-3); border-color: var(--color-rule);
        box-shadow: none; backdrop-filter: none;
      }}
    }}
  </style>
  <link rel="stylesheet" href="nav.css?v=20261015n">
  <link rel="stylesheet" href="shadcn-chart.css?v=20261015g">
</head>
<body>
<a class="skip-link" href="#crowding">Skip to crowding</a>
<header class="nav-edge">
  <div class="brand"><h1 class="product">GB Market Terminal</h1></div>
  <nav class="bbg-keys" aria-label="Terminal panels">
    <a class="desk-tab" href="regime.html">Regime</a>
    <a class="desk-tab" href="monitor.html">Monitor</a>
    <a class="desk-tab" href="themes.html">Themes</a>
    <a class="desk-tab" href="liquid.html">Leaders</a>
    <a class="desk-tab" href="rs.html">Setups</a>
    <a class="desk-tab" href="tape.html">Tape</a>
    <a class="desk-tab" href="crowding.html" aria-current="page">Crowding</a>
    <a class="desk-tab" href="terminal.html">Terminal</a>
  </nav>
</header>
<p class="lede" role="note"><span class="lede-mark" aria-hidden="true">i</span><span class="visually-hidden">Information. </span>{html.escape(lede)}</p>
<main id="crowding">
  <h2 class="page-title">Crowding</h2>
  <section class="panel" aria-labelledby="compare-title">
    <p id="compare-title" class="kicker">This report</p>
    <p class="meta">Net contracts as a share of open interest. Above the line is net long.</p>
    {market_legend}
    <div id="compare" class="plot" aria-label="Net share of open interest by group and index"></div>
  </section>
  {group_legend}
  <div class="cards">
{cards}
  </div>
</main>
<p class="foot">Net is long contracts minus short contracts. Share is that net divided by open interest. The dashed line is zero. Range is the group’s place in its own last {reports} reports. Not an instruction to trade.</p>
{script}
</body>
</html>
"""


def main() -> None:
    markets = [build_market(code, name, etf, fetch(code)) for code, name, etf in MARKETS]
    dates = {market["as_of"][:10] for market in markets}
    if len(dates) != 1:
        raise RuntimeError(f"report dates differ: {sorted(dates)}")
    OUT.write_text(render(markets), encoding="utf-8")
    for market in markets:
        lev = next(group for group in market["groups"] if group["name"] == "Leveraged funds")
        print(f"{market['name']} {market['as_of'][:10]} oi={market['oi']} lev={lev['place']} {market['badge']}")


if __name__ == "__main__":
    main()
