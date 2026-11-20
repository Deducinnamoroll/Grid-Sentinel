const REPO = 'https://github.com/Deducinnamoroll/Grid-Sentinel'

function Link({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-slate-300 underline decoration-white/20 underline-offset-2 hover:text-sky-300 hover:decoration-sky-300/50">
      {children}
    </a>
  )
}

function Column({ title, children }) {
  return (
    <div className="min-w-0">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">{title}</div>
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

export default function Footer() {
  return (
    <footer className="mt-4 rounded-3xl border border-white/5 bg-[#0d1016]/60 px-6 py-5 text-xs leading-relaxed text-slate-500 sm:px-8">
      <div className="grid gap-5 sm:grid-cols-3 sm:gap-8">
        <Column title="About">
          <p>
            Tracks India's national grid from NLDC's daily reports, with forecasts scored against what actually happened.
            An independent student project, not affiliated with Grid-India; figures are as reported and can be revised.
          </p>
          <p><Link href={REPO}>Source code on GitHub</Link></p>
        </Column>
        <Column title="Data">
          <p>
            <Link href="https://grid-india.in/en/reports/daily-psp-report">NLDC / Grid-India daily PSP reports</Link>: daily, 15-minute and state-level figures behind every chart.
          </p>
          <p>
            <Link href="https://github.com/vacanza/holidays">python-holidays</Link>: India's gazetted holidays for the forecast's holiday correction.
          </p>
          <p>
            <Link href="https://github.com/VictorCazanave/svg-maps/tree/master/packages/india">@svg-maps/india</Link> by Victor Cazanave (CC BY 4.0): state outlines for the map.
          </p>
          <p>
            <Link href="https://www.kaggle.com/datasets/halcyonvector/india-power-grid-nldc-daily-psp-reports">Kaggle dataset</Link>: the cleaned data this page is built from, updated daily.
          </p>
        </Column>
        <Column title="References">
          <p>
            <Link href="https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html">Ke et al. (2017), LightGBM</Link>: the model behind the demand forecasts and risk scores.
          </p>
          <p>
            <Link href="https://scikit-learn.org/stable/modules/calibration.html">Probability calibration (Platt scaling)</Link>: how risk scores are turned into event rates.
          </p>
        </Column>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-y-1 border-t border-white/5 pt-4 text-slate-500">
        <span>
          Built by <strong className="font-semibold text-slate-300">Sagnik</strong>{' '}
          (<Link href="https://github.com/HalcyonVector">@HalcyonVector</Link>) and{' '}
          <strong className="font-semibold text-slate-300">Abhirami</strong>{' '}
          (<Link href="https://github.com/menaegerie">@menaegerie</Link>)
        </span>
        <span className="mx-2.5 text-slate-600" aria-hidden="true">·</span>
        <Link href={REPO}>Repository</Link>
        <span className="mx-2.5 text-slate-600" aria-hidden="true">·</span>
        <Link href={`${REPO}/blob/main/LICENSE`}>MIT License</Link>
      </div>
    </footer>
  )
}
