import { useEffect, useMemo, useState } from 'react'
import { ComposedChart, Area, Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { SectionCard, ChartBox, ChartTooltip, Empty } from './ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { fmtDateLong, fmtNum } from '../lib/format'

// Stacked bottom to top: steady baseload first, weather-driven sources last.
const SOURCES = [
  { key: 'nuclear', label: 'Nuclear', color: '#059669' },
  { key: 'thermal', label: 'Coal and lignite', color: '#64748b' },
  { key: 'gas', label: 'Gas', color: '#f43f5e' },
  { key: 'hydro', label: 'Hydro', color: '#8b5cf6' },
  { key: 'wind', label: 'Wind', color: '#0284c7' },
  { key: 'solar', label: 'Solar', color: '#d97706' },
  { key: 'others', label: 'Others', color: '#475569' },
]

// One file per month (public/data/days/YYYY-MM.json), fetched when first
// viewed and kept for the visit.
const cache = new Map()
function loadMonth(month) {
  if (!cache.has(month)) {
    const p = fetch(`/data/days/${month}.json`).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    })
    p.catch(() => cache.delete(month))
    cache.set(month, p)
  }
  return cache.get(month)
}

const kTick = (v) => Math.round(v / 1000) + 'k'

function shiftDay(date, n) {
  const d = new Date(date + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export default function DayView({ index }) {
  const [date, setDate] = useState(index.last)
  const [month, setMonth] = useState(null)
  const [error, setError] = useState(null)
  const want = date.slice(0, 7)

  useEffect(() => {
    let alive = true
    setError(null)
    loadMonth(want)
      .then((m) => alive && setMonth({ id: want, ...m }))
      .catch((e) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [want])

  const day = month && month.id === want ? month.days[date] : undefined
  const rows = useMemo(() => {
    if (!day) return []
    return month.slots.map((t, i) => {
      const r = { t }
      for (const s of SOURCES) r[s.label] = day[s.key][i]
      r.Demand = day.demand[i]
      r.Frequency = day.freq[i]
      return r
    })
  }, [day, month])

  const stats = useMemo(() => {
    if (!day) return null
    const valid = (a) => a.filter((v) => v !== null)
    const dem = valid(day.demand)
    const freq = valid(day.freq)
    const peak = Math.max(...dem)
    const peakAt = month.slots[day.demand.indexOf(peak)]
    const solarMax = Math.max(...valid(day.solar))
    return { peak, peakAt, min: Math.min(...dem), solarMax, fLo: Math.min(...freq), fHi: Math.max(...freq) }
  }, [day, month])

  const step = (n) => {
    let d = shiftDay(date, n)
    if (d < index.first) d = index.first
    if (d > index.last) d = index.last
    setDate(d)
  }

  const btn = 'rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-sky-400/40 disabled:opacity-30'
  return (
    <SectionCard
      title="A day on the grid"
      subtitle="Every 15 minutes of any day since November 2024, from NLDC's SCADA: what each source generated, how demand moved, and how far frequency drifted from 50 Hz."
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button type="button" className={btn} onClick={() => step(-1)} disabled={date <= index.first} aria-label="Previous day">
          Previous
        </button>
        <input
          type="date"
          value={date}
          min={index.first}
          max={index.last}
          onChange={(e) => e.target.value && setDate(e.target.value)}
          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-200 outline-none [color-scheme:dark] focus:border-sky-400/40"
          aria-label="Day to show"
        />
        <button type="button" className={btn} onClick={() => step(1)} disabled={date >= index.last} aria-label="Next day">
          Next
        </button>
        <span className="ml-1 text-xs text-slate-500">{fmtDateLong(date)}</span>
      </div>

      {error && <Empty>Couldn't load this month ({error}).</Empty>}
      {!error && month?.id === want && !day && <Empty>No SCADA data for this day (the report was missing or too broken to use).</Empty>}
      {!error && !day && month?.id !== want && <div className="skeleton h-80 rounded-2xl" />}

      {day && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
            {[
              ['Peak demand', `${fmtNum(stats.peak)} MW at ${stats.peakAt}`],
              ['Lowest demand', `${fmtNum(stats.min)} MW`],
              ['Solar at its highest', `${fmtNum(stats.solarMax)} MW`],
              ['Frequency range', `${stats.fLo.toFixed(2)} to ${stats.fHi.toFixed(2)} Hz`],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl border border-white/8 bg-black/20 px-3 py-2">
                <div className="text-[11px] uppercase tracking-wider text-slate-500">{k}</div>
                <div className="mt-0.5 font-medium tabular-nums text-slate-200">{v}</div>
              </div>
            ))}
          </div>

          <ChartBox title="Generation by source and demand (MW)">
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="t" {...AXIS} interval={11} />
                  <YAxis {...AXIS} tickFormatter={kTick} width={44} />
                  <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : fmtNum(v) + ' MW')} />} />
                  <Legend {...LEGEND} />
                  {SOURCES.map((s) => (
                    <Area key={s.key} type="monotone" dataKey={s.label} stackId="g" stroke={s.color} fill={s.color} fillOpacity={0.6} strokeWidth={0.5} isAnimationActive={false} />
                  ))}
                  <Line type="monotone" dataKey="Demand" stroke="#f8fafc" strokeWidth={2} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </ChartBox>

          <ChartBox className="mt-4" title="Frequency (Hz)" note="Normal band 49.9 to 50.05 Hz">
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="t" {...AXIS} interval={11} />
                  <YAxis {...AXIS} domain={[49.8, 50.2]} width={44} tickFormatter={(v) => v.toFixed(1)} />
                  <ReferenceLine y={49.9} stroke="rgba(251,113,133,0.5)" strokeDasharray="4 4" />
                  <ReferenceLine y={50.05} stroke="rgba(56,189,248,0.5)" strokeDasharray="4 4" />
                  <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : v.toFixed(2) + ' Hz')} />} />
                  <Line type="monotone" dataKey="Frequency" stroke="#fb7185" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </ChartBox>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            Generation runs a few percent above demand met; the gap is mostly transmission losses and power used inside the plants, with a small part traded with neighbouring countries. Frequency drops when load runs ahead of generation and rises when it falls behind.
          </p>
        </>
      )}
    </SectionCard>
  )
}
