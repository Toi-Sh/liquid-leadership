# GB Market Terminal

GB Market Terminal is a daily US equity desk. After the close it builds the lists, theme tape, and regime page, then writes them as static HTML you can open in a browser. The lists are a review desk. They are not an instruction to trade.

The short version is this file. Panel rules, thresholds, and output files are on the [wiki](https://github.com/Toi-Sh/liquid-leadership/wiki).

The bar has seven panels:

| Panel | Page | What it shows |
| --- | --- | --- |
| Regime | `regime.html` | Market cycle, T2108, Nasdaq 40, the day’s breadth, the index tape, and index health |
| Monitor | `monitor.html` | SPY, QQQ, and IWM implied volatility, open interest, and gamma walls |
| Themes | `themes.html` | Industry leadership, rising groups, and one leader from each top theme |
| Leaders | `liquid.html` | Liquid Leaders, Focus, and Non-extended Leaders |
| Setups | `rs.html` | Relative strength, 8-week pullbacks, moving-average stack, and flag breakouts |
| Tape | `tape.html` | Equal-weight theme baskets (GPUs, nuclear, banks, and the rest of the catalog) |
| Crowding | `crowding.html` | CFTC futures positioning in the S&P 500, Nasdaq 100, Russell 2000, and Dow |

`index.html` is the Themes, Leaders, and Setups desk. `themes.html`, `liquid.html`, `focus.html`, `nel.html`, `rs.html`, `ema8.html`, `ma.html`, and `aplus.html` open that same desk on the matching list. `tape.html` opens the theme tape.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Daily procedure

One command builds the leader lists, the setup scans, the theme scan, the dashboard, the theme tape, and the regime page:

```bash
python focus_list.py
```

To keep the top 2% of each performance rank instead of the default 5%:

```bash
python focus_list.py --top-pct 0.02
```

Monitor and Crowding are separate pages. Run them on their own:

```bash
python options_monitor.py
python crowding.py
```

You can also rebuild one piece:

```bash
python theme_scan.py
python theme_tracker.py
python regime.py
python rs_lead_scan.py
python ema8_pullback_scan.py
python ma_stack_scan.py
python a_plus_flag_scan.py
```

### Automatic daily procedure (macOS)

`scripts/run_after_close.py` checks once a minute and runs the scanner once after 4:10 PM New York time, only on a regular US market day. It uses New York time for the close and for holidays.

Output files use the date of the next NYSE session. A Friday run after the close uses Monday. If the computer starts later that night, the scheduler does the missed run. Each run writes `logs/daily_scan_YYYY-MM-DD.log`.

## Leaders

The scanner keeps NASDAQ, NYSE, and AMEX common stocks that pass all of these tests:

- 30-day average dollar volume above $30 million
- 14-period ADR% above 4%
- 10-day average volume above 350,000 shares
- Industry name does not include Biotech

That set is the filtered universe. The scanner ranks it by TradingView performance over 1 month, 3 months, and 6 months, keeps the top 5% of each rank, and merges the three lists. The merged list is Liquid Leaders.

Non-extended Leaders (NEL) is Liquid Leaders with the extension filter applied. A name drops when price is more than 4 ATR% above the 50-day SMA:

`ATR extension from the 50-day SMA = (Price − SMA50) / (SMA50 × ATR%)`

`ADRP` is the ADR% activity filter. `ATRP` is the ATR% used in that formula.

Focus is the part of NEL that also passes the structure filters. A name stays in Focus only when all of these are true:

- It is not extended from the 50-day SMA.
- Price is above the 10-day, 20-day, 50-day, and 200-day moving averages.
- Earnings are not in the next 3 days.
- The day’s range is not more than 1 ATR.
- The low of the day is not more than 60% of the ATR.
- The close is at or above EMA10, and EMA10 is at or above EMA21.
- One tightness test passes: distance from EMA21 is not more than 1.5 ATR, the day’s range is not more than 75% of ADR%, or Bollinger bandwidth is not more than 10%.

An RVOL of 1.2 or more is a flag. An RVOL of 1.5 or more is a pass or fail column, and a stock of $10 billion or more skips that column. RVOL is not required for Focus. Each ticker links to a daily TradingView chart.

The scanner cannot score these session rules after the close: wait 30 minutes after the open, add no more than 3 new names, do not chase, use caution after consecutive up days, add to winners, use caution on a gap-up, and use inverse ETFs for a short. It also does not test consecutive tight closes, because the TradingView screener does not give that history.

Daily files in `outputs/`:

- `non_extended_leaders_YYYY-MM-DD.csv` and `EXPORT/nel_symbols_YYYY-MM-DD.csv`
- `focus_candidates_YYYY-MM-DD.csv` and `EXPORT/focus_symbols_YYYY-MM-DD.csv`
- `momentum_leaders_YYYY-MM-DD.csv` for Liquid Leaders, before the extension filter
- `filtered_universe_YYYY-MM-DD.csv`
- `settings_YYYY-MM-DD.csv` for the rules used that day

## Themes

The Themes panel reads every saved snapshot in `outputs/` and shows industry leadership for 1 month, 3 months, and 6 months. Theme cards use the full Liquid Leaders file. An extended name still counts toward the industry.

When an industry’s 1-month count rises versus the prior day, the panel marks a “Do not miss” alert and draws a dashed line on those names. The same rule applies to the Semis group. `KICKOFF` is a theme that just reached the minimum count. `RISING` is a theme that was already on the list and now has more names.

The panel also keeps a note, a pin list, a Livermore quote, and the session line in the browser. Across the latest two snapshots it reports names that entered or left Liquid Leaders, Focus, relative strength, and the theme scan, plus industries that grew or faded, names that sit on more than one list, earnings in the next seven days, and the strongest and weakest theme-tape baskets.

The theme scan picks one leader from each top theme. Top themes are the five strongest 1-month industries, plus any 1-month industry with a `KICKOFF` or `RISING` signal. A name must pass all of these:

- Price above $1
- Day change from −5% to +5%
- Volume above 1 million shares
- Price above the 10-day average, the 20-day average, and the weekly 10-day average
- The 10-day and 20-day averages are higher than five sessions ago
- Quarterly earnings and revenue are each up 40% or more
- Best 1-month performance in its industry

Files:

- `outputs/rising_themes_YYYY-MM-DD.csv`
- `outputs/EXPORT/rising_theme_symbols_YYYY-MM-DD.csv`
- `outputs/theme_scan_YYYY-MM-DD.csv`
- `outputs/theme_scan_themes_YYYY-MM-DD.csv`
- `outputs/EXPORT/theme_scan_symbols_YYYY-MM-DD.csv`

## Setups

These scans run inside `focus_list.py`. On the desk, open Setups.

**Relative strength.** After the stock group is built, the scanner compares the filtered universe with SPY. RS is the close divided by the SPY close. An RS new high is the highest RS in 252 days, or in 52 weeks. An RS lead is an RS new high while price is still at least 0.5% under its own high for that period.

- `outputs/rs_new_highs_YYYY-MM-DD.csv` for every RS new high, daily and weekly
- `outputs/rs_leads_YYYY-MM-DD.csv`
- `outputs/EXPORT/rs_lead_symbols_YYYY-MM-DD.csv`

**8-week EMA pullbacks.** Liquid Leaders only. The weekly EMA(8) slope is positive, the daily close is within 3% above the EMA and 1.5% below it, and price is at least 1% under the high of the last 8 weeks.

- `outputs/ema8_pullbacks_YYYY-MM-DD.csv`
- `outputs/EXPORT/ema8_pullback_symbols_YYYY-MM-DD.csv`

**Moving averages.** Liquid Leaders only. SMA5 is above SMA10, and SMA20 crossed above SMA30 in the last 3 sessions or the gap between them is not more than 0.75%.

- `outputs/ma_stack_YYYY-MM-DD.csv`
- `outputs/EXPORT/ma_stack_symbols_YYYY-MM-DD.csv`

**Flag breakouts.** Liquid Leaders only. The scan looks for a coil before the break and drops a late continuation. A name needs an 18% or larger advance into the base, then a coil of 20 sessions or more with depth of 35% or less and a smaller range. The 50-day average is flat or rising, the 20-day and 50-day averages are close, and the close is not more than 10% above the 20-day average. `APLUS_COIL` means price is within 6% of the flag high and volume dried up versus the advance. `APLUS_BREAKOUT` means the close went through the pivot that day. MACD is a soft check.

- `outputs/a_plus_flags_YYYY-MM-DD.csv`
- `outputs/EXPORT/a_plus_flag_coil_symbols_YYYY-MM-DD.csv`
- `outputs/EXPORT/a_plus_flag_breakout_symbols_YYYY-MM-DD.csv`
- `outputs/EXPORT/a_plus_flag_symbols_YYYY-MM-DD.csv`

## Tape

The Tape panel is a different page from TradingView industries. Baskets live in `themes_catalog.py` and are grouped into Semis, AI, Health, Power, Materials, and Macro. Each row is the equal-weight average of the listed common stocks and primary ADRs on NYSE, NASDAQ, or AMEX. A period stays blank until at least three names have a price. A proxy ETF is a label only. Select a theme to see its members. A basket link on the Themes desk shows which of those names are already on the lists.

- `theme_tracker.html`
- `outputs/theme_tracker_YYYY-MM-DD.csv`
- `outputs/theme_members_YYYY-MM-DD.csv`

## Regime

Regime reads the cycle, T2108, the day’s breadth, and the index tape. T2108 is the share of liquid NYSE names above the 40-day average. A 4% day is a close up or down 4% or more. The 5-day ratio is five sessions of 4% up days divided by five sessions of 4% down days. The 10-day ratio uses the same idea.

The cycle calls a washout when T2108 closes at 29 or below, and extended when it closes at 70 or above. A bounce from a washout needs a 5-point lift off the low and either a 5-day ratio of 1.5 or a day with 500 names up 4%. The breadth thrust fires when T2108 rises at least 15 points in 2 sessions, give or take 2, from a reading at or under 30, give or take 2, the 5-day ratio is at least 1.5, and that rise beats the 10-day average. Those levels were fit to S&P lows of 15% or more that later made a new high. Nasdaq 40 is the same share for liquid Nasdaq names and uses the same band. A 10-day average still under 40 that is rising toward T2108 is catching up.

The universe is US common stocks with a price above $5 and a 10-day average volume above 300,000. The page also shows SPY, QQQ, DIA, and IWM, VIX, the 10-year yield, and a daily EMA health table for those four indexes.

- `regime.html`
- `outputs/regime_history.csv`
- `outputs/regime_YYYY-MM-DD.csv`

## Monitor

Monitor reads delayed CBOE option chains for SPY, QQQ, and IWM. It charts the implied-volatility term, VIX and Nasdaq volatility, call and put open interest, and gamma by strike, including the call wall, put wall, and gamma flip. Gamma uses CBOE’s gamma, signed so calls are positive and puts are negative, for a 1% move. VIX and Nasdaq volatility history comes from Yahoo.

- `monitor.html`
- `outputs/options_monitor.json`

## Crowding

Crowding reads the CFTC Traders in Financial Futures report, futures only, for the S&P 500, Nasdaq 100, Russell 2000, and Dow. It charts dealers, asset managers, leveraged funds, other reportables, and small traders. Net is contracts as a share of that week’s open interest. Range runs from 0, the most net short in 156 reports, to 100, the most net long. An extreme is 10 or below, or 90 or above.

- `crowding.html`

## GitHub Pages

`index.html` is the same file as `industry_flow_dashboard.html`. GitHub Pages serves the repository root. The workflow `.github/workflows/daily-scan.yml` starts the scanner after the US close and commits the new CSV files, `index.html`, `industry_flow_dashboard.html`, `theme_tracker.html`, and `regime.html`. The Mac can be off. Monitor and Crowding stay local until you run those two scripts and commit the pages yourself.

To publish: open the repository’s GitHub Pages settings, choose the `main` branch, and set the source to the root folder.
