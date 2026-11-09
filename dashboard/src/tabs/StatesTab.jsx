import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Brush } from 'recharts'
import india from '@svg-maps/india'
import StatePanel from '../components/StatePanel'
import RegionsPanel from '../components/RegionsPanel'
import { SectionCard, ChartBox, Pills, Select, Empty, ChartTooltip } from '../components/ui'
import { AXIS, GRID } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtMonth, fmtNum, fmtMW, REGION_NAMES } from '../lib/format'
import { sequentialRamp, diverging, SEQ_GRADIENT, DIV_GRADIENT, NO_DATA, REGION_COLORS, REGION_LIGHT } from '../lib/colors'

// study3 entity name (as cleaned by build_dashboard_data.py) -> map polygon
// ids in @svg-maps/india. DNH and DD is one merged UT in the data but two
// polygons on the map, so both light up together. Andaman & Nicobar and
// Lakshadweep are not on the national grid and have no rows.
const MAP_IDS = {
  'Andhra Pradesh': ['ap'], 'Arunachal Pradesh': ['ar'], Assam: ['as'], Bihar: ['br'], Chandigarh: ['ch'],
  Chhattisgarh: ['ct'], 'DNH and DD': ['dn', 'dd'], Delhi: ['dl'], Goa: ['ga'], Gujarat: ['gj'], Haryana: ['hr'],
  'Himachal Pradesh': ['hp'], 'J&K and Ladakh': ['jk'], Jharkhand: ['jh'], Karnataka: ['ka'], Kerala: ['kl'],
  'Madhya Pradesh': ['mp'], Maharashtra: ['mh'], Manipur: ['mn'], Meghalaya: ['ml'], Mizoram: ['mz'],
  Nagaland: ['nl'], Odisha: ['or'], Puducherry: ['py'], Punjab: ['pb'], Rajasthan: ['rj'], Sikkim: ['sk'],
  'Tamil Nadu': ['tn'], Telangana: ['tg'], Tripura: ['tr'], 'Uttar Pradesh': ['up'], Uttarakhand: ['ut'],
  'West Bengal': ['wb'],
}

const METRICS = [
  { id: 'energyMu', label: 'Energy, last 365 days', kind: 'log', ramp: 'sky', tone: 'sky', fmt: (v) => fmtNum(v) + ' MU' },
  { id: 'peakMw', label: 'Peak demand, last 365 days', kind: 'log', ramp: 'violet', tone: 'violet', fmt: (v) => fmtMW(v) },
  { id: 'growthPct', label: 'Energy growth vs prior year', kind: 'div', tone: 'rose', fmt: (v) => (v >= 0 ? '+' : '') + v.toFixed(1) + '%' },
  { id: 'shortageMu', label: 'Energy shortage, last 365 days', kind: 'log1p', ramp: 'amber', tone: 'amber', fmt: (v) => fmtNum(v, 1) + ' MU' },
]

const REGIONS = ['NR', 'WR', 'SR', 'ER', 'NER']

// One scale shared by the map and the ranking, so a row's bar is the same
// colour as its state on the map (the ranking doubles as a legend).
function useScale(entities, metric) {
  return useMemo(() => {
    const vals = entities.map((e) => e[metric.id]).filter((v) => v !== null && v !== undefined)
    if (!vals.length) return { color: () => NO_DATA, frac: () => 0, min: null, max: null, gradient: SEQ_GRADIENT }
    if (metric.kind === 'div') {
      const cap = Math.max(...vals.map(Math.abs), 1)
      return { color: (v) => diverging(v / cap), frac: (v) => Math.abs(v) / cap, min: -cap, max: cap, gradient: DIV_GRADIENT }
    }
    const ramp = sequentialRamp(metric.ramp)
    const f = metric.kind === 'log1p' ? (v) => Math.log1p(v) : (v) => Math.log(Math.max(v, 1))
    const lo = f(Math.min(...vals))
    const hi = f(Math.max(...vals))
    const max = Math.max(...vals)
    return {
      color: (v) => ramp.color(hi === lo ? 1 : (f(v) - lo) / (hi - lo)),
      // Bar lengths are linear (true proportions); only the colour is log-scaled.
      frac: (v) => (max ? v / max : 0),
      min: Math.min(...vals),
      max,
      gradient: ramp.gradient,
    }
  }, [entities, metric])
}

function RegionFilter({ value, onChange, counts }) {
  const opts = [{ id: 'all', label: 'All regions' }, ...REGIONS.map((r) => ({ id: r, label: REGION_NAMES[r] }))]
  return (
    <div className="flex flex-wrap gap-2">
      {opts.map((o) => {
        const active = value === o.id
        const color = o.id === 'all' ? '#94a3b8' : REGION_COLORS[o.id]
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.id)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition ${
              active ? 'text-slate-100' : 'border-white/8 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200'
            }`}
            style={active ? { borderColor: color, background: `${color}2e` } : undefined}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: color }} />
            {o.label}
            <span className="tabular-nums text-slate-500">{counts[o.id] || 0}</span>
          </button>
        )
      })}
    </div>
  )
}

function IndiaMap({ states, metric, scale, region, selected, onSelect }) {
  const [hover, setHover] = useState(null)
  const byId = useMemo(() => {
    const m = {}
    states.forEach((e) => (MAP_IDS[e.name] || []).forEach((id) => (m[id] = e)))
    return m
  }, [states])
  const hovered = hover ? byId[hover.id] : null

  return (
    <div className="relative" onMouseLeave={() => setHover(null)}>
      <svg viewBox={india.viewBox} className="mx-auto h-auto w-full max-w-[520px]" role="img" aria-label={`India map: ${metric.label}`}>
        {india.locations.map((loc) => {
          const e = byId[loc.id]
          const v = e ? e[metric.id] : null
          const isSel = e && selected === e.name
          const dimmed = region !== 'all' && (!e || e.region !== region)
          return (
            <path
              key={loc.id}
              d={loc.path}
              fill={v === null || v === undefined ? NO_DATA : scale.color(v)}
              fillOpacity={dimmed ? 0.15 : 1}
              stroke={isSel ? '#f8fafc' : '#0d1016'}
              strokeWidth={isSel ? 1.6 : 0.6}
              className={e ? 'cursor-pointer hover:opacity-80' : ''}
              onMouseMove={(ev) => {
                const box = ev.currentTarget.ownerSVGElement.parentNode.getBoundingClientRect()
                setHover({ id: loc.id, name: loc.name, x: ev.clientX - box.left, y: ev.clientY - box.top })
              }}
              onClick={() => e && onSelect(e.name)}
            >
              <title>{e ? `${e.name}: ${v === null ? 'N/A' : metric.fmt(v)}` : `${loc.name}: not on the national grid`}</title>
            </path>
          )
        })}
      </svg>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded-xl border border-white/10 bg-[#0a0c11]/95 px-3 py-2 text-xs shadow-xl"
          style={{ left: Math.min(hover.x + 14, 380), top: hover.y + 14 }}
        >
          <div className="font-semibold text-slate-200">{hovered ? hovered.name : hover.name}</div>
          {hovered ? (
            <>
              <div className="text-slate-400">
                {metric.label}:{' '}
                <span className="font-medium text-slate-200">
                  {hovered[metric.id] === null ? 'N/A' : metric.fmt(hovered[metric.id])}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: REGION_COLORS[hovered.region] }} />
                {REGION_NAMES[hovered.region]} region · click for trend
              </div>
            </>
          ) : (
            <div className="text-slate-500">No grid data (island UT, not on the national grid)</div>
          )}
        </div>
      )}
      <div className="mx-auto mt-3 max-w-[360px]">
        <div className="h-2 rounded-full" style={{ background: scale.gradient }} />
        <div className="mt-1 flex justify-between text-[11px] tabular-nums text-slate-500">
          <span>{scale.min === null ? '' : metric.fmt(scale.min)}</span>
          {metric.kind === 'div' && <span>0%</span>}
          <span>{scale.max === null ? '' : metric.fmt(scale.max)}</span>
        </div>
        {metric.kind !== 'div' && <div className="mt-0.5 text-center text-[10px] text-slate-600">map colour on a log scale</div>}
      </div>
    </div>
  )
}

// Gold, silver, bronze for the top three.
const MEDALS = ['#fbbf24', '#cbd5e1', '#fb923c']

function RankList({ states, metric, scale, selected, onSelect }) {
  const ranked = [...states]
    .filter((e) => e[metric.id] !== null && e[metric.id] !== undefined)
    .sort((a, b) => b[metric.id] - a[metric.id])
  const isDiv = metric.kind === 'div'
  const showTotal = metric.id === 'energyMu' || metric.id === 'shortageMu'
  const total = showTotal ? ranked.reduce((a, e) => a + e[metric.id], 0) : null

  return (
    <div className="flex flex-col rounded-2xl border border-white/8 bg-black/20">
      <div className="flex items-baseline justify-between gap-2 border-b border-white/6 px-4 py-3">
        <div className="text-xs font-medium uppercase tracking-wider text-slate-500">Ranking</div>
        <div className="text-[11px] tabular-nums text-slate-500">
          {ranked.length} states{total !== null ? ` · total ${metric.fmt(total)}` : ''}
        </div>
      </div>
      {ranked.length ? (
        <ol className="custom-scrollbar max-h-[520px] space-y-0.5 overflow-y-auto p-2">
          {ranked.map((e, i) => {
            const v = e[metric.id]
            const pct = Math.max(2, scale.frac(v) * 100)
            const isSel = selected === e.name
            const regionColor = REGION_COLORS[e.region]
            const valueClass = isDiv ? (v >= 0 ? 'text-sky-300' : 'text-rose-300') : 'text-slate-100'
            return (
              <li key={e.name}>
                <button
                  type="button"
                  onClick={() => onSelect(e.name)}
                  className={`flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition ${
                    isSel ? 'bg-white/[0.07] ring-1 ring-white/15' : 'hover:bg-white/[0.04]'
                  }`}
                >
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums ${
                      i < 3 ? 'text-[#0d1016]' : 'bg-white/[0.04] text-slate-500'
                    }`}
                    style={i < 3 ? { background: MEDALS[i] } : undefined}
                  >
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-[13px] text-slate-200">{e.name}</span>
                        <span
                          className="shrink-0 rounded-md px-1.5 py-px text-[10px] font-semibold tracking-wide text-slate-100"
                          style={{ background: `${regionColor}40`, boxShadow: `inset 0 0 0 1px ${regionColor}90` }}
                          title={`${REGION_NAMES[e.region]} region`}
                        >
                          {e.region}
                        </span>
                      </span>
                      <span className={`shrink-0 text-xs font-medium tabular-nums ${valueClass}`}>{metric.fmt(v)}</span>
                    </span>
                    <span className="relative mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                      {isDiv && <span className="absolute inset-y-0 left-1/2 w-px bg-white/20" />}
                      <span
                        className="absolute inset-y-0 rounded-full"
                        style={
                          isDiv
                            ? { background: scale.color(v), width: `${pct / 2}%`, left: v >= 0 ? '50%' : `${50 - pct / 2}%` }
                            : { background: scale.color(v), width: `${pct}%`, left: 0 }
                        }
                      />
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      ) : (
        <div className="p-4">
          <Empty>No state in this region has a value for this metric.</Empty>
        </div>
      )}
    </div>
  )
}

const TREND_METRICS = [
  { id: 'peak', label: 'Peak demand (MW)', fmt: (v) => fmtMW(v), tick: (v) => (v >= 1000 ? Math.round(v / 1000) + 'k' : v) },
  { id: 'energy', label: 'Energy met (MU/day)', fmt: (v) => fmtNum(v, 1) + ' MU/day', tick: (v) => v },
  { id: 'shortage', label: 'Energy shortage (MU/day)', fmt: (v) => fmtNum(v, 3) + ' MU/day', tick: (v) => v },
]

function StateTrend({ data, selected, onSelect }) {
  const [metricId, setMetricId] = useState('peak')
  const metric = TREND_METRICS.find((m) => m.id === metricId)
  const options = useMemo(() => {
    const states = data.entities.filter((e) => e.isState).map((e) => e.name).sort()
    const others = data.entities.filter((e) => !e.isState).map((e) => e.name).sort()
    return [...states.map((n) => ({ value: n, label: n })), ...others.map((n) => ({ value: n, label: `${n} (grid entity)` }))]
  }, [data.entities])
  const rows = useMemo(() => {
    const h = data.history[selected]
    if (!h) return []
    return zipColumns(h).map((r, i) => ({ month: fmtMonth(data.months[i]), value: r[metricId] }))
  }, [data, selected, metricId])
  const firstIdx = rows.findIndex((r) => r.value !== null)
  const shown = firstIdx > 0 ? rows.slice(firstIdx) : rows
  const lastMonth = data.months[data.months.length - 1]
  // Line takes the selected state's region colour, same as its ranking chip.
  const lineColor = REGION_LIGHT[data.entities.find((e) => e.name === selected)?.region] || '#34d399'

  return (
    <SectionCard
      title="State trend"
      subtitle="Monthly history for any state, UT or grid entity since 2019. Energy and shortage are per-day averages, so the current, partial month compares fairly."
      accent="emerald"
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select id="state-trend-select" label="State" value={selected} onChange={onSelect} options={options} />
        <Pills options={TREND_METRICS} value={metricId} onChange={setMetricId} tone="emerald" />
      </div>
      <ChartBox title={`${selected}: ${metric.label}`} note={`${fmtMonth(lastMonth)} is month-to-date`}>
        {shown.length ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={shown} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="month" {...AXIS} interval={Math.max(0, Math.floor(shown.length / 8))} />
                <YAxis {...AXIS} tickFormatter={metric.tick} width={48} />
                <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : metric.fmt(v))} />} />
                <Line type="monotone" dataKey="value" name={metric.label} stroke={lineColor} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Brush dataKey="month" height={22} travellerWidth={8} stroke={lineColor} fill="rgba(255,255,255,0.03)" tickFormatter={() => ''} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <Empty>No history for {selected}.</Empty>
        )}
      </ChartBox>
    </SectionCard>
  )
}

function OtherEntities({ entities }) {
  const others = entities.filter((e) => !e.isState)
  if (!others.length) return null
  return (
    <SectionCard
      title="Other grid entities"
      subtitle="Rows in the state table that are not states or UTs (DVC, Railways, bulk consumers on the inter-state network, large industrial users), so they have no shape on the map."
      accent="emerald"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-1.5 font-medium">Entity</th>
              <th className="py-1.5 font-medium">Region</th>
              <th className="py-1.5 text-right font-medium">Energy, 365d</th>
              <th className="py-1.5 text-right font-medium">Peak, 365d</th>
              <th className="py-1.5 text-right font-medium">Latest day</th>
            </tr>
          </thead>
          <tbody>
            {others.map((e) => (
              <tr key={e.name} className="border-t border-white/5">
                <td className="py-1.5 text-slate-300">{e.name}</td>
                <td className="py-1.5 text-slate-400">{e.region}</td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtNum(e.energyMu)} MU</td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtMW(e.peakMw)}</td>
                <td className="py-1.5 text-right tabular-nums text-slate-400">{e.latestDemandMw === null ? 'not reported' : fmtMW(e.latestDemandMw)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}

export default function StatesTab({ data }) {
  const [metricId, setMetricId] = useState('energyMu')
  const [selected, setSelected] = useState(data.entities.find((e) => e.isState)?.name || '')
  const metric = METRICS.find((m) => m.id === metricId)
  const [region, setRegion] = useState('all')
  const states = useMemo(() => data.entities.filter((e) => e.isState), [data.entities])
  // Scale over all states, not the filtered region, so a state's colour
  // never changes when the region filter does.
  const scale = useScale(states, metric)
  const regionCounts = useMemo(() => {
    const c = { all: states.length }
    states.forEach((e) => (c[e.region] = (c[e.region] || 0) + 1))
    return c
  }, [states])

  // Same shape the original single-page StatePanel was written against.
  const snapshot = useMemo(
    () => ({
      totals: { ...data.totals, date: data.asOf },
      states: data.entities
        .filter((e) => e.latestDemandMw !== null)
        .map((e) => ({ state: e.name, region: e.region, max_demand_met_mw: e.latestDemandMw, shortage_max_demand_mw: e.latestShortageMw || 0 }))
        .sort((a, b) => b.max_demand_met_mw - a.max_demand_met_mw),
    }),
    [data],
  )

  const pick = (name) => {
    setSelected(name)
    document.getElementById('state-trend-select')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <>
      <SectionCard
        title="India map"
        subtitle={`Per-state figures over the 365 days to ${data.asOf}. Growth compares with the 365 days before that, and is shown only where both years are complete. Click a state for its trend.`}
        accent="emerald"
      >
        <div className="mb-5 space-y-3">
          <Pills options={METRICS} value={metricId} onChange={setMetricId} />
          <RegionFilter value={region} onChange={setRegion} counts={regionCounts} />
        </div>
        {states.length ? (
          <div className="grid items-start gap-6 lg:grid-cols-[3fr_2fr]">
            <IndiaMap states={states} metric={metric} scale={scale} region={region} selected={selected} onSelect={pick} />
            <RankList
              states={region === 'all' ? states : states.filter((e) => e.region === region)}
              metric={metric}
              scale={scale}
              selected={selected}
              onSelect={pick}
            />
          </div>
        ) : (
          <Empty>No state data.</Empty>
        )}
        <p className="mt-4 text-[11px] leading-relaxed text-slate-600">
          J&amp;K and Ladakh report as one entity and are drawn as one shape. Map:{' '}
          <a
            href="https://github.com/VictorCazanave/svg-maps/tree/master/packages/india"
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-white/20 hover:text-slate-400"
          >
            @svg-maps/india
          </a>{' '}
          by Victor Cazanave,{' '}
          <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer" className="underline decoration-white/20 hover:text-slate-400">
            CC BY 4.0
          </a>
          , recoloured. Boundaries are illustrative.
        </p>
      </SectionCard>
      {data.regions && <RegionsPanel regions={data.regions} />}
      <StateTrend data={data} selected={selected} onSelect={setSelected} />
      <StatePanel study3Latest={snapshot} />
      <OtherEntities entities={data.entities} />
    </>
  )
}
