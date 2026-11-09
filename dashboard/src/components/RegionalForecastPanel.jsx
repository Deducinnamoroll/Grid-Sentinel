import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { SectionCard, ChartBox, ChartTooltip, Pills, Empty } from './ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { fmtDateShort, fmtDateLong, fmtNum, REGION_NAMES } from '../lib/format'
import { REGION_LIGHT } from '../lib/colors'

const REGIONS = ['NR', 'WR', 'SR', 'ER', 'NER']
// "10 Nov": the shared short format is month and year, which reads wrong for a single day.
const fmtDay = (d) => new Date(d + 'T00:00:00Z').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' })
// Walk-forward backtest, 2024-01 to 2026-11, 1,039 forecasts per region
// (Pipeline/docs/study1_predict_notes.md): model MAPE, and the better of two
// naive baselines (repeat the made day, or same weekday a week earlier).
const BACKTEST = { NR: [3.91, 4.19], WR: [2.65, 3.35], SR: [3.53, 4.91], ER: [3.76, 3.94], NER: [4.96, 5.64] }

export default function RegionalForecastPanel({ rows }) {
  const [region, setRegion] = useState('NR')
  const byRegion = useMemo(() => {
    const out = {}
    for (const k of REGIONS) out[k] = rows.filter((r) => r.region === k)
    return out
  }, [rows])

  if (!rows.length) {
    return (
      <SectionCard title="Regional peak forecast" accent="violet">
        <Empty>No regional forecasts logged yet.</Empty>
      </SectionCard>
    )
  }

  const summary = REGIONS.map((k) => {
    const all = byRegion[k]
    const scored = all.filter((r) => r.actual_mw !== null)
    const latest = all[all.length - 1]
    const lastScored = scored[scored.length - 1]
    const mape = scored.length ? (scored.reduce((a, r) => a + Math.abs(r.residual_mw / r.actual_mw), 0) / scored.length) * 100 : null
    return { k, latest, lastScored, mape, n: scored.length }
  })
  const chart = byRegion[region].map((r) => ({ date: r.target_date, Forecast: r.predicted_mw, Actual: r.actual_mw }))

  return (
    <SectionCard
      title="Regional peak forecast"
      subtitle="The same model and holiday correction as the national forecast, trained separately for each region's daily peak, two days ahead. In a 2024 to 2026 backtest it beat simply repeating recent days in every region; the small North-Eastern grid is the hardest to call."
      accent="violet"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] whitespace-nowrap text-xs">
          <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-1.5 font-medium">Region</th>
              <th className="py-1.5 text-right font-medium">Latest forecast</th>
              <th className="py-1.5 text-right font-medium">Last scored day</th>
              <th className="py-1.5 text-right font-medium">Live MAPE</th>
              <th className="py-1.5 text-right font-medium">Backtest MAPE</th>
              <th className="py-1.5 text-right font-medium">Naive baseline</th>
            </tr>
          </thead>
          <tbody>
            {summary.map((s) => (
              <tr key={s.k} className="border-t border-white/5">
                <td className="py-1.5">
                  <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: REGION_LIGHT[s.k] }} />
                  <span className="text-slate-200">{REGION_NAMES[s.k]}</span>
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-200">
                  {fmtNum(s.latest.predicted_mw)} MW <span className="text-slate-500">for {fmtDay(s.latest.target_date)}</span>
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-400">
                  {s.lastScored
                    ? `${((s.lastScored.residual_mw / s.lastScored.actual_mw) * 100 >= 0 ? '+' : '')}${((s.lastScored.residual_mw / s.lastScored.actual_mw) * 100).toFixed(1)}% on ${fmtDay(s.lastScored.target_date)}`
                    : 'N/A'}
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{s.mape === null ? 'N/A' : `${s.mape.toFixed(2)}% (${s.n} days)`}</td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{BACKTEST[s.k][0].toFixed(2)}%</td>
                <td className="py-1.5 text-right tabular-nums text-slate-500">{BACKTEST[s.k][1].toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-5 mb-3">
        <Pills options={REGIONS.map((k) => ({ id: k, label: REGION_NAMES[k] }))} value={region} onChange={setRegion} tone="violet" />
      </div>
      <ChartBox title={`${REGION_NAMES[region]} region: forecast vs actual peak (MW)`}>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="date" {...AXIS} tickFormatter={fmtDateShort} minTickGap={40} />
              <YAxis {...AXIS} width={52} tickFormatter={(v) => Math.round(v / 1000) + 'k'} domain={['auto', 'auto']} />
              <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : fmtNum(v) + ' MW')} />} labelFormatter={fmtDateLong} />
              <Legend {...LEGEND} />
              <Line type="monotone" dataKey="Actual" stroke={REGION_LIGHT[region]} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="Forecast" stroke="#f8fafc" strokeDasharray="4 3" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ChartBox>
    </SectionCard>
  )
}
