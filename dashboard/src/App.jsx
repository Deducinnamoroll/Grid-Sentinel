import { useEffect, useState } from 'react'
import Hero from './components/Hero'
import LiveStatus from './components/LiveStatus'
import StatePanel from './components/StatePanel'
import ForecastPanel from './components/ForecastPanel'
import RiskPanel from './components/RiskPanel'
import HistoricalExplorer from './components/HistoricalExplorer'
import ResearchFindings from './components/ResearchFindings'
import AnomalyLog from './components/AnomalyLog'

const EMPTY_DATA = {
  dailySlim: [],
  era1Monthly: [],
  era2CorridorCorr: [],
  forecast: [],
  risk: [],
  hourDowHeatmap: null,
  monthSeasonality: [],
  solarHourRates: null,
  resShareFindings: null,
  featureImportance: null,
  study3Latest: null,
}

function App() {
  const [data, setData] = useState(EMPTY_DATA)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/data/dashboard.json')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((json) => {
        setData(json)
        setStatus('ready')
      })
      .catch((err) => {
        setError(err.message)
        setStatus('error')
      })
  }, [])

  const asOfDate = data.dailySlim.length ? data.dailySlim[data.dailySlim.length - 1].date : null

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.16),_transparent_60%),linear-gradient(180deg,_#0a0d13_0%,_#06070a_78%,_#030304_100%)] px-5 py-10 text-slate-200 sm:px-8 lg:px-14">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <Hero asOfDate={status === 'ready' ? asOfDate : null} />

        {status === 'error' && (
          <div className="rounded-2xl border border-amber-400/30 bg-amber-400/[0.06] px-5 py-3 text-center text-sm text-amber-300">
            Couldn't load dashboard data ({error}). Run <code className="rounded bg-white/10 px-1.5 py-0.5">python Pipeline/build_dashboard_data.py</code> to generate it.
          </div>
        )}

        <LiveStatus dailySlim={data.dailySlim} />
        <StatePanel study3Latest={data.study3Latest} />
        <ForecastPanel forecast={data.forecast} />
        <RiskPanel risk={data.risk} />
        <HistoricalExplorer dailySlim={data.dailySlim} era1Monthly={data.era1Monthly} era2CorridorCorr={data.era2CorridorCorr} />
        <ResearchFindings
          hourDowHeatmap={data.hourDowHeatmap}
          monthSeasonality={data.monthSeasonality}
          solarHourRates={data.solarHourRates}
          resShareFindings={data.resShareFindings}
          featureImportance={data.featureImportance}
        />
        <AnomalyLog forecast={data.forecast} risk={data.risk} thresholds={data.featureImportance?.thresholds} />

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
