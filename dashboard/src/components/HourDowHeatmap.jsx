import { Fragment } from 'react'

const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function Grid({ title, hours, values, colorFrom, colorTo, formatter }) {
  const flat = values.flat()
  const max = Math.max(...flat)
  const min = Math.min(...flat)

  const cellColor = (v) => {
    const t = max === min ? 0.5 : (v - min) / (max - min)
    return `color-mix(in srgb, ${colorFrom} ${(1 - t) * 100}%, ${colorTo} ${t * 100}%)`
  }

  return (
    <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">{title}</div>
      <div className="overflow-x-auto">
        <div className="inline-grid gap-[2px]" style={{ gridTemplateColumns: `32px repeat(${hours.length}, 1fr)` }}>
          <div />
          {hours.map((h) => (
            <div key={h} className="text-center text-[10px] text-slate-600">
              {h % 3 === 0 ? h : ''}
            </div>
          ))}
          {values.map((row, i) => (
            <Fragment key={i}>
              <div className="flex items-center text-[10px] text-slate-500">{DOW_LABELS[i]}</div>
              {row.map((v, j) => (
                <div
                  key={`${i}-${j}`}
                  title={`${DOW_LABELS[i]} ${hours[j]}:00, ${formatter(v)}`}
                  className="aspect-square min-w-[10px] rounded-[2px]"
                  style={{ background: cellColor(v) }}
                />
              ))}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function HourDowHeatmap({ heatmap }) {
  if (!heatmap) return null
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Grid
        title="Violation rate: hour x day-of-week"
        hours={heatmap.hours}
        values={heatmap.violation}
        colorFrom="#1a0a12"
        colorTo="#fb7185"
        formatter={(v) => (v * 100).toFixed(2) + '%'}
      />
      <Grid
        title="Ramp-shock rate: hour x day-of-week"
        hours={heatmap.hours}
        values={heatmap.ramp}
        colorFrom="#08131f"
        colorTo="#38bdf8"
        formatter={(v) => (v * 100).toFixed(2) + '%'}
      />
    </div>
  )
}
