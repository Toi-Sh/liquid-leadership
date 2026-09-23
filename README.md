# Non-Extended Leaders (NEL)

This daily scanner recreates the mechanical portion of your workflow and writes plain CSV files. NEL membership is unchanged from the original rules. A second **Focus Candidates** layer then flags names that also pass Jeff @jfsrev’s pre-trade structure filters and the planned EMA/tightness overlay (10/21 EMA stack, distance from EMA21, ADR-range compression, Bollinger bandwidth). Chart review is still required; Focus is a shortlist, not a trade.

It keeps US common stocks listed on NASDAQ, NYSE, and AMEX that meet all of these filters:

- 30-day average dollar volume above $30M
- 14-period ADR% above 4%
- 10-day average volume above 350K shares
- Industry does not contain “Biotech”

It takes the top 5% of stocks by TradingView performance over each of 1 month, 3 months, and 6 months. It combines those three groups, removes duplicate tickers, and removes names more than 4 ATR% multiples above the 50-day SMA. The result is NEL, not a discretionary focus list.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Daily run

```bash
python focus_list.py
```

## Automatic daily run (macOS)

The installed scheduler checks once per minute and runs the scanner once after 4:10 PM New York time on regular US market days. It uses New York time for market-close and holiday checks, and stamps output files with the **next NYSE session date** (Friday post-close → Monday). If the Mac wakes later that evening, it catches up automatically. It handles daylight-saving changes and writes each run to `logs/daily_scan_YYYY-MM-DD.log`.

The CSV files appear in `outputs/`:

- `Non-Extended Leaders`: leaders below the 4× ATR% extension threshold
- `NEL Symbols`: a one-column ticker list for NEL
- `Focus Candidates`: NEL names that also pass the Jeff hard-rule overlays
- `Focus Symbols`: a one-column ticker list for Focus
- `Momentum Leaders`: names qualifying on momentum before the extension filter
- `Filtered Universe`: every name passing the liquidity, ADR%, and industry filters
- `Settings`: the exact run rules, including Focus thresholds

To use the top 2% in each performance ranking:

```bash
python focus_list.py --top-pct 0.02
```

## Metric definitions

The TradingView screener returns `ADRP` (ADR%) and `ATRP` (ATR%) as distinct percentage fields. ADR% is only the activity filter. ATR% is retained as a percentage and applies your extension formula exactly: `ATR Extension from 50d = (Price − SMA50) / (SMA50 × ATR%)`.

Focus Candidates are a subset of NEL. A name stays in Focus only if it still passes the Jeff overlays (non-extended from the 50-day, above the 10/20/50 and 200-day MAs, not inside 3 days of earnings, day’s range ≤ 1 ATR, LoD ≤ 60% of ATR) **and** the planned tightness layer: `close ≥ EMA10 ≥ EMA21` plus at least one of near-EMA21 (≤ 1.5 ATR), ADR-compressed day range (≤ 75% of ADR%), or Bollinger bandwidth ≤ 10%. RVOL ≥ 1.2 is shown as an expansion flag and RVOL ≥ 1.5 is a Jeff pass/fail column (mega-caps ≥ $10B exempt); neither is required to enter Focus. Tickers link to daily TradingView charts.

Session rules (30-minute open delay, ≤ 3 new names, no chase, consecutive-up-day caution, add to winners, gap-up caution, express shorts via inverse ETFs) are shown on the dashboard as reminders. They cannot be scored from a post-close scan.

Consecutive tight closes are not in this pass; that needs daily history, which TradingView’s screener snapshot does not provide.

## Industry leadership dashboard

Every run also refreshes `industry_flow_dashboard.html`. Open it in a browser to compare industry leadership across the saved daily snapshots. It shows the 1-month, 3-month, and 6-month views together, plus Focus Candidates, Jeff’s 14 hard rules, and per-symbol notes stored in the browser. Theme cards always derive from the full momentum-leader file, not NEL or Focus, so extended names do not distort the strongest-industry signal. Keep prior daily CSV files in `outputs/`; the dashboard reads all of them when it is regenerated.

**Rising themes:** each snapshot is compared to the prior day. If an industry’s 1-month LL count expands (or the Semis complex cluster expands), the desk shows a **Do not miss** alert on F2 Themes, dashes those names in the lists, and writes:

- `outputs/rising_themes_YYYY-MM-DD.csv`
- `outputs/EXPORT/rising_theme_symbols_YYYY-MM-DD.csv`

`KICKOFF` = new/thin theme reaching real breadth; `RISING` = already-present theme adding names.

## Theme tape

`theme_tracker.html` is a separate page (nav: **Tape**) for investable themes that cut across TradingView industries: GPUs, CPUs, Memory, MLCC, Semi Testing, Robotics, Agentic AI, Edge AI, Routers, GLP-1, and the rest of the baskets in `themes_catalog.py`.

Each row is the equal-weight average of the listed common stocks and major ADRs that printed on NYSE, NASDAQ, or AMEX. A period stays blank until at least three names print. Proxy ETFs are labels only. Click a theme for the members. The daily scan refreshes it with the desk; standalone:

```bash
python theme_tracker.py
```

Outputs:

- `theme_tracker.html`
- `outputs/theme_tracker_YYYY-MM-DD.csv`
- `outputs/theme_members_YYYY-MM-DD.csv`

## RS leads (1ChartMaster)

After the universe is built, the desk also scans StockCharts-style relative strength vs SPY:

- `RS = close / SPY close`
- **RS new high** = RS at a 252-day (daily) or 52-week (weekly) high
- **RS lead** = RS new high while price is still at least `0.5%` below its own lookback high

That is the “clue before the gap”: RS prints first, price highs often follow. Outputs:

- `outputs/rs_new_highs_YYYY-MM-DD.csv` — every RS new high (D/W)
- `outputs/rs_leads_YYYY-MM-DD.csv` — only the lead setups
- `outputs/EXPORT/rs_lead_symbols_YYYY-MM-DD.csv`

Standalone:

```bash
python rs_lead_scan.py
```

NEL membership rules are unchanged; RS is an extra watchlist layer. Dashboard panel: **F6 RS**.

## 8-week EMA pullbacks (Liquid Leaders)

From the Liquid Leaders list only, scan for names tagging a **rising 8-week EMA**:

- Weekly `EMA(8)` sloping up
- Daily close within `3%` above / `1.5%` undercut
- At least `1%` off the recent 8-week high (actual pullback, not a fresh high)

Outputs:

- `outputs/ema8_pullbacks_YYYY-MM-DD.csv`
- `outputs/EXPORT/ema8_pullback_symbols_YYYY-MM-DD.csv`

```bash
python ema8_pullback_scan.py
```

Runs automatically with the daily `focus_list.py` job. Dashboard panel: **F7 8W**.

## MA stack (5>10 · 20×30)

From Liquid Leaders only: **SMA5 already above SMA10**, and **SMA20 just crossed / is crossing above SMA30** (actual cross within 3 sessions, or gap ≤ 0.75%).

Outputs:

- `outputs/ma_stack_YYYY-MM-DD.csv`
- `outputs/EXPORT/ma_stack_symbols_YYYY-MM-DD.csv`

```bash
python ma_stack_scan.py
```

Runs automatically with the daily `focus_list.py` job. Dashboard panel: **F8 MA**.

## A++ Flag Breakouts (20MA / 50MA)

Distilled from NVDA / MU / SNDK / INTC / TSLA — **find the coil before the break**, not late continuation (ASST after Aug 19 is rejected).

1. **Thrust (flagpole)** — ≥18% advance into the base
2. **Flag coil** — ≥20 sessions after the thrust peak, depth ≤35%, range contracts
3. **MA stack** — rising/flat 50MA holds; 20/50 pinch; close not >10% above 20MA
4. **Pivot stalk** — primary signal `APLUS_COIL` = within 6% under flag/peak high, volume dry vs thrust
5. **Day-0 break only** — `APLUS_BREAKOUT` = first close through pivot today (RVOL + anti-chase)
6. **MACD** — soft confirm

Rejects late runners (e.g. ASST weeks after the Aug-19 base break).

Outputs:

- `outputs/a_plus_flags_YYYY-MM-DD.csv`
- `outputs/EXPORT/a_plus_flag_coil_symbols_YYYY-MM-DD.csv` (stalk list)
- `outputs/EXPORT/a_plus_flag_breakout_symbols_YYYY-MM-DD.csv` (day-0 only)
- `outputs/EXPORT/a_plus_flag_symbols_YYYY-MM-DD.csv`

```bash
python a_plus_flag_scan.py
```

Runs automatically with the daily `focus_list.py` job. Dashboard panel: **F9 A++** (coils first).

## GitHub Pages and cloud automation

`index.html` is refreshed with the dashboard for GitHub Pages. The GitHub Actions workflow in `.github/workflows/daily-scan.yml` schedules the scanner after the US close, commits the refreshed CSVs and dashboard, and works without your Mac being awake. GitHub Pages must be enabled for the repository with the `main` branch and `/ (root)` folder selected as its source.
