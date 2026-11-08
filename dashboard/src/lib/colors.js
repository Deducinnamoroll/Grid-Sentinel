// Categorical order for multi-series charts, validated with the dataviz
// skill's validate_palette.js against the card surface #0d1016 (dark mode):
// lightness band, chroma, adjacent-pair CVD and normal-vision separation and
// contrast all PASS. Assign in this fixed order, never cycled; a filter that
// hides a series must not repaint the others (colour follows the entity).
export const CAT = ['#0284c7', '#d97706', '#8b5cf6', '#059669', '#f43f5e']

export const REGION_COLORS = { NR: CAT[0], WR: CAT[1], SR: CAT[2], ER: CAT[3], NER: CAT[4] }
export const COUNTRY_COLORS = { bhutan: CAT[0], nepal: CAT[1], bangladesh: CAT[2], myanmar: CAT[3] }
export const SOURCE_COLORS = { solar: CAT[1], wind: CAT[0], hydro: CAT[2] }

function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function mix(a, b, t) {
  const A = hexToRgb(a)
  const B = hexToRgb(b)
  const c = A.map((v, i) => Math.round(v + (B[i] - v) * t))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

// Sequential: one hue, dark (low) -> bright (high) on the dark surface.
const SEQ_LOW = '#12302a'
const SEQ_HIGH = '#6ee7b7'
export function sequential(t) {
  return mix(SEQ_LOW, SEQ_HIGH, Math.max(0, Math.min(1, t)))
}
export const SEQ_GRADIENT = `linear-gradient(90deg, ${SEQ_LOW}, ${SEQ_HIGH})`

// Diverging: rose (negative) <- neutral slate -> sky (positive).
const DIV_NEG = '#fb7185'
const DIV_MID = '#334155'
const DIV_POS = '#38bdf8'
export function diverging(t) {
  // t in [-1, 1]
  const c = Math.max(-1, Math.min(1, t))
  return c < 0 ? mix(DIV_MID, DIV_NEG, -c) : mix(DIV_MID, DIV_POS, c)
}
export const DIV_GRADIENT = `linear-gradient(90deg, ${DIV_NEG}, ${DIV_MID}, ${DIV_POS})`

export const NO_DATA = '#1b2029'
