# Non-Extended Leaders (NEL)

This scanner makes a list of US common stocks each day. The list name is Non-Extended Leaders (NEL). The scanner writes the results to CSV files.

NEL uses the original rules. A second list has the name Focus Candidates. This list shows NEL names that also agree with the structure filters. You must examine the charts. Focus Candidates is not an instruction to trade.

The scanner keeps stocks on NASDAQ, NYSE, and AMEX. A stock must agree with all of these conditions:

- The 30-day average dollar volume is more than $30 million.
- The 14-period ADR% is more than 4%.
- The 10-day average volume is more than 350,000 shares.
- The industry name does not include "Biotech".

The scanner ranks the stocks by TradingView performance. It uses three periods: 1 month, 3 months, and 6 months. It keeps the top 5% for each period. It makes one group from the three lists. It removes duplicate tickers. It removes a name if the price is more than 4 ATR% above the 50-day SMA. The result is the NEL list. NEL is not a discretionary list.

## Setup

Do these steps:

1. Make a virtual environment:

```bash
python3 -m venv .venv
```

2. Start the virtual environment:

```bash
source .venv/bin/activate
```

3. Install the necessary packages:

```bash
pip install -r requirements.txt
```

## Daily procedure

1. Run the scanner:

```bash
python focus_list.py
```

To keep the top 2% in each performance rank, run this command:

```bash
python focus_list.py --top-pct 0.02
```

## Automatic daily procedure (macOS)

The scheduler does a check one time each minute. It runs the scanner one time after 4:10 PM New York time. It runs the scanner only on a regular US market day. The scheduler uses New York time. It uses this time for the market close and for holidays.

The output files show the date of the next NYSE session. A Friday procedure after the close uses the Monday date. If the computer starts later that night, the scheduler does the missed procedure. The scheduler adjusts for daylight saving time. Each procedure writes a log file: `logs/daily_scan_YYYY-MM-DD.log`.

The CSV files are in `outputs/`:

- `Non-Extended Leaders`: leaders below the 4× ATR% limit.
- `NEL Symbols`: a list of NEL tickers in one column.
- `Focus Candidates`: NEL names that also agree with the structure filters.
- `Focus Symbols`: a list of Focus tickers in one column.
- `Momentum Leaders`: names that pass the momentum test before the extension filter.
- `Filtered Universe`: names that pass the liquidity test, the ADR% test, and the industry test.
- `Settings`: the rules for that procedure, with the Focus limits.

## Definitions of the metrics

The TradingView screener gives two different values. `ADRP` is the ADR%. `ATRP` is the ATR%. ADR% is only a filter for activity. ATR% stays a percentage. Use this formula for the extension:

`ATR extension from the 50-day SMA = (Price − SMA50) / (SMA50 × ATR%)`

Focus Candidates is a part of NEL. A name stays in Focus Candidates only if all of these conditions are true:

- The name is not extended from the 50-day SMA.
- The price is above the 10-day, 20-day, 50-day, and 200-day moving averages.
- The earnings date is not in the next 3 days.
- The range of the day is not more than 1 ATR.
- The low of the day is not more than 60% of the ATR.

The name must also agree with the tightness conditions:

- The close is above or equal to EMA10.
- EMA10 is above or equal to EMA21.
- One of these conditions is true:
  - The distance from EMA21 is not more than 1.5 ATR.
  - The range of the day is not more than 75% of the ADR%.
  - The Bollinger bandwidth is not more than 10%.

An RVOL of 1.2 or more is a flag. The scanner shows this flag. An RVOL of 1.5 or more is a pass or fail column. A stock with a value of $10 billion or more does not use this column. RVOL is not necessary for Focus Candidates. Each ticker has a link to a daily TradingView chart.

Some session rules are manual. The scanner cannot score them after the market closes. These rules are:

- Wait 30 minutes after the open.
- Do not add more than 3 new names.
- Do not chase a name.
- Use caution after consecutive up days.
- Add to winners.
- Use caution with a gap-up.
- Use inverse ETFs for a short position.

This procedure does not test consecutive tight closes. That test needs the price for each day. The TradingView screener does not give that history.

## Industry leadership dashboard

Each procedure also makes `industry_flow_dashboard.html` new. Open this file in a browser. You can also open `index.html`. The page title is "State of the Markets".

The page shows industry leadership for the saved snapshots. It shows the 1-month view, the 3-month view, and the 6-month view. It also shows Focus Candidates. You can write a note for each symbol. The browser keeps the notes.

Theme cards use the full momentum-leader file. They do not use the NEL list or the Focus Candidates list. An extended name does not change the industry signal.

Keep the older CSV files in `outputs/`. The dashboard reads all of these files when you make the page again.

The scanner compares each snapshot with the previous day. If the 1-month count for an industry increases, the Themes view shows a "Do not miss" alert. The lists show a dash on those names. The same rule applies to the Semis group. The scanner writes these files:

- `outputs/rising_themes_YYYY-MM-DD.csv`
- `outputs/EXPORT/rising_theme_symbols_YYYY-MM-DD.csv`

`KICKOFF` means a new theme that now has enough names. `RISING` means a theme that was already in the list and now has more names.

## Theme scan

The Themes view also shows one leader for each top theme. The scanner uses the top five 1-month industries. It also uses the 1-month themes with a `KICKOFF` or `RISING` signal. A name must agree with all of these conditions:

- The price is above $1.
- The change for the day is from −5% to +5%.
- The volume is more than 1 million shares.
- The price is above the 10-day average, the 20-day average, and the weekly 10-day average.
- The 10-day average and the 20-day average are higher than 5 sessions before.
- Earnings and revenue are each up 40% or more.
- The name has the best 1-month performance in its industry.

The scanner keeps one name for each industry. It writes these files:

- `outputs/theme_scan_YYYY-MM-DD.csv`
- `outputs/theme_scan_themes_YYYY-MM-DD.csv`
- `outputs/EXPORT/theme_scan_symbols_YYYY-MM-DD.csv`

You can run this procedure alone:

```bash
python theme_scan.py
```

## Theme tape

`theme_tracker.html` is a different page. In the navigation, select Tape. This page shows themes that are not the same as TradingView industries. The groups are in `themes_catalog.py`. Examples are GPUs, CPUs, and Memory.

Each row is the equal-weight average of the listed common stocks and the primary ADRs. These names trade on NYSE, NASDAQ, or AMEX. A period stays empty until a minimum of three names have a price. A proxy ETF is a label only. Select a theme to see the members.

The daily procedure also makes this page new. You can run the procedure alone:

```bash
python theme_tracker.py
```

The procedure writes these files:

- `theme_tracker.html`
- `outputs/theme_tracker_YYYY-MM-DD.csv`
- `outputs/theme_members_YYYY-MM-DD.csv`

## RS leads

After the scanner makes the stock group, it compares relative strength with SPY.

- RS is the close divided by the SPY close.
- An RS new high is the highest RS in 252 days, or in 52 weeks.
- An RS lead is an RS new high. At the same time, the price is a minimum of 0.5% below its high for that period.

The relative strength can make a new high before the price makes a new high. The procedure writes these files:

- `outputs/rs_new_highs_YYYY-MM-DD.csv` for each RS new high. The file shows daily and weekly results.
- `outputs/rs_leads_YYYY-MM-DD.csv` for the RS lead setups only.
- `outputs/EXPORT/rs_lead_symbols_YYYY-MM-DD.csv`

You can run this procedure alone:

```bash
python rs_lead_scan.py
```

The NEL rules do not change. RS is an additional list. On the dashboard, select Setups, then select RS leads.

## 8-week EMA pullbacks

This scan uses the Liquid Leaders list only. It finds names near an 8-week EMA when all of these conditions are true:

- The slope of the weekly EMA(8) is positive.
- The daily close is not more than 3% above the EMA.
- The daily close is not more than 1.5% below the EMA.
- The price is a minimum of 1% below the high of the last 8 weeks.

The procedure writes these files:

- `outputs/ema8_pullbacks_YYYY-MM-DD.csv`
- `outputs/EXPORT/ema8_pullback_symbols_YYYY-MM-DD.csv`

You can run this procedure alone:

```bash
python ema8_pullback_scan.py
```

The daily `focus_list.py` procedure includes this scan. On the dashboard, select Setups, then select 8-week.

## MA stack

This scan uses the Liquid Leaders list only. A name must agree with these conditions:

- SMA5 is above SMA10.
- SMA20 moved above SMA30 in the last 3 sessions, or the gap between them is not more than 0.75%.

The procedure writes these files:

- `outputs/ma_stack_YYYY-MM-DD.csv`
- `outputs/EXPORT/ma_stack_symbols_YYYY-MM-DD.csv`

You can run this procedure alone:

```bash
python ma_stack_scan.py
```

The daily `focus_list.py` procedure includes this scan. On the dashboard, select Setups, then select MA stack.

## A++ flag breakouts

This scan finds a coil before the price break. It does not keep a late continuation. The pattern examples are NVDA, MU, SNDK, INTC, and TSLA. The scanner rejects a late move. An example is ASST after the base break on 19 August.

A name must agree with these conditions:

1. The price increases 18% or more into the base.
2. After the peak, the coil continues for 20 sessions or more. The depth is not more than 35%. The range becomes smaller.
3. The 50-day moving average is flat or has a positive slope. The 20-day and 50-day averages are close. The close is not more than 10% above the 20-day average.
4. `APLUS_COIL` means the price is not more than 6% below the flag high or the peak. The volume is lower than the volume in the advance.
5. `APLUS_BREAKOUT` means the close goes through the pivot on that day only.
6. MACD is a soft confirmation. It is not a required condition.

The procedure writes these files:

- `outputs/a_plus_flags_YYYY-MM-DD.csv`
- `outputs/EXPORT/a_plus_flag_coil_symbols_YYYY-MM-DD.csv` for the coil list
- `outputs/EXPORT/a_plus_flag_breakout_symbols_YYYY-MM-DD.csv` for the day of the break only
- `outputs/EXPORT/a_plus_flag_symbols_YYYY-MM-DD.csv`

You can run this procedure alone:

```bash
python a_plus_flag_scan.py
```

The daily `focus_list.py` procedure includes this scan. On the dashboard, select Setups, then select A++ flags. The coil names are first.

## GitHub Pages

`index.html` is the same file as the dashboard. GitHub Pages uses this file. The workflow is `.github/workflows/daily-scan.yml`. This workflow starts the scanner after the US market closes. It saves the new CSV files and the dashboard. The Mac can be off.

Do these steps to publish the page:

1. Open the GitHub Pages settings for the repository.
2. Select the `main` branch.
3. Select the root folder as the source.
