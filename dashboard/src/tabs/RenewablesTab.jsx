import { useMemo, useState } from 'react'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush,
} from 'recharts'
import { SectionCard, StatCard, StatGrid, ChartBox, Select, Empty, ChartTooltip } from '../components/ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtMonth, fmtNum, fmtPct, fmtMW, fmtDateLong, REGION_NAMES } from '../lib/format'
import { SOURCE_COLORS, CAT } from '../lib/colors'

const kTick = (v) => (Math.abs(v) >= 1000 ? Math.round(v / 1000) + 'k' : v)

function DuckCurve({ duck }) {
  const latest = duck.months[duck.months.length - 1]
  const [month, setMonth] = useState(latest)
  const [y, m] = month.split('-')
  const prevKey = `${Number(y) - 1}-${m}`
  const prev = duck.profiles[prevKey]

  const rows = useMemo(() => {
    const p = duck.profiles[month]
    return duck.slots.map((t, i) => {
      const net = p.demand[i] === null ? null : p.demand[i] - (p.solar[i] || 0) - (p.wind[i] || 0)
      const r = { time: t, Demand: p.demand[i], 'Net demand': net, Solar: p.solar[i] }
      if (prev && prev.demand[i] !== null) {
        r[`Net demand, ${fmtMonth(prevKey)}`] = prev.demand[i] - (prev.solar[i] || 0) - (prev.wind[i] || 0)
      }
      return r
    })
  }, [duck, month, prev, prevKey])

  const p = duck.profiles[month]
  const net = rows.map((r) => r['Net demand']).filter((v) => v !== null)
  const peakSolar = Math.max(...p.solar.filter((v) => v !== null))
  const belly = Math.min(...net)
  const neck = Math.max(...net)
  const bellyIdx = rows.findIndex((r) => r['Net demand'] === belly)
  const neckIdx = rows.findIndex((r) => r['Net demand'] === neck)

  return (
    <SectionCard
      title="The duck curve"
      subtitle="Average 15-minute profile for a month, from live SCADA (Nov 2024 on). Net demand is what the rest of the fleet must cover once solar and wind are taken off: it sags at midday and climbs steeply into the evening peak."
      accent="amber"
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select
          id="duck-month"
          label="Month"
          value={month}
          onChange={setMonth}
          options={[...duck.months].reverse().map((mm) => ({ value: mm, label: fmtMonth(mm) + (mm === latest ? ' (month to date)' : '') }))}
        />
      </div>
      <StatGrid>
        <StatCard value={fmtMW(peakSolar)} label="Avg. solar at its peak slot" />
        <StatCard value={fmtMW(belly)} label="Net demand, midday low" sub={bellyIdx >= 0 ? `at ${rows[bellyIdx].time}` : null} />
        <StatCard value={fmtMW(neck)} label="Net demand, evening high" sub={neckIdx >= 0 ? `at ${rows[neckIdx].time}` : null} />
        <StatCard value={fmtMW(neck - belly)} label="Swing the fleet must follow" tone="warning" />
      </StatGrid>
      <ChartBox className="mt-5" title={`Average day, ${fmtMonth(month)} (MW)`} note={prev ? `dashed: same month a year earlier` : null}>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="time" {...AXIS} interval={11} />
              <YAxis {...AXIS} tickFormatter={kTick} width={44} />
              <Tooltip content={<ChartTooltip formatter={(v) => fmtMW(v)} />} />
              <Legend {...LEGEND} />
              <Line type="monotone" dataKey="Demand" stroke="#94a3b8" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="Net demand" stroke="#38bdf8" strokeWidth={2.5} dot={false} isAnimationActive={false} />
              {prev && (
                <Line
                  type="monotone"
                  dataKey={`Net demand, ${fmtMonth(prevKey)}`}
                  stroke="#38bdf8"
                  strokeOpacity={0.55}
                  strokeDasharray="5 4"
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              )}
              <Line type="monotone" dataKey="Solar" stroke={SOURCE_COLORS.solar} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ChartBox>
    </SectionCard>
  )
}

export default function RenewablesTab({ data }) {
  const monthly = useMemo(() => zipColumns(data.monthly).map((r) => ({ ...r, label: fmtMonth(r.month) })), [data.monthly])
  const lastFull = monthly.length > 1 ? monthly[monthly.length - 2] : null
  const yearly = data.yearly.map((r) => ({
    year: r.year + (r.days < 330 && r.year === data.yearly[data.yearly.length - 1].year ? ' (YTD)' : ''),
    Solar: r.solar / r.days,
    Wind: r.wind / r.days,
  }))
  const first = data.yearly[0]
  const lastY = data.yearly[data.yearly.length - 1]
  const solarMultiple = first && lastY ? lastY.solar / lastY.days / (first.solar / first.days) : null
  const rec = data.records

  return (
    <>
      <SectionCard title="Renewables at a glance" subtitle="Solar, wind and hydro from the NLDC daily reports, 2019 to date." accent="amber">
        <StatGrid>
          <StatCard value={lastFull ? fmtPct(lastFull.resShare) : 'N/A'} label="RES share, last full month" sub={lastFull ? fmtMonth(lastFull.month) : null} tone="good" />
          <StatCard value={solarMultiple ? solarMultiple.toFixed(1) + 'x' : 'N/A'} label={`Solar per day, ${lastY.year} vs ${first.year}`} />
          <StatCard value={fmtNum(rec.maxSolarDay.value, 0) + ' MU'} label="Record solar day" sub={fmtDateLong(rec.maxSolarDay.date)} />
          <StatCard value={fmtMW(rec.maxSolarSlot.value)} label="Record solar, one 15-min slot" sub={`${fmtDateLong(rec.maxSolarSlot.date)}, ${rec.maxSolarSlot.time}`} />
        </StatGrid>
      </SectionCard>

      <SectionCard title="Generation from renewables and hydro" subtitle="Monthly average energy per day. Solar passed wind in 2020 and has pulled away since; wind and hydro peak with the monsoon." accent="amber">
        <ChartBox title="MU per day, monthly average" note="Drag the strip below to zoom">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={monthly} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(monthly.length / 9))} />
                <YAxis {...AXIS} width={44} />
                <Tooltip content={<ChartTooltip formatter={(v) => fmtNum(v, 1) + ' MU/day'} />} />
                <Legend {...LEGEND} />
                <Area type="monotone" dataKey="solar" name="Solar" stackId="g" stroke={SOURCE_COLORS.solar} fill={SOURCE_COLORS.solar} fillOpacity={0.5} strokeWidth={1.5} isAnimationActive={false} />
                <Area type="monotone" dataKey="wind" name="Wind" stackId="g" stroke={SOURCE_COLORS.wind} fill={SOURCE_COLORS.wind} fillOpacity={0.5} strokeWidth={1.5} isAnimationActive={false} />
                <Area type="monotone" dataKey="hydro" name="Hydro" stackId="g" stroke={SOURCE_COLORS.hydro} fill={SOURCE_COLORS.hydro} fillOpacity={0.5} strokeWidth={1.5} isAnimationActive={false} />
                <Brush dataKey="label" height={22} travellerWidth={8} stroke="#fbbf24" fill="rgba(251,191,36,0.05)" tickFormatter={() => ''} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartBox>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <ChartBox title="Share of generation (%), monthly">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={monthly} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(monthly.length / 5))} />
                  <YAxis {...AXIS} tickFormatter={(v) => v + '%'} width={40} />
                  <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : v.toFixed(1) + '%')} />} />
                  <Legend {...LEGEND} />
                  <Line type="monotone" dataKey="nonFossilShare" name="Non-fossil (RES + hydro + nuclear)" stroke={CAT[3]} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="resShare" name="RES (solar, wind, other renewables)" stroke={CAT[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </ChartBox>
          <ChartBox title="Average MU per day, by year">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={yearly} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="year" {...AXIS} tick={{ ...AXIS.tick, fontSize: 10 }} />
                  <YAxis {...AXIS} width={40} />
                  <Tooltip content={<ChartTooltip formatter={(v) => fmtNum(v, 0) + ' MU/day'} />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                  <Legend {...LEGEND} />
                  <Bar dataKey="Solar" fill={SOURCE_COLORS.solar} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="Wind" fill={SOURCE_COLORS.wind} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartBox>
        </div>

        <ChartBox className="mt-4" title="Where it comes from: last 365 days (MU)">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.regional.map((r) => ({ region: REGION_NAMES[r.region], Solar: r.solar, Wind: r.wind }))}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
              >
                <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
                <XAxis type="number" {...AXIS} tickFormatter={kTick} />
                <YAxis type="category" dataKey="region" {...AXIS} tick={{ fill: '#94a3b8', fontSize: 11 }} width={96} />
                <Tooltip content={<ChartTooltip formatter={(v) => fmtNum(v, 0) + ' MU'} />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Legend {...LEGEND} />
                <Bar dataKey="Solar" stackId="r" fill={SOURCE_COLORS.solar} stroke="#0d1016" strokeWidth={1} isAnimationActive={false} />
                <Bar dataKey="Wind" stackId="r" fill={SOURCE_COLORS.wind} stroke="#0d1016" strokeWidth={1} radius={[0, 4, 4, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartBox>
      </SectionCard>

      {data.duck?.months?.length ? <DuckCurve duck={data.duck} /> : <Empty>No SCADA profile data.</Empty>}
    </>
  )
}
