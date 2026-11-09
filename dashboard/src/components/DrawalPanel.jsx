import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { SectionCard, ChartBox, ChartTooltip, Pills } from './ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtMonth, fmtNum, fmtDateLong, REGION_NAMES } from '../lib/format'
import { REGION_LIGHT } from '../lib/colors'

const REGIONS = ['NR', 'WR', 'SR', 'ER', 'NER']
const SORTS = [
  { id: 'absMu', label: 'Total deviation' },
  { id: 'absPctOfSchedule', label: 'Deviation vs schedule' },
  { id: 'maxOdMw', label: 'Largest over-drawal' },
]

export default function DrawalPanel({ drawal }) {
  const [sort, setSort] = useState('absMu')
  const rows = useMemo(
    () => zipColumns(drawal.regionMonthly).map((r) => ({
      label: fmtMonth(r.month),
      ...Object.fromEntries(REGIONS.map((k) => [REGION_NAMES[k], r[k]])),
    })),
    [drawal.regionMonthly],
  )
  const states = useMemo(
    () => [...drawal.states].sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity)).slice(0, 15),
    [drawal.states, sort],
  )
  const maxBar = Math.max(...states.map((s) => s[sort] ?? 0))

  return (
    <SectionCard
      title="Grid discipline: over- and under-drawal"
      subtitle="Each state and region is scheduled to draw a set amount from the grid. Drawing more (over-drawal, above zero) or less (under-drawal, below zero) than the schedule pushes the grid off balance and moves frequency."
      accent="rose"
    >
      <ChartBox title="Net deviation by region (MU/day, monthly average)" note="Above zero: drew more than scheduled">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(rows.length / 9))} />
              <YAxis {...AXIS} width={44} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
              <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : `${fmtNum(v, 2)} MU/day`)} />} />
              <Legend {...LEGEND} />
              {REGIONS.map((k) => (
                <Line key={k} type="monotone" dataKey={REGION_NAMES[k]} stroke={REGION_LIGHT[k]} strokeWidth={1.5} dot={false} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ChartBox>

      <div className="mt-6 mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs font-medium uppercase tracking-wider text-slate-500">States, last 365 days to {fmtDateLong(drawal.asOf)}</div>
        <Pills options={SORTS} value={sort} onChange={setSort} tone="rose" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] whitespace-nowrap text-xs">
          <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-1.5 font-medium">State</th>
              <th className="w-[30%] py-1.5 font-medium" />
              <th className="py-1.5 text-right font-medium">Total deviation</th>
              <th className="py-1.5 text-right font-medium">Net</th>
              <th className="py-1.5 text-right font-medium">vs schedule</th>
              <th className="py-1.5 text-right font-medium">Days over-drawn</th>
              <th className="py-1.5 text-right font-medium">Largest over-drawal</th>
            </tr>
          </thead>
          <tbody>
            {states.map((s) => (
              <tr key={s.name} className="border-t border-white/5">
                <td className="py-1.5 pr-3">
                  <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: REGION_LIGHT[s.region] }} />
                  <span className="text-slate-200">{s.name}</span>
                </td>
                <td className="py-1.5 pr-3">
                  <div className="h-1.5 rounded-full bg-white/5">
                    <div className="h-1.5 rounded-full bg-rose-400/70" style={{ width: `${maxBar ? ((s[sort] ?? 0) / maxBar) * 100 : 0}%` }} />
                  </div>
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtNum(s.absMu)} MU</td>
                <td className={`py-1.5 text-right tabular-nums ${s.netMu > 0 ? 'text-amber-300' : 'text-sky-300'}`}>
                  {(s.netMu > 0 ? '+' : '') + fmtNum(s.netMu)} MU
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-400">{s.absPctOfSchedule === null ? 'N/A' : s.absPctOfSchedule.toFixed(1) + '%'}</td>
                <td className="py-1.5 text-right tabular-nums text-slate-400">{s.odDaysPct.toFixed(0)}%</td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{s.maxOdMw === null ? 'N/A' : fmtNum(s.maxOdMw) + ' MW'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        Total deviation adds up every day's gap from schedule whichever way it went; net lets over- and under-drawal cancel. {drawal.states.filter((s) => s.netMu < 0).length} of {drawal.states.length} states and UTs drew less than scheduled on balance. Top 15 shown.
      </p>
    </SectionCard>
  )
}
