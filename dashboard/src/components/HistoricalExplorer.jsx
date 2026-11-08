import { useState } from 'react'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine, Brush,
} from 'recharts'
import { SectionCard, Empty, ChartTooltip } from './ui'
import { fmtDateShort, index0to100, shortCorridorName } from '../lib/format'

const TABS = [
  { id: 'overview', label: 'Full history (2019–present)' },
  { id: 'era1', label: 'Era 1: Ramp trend vs RES share (2019–2022)' },
  { id: 'era2', label: 'Era 2: Corridor-stress correlation (2023–Oct 2024)' },
]

function FullHistory({ history }) {
  if (!history.length) return <Empty>No data.</Empty>
  const demandData = history.map((r) => ({ date: fmtDateShort(r.date), Demand: r.demand }))
  const resData = history.map((r) => ({ date: fmtDateShort(r.date), 'RES share': r.res }))

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="mb-3 flex items-center justify-between text-xs font-medium uppercase tracking-wider text-slate-500">
          <span>National peak demand met (MW)</span>
          <span className="normal-case tracking-normal text-slate-600">Drag the strip below to zoom</span>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={demandData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="demandHistGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="date" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} interval={Math.floor(demandData.length / 8)} />
              <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={(v) => Math.round(v / 1000) + 'k'} width={44} />
              <Tooltip content={<ChartTooltip formatter={(v) => Math.round(v).toLocaleString('en-IN') + ' MW'} />} />
              <Area type="monotone" dataKey="Demand" stroke="#38bdf8" strokeWidth={1.5} fill="url(#demandHistGrad)" dot={false} isAnimationActive={false} />
              <Brush
                dataKey="date"
                height={24}
                travellerWidth={8}
                stroke="#38bdf8"
                fill="rgba(56,189,248,0.05)"
                tickFormatter={() => ''}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="mb-3 flex items-center justify-between text-xs font-medium uppercase tracking-wider text-slate-500">
          <span>RES share of generation (%)</span>
          <span className="normal-case tracking-normal text-slate-600">Drag the strip below to zoom</span>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={resData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="resHistGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="date" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} interval={Math.floor(resData.length / 8)} />
              <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={(v) => v + '%'} width={40} />
              <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : v.toFixed(1) + '%')} />} />
              <Area type="monotone" dataKey="RES share" stroke="#fbbf24" strokeWidth={1.5} fill="url(#resHistGrad)" dot={false} isAnimationActive={false} />
              <Brush
                dataKey="date"
                height={24}
                travellerWidth={8}
                stroke="#fbbf24"
                fill="rgba(251,191,36,0.05)"
                tickFormatter={() => ''}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function Era1Tab({ era1Monthly }) {
  if (!era1Monthly.length) return <Empty>No data.</Empty>
  const ramp = index0to100(era1Monthly.map((r) => r.ramp_magnitude))
  const res = index0to100(era1Monthly.map((r) => r.share_res_pct))
  const data = era1Monthly.map((r, i) => ({
    month: fmtDateShort(r.month),
    'Ramp magnitude (indexed)': ramp[i],
    'RES share % (indexed)': res[i],
  }))

  return (
    <div>
      <p className="mb-4 text-sm leading-relaxed text-slate-400">
        Non-live, historical: intra-day ramp magnitude (max hour-to-hour demand swing) tracked against rising RES share, both
        indexed to a common 0–100 scale (each series' own min-max), never a dual-axis chart.
      </p>
      <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="month" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} interval={4} />
              <YAxis domain={[0, 100]} stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} width={30} />
              <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(0)} />} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
              <Line type="monotone" dataKey="Ramp magnitude (indexed)" stroke="#38bdf8" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="RES share % (indexed)" stroke="#fb7185" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function CorrBar({ title, bars }) {
  const data = bars.map((b) => ({ name: shortCorridorName(b.name), corr: b.corr }))
  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">{title}</div>
      <div style={{ height: Math.max(160, data.length * 34) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 4 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
            <XAxis type="number" domain={[-0.5, 0.5]} stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis type="category" dataKey="name" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#94a3b8', fontSize: 11 }} width={90} />
            <ReferenceLine x={0} stroke="rgba(255,255,255,0.25)" />
            <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(3)} />} />
            <Bar dataKey="corr" radius={3}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.corr >= 0 ? '#fb7185' : '#38bdf8'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function Era2Tab({ era2CorridorCorr }) {
  if (!era2CorridorCorr.length) return <Empty>No data.</Empty>
  const corridor = era2CorridorCorr.filter((r) => r.group === 'corridor').sort((a, b) => a.corr - b.corr)
  const xb = era2CorridorCorr.filter((r) => r.group === 'cross_border').sort((a, b) => a.corr - b.corr)

  return (
    <div>
      <p className="mb-4 text-sm leading-relaxed text-slate-400">
        Non-live, historical: daily-resolution correlation between corridor/cross-border power flow and same-day frequency
        stress. Blue = flow relieves stress; red = flow coincides with stress.
      </p>
      <div className="space-y-4">
        <CorrBar title="Corridor flow vs. frequency stress" bars={corridor} />
        <CorrBar title="Cross-border exchange vs. frequency stress" bars={xb} />
      </div>
    </div>
  )
}

export default function HistoricalExplorer({ history, era1Monthly, era2CorridorCorr }) {
  const [tab, setTab] = useState('overview')

  return (
    <SectionCard title="Historical Explorer" accent="amber">
      <div className="mb-5 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-lg border px-3.5 py-1.5 text-xs font-medium transition ${
              tab === t.id
                ? 'border-amber-400/30 bg-amber-400/10 text-amber-200'
                : 'border-white/8 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <FullHistory history={history} />}
      {tab === 'era1' && <Era1Tab era1Monthly={era1Monthly} />}
      {tab === 'era2' && <Era2Tab era2CorridorCorr={era2CorridorCorr} />}
    </SectionCard>
  )
}
