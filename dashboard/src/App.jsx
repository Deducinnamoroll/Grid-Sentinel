import { lazy, Suspense, useEffect, useState } from 'react'
import Hero from './components/Hero'
import { useTabData, prefetch } from './lib/data'

// Each tab is its own JS chunk and its own JSON file (public/data/<id>.json),
// so opening the site only downloads what the Overview needs.
const TABS = [
  { id: 'overview', label: 'Overview', Component: lazy(() => import('./tabs/OverviewTab')) },
  { id: 'states', label: 'States', Component: lazy(() => import('./tabs/StatesTab')) },
  { id: 'flows', label: 'Power flows', Component: lazy(() => import('./tabs/FlowsTab')) },
  { id: 'renewables', label: 'Renewables', Component: lazy(() => import('./tabs/RenewablesTab')) },
  { id: 'reliability', label: 'Reliability', Component: lazy(() => import('./tabs/ReliabilityTab')) },
  { id: 'models', label: 'Models', Component: lazy(() => import('./tabs/ModelsTab')) },
]

function tabFromHash() {
  const id = window.location.hash.replace('#', '')
  return TABS.some((t) => t.id === id) ? id : 'overview'
}

function TabBar({ active, onSelect }) {
  return (
    <nav
      aria-label="Dashboard sections"
      className="sticky top-3 z-20 -mx-1 overflow-x-auto rounded-2xl border border-white/8 bg-[#0b0e14]/85 p-1.5 shadow-[0_10px_30px_rgba(0,0,0,0.35)] backdrop-blur-md"
    >
      <div role="tablist" className="flex min-w-max gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={active === t.id}
            onClick={() => onSelect(t.id)}
            onMouseEnter={() => prefetch(t.id)}
            onFocus={() => prefetch(t.id)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              active === t.id
                ? 'bg-sky-400/15 text-sky-100 shadow-[inset_0_0_0_1px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
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
