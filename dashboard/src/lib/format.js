export function fmtMW(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'N/A'
  return Math.round(v).toLocaleString('en-IN') + ' MW'
}

export function fmtPct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'N/A'
  return v.toFixed(digits) + '%'
}

export function fmtDateShort(dateStr) {
  const d = new Date(dateStr + 'T00:00:00Z')
  return d.toLocaleDateString('en-IN', { year: '2-digit', month: 'short', timeZone: 'UTC' })
}

export function fmtDateLong(dateStr) {
  const d = new Date(dateStr + 'T00:00:00Z')
  return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })
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
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits })
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
