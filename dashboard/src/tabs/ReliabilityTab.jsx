import { useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush,
} from 'recharts'
import { SectionCard, StatCard, StatGrid, ChartBox, ChartTooltip } from '../components/ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtMonth, fmtNum, fmtPct, fmtMW, fmtDateShort, fmtDateLong, REGION_NAMES } from '../lib/format'
import { REGION_COLORS, CAT } from '../lib/colors'

const REGIONS = ['NR', 'WR', 'SR', 'ER', 'NER']
const kTick = (v) => (Math.abs(v) >= 1000 ? Math.round(v / 1000) + 'k' : v)

function monthlyBands(daily) {
  const by = new Map()
  for (const r of daily) {
    if (r.inBand === null) continue
    const m = r.date.slice(0, 7)
    if (!by.has(m)) by.set(m, { n: 0, below: 0, inBand: 0, above: 0 })
    const a = by.get(m)
    a.n += 1
    a.below += r.below || 0
    a.inBand += r.inBand || 0
    a.above += r.above || 0
  }
  return [...by.entries()].map(([m, a]) => ({
    label: fmtMonth(m),
    'Below 49.9 Hz': a.below / a.n,
    'In band (49.9 to 50.05 Hz)': a.inBand / a.n,
    'Above 50.05 Hz': a.above / a.n,
  }))
}

function RegionBars({ title, cols, unit, digits, height = 'h-72' }) {
  const rows = useMemo(
    () => zipColumns(cols).map((r) => ({ ...Object.fromEntries(REGIONS.map((k) => [REGION_NAMES[k], r[k]])), label: fmtMonth(r.month) })),
    [cols],
  )
  return (
    <ChartBox title={title}>
      <div className={height}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(rows.length / 9))} />
            <YAxis {...AXIS} tickFormatter={kTick} width={44} />
            <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : `${fmtNum(v, digits)} ${unit}`)} />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Legend {...LEGEND} />
            {REGIONS.map((k) => (
              <Bar key={k} dataKey={REGION_NAMES[k]} stackId="r" fill={REGION_COLORS[k]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartBox>
  )
}

export default function ReliabilityTab({ data }) {
  const daily = useMemo(() => zipColumns(data.daily), [data.daily])
  const bands = useMemo(() => monthlyBands(daily), [daily])
  const latest = daily[daily.length - 1]
  const fviRows = useMemo(() => daily.filter((r) => r.fvi !== null).map((r) => ({ date: r.date, FVI: r.fvi })), [daily])

  return (
    <>
      <SectionCard
        title="Grid reliability"
        subtitle={`How tightly the grid held 50 Hz, how much capacity was out on forced outage, and how much demand went unmet. Latest day: ${fmtDateLong(latest.date)}.`}
        accent="rose"
      >
        <StatGrid>
          <StatCard value={fmtPct(latest.inBand)} label="Time in normal frequency band" sub="49.9 to 50.05 Hz" tone={latest.inBand < 70 ? 'warning' : 'good'} />
          <StatCard value={latest.fvi === null ? 'N/A' : latest.fvi.toFixed(3)} label="Frequency variation index" sub="lower is steadier" />
          <StatCard value={fmtMW(latest.outage)} label="Capacity on forced outage" />
          <StatCard value={`${fmtNum(latest.shortageMu, 2)} MU`} label="Energy not served" tone={latest.shortageMu > 0 ? 'warning' : 'good'} />
        </StatGrid>

        <ChartBox className="mt-5" title="Time spent in each frequency band (% of day, monthly average)">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={bands} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(bands.length / 9))} />
                <YAxis {...AXIS} domain={[0, 100]} tickFormatter={(v) => v + '%'} width={40} />
                <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(1) + '%'} />} />
                <Legend {...LEGEND} />
                <Area type="monotone" dataKey="Below 49.9 Hz" stackId="f" stroke={CAT[4]} fill={CAT[4]} fillOpacity={0.55} isAnimationActive={false} />
                <Area type="monotone" dataKey="In band (49.9 to 50.05 Hz)" stackId="f" stroke={CAT[3]} fill={CAT[3]} fillOpacity={0.45} isAnimationActive={false} />
                <Area type="monotone" dataKey="Above 50.05 Hz" stackId="f" stroke={CAT[0]} fill={CAT[0]} fillOpacity={0.55} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartBox>
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          In every year since 2019, the grid has spent between 1.5 and 3.5 times as long{' '}
          <span className="text-slate-300">above</span> the band (generation running ahead of load) as below it.
        </p>

        <ChartBox className="mt-4" title="Frequency variation index, daily" note="Drag the strip below to zoom">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={fviRows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="date" {...AXIS} tickFormatter={fmtDateShort} minTickGap={40} />
                <YAxis {...AXIS} width={44} />
                <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(3)} />} labelFormatter={fmtDateLong} />
                <Line type="monotone" dataKey="FVI" stroke="#fb7185" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                <Brush dataKey="date" height={22} travellerWidth={8} stroke="#fb7185" fill="rgba(251,113,133,0.05)" tickFormatter={() => ''} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartBox>
      </SectionCard>

      <SectionCard title="Forced outages" subtitle="Generating capacity out of service on forced (unplanned) outage, monthly average of the daily figure, by region." accent="rose">
        <RegionBars title="MW on forced outage, monthly average" cols={data.outageMonthly} unit="MW" digits={0} />
      </SectionCard>

      <SectionCard title="Energy shortage" subtitle="Demand that could not be met, monthly average per day, by region." accent="rose">
        <RegionBars title="Energy not served (MU/day), monthly average" cols={data.shortageMonthly} unit="MU/day" digits={2} />
      </SectionCard>

      <SectionCard title="Year by year" subtitle="Calendar-year averages. Days counts the days with a published report." accent="rose">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-1.5 font-medium">Year</th>
                <th className="py-1.5 text-right font-medium">In band</th>
                <th className="py-1.5 text-right font-medium">Avg. FVI</th>
                <th className="py-1.5 text-right font-medium">Avg. forced outage</th>
                <th className="py-1.5 text-right font-medium">Energy not served</th>
                <th className="py-1.5 text-right font-medium">Days</th>
              </tr>
            </thead>
            <tbody>
              {data.yearly.map((r) => (
                <tr key={r.year} className="border-t border-white/5">
                  <td className="py-1.5 text-slate-300">{r.year}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtPct(r.inBand)}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-300">{r.fvi === null ? 'N/A' : r.fvi.toFixed(3)}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtMW(r.outage)}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtNum(r.shortageMu, 0)} MU</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-500">{r.days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </>
  )
}
