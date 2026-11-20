// Intl formatters are built once and reused. toLocaleString/toLocaleDateString
// with options build a new formatter on every call, and charts call these for
// every point and tick: on 2026-11-20 fmtDateShort alone took 1.2 s of a
// fast tab-switching test, the largest single cost on the page.
const intInt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const numFmts = new Map()
function numFmt(digits) {
  let f = numFmts.get(digits)
  if (!f) {
    f = new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits })
    numFmts.set(digits, f)
  }
  return f
}
const monthYear = new Intl.DateTimeFormat('en-IN', { year: '2-digit', month: 'short', timeZone: 'UTC' })
const dayMonthYear = new Intl.DateTimeFormat('en-IN', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })
const shortCache = new Map()
const dayMonth = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' })

export function fmtMW(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'N/A'
  return intInt.format(Math.round(v)) + ' MW'
}

export function fmtPct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'N/A'
  return v.toFixed(digits) + '%'
}

export function fmtDateShort(dateStr) {
  let out = shortCache.get(dateStr)
  if (out === undefined) {
    out = monthYear.format(new Date(dateStr + 'T00:00:00Z'))
    shortCache.set(dateStr, out)
  }
  return out
}

export function fmtDateLong(dateStr) {
  const d = new Date(dateStr + 'T00:00:00Z')
  return dayMonthYear.format(d)
}

export function index0to100(values) {
  const finite = values.filter((v) => v !== null && v !== undefined && Number.isFinite(v))
  const min = Math.min(...finite)
  const max = Math.max(...finite)
  return values.map((v) => (v === null || v === undefined ? null : max === min ? 50 : ((v - min) / (max - min)) * 100))
}

export function shortCorridorName(name) {
  return name.replace('ir_', '').replace('_net_mu', '').replace('xb_net_', '').replace(/_/g, '-')
}

// "2026-11" -> "Nov 26"
export function fmtMonth(ym) {
  return fmtDateShort(ym + '-01')
}

export function fmtNum(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'N/A'
  return numFmt(digits).format(Number(v))
}

export function fmtMU(v, digits = 0) {
  return v === null || v === undefined || Number.isNaN(v) ? 'N/A' : fmtNum(v, digits) + ' MU'
}

export const REGION_NAMES = { NR: 'Northern', WR: 'Western', SR: 'Southern', ER: 'Eastern', NER: 'North-Eastern' }

// Percentage axis tick. A raw `v + '%'` printed float noise such as
// "100.00200000000001%" when stacked monthly averages summed just over 100.
export function pctTick(v) {
  return `${Number(Number(v).toFixed(1))}%`
}

// "2026-11-20" -> "20 Nov"
export function fmtDayMonth(dateStr) {
  return dayMonth.format(new Date(dateStr + 'T00:00:00Z'))
}
