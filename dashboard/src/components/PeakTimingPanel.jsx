import { useMemo } from 'react'
import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { SectionCard, ChartBox, ChartTooltip } from './ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtMonth, fmtNum, pctTick } from '../lib/format'

const kTick = (v) => Math.round(v / 1000) + 'k'

function HourGrid({ months, counts }) {
  // Rows: months; columns: hour of day; shade = share of that month's days
  // whose national peak fell in that hour.
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[640px]">
        <div className="ml-14 grid grid-cols-24 gap-px text-[10px] text-slate-500" style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))' }}>
          {Array.from({ length: 24 }, (_, h) => (
            <div key={h} className="text-center">{h % 3 === 0 ? String(h).padStart(2, '0') : ''}</div>
          ))}
        </div>
        {months.map((m, i) => {
          const total = counts[i].reduce((a, b) => a + b, 0) || 1
          return (
            <div key={m} className="mt-px flex items-center">
              <div className="w-14 shrink-0 pr-2 text-right text-[10px] text-slate-500">{fmtMonth(m)}</div>
              <div className="grid flex-1 gap-px" style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))' }}>
                {counts[i].map((c, h) => (
                  <div
                    key={h}
                    className="h-3.5 rounded-[2px]"
                    style={{ background: c ? `rgba(251,191,36,${0.15 + 0.85 * (c / total)})` : 'rgba(255,255,255,0.03)' }}
                    title={`${fmtMonth(m)}, ${String(h).padStart(2, '0')}:00 to ${String(h).padStart(2, '0')}:59: ${c} of ${total} days`}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function PeakTimingPanel({ timing }) {
  const rows = useMemo(
    () => zipColumns(timing.monthly).map((r) => ({
      label: fmtMonth(r.month),
      'Peak in solar hours': r.solarPeak,
      'Peak outside solar hours': r.nonSolarPeak,
      'Days the solar-hour peak was higher (%)': r.solarWinsShare,
      'Shortage in solar hours': r.solarShortage,
      'Shortage outside solar hours': r.nonSolarShortage,
    })),
    [timing.monthly],
  )
  const fmt = (v, name) => (v === null ? 'N/A' : name.includes('%') ? v.toFixed(0) + '%' : fmtNum(v) + ' MW')

  return (
    <SectionCard
      title="When the peak happens"
      subtitle="Solar is moving India's daily peak. NLDC reports the highest demand met inside solar hours and outside them separately (from May 2023), and the minute the national peak was reached."
      accent="amber"
    >
      <ChartBox title="Average daily peak, inside vs outside solar hours (MW)" note="Bars: share of days the solar-hour peak was higher">
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(rows.length / 9))} />
              <YAxis yAxisId="mw" {...AXIS} tickFormatter={kTick} width={44} domain={['auto', 'auto']} />
              <YAxis yAxisId="pct" orientation="right" {...AXIS} domain={[0, 100]} tickFormatter={pctTick} width={40} />
              <Tooltip content={<ChartTooltip formatter={fmt} />} />
              <Legend {...LEGEND} />
              <Bar yAxisId="pct" dataKey="Days the solar-hour peak was higher (%)" fill="rgba(251,191,36,0.18)" isAnimationActive={false} />
              <Line yAxisId="mw" type="monotone" dataKey="Peak in solar hours" stroke="#fbbf24" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line yAxisId="mw" type="monotone" dataKey="Peak outside solar hours" stroke="#a78bfa" strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </ChartBox>

      <ChartBox className="mt-4" title="Average shortage at those peaks (MW)">
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(rows.length / 9))} />
              <YAxis {...AXIS} width={44} />
              <Tooltip content={<ChartTooltip formatter={fmt} />} />
              <Legend {...LEGEND} />
              <Bar dataKey="Shortage in solar hours" fill="#d97706" isAnimationActive={false} />
              <Bar dataKey="Shortage outside solar hours" fill="#8b5cf6" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </ChartBox>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        In winter the day's highest demand comes while the sun is up on nearly every day; in the monsoon and autumn it often comes after dark. Shortage is one-sided: in{' '}
        {rows.filter((r) => (r['Shortage outside solar hours'] ?? 0) > (r['Shortage in solar hours'] ?? 0)).length} of {rows.length} months more demand went unmet outside solar hours, when solar has gone and the evening load is still high.
      </p>

      <ChartBox className="mt-4" title="Hour the national peak was reached, by month" note="Darker: more days that month">
        <HourGrid months={timing.hourMonths} counts={timing.hourCounts} />
      </ChartBox>
    </SectionCard>
  )
}
