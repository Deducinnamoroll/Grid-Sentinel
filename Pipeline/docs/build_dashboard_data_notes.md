# Notes: build_dashboard_data.py

**Script:** `Pipeline/build_dashboard_data.py`
**Purpose:** Precompute the small JSON files the dashboard (`dashboard/`) loads, one per dashboard tab, from the full datasets and the two model prediction logs.

---

## In plain English

The dashboard is a static website with no server behind it, so anything it shows has to be sitting in a file the browser can download. The real datasets are far too big for that (the 15-minute SCADA file alone is 60 MB). This script reads the big files once, works out exactly the numbers each chart needs (monthly averages, the latest day, a 365-day summary per state, and so on), and writes them out as six small files, one for each tab of the dashboard. A visitor only downloads the file for the tab they open.

---

## When to run

CI runs it every day in `.github/workflows/daily_scrape.yml` (step "Build dashboard data"), right after the two `predict.py` steps, and commits everything under `dashboard/public/data/`. Run it by hand only when changing what a tab shows:

```
python Pipeline/build_dashboard_data.py
```

It takes about 15 to 20 seconds locally. Most of that is reloading the SCADA file and retraining the three models for feature importance.

---

## Inputs

| File | Used for |
|------|----------|
| `Dataset/study1_daily.csv` | Overview, Power flows, Renewables, Reliability |
| `Dataset/study1_hourly.csv` | Era 1 monthly ramp table (Overview) |
| `Dataset/study2_scada.csv` | Duck curve (Renewables), EDA findings and feature importance (Models) |
| `Dataset/study3_states.csv` | States |
| `Dataset/predictions/study1_forecast.csv` | Models: forecast and accuracy |
| `Dataset/predictions/study2_risk.csv` | Models: risk timeline, calibration, anomaly log |

---

## Outputs (`dashboard/public/data/`)

| File | Approx. size | Contents |
|------|--------------|----------|
| `overview.json` | 77 KB | `latest` (last two days of the slim daily columns), `history` (date, peak demand, RES share since 2019), `era1Monthly`, `era2CorridorCorr` |
| `states.json` | 76 KB | `totals` (latest day), `entities` (one summary per state/UT/grid entity over the last 365 days), `months` + `history` (monthly peak, average daily energy, average daily shortage per entity) |
| `flows.json` | 108 KB | `daily` (7 corridor nets + 4 country nets), `irMonthly`, `xbMonthly` (import and export per country), `irLatest`, `xbLatest` |
| `renewables.json` | 47 KB | `monthly` (solar, wind, hydro, RES, total, shares), `yearly`, `regional` (last 365 days), `duck` (average 15-min profile per month), `records` |
| `reliability.json` | 148 KB | `daily` (FVI, frequency bands, forced outage, shortage), `outageMonthly`, `shortageMonthly` (by region), `yearly` |
| `models.json` | 281 KB | `forecast`, `risk` (grouped by day), `calibration`, `featureImportance`, `hourDowHeatmap`, `monthSeasonality`, `solarHourRates`, `resShareFindings` |

Every file has an `asOf` date. Before 2026-11-08 the script wrote one `dashboard.json` (~2.5 MB) that every visitor downloaded in full; the script now deletes that file if it finds it.

**Format choices that keep the files small:**
- Long series are columnar: `{"date": [...], "demand": [...]}` instead of a list of `{date, demand}` objects, so key names are not repeated thousands of times. The frontend turns them back into rows (`zipColumns` in `dashboard/src/lib/data.js`).
- Values are rounded to what the charts can show (MW to whole numbers, percentages to 2 decimals, probabilities to 4).
- The risk log is grouped by day as parallel arrays (`t`, `v`, `r`, `av`, `ar`), about a fifth of its old size. `expandRisk` in `data.js` rebuilds the original rows so `RiskPanel` and `AnomalyLog` did not need changing.
- JSON is written without spaces and with `allow_nan=False`, so a stray NaN fails the build instead of producing a file browsers cannot parse.

---

## Decisions worth knowing

**Monthly series are per-day averages, not sums.** The current month is always partial; a monthly sum would show a fake dip at the end of every chart. Averages compare fairly.

**Corridor sign convention.** `ir_<a>_<b>_net_mu` is import minus export from region A's side, so a negative value means power flowed from A to B. This was checked against the parser (`_xls_parse_ir_line` reads the IR-Line sheet's import/export columns for the named pair) and against the physics: WR to SR, ER to SR and ER to NR show up as large daily exports from the first region, as expected. The dashboard flips the sign so "A to B" is positive. The `Dataset/data_dictionary.xlsx` note for these columns says "positive = net import by the destination region", which reads as the opposite; see Known issues.

**Cross-border sign.** `xb_net_<country>_mu` is import minus export from India's side: positive means India imported.

**State names.** `study3_states.csv` uses short labels (HP, MP, UP, `J&K(UT) & Ladakh(UT)`). The script maps them to full names. DD and DNH were separate rows until 2022-05-31 and the merged `DNHDDPDCL` row from 2022-06-01; all three become "DNH and DD", summed per day, so the merged UT has one continuous history. Summing the two pre-merger peaks slightly overstates that UT's pre-2022 peak demand, which is acceptable for a small UT.

**States vs grid entities.** DVC, AMNSIL, BALCO, Essar steel, RIL JAMNAGAR and the `Bulk Consumer_*` and `Railways_*` rows are flagged `isState: false`. They have no shape on the map and are listed in their own table.

**Year-on-year growth** is energy over the last 365 days against the 365 days before. It is left blank unless both windows have at least 360 reported days, so an entity that started reporting recently (the bulk-consumer rows began in 2026) does not show a meaningless jump.

**Calibration** uses every logged risk prediction that has a known actual outcome. Predictions are split into ten equal-size groups by predicted probability, then the mean predicted risk is compared with the observed event rate in each group. Precision and recall are reported at each classifier's VAL-selected best-F1 threshold, the same threshold the Anomaly Log uses. These are live, out-of-sample numbers, not the training-time validation scores.

**Duck curve** uses the Era 3 frame after `drop_bad_days()` (the same cleaned frame the EDA findings use), so known-broken SCADA days do not distort the monthly averages. Net demand (`demand - solar - wind`) is computed in the browser.

---

## Display-only guards on the source data

`_load_daily()` blanks two kinds of values it can prove are wrong, for the dashboard only. The CSVs are not changed. The build prints the affected dates every run.

| Column | Rule | Days caught (2026-11-08) |
|--------|------|--------------------------|
| `share_res_pct` | Blank when it differs from `gen_res_mu / gen_total_mu * 100` by more than 1 percentage point | 8: 2022-06-20, 2022-06-28, 2022-08-18, 2022-11-08, 2023-03-30, 2023-09-03, 2024-03-12 (reads 96.8%), 2024-12-18 |
| `freq_fvi` | Blank when above 5 (every other day is below 0.43) | 1: 2021-03-02 (reads 49.215, which looks like a frequency in Hz) |

The Era 1 and Era 2 tables reproduce notebook numbers and still read the CSV directly, without these guards, so they keep matching the notebooks.

---

## Known issues

- The two guards above hide parse errors that should be fixed at the source (the parsers or the published CSVs), then the guards can go.
- The data dictionary's description of the `ir_*_net_mu` sign looks inverted relative to the data (see "Corridor sign convention").
- `Pipeline/validate.py` does not yet check `share_res_pct` against the generation columns or range-check `freq_fvi`; either check would have caught these.
