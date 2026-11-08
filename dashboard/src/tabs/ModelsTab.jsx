import { useMemo } from 'react'
import {
  ComposedChart, Bar, Line, BarChart, Cell, Scatter, ScatterChart, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts'
import ForecastPanel from '../components/ForecastPanel'
import RiskPanel from '../components/RiskPanel'
import AnomalyLog from '../components/AnomalyLog'
import ResearchFindings from '../components/ResearchFindings'
import { SectionCard, StatCard, StatGrid, ChartBox, Empty, ChartTooltip } from '../components/ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { expandRisk } from '../lib/data'
import { fmtDateShort, fmtDateLong, fmtNum } from '../lib/format'

function ForecastAccuracy({ forecast }) {
  const rows = useMemo(() => {
    const done = forecast.filter((r) => r.actual_mw !== null && r.residual_mw !== null)
    const out = []
    for (let i = 0; i < done.length; i++) {
      const r = done[i]
      // residual = actual - predicted, so positive means the model under-forecast.
      const err = (r.residual_mw / r.actual_mw) * 100
      const win = done.slice(Math.max(0, i - 6), i + 1)
      const mape = win.reduce((a, w) => a + Math.abs(w.residual_mw / w.actual_mw), 0) / win.length * 100
      out.push({ date: r.target_date, 'Daily error': err, '7-day MAPE': win.length >= 7 ? mape : null })
    }
    return out
  }, [forecast])

  if (!rows.length) {
    return (
      <SectionCard title="Study 1: Forecast accuracy" accent="violet">
        <Empty>No forecasts with a known actual yet.</Empty>
      </SectionCard>
    )
  }

  const errs = rows.map((r) => r['Daily error'])
  const mean = errs.reduce((a, b) => a + b, 0) / errs.length
  const within2 = (errs.filter((e) => Math.abs(e) <= 2).length / errs.length) * 100
  const worst = rows.reduce((a, b) => (Math.abs(b['Daily error']) > Math.abs(a['Daily error']) ? b : a))

  // Histogram of daily % error in 1-point bins, clipped at +/-8%.
  const bins = []
  for (let b = -8; b < 8; b++) bins.push({ bin: b, label: `${b}%`, count: 0 })
  errs.forEach((e) => {
    const b = Math.max(-8, Math.min(7, Math.floor(e)))
    bins[b + 8].count += 1
  })

  return (
    <SectionCard
      title="Study 1: Forecast accuracy"
      subtitle="Every logged next-day forecast scored against the demand that actually happened. Error is (actual minus predicted) / actual: above zero means the model under-forecast."
      accent="violet"
    >
      <StatGrid>
        <StatCard value={rows.length} label="Forecasts scored" sub={`${fmtDateShort(rows[0].date)} to ${fmtDateShort(rows[rows.length - 1].date)}`} />
        <StatCard value={`${mean >= 0 ? '+' : ''}${mean.toFixed(2)}%`} label="Average bias" sub={mean >= 0 ? 'tends to under-forecast' : 'tends to over-forecast'} />
        <StatCard value={within2.toFixed(0) + '%'} label="Days within 2%" tone={within2 >= 70 ? 'good' : 'warning'} />
        <StatCard value={`${worst['Daily error'] >= 0 ? '+' : ''}${worst['Daily error'].toFixed(1)}%`} label="Worst miss" sub={fmtDateLong(worst.date)} tone="warning" />
      </StatGrid>
      <div className="mt-5 grid gap-4 lg:grid-cols-[3fr_2fr]">
        <ChartBox title="Daily error (%) and trailing 7-day MAPE">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="date" {...AXIS} tickFormatter={fmtDateShort} minTickGap={40} />
                <YAxis {...AXIS} tickFormatter={(v) => v + '%'} width={40} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" />
                <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : v.toFixed(2) + '%')} />} labelFormatter={fmtDateLong} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Legend {...LEGEND} />
                <Bar dataKey="Daily error" isAnimationActive={false}>
                  {rows.map((r, i) => (
                    <Cell key={i} fill={r['Daily error'] >= 0 ? '#a78bfa' : '#38bdf8'} />
                  ))}
                </Bar>
                <Line type="monotone" dataKey="7-day MAPE" stroke="#f8fafc" strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </ChartBox>
        <ChartBox title="How big the misses are (days per 1% bin)">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bins} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="label" {...AXIS} tick={{ ...AXIS.tick, fontSize: 10 }} interval={1} />
                <YAxis {...AXIS} allowDecimals={false} width={30} />
                <Tooltip
                  content={<ChartTooltip formatter={(v) => `${v} days`} />}
                  labelFormatter={(l) => `${l} to ${parseInt(l, 10) + 1}%`}
                  cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                />
                <Bar dataKey="count" name="Days" fill="#a78bfa" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartBox>
      </div>
      <p className="mt-3 text-[11px] text-slate-600">Bins clip at plus or minus 8%; a larger miss counts in the end bin.</p>
    </SectionCard>
  )
}

function ReliabilityDiagram({ title, cal, color }) {
  if (!cal) return <Empty>Not enough labelled slots yet for {title.toLowerCase()}.</Empty>
  const pts = cal.bins.map((b) => ({ predicted: b.predicted * 100, observed: b.observed * 100, n: b.n }))
  const max = Math.ceil(Math.max(...pts.map((p) => Math.max(p.predicted, p.observed)), 1) / 5) * 5
  return (
    <ChartBox title={title}>
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {[
          ['ROC AUC', cal.auc.toFixed(3)],
          ['Avg. precision', cal.avgPrecision.toFixed(3)],
          ['Base rate', (cal.baseRate * 100).toFixed(1) + '%'],
          ['Brier score', cal.brier.toFixed(4)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-lg border border-white/6 bg-white/[0.02] px-2.5 py-1.5">
            <div className="tabular-nums text-slate-100">{v}</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">{k}</div>
          </div>
        ))}
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 16 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis
              type="number"
              dataKey="predicted"
              name="Predicted"
              domain={[0, max]}
              {...AXIS}
              tickFormatter={(v) => v + '%'}
              label={{ value: 'Predicted risk', position: 'insideBottom', offset: -10, fill: '#64748b', fontSize: 11 }}
            />
            <YAxis type="number" dataKey="observed" name="Observed" domain={[0, max]} {...AXIS} tickFormatter={(v) => v + '%'} width={40} />
            <ZAxis range={[90, 90]} />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: max, y: max },
              ]}
              stroke="rgba(255,255,255,0.3)"
              strokeDasharray="4 4"
            />
            <Tooltip
              cursor={{ strokeDasharray: '3 3', stroke: 'rgba(255,255,255,0.2)' }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-xl border border-white/10 bg-[#0a0c11]/95 px-3 py-2 text-xs shadow-xl">
                    <div className="text-slate-400">
                      Predicted <span className="font-medium text-slate-200">{payload[0].payload.predicted.toFixed(1)}%</span>
                    </div>
                    <div className="text-slate-400">
                      Happened <span className="font-medium text-slate-200">{payload[0].payload.observed.toFixed(1)}%</span>
                    </div>
                    <div className="text-slate-500">{fmtNum(payload[0].payload.n)} slots in this decile</div>
                  </div>
                ) : null
              }
            />
            <Scatter data={pts} fill={color} stroke="#0d1016" strokeWidth={2} line={{ stroke: color, strokeWidth: 2 }} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-500">
        At its alert threshold ({(cal.threshold * 100).toFixed(1)}%) the model flagged {fmtNum(cal.flagged)} of {fmtNum(cal.n)} slots:{' '}
        <span className="text-slate-300">{cal.precision === null ? 'N/A' : (cal.precision * 100).toFixed(0) + '%'}</span> of alerts were real, and
        it caught <span className="text-slate-300">{cal.recall === null ? 'N/A' : (cal.recall * 100).toFixed(0) + '%'}</span> of the{' '}
        {fmtNum(cal.positives)} actual events.
      </p>
    </ChartBox>
  )
}

function RiskCalibration({ calibration }) {
  if (!calibration) return null
  const under = ['violation', 'ramp'].filter((k) => calibration[k] && calibration[k].bins.slice(-3).every((b) => b.observed > b.predicted))
  return (
    <SectionCard
      title="Study 2: Is the risk score trustworthy?"
      subtitle="Every logged 15-minute prediction since the live log began, split into ten equal-size groups by predicted risk and compared with how often the event actually happened. Dots on the dashed line mean the stated risk is honest; above it, events happen more often than the score says."
      accent="rose"
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <ReliabilityDiagram title="Frequency-violation risk" cal={calibration.violation} color="#fb7185" />
        <ReliabilityDiagram title="Ramp-shock risk" cal={calibration.ramp} color="#38bdf8" />
      </div>
      {under.length > 0 && (
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          In the riskiest groups, {under.length === 2 ? 'both models' : `the ${under[0]} model`} understate the risk: events happen more often than
          the score says. Ranking is what the alerts rely on (ROC AUC above), so read the score as relative, not as a literal probability.
        </p>
      )}
    </SectionCard>
  )
}

export default function ModelsTab({ data }) {
  const risk = useMemo(() => expandRisk(data.risk), [data.risk])
  const forecast = data.forecast || []
  return (
    <>
      <ForecastPanel forecast={forecast} />
      <ForecastAccuracy forecast={forecast} />
      <RiskPanel risk={risk} />
      <RiskCalibration calibration={data.calibration} />
      <AnomalyLog forecast={forecast} risk={risk} thresholds={data.featureImportance?.thresholds} />
      <ResearchFindings
        hourDowHeatmap={data.hourDowHeatmap}
        monthSeasonality={data.monthSeasonality || []}
        solarHourRates={data.solarHourRates}
        resShareFindings={data.resShareFindings}
        featureImportance={data.featureImportance}
      />
    </>
  )
}
