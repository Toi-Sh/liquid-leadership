/* Browser terminal. shortcut: House filings are the full JSON (~12MB) and only the latest 40 are shown — upgrade when a recent-only feed exists. */

const COMMANDS = new Set([
  "CONG", "CONGRESS", "POL", "PROFILE", "TRACK", "UNTRACK", "PORT", "PORTFOLIO", "PRTU",
  "ACCT", "ACCOUNTS", "BAL", "POS", "POSITIONS", "ORD", "ORDERS", "ACTV", "ACTIVITY",
  "BROKER", "BROKERAGE", "BUY", "SELL", "TRADE", "TICKET", "DEMO", "PAPER",
  "LAYOUT", "LAYOUTS", "GRID", "THEME", "OMON", "OPT", "OPTIONS", "CHAIN",
  "HELP", "LINE", "WEI", "NEWS", "GC", "W", "H", "ALL",
]);

const YELLOW = new Set([
  "EQUITY", "EQ", "EQTY", "ETF", "INDEX", "IDX", "CRNCY", "CURNCY", "CURRENCY", "CCY",
  "CRYPTO", "FX", "GOVT", "GOV", "RATES", "CMDTY", "COMDTY", "COMMODITY", "FUT", "US",
]);

const CRYPTO = new Set(["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "AVAX", "LINK", "LTC", "BCH"]);

const ALIAS = {
  SPX: ".SPX", INDU: ".DJI", COMP: ".IXIC", NDX: ".NDX", RTY: ".RUT", VIX: ".VIX",
  USDJPY: "JPY=", CL1: "@CL.1", GC1: "@GC.1",
  SPTSX: ".GSPTSE", IBOV: ".BVSP", MEXBOL: ".MXX",
  UKX: ".FTSE", DAX: ".GDAXI", CAC: ".FCHI", SX5E: ".STOXX50E", SMI: ".SSMI",
  IBEX: ".IBEX", FTSEMIB: ".FTMIB",
  NKY: ".N225", HSI: ".HSI", KOSPI: ".KS11", AS51: ".AXJO", NIFTY: ".NSEI",
};

const PRESET = {
  "1m": "1D", "5m": "5D", "15m": "5D", "30m": "5D", "1H": "5D", "4H": "5D",
  "1D": "6M", "1W": "6M", "1M": "6M",
};

const INTERVALS = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"];
const RANGES = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "ALL"];
const THEMES = [
  ["dark", "Terminal Dark"], ["light", "Terminal Light"], ["bloomberg", "Bloomberg"], ["contrast", "High Contrast"],
  ["solarized-dark", "Solarized Dark"], ["solarized-light", "Solarized Light"], ["nord", "Nord"], ["monokai", "Monokai"],
];
const STYLES = ["Candles", "Bars", "Line", "Area"];
const WATCH = [
  ["SPX", "Index"], ["AAPL", "Equity"], ["NVDA", "Equity"], ["SPY", "Equity"],
  ["BTCUSD", "Currency"], ["ETHUSD", "Currency"], ["EURUSD", "Currency"], ["USDJPY", "Currency"],
  ["US10Y", "Govt"], ["CL1", "Comdty"], ["GC1", "Comdty"],
].map(([symbol, kind]) => ({ symbol, kind }));

const WORLD = [
  ["AMERICAS", [
    ["SPX", "S&P 500 Index"], ["INDU", "Dow Jones Industrial Average"], ["COMP", "NASDAQ Composite"],
    ["NDX", "NASDAQ 100"], ["RTY", "Russell 2000"], ["VIX", "CBOE Volatility Index"],
    ["SPTSX", "S&P/TSX Composite"], ["IBOV", "Bovespa"], ["MEXBOL", "Mexico IPC"],
  ]],
  ["EMEA", [
    ["UKX", "FTSE 100"], ["DAX", "Germany DAX"], ["CAC", "CAC 40"], ["SX5E", "Euro STOXX 50"],
    ["SMI", "Swiss Market"], ["IBEX", "IBEX 35"], ["FTSEMIB", "FTSE MIB"],
  ]],
  ["ASIA/PACIFIC", [
    ["NKY", "Nikkei 225"], ["HSI", "Hang Seng"], ["KOSPI", "KOSPI"], ["AS51", "S&P/ASX 200"], ["NIFTY", "Nifty 50"],
  ]],
];

function intervalOf(token) {
  const raw = String(token);
  const upper = raw.toUpperCase();
  if (raw === "1" || raw === "1m" || raw === "1min") return "1m";
  if (raw === "5" || raw === "5m" || raw === "5min") return "5m";
  if (raw === "15" || raw === "15m" || raw === "15min") return "15m";
  if (raw === "30" || raw === "30m" || raw === "30min") return "30m";
  if (raw === "60" || raw === "1h" || upper === "1H") return "1H";
  if (raw === "240" || raw === "4h" || upper === "4H") return "4H";
  if (upper === "D" || upper === "1D" || upper === "DAY") return "1D";
  if (upper === "1W" || upper === "WEEK") return "1W";
  if (upper === "M" || upper === "1M" || upper === "MO" || upper === "1MO" || upper === "MONTH") return "1M";
  return "";
}

function canonical(token) {
  const text = String(token || "").trim().toUpperCase();
  const slash = text.indexOf("/");
  if (slash > 0) {
    const left = text.slice(0, slash);
    const right = text.slice(slash + 1);
    if (left.length >= 3 && right.length >= 3) return left + right;
    return left + "." + right;
  }
  return text;
}

function parseCommand(raw) {
  const cleaned = String(raw || "").replace(/<GO>/gi, " ").trim();
  if (!cleaned) return { kind: "empty" };
  const parts = cleaned.split(/\s+/);
  if (parts.length === 1 && COMMANDS.has(parts[0].toUpperCase())) {
    return { kind: "unsupported", command: parts[0].toUpperCase() };
  }
  let interval = "";
  let body = parts.slice();
  const tail = intervalOf(body[body.length - 1]);
  if (tail) {
    if (body.length === 1) return { kind: "interval", interval: tail };
    interval = tail;
    body = body.slice(0, -1);
  }
  body = body.filter((part) => !YELLOW.has(part.toUpperCase()));
  if (!body.length) return { kind: "unsupported", command: cleaned.toUpperCase() };
  return { kind: "load", symbol: canonical(body.join("")), interval };
}

function cnbcSymbol(symbol) {
  if (ALIAS[symbol]) return ALIAS[symbol];
  if (/^[A-Z]{3}USD$/.test(symbol) && (CRYPTO.has(symbol.slice(0, 3)) || /^[A-Z]{6}$/.test(symbol))) {
    return symbol.slice(0, 3) + "=";
  }
  if (/^[A-Z]{6}$/.test(symbol) && symbol.endsWith("USD")) return symbol.slice(0, 3) + "=";
  return symbol;
}

function bucketOf(bar, interval) {
  const time = bar.t;
  if (interval === "1W") {
    const date = new Date(time);
    const monday = (date.getUTCDay() + 6) % 7;
    return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() - monday);
  }
  if (interval === "1M") return Date.UTC(new Date(time).getUTCFullYear(), new Date(time).getUTCMonth(), 1);
  const minutes = { "15m": 15, "30m": 30, "1H": 60, "4H": 240 }[interval];
  if (!minutes) return time;
  const size = minutes * 60000;
  return Math.floor(time / size) * size;
}

function resample(bars, interval) {
  if (!bars.length || interval === "1m" || interval === "5m" || interval === "1D") return bars;
  const groups = new Map();
  bars.forEach((bar) => {
    const key = bucketOf(bar, interval);
    const group = groups.get(key);
    if (!group) {
      groups.set(key, { t: key, o: bar.o, h: bar.h, l: bar.l, c: bar.c, v: bar.v });
      return;
    }
    group.h = Math.max(group.h, bar.h);
    group.l = Math.min(group.l, bar.l);
    group.c = bar.c;
    group.v += bar.v;
  });
  return [...groups.values()];
}

function decimals(symbol, price) {
  if (/USD$/.test(symbol) && CRYPTO.has(symbol.slice(0, -3))) return Math.abs(price) >= 100 ? 2 : 4;
  if (/^[A-Z]{6}$/.test(symbol)) return symbol.endsWith("JPY") ? 3 : 4;
  const abs = Math.abs(price);
  if (abs >= 1) return 2;
  if (abs >= 0.01) return 4;
  return 6;
}

function sma(bars, period) {
  const out = bars.map(() => null);
  let sum = 0;
  bars.forEach((bar, index) => {
    sum += bar.c;
    if (index >= period) sum -= bars[index - period].c;
    if (index >= period - 1) out[index] = sum / period;
  });
  return out;
}

function rsi(bars, period) {
  const out = bars.map(() => null);
  if (bars.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = bars[i].c - bars[i - 1].c;
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  gain /= period;
  loss /= period;
  out[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = period + 1; i < bars.length; i++) {
    const diff = bars[i].c - bars[i - 1].c;
    gain = (gain * (period - 1) + Math.max(diff, 0)) / period;
    loss = (loss * (period - 1) + Math.max(-diff, 0)) / period;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

function rangeCount(range, interval, bars) {
  if (!bars.length || range === "ALL" || range === "5Y") return bars.length;
  if (range === "YTD") {
    const start = Date.UTC(new Date().getUTCFullYear(), 0, 1);
    const count = bars.reduce((total, bar) => total + (bar.t >= start ? 1 : 0), 0);
    return count || bars.length;
  }
  const days = { "1D": 1, "5D": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252 }[range] || bars.length;
  if (interval === "1W") return Math.max(1, Math.round(days / 5));
  if (interval === "1M") return Math.max(1, Math.round(days / 21));
  if (interval === "1D") return days;
  const perDay = { "1m": 78, "5m": 78, "15m": 26, "30m": 13, "1H": 7, "4H": 2 }[interval] || 26;
  return perDay * days;
}

function colors() {
  const style = getComputedStyle(document.documentElement);
  const pick = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
  return {
    up: pick("--tr-up", "#30d158"),
    down: pick("--tr-down", "#ff453a"),
    amber: pick("--tr-amber", "#ffb000"),
    cyan: pick("--tr-cyan", "#64d2ff"),
    grid: pick("--tr-grid", "#222224"),
    muted: pick("--tr-muted", "#8e8e93"),
    card: pick("--tr-card", "#0c0c0d"),
    rsi: pick("--tr-rsi", "#ff375f"),
  };
}

function parseMDY(value) {
  const parts = String(value || "").split("/");
  if (parts.length !== 3) return NaN;
  const time = Date.UTC(Number(parts[2]), Number(parts[0]) - 1, Number(parts[1]));
  return Number.isFinite(time) ? time : NaN;
}

function lagDays(filed, traded) {
  const left = parseMDY(filed);
  const right = parseMDY(traded);
  if (!Number.isFinite(left) || !Number.isFinite(right)) return "";
  return Math.round((left - right) / 86400000);
}

function latestTrades(rows, limit) {
  return rows
    .filter((row) => Number.isFinite(parseMDY(row && row.disclosure_date)))
    .sort((a, b) => parseMDY(b.disclosure_date) - parseMDY(a.disclosure_date))
    .slice(0, limit);
}

function focusName(rows) {
  if (rows.some((row) => row.representative === "Nancy Pelosi")) return "Nancy Pelosi";
  const latest = latestTrades(rows, 1)[0];
  return latest ? latest.representative : "";
}

function profileLine(party, district) {
  const state = String(district || "").slice(0, 2);
  const house = state ? "House " + state : "House";
  const seat = district ? " (" + district + ")" : "";
  return [party, house + seat].filter(Boolean).join(" · ");
}

function shortDate(value) {
  const parts = String(value || "").split("/");
  if (parts.length !== 3) return value || "";
  return parts[0] + "/" + parts[1] + "/" + parts[2].slice(-2);
}

function shortType(type) {
  const text = String(type || "");
  if (/purchase|buy/i.test(text)) return "BUY";
  if (/sale|sell/i.test(text)) return "SELL";
  if (/exchange/i.test(text)) return "EXCH";
  return text.slice(0, 6).toUpperCase();
}

function tradeSide(type) {
  const label = shortType(type);
  if (label === "BUY") return 1;
  if (label === "SELL") return -1;
  return 0;
}

function mostTraded(rows) {
  const counts = new Map();
  rows.forEach((row) => {
    const ticker = String(row.ticker || "").toUpperCase();
    if (!/^[A-Z][A-Z.]{0,5}$/.test(ticker)) return;
    counts.set(ticker, (counts.get(ticker) || 0) + 1);
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function scoreTrades(rows, priceAt, latest) {
  const items = [];
  rows.forEach((row, index) => {
    const dir = tradeSide(row.type);
    const ticker = String(row.ticker || "").toUpperCase();
    if (!dir || !/^[A-Z][A-Z.]{0,5}$/.test(ticker)) return;
    const entry = priceAt(ticker, parseMDY(row.transaction_date));
    const now = latest(ticker);
    if (!(entry > 0) || !(now > 0)) return;
    const weight = Number(row.amount_mid) > 0 ? Number(row.amount_mid) : 1;
    items.push({ index, ret: dir * (now / entry - 1), weight });
  });
  const weightSum = items.reduce((sum, item) => sum + item.weight, 0);
  const lags = rows.map((row) => lagDays(row.disclosure_date, row.transaction_date)).filter((days) => days !== "");
  return {
    items,
    weighted: weightSum ? items.reduce((sum, item) => sum + item.ret * item.weight, 0) / weightSum : 0,
    hit: items.length ? items.filter((item) => item.ret > 0).length / items.length : 0,
    avgLag: lags.length ? lags.reduce((sum, days) => sum + days, 0) / lags.length : 0,
  };
}

function cleanText(value) {
  const text = String(value || "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/ {2,}/g, " ").trim();
  return text.split(" : ")[0].replace(/\s+[A-Z](?:\s+[A-Z])+$/, "").trim();
}

function signedPct(value) {
  const pct = value * 100;
  return (pct > 0 ? "+" : "") + pct.toFixed(1) + "%";
}

function closeOn(bars, time) {
  const day = Date.UTC(new Date(time).getUTCFullYear(), new Date(time).getUTCMonth(), new Date(time).getUTCDate());
  let close = NaN;
  bars.forEach((bar) => {
    const barDay = Date.UTC(new Date(bar.t).getUTCFullYear(), new Date(bar.t).getUTCMonth(), new Date(bar.t).getUTCDate());
    if (barDay <= day) close = bar.c;
  });
  return close;
}

function quoteMap(data) {
  const rows = (((data || {}).FormattedQuoteResult || {}).FormattedQuote) || [];
  const map = new Map();
  rows.forEach((row) => {
    if (row && row.code === 0) map.set(row.symbol, row);
  });
  return map;
}

function tone(row) {
  const type = String((row && row.changetype) || "").toUpperCase();
  if (type === "UP") return "up";
  if (type === "DOWN") return "down";
  return "";
}

async function loadBars(symbol, interval) {
  const preset = PRESET[interval] || "6M";
  const url = "https://ts-api.cnbc.com/harmony/app/charts/" + preset + ".json?symbol=" + encodeURIComponent(cnbcSymbol(symbol));
  const response = await fetch(url);
  if (!response.ok) throw new Error("No chart for " + symbol);
  const data = await response.json();
  const rows = (data.barData && data.barData.priceBars) || [];
  const bars = rows.map((row) => ({
    t: Number(row.tradeTimeinMills),
    o: Number(row.open),
    h: Number(row.high),
    l: Number(row.low),
    c: Number(row.close),
    v: Number(row.volume) || 0,
  })).filter((bar) => Number.isFinite(bar.t) && Number.isFinite(bar.c));
  if (!bars.length) throw new Error("No bars for " + symbol);
  return resample(bars, interval);
}

function boot() {
  const canvas = document.getElementById("chart");
  const readout = document.getElementById("readout");
  const form = document.getElementById("command");
  const field = document.getElementById("command-line");
  const status = document.getElementById("status");
  const tab = document.getElementById("tab-symbol");
  const side = document.getElementById("side-quotes");
  const world = document.getElementById("world");
  const wl = document.getElementById("wl-body");
  const ctx = canvas.getContext("2d");
  let symbol = "AAPL";
  let interval = "1D";
  let range = "6M";
  let style = "Candles";
  let bars = [];
  let hover = -1;
  let frame = null;

  function viewOf(series) {
    if (!series.length) return series;
    const count = Math.min(series.length, rangeCount(range, interval, series), 180);
    return series.slice(-count);
  }

  function paint() {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(width * ratio));
    canvas.height = Math.max(1, Math.floor(height * ratio));
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const ink = colors();
    ctx.fillStyle = ink.card;
    ctx.fillRect(0, 0, width, height);
    const view = viewOf(bars);
    const sma20 = viewOf(sma(bars, 20));
    const sma50 = viewOf(sma(bars, 50));
    const rsi14 = viewOf(rsi(bars, 14));
    if (!view.length || width < 20 || height < 20) {
      frame = null;
      return;
    }
    const pad = { l: 8, r: 64, t: 8, b: 18 };
    const volumeH = style === "Line" || style === "Area" ? 0 : Math.max(26, height * 0.11);
    const rsiH = Math.max(32, height * 0.16);
    const plotB = height - pad.b - volumeH - rsiH;
    const lows = view.map((bar) => bar.l);
    const highs = view.map((bar) => bar.h);
    let min = Math.min(...lows);
    let max = Math.max(...highs);
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    const slot = (width - pad.l - pad.r) / view.length;
    const xAt = (index) => pad.l + slot * index + slot / 2;
    const yAt = (price) => pad.t + (max - price) / span * (plotB - pad.t);
    frame = { pad, slot, view };
    ctx.strokeStyle = ink.grid;
    ctx.lineWidth = 1;
    ctx.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillStyle = ink.muted;
    ctx.textAlign = "left";
    [max, (max + min) / 2, min].forEach((price) => {
      const y = yAt(price);
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(width - pad.r, y);
      ctx.stroke();
      ctx.fillText(price.toFixed(decimals(symbol, price)), width - pad.r + 6, y + 4);
    });
    const shownIndex = hover >= 0 ? hover : view.length - 1;
    if (style === "Line" || style === "Area") {
      ctx.beginPath();
      view.forEach((bar, index) => {
        const x = xAt(index);
        const y = yAt(bar.c);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = ink.cyan;
      ctx.lineWidth = 1.4;
      ctx.stroke();
      if (style === "Area") {
        ctx.lineTo(xAt(view.length - 1), plotB);
        ctx.lineTo(xAt(0), plotB);
        ctx.closePath();
        ctx.globalAlpha = 0.16;
        ctx.fillStyle = ink.cyan;
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    } else {
      const maxVol = Math.max(...view.map((bar) => bar.v), 1);
      view.forEach((bar, index) => {
        const x = xAt(index);
        const rising = bar.c >= bar.o;
        const color = rising ? ink.up : ink.down;
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, yAt(bar.h));
        ctx.lineTo(x, yAt(bar.l));
        ctx.stroke();
        if (style === "Candles") {
          const body = Math.max(1, Math.abs(yAt(bar.o) - yAt(bar.c)));
          ctx.fillRect(x - Math.max(1, slot * 0.32), Math.min(yAt(bar.o), yAt(bar.c)), Math.max(2, slot * 0.64), body);
        } else {
          ctx.beginPath();
          ctx.moveTo(x - slot * 0.28, yAt(bar.o));
          ctx.lineTo(x, yAt(bar.o));
          ctx.moveTo(x, yAt(bar.c));
          ctx.lineTo(x + slot * 0.28, yAt(bar.c));
          ctx.stroke();
        }
        const volH = (bar.v / maxVol) * (volumeH - 6);
        ctx.globalAlpha = 0.55;
        ctx.fillRect(x - Math.max(1, slot * 0.32), plotB + volumeH - volH, Math.max(2, slot * 0.64), volH);
        ctx.globalAlpha = 1;
      });
    }
    strokeSeries(sma20, ink.amber, xAt, yAt);
    strokeSeries(sma50, ink.cyan, xAt, yAt);
    const last = view[view.length - 1];
    const tagY = yAt(last.c);
    const tag = last.c.toFixed(decimals(symbol, last.c));
    ctx.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
    const tagW = ctx.measureText(tag).width + 8;
    ctx.fillStyle = last.c >= last.o ? ink.up : ink.down;
    ctx.fillRect(width - pad.r + 2, tagY - 8, tagW, 16);
    ctx.fillStyle = ink.card;
    ctx.fillText(tag, width - pad.r + 6, tagY + 4);
    const rsiTop = plotB + volumeH + 4;
    const rsiBot = height - pad.b;
    ctx.strokeStyle = ink.grid;
    [30, 70].forEach((level) => {
      const y = rsiBot - (level / 100) * (rsiBot - rsiTop);
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(width - pad.r, y);
      ctx.stroke();
    });
    ctx.beginPath();
    let rsiStarted = false;
    rsi14.forEach((value, index) => {
      if (value == null) return;
      const x = xAt(index);
      const y = rsiBot - (value / 100) * (rsiBot - rsiTop);
      if (!rsiStarted) { ctx.moveTo(x, y); rsiStarted = true; }
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = ink.rsi;
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.fillStyle = ink.muted;
    ctx.fillText("RSI 14", pad.l, rsiTop + 10);
    let lastLabel = "";
    ctx.textAlign = "center";
    view.forEach((bar, index) => {
      if (index % Math.ceil(view.length / 6) !== 0) return;
      const label = axisLabel(bar.t, interval);
      if (label === lastLabel) return;
      lastLabel = label;
      ctx.fillText(label, xAt(index), height - 4);
    });
    if (hover >= 0) {
      ctx.strokeStyle = "rgba(236,236,238,0.35)";
      ctx.beginPath();
      ctx.moveTo(xAt(hover), pad.t);
      ctx.lineTo(xAt(hover), height - pad.b);
      ctx.stroke();
    }
    writeReadout(view[shownIndex], view[Math.max(0, shownIndex - 1)]);
  }

  function strokeSeries(values, color, xAt, yAt) {
    ctx.beginPath();
    let started = false;
    values.forEach((value, index) => {
      if (value == null) return;
      const x = xAt(index);
      const y = yAt(value);
      if (!started) { ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.15;
    ctx.stroke();
  }

  function writeReadout(shown, prev) {
    readout.replaceChildren();
    if (!shown) return;
    const change = shown.c - (prev ? prev.c : shown.o);
    const pct = prev && prev.c ? change / prev.c * 100 : 0;
    const digits = decimals(symbol, shown.c);
    const sign = change > 0 ? "+" : "";
    add(symbol + " · " + interval + "  " + barDate(shown.t) + "  ");
    add("O " + shown.o.toFixed(digits) + "  H " + shown.h.toFixed(digits) + "  L " + shown.l.toFixed(digits) + "  C " + shown.c.toFixed(digits) + "  ");
    add(sign + change.toFixed(digits) + " (" + sign + pct.toFixed(2) + "%)  ", change >= 0 ? "up" : "down");
    add("Vol " + compactVol(shown.v));
  }

  function add(text, cls) {
    const span = document.createElement("span");
    if (cls) span.className = cls;
    span.textContent = text;
    readout.append(span);
  }

  function mark() {
    tab.textContent = symbol;
    document.querySelectorAll("[data-symbol]").forEach((node) => {
      node.classList.toggle("on", node.dataset.symbol === symbol);
    });
    document.querySelectorAll("#intervals button").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.interval === interval ? "true" : "false");
    });
    document.querySelectorAll("#styles button").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.style === style ? "true" : "false");
    });
    document.querySelectorAll("#ranges button").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.range === range ? "true" : "false");
    });
  }

  function note() {
    if (!bars.length) return;
    const shown = viewOf(bars).length;
    status.textContent = shown < bars.length ? "Last " + shown + " of " + bars.length + " bars" : bars.length + " bars";
  }

  async function show(nextSymbol, nextInterval) {
    symbol = nextSymbol || symbol;
    interval = nextInterval || interval;
    mark();
    status.textContent = "Loading " + symbol + " " + interval;
    try {
      bars = await loadBars(symbol, interval);
      hover = -1;
      note();
      paint();
    } catch (error) {
      bars = [];
      status.textContent = error.message || "Chart failed";
      paint();
    }
  }

  function quoteButton(item) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quote";
    button.dataset.symbol = item.symbol;
    ["sym", "last", "pct"].forEach((name) => {
      const span = document.createElement("span");
      span.className = name;
      span.textContent = name === "sym" ? item.symbol : "—";
      button.append(span);
    });
    button.addEventListener("click", () => show(item.symbol, interval));
    return button;
  }

  function applyQuote(node, row) {
    const last = node.querySelector(".last");
    const pct = node.querySelector(".pct");
    const change = node.querySelector(".chg");
    if (last) last.textContent = row && row.last ? row.last : "—";
    if (change) {
      change.textContent = row && row.change ? row.change : "—";
      change.className = "chg num " + (row ? tone(row) : "");
    }
    if (pct) {
      pct.textContent = row && row.change_pct ? row.change_pct : "—";
      pct.className = (node.classList.contains("quote") ? "pct " : "num ") + (row ? tone(row) : "");
    }
  }

  WATCH.forEach((item) => side.append(quoteButton(item)));
  WATCH.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.symbol = item.symbol;
    const name = document.createElement("td");
    name.className = "name";
    const ticker = document.createElement("b");
    ticker.textContent = item.symbol;
    const kind = document.createElement("span");
    kind.className = "kind";
    kind.textContent = " " + item.kind;
    name.append(ticker, kind);
    const last = document.createElement("td");
    last.className = "last num";
    last.textContent = "—";
    const change = document.createElement("td");
    change.className = "chg num";
    change.textContent = "—";
    const pct = document.createElement("td");
    pct.className = "pct num";
    pct.textContent = "—";
    row.append(name, last, change, pct);
    row.addEventListener("click", () => show(item.symbol, interval));
    wl.append(row);
  });
  WORLD.forEach(([region, rows]) => {
    const heading = document.createElement("h3");
    heading.className = "region";
    heading.textContent = region;
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const labels = ["", "", "Last", "Chg", "%"];
    const headRow = document.createElement("tr");
    labels.forEach((label, index) => {
      const cell = document.createElement("th");
      cell.textContent = label;
      if (index > 1) cell.className = "num";
      headRow.append(cell);
    });
    head.append(headRow);
    const body = document.createElement("tbody");
    rows.forEach(([ticker, name]) => {
      const row = document.createElement("tr");
      row.dataset.symbol = ticker;
      const security = document.createElement("td");
      security.className = "name";
      const strong = document.createElement("b");
      strong.textContent = ticker;
      const label = document.createElement("span");
      label.textContent = " " + name;
      security.append(strong, label);
      const spark = document.createElement("td");
      spark.className = "spark";
      const last = document.createElement("td");
      last.className = "last num";
      last.textContent = "—";
      const change = document.createElement("td");
      change.className = "chg num";
      change.textContent = "—";
      const pct = document.createElement("td");
      pct.className = "pct num";
      pct.textContent = "—";
      row.append(security, spark, last, change, pct);
      row.addEventListener("click", () => show(ticker, interval));
      body.append(row);
    });
    table.append(head, body);
    world.append(heading, table);
  });

  const ranges = document.getElementById("ranges");
  RANGES.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.range = name;
    button.textContent = name;
    button.addEventListener("click", () => { range = name; mark(); note(); paint(); });
    ranges.append(button);
  });
  const gallery = document.getElementById("theme-gallery");
  THEMES.forEach(([name, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "swatch";
    button.dataset.theme = name;
    const mini = document.createElement("span");
    mini.className = "mini";
    for (let i = 0; i < 4; i++) mini.append(document.createElement("i"));
    const caption = document.createElement("em");
    caption.textContent = label;
    button.append(mini, caption);
    button.addEventListener("click", () => applyTheme(name));
    gallery.append(button);
  });
  function applyTheme(name) {
    document.documentElement.dataset.theme = name;
    try { localStorage.setItem("terminal-theme", name); } catch (error) { /* private mode */ }
    document.querySelectorAll(".swatch").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.theme === name ? "true" : "false");
    });
    paint();
  }
  try {
    const saved = localStorage.getItem("terminal-theme");
    if (saved && THEMES.some(([name]) => name === saved)) document.documentElement.dataset.theme = saved;
  } catch (error) { /* private mode */ }
  applyTheme(document.documentElement.dataset.theme || "dark");
  const intervals = document.getElementById("intervals");
  INTERVALS.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.interval = name;
    button.textContent = name;
    button.addEventListener("click", () => show(symbol, name));
    intervals.append(button);
  });
  const styles = document.getElementById("styles");
  STYLES.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.style = name;
    button.textContent = name;
    button.addEventListener("click", () => { style = name; mark(); paint(); });
    styles.append(button);
  });
  function toggleSettings() {
    const themes = document.getElementById("theme-card");
    const open = themes.hidden;
    themes.hidden = !open;
    document.getElementById("trade-card").hidden = open;
    document.querySelector('[data-go="THEME"]').setAttribute("aria-pressed", open ? "true" : "false");
    if (open) themes.focus();
  }
  function renderPolitician(rows, roster) {
    const name = focusName(rows);
    const sheet = latestTrades(rows.filter((row) => row.representative === name), 40);
    const district = (sheet[0] && sheet[0].district) || "";
    const party = (roster.get(name) || {}).party || "";
    document.getElementById("pol-name").textContent = name || "No filings";
    const head = document.getElementById("pol-head");
    head.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = name;
    const who = document.createElement("p");
    who.textContent = profileLine(party, district);
    const stats = document.createElement("p");
    stats.id = "pol-stats";
    const traded = document.createElement("p");
    traded.className = "tickers";
    traded.textContent = "Most traded: " + mostTraded(sheet).map(([ticker, count]) => ticker + "(" + count + ")").join(" ");
    head.append(title, who, stats, traded);
    const body = document.getElementById("trades");
    body.replaceChildren();
    sheet.forEach((row) => {
      const tr = document.createElement("tr");
      const lag = lagDays(row.disclosure_date, row.transaction_date);
      const kind = shortType(row.type);
      [shortDate(row.disclosure_date), shortDate(row.transaction_date), lag === "" ? "" : lag + "d", kind, String(row.ticker || "").toUpperCase(), cleanText(row.amount), "—", cleanText(row.owner), cleanText(row.asset_description)].forEach((text, index) => {
        const cell = document.createElement("td");
        cell.textContent = text || "";
        if (index === 3) cell.className = kind === "SELL" ? "down" : kind === "BUY" ? "up" : "";
        if (index === 6) { cell.className = "num"; cell.dataset.ret = "1"; }
        if (index === 8) cell.className = "asset";
        tr.append(cell);
      });
      const ticker = String(row.ticker || "").toUpperCase();
      if (/^[A-Z][A-Z.]{0,5}$/.test(ticker)) tr.addEventListener("click", () => show(ticker, interval));
      body.append(tr);
    });
    const pending = scoreTrades(sheet, () => NaN, () => NaN);
    stats.textContent = "Trades " + sheet.length + "  Avg lag " + Math.round(pending.avgLag) + "d";
    const tickers = [...new Set(sheet.map((row) => String(row.ticker || "").toUpperCase()).filter((ticker) => /^[A-Z][A-Z.]{0,5}$/.test(ticker)))];
    Promise.all(tickers.map((ticker) => loadBars(ticker, "1D").then((bars) => [ticker, bars]).catch(() => [ticker, []])))
      .then((books) => {
        const byTicker = new Map(books);
        const scored = scoreTrades(
          sheet,
          (ticker, time) => closeOn(byTicker.get(ticker) || [], time),
          (ticker) => {
            const bars = byTicker.get(ticker) || [];
            return bars.length ? bars[bars.length - 1].c : NaN;
          },
        );
        stats.textContent = "Trades " + sheet.length + "  Scored " + scored.items.length + "  Est. return " + signedPct(scored.weighted) + "  Hit rate " + Math.round(scored.hit * 100) + "%  Avg lag " + Math.round(scored.avgLag) + "d";
        const returns = new Map(scored.items.map((item) => [item.index, item.ret]));
        [...body.rows].forEach((tr, index) => {
          const cell = tr.querySelector("[data-ret]");
          if (!cell || !returns.has(index)) return;
          const ret = returns.get(index);
          cell.textContent = signedPct(ret);
          cell.className = "num " + (ret >= 0 ? "up" : "down");
        });
      })
      .catch(() => {});
  }
  Promise.all([
    fetch("https://raw.githubusercontent.com/TattooedHead/house-stock-watcher-data/main/data/all_transactions.json").then((response) => { if (!response.ok) throw new Error("filings"); return response.json(); }),
    fetch("https://unitedstates.github.io/congress-legislators/legislators-current.json").then((response) => response.ok ? response.json() : []).catch(() => []),
  ]).then(([rows, people]) => {
    const roster = new Map();
    (people || []).forEach((person) => {
      const full = ((person.name || {}).official_full) || "";
      const term = ((person.terms || []).slice(-1)[0]) || {};
      if (full) roster.set(full, { party: term.party || "" });
    });
    renderPolitician(rows, roster);
  }).catch(() => {
    document.getElementById("pol-head").textContent = "Filings did not load";
  });
  document.querySelector(".sidebar").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-go]");
    if (!button) return;
    const go = button.dataset.go;
    if (go === "SECF") { field.focus(); return; }
    if (go === "WEI") { document.getElementById("world-card").focus(); return; }
    if (go === "THEME") { toggleSettings(); return; }
  });

  const quoted = [...WATCH.map((item) => item.symbol), ...WORLD.flatMap((group) => group[1].map((row) => row[0]))];
  const unique = [...new Set(quoted.map(cnbcSymbol))];
  fetch("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=" + encodeURIComponent(unique.join("|")) + "&requestMethod=itv&noform=1&partnerId=2&output=json")
    .then((response) => response.json())
    .then((data) => {
      const map = quoteMap(data);
      document.querySelectorAll("[data-symbol]").forEach((node) => {
        applyQuote(node, map.get(cnbcSymbol(node.dataset.symbol)));
      });
    })
    .catch(() => {});
  WORLD.flatMap((group) => group[1]).forEach(([ticker]) => {
    fetch("https://ts-api.cnbc.com/harmony/app/charts/1M.json?symbol=" + encodeURIComponent(cnbcSymbol(ticker)))
      .then((response) => response.json())
      .then((data) => {
        const rows = (data.barData && data.barData.priceBars) || [];
        const closes = rows.map((row) => Number(row.close)).filter(Number.isFinite).slice(-48);
        const cell = document.querySelector('#world tr[data-symbol="' + ticker + '"] .spark');
        if (cell && closes.length > 1) cell.append(sparkLine(closes));
      })
      .catch(() => {});
  });

  canvas.addEventListener("mousemove", (event) => {
    if (!frame) return;
    const index = Math.floor((event.offsetX - frame.pad.l) / frame.slot);
    hover = Math.max(0, Math.min(frame.view.length - 1, index));
    paint();
  });
  canvas.addEventListener("mouseleave", () => { hover = -1; paint(); });
  window.addEventListener("resize", paint);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const command = parseCommand(field.value);
    field.value = "";
    if (command.kind === "empty") return;
    if (command.kind === "unsupported") {
      if (command.command === "WEI") document.getElementById("world-card").focus();
      else if (command.command === "THEME") toggleSettings();
      else status.textContent = command.command + " is not in this chart";
      return;
    }
    if (command.kind === "interval") show(symbol, command.interval);
    else show(command.symbol, command.interval || "1D");
  });
  document.addEventListener("keydown", (event) => {
    if (event.target === field || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key.length === 1) field.focus();
  });
  mark();
  show(symbol, interval);
}

function axisLabel(time, interval) {
  const date = new Date(time);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  if (interval === "1D" || interval === "1W" || interval === "1M") return months[date.getMonth()];
  return months[date.getMonth()] + " " + date.getDate();
}

function barDate(time) {
  const date = new Date(time);
  const pad = (value) => String(value).padStart(2, "0");
  return pad(date.getMonth() + 1) + "/" + pad(date.getDate()) + "/" + String(date.getFullYear()).slice(2);
}

function compactVol(value) {
  if (value >= 1e9) return (value / 1e9).toFixed(2) + "B";
  if (value >= 1e6) return (value / 1e6).toFixed(2) + "M";
  if (value >= 1e3) return (value / 1e3).toFixed(1) + "K";
  return String(Math.round(value));
}

function sparkLine(closes) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 72 16");
  svg.setAttribute("width", "72");
  svg.setAttribute("height", "16");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  const min = Math.min(...closes);
  const span = Math.max(...closes) - min || 1;
  const d = closes.map((close, index) => {
    const x = (index / (closes.length - 1)) * 72;
    const y = 15 - ((close - min) / span) * 14;
    return (index ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  }).join(" ");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  const ink = colors();
  path.setAttribute("stroke", closes[closes.length - 1] >= closes[0] ? ink.up : ink.down);
  path.setAttribute("stroke-width", "1.2");
  svg.append(path);
  return svg;
}

if (typeof document === "undefined") {
  const assert = require("node:assert");
  assert.deepStrictEqual(parseCommand("AAPL"), { kind: "load", symbol: "AAPL", interval: "" });
  assert.deepStrictEqual(parseCommand("aapl <GO>"), { kind: "load", symbol: "AAPL", interval: "" });
  assert.deepStrictEqual(parseCommand("AAPL US EQUITY 1W"), { kind: "load", symbol: "AAPL", interval: "1W" });
  assert.deepStrictEqual(parseCommand("5"), { kind: "interval", interval: "5m" });
  assert.deepStrictEqual(parseCommand("1m"), { kind: "interval", interval: "1m" });
  assert.deepStrictEqual(parseCommand("1M"), { kind: "interval", interval: "1M" });
  assert.strictEqual(parseCommand("CONG").kind, "unsupported");
  assert.strictEqual(parseCommand("W").kind, "unsupported");
  assert.strictEqual(parseCommand("").kind, "empty");
  assert.strictEqual(cnbcSymbol("AAPL"), "AAPL");
  assert.strictEqual(cnbcSymbol("BTCUSD"), "BTC=");
  assert.strictEqual(cnbcSymbol("EURUSD"), "EUR=");
  assert.strictEqual(cnbcSymbol("SPX"), ".SPX");
  assert.strictEqual(cnbcSymbol("USDJPY"), "JPY=");
  assert.strictEqual(cnbcSymbol("CL1"), "@CL.1");
  assert.strictEqual(canonical("BRK/B"), "BRK.B");
  const weekly = resample([
    { t: Date.UTC(2026, 0, 5), o: 1, h: 2, l: 1, c: 2, v: 1 },
    { t: Date.UTC(2026, 0, 6), o: 2, h: 4, l: 2, c: 3, v: 1 },
    { t: Date.UTC(2026, 0, 12), o: 3, h: 3, l: 1, c: 1, v: 1 },
  ], "1W");
  assert.strictEqual(weekly.length, 2);
  assert.strictEqual(weekly[0].h, 4);
  assert.strictEqual(weekly[0].c, 3);
  const averages = sma([{ c: 1 }, { c: 2 }, { c: 3 }, { c: 4 }], 2);
  assert.strictEqual(averages[0], null);
  assert.strictEqual(averages[1], 1.5);
  assert.strictEqual(averages[3], 3.5);
  const rising = Array.from({ length: 20 }, (_, index) => ({ c: index + 1 }));
  assert.ok(rsi(rising, 14)[19] > 70);
  assert.strictEqual(rangeCount("6M", "1D", Array.from({ length: 300 }, () => ({ t: Date.now() }))), 126);
  assert.strictEqual(rangeCount("ALL", "1D", [{ t: 1 }, { t: 2 }]), 2);
  assert.strictEqual(rangeCount("1D", "5m", Array(1000).fill({ t: 1 })), 78);
  const filings = [
    { disclosure_date: "10/01/2026", transaction_date: "09/01/2026" },
    { disclosure_date: "10/15/2026", transaction_date: "10/09/2026" },
  ];
  assert.strictEqual(latestTrades(filings, 1)[0].disclosure_date, "10/15/2026");
  assert.strictEqual(lagDays("10/15/2026", "10/09/2026"), 6);
  assert.strictEqual(focusName([{ representative: "Nancy Pelosi" }, { representative: "Other" }]), "Nancy Pelosi");
  assert.strictEqual(profileLine("Democrat", "CA11"), "Democrat · House CA (CA11)");
  assert.deepStrictEqual(mostTraded([{ ticker: "AAPL" }, { ticker: "NVDA" }, { ticker: "NVDA" }]), [["NVDA", 2], ["AAPL", 1]]);
  const scored = scoreTrades([
    { type: "Purchase", ticker: "UP", transaction_date: "01/01/2026", disclosure_date: "01/31/2026", amount_mid: 8000 },
    { type: "Sale", ticker: "DOWN", transaction_date: "01/01/2026", disclosure_date: "01/31/2026", amount_mid: 32500 },
    { type: "Purchase", ticker: "NOPE", transaction_date: "01/01/2026", disclosure_date: "01/31/2026", amount_mid: 8000 },
  ], (ticker) => ticker === "NOPE" ? NaN : 100, (ticker) => ticker === "UP" ? 110 : ticker === "DOWN" ? 80 : NaN);
  assert.strictEqual(scored.items.length, 2);
  assert.ok(Math.abs(scored.items[0].ret - 0.1) < 1e-9);
  assert.ok(Math.abs(scored.items[1].ret - 0.2) < 1e-9);
  assert.strictEqual(scored.hit, 1);
  assert.strictEqual(cleanText("Bloom Energy F\u0000 S : New"), "Bloom Energy");
  assert.strictEqual(quoteMap({ FormattedQuoteResult: { FormattedQuote: [{ symbol: "AAPL", code: 0, last: "1" }] } }).get("AAPL").last, "1");
} else {
  boot();
}
