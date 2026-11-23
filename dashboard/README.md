# Grid-Sentinel Dashboard

React + Vite + Tailwind + Recharts. Static site, no backend. The page is split
into six tabs; each tab fetches its own small JSON file from `public/data/`
the first time it is opened, and renders everything client-side.

## Local development

```bash
npm install
npm run dev
```

The JSON files in `public/data/` are committed to the repo (rebuilt daily by
CI), so `npm run dev` works out of the box without running anything else
first. Both commands serve on **port 1001** (set in `vite.config.js`).

To check exactly what a deploy will actually look like (the same static
build Vercel serves, not the dev server):

```bash
npm run build
npm run preview
```

Each tab has its own URL hash (`/#states`, `/#models`, ...), so a tab can be
linked to directly.

## Regenerating the data files

`public/data/*.json` is generated from the main dataset by
`Pipeline/build_dashboard_data.py` (run from the repo root, needs
`pandas`/`numpy`/`scikit-learn`/`lightgbm`):

```bash
python Pipeline/build_dashboard_data.py
```

This is wired into `.github/workflows/daily_scrape.yml`, so it refreshes
automatically whenever new PSP data lands. You only need to run it by hand
if you're testing a change to the aggregation logic itself. What goes into
each file, and why, is in `Pipeline/docs/build_dashboard_data_notes.md`.

## Deploying to Vercel

Live at [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/).

1. [Import this repo on Vercel](https://vercel.com/new).
2. Set **Root Directory** to `dashboard`.
3. Framework preset should auto-detect as **Vite**: build command
   `npm run build`, output directory `dist`. No environment variables needed.
4. Deploy. Every push to `main` that touches `dashboard/` (or CI's daily data
   commit) triggers a new deployment automatically.

## What each tab shows

| Tab | Data file | Panels |
|---|---|---|
| **Overview** | `overview.json` (~77 KB) | Live Grid Status and the latest day's generation mix; Historical Explorer (2019-present demand and RES share, Era 1 ramp trend, Era 2 corridor-stress correlation). |
| **States** | `states.json` (~76 KB) | India choropleth (energy, peak demand, year-on-year growth or shortage over the last 365 days) with a ranked list; monthly trend for any state or grid entity since 2019; the latest-day state snapshot; non-state grid entities (DVC, Railways, bulk consumers). |
| **Power flows** | `flows.json` (~108 KB) | Diagram of net flows between the five regions on the latest day; daily flow on each inter-regional corridor since 2023 with a 30-day mean; cross-border exchange with Bhutan, Nepal, Bangladesh and Myanmar since July 2023. |
| **Renewables** | `renewables.json` (~47 KB) | Records and headline numbers; monthly solar/wind/hydro generation; RES and non-fossil share; yearly averages; regional split; the duck curve (average 15-min demand, solar and net demand for any month since Nov 2024, against the same month a year earlier). |
| **Reliability** | `reliability.json` (~148 KB) | Time in each frequency band; daily frequency variation index; forced outages and energy shortage by region; a year-by-year table. |
| **Models** | `models.json` (~281 KB) | Study 1 forecast vs actual, plus forecast accuracy (daily error, 7-day MAPE, error histogram); Study 2 risk timeline for any logged day, plus calibration of the risk scores against what happened; Anomaly Log; Research Findings (EDA and feature importance). |

Sizes are uncompressed; gzipped (as Vercel serves them) each file is about
20 to 50 KB. The old single `dashboard.json` was ~2.5 MB and loaded in full on
every visit; now a first visit loads only the Overview file. The Models
tab's 15-minute risk log is stored grouped by day as arrays, which is about
a fifth of its old row-by-row size.

`study1_hourly.csv` (36MB), `study2_scada.csv` (70MB joined) and
`study3_states.csv` are never fetched by the browser.

### Notes on the data shown

- **Corridor direction.** `ir_<a>_<b>_net_mu` is import minus export from
  region A's side, so a negative value means power flowed A to B. The Power
  flows tab flips the sign so that "A to B" reads as positive.
- **Partial months.** Monthly series are per-day averages, so the current,
  month-to-date bar or point is directly comparable with full months.
- **Masked source glitches.** The build blanks a handful of values that are
  clearly parse errors in the source data (a few days where `share_res_pct`
  disagrees with `gen_res_mu / gen_total_mu`, and one day where `freq_fvi`
  reads 49.2). The datasets themselves are untouched; the build log lists
  the dates.

### Map credit

The States tab map is [`@svg-maps/india`](https://github.com/VictorCazanave/svg-maps/tree/master/packages/india)
by Victor Cazanave, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
recoloured. The credit also appears under the map on the page.

### Keeping scrolling and tab switches smooth

Measured on 2026-11-20 with a headless Chrome script that scrolls and switches
tabs as fast as a reader can. Each change below fixed a freeze it found.

- Every visited tab stays mounted, hidden, so going back to it costs nothing.
- Lower sections are wrapped in `LazyMount` (`src/components/ui.jsx`) and
  built only as they come near the screen, one at a time and nearest first.
  Each section waits until its charts have drawn before the next one starts,
  because each Recharts chart ends with a pass React cannot pause, and
  building several at once froze the page for up to 1.5 s.
- Chart animations are off (`isAnimationActive={false}` on every series):
  an animating chart redraws on every frame while the reader scrolls.
- The number and date formatters in `src/lib/format.js` reuse one `Intl`
  formatter each. Building a new one per call cost 1.2 s in the test, the
  largest single item.

Result at normal CPU speed: the longest freeze while switching tabs fast went
from 1.1 s to 0.3 s and total blocking time roughly halved. The daily charts
with a zoom strip (full history, corridor flows, frequency variation index)
still plot every day of 4 to 8 years and are the slowest sections left.

### Phone layout

Checked on 2026-11-23 at 320, 375, 768 and 1280 px wide with a headless Chrome
script that opens every tab, scrolls it at reading speed and checks for
anything wider than the screen, overlapping axis labels, text under 10 px and
buttons under 28 px. All four widths pass. What it found and fixed:

- Date axes used a fixed "every nth label" spacing, which ran together on a
  phone in 12 charts. They now use `DATE_AXIS` from `src/lib/chart.js`, where
  Recharts drops the labels that would overlap; 15-minute day axes use
  `TIME_AXIS` (every 3 hours, every 6 on a phone).
- The peak-hour heatmap had a 640 px minimum width, so on a phone the midday
  and evening peaks were off-screen. It now fits the screen.
- Chart boxes get `min-w-0`, so a chart in a two-column grid measures its own
  column rather than its content.
- The "Other grid entities" table scrolls instead of wrapping numbers, the
  region filter buttons are taller, and the footer's links take their own
  line on a phone.

### Colours

Multi-series charts use one fixed categorical order (`src/lib/colors.js`),
checked for lightness, colour-blind separation and contrast against the
dark card surface. Regions and countries always keep the same colour.
