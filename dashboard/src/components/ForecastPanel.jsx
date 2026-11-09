import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { SectionCard, StatCard, StatGrid, Empty, ChartTooltip } from './ui'
import { fmtMW, fmtDateShort } from '../lib/format'

export default function ForecastPanel({ forecast }) {
  if (!forecast.length) {
    return (
      <SectionCard title="Study 1: Next-Day Demand Forecast" accent="violet">
        <Empty>
          Forecast history is empty. <code className="rounded bg-white/10 px-1.5 py-0.5">ML/Study1/predict.py</code> runs daily via CI. Check back after the next run.
        </Empty>
      </SectionCard>
    )
  }

  const withActual = forecast.filter((r) => r.actual_mw !== null)
  const latest = forecast[forecast.length - 1]
  // The newest forecasts target days not reported yet, so show the most
  // recent forecast that has been scored next to the newest one.
  const lastScored = withActual.length ? withActual[withActual.length - 1] : null
  const mapes = withActual.map((r) => Math.abs(r.residual_mw) / r.actual_mw)
  const avgMape = mapes.length ? (mapes.reduce((a, b) => a + b, 0) / mapes.length) * 100 : null

  const chartData = forecast.map((r) => ({
    date: fmtDateShort(r.target_date),
    Predicted: r.predicted_mw,
    Actual: r.actual_mw,
  }))

  return (
    <SectionCard
      title="Study 1: Next-Day Demand Forecast"
      subtitle="LightGBM baseline, retrained daily on all available history, then scaled on holidays by how much demand dipped on the same holiday in past years (Diwali about -12%). NLDC publishes each day's report the following afternoon, so every forecast is made for two days after the latest report: it appears the day before the day it predicts."
      accent="violet"
    >
      <StatGrid>
        <StatCard
          value={fmtMW(latest.predicted_mw)}
          label="Latest forecast"
          sub={`for ${latest.target_date}, from data through ${latest.prediction_made_date}`}
        />
        <StatCard
          value={lastScored ? fmtMW(lastScored.actual_mw) : 'N/A'}
          label="Latest actual"
          sub={lastScored ? `${lastScored.target_date}, forecast ${fmtMW(lastScored.predicted_mw)}` : null}
        />
        <StatCard
          value={lastScored ? `${lastScored.residual_mw >= 0 ? '+' : ''}${Math.round(lastScored.residual_mw).toLocaleString('en-IN')} MW` : 'N/A'}
          label="Its error"
          sub={lastScored ? `${((lastScored.residual_mw / lastScored.actual_mw) * 100).toFixed(1)}% (actual minus forecast)` : null}
        />
        <StatCard value={avgMape !== null ? avgMape.toFixed(2) + '%' : 'N/A'} label="Avg. MAPE (logged history)" />
      </StatGrid>

      <div className="mt-5 h-72 rounded-2xl border border-white/8 bg-black/20 p-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="predictedGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis dataKey="date" stroke="rgba(255,255,255,0.3)" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis
              stroke="rgba(255,255,255,0.3)"
              tick={{ fill: '#64748b', fontSize: 11 }}
              tickFormatter={(v) => Math.round(v / 1000) + 'k'}
              width={44}
            />
            <Tooltip content={<ChartTooltip formatter={(v) => fmtMW(v)} />} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
            <Area type="monotone" dataKey="Predicted" stroke="#a78bfa" strokeWidth={2} fill="url(#predictedGrad)" dot={{ r: 3, fill: '#a78bfa' }} />
            <Area type="monotone" dataKey="Actual" stroke="#38bdf8" strokeWidth={2} fill="url(#actualGrad)" dot={{ r: 3, fill: '#38bdf8' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </SectionCard>
  )
}
