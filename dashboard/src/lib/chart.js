// Shared Recharts axis/grid styling so every new chart matches the old ones.
export const AXIS = { stroke: 'rgba(255,255,255,0.3)', tick: { fill: '#64748b', fontSize: 11 } }
export const GRID = { stroke: 'rgba(255,255,255,0.06)', vertical: false }
// itemSorter null: legend follows series order (Recharts 3 sorts alphabetically by default).
export const LEGEND = { wrapperStyle: { fontSize: 12, color: '#94a3b8' }, itemSorter: null }

// Category axes of dates or months: Recharts picks which labels to show from
// their measured width, so they never run together. A fixed "every nth label"
// overlapped on phones (found 2026-11-23 in 12 charts at 375 px).
export const DATE_AXIS = { interval: 'preserveStartEnd', minTickGap: 16 }
// The 96 fifteen-minute slots of a day: a label every three hours, and the
// ones that would overlap are skipped, so a phone shows every six hours.
export const TIME_AXIS = {
  ticks: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00'],
  interval: 'preserveStart',
  minTickGap: 12,
}
