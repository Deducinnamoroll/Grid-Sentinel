import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { ChartTooltip } from './ui'

function ImportanceBar({ title, data, color }) {
  const max = Math.max(...data.map((d) => d.importance))
  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">{title}</div>
      <div style={{ height: Math.max(180, data.length * 26) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 20, left: 8, bottom: 4 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
            <XAxis type="number" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 10 }} />
            <YAxis type="category" dataKey="feature" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#94a3b8', fontSize: 10 }} width={130} />
            <Tooltip content={<ChartTooltip formatter={(v) => v + ' splits'} />} />
            <Bar dataKey="importance" radius={3} isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={i} fill={color} fillOpacity={0.4 + 0.6 * (d.importance / max)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function FeatureImportance({ featureImportance }) {
  if (!featureImportance) return null
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <ImportanceBar title="Demand forecast (Study 1)" data={featureImportance.study1Demand} color="#a78bfa" />
      <ImportanceBar title="Violation classifier" data={featureImportance.study2Violation} color="#fb7185" />
      <ImportanceBar title="Ramp-shock classifier" data={featureImportance.study2Ramp} color="#38bdf8" />
    </div>
  )
}
