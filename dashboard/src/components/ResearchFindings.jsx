import { pctTick } from '../lib/format'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts'
import { SectionCard } from './ui'
import { ChartTooltip } from './ui'
import HourDowHeatmap from './HourDowHeatmap'
import FeatureImportance from './FeatureImportance'

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function MonthSeasonality({ monthSeasonality }) {
  const data = monthSeasonality.map((r) => ({ month: MONTH_NAMES[r.month - 1], violation: r.violation * 100, ramp: r.ramp * 100 }))
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">Violation rate by month</div>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="month" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={pctTick} width={34} />
              <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(2) + '%'} />} />
              <Bar dataKey="violation" radius={2}>
                {data.map((_, i) => <Cell key={i} fill="#fb7185" fillOpacity={0.5 + (0.5 * data[i].violation) / Math.max(...data.map((d) => d.violation))} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">Ramp-shock rate by month</div>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="month" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={pctTick} width={34} />
              <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(2) + '%'} />} />
              <Bar dataKey="ramp" radius={2}>
                {data.map((_, i) => <Cell key={i} fill="#38bdf8" fillOpacity={0.5 + (0.5 * data[i].ramp) / Math.max(...data.map((d) => d.ramp))} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function SolarHourRates({ solarHourRates }) {
  const data = [
    { label: 'Non-solar hour', violation: solarHourRates.nonSolar.violation * 100, ramp: solarHourRates.nonSolar.ramp * 100 },
    { label: 'Solar hour', violation: solarHourRates.solar.violation * 100, ramp: solarHourRates.solar.ramp * 100 },
  ]
  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">Event rate: solar vs non-solar hour</div>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="label" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={pctTick} width={34} />
            <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(2) + '%'} />} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
            <Bar dataKey="violation" name="Violation rate" fill="#fb7185" radius={2} />
            <Bar dataKey="ramp" name="Ramp rate" fill="#38bdf8" radius={2} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ResShareViolation({ pooledViolationByResShare }) {
  const data = pooledViolationByResShare.map((r) => ({ quintile: r.quintile, violation: r.violation * 100 }))
  const max = Math.max(...data.map((d) => d.violation))
  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
        Violation rate rises with RES share (pooled)
      </div>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="quintile" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} />
            <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={pctTick} width={34} />
            <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(2) + '%'} />} />
            <Bar dataKey="violation" radius={3}>
              {data.map((d, i) => <Cell key={i} fill="#fb7185" fillOpacity={0.35 + 0.65 * (d.violation / max)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function RampReversal({ rampReversal }) {
  const data = rampReversal.map((r) => ({ quintile: r.quintile, Pooled: r.pooled * 100, 'Within-month': r.withinMonth * 100 }))
  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
        RES share vs. ramp-shock rate: pooled sign reverses once season is controlled for
      </div>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="quintile" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} />
            <YAxis stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={pctTick} width={34} />
            <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(2) + '%'} />} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
            <Bar dataKey="Pooled" fill="#9085e9" radius={2} />
            <Bar dataKey="Within-month" fill="#38bdf8" radius={2} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function ResearchFindings({ hourDowHeatmap, monthSeasonality, solarHourRates, resShareFindings, featureImportance }) {
  if (!hourDowHeatmap || !monthSeasonality || !solarHourRates || !resShareFindings || !featureImportance) return null

  return (
    <SectionCard
      title="Research Findings"
      subtitle="The full set of verified findings, not just the live operational panels above."
      accent="violet"
    >
      <div className="space-y-6">
        <div>
          <div className="mb-3 text-sm font-medium text-slate-300">
            Day-of-week decoupling: violations peak on Sunday, ramp-shocks are lowest on Sunday
          </div>
          <HourDowHeatmap heatmap={hourDowHeatmap} />
        </div>

        <div>
          <div className="mb-3 text-sm font-medium text-slate-300">Seasonality</div>
          <MonthSeasonality monthSeasonality={monthSeasonality} />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <SolarHourRates solarHourRates={solarHourRates} />
          <ResShareViolation pooledViolationByResShare={resShareFindings.pooledViolationByResShare} />
        </div>

        <div>
          <div className="mb-3 text-sm font-medium text-slate-300">
            The season-confounding finding: RES share vs. ramp rate flips sign once season is controlled for
          </div>
          <RampReversal rampReversal={resShareFindings.rampReversal} />
        </div>

        <div>
          <div className="mb-3 text-sm font-medium text-slate-300">What drives each model (top 10 features, freshly retrained)</div>
          <FeatureImportance featureImportance={featureImportance} />
        </div>
      </div>
    </SectionCard>
  )
}
