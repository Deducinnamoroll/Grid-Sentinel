// One JSON file per tab (built by Pipeline/build_dashboard_data.py), fetched
// the first time a tab opens and kept for the rest of the visit.
const pending = new Map()
const ready = new Map()

export function loadData(name) {
  if (!pending.has(name)) {
    const p = fetch(`/data/${name}.json`).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${name}.json`)
      return res.json()
    })
    // A failed fetch must not stay cached, or a retry would never refetch.
    p.then(
      (d) => ready.set(name, d),
      () => pending.delete(name),
    )
    pending.set(name, p)
  }
  return pending.get(name)
}

// The data if it has already arrived, so a revisited tab renders in the same
// frame instead of flashing a loading state.
export function peekData(name) {
  return ready.get(name)
}

// {"date": [...], "x": [...]} -> [{date, x}, ...]
export function zipColumns(cols) {
  if (!cols) return []
  const keys = Object.keys(cols)
  const n = keys.length ? cols[keys[0]].length : 0
  const rows = new Array(n)
  for (let i = 0; i < n; i++) {
    const row = {}
    for (const k of keys) row[k] = cols[k][i]
    rows[i] = row
  }
  return rows
}

// models.json groups the 15-min risk log by day; expand it back into the
// row shape RiskPanel and AnomalyLog were written against.
export function expandRisk(byDay) {
  if (!byDay) return []
  const rows = []
  for (const date of Object.keys(byDay).sort()) {
    const d = byDay[date]
    for (let i = 0; i < d.t.length; i++) {
      rows.push({
        date,
        time: d.t[i],
        violation_prob: d.v[i],
        ramp_prob: d.r[i],
        actual_violation: d.av[i],
        actual_ramp: d.ar[i],
      })
    }
  }
  return rows
}
