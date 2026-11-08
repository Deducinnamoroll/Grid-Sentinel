import { SectionCard, StatCard, StatGrid, Empty } from './ui'
import { fmtMW } from '../lib/format'
import { REGION_LIGHT } from '../lib/colors'

export default function StatePanel({ study3Latest }) {
  if (!study3Latest || !study3Latest.states.length) {
    return (
      <SectionCard title="State-Level Snapshot" accent="emerald">
        <Empty>No state-level data available.</Empty>
      </SectionCard>
    )
  }

  const { totals, states } = study3Latest
  const top10 = states.slice(0, 10)
  const maxDemand = Math.max(...top10.map((s) => s.max_demand_met_mw))
  const statesWithShortage = states.filter((s) => s.shortage_max_demand_mw > 0)

  return (
    <SectionCard
      title="State-Level Snapshot"
      subtitle="Latest date's per-state demand and shortage."
      accent="emerald"
    >
      <StatGrid>
        <StatCard value={fmtMW(totals.totalDemand)} label="Total demand (all states)" sub={totals.date} />
        <StatCard value={totals.stateCount} label="States/UTs reporting" />
        <StatCard
          value={totals.statesWithShortage}
          label="States with a shortage"
          tone={totals.statesWithShortage > 0 ? 'warning' : 'good'}
        />
        <StatCard
          value={totals.totalShortage > 0 ? fmtMW(totals.totalShortage) : '0 MW'}
          label="Total shortage"
          tone={totals.totalShortage > 0 ? 'warning' : 'good'}
        />
      </StatGrid>

      <div className="mt-5 rounded-2xl border border-white/8 bg-black/20 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">Top 10 states by demand met</div>
          <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
            {Object.entries(REGION_LIGHT).map(([r, c]) => (
              <span key={r} className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full" style={{ background: c }} />
                {r}
              </span>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          {top10.map((s) => (
            <div key={s.state} className="flex items-center gap-3">
              <div className="w-28 shrink-0 truncate text-xs text-slate-300">{s.state}</div>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${(s.max_demand_met_mw / maxDemand) * 100}%`, background: REGION_LIGHT[s.region] || '#34d399' }}
                />
              </div>
              <div className="w-20 shrink-0 text-right text-xs tabular-nums text-slate-400">
                {Math.round(s.max_demand_met_mw).toLocaleString('en-IN')}
              </div>
            </div>
          ))}
        </div>
      </div>

      {statesWithShortage.length > 0 && (
        <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/[0.04] p-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wider text-amber-300/80">States reporting a shortage</div>
          <div className="flex flex-wrap gap-2">
            {statesWithShortage.map((s) => (
              <span key={s.state} className="rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-2.5 py-1 text-xs text-amber-200">
                {s.state}: {Math.round(s.shortage_max_demand_mw).toLocaleString('en-IN')} MW
              </span>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
