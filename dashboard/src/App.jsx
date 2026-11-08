import { lazy, Suspense, useEffect, useState } from 'react'
import Hero from './components/Hero'
import { useTabData, prefetch } from './lib/data'

// Each tab is its own JS chunk and its own JSON file (public/data/<id>.json),
// so opening the site only downloads what the Overview needs.
// Each tab carries the same accent as its section cards, plus a short hint
// shown on wide screens so the bar spans its width with something useful.
const TABS = [
  { id: 'overview', label: 'Overview', hint: "Today's grid", color: '#38bdf8', icon: 'M3 12h4l3-8 4 16 3-8h4', Component: lazy(() => import('./tabs/OverviewTab')) },
  { id: 'states', label: 'States', hint: 'Map and trends', color: '#34d399', icon: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14', Component: lazy(() => import('./tabs/StatesTab')) },
  { id: 'flows', label: 'Power flows', hint: 'Regions, borders', color: '#22d3ee', icon: 'M4 8h13l-3-3M20 16H7l3 3', Component: lazy(() => import('./tabs/FlowsTab')) },
  { id: 'renewables', label: 'Renewables', hint: 'Solar, wind, duck', color: '#fbbf24', icon: 'M12 3v2M12 19v2M5 12H3M21 12h-2M6.3 6.3 4.9 4.9M19.1 19.1l-1.4-1.4M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z', Component: lazy(() => import('./tabs/RenewablesTab')) },
  { id: 'reliability', label: 'Reliability', hint: 'Frequency, outages', color: '#fb7185', icon: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3zM9 12l2 2 4-4', Component: lazy(() => import('./tabs/ReliabilityTab')) },
  { id: 'models', label: 'Models', hint: 'Forecasts, risk', color: '#a78bfa', icon: 'M4 19V5M4 19h16M8 15l3-4 3 2 5-6', Component: lazy(() => import('./tabs/ModelsTab')) },
]

function tabFromHash() {
  const id = window.location.hash.replace('#', '')
  return TABS.some((t) => t.id === id) ? id : 'overview'
}

function TabIcon({ d, color }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

function TabBar({ active, onSelect }) {
  return (
    <nav
      aria-label="Dashboard sections"
      className="custom-scrollbar sticky top-3 z-20 -mx-1 overflow-x-auto rounded-2xl border border-white/8 bg-[#0b0e14]/85 p-1.5 shadow-[0_10px_30px_rgba(0,0,0,0.35)] backdrop-blur-md"
    >
      <div role="tablist" className="grid min-w-[720px] grid-cols-6 gap-1">
        {TABS.map((t) => {
          const on = active === t.id
          return (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={on}
              onClick={() => onSelect(t.id)}
              onMouseEnter={() => prefetch(t.id)}
              onFocus={() => prefetch(t.id)}
              className={`group relative flex items-center gap-2.5 overflow-hidden rounded-xl px-3 py-2 text-left transition ${
                on ? 'text-slate-50' : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
              }`}
              style={on ? { background: `${t.color}1f`, boxShadow: `inset 0 0 0 1px ${t.color}59` } : undefined}
            >
              <span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition"
                style={{ background: on ? `${t.color}33` : `${t.color}14` }}
              >
                <TabIcon d={t.icon} color={on ? t.color : `${t.color}b3`} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{t.label}</span>
                <span className={`hidden truncate text-[11px] lg:block ${on ? 'text-slate-400' : 'text-slate-600 group-hover:text-slate-500'}`}>
                  {t.hint}
                </span>
              </span>
              <span
                className="absolute inset-x-3 bottom-0 h-0.5 rounded-full transition-opacity"
                style={{ background: t.color, opacity: on ? 0.9 : 0 }}
              />
            </button>
          )
        })}
      </div>
    </nav>
  )
}

function Loading() {
  return (
    <div className="rounded-3xl border border-white/6 bg-[#0d1016]/60 px-5 py-16 text-center text-sm text-slate-500">Loading…</div>
  )
}

function App() {
  const [active, setActive] = useState(tabFromHash)
  const { data, error, status } = useTabData(active)
  const [asOf, setAsOf] = useState(null)

  useEffect(() => {
    const onHash = () => setActive(tabFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    if (data?.asOf) setAsOf((prev) => (prev && prev > data.asOf ? prev : data.asOf))
  }, [data])

  const select = (id) => {
    if (id === active) return
    // pushState rather than location.hash: no jump-to-anchor scroll.
    window.history.pushState(null, '', `#${id}`)
    setActive(id)
  }

  const { Component } = TABS.find((t) => t.id === active)

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.16),_transparent_60%),linear-gradient(180deg,_#0a0d13_0%,_#06070a_78%,_#030304_100%)] px-5 py-10 text-slate-200 sm:px-8 lg:px-14">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <Hero asOfDate={asOf} />
        <TabBar active={active} onSelect={select} />

        {status === 'error' && (
          <div className="rounded-2xl border border-amber-400/30 bg-amber-400/[0.06] px-5 py-3 text-center text-sm text-amber-300">
            Couldn't load this tab's data ({error}). Run{' '}
            <code className="rounded bg-white/10 px-1.5 py-0.5">python Pipeline/build_dashboard_data.py</code> to generate it.
          </div>
        )}
        {status === 'loading' && <Loading />}
        {status === 'ready' && (
          <Suspense fallback={<Loading />}>
            <div role="tabpanel" className="flex flex-col gap-6">
              <Component data={data} />
            </div>
          </Suspense>
        )}

        <footer className="mt-2 pb-6 text-center text-xs text-slate-600">
          Data and models:{' '}
          <a href="https://github.com/Deducinnamoroll/Grid-Sentinel" target="_blank" rel="noopener noreferrer" className="text-slate-500 underline decoration-white/20 hover:text-slate-300">
            Deducinnamoroll/Grid-Sentinel
          </a>{' '}
          · Dataset on{' '}
          <a
            href="https://www.kaggle.com/datasets/halcyonvector/india-power-grid-nldc-daily-psp-reports"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 underline decoration-white/20 hover:text-slate-300"
          >
            Kaggle
          </a>{' '}
          · Source: NLDC daily Power System Position reports
        </footer>
      </div>
    </main>
  )
}

export default App
