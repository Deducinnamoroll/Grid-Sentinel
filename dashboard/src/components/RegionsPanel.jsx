import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { SectionCard, ChartBox, ChartTooltip, Pills } from './ui'
import { AXIS, GRID, LEGEND } from '../lib/chart'
import { zipColumns } from '../lib/data'
import { fmtMonth, fmtNum, fmtDateLong, REGION_NAMES } from '../lib/format'
import { REGION_LIGHT } from '../lib/colors'

const REGIONS = ['NR', 'WR', 'SR', 'ER', 'NER']
const METRICS = [
  { id: 'peak', label: 'Peak demand (MW, monthly max)', unit: 'MW', digits: 0 },
  { id: 'energy', label: 'Energy (MU/day, monthly average)', unit: 'MU/day', digits: 1 },
]

export default function RegionsPanel({ regions }) {
  const [metric, setMetric] = useState('peak')
  const m = METRICS.find((x) => x.id === metric)
  const rows = useMemo(
    () => zipColumns(regions.monthly).map((r) => ({
      label: fmtMonth(r.month),
      ...Object.fromEntries(REGIONS.map((k) => [REGION_NAMES[k], r[`${metric}_${k.toLowerCase()}`]])),
    })),
    [regions.monthly, metric],
  )
  const kTick = (v) => (metric === 'peak' ? Math.round(v / 1000) + 'k' : fmtNum(v))

  return (
    <SectionCard
      title="The five regions"
      subtitle={`India's grid is run as five regional grids. Shares and growth compare the last 365 days with the 365 before; the right-hand columns are ${fmtDateLong(regions.asOf)}.`}
      accent="emerald"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] whitespace-nowrap text-xs">
          <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-1.5 font-medium">Region</th>
              <th className="py-1.5 text-right font-medium">Share of energy</th>
              <th className="py-1.5 text-right font-medium">Growth</th>
              <th className="py-1.5 text-right font-medium">Highest peak, 365 days</th>
              <th className="py-1.5 text-right font-medium">Peak, latest day</th>
              <th className="py-1.5 text-right font-medium">At evening peak</th>
              <th className="py-1.5 text-right font-medium">Shortage then</th>
            </tr>
          </thead>
          <tbody>
            {regions.summary.map((r) => (
              <tr key={r.region} className="border-t border-white/5">
                <td className="py-1.5">
                  <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: REGION_LIGHT[r.region] }} />
                  <span className="text-slate-200">{REGION_NAMES[r.region]}</span>
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{r.sharePct === null ? 'N/A' : r.sharePct.toFixed(1) + '%'}</td>
                <td className={`py-1.5 text-right tabular-nums ${r.growthPct > 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {r.growthPct === null ? 'N/A' : (r.growthPct > 0 ? '+' : '') + r.growthPct.toFixed(1) + '%'}
                </td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtNum(r.peakMw)} MW</td>
                <td className="py-1.5 text-right tabular-nums text-slate-300">{fmtNum(r.latestMaxMw)} MW</td>
                <td className="py-1.5 text-right tabular-nums text-slate-400">{fmtNum(r.latestEveningMw)} MW</td>
                <td className={`py-1.5 text-right tabular-nums ${r.latestShortageMw > 0 ? 'text-amber-300' : 'text-slate-500'}`}>
                  {r.latestShortageMw === null ? 'N/A' : fmtNum(r.latestShortageMw) + ' MW'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-5 mb-3">
        <Pills options={METRICS.map((x) => ({ id: x.id, label: x.label }))} value={metric} onChange={setMetric} tone="emerald" />
      </div>
      <ChartBox title={m.label}>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} interval={Math.max(0, Math.floor(rows.length / 9))} />
              <YAxis {...AXIS} tickFormatter={kTick} width={44} />
              <Tooltip content={<ChartTooltip formatter={(v) => (v === null ? 'N/A' : `${fmtNum(v, m.digits)} ${m.unit}`)} />} />
              <Legend {...LEGEND} />
              {REGIONS.map((k) => (
                <Line key={k} type="monotone" dataKey={REGION_NAMES[k]} stroke={REGION_LIGHT[k]} strokeWidth={1.75} dot={false} connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ChartBox>
    </SectionCard>
  )
}
