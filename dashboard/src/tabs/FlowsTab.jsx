import { useMemo, useState } from 'react'
import {
  ComposedChart, Line, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ReferenceLine, Brush,
} from 'recharts'
import { SectionCard, StatCard, StatGrid, ChartBox, Pills, Empty, ChartTooltip } from '../components/ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtDateShort, fmtDateLong, fmtMonth, fmtNum, REGION_NAMES } from '../lib/format'
import { COUNTRY_COLORS } from '../lib/colors'

// Sign convention (checked against the parser and live values, e.g. WR->SR
// is a large WR export every day): ir_<a>_<b>_net = import minus export from
// region A's point of view, so a NEGATIVE net means power flowed A -> B.
// Charts below plot -net, so "positive" always reads as "A -> B".
const CORRIDOR_LABEL = (k) => {
  const [a, b] = k.toUpperCase().split('_')
  return { a, b, label: `${a} → ${b}` }
}

const NODES = {
  NR: { x: 200, y: 62 },
  WR: { x: 88, y: 168 },
  SR: { x: 190, y: 272 },
  ER: { x: 300, y: 160 },
  NER: { x: 400, y: 84 },
}

function FlowDiagram({ latest }) {
  const max = Math.max(...latest.items.map((i) => Math.abs(i.net || 0)), 1)
  return (
    <svg viewBox="0 0 480 320" className="h-auto w-full" role="img" aria-label="Net inter-regional flows on the latest day">
      <defs>
        <marker id="flowArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="#38bdf8" />
        </marker>
      </defs>
      {latest.items.map((it) => {
        if (it.net === null) return null
        const { a, b } = CORRIDOR_LABEL(it.key)
        // net < 0: A exports to B.
        const [from, to] = it.net < 0 ? [NODES[a], NODES[b]] : [NODES[b], NODES[a]]
        const dx = to.x - from.x
        const dy = to.y - from.y
        const len = Math.hypot(dx, dy)
        const r = 34
        const x1 = from.x + (dx / len) * r
        const y1 = from.y + (dy / len) * r
        const x2 = to.x - (dx / len) * (r + 4)
        const y2 = to.y - (dy / len) * (r + 4)
        const w = 1.5 + (Math.abs(it.net) / max) * 7
        const mx = (x1 + x2) / 2
        const my = (y1 + y2) / 2
        return (
          <g key={it.key}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#38bdf8" strokeOpacity={0.75} strokeWidth={w} markerEnd="url(#flowArrow)">
              <title>{`${it.net < 0 ? `${a} → ${b}` : `${b} → ${a}`}: ${fmtNum(Math.abs(it.net), 1)} MU net`}</title>
            </line>
            <rect x={mx - 22} y={my - 9} width={44} height={18} rx={5} fill="#0d1016" stroke="rgba(255,255,255,0.1)" />
            <text x={mx} y={my + 4} textAnchor="middle" className="fill-slate-300 text-[10px] tabular-nums">
              {fmtNum(Math.abs(it.net), 0)}
            </text>
          </g>
        )
      })}
      {Object.entries(NODES).map(([k, n]) => (
        <g key={k}>
          <circle cx={n.x} cy={n.y} r={30} fill="#111722" stroke="rgba(56,189,248,0.45)" strokeWidth={1.5} />
          <text x={n.x} y={n.y + 4} textAnchor="middle" className="fill-slate-100 text-[13px] font-semibold">
            {k}
          </text>
          <title>{REGION_NAMES[k]} region</title>
        </g>
      ))}
    </svg>
  )
}

function CorridorTrend({ dailyRows }) {
  const corridors = ['er_nr', 'er_wr', 'er_sr', 'er_ner', 'ner_nr', 'wr_nr', 'wr_sr']
  const [key, setKey] = useState('wr_sr')
  const { label } = CORRIDOR_LABEL(key)
  const data = useMemo(() => {
    const rows = dailyRows.filter((r) => r[key] !== null)
    // 30-day trailing mean of the same flow, to show the trend under the noise.
    const out = []
    let sum = 0
    const win = []
    for (const r of rows) {
      const v = -r[key]
      win.push(v)
      sum += v
      if (win.length > 30) sum -= win.shift()
      out.push({ date: r.date, Daily: v, '30-day mean': win.length >= 15 ? sum / win.length : null })
    }
    return out
  }, [dailyRows, key])

  return (
    <SectionCard
      title="Corridor flow over time"
      subtitle="Daily net energy over each inter-regional corridor since 2023. Above zero means power flowed in the direction named; below zero means it reversed."
      accent="sky"
    >
      <div className="mb-4">
        <Pills options={corridors.map((c) => ({ id: c, label: CORRIDOR_LABEL(c).label }))} value={key} onChange={setKey} tone="sky" />
      </div>
      <ChartBox title={`${label} net flow (MU/day)`} note="Drag the strip below to zoom">
        {data.length ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="date" {...AXIS} tickFormatter={fmtDateShort} minTickGap={40} />
                <YAxis {...AXIS} width={44} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
                <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : fmtNum(v, 1) + ' MU')} />} labelFormatter={fmtDateLong} />
                <Legend {...LEGEND} />
                <Area type="monotone" dataKey="Daily" stroke="#38bdf8" strokeOpacity={0.5} strokeWidth={1} fill="rgba(56,189,248,0.12)" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="30-day mean" stroke="#f8fafc" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Brush dataKey="date" height={22} travellerWidth={8} stroke="#38bdf8" fill="rgba(56,189,248,0.05)" tickFormatter={() => ''} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <Empty>No corridor data.</Empty>
        )}
      </ChartBox>
    </SectionCard>
  )
}

const COUNTRIES = ['bhutan', 'nepal', 'bangladesh', 'myanmar']
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)

function CrossBorder({ xbMonthly, xbLatest }) {
  const rows = useMemo(
    () =>
      zipColumns(xbMonthly).map((r) => {
        const o = { month: fmtMonth(r.month) }
        COUNTRIES.forEach((c) => {
          const imp = r[`import_${c}`]
          const exp = r[`export_${c}`]
          o[cap(c)] = imp === null && exp === null ? null : (imp || 0) - (exp || 0)
        })
        return o
      }),
    [xbMonthly],
  )
  const tot = xbLatest ? xbLatest.items.reduce((a, i) => a + (i.net || 0), 0) : null

  return (
    <SectionCard
      title="Cross-border exchange"
      subtitle="India's trade with Bhutan, Nepal, Bangladesh and Myanmar since July 2023 (when the reports started itemising it). Above zero is a net import into India, below zero a net export."
      accent="sky"
    >
      {xbLatest && (
        <StatGrid>
          {xbLatest.items
            .filter((i) => i.key !== 'myanmar' || i.import || i.export)
            .map((i) => (
              <StatCard
                key={i.key}
                value={`${i.net > 0 ? '+' : ''}${fmtNum(i.net, 1)} MU`}
                label={cap(i.key)}
                sub={i.net > 0 ? 'net import into India' : i.net < 0 ? 'net export from India' : 'balanced'}
              />
            ))}
          <StatCard value={`${tot > 0 ? '+' : ''}${fmtNum(tot, 1)} MU`} label="All countries, net" sub={fmtDateLong(xbLatest.date)} />
        </StatGrid>
      )}
      <ChartBox className="mt-5" title="Monthly net exchange by country (MU/day, monthly average)">
        {rows.length ? (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} stackOffset="sign" margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="month" {...AXIS} interval={Math.max(0, Math.floor(rows.length / 10))} />
                <YAxis {...AXIS} width={40} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.35)" />
                <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : `${v > 0 ? '+' : ''}${fmtNum(v, 2)} MU/day`)} />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Legend {...LEGEND} />
                {COUNTRIES.map((c) => (
                  <Bar key={c} dataKey={cap(c)} stackId="xb" fill={COUNTRY_COLORS[c]} stroke="#0d1016" strokeWidth={1} isAnimationActive={false} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <Empty>No cross-border data.</Empty>
        )}
      </ChartBox>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        Bhutan and Nepal swing with the monsoon: both sell surplus hydro to India from about June to November and buy from
        India in the dry months. Bangladesh buys a steady 17 to 24 MU a day all year.
      </p>
    </SectionCard>
  )
}

export default function FlowsTab({ data }) {
  const dailyRows = useMemo(() => zipColumns(data.daily), [data.daily])
  const ir = data.irLatest

  return (
    <>
      <SectionCard
        title="Inter-regional flows, latest day"
        subtitle={ir ? `Net energy moved between India's five grid regions on ${fmtDateLong(ir.date)}. Arrow width scales with the flow.` : 'No corridor data.'}
        accent="sky"
      >
        {ir ? (
          <div className="grid items-center gap-6 lg:grid-cols-[3fr_2fr]">
            <FlowDiagram latest={ir} />
            <table className="w-full text-xs">
              <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-1.5 font-medium">Corridor</th>
                  <th className="py-1.5 text-right font-medium">A to B</th>
                  <th className="py-1.5 text-right font-medium">B to A</th>
                  <th className="py-1.5 text-right font-medium">Net</th>
                </tr>
              </thead>
              <tbody>
                {ir.items.map((i) => {
                  const { a, b } = CORRIDOR_LABEL(i.key)
                  return (
                    <tr key={i.key} className="border-t border-white/5">
                      <td className="py-1.5 text-slate-300">
                        {a} / {b}
                      </td>
                      <td className="py-1.5 text-right tabular-nums text-slate-400">{fmtNum(i.export, 1)}</td>
                      <td className="py-1.5 text-right tabular-nums text-slate-400">{fmtNum(i.import, 1)}</td>
                      <td className="py-1.5 text-right tabular-nums text-slate-200">
                        {i.net === null ? 'N/A' : `${fmtNum(Math.abs(i.net), 1)} ${i.net < 0 ? `${a}→${b}` : `${b}→${a}`}`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No corridor data.</Empty>
        )}
        <p className="mt-3 text-[11px] text-slate-600">All values in MU (million units = GWh) for the day.</p>
      </SectionCard>
      <CorridorTrend dailyRows={dailyRows} />
      <CrossBorder xbMonthly={data.xbMonthly} xbLatest={data.xbLatest} />
    </>
  )
}
