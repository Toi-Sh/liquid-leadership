"""Generate a self-contained interactive industry-leadership dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


TIMEFRAMES = {
    "1m": "is_top_1m",
    "3m": "is_top_3m",
    "6m": "is_top_6m",
}

# Related industries roll up so a Semis kickoff is not missed when
# leadership spreads across peripherals / equipment names.
THEME_CLUSTERS = {
    "Semis complex": frozenset({
        "Semiconductors",
        "Computer Peripherals",
        "Computer Processing Hardware",
        "Electronic Production Equipment",
        "Electronic Equipment/Instruments",
        "Electronics/Appliances",
    }),
}

RISING_MIN_COUNT = 2
RISING_MIN_DELTA = 1

# Livingston's voice in Edwin Lefèvre, Reminiscences of a Stock Operator (1923).
# Public domain in the USA. Short lines only — not passages from later books.
LIVERMORE_QUOTES = [
    "There is nothing new in Wall Street. There can't be because speculation is as old as the hills. Whatever happens in the stock market today has happened before and will happen again.",
    "A battle goes on in the stock market and the tape is your telescope. You can depend upon it seven out of ten cases.",
    "I didn't ask the tape why when I was fourteen, and I don't ask it today, at forty. Your business with the tape is now — not tomorrow. The reason can wait.",
    "I kept my business to myself. It was a one-man business. That is why I have always played a lone hand.",
    "I was playing a system and not a favorite stock or backing opinions.",
    "There is the plain fool, who does the wrong thing at all times everywhere, but there is the Wall Street fool, who thinks he must trade all the time.",
    "No man can always have adequate reasons for buying or selling stocks daily — or sufficient knowledge to make his play an intelligent play.",
    "Whenever I read the tape by the light of experience I made money, but when I made a plain fool play I had to lose.",
    "The desire for constant action irrespective of underlying conditions is responsible for many losses in Wall Street even among the professionals, who feel that they must take home some money every day, as though they were working for regular wages.",
    "I always made money when I was sure I was right before I began. What beat me was not having brains enough to stick to my own game — to play the market only when I was satisfied that precedents favored my play.",
    "There is a time for all things, but I didn't know it. And that is precisely what beats so many men in Wall Street.",
    "I never lose my temper over the stock market. I never argue with the tape. Getting sore at the market doesn't get you anywhere.",
    "There wasn't anything wrong with me; only with my play.",
    "It takes a man a long time to learn all the lessons of all his mistakes.",
    "There is only one side to the stock market; and it is not the bull side or the bear side, but the right side.",
    "A man must believe in himself and his judgment if he expects to make a living at this game. That is why I don't believe in tips.",
    "Nobody can make big money on what someone else tells him to do.",
    "If I buy stocks on Smith's tip I must sell those same stocks on Smith's tip. I am depending on him.",
    "The game taught me the game. And it didn't spare the rod while teaching.",
    "Reading the tape like an expert did not save me.",
    "In A. R. Fullerton's office the tape always talked ancient history to me, as far as my system of trading went, and I didn't realise it.",
    "It was not that I was playing it legitimately that made me lose, but that I was playing it ignorantly.",
    "Of course I let the craving for excitement get the better of my judgment.",
    "I was accustomed to regarding the tape as the best little friend I had, because I bet according to what it told me. But this time the tape double-crossed me.",
    "It took me five years to learn to play the game intelligently enough to make big money when I was right.",
    "I thought I was beating the game when in reality I was only beating the shop.",
    "The market does not beat them. They beat themselves, because though they have brains they cannot sit tight.",
    "Old Turkey was dead right in doing and saving what he did. He had not only the courage of his convictions but the intelligent patience to sit tight.",
    "Disregarding the big swing and trying to jump in and out was fatal to me. Nobody can catch all the fluctuations.",
    "In a bull market your game is to buy and hold until you believe that the bull market is near its end.",
    "To do this you must study the general conditions and not tips or special factors affecting individual stocks. Then get out of all your stocks; get out for keeps!",
    "The big money was not in the individual fluctuations but in the main movements — not in reading the tape but in sizing up the entire market and its trend.",
    "When old Mr. Partridge kept on telling the other customers, \"Well, you know this is a bull market!\" he really meant to tell them that the big money was not in the individual fluctuations but in the main movements.",
    "It never was my thinking that made the big money for me. It always was my sitting. My sitting tight!",
    "It is no trick at all to be right on the market. You always find lots of early bulls in bull markets and early bears in bear markets.",
    "Men who can both be right and sit tight are uncommon. I found it one of the hardest things to learn.",
    "It is literally true that millions come easier to a trader after he knows how to trade than hundreds did in the days of his ignorance.",
    "A man may see straight and clearly and yet become impatient or doubtful when the market takes its time about doing as he figured it must do.",
    "They say you never grow poor taking profits. No, you don't. But neither do you grow rich taking a four-point profit in a bull market.",
    "Of all speculative blunders there are few greater than trying to average a losing game.",
    "Always sell what shows you a loss and keep what shows you a profit.",
    "The cotton showed me a loss and I kept it. The wheat showed me a profit and I sold it out.",
    "The speculator's chief enemies are always boring from within.",
    "It is inseparable from human nature to hope and to fear.",
    "When the market goes against you, you hope that every day will be the last day — and you lose more than you should had you not listened to hope.",
    "When the market goes your way you become fearful that the next day will take away your profit, and you get out — too soon.",
    "Fear keeps you from making as much money as you ought to. The successful trader has to fight these two deep-seated instincts.",
    "Instead of hoping he must fear; instead of fearing he must hope. He must fear that his loss may develop into a much bigger loss, and hope that his profit may become a big profit.",
    "The speculator's deadly enemies are ignorance, greed, fear and hope. All the statute books in the world and all the rules of all the Exchanges on earth cannot eliminate these from the human animal.",
    "If a stock doesn't act right don't touch it; because, being unable to tell precisely what is wrong, you cannot tell which way it is going. No diagnosis, no prognosis. No prognosis, no profit.",
    "It is enough for the experienced trader to perceive that something is wrong. He must not expect the tape to become a lecturer. His job is to listen for it to say \"Get out!\"",
    "Prices, like everything else, move along the line of least resistance. They will go up if there is less resistance to an advance than to a decline; and vice versa.",
    "The trend is evident to a man who has an open mind and reasonably clear sight, for it is never wise for a speculator to fit his facts to his theories.",
    "The speculator is not an investor. His object is not to secure a steady return on his money at a good rate of interest, but to profit by either a rise or a fall in the price of whatever he may be speculating in.",
    "A man cannot be convinced against his own convictions, but he can be talked into a state of uncertainty and indecision, which is even worse, for that means that he cannot trade with confidence and comfort.",
    "The professional concerns himself with doing the right thing rather than with making money, knowing that the profit takes care of itself if the other things are attended to.",
    "A trader gets to play the game as the professional billiard player does — he looks far ahead instead of considering the particular shot before him.",
    "I have always found it profitable to study my mistakes.",
    "It was all very well not to lose your bear position in a bear market, but at all times the tape should be read to determine the propitiousness of the time for operating.",
    "Observation, experience, memory and mathematics — these are what the successful trader must depend on.",
    "He must not only observe accurately but remember at all times what he has observed.",
    "He cannot bet on the unreasonable or on the unexpected, however strong his personal convictions may be.",
    "The principles of successful stock speculation are based on the supposition that people will continue in the future to make the mistakes that they have made in the past.",
    "The public is so often whipsawed that one marvels at their persistence in not learning their lesson.",
    "The average man doesn't wish to be told that it is a bull or a bear market. What he desires is to be told specifically which particular stock to buy or sell.",
    "He wants to get something for nothing. He does not wish to work. He doesn't even wish to have to think.",
    "I never hesitate to tell a man that I am bullish or bearish. But I do not tell people to buy or sell any particular stock.",
    "In a bear market all stocks go down and in a bull market they go up.",
    "To buy on a rising market is the most comfortable way of buying stocks. The point is not to buy as cheap as possible or go short at top prices, but to buy or sell at the right time.",
    "When I am bearish and I sell a stock, each sale must be at a lower level than the previous sale. When I am buying, the reverse is true. I must buy on a rising scale.",
    "I don't buy long stock on a scale down. I buy on a scale up.",
    "Remember that stocks are never too high for you to begin buying or too low to begin selling.",
    "After the initial transaction, don't make a second unless the first shows you a profit. Wait and watch.",
    "Never try to sell at the top. It isn't wise. Sell after a reaction if there is no rally.",
    "Give up trying to catch the last eighth — or the first. These two are the most expensive eighths in the world.",
    "The man who is right always has two forces working in his favor — basic conditions and the men who are wrong.",
    "In a bull market bear factors are ignored. That is human nature.",
    "A man may possess an original mind and a lifelong habit of independent thinking and withal be vulnerable to attacks by a persuasive personality.",
    "The training of a stock trader is like a medical education. He learns the theory and then proceeds to devote his life to the practice.",
    "He must not permit himself set opinions. He must have an open mind and flexibility.",
    "It is not wise to disregard the message of the tape, no matter what your opinion of crop conditions or of the probable demand may be.",
    "The weaknesses to which a speculator is prone are almost numberless.",
    "I have been in the speculative game ever since I was fourteen. It is all I have ever done.",
    "A man may beat a stock or a group at a certain time, but no man living can beat the stock market!",
]


RECORD_COLUMNS = [
    "name",
    "industry",
    "exchange",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "average_dollar_volume_30d",
    "dollar_volume_30d",
    "atr_extension_from_50d",
    "is_top_1m",
    "is_top_3m",
    "is_top_6m",
    "rvol",
    "lod_atr_pct",
    "sma20_distance_pct",
    "above_sma200",
    "earnings_soon",
    "earnings_date",
    "hard_rule_passes",
    "hard_rule_fails",
    "focus_score",
    "tradingview_url",
    "ma_aligned",
    "range_tight",
    "lod_ok",
    "ema_aligned",
    "near_ema",
    "adr_tight",
    "bb_tight",
    "plan_tight",
    "tightness_flags",
    "rvol_expand",
]

RS_RECORD_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "rs",
    "signal",
    "is_rs_lead",
    "rs_new_high_d",
    "rs_new_high_w",
    "rs_lead_d",
    "rs_lead_w",
    "price_new_high_d",
    "price_new_high_w",
    "pct_below_price_high",
    "lookback_price_high",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "tradingview_url",
]

EMA8_RECORD_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "ema8w",
    "dist_to_ema8w_pct",
    "ema8w_slope_pct",
    "off_8w_high_pct",
    "tagged_ema8w",
    "ema8w_rising",
    "signal",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "tradingview_url",
]

MA_STACK_RECORD_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "SMA5",
    "SMA10",
    "SMA20",
    "SMA30",
    "sma5_gt_sma10",
    "sma20_gt_sma30",
    "sma20_30_gap_pct",
    "cross_days_ago",
    "signal",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "tradingview_url",
]

APLUS_FLAG_RECORD_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "signal",
    "grade",
    "sma20",
    "sma50",
    "flag_len",
    "flag_high",
    "flag_depth_pct",
    "thrust_pct",
    "dist_to_pivot_pct",
    "break_days_ago",
    "rvol",
    "ma_pinch_pct",
    "checks_passed",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "tradingview_url",
]

THEME_SCAN_RECORD_COLUMNS = [
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
    "tradingview_url",
]


def _records_from_frame(frame: pd.DataFrame) -> list[dict]:
    columns = [column for column in RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return _records_from_frame(pd.read_csv(path))


def _rs_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    columns = [column for column in RS_RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _ema8_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    columns = [column for column in EMA8_RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _ma_stack_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    columns = [column for column in MA_STACK_RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _theme_scan_records(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    if path.stat().st_size == 0:
        return []
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    columns = [column for column in THEME_SCAN_RECORD_COLUMNS if column in frame.columns]
    if frame.empty or "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _theme_scan_themes(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    if frame.empty or "industry" not in frame.columns:
        return []
    return [str(name) for name in frame["industry"].fillna("").tolist() if str(name).strip()]


def _a_plus_flag_records(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    if frame.empty or "name" not in frame.columns:
        return []
    columns = [column for column in APLUS_FLAG_RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _cluster_counts(groups: dict[str, int], members: frozenset[str]) -> int:
    return sum(int(groups.get(name, 0) or 0) for name in members)


def _signal_for_rise(prior: int, current: int) -> str | None:
    delta = current - prior
    if delta < RISING_MIN_DELTA or current < RISING_MIN_COUNT:
        return None
    # Fresh breadth: new or thin theme expanding into real participation.
    if prior == 0 or (prior <= 1 and current >= 3):
        return "KICKOFF"
    return "RISING"


def detect_rising_themes(
    current_groups: dict[str, dict[str, int]] | None,
    prior_groups: dict[str, dict[str, int]] | None,
    *,
    primary_frame: str = "1m",
) -> list[dict]:
    """Flag industries (and clusters) whose LL window count is expanding."""
    current_groups = current_groups or {}
    prior_groups = prior_groups or {}
    frames = [primary_frame] + [frame for frame in TIMEFRAMES if frame != primary_frame]
    rising: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for frame in frames:
        now = current_groups.get(frame) or {}
        then = prior_groups.get(frame) or {}
        industries = set(now) | set(then)
        for industry in industries:
            current = int(now.get(industry, 0) or 0)
            prior = int(then.get(industry, 0) or 0)
            signal = _signal_for_rise(prior, current)
            if not signal:
                continue
            key = (frame, industry)
            if key in seen:
                continue
            seen.add(key)
            rising.append({
                "frame": frame,
                "industry": industry,
                "kind": "industry",
                "prior_count": prior,
                "current_count": current,
                "delta": current - prior,
                "signal": signal,
            })
        for cluster_name, members in THEME_CLUSTERS.items():
            current = _cluster_counts(now, members)
            prior = _cluster_counts(then, members)
            signal = _signal_for_rise(prior, current)
            if not signal:
                continue
            key = (frame, cluster_name)
            if key in seen:
                continue
            seen.add(key)
            rising.append({
                "frame": frame,
                "industry": cluster_name,
                "kind": "cluster",
                "prior_count": prior,
                "current_count": current,
                "delta": current - prior,
                "signal": signal,
                "members": sorted(members),
            })

    rising.sort(
        key=lambda row: (
            0 if row["frame"] == primary_frame else 1,
            0 if row["signal"] == "KICKOFF" else 1,
            -int(row["delta"]),
            -int(row["current_count"]),
            str(row["industry"]),
        )
    )
    return rising


def rising_industry_names(rising: list[dict], *, frame: str | None = "1m") -> set[str]:
    """Industries to highlight on desk lists for a rising / kickoff theme."""
    names: set[str] = set()
    for row in rising:
        if frame is not None and row.get("frame") != frame:
            continue
        if row.get("kind") == "cluster":
            names.update(row.get("members") or [])
        else:
            names.add(str(row["industry"]))
    return names


def annotate_rising_themes(snapshots: list[dict]) -> list[dict]:
    for index, snapshot in enumerate(snapshots):
        prior = snapshots[index - 1] if index else None
        rising = detect_rising_themes(
            snapshot.get("groups"),
            prior.get("groups") if prior else None,
        )
        snapshot["rising_themes"] = rising
        snapshot["rising_industries"] = sorted(rising_industry_names(rising, frame="1m"))
    return snapshots


def write_rising_theme_csvs(output_dir: Path, snapshots: list[dict]) -> list[Path]:
    """Persist rising-theme flags beside the daily scan outputs."""
    written: list[Path] = []
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(parents=True, exist_ok=True)
    for snapshot in snapshots:
        rising = snapshot.get("rising_themes") or []
        stamp = snapshot["date"]
        path = output_dir / f"rising_themes_{stamp}.csv"
        rows = []
        for item in rising:
            rows.append({
                "date": stamp,
                "frame": item.get("frame"),
                "kind": item.get("kind"),
                "industry": item.get("industry"),
                "signal": item.get("signal"),
                "prior_count": item.get("prior_count"),
                "current_count": item.get("current_count"),
                "delta": item.get("delta"),
                "members": "|".join(item.get("members") or []),
            })
        frame = pd.DataFrame(rows, columns=[
            "date", "frame", "kind", "industry", "signal",
            "prior_count", "current_count", "delta", "members",
        ])
        frame.to_csv(path, index=False)
        written.append(path)

        rising_set = set(snapshot.get("rising_industries") or [])
        symbols = sorted({
            str(row.get("name") or "").strip()
            for row in (snapshot.get("liquid") or [])
            if str(row.get("industry") or "").strip() in rising_set and str(row.get("name") or "").strip()
        })
        symbol_path = export_dir / f"rising_theme_symbols_{stamp}.csv"
        pd.DataFrame({"symbol": symbols}).to_csv(symbol_path, index=False)
        written.append(symbol_path)
    return written


def collect_industry_history(output_dir: Path) -> list[dict]:
    """Summarise every dated momentum-leader snapshot by industry and timeframe."""
    snapshots = []
    for path in sorted(output_dir.glob("momentum_leaders_*.csv")):
        match = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", path.name)
        if not match:
            continue
        frame = pd.read_csv(path)
        if "industry" not in frame.columns:
            continue
        groups = {}
        for label, flag in TIMEFRAMES.items():
            if flag not in frame.columns:
                continue
            counts = (
                frame.loc[frame[flag].fillna(False).astype(bool), "industry"]
                .fillna("Unclassified")
                .value_counts()
                .to_dict()
            )
            groups[label] = {str(industry): int(count) for industry, count in counts.items()}
        stamp = match.group(1)
        # `groups` comes only from full momentum-leader files. The NEL subset
        # below is a display table and cannot influence theme leadership.
        snapshots.append({
            "date": stamp,
            "groups": groups,
            "liquid": _records_from_frame(frame),
            "nel": _records(output_dir / f"non_extended_leaders_{stamp}.csv"),
            "focus": _records(output_dir / f"focus_candidates_{stamp}.csv"),
            "rs_leads": _rs_records(output_dir / f"rs_leads_{stamp}.csv"),
            "rs_highs": _rs_records(output_dir / f"rs_new_highs_{stamp}.csv"),
            "ema8_pullbacks": _ema8_records(output_dir / f"ema8_pullbacks_{stamp}.csv"),
            "ma_stack": _ma_stack_records(output_dir / f"ma_stack_{stamp}.csv"),
            "a_plus_flags": _a_plus_flag_records(output_dir / f"a_plus_flags_{stamp}.csv"),
            "theme_scan": _theme_scan_records(output_dir / f"theme_scan_{stamp}.csv"),
            "theme_scan_themes": _theme_scan_themes(output_dir / f"theme_scan_themes_{stamp}.csv"),
        })
    return annotate_rising_themes(snapshots)


def write_dashboard(output_dir: Path) -> Path:
    """Write an offline-friendly interactive dashboard with embedded history."""
    history = collect_industry_history(output_dir)
    write_rising_theme_csvs(output_dir, history)
    dashboard = Path("industry_flow_dashboard.html")
    pages_entrypoint = Path("index.html")
    payload = json.dumps(history, separators=(",", ":"))
    quotes_payload = json.dumps(LIVERMORE_QUOTES, ensure_ascii=False, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>State of the Markets</title>
  <meta name="description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://toi-sh.github.io/liquid-leadership/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Liquid Leadership">
  <meta property="og:title" content="State of the Markets">
  <meta property="og:description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta property="og:url" content="https://toi-sh.github.io/liquid-leadership/">
  <meta property="og:image" content="https://toi-sh.github.io/liquid-leadership/assets/nel-social-preview.png">
  <meta property="og:image:width" content="1731">
  <meta property="og:image:height" content="909">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="State of the Markets">
  <meta name="twitter:description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta name="twitter:image" content="https://toi-sh.github.io/liquid-leadership/assets/nel-social-preview.png">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="apple-touch-icon" href="assets/nel-favicon.png">
  <link rel="preload" href="assets/fonts/newsreader-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/source-sans-3-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css?v=20261006">
  <style>
html { color-scheme: light; }
html, body { overflow-x: clip; overflow-anchor: none; }
* { box-sizing: border-box; }
html { background: var(--color-paper); }
body {
  margin: 0;
  background: var(--color-paper);
  color: var(--color-ink-2);
  font-family: var(--font-body);
  font-weight: 400;
  font-size: var(--text-base);
  line-height: 1.35;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
  overscroll-behavior-y: contain;
}
main { min-height: 100dvh; }
img, svg, table { max-width: 100%; }
h1, h2, h3 {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  letter-spacing: -0.02em;
  line-height: 1.15;
  text-transform: none;
  color: var(--color-ink);
  overflow-wrap: anywhere;
  min-width: 0;
  line-height: 1;
  scroll-margin-top: calc(var(--banner-height) + var(--mobile-nav-keys, 0px) + var(--space-xs));
}
#qotd { scroll-margin-top: calc(var(--banner-height) + var(--mobile-nav-keys, 0px)); }
a { color: inherit; }
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
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
  white-space: nowrap;
}
.skip-link:focus-visible { transform: none; outline: 2px solid var(--color-focus); outline-offset: var(--space-3xs); }

.nav-edge {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky-nav);
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: var(--space-sm);
  min-height: var(--banner-height);
  padding: 0 var(--page-gutter);
  padding-left: max(var(--page-gutter), env(safe-area-inset-left));
  padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  background: var(--color-paper);
  color: var(--color-ink);
  border-bottom: var(--rule) solid var(--color-rule);
}
.bbg-product {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  letter-spacing: -0.02em;
  text-transform: none;
  color: var(--color-ink);
  text-decoration: none;
  line-height: 1;
  white-space: nowrap;
}
.bbg-brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  color: inherit;
  text-decoration: none;
}
.bbg-brand:hover { color: var(--color-accent); }
.bbg-brand:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
.bbg-product {
  font-size: var(--text-md);
  color: var(--color-ink);
}
.bbg-keys {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: stretch;
  gap: 0;
  overflow: visible;
}
.desk-menu { position: relative; display: flex; align-items: stretch; }
.desk-tab {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin: 0;
  padding: 0 var(--space-12);
  min-height: var(--banner-height);
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-ink);
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-weight: 400;
  font-style: normal;
  letter-spacing: 0.01em;
  text-transform: none;
  text-decoration: none;
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
.desk-tab[aria-current="true"],
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
  margin: 0;
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
  letter-spacing: 0;
  text-decoration: none;
  text-transform: none;
  white-space: nowrap;
}
.desk-menu__panel a[aria-current="true"] { color: var(--color-accent); }
.nav-edge__controls {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
}
.bbg-clock {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--color-muted);
  white-space: nowrap;
}
select,
.btn,
.note-input {
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-control);
  background: var(--color-paper);
  color: var(--color-ink);
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
  line-height: 1;
  outline: 2px solid transparent;
  outline-offset: 1px;
}
select,
.btn {
  min-height: var(--control-height);
  padding: 0 var(--space-sm);
  white-space: nowrap;
}
select { width: 9.5rem; max-width: 100%; min-width: 0; background: var(--color-paper); }
.btn { cursor: pointer; }
.btn--primary {
  background: var(--color-ink);
  color: var(--color-paper);
  border-color: var(--color-ink);
}
.btn--ghost {
  background: transparent;
  color: var(--color-ink);
  border-color: var(--color-rule);
}
@media (hover: hover) and (pointer: fine) {
  select:hover, .btn:hover, .note-input:hover { border-color: var(--color-accent); color: var(--color-accent); }
  .btn--primary:hover { background: var(--color-ink-2); color: var(--color-paper); border-color: var(--color-ink-2); }
  .ticker-link:hover { color: var(--color-accent); text-decoration: underline; text-underline-offset: var(--space-3xs); }
  .desk-tab:hover,
  .desk-menu__panel a:hover,
  .subnav__tab:hover { color: var(--color-accent); }
}
select:focus-visible,
.btn:focus-visible,
.note-input:focus-visible,
.ticker-link:focus-visible,
.desk-tab:focus-visible,
.desk-menu__panel a:focus-visible,
.subnav__tab:focus-visible {
  outline: 2px solid var(--color-ink);
  outline-offset: 1px;
}
select:active, .btn:active { transform: translateY(1px); }
.btn:disabled, select:disabled, .note-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.btn[data-state="loading"] { cursor: wait; opacity: 0.7; }
.btn[data-state="error"], .note-input[aria-invalid="true"] { border-color: var(--color-danger); color: var(--color-danger); }
.btn[data-state="success"] { border-color: var(--color-up); }

main {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0 var(--page-gutter) var(--space-lg);
}
.lede {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-sm);
  max-width: none;
  margin: 0 calc(var(--page-gutter) * -1) var(--space-sm);
  padding: var(--space-2xs) var(--page-gutter);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  letter-spacing: 0;
  text-transform: none;
  color: var(--color-muted);
  background: transparent;
  border-bottom: var(--rule) solid var(--color-rule);
}
.desk-block {
  margin-top: var(--space-md);
  border: var(--rule) solid var(--color-rule);
  padding: var(--space-xs);
  background: var(--color-paper);
  border-radius: var(--radius-card);
}
.desk-block--graphite {
  margin-inline: 0;
  padding: var(--space-xs);
  background: var(--color-paper-2);
  color: var(--color-ink);
  border-color: var(--color-rule);
}
.desk-block--graphite h1,
.desk-block--graphite h2,
.desk-block--graphite h3 { color: var(--color-ink); }
.desk-block--graphite .btn--ghost {
  background: transparent;
  color: var(--color-accent);
  border-color: var(--color-accent);
}
.section-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-2xs);
  align-items: center;
  margin: 0 0 var(--space-sm);
  padding: 0;
  background: transparent;
  border-bottom: 0;
}
.section-heading h1,
.section-heading h2 {
  margin: 0;
  font-size: var(--text-display);
  font-style: normal;
}
.section-heading .btn,
.section-heading .theme-scan__count { justify-self: start; }
#bbg-session { flex: 0 0 auto; }
.qotd-strip {
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
  margin: 0 calc(var(--page-gutter) * -1) var(--space-sm);
  padding: var(--space-2xs) var(--page-gutter);
  border-bottom: var(--rule) solid var(--color-rule);
}
.qotd-strip__text {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-style: normal;
  line-height: 1.45;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qotd-strip__meta {
  flex: 0 0 auto;
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.01em;
  text-transform: none;
  color: var(--color-muted);
  white-space: nowrap;
}
.qotd-strip .btn { min-height: 2rem; padding: 0 var(--space-8); }
.desk-view[hidden] { display: none; }
.subnav {
  display: flex;
  align-items: stretch;
  gap: 0;
  margin-top: var(--space-sm);
  border-bottom: var(--rule) solid var(--color-rule);
  overflow-x: auto;
  scrollbar-width: none;
}
.subnav::-webkit-scrollbar { display: none; }
.subnav__tab {
  margin: 0;
  padding: 0 var(--space-sm);
  min-height: 2.5rem;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-ink);
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-style: normal;
  font-weight: 400;
  letter-spacing: 0.01em;
  text-transform: none;
  white-space: nowrap;
  cursor: pointer;
}
.subnav__tab[aria-selected="true"] {
  color: var(--color-accent);
  border-bottom-color: var(--color-accent);
}
.desk-view .desk-block { margin-top: var(--space-sm); }
.desk-block[hidden] { display: none; }
.theme-scan { margin-top: var(--space-sm); }
.theme-scan[hidden] { display: none; }
.theme-scan__count {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.01em;
  text-transform: none;
  color: var(--color-muted);
}
.window-sections {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-sm);
  align-items: start;
}
.panel,
.nel-window {
  min-width: 0;
  padding: 0;
  border: var(--rule) solid var(--color-rule);
  background: var(--color-paper);
}
.panel h2,
.nel-window h3 {
  margin: 0;
  padding: var(--space-2xs) var(--space-xs);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  background: var(--color-paper-3);
}
.trend-label { margin-top: 0; border-top: var(--rule) solid var(--color-rule); }
.trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-8) var(--space-16);
  padding: var(--space-8) var(--space-xs) var(--space-xs);
  border-top: var(--rule) solid var(--color-rule);
}
.trend-legend__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-8);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-ink-2);
  min-width: 0;
}
.trend-legend__swatch {
  width: 0.75rem;
  height: 0.125rem;
  flex-shrink: 0;
  background: currentColor;
}
.panel[data-frame="1m"] h2, .nel-window[data-frame="1m"] h3 { color: var(--color-frame-1m); }
.panel[data-frame="3m"] h2, .nel-window[data-frame="3m"] h3 { color: var(--color-frame-3m); }
.panel[data-frame="6m"] h2, .nel-window[data-frame="6m"] h3 { color: var(--color-frame-6m); }
.desk-block--graphite .panel,
.desk-block--graphite .nel-window { border-color: var(--color-graphite-rule); }
.bars { display: grid; gap: var(--space-2xs); padding: var(--space-xs); }
.bar-row {
  display: grid;
  grid-template-columns: minmax(0, 8rem) minmax(0, 1fr) 2.5rem;
  gap: var(--space-xs);
  align-items: center;
}
.industry {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.industry--lead { font-weight: 600; color: var(--color-accent); }
tbody tr.row--theme-lead {
  outline: 1px solid var(--color-up);
  outline-offset: -1px;
  background: color-mix(in oklch, var(--color-up) 12%, var(--color-paper));
}
tbody tr.row--theme-lead td {
  border-bottom-color: color-mix(in oklch, var(--color-up) 45%, var(--color-rule));
}
tbody tr.row--theme-lead .ticker-link {
  color: var(--color-up);
}
tbody tr.row--theme-lead .col-ticker {
  box-shadow: inset 2px 0 0 var(--color-up);
}
.desk-block--graphite tbody tr.row--theme-lead {
  background: color-mix(in oklch, var(--color-up) 14%, var(--color-paper));
}
.desk-block--graphite tbody tr.row--theme-lead .ticker-link {
  color: var(--color-up);
}
tbody tr.row--theme-rising {
  outline: 1px dashed var(--color-frame-1m);
  outline-offset: -1px;
  background: color-mix(in oklch, var(--color-frame-1m) 10%, var(--color-paper));
}
tbody tr.row--theme-rising td {
  border-bottom-color: color-mix(in oklch, var(--color-frame-1m) 40%, var(--color-rule));
}
tbody tr.row--theme-rising .ticker-link {
  color: var(--color-frame-1m);
}
tbody tr.row--theme-rising .col-ticker {
  box-shadow: inset 2px 0 0 var(--color-frame-1m);
}
tbody tr.row--theme-lead.row--theme-rising {
  outline: 1px solid var(--color-up);
  background: color-mix(in oklch, var(--color-up) 10%, color-mix(in oklch, var(--color-frame-1m) 8%, var(--color-paper)));
}
.rising-alert {
  margin: 0 0 var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-frame-1m);
  background: color-mix(in oklch, var(--color-frame-1m) 12%, var(--color-paper));
  font-family: var(--font-body);
  font-size: var(--text-sm);
  line-height: 1.5;
  color: var(--color-ink-2);
}
.rising-alert[hidden] { display: none; }
.rising-alert__label {
  display: block;
  width: fit-content;
  margin: 0 0 var(--space-xs);
  padding: 0.1rem 0.4rem;
  border: 1px solid var(--color-frame-1m);
  color: var(--color-frame-1m);
  font-family: var(--font-body);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.rising-alert strong {
  color: var(--color-frame-1m);
  font-family: var(--font-body);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.industry--rising::after {
  content: " ▲";
  color: var(--color-frame-1m);
  font-size: 0.85em;
}
.track {
  height: 0.75rem;
  position: relative;
  background: var(--color-paper-3);
}
.desk-block--graphite .track { background: var(--color-paper-3); }
.bar {
  height: 0.25rem;
  position: absolute;
  left: 0;
}
.bar.current { top: 0.0625rem; }
.bar.previous { bottom: 0.0625rem; background: var(--color-prior); }
.value {
  color: var(--color-ink);
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--text-xs);
}
.desk-block--graphite .value { color: var(--color-graphite-ink); }
svg {
  width: 100%;
  height: var(--chart-height);
  display: block;
  overflow: visible;
  padding: 0 var(--space-xs) var(--space-xs);
}
.theme-card {
  padding: var(--space-2xs) var(--space-xs);
  margin: 0;
  border-bottom: var(--rule) solid var(--color-rule);
  background: var(--color-paper-2);
}
.desk-block--graphite .theme-card { border-bottom-color: var(--color-graphite-rule); }
.theme-line { display: block; color: var(--color-ink-2); font-family: var(--font-body); font-size: var(--text-sm); line-height: 1.5; }
.theme-line + .theme-line { margin-top: var(--space-2xs); }
.desk-block--graphite .theme-line { color: var(--color-graphite-muted); }
.theme-line strong { color: var(--color-accent); font-weight: 600; }
.desk-block--graphite .theme-line strong { color: var(--color-accent); }
.rs-lede { margin: 0 0 var(--space-sm); max-width: 46rem; color: var(--color-ink-2); font-family: var(--font-body); font-size: var(--text-sm); line-height: 1.5; }
.table-wrap { overflow-x: auto; max-width: 100%; -webkit-overflow-scrolling: touch; }
.scrollable-table { max-height: 16rem; overflow-y: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-family: var(--font-body);
  font-variant-numeric: tabular-nums;
}
.scrollable-table th {
  position: sticky;
  top: 0;
  background: var(--color-paper-3);
  z-index: var(--z-raised);
}
.desk-block--graphite .scrollable-table th { background: var(--color-paper-3); }
th, td {
  padding: var(--space-xs) var(--space-sm);
  border-bottom: var(--rule) solid var(--color-rule);
  text-align: right;
  font-size: var(--text-xs);
}
.desk-block--graphite th,
.desk-block--graphite td { border-bottom-color: var(--color-graphite-rule); }
th:first-child, th:nth-child(2), td:first-child, td:nth-child(2) { text-align: left; }
th {
  color: var(--color-muted);
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--color-paper-3);
}
.desk-block--graphite th { color: var(--color-accent); }
td.col-industry { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--color-muted); }
td.col-rules { white-space: normal; line-height: 1.4; }
.ticker-link {
  font-family: var(--font-outlier);
  font-weight: 600;
  color: var(--color-ink);
  text-decoration: none;
}
.desk-block--graphite .ticker-link { color: var(--color-graphite-ink); }
.high-liquidity { color: var(--color-liquidity); }
tbody tr:nth-child(even) { background: color-mix(in oklch, var(--color-paper-2) 70%, transparent); }
.tick-up { color: var(--color-up); }
.tick-down { color: var(--color-down); }
.ticker-link--earn { box-shadow: inset 0 -2px 0 var(--color-warn); }
.note-input {
  width: 100%;
  min-height: 1.5rem;
  padding: var(--space-3xs) var(--space-2xs);
  background: var(--color-paper-2);
  color: var(--color-ink);
  border-color: var(--color-rule-2);
  text-transform: none;
  letter-spacing: 0;
  font-weight: 400;
}
.desk-block--graphite .note-input {
  background: var(--color-paper);
  color: var(--color-graphite-ink);
  border-color: var(--color-graphite-rule);
}
.empty {
  color: var(--color-muted);
  padding: var(--space-sm) var(--space-xs);
  text-align: left;
  font-family: var(--font-mono);
}
.desk-block--graphite .empty { color: var(--color-graphite-muted); }
.snapshot-date {
  font-family: var(--font-outlier);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-accent-ink);
}
.dashboard-title { margin: 0; }
.foot-line {
  border-top: var(--rule) solid var(--color-rule);
  padding: var(--space-xs) var(--page-gutter);
  max-width: none;
  margin: 0;
  background: var(--color-paper);
}
.foot-line p {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.01em;
  text-transform: none;
  color: var(--color-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (min-width: 40rem) {
  .section-heading { grid-template-columns: minmax(0, 1fr) auto; }
  .section-heading .btn,
  .section-heading .theme-scan__count { justify-self: end; }
  .bar-row { grid-template-columns: minmax(0, 11rem) minmax(0, 1fr) 2.5rem; }
}
@media (min-width: 60rem) {
  .window-sections { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (min-width: 90rem) {
  .window-sections { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 60rem) {
  .bbg-clock { display: none; }
}
@media (max-width: 47.99rem) {
  :root {
    --page-gutter: var(--space-8);
    --chart-height: 11rem;
    --banner-height: 3.25rem;
    --control-height: 2.75rem;
    --mobile-nav-keys: 2.5rem;
  }
  body {
    padding-bottom: env(safe-area-inset-bottom);
    font-size: var(--text-sm);
  }
  .nav-edge {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      "brand controls"
      "keys keys";
    align-items: center;
    gap: 0;
    min-height: 0;
    padding: 0;
    padding-top: env(safe-area-inset-top);
  }
  .bbg-brand {
    grid-area: brand;
    min-height: var(--banner-height);
    padding-left: max(var(--page-gutter), env(safe-area-inset-left));
  }
  .nav-edge__controls {
    grid-area: controls;
    gap: var(--space-4);
    flex-shrink: 0;
    padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  }
  .bbg-keys {
    grid-area: keys;
    flex: 0 0 auto;
    width: 100%;
    min-height: var(--mobile-nav-keys);
    height: auto;
    gap: 0;
    border-top: var(--rule) solid var(--color-paper-2);
    padding: 0 max(var(--page-gutter), env(safe-area-inset-left)) 0 max(var(--page-gutter), env(safe-area-inset-right));
    overflow: visible;
  }
  .desk-tab {
    min-height: var(--mobile-nav-keys);
    height: var(--mobile-nav-keys);
    padding: 0 var(--space-12);
    font-size: 0.625rem;
    touch-action: manipulation;
  }
  .desk-menu__panel a { min-height: 2.75rem; font-size: var(--text-xs); touch-action: manipulation; }
  select,
  .btn {
    min-height: var(--control-height);
    padding: 0 var(--space-8);
    font-size: 0.625rem;
    touch-action: manipulation;
  }
  select { width: auto; min-width: 6.5rem; }
  .lede,
  .qotd-strip {
    margin-left: 0;
    margin-right: 0;
    padding-left: max(var(--page-gutter), env(safe-area-inset-left));
    padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  }
  .lede { flex-wrap: wrap; }
  .qotd-strip { flex-wrap: wrap; align-items: center; }
  .qotd-strip__text { flex-basis: 100%; white-space: normal; }
  .qotd-strip__meta { flex: 1 1 auto; }
  .desk-block,
  .foot-line {
    padding-left: max(var(--page-gutter), env(safe-area-inset-left));
    padding-right: max(var(--page-gutter), env(safe-area-inset-right));
  }
  .section-heading { gap: var(--space-8); }
  .section-heading .btn { width: 100%; justify-self: stretch; }
  .col-industry,
  .col-vol,
  .col-ext,
  .col-rules,
  .col-score,
  .col-rs-d,
  .col-rs-w,
  .col-below { display: none; }
  .bar-row {
    grid-template-columns: minmax(0, 1fr) 2rem;
    gap: var(--space-4) var(--space-8);
  }
  .bar-row .industry { grid-column: 1 / -1; }
  .bar-row .track { grid-column: 1; }
  .bar-row .value { grid-column: 2; grid-row: 2; }
  .trend-legend {
    gap: var(--space-4) var(--space-8);
    padding-inline: var(--space-2xs);
  }
  .scrollable-table { max-height: 22rem; overscroll-behavior: contain; }
  th, td { padding: var(--space-2xs) var(--space-3xs); }
  .note-input {
    min-height: var(--control-height);
    font-size: 16px;
    touch-action: manipulation;
  }
  .rs-lede { margin: 0 0 var(--space-xs); }
  .foot-line p { white-space: normal; }
  .ticker-link { touch-action: manipulation; }
}
@media (max-width: 22.5rem) {
  .desk-tab { padding: 0 var(--space-8); }
  select { min-width: 5.5rem; }
  .btn--primary { padding: 0 var(--space-8); }
}
@media (pointer: coarse) {
  .note-input { min-height: var(--control-height); }
  .ticker-link { padding: var(--space-2xs) 0; display: inline-block; }
}
@media (prefers-reduced-motion: reduce) {
  select, .btn, .note-input, .ticker-link, .skip-link {
    transition: none;
  }
  select:active, .btn:active { transform: none; }
}
  </style>
</head>
<body>
<a class="skip-link" href="#desk">Skip to desk</a>
<main>
  <header class="nav-edge topbar">
    <a class="bbg-brand" href="index.html#thematic-title">
      <span class="bbg-product">Liquid Leadership</span>
    </a>
    <nav class="bbg-keys" aria-label="Terminal panels">
      <a class="desk-tab" data-panel="themes" href="#thematic-title">Themes</a>
      <div class="desk-menu">
        <button class="desk-tab" type="button" data-panel="leaders" aria-haspopup="menu" aria-expanded="false" aria-controls="menu-leaders">Leaders <span class="desk-caret" aria-hidden="true"></span></button>
        <div id="menu-leaders" class="desk-menu__panel" role="menu" hidden>
          <a role="menuitem" href="#liquid-title">Liquid Leaders</a>
          <a role="menuitem" href="#focus-title">Focus</a>
          <a role="menuitem" href="#nel-title">Non-extended</a>
        </div>
      </div>
      <div class="desk-menu">
        <button class="desk-tab" type="button" data-panel="setups" aria-haspopup="menu" aria-expanded="false" aria-controls="menu-setups">Setups <span class="desk-caret" aria-hidden="true"></span></button>
        <div id="menu-setups" class="desk-menu__panel" role="menu" hidden>
          <a role="menuitem" href="#rs-title">Relative strength</a>
          <a role="menuitem" href="#ema8-title">8-week</a>
          <a role="menuitem" href="#ma-stack-title">Moving averages</a>
          <a role="menuitem" href="#aplus-title">Flag breakouts</a>
        </div>
      </div>
      <a class="desk-tab" data-panel="tape" href="theme_tracker.html">Tape</a>
    </nav>
    <div class="nav-edge__controls">
      <span id="bbg-clock" class="bbg-clock" aria-live="off"></span>
      <label class="visually-hidden" for="date">Snapshot date</label>
      <select id="date" aria-label="Snapshot date"></select>
    </div>
  </header>
  <p class="lede"><span id="bbg-session">US equity session</span></p>
  <p class="qotd-strip" id="qotd">
    <span id="qotd-text" class="qotd-strip__text"></span>
    <span id="qotd-meta" class="qotd-strip__meta">Jesse Livermore</span>
    <button id="qotd-next" class="btn btn--ghost" type="button">Next</button>
  </p>
  <div id="desk">
  <div id="view-themes" class="desk-view" data-view="themes">
  <section class="desk-block" aria-labelledby="thematic-title">
    <div class="section-heading"><h1 id="thematic-title" class="dashboard-title">Thematic Leadership</h1></div>
    <div id="rising-theme-alert" class="rising-alert" hidden role="status" aria-live="polite"></div>
    <div id="theme-scan" class="theme-scan" hidden></div>
    <div id="leadership-sections" class="window-sections"></div>
  </section>
  </div>
  <div id="view-leaders" class="desk-view" data-view="leaders" hidden>
    <div class="subnav" role="tablist" aria-label="Leader lists">
      <button class="subnav__tab" type="button" role="tab" data-hash="#liquid-title" aria-selected="true">Liquid Leaders</button>
      <button class="subnav__tab" type="button" role="tab" data-hash="#focus-title" aria-selected="false">Focus</button>
      <button class="subnav__tab" type="button" role="tab" data-hash="#nel-title" aria-selected="false">Non-extended</button>
    </div>
  <section class="desk-block" data-sub="liquid" aria-labelledby="liquid-title">
    <div class="section-heading">
      <h2 id="liquid-title">Liquid leaders</h2>
      <button id="download-ll" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="liquid-sections" class="window-sections"></div>
  </section>
  <section class="desk-block desk-block--graphite" data-sub="focus" aria-labelledby="focus-title" hidden>
    <div class="section-heading">
      <h2 id="focus-title">Focus</h2>
      <button id="download-focus" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="focus-sections" class="window-sections"></div>
  </section>
  <section class="desk-block" data-sub="nel" aria-labelledby="nel-title" hidden>
    <div class="section-heading">
      <h2 id="nel-title">Non-extended leaders</h2>
      <button id="download-nel" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="nel-sections" class="window-sections"></div>
  </section>
  </div>
  <div id="view-setups" class="desk-view" data-view="setups" hidden>
    <div class="subnav" role="tablist" aria-label="Setup scans">
      <button class="subnav__tab" type="button" role="tab" data-hash="#rs-title" aria-selected="true">Relative strength</button>
      <button class="subnav__tab" type="button" role="tab" data-hash="#ema8-title" aria-selected="false">8-week</button>
      <button class="subnav__tab" type="button" role="tab" data-hash="#ma-stack-title" aria-selected="false">Moving averages</button>
      <button class="subnav__tab" type="button" role="tab" data-hash="#aplus-title" aria-selected="false">Flag breakouts</button>
    </div>
  <section class="desk-block desk-block--graphite" data-sub="rs" aria-labelledby="rs-title">
    <div class="section-heading">
      <h2 id="rs-title">Relative strength</h2>
      <button id="download-rs" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="rs-sections" class="window-sections"></div>
  </section>
  <section class="desk-block" data-sub="ema8" aria-labelledby="ema8-title" hidden>
    <div class="section-heading">
      <h2 id="ema8-title">8-week pullbacks</h2>
      <button id="download-ema8" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="ema8-sections" class="window-sections"></div>
  </section>
  <section class="desk-block desk-block--graphite" data-sub="ma" aria-labelledby="ma-stack-title" hidden>
    <div class="section-heading">
      <h2 id="ma-stack-title">Moving averages</h2>
      <button id="download-ma-stack" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="ma-stack-sections" class="window-sections"></div>
  </section>
  <section class="desk-block" data-sub="aplus" aria-labelledby="aplus-title" hidden>
    <div class="section-heading">
      <h2 id="aplus-title">Flag breakouts</h2>
      <button id="download-aplus" class="btn btn--ghost" type="button">Export</button>
    </div>
    <div id="aplus-sections" class="window-sections"></div>
  </section>
  </div>
  </div>
</main>
<footer class="foot-line">
  <p>Liquid Leadership · not financial advice</p>
</footer>
<script>
const history = __DATA__;
const QUOTES = __QUOTES__;
(function initQuoteOfDay() {
  const text = document.getElementById('qotd-text');
  const meta = document.getElementById('qotd-meta');
  const button = document.getElementById('qotd-next');
  if (!text || !Array.isArray(QUOTES) || !QUOTES.length) return;
  const storageKey = 'lld-qotd';
  function nyDate() {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  }
  function hash(value) {
    let h = 2166136261;
    for (let i = 0; i < value.length; i++) {
      h ^= value.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }
  function readSaved() {
    try { return JSON.parse(localStorage.getItem(storageKey) || 'null'); } catch { return null; }
  }
  function save(index) {
    try { localStorage.setItem(storageKey, JSON.stringify({ date: nyDate(), index })); } catch { /* private mode */ }
  }
  function show(index) {
    text.textContent = QUOTES[index];
    text.dataset.index = String(index);
    if (meta) meta.textContent = (index + 1) + ' / ' + QUOTES.length + ' · Jesse Livermore · Reminiscences, 1923';
  }
  const today = nyDate();
  const saved = readSaved();
  let index = hash('lld|' + today) % QUOTES.length;
  if (saved && saved.date === today && Number.isInteger(saved.index) && saved.index >= 0 && saved.index < QUOTES.length) index = saved.index;
  show(index);
  if (!button) return;
  button.addEventListener('click', () => {
    const current = Number(text.dataset.index);
    let next = current;
    if (QUOTES.length > 1) {
      while (next === current) next = Math.floor(Math.random() * QUOTES.length);
    }
    show(next);
    save(next);
  });
})();
const dateSelect = document.getElementById('date');
const thematicTitle = document.getElementById('thematic-title');
const liquidTitle = document.getElementById('liquid-title');
const nelTitle = document.getElementById('nel-title');
const focusTitle = document.getElementById('focus-title');
const rsTitle = document.getElementById('rs-title');
const ema8Title = document.getElementById('ema8-title');
const maStackTitle = document.getElementById('ma-stack-title');
const aplusTitle = document.getElementById('aplus-title');
const leadershipSections = document.getElementById('leadership-sections');
const risingThemeAlert = document.getElementById('rising-theme-alert');
const liquidSections = document.getElementById('liquid-sections');
const nelSections = document.getElementById('nel-sections');
const focusSections = document.getElementById('focus-sections');
const rsSections = document.getElementById('rs-sections');
const ema8Sections = document.getElementById('ema8-sections');
const maStackSections = document.getElementById('ma-stack-sections');
const aplusSections = document.getElementById('aplus-sections');
const downloadLiquidButton = document.getElementById('download-ll');
const downloadNelButton = document.getElementById('download-nel');
const downloadFocusButton = document.getElementById('download-focus');
const downloadRsButton = document.getElementById('download-rs');
const downloadEma8Button = document.getElementById('download-ema8');
const downloadMaStackButton = document.getElementById('download-ma-stack');
const downloadAplusButton = document.getElementById('download-aplus');
const flowMeta = { '1m': { label:'1 month', color:'var(--color-frame-1m)' }, '3m': { label:'3 months', color:'var(--color-frame-3m)' }, '6m': { label:'6 months', color:'var(--color-frame-6m)' } };
const rankColors = ['var(--color-rank-1)', 'var(--color-rank-2)', 'var(--color-rank-3)', 'var(--color-rank-4)', 'var(--color-rank-5)'];
const NOTE_KEY = 'nel-note:';

function risingThemes(snapshot) { return snapshot?.rising_themes || []; }
function risingIndustrySet(snapshot) { return new Set(snapshot?.rising_industries || []); }
function isRisingThemeRow(row, snapshot) {
  const industry = String(row?.industry || '').trim();
  return Boolean(industry && risingIndustrySet(snapshot).has(industry));
}
function stockCount(n) {
  const count = Math.max(0, Number(n) || 0);
  return count === 1 ? '1 stock' : `${count} stocks`;
}
function leaderPhrase(count) {
  const n = Number(count) || 0;
  if (n === 0) return 'no stocks';
  return stockCount(n);
}
function riseSentence(row) {
  const name = row.industry;
  const before = leaderPhrase(row.prior_count);
  const after = Number(row.current_count) || 0;
  const now = after === 1 ? '1 stock' : `${after} stocks`;
  if (row.signal === 'KICKOFF') return `${name} is new. Last time it had ${before}. Now it has ${now}.`;
  return `${name} has more stocks than last time. It had ${before}. Now it has ${now}.`;
}
function rsSignalLabel(signal) {
  return {
    LEAD_D_W: 'Leads this session and this week',
    LEAD_D: 'Leads this session',
    LEAD_W: 'Leads this week',
    RS_D_W: 'New high this session and this week',
    RS_D: 'New high this session',
    RS_W: 'New high this week'
  }[signal] || '—';
}
function maSignalLabel(signal) {
  return {
    '20x30_TODAY': 'Crossed this session',
    '20x30_1D': 'Crossed the session before',
    '20x30_2D': 'Crossed two sessions before',
    '20x30_NEAR': 'Close to a cross'
  }[signal] || '—';
}
function renderRisingAlert(snapshot) {
  if (!risingThemeAlert) return;
  const primary = risingThemes(snapshot).filter(row => row.frame === '1m');
  if (!primary.length) {
    risingThemeAlert.hidden = true;
    risingThemeAlert.innerHTML = '';
    return;
  }
  const sentences = primary.slice(0, 6).map(row => escapeHTML(riseSentence(row))).join(' ');
  const mark = primary.length === 1
    ? 'That group has a dashed line in the lists.'
    : 'These groups have a dashed line in the lists.';
  risingThemeAlert.hidden = false;
  risingThemeAlert.innerHTML = `<span class="rising-alert__label">Since last time</span><span class="rising-alert__text">${sentences} ${mark}</span>`;
}
function counts(snapshot, frame) { return snapshot?.groups?.[frame] || {}; }
function total(map) { return Object.values(map).reduce((a,b) => a + b, 0); }
function escapeHTML(value) { return String(value ?? '—').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
function formatPct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'; }
function formatNumber(value) { return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—'; }
function formatDollarVolume(value) { const amount = Number(value); if (!Number.isFinite(amount) || amount <= 0) return '—'; if (amount >= 1_000_000_000) return `$${Math.ceil(amount / 1_000_000_000)}B`; return `$${Math.ceil(amount / 10_000_000) * 10}M`; }
function formatShares(value) { const amount = Number(value); if (!Number.isFinite(amount) || amount <= 0) return '—'; if (amount >= 1_000_000_000) return `${(amount / 1_000_000_000).toFixed(1)}B`; if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(1)}M`; return `${Math.round(amount / 1000)}K`; }
function averageDollarVolume(row) { return row.average_dollar_volume_30d ?? row.dollar_volume_30d; }
function isTrue(value) { return value === true || String(value).toLowerCase() === 'true'; }
function noteValue(symbol) { try { return localStorage.getItem(NOTE_KEY + symbol) || ''; } catch { return ''; } }
function saveNote(symbol, value) {
  try {
    const key = NOTE_KEY + symbol;
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch { /* private mode */ }
}
function chartUrl(row) {
  const url = String(row.tradingview_url || '').trim();
  if (url) return url;
  const name = String(row.name || '').trim();
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(name)}&interval=D`;
}
function tickerMarkup(row) {
  const name = String(row.name || '').trim();
  const highLiquidity = Number(averageDollarVolume(row)) > 450_000_000;
  const earn = isTrue(row.earnings_soon);
  const title = earn && row.earnings_date ? `Earnings are on ${String(row.earnings_date)}.` : 'Open the chart in a new tab.';
  const classes = `ticker-link${highLiquidity ? ' high-liquidity' : ''}${earn ? ' ticker-link--earn' : ''}`;
  return `<td class="col-ticker"><a class="${classes}" href="${escapeHTML(chartUrl(row))}" target="_blank" rel="noopener noreferrer" title="${escapeHTML(title)}">${escapeHTML(name)}</a></td>`;
}
function noteMarkup(row) {
  const name = String(row.name || '').trim();
  return `<td class="col-note"><label><span class="visually-hidden">Note for ${escapeHTML(name)}</span><input class="note-input" type="text" data-symbol="${escapeHTML(name)}" value="${escapeHTML(noteValue(name))}" autocomplete="off" spellcheck="false" maxlength="240"></label></td>`;
}
function metricCells(row, performance, top) {
  const dollarVolume = averageDollarVolume(row);
  const highLiquidity = Number(dollarVolume) > 450_000_000;
  const lead = top && row.industry === top[0] ? ' industry--lead' : '';
  const move = Number(row[performance]);
  const tick = Number.isFinite(move) && move > 0 ? ' tick-up' : Number.isFinite(move) && move < 0 ? ' tick-down' : '';
  return `${tickerMarkup(row)}<td class="col-industry${lead}">${escapeHTML(row.industry)}</td><td class="col-perf${tick}">${formatPct(row[performance])}</td><td class="col-vol${highLiquidity ? ' high-liquidity' : ''}">${formatDollarVolume(dollarVolume)}</td><td class="col-ext">${formatNumber(row.atr_extension_from_50d)}×</td>`;
}
function focusExtras(row) {
  const score = Number.isFinite(Number(row.focus_score)) ? String(row.focus_score) : '—';
  const failText = {
    'LoD>60% ATR': 'The low of the day is far from the close.',
    '>4x 50-MA': 'The price is far above the 50-day average.',
    'thin RVOL': 'Volume is light.',
    'earnings soon': 'Earnings are soon.',
    'below 200-MA': 'The price is below the 200-day average.',
    'large gap': 'The opening gap is large.'
  };
  const tightText = {
    EMA: 'The short averages are stacked.',
    near21: 'The price is near the 21-day average.',
    ADR: 'The day range is tight.',
    BB: 'The price band is tight.',
    RVOL: 'Volume is expanding.'
  };
  const phrases = raw => String(raw || '').split(',').map(part => part.trim()).filter(Boolean).map(token => failText[token] || tightText[token] || token);
  const passed = Number(row.hard_rule_passes);
  const passedLine = Number.isFinite(passed) ? (passed === 1 ? '1 check passed.' : `${passed} checks passed.`) : '';
  const text = [passedLine, ...phrases(row.hard_rule_fails), ...phrases(row.tightness_flags)].filter(Boolean).join(' ');
  return `<td class="col-score">${escapeHTML(score)}</td><td class="col-rules">${escapeHTML(text || '—')}</td>`;
}
function updateDates() {
  dateSelect.innerHTML = history.map((d,i) => `<option value="${i}">${d.date}</option>`).join('');
  dateSelect.value = Math.max(0, history.length - 1);
}
function tickClock() {
  const clock = document.getElementById('bbg-clock');
  if (!clock) return;
  clock.textContent = new Date().toLocaleString('en-US', {
    timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }) + ' NY';
}
function currentSnapshot() { return history[Number(dateSelect.value)] || null; }
function renderBars(current, previous, frame, container) {
  const now = counts(current, frame), then = counts(previous, frame);
  const rising = new Set((risingThemes(current) || []).filter(row => row.frame === frame).map(row => row.industry));
  // Cluster members still mark individual bars when the cluster itself is rising.
  (risingThemes(current) || []).filter(row => row.frame === frame && row.kind === 'cluster').forEach(row => {
    (row.members || []).forEach(name => rising.add(name));
  });
  const names = [...new Set([...Object.keys(now), ...Object.keys(then)])].sort((a,b) => (now[b]||0) - (now[a]||0) || (then[b]||0) - (then[a]||0)).slice(0, 5);
  if (!names.length) { container.innerHTML = '<p class="empty">No leaders are available for this date.</p>'; return []; }
  const max = Math.max(1, ...names.flatMap(n => [now[n]||0, then[n]||0]));
  container.innerHTML = names.map((name, index) => {
    const color = rankColors[index];
    const risingClass = rising.has(name) ? ' industry--rising' : '';
    const nowCount = now[name] || 0;
    const thenCount = then[name] || 0;
    const title = rising.has(name) ? `${name} has more stocks than last time. It had ${leaderPhrase(thenCount)}. Now it has ${leaderPhrase(nowCount)}.` : name;
    return `<div class="bar-row"><div class="industry${risingClass}" style="color:${color}" title="${escapeHTML(title)}">${escapeHTML(name)}</div><div class="track"><div class="bar current" style="width:${nowCount/max*100}%;background:${color}" title="This session has ${leaderPhrase(nowCount)}."></div><div class="bar previous" style="width:${thenCount/max*100}%" title="The last session had ${leaderPhrase(thenCount)}."></div></div><div class="value">${nowCount}</div></div>`;
  }).join('');
  return names;
}
function renderTrend(frame, svg, names) {
  const legend = document.getElementById(`trend-legend-${frame}`);
  if (legend) {
    legend.innerHTML = (names || []).map((name, index) => `<span class="trend-legend__item"><span class="trend-legend__swatch" style="background:${rankColors[index]}"></span>${escapeHTML(name)}</span>`).join('');
  }
  const active = history.filter(d => d.groups?.[frame]);
  if (active.length < 2) { svg.innerHTML = '<text x="20" y="45" fill="var(--color-muted)">More daily updates will show how these industries change.</text>'; return; }
  const width = Math.max(620, svg.clientWidth || 900), height = 300, left = 42, right = 28, top = 18, bottom = 34;
  const max = Math.max(1, ...active.flatMap(d => Object.values(counts(d, frame))));
  const x = i => left + i * ((width-left-right) / Math.max(1, active.length-1));
  const y = value => top + (max-value) * ((height-top-bottom)/max);
  let markup = `<line x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}" stroke="var(--color-rule)"/><line x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}" stroke="var(--color-rule)"/>`;
  for (let i=0;i<=max;i++) markup += `<text x="${left-8}" y="${y(i)+4}" text-anchor="end" font-size="12" fill="var(--color-ink-2)">${i}</text>`;
  active.forEach((d,i) => markup += `<text x="${x(i)}" y="${height-12}" text-anchor="middle" font-size="12" fill="var(--color-ink-2)">${d.date.slice(5)}</text>`);
  names.forEach((name, index) => { const color = rankColors[index]; const points = active.map((d,i) => `${x(i)},${y(counts(d,frame)[name]||0)}`).join(' '); markup += `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5"/>`; active.forEach((d,i) => markup += `<circle cx="${x(i)}" cy="${y(counts(d,frame)[name]||0)}" r="3" fill="${color}"><title>${escapeHTML(name)} had ${leaderPhrase(counts(d,frame)[name]||0)} on ${d.date}.</title></circle>`); });
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.innerHTML = markup;
}
function windowTables(prefix, heading, extraHead, extraCell, emptyLabel) {
  return Object.entries(flowMeta).map(([frame, meta]) => {
    const extras = extraHead ? extraHead : '';
    return `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} ${heading}</h3><div id="${prefix}-theme-${frame}" class="theme-card frame-${frame}"></div><div class="table-wrap${prefix === 'liquid' ? ' scrollable-table' : ''}"><table><thead><tr><th>Symbol</th><th class="col-industry">Industry</th><th>Performance</th><th class="col-vol">Dollar volume</th><th class="col-ext">Stretch</th>${extras}<th>Notes</th></tr></thead><tbody id="${prefix}-table-${frame}"></tbody></table></div></section>`;
  }).join('');
}
function leadingTheme(snapshot, frame) {
  return Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0] || null;
}
function isLeadingThemeRow(row, top) {
  return Boolean(top && row.industry && row.industry === top[0]);
}
function rowThemeClasses(row, top, snapshot) {
  const lead = isLeadingThemeRow(row, top);
  const rising = isRisingThemeRow(row, snapshot);
  return [lead ? 'row--theme-lead' : '', rising ? 'row--theme-rising' : ''].filter(Boolean).join(' ');
}
function rowThemeTitle(row, top, snapshot) {
  const bits = [];
  if (isLeadingThemeRow(row, top)) bits.push(`This stock is in ${top[0]}, the biggest group.`);
  if (isRisingThemeRow(row, snapshot)) bits.push('This group has more stocks than last time.');
  return bits.join(' · ');
}
function fillTheme(id, snapshot, frame) {
  const themeCard = document.getElementById(id);
  if (!themeCard) return null;
  const top = leadingTheme(snapshot, frame);
  const label = flowMeta[frame]?.label || frame;
  const rising = risingThemes(snapshot).filter(row => row.frame === frame);
  const risingNote = rising.slice(0, 3).map(row => escapeHTML(riseSentence(row))).join(' ');
  const period = label === '1 month' ? 'the past month' : `the past ${label}`;
  const count = top ? stockCount(top[1]) : '';
  const green = top && Number(top[1]) === 1 ? 'That row is green.' : 'Green rows are in that group.';
  const changes = risingNote ? `<span class="theme-line">${risingNote}</span>` : '';
  themeCard.innerHTML = top
    ? `<span class="theme-line">In ${escapeHTML(period)}, <strong>${escapeHTML(top[0])}</strong> is the biggest group, with ${count}. ${green}</span>${changes}`
    : `<span class="theme-line">No group stands out in ${escapeHTML(period)}.</span>${changes}`;
  return top;
}
function renderTableRows(records, frame, performance, flag, tableId, extraCell, emptyLabel, colspan) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const snapshot = currentSnapshot();
  const top = leadingTheme(snapshot, frame);
  const rows = records.filter(row => isTrue(row[flag])).sort((a, b) => {
    const scoreDelta = Number(b.focus_score) - Number(a.focus_score);
    if (extraCell && Number.isFinite(scoreDelta) && scoreDelta) return scoreDelta;
    return Number(b[performance]) - Number(a[performance]);
  });
  table.innerHTML = rows.length ? rows.map(row => {
    const classes = rowThemeClasses(row, top, snapshot);
    const title = rowThemeTitle(row, top, snapshot);
    return `<tr class="${classes}"${title ? ` title="${escapeHTML(title)}"` : ''}>${metricCells(row, performance, top)}${extraCell ? extraCell(row) : ''}${noteMarkup(row)}</tr>`;
  }).join('') : `<tr><td colspan="${colspan}" class="empty">${emptyLabel}</td></tr>`;
}
function renderLiquid(snapshot) {
  const records = snapshot?.liquid || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    fillTheme(`liquid-theme-${frame}`, snapshot, frame);
    renderTableRows(records, frame, performance, flag, `liquid-table-${frame}`, null, 'No liquid leaders for this window.', 6);
  });
}
function renderNEL(snapshot) {
  const records = snapshot?.nel || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    fillTheme(`nel-theme-${frame}`, snapshot, frame);
    renderTableRows(records, frame, performance, flag, `nel-table-${frame}`, null, 'No non-extended leaders for this window.', 6);
  });
}
function renderFocus(snapshot) {
  const records = snapshot?.focus || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    fillTheme(`focus-theme-${frame}`, snapshot, frame);
    renderTableRows(records, frame, performance, flag, `focus-table-${frame}`, focusExtras, 'No focus stocks for this window.', 8);
  });
}
function rsFlag(value) { return isTrue(value) ? 'Y' : '—'; }
function renderRS(snapshot) {
  if (!rsSections) return;
  const leads = snapshot?.rs_leads || [];
  const highs = snapshot?.rs_highs || [];
  const top = leadingTheme(snapshot, '1m');
  const rows = (leads.length ? leads : highs).slice().sort((a, b) => {
    const leadDelta = Number(isTrue(b.is_rs_lead)) - Number(isTrue(a.is_rs_lead));
    if (leadDelta) return leadDelta;
    return Number(b.pct_below_price_high || 0) - Number(a.pct_below_price_high || 0);
  });
  const highLine = !highs.length
    ? ''
    : highs.length === 1
      ? '1 stock has a new high in relative strength.'
      : `${highs.length} stocks have a new high in relative strength.`;
  const rsSummary = !highs.length
    ? 'This scan has not run for this date.'
    : !leads.length
      ? `${highLine} ${highs.length === 1 ? 'It does not lead the market before the price does.' : 'None of them lead the market before the price does.'}`
      : `${leads.length === 1 ? '1 stock leads the market before its own price does.' : leads.length + ' stocks lead the market before their own price does.'} ${highLine}`;
  const rsTheme = !top ? '' : Number(top[1]) === 1
    ? ` That row is in <strong>${escapeHTML(top[0])}</strong>.`
    : ` Green rows are in <strong>${escapeHTML(top[0])}</strong>.`;
  rsSections.innerHTML = `<section class="nel-window" data-frame="1m"><h3>Relative strength</h3><div class="theme-card frame-1m"><span class="theme-line">${rsSummary}${rsTheme}</span></div><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th class="col-industry">Industry</th><th>Status</th><th class="col-rs-d">Daily high</th><th class="col-rs-w">Weekly high</th><th>Leads</th><th class="col-below">Below the high</th><th>Notes</th></tr></thead><tbody id="rs-table">${rows.length ? rows.map(row => { const classes = rowThemeClasses(row, top, snapshot); const title = rowThemeTitle(row, top, snapshot); return `<tr class="${classes}"${title ? ` title="${escapeHTML(title)}"` : ''}>${tickerMarkup(row)}<td class="col-industry${isLeadingThemeRow(row, top) ? ' industry--lead' : ''}">${escapeHTML(row.industry || '—')}</td><td>${escapeHTML(rsSignalLabel(row.signal))}</td><td class="col-rs-d">${rsFlag(row.rs_new_high_d) === 'Y' ? 'Yes' : 'No'}</td><td class="col-rs-w">${rsFlag(row.rs_new_high_w) === 'Y' ? 'Yes' : 'No'}</td><td>${isTrue(row.is_rs_lead) ? 'Yes' : 'No'}</td><td class="col-below">${formatNumber(row.pct_below_price_high)}%</td>${noteMarkup(row)}</tr>`; }).join('') : `<tr><td colspan="8" class="empty">No stocks lead the market today.</td></tr>`}</tbody></table></div></section>`;
}
function renderEMA8(snapshot) {
  if (!ema8Sections) return;
  const rows = (snapshot?.ema8_pullbacks || []).slice().sort((a, b) => Math.abs(Number(a.dist_to_ema8w_pct || 99)) - Math.abs(Number(b.dist_to_ema8w_pct || 99)));
  const top = leadingTheme(snapshot, '1m');
  const emaSummary = rows.length
    ? `${rows.length === 1 ? '1 liquid leader is' : rows.length + ' liquid leaders are'} within 3% of a rising 8-week average.`
    : 'No stock is near a rising 8-week average for this date.';
  ema8Sections.innerHTML = `<section class="nel-window" data-frame="1m"><h3>8-week pullbacks</h3><div class="theme-card frame-1m"><span class="theme-line">${emaSummary}</span></div><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th class="col-industry">Industry</th><th>Distance</th><th class="col-ext">Slope</th><th class="col-vol">Below the high</th><th>Notes</th></tr></thead><tbody id="ema8-table">${rows.length ? rows.map(row => { const classes = rowThemeClasses(row, top, snapshot); const title = rowThemeTitle(row, top, snapshot); return `<tr class="${classes}"${title ? ` title="${escapeHTML(title)}"` : ''}>${tickerMarkup(row)}<td class="col-industry${isLeadingThemeRow(row, top) ? ' industry--lead' : ''}">${escapeHTML(row.industry || '—')}</td><td>${formatNumber(row.dist_to_ema8w_pct)}%</td><td class="col-ext">${formatNumber(row.ema8w_slope_pct)}%</td><td class="col-vol">${formatNumber(row.off_8w_high_pct)}%</td>${noteMarkup(row)}</tr>`; }).join('') : `<tr><td colspan="6" class="empty">No pullbacks for this date.</td></tr>`}</tbody></table></div></section>`;
}
function renderMaStack(snapshot) {
  if (!maStackSections) return;
  const signalRank = { '20x30_TODAY': 0, '20x30_1D': 1, '20x30_2D': 2, '20x30_NEAR': 3 };
  const rows = (snapshot?.ma_stack || []).slice().sort((a, b) => {
    const rankDelta = (signalRank[a.signal] ?? 9) - (signalRank[b.signal] ?? 9);
    if (rankDelta) return rankDelta;
    return Number(a.sma20_30_gap_pct || 99) - Number(b.sma20_30_gap_pct || 99);
  });
  const top = leadingTheme(snapshot, '1m');
  const maSummary = rows.length
    ? `${rows.length === 1 ? '1 liquid leader has' : rows.length + ' liquid leaders have'} the 5-day average above the 10-day average. The 20-day average is crossing the 30-day average.`
    : 'No moving-average crosses for this date.';
  maStackSections.innerHTML = `<section class="nel-window" data-frame="1m"><h3>Moving averages</h3><div class="theme-card frame-1m"><span class="theme-line">${maSummary}</span></div><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th class="col-industry">Industry</th><th>Status</th><th class="col-ext">Gap</th><th class="col-vol">When</th><th>Notes</th></tr></thead><tbody id="ma-stack-table">${rows.length ? rows.map(row => { const classes = rowThemeClasses(row, top, snapshot); const title = rowThemeTitle(row, top, snapshot); const days = row.cross_days_ago === '' || row.cross_days_ago == null ? '—' : (Number(row.cross_days_ago) === 0 ? 'This session' : Number(row.cross_days_ago) === 1 ? 'The session before' : `${row.cross_days_ago} sessions before`); return `<tr class="${classes}"${title ? ` title="${escapeHTML(title)}"` : ''}>${tickerMarkup(row)}<td class="col-industry${isLeadingThemeRow(row, top) ? ' industry--lead' : ''}">${escapeHTML(row.industry || '—')}</td><td>${escapeHTML(maSignalLabel(row.signal))}</td><td class="col-ext">${formatNumber(row.sma20_30_gap_pct)}%</td><td class="col-vol">${escapeHTML(days)}</td>${noteMarkup(row)}</tr>`; }).join('') : `<tr><td colspan="6" class="empty">No moving-average crosses for this date.</td></tr>`}</tbody></table></div></section>`;
}
function renderAPlusFlags(snapshot) {
  if (!aplusSections) return;
  const signalRank = { APLUS_COIL: 0, APLUS_BREAKOUT: 1 };
  const gradeRank = { 'A++': 0, 'A+': 1, A: 2 };
  const rows = (snapshot?.a_plus_flags || []).slice().sort((a, b) => {
    const s = (signalRank[a.signal] ?? 9) - (signalRank[b.signal] ?? 9);
    if (s) return s;
    const g = (gradeRank[a.grade] ?? 9) - (gradeRank[b.grade] ?? 9);
    if (g) return g;
    return Number(a.dist_to_pivot_pct || 99) - Number(b.dist_to_pivot_pct || 99);
  });
  const bos = rows.filter(r => r.signal === 'APLUS_BREAKOUT').length;
  const coils = rows.length - bos;
  const top = leadingTheme(snapshot, '1m');
  const coilLine = coils === 0 ? 'No stock is still coiled under the breakout price.' : coils === 1 ? '1 stock is still coiled under the breakout price.' : `${coils} stocks are still coiled under the breakout price.`;
  const breakLine = bos === 0 ? 'None broke out this session.' : bos === 1 ? '1 stock broke out this session.' : `${bos} stocks broke out this session.`;
  aplusSections.innerHTML = `<section class="nel-window" data-frame="1m"><h3>Flag breakouts</h3><div class="theme-card frame-1m"><span class="theme-line">${rows.length ? `${coilLine} ${breakLine}` : 'No flag setups for this date.'}</span></div><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th class="col-industry">Industry</th><th>Status</th><th>Grade</th><th class="col-ext">Advance</th><th class="col-vol">Depth</th><th>Breakout price</th><th>Volume</th><th>Notes</th></tr></thead><tbody id="aplus-table">${rows.length ? rows.map(row => { const classes = rowThemeClasses(row, top, snapshot); const title = rowThemeTitle(row, top, snapshot); const sig = row.signal === 'APLUS_BREAKOUT' ? 'Broke out this session' : 'Still coiled'; return `<tr class="${classes}"${title ? ` title="${escapeHTML(title)}"` : ''}>${tickerMarkup(row)}<td class="col-industry${isLeadingThemeRow(row, top) ? ' industry--lead' : ''}">${escapeHTML(row.industry || '—')}</td><td>${sig}</td><td>${escapeHTML(row.grade || '—')}</td><td class="col-ext">${formatNumber(row.thrust_pct)}%</td><td class="col-vol">${formatNumber(row.flag_depth_pct)}%</td><td>${formatNumber(row.dist_to_pivot_pct)}%</td><td>${formatNumber(row.rvol)}</td>${noteMarkup(row)}</tr>`; }).join('') : `<tr><td colspan="9" class="empty">No flag setups for this date.</td></tr>`}</tbody></table></div></section>`;
}
function renderThemeScan(snapshot) {
  const host = document.getElementById('theme-scan');
  if (!host) return;
  const rows = snapshot ? snapshot.theme_scan : null;
  if (rows == null) { host.hidden = true; host.innerHTML = ''; return; }
  host.hidden = false;
  const themes = (snapshot.theme_scan_themes || []).filter(Boolean);
  const themeLine = !themes.length
    ? 'The top industries for the month were checked.'
    : themes.length === 1
      ? `This theme was checked: ${escapeHTML(themes[0])}.`
      : `These themes were checked: ${themes.map(name => escapeHTML(name)).join(', ')}.`;
  const rules = 'A stock must cost more than $1. The daily move must stay between a loss of 5% and a gain of 5%. Volume must be above 1 million shares. The price must be above the 10-day average, the 20-day average, and the weekly 10-day average. The 10-day and 20-day averages must be rising. Earnings and sales must both be up at least 40% from a year ago. Only the strongest stock in each theme is kept.';
  const body = rows.length ? rows.map(row => {
    const day = Number(row.change);
    const dayClass = Number.isFinite(day) && day > 0 ? ' tick-up' : Number.isFinite(day) && day < 0 ? ' tick-down' : '';
    return `<tr>${tickerMarkup(row)}<td class="col-industry">${escapeHTML(row.industry)}</td><td>${formatNumber(row.close)}</td><td class="col-perf${dayClass}">${formatPct(row.change)}</td><td class="col-vol">${formatShares(row.volume)}</td><td class="col-perf">${formatPct(row.earn_yoy)}</td><td class="col-perf">${formatPct(row.sales_yoy)}</td>${noteMarkup(row)}</tr>`;
  }).join('') : '<tr><td class="empty" colspan="8">No stock in these themes passed every check.</td></tr>';
  const countLabel = rows.length ? stockCount(rows.length) : 'No stocks';
  host.innerHTML = `<div class="section-heading"><h2>Theme scan</h2><span class="theme-scan__count">${countLabel}</span></div><p class="rs-lede">${themeLine} ${rules}</p><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th>Theme</th><th>Price</th><th>Day</th><th>Volume</th><th>Earnings</th><th>Sales</th><th>Notes</th></tr></thead><tbody>${body}</tbody></table></div>`;
}
function render() {
  const current = currentSnapshot(), index = Number(dateSelect.value), previous = history[index-1];
  liquidTitle.textContent = `Liquid leaders — ${stockCount((current.liquid || []).length)}`;
  nelTitle.textContent = `Non-extended leaders — ${stockCount((current.nel || []).length)}`;
  if (focusTitle) focusTitle.textContent = `Focus — ${stockCount((current.focus || []).length)}`;
  if (rsTitle) rsTitle.textContent = `Relative strength — ${stockCount((current.rs_leads || []).length)}`;
  if (ema8Title) ema8Title.textContent = `8-week pullbacks — ${stockCount((current.ema8_pullbacks || []).length)}`;
  if (maStackTitle) maStackTitle.textContent = `Moving averages — ${stockCount((current.ma_stack || []).length)}`;
  if (aplusTitle) aplusTitle.textContent = `Flag breakouts — ${stockCount((current.a_plus_flags || []).length)}`;
  renderRisingAlert(current);
  renderThemeScan(current);
  leadershipSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="panel" data-frame="${frame}"><h2>${meta.label} leadership</h2><div id="bars-${frame}" class="bars"></div><h2 class="trend-label">Leadership over time</h2><svg id="trend-${frame}" role="img" aria-label="How many leaders each industry had over ${meta.label}"></svg><div id="trend-legend-${frame}" class="trend-legend"></div></section>`).join('');
  liquidSections.innerHTML = windowTables('liquid', 'leaders', '', null, 'No liquid leaders.');
  if (focusSections) focusSections.innerHTML = windowTables('focus', 'focus stocks', '<th class="col-score">Score</th><th class="col-rules">Checks</th>', focusExtras, 'No focus stocks.');
  nelSections.innerHTML = windowTables('nel', 'leaders', '', null, 'No non-extended leaders.');
  Object.keys(flowMeta).forEach(frame => { const rankedNames = renderBars(current, previous, frame, document.getElementById(`bars-${frame}`)); renderTrend(frame, document.getElementById(`trend-${frame}`), rankedNames); });
  renderLiquid(current);
  renderFocus(current);
  renderNEL(current);
  renderRS(current);
  renderEMA8(current);
  renderMaStack(current);
  renderAPlusFlags(current);
}
function redrawChartsOnly() {
  const current = currentSnapshot(), index = Number(dateSelect.value), previous = history[index-1];
  if (!current) return;
  Object.keys(flowMeta).forEach(frame => {
    const bars = document.getElementById(`bars-${frame}`);
    const svg = document.getElementById(`trend-${frame}`);
    if (!bars || !svg) return;
    const rankedNames = renderBars(current, previous, frame, bars);
    renderTrend(frame, svg, rankedNames);
  });
}
function downloadSymbols(key, filePrefix) {
  const snapshot = currentSnapshot();
  const symbols = [...new Set((snapshot?.[key] || []).map(row => String(row.name || '').trim()).filter(Boolean))].sort();
  const csv = ['symbol', ...symbols.map(symbol => `"${symbol.replaceAll('"', '""')}"`)].join('\n') + '\n';
  const blob = new Blob([csv], { type:'text/csv;charset=utf-8' });
  const link = document.createElement('a'); link.download = `${filePrefix}_symbols_${snapshot.date}.csv`; link.href = URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href);
}
const panelViews = {
  '#thematic-title': { view: 'themes', sub: '' },
  '#liquid-title': { view: 'leaders', sub: 'liquid' },
  '#focus-title': { view: 'leaders', sub: 'focus' },
  '#nel-title': { view: 'leaders', sub: 'nel' },
  '#rs-title': { view: 'setups', sub: 'rs' },
  '#ema8-title': { view: 'setups', sub: 'ema8' },
  '#ma-stack-title': { view: 'setups', sub: 'ma' },
  '#aplus-title': { view: 'setups', sub: 'aplus' }
};
const panelGroups = Object.fromEntries(Object.entries(panelViews).map(([hash, spec]) => [hash, spec.view]));
function closeDeskMenus() {
  document.querySelectorAll('.desk-menu__panel').forEach(panel => {
    panel.hidden = true;
    const toggle = document.querySelector(`[aria-controls="${panel.id}"]`);
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  });
}
function setCurrentPanel(hash) {
  const group = panelGroups[hash] || 'themes';
  document.querySelectorAll('.desk-tab[data-panel]').forEach(tab => {
    if (tab.dataset.panel === 'tape') return;
    if (tab.dataset.panel === group) tab.setAttribute('aria-current', 'true');
    else tab.removeAttribute('aria-current');
  });
  document.querySelectorAll('.desk-menu__panel a').forEach(link => {
    if (link.getAttribute('href') === hash) link.setAttribute('aria-current', 'true');
    else link.removeAttribute('aria-current');
  });
}
function showPanel(hash) {
  const spec = panelViews[hash] || panelViews['#thematic-title'];
  const resolved = panelViews[hash] ? hash : '#thematic-title';
  document.querySelectorAll('.desk-view').forEach(view => {
    view.hidden = view.dataset.view !== spec.view;
  });
  const active = document.querySelector(`.desk-view[data-view="${spec.view}"]`);
  if (active && spec.sub) {
    active.querySelectorAll('.desk-block').forEach(block => {
      block.hidden = block.dataset.sub !== spec.sub;
    });
    active.querySelectorAll('.subnav__tab').forEach(tab => {
      tab.setAttribute('aria-selected', tab.dataset.hash === resolved ? 'true' : 'false');
    });
  }
  setCurrentPanel(resolved);
  if (history.replaceState) history.replaceState(null, '', resolved);
  if (spec.view === 'themes') requestAnimationFrame(redrawChartsOnly);
}
document.addEventListener('click', event => {
  const sub = event.target.closest('.subnav__tab');
  if (sub && sub.dataset.hash) {
    closeDeskMenus();
    showPanel(sub.dataset.hash);
    return;
  }
  const toggle = event.target.closest('.desk-tab[aria-haspopup]');
  if (toggle) {
    const panel = document.getElementById(toggle.getAttribute('aria-controls'));
    const open = toggle.getAttribute('aria-expanded') === 'true';
    closeDeskMenus();
    if (!open && panel) {
      panel.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
    }
    return;
  }
  const nav = event.target.closest('.desk-menu__panel a[href^="#"], .desk-tab[href^="#"]');
  if (nav) {
    const href = nav.getAttribute('href');
    if (href && document.querySelector(href)) {
      event.preventDefault();
      closeDeskMenus();
      showPanel(href);
    }
    return;
  }
  if (!event.target.closest('.desk-menu')) closeDeskMenus();
  const link = event.target.closest('a.ticker-link');
  if (!link) return;
  const href = link.getAttribute('href');
  if (!href || href.startsWith('#')) return;
  event.preventDefault();
  window.open(href, '_blank', 'noopener,noreferrer');
});
document.addEventListener('input', event => {
  const field = event.target.closest('.note-input');
  if (!field || !field.dataset.symbol) return;
  saveNote(field.dataset.symbol, field.value);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.querySelector('.desk-menu__panel:not([hidden])')) {
    closeDeskMenus();
    return;
  }
  const menu = event.target.closest('.desk-menu__panel');
  if (menu && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
    const items = [...menu.querySelectorAll('a')];
    const index = items.indexOf(document.activeElement);
    const next = event.key === 'ArrowDown' ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
    event.preventDefault();
    items[next]?.focus();
    return;
  }
});
let resizeTimer = 0;
let lastLayoutWidth = window.innerWidth;
function onViewportChange() {
  const width = window.innerWidth;
  // Mobile URL-bar show/hide changes height only — skip full re-renders.
  if (Math.abs(width - lastLayoutWidth) < 12) return;
  lastLayoutWidth = width;
  clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(redrawChartsOnly, 180);
}
if (!history.length) { document.querySelector('main').innerHTML = '<p class="empty">Run the scanner once to create a momentum-leader snapshot.</p>'; } else { updateDates(); tickClock(); setInterval(tickClock, 1000); dateSelect.addEventListener('change', render); downloadLiquidButton.addEventListener('click', () => downloadSymbols('liquid', 'liquid_leaders')); downloadNelButton.addEventListener('click', () => downloadSymbols('nel', 'nel')); if (downloadFocusButton) downloadFocusButton.addEventListener('click', () => downloadSymbols('focus', 'focus')); if (downloadRsButton) downloadRsButton.addEventListener('click', () => downloadSymbols('rs_leads', 'rs_leads')); if (downloadEma8Button) downloadEma8Button.addEventListener('click', () => downloadSymbols('ema8_pullbacks', 'ema8_pullbacks')); if (downloadMaStackButton) downloadMaStackButton.addEventListener('click', () => downloadSymbols('ma_stack', 'ma_stack')); if (downloadAplusButton) downloadAplusButton.addEventListener('click', () => downloadSymbols('a_plus_flags', 'a_plus_flags')); window.addEventListener('resize', onViewportChange, { passive: true }); render(); showPanel(panelViews[location.hash] ? location.hash : '#thematic-title'); }
</script>
</body>
</html>'''
    rendered = template.replace("__DATA__", payload).replace("__QUOTES__", quotes_payload)
    dashboard.write_text(rendered, encoding="utf-8")
    pages_entrypoint.write_text(rendered, encoding="utf-8")
    return dashboard
