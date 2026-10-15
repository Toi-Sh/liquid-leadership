// shadcn/ui chart pattern: ChartContainer sets --color-<key>, Recharts draws the series.
// https://ui.shadcn.com/docs/components/chart
import { createRoot } from "react-dom/client"
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts"

function Tip({ active, payload, label, yFormat }) {
  if (!active || !payload || !payload.length) return null
  const rows = payload.filter(item => item && item.value != null && item.value !== "")
  if (!rows.length) return null
  return (
    <div className="shadcn-tip">
      {label ? <div className="shadcn-tip__label">{label}</div> : null}
      {rows.map(item => (
        <div className="shadcn-tip__row" key={item.dataKey}>
          <span className="shadcn-tip__swatch" style={{ background: item.color || item.fill }} />
          <span className="shadcn-tip__name">{item.name}</span>
          <span className="shadcn-tip__value">{formatTip(item.value, yFormat)}</span>
        </div>
      ))}
    </div>
  )
}

function formatTip(value, yFormat) {
  const number = Number(value)
  if (!Number.isFinite(number)) return ""
  if (typeof yFormat === "function") return yFormat(number)
  return String(number)
}

function ChartView({ type, data, xKey, series, yFormat, spark, tooltip, guides, domain, decimals }) {
  if (!data || !data.length) return <p className="muted">No print for this chart.</p>
  const style = {}
  series.forEach(item => {
    style["--color-" + item.key] = item.color
  })
  const Chart = type === "bar" ? BarChart : type === "line" ? LineChart : AreaChart
  const margin = spark
    ? { top: 2, right: 0, left: 0, bottom: 2 }
    : { top: 16, right: 12, left: 4, bottom: 0 }
  const yDomain = domain || ["auto", "auto"]
  return (
    <div className={spark ? "shadcn-chart is-spark" : "shadcn-chart"} style={style} data-slot="chart">
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={data} margin={margin} accessibilityLayer>
          {spark ? null : <CartesianGrid vertical={false} stroke="var(--color-grid)" />}
          <XAxis
            dataKey={xKey}
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={28}
            hide={Boolean(spark)}
            tick={{ fontSize: 12, fill: "var(--color-muted)" }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            width={spark ? 0 : 56}
            hide={Boolean(spark)}
            domain={yDomain}
            allowDecimals={decimals !== false}
            tickFormatter={value => formatTip(value, yFormat)}
            tick={{ fontSize: 12, fill: "var(--color-muted)" }}
          />
          {(guides || []).map(level => (
            <ReferenceLine key={level} y={level} stroke="var(--color-rule-2)" strokeDasharray="3 3" />
          ))}
          {tooltip === false ? null : (
            <Tooltip
              wrapperStyle={{ zIndex: 30, outline: "none" }}
              cursor={type === "bar" ? { fill: "var(--color-paper-3)" } : { stroke: "var(--color-rule)" }}
              content={<Tip yFormat={yFormat} />}
            />
          )}
          {type === "area" && series.map(item => (
            <Area
              key={item.key}
              dataKey={item.key}
              name={item.label}
              type="natural"
              fill={"var(--color-" + item.key + ")"}
              fillOpacity={series.length === 1 ? 0.4 : 0}
              stroke={"var(--color-" + item.key + ")"}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
            />
          ))}
          {type === "line" && series.map(item => (
            <Line
              key={item.key}
              dataKey={item.key}
              name={item.label}
              type="natural"
              stroke={"var(--color-" + item.key + ")"}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
              isAnimationActive={false}
            />
          ))}
          {type === "bar" && series.map(item => (
            <Bar
              key={item.key}
              dataKey={item.key}
              name={item.label}
              fill={"var(--color-" + item.key + ")"}
              radius={spark ? 2 : 4}
              isAnimationActive={false}
            >
              {item.signed
                ? data.map((row, index) => (
                  <Cell
                    key={index}
                    fill={Number(row[item.key]) >= 0 ? "var(--color-up)" : "var(--color-down)"}
                  />
                ))
                : null}
            </Bar>
          ))}
        </Chart>
      </ResponsiveContainer>
    </div>
  )
}

export function mount(host, spec) {
  if (!host || !spec) return
  host.classList.add("shadcn-host")
  if (spec.height != null) host.style.height = typeof spec.height === "number" ? spec.height + "px" : spec.height
  if (spec.series && spec.series.length === 1 && spec.series[0].label) {
    host.setAttribute("aria-label", spec.series[0].label)
  }
  let root = host.__gbRoot
  if (!root) {
    root = createRoot(host)
    host.__gbRoot = root
  }
  root.render(
    <ChartView
      type={spec.type || "area"}
      data={spec.data || []}
      xKey={spec.xKey || "label"}
      series={spec.series || []}
      yFormat={spec.yFormat}
      spark={Boolean(spec.spark)}
      tooltip={spec.tooltip}
      guides={spec.guides || []}
      domain={spec.domain}
      decimals={spec.decimals}
    />
  )
}

function seriesColor(node) {
  const parent = node.closest(".chart-down, .chart-up, .chart-ink")
  if (parent && parent.classList.contains("chart-down")) return "var(--color-down)"
  if (parent && parent.classList.contains("chart-up")) return "var(--color-up)"
  return "var(--chart-1)"
}

function mountDeclared(host) {
  let spec
  try {
    spec = JSON.parse(host.dataset.chart)
  } catch {
    return
  }
  const values = Array.isArray(spec.values) ? spec.values : []
  const data = values.map((value, index) => ({ label: String(index + 1), v: value })).filter(row => row.v != null)
  const big = Boolean(host.closest(".chart-row")) && !host.closest(".intra")
  mount(host, {
    type: spec.kind === "bar" ? "bar" : "area",
    data,
    xKey: "label",
    series: [{ key: "v", label: spec.label || "Series", color: seriesColor(host), signed: Boolean(spec.signed) }],
    guides: big ? spec.guides || [] : [],
    spark: !big,
    tooltip: true,
    yFormat: autoFormat,
    domain: spec.kind === "bar" ? ["auto", "auto"] : undefined,
  })
}

function autoFormat(value) {
  const magnitude = Math.abs(value)
  if (magnitude >= 100) return value.toFixed(0)
  if (magnitude >= 10) return value.toFixed(1)
  return value.toFixed(2)
}

function monthDay(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "")
  if (!match) return iso || ""
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  return Number(match[3]) + " " + months[Number(match[2]) - 1]
}

function parseCsv(text) {
  const lines = text.trim().split(/\n/)
  if (lines.length < 2) return []
  const header = lines[0].split(",")
  return lines.slice(1).map(line => {
    const cells = line.split(",")
    const row = {}
    header.forEach((key, index) => { row[key] = cells[index] })
    return row
  })
}

function num(row, key) {
  const value = Number(row[key])
  return Number.isFinite(value) ? value : null
}

function swap(svg) {
  const host = document.createElement("div")
  host.className = "shadcn-host"
  svg.replaceWith(host)
  return host
}

function seriesRows(rows, count, pick, dropSentinel) {
  return rows.slice(-count).map(row => {
    const value = pick(row)
    return { label: monthDay(row.date), v: value }
  }).filter(row => row.v != null && !(dropSentinel && row.v >= 99))
}

function mountHistory(root, rows) {
  const grows = [...root.querySelectorAll(".chart-row .grow svg.spark")]
  const specs = [
    { label: "T2108", column: "t2108", guides: [29, 70], digits: 0 },
    { label: "Nasdaq 40", column: "nasdaq", guides: [29, 70], digits: 0 },
  ]
  specs.forEach((item, index) => {
    if (!grows[index]) return
    const host = swap(grows[index])
    mount(host, {
      type: "area",
      data: seriesRows(rows, 126, row => num(row, item.column)),
      xKey: "label",
      series: [{ key: "v", label: item.label, color: "var(--chart-1)" }],
      guides: item.guides,
      spark: false,
      tooltip: true,
      yFormat: value => value.toFixed(item.digits),
    })
  })
  const articles = [...root.querySelectorAll(".rail .cards article")]
  const cards = [
    { kind: "bar", label: "4% up minus down", pick: row => { const up = num(row, "up4"); const down = num(row, "down4"); return up == null || down == null ? null : up - down }, count: 24, signed: true, digits: 0 },
    { kind: "area", label: "5-day ratio", pick: row => num(row, "ratio5"), count: 40, digits: 2, dropSentinel: true },
    { kind: "area", label: "13/34 balance", pick: row => num(row, "balance"), count: 40, digits: 0 },
    { kind: "area", label: "Bull minus bear", pick: row => { const bull = num(row, "bull20"); const bear = num(row, "bear20"); return bull == null || bear == null ? null : bull - bear }, count: 40, digits: 0 },
    { kind: "area", label: "Quarter up minus down", pick: row => { const up = num(row, "up25q"); const down = num(row, "down25q"); return up == null || down == null ? null : up - down }, count: 40, digits: 0 },
    { kind: "area", label: "50% up minus down", pick: row => { const up = num(row, "up50"); const down = num(row, "down50"); return up == null || down == null ? null : up - down }, count: 40, digits: 0 },
  ]
  cards.forEach((item, index) => {
    const svg = articles[index] && articles[index].querySelector("svg.spark")
    if (!svg) return
    const host = swap(svg)
    mount(host, {
      type: item.kind,
      data: seriesRows(rows, item.count, item.pick, item.dropSentinel),
      xKey: "label",
      series: [{ key: "v", label: item.label, color: "var(--chart-1)", signed: Boolean(item.signed) }],
      spark: true,
      tooltip: true,
      yFormat: value => value.toFixed(item.digits),
    })
  })
}

function mountGeometry(svg) {
  const polyline = svg.querySelector("polyline")
  const rects = [...svg.querySelectorAll("rect")]
  const color = seriesColor(svg)
  const host = swap(svg)
  if (polyline) {
    const box = svg.viewBox && svg.viewBox.baseVal
    const height = box && box.height ? box.height : 40
    const points = polyline.getAttribute("points").trim().split(/\s+/).map((pair, index) => {
      const y = Number(pair.split(",")[1])
      return { label: String(index + 1), v: height - y }
    })
    mount(host, {
      type: "area",
      data: points,
      xKey: "label",
      series: [{ key: "v", label: "Path", color }],
      spark: true,
      tooltip: false,
    })
    return
  }
  if (rects.length) {
    const data = rects.map((rect, index) => {
      const magnitude = Number(rect.getAttribute("height")) || 0
      const up = rect.classList.contains("bar-up")
      return { label: String(index + 1), v: up ? magnitude : -magnitude }
    })
    mount(host, {
      type: "bar",
      data,
      xKey: "label",
      series: [{ key: "v", label: "Breadth", color: "var(--color-up)", signed: true }],
      spark: true,
      tooltip: false,
    })
  }
}

export function upgradeRegime(root) {
  const scope = root || document
  scope.querySelectorAll("[data-chart]").forEach(mountDeclared)
  const sparks = [...scope.querySelectorAll("svg.spark")]
  if (!sparks.length) return
  fetch("outputs/regime_history.csv")
    .then(response => response.ok ? response.text() : "")
    .then(text => {
      const rows = text ? parseCsv(text) : []
      if (rows.length) mountHistory(scope, rows)
      scope.querySelectorAll("svg.spark").forEach(mountGeometry)
    })
    .catch(() => {
      scope.querySelectorAll("svg.spark").forEach(mountGeometry)
    })
}
