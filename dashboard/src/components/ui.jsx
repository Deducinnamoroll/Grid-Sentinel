export function SectionCard({ title, subtitle, children, accent = 'sky' }) {
  const accentBorder = {
    sky: 'border-sky-500/15',
    amber: 'border-amber-500/15',
    violet: 'border-violet-500/15',
    rose: 'border-rose-500/15',
    emerald: 'border-emerald-500/15',
  }[accent]

  return (
    <section
      className={`rounded-3xl border ${accentBorder} bg-[#0d1016]/76 p-6 shadow-[0_0_0_1px_rgba(56,189,248,0.04)] backdrop-blur-sm sm:p-8`}
    >
      {title && (
        <div className="mb-5">
          <h2 className="text-lg font-semibold tracking-tight text-slate-50 sm:text-xl">{title}</h2>
          {subtitle && <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{subtitle}</p>}
        </div>
      )}
      {children}
    </section>
  )
}

export function StatCard({ label, value, sub, tone = 'default' }) {
  const toneClass = {
    default: 'text-slate-50',
    warning: 'text-amber-400',
    critical: 'text-rose-400',
    good: 'text-emerald-400',
  }[tone]

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/8 bg-[#0a0c11]/85 p-4 shadow-[0_12px_30px_rgba(0,0,0,0.18)] transition hover:-translate-y-0.5 hover:border-sky-400/25">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-white/[0.04] to-transparent" />
      <div className={`relative text-2xl font-semibold tabular-nums tracking-tight ${toneClass}`}>{value}</div>
      <div className="relative mt-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      {sub && <div className="relative mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  )
}

export function StatGrid({ children }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{children}</div>
}

export function Badge({ tone = 'info', children }) {
  const dot = { critical: 'bg-rose-400', warning: 'bg-amber-400', info: 'bg-slate-500', good: 'bg-emerald-400' }[tone]
  const text = { critical: 'text-rose-300', warning: 'text-amber-300', info: 'text-slate-400', good: 'text-emerald-300' }[tone]
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {children}
    </span>
  )
}

export function Empty({ children }) {
  return <div className="rounded-xl border border-white/6 bg-black/20 px-5 py-10 text-center text-sm text-slate-500">{children}</div>
}

export function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0c11]/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      <div className="mb-1 font-semibold text-slate-200">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-slate-400">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span>{p.name}:</span>
          <span className="font-medium text-slate-200">{formatter ? formatter(p.value, p.name) : p.value}</span>
        </div>
      ))}
    </div>
  )
}

// Inner chart container used across tabs: same bordered box the original
// panels draw inline, with an optional uppercase caption and right-side note.
export function ChartBox({ title, note, children, className = '' }) {
  return (
    <div className={`rounded-2xl border border-white/8 bg-black/20 p-4 ${className}`}>
      {(title || note) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs font-medium uppercase tracking-wider text-slate-500">
          <span>{title}</span>
          {note && <span className="normal-case tracking-normal text-slate-600">{note}</span>}
        </div>
      )}
      {children}
    </div>
  )
}

const PILL_TONES = {
  sky: 'border-sky-400/30 bg-sky-400/10 text-sky-200',
  amber: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  emerald: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  rose: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
  violet: 'border-violet-400/30 bg-violet-400/10 text-violet-200',
}

// Small segmented control, same look as the Historical Explorer's sub-tabs.
export function Pills({ options, value, onChange, tone = 'amber' }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          onClick={() => onChange(o.id)}
          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
            value === o.id
              ? PILL_TONES[tone]
              : 'border-white/8 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Select({ id, label, value, onChange, options }) {
  return (
    <div className="flex items-center gap-2">
      {label && (
        <label htmlFor={id} className="text-xs font-medium uppercase tracking-wider text-slate-500">
          {label}
        </label>
      )}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-200 outline-none transition focus:border-sky-400/40"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-[#0d1016]">
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}
