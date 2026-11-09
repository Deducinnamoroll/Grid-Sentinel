import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import Hero from './components/Hero'
import { loadData, peekData } from './lib/data'

// Each tab is its own JS chunk and its own JSON file (public/data/<id>.json),
// so opening the site only downloads what the first tab needs. The rest are
// fetched in the background once it is on screen.
// Each tab carries the same accent as its section cards, plus a short hint
// shown on wide screens so the bar spans its width with something useful.
const TABS = [
  { id: 'overview', label: 'Overview', hint: "Today's grid", color: '#38bdf8', icon: 'M3 12h4l3-8 4 16 3-8h4', load: () => import('./tabs/OverviewTab') },
  { id: 'states', label: 'States', hint: 'Map and trends', color: '#34d399', icon: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14', load: () => import('./tabs/StatesTab') },
  { id: 'flows', label: 'Power flows', hint: 'Regions, borders', color: '#22d3ee', icon: 'M4 8h13l-3-3M20 16H7l3 3', load: () => import('./tabs/FlowsTab') },
  { id: 'renewables', label: 'Renewables', hint: 'Solar, wind, duck', color: '#fbbf24', icon: 'M12 3v2M12 19v2M5 12H3M21 12h-2M6.3 6.3 4.9 4.9M19.1 19.1l-1.4-1.4M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z', load: () => import('./tabs/RenewablesTab') },
  { id: 'reliability', label: 'Reliability', hint: 'Frequency, outages', color: '#fb7185', icon: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3zM9 12l2 2 4-4', load: () => import('./tabs/ReliabilityTab') },
  { id: 'models', label: 'Models', hint: 'Forecasts, risk', color: '#a78bfa', icon: 'M4 19V5M4 19h16M8 15l3-4 3 2 5-6', load: () => import('./tabs/ModelsTab') },
]

// Tab code, cached the same way as tab data: a promise while loading, then the
// component itself so a revisit renders in the same frame.
const modPending = new Map()
const modReady = new Map()

function loadModule(tab) {
  if (!modPending.has(tab.id)) {
    const p = tab.load().then((m) => m.default)
    p.then(
      (C) => modReady.set(tab.id, C),
      () => modPending.delete(tab.id),
    )
    modPending.set(tab.id, p)
  }
  return modPending.get(tab.id)
}

function loadTab(tab) {
  return Promise.all([loadModule(tab), loadData(tab.id)])
}

function instantView(id) {
  const Component = modReady.get(id)
  const data = peekData(id)
  return Component && data ? { id, Component, data } : null
}

function tabFromHash() {
  const id = window.location.hash.replace('#', '')
  return TABS.some((t) => t.id === id) ? id : 'overview'
}

// Keeps the last fully loaded tab on screen until the next one has both its
// code and its data, so switching never collapses the page into a spinner.
function useTabView(active) {
  const [view, setView] = useState(() => instantView(active))
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setError(null)
    loadTab(TABS.find((t) => t.id === active))
      .then(([Component, data]) => alive && setView({ id: active, Component, data }))
      .catch((err) => alive && setError(err.message))
    return () => {
      alive = false
    }
  }, [active])

  // Already cached: show it now rather than one effect later.
  const shown = view?.id === active ? view : instantView(active) || view
  return { shown, pending: !error && shown?.id !== active, error }
}

function TabIcon({ d, color }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 transition-colors duration-300" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

function TabBar({ active, pending, onSelect }) {
  const btnRefs = useRef({})
  const [pill, setPill] = useState(null)
  const activeTab = TABS.find((t) => t.id === active)

  // One highlight that slides between tabs instead of each tab toggling its own.
  useLayoutEffect(() => {
    const measure = () => {
      const el = btnRefs.current[active]
      if (el) setPill({ x: el.offsetLeft, w: el.offsetWidth })
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [active])

  return (
    <nav
      aria-label="Dashboard sections"
      className="custom-scrollbar sticky top-3 z-20 -mx-1 overflow-x-auto rounded-2xl border border-white/8 bg-[#0b0e14]/85 p-1.5 shadow-[0_10px_30px_rgba(0,0,0,0.35)] backdrop-blur-md"
    >
      <div role="tablist" className="relative grid min-w-[720px] grid-cols-6 gap-1">
        {pill && (
          <span
            aria-hidden="true"
            className="tab-pill pointer-events-none absolute inset-y-0 left-0 rounded-xl"
            style={{
              width: pill.w,
              transform: `translateX(${pill.x}px)`,
              background: `${activeTab.color}1f`,
              boxShadow: `inset 0 0 0 1px ${activeTab.color}59`,
            }}
          >
            <span className="absolute inset-x-3 bottom-0 h-0.5 overflow-hidden rounded-full" style={{ background: `${activeTab.color}e6` }}>
              {pending && <span className="tab-progress absolute inset-y-0 w-1/3 bg-white/80" />}
            </span>
          </span>
        )}
        {TABS.map((t) => {
          const on = active === t.id
          return (
            <button
              key={t.id}
              ref={(el) => (btnRefs.current[t.id] = el)}
              role="tab"
              type="button"
              aria-selected={on}
              aria-busy={on && pending}
              onClick={() => onSelect(t.id)}
              onMouseEnter={() => loadTab(t).catch(() => {})}
              onFocus={() => loadTab(t).catch(() => {})}
              className={`group relative flex items-center gap-2.5 overflow-hidden rounded-xl px-3 py-2 text-left transition-colors duration-300 ${
                on ? 'text-slate-50' : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
              }`}
            >
              <span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-[background-color,transform] duration-300 group-active:scale-90"
                style={{ background: on ? `${t.color}33` : `${t.color}14` }}
              >
                <TabIcon d={t.icon} color={on ? t.color : `${t.color}b3`} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{t.label}</span>
                <span className={`hidden truncate text-[11px] transition-colors duration-300 lg:block ${on ? 'text-slate-400' : 'text-slate-600 group-hover:text-slate-500'}`}>
                  {t.hint}
                </span>
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}

// Shown only on the very first load, shaped like the cards it stands in for.
function Skeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading">
      {[0, 1].map((i) => (
        <div key={i} className="rounded-3xl border border-white/6 bg-[#0d1016]/76 p-6 sm:p-8">
          <div className="skeleton h-5 w-48 rounded-md" />
          <div className="skeleton mt-3 h-3 w-80 max-w-full rounded" />
          {i === 0 ? (
            <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[0, 1, 2, 3].map((j) => (
                <div key={j} className="skeleton h-20 rounded-2xl" />
              ))}
            </div>
          ) : (
            <div className="skeleton mt-6 h-64 rounded-2xl" />
          )}
        </div>
      ))}
    </div>
  )
}

function App() {
  const [active, setActive] = useState(tabFromHash)
  const { shown, pending, error } = useTabView(active)
  const [asOf, setAsOf] = useState(null)
  const navAnchor = useRef(null)

  useEffect(() => {
    const onHash = () => setActive(tabFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    const d = shown?.data?.asOf
    if (d) setAsOf((prev) => (prev && prev > d ? prev : d))
  }, [shown])

  // Once the first tab is on screen, fetch the others while the browser is
  // idle, so later switches are instant. About 750 KB in total, before gzip.
  const firstShown = Boolean(shown)
  useEffect(() => {
    if (!firstShown) return
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1200))
    const cancel = window.cancelIdleCallback || clearTimeout
    const handle = idle(() => TABS.forEach((t) => loadTab(t).catch(() => {})))
    return () => cancel(handle)
  }, [firstShown])

  const select = (id) => {
    if (id === active) return
    // pushState rather than location.hash: no jump-to-anchor scroll.
    window.history.pushState(null, '', `#${id}`)
    setActive(id)
    // If the reader is deep in a long tab, bring the new tab's top into view.
    const top = navAnchor.current?.getBoundingClientRect().top ?? 0
    if (top < 0) window.scrollBy({ top: top - 12, behavior: 'smooth' })
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.16),_transparent_60%),linear-gradient(180deg,_#0a0d13_0%,_#06070a_78%,_#030304_100%)] px-5 py-10 text-slate-200 sm:px-8 lg:px-14">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="fade-in">
          <Hero asOfDate={asOf} />
        </div>
        <div ref={navAnchor} className="-mb-6 h-0" aria-hidden="true" />
        <TabBar active={active} pending={pending} onSelect={select} />

        {error && (
          <div className="rounded-2xl border border-amber-400/30 bg-amber-400/[0.06] px-5 py-3 text-center text-sm text-amber-300">
            Couldn't load this tab ({error}). Run{' '}
            <code className="rounded bg-white/10 px-1.5 py-0.5">python Pipeline/build_dashboard_data.py</code> to generate its data.
          </div>
        )}
        {!shown && !error && <Skeleton />}
        {shown && (
          <div
            key={shown.id}
            role="tabpanel"
            className={`tab-enter flex flex-col gap-6 transition-opacity duration-200 ${pending ? 'opacity-50' : 'opacity-100'}`}
          >
            <shown.Component data={shown.data} />
          </div>
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
