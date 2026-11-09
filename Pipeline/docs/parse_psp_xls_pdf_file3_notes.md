# Notes: parse_psp_xls_pdf_file3.py

**Script:** `Scrapings/parse_psp_xls_pdf_file3.py`
**Purpose:** The parser for `Dataset/Raw/File3_Raw/`. Its `long` mode builds the 15-minute SCADA table behind `Dataset/study2_scada.csv`.

---

## In plain English

Since FY2025 the NLDC Excel reports have a `TimeSeries` sheet with one reading every 15 minutes: frequency, demand and generation by source. This script reads that sheet and writes one row per 15-minute slot. It also reads the day's summary figures, so every slot row carries them, but those are dropped before saving, because `study1_daily.csv` already holds them (see `study2_io_notes.md`).

---

## How it is called

| Caller | Call |
|---|---|
| `Scrapings/update_live.py` `append_study2()` | `build_timeseries_long(one_file, tmp_csv)`, one day at a time |
| `Pipeline/build_all.py` step 4 | `python Scrapings/parse_psp_xls_pdf_file3.py long Dataset/Raw/File3_Raw Dataset/study2_scada.csv`, then `study2_io.py --slim-in-place` |

Other modes (`INPUT_DIR OUTPUT_CSV` for a wide one-row-per-day table, or a single file to print its fields) are for inspection. No pipeline step uses them.

## Long mode (`build_timeseries_long`)

For each `.xls`/`.xlsx` file that has a `TimeSeries` sheet:

1. Reads the date from `MOP_E`. A file without `MOP_E` or a readable date is reported as failed.
2. Reads the day's figures from `MOP_E`, `IR-Line` (7 region-pair aggregates) and `CrossBorder`, and reconciles them (`_reconcile_daily`).
3. Parses the `TimeSeries` sheet into one record per slot (`_xls_parse_timeseries_records`) and attaches the date and the day's figures to each record.

Output columns are `date`, `time`, `hhmm` first, then the rest. Rows are sorted by date and `hhmm`. Files with no `TimeSeries` sheet, or one with a header but no data rows, are counted as skipped.

## TimeSeries records (`_xls_parse_timeseries_records`)

- Finds the header row (first cell `TIME`) and maps columns by label, most specific first, so `NET DEMAND MET` is not taken as `DEMAND MET`.
- The TIME cell may be a time object, a fraction of a day, or `H:MM[:SS]` text (`_parse_timeseries_time_cell`).
- Blank rows are skipped. A non-time row before the data is skipped (units sub-header). The first non-time row after the data ends the table (footer).
- **Dropout zeros become blanks (since 2026-11-10).** `_blank_scada_dropouts()` blanks `freq_hz` when it is 0, and when `thermal_mw` is 0 it blanks every source column that is 0 plus `total_gen_mw`. See the fix below.
- **One row per time (since 2026-11-10).** If a time appears twice, only the first row is kept. An exact repeat is dropped silently. A repeat with different values prints `TimeSeries: slot HH:MM appears twice with different values -- keeping the first`.

## Fix 2026-11-10: repeated slot rows

The 2024-11-16 report's `TimeSeries` sheet lists 12:00 and 23:00 twice, with identical values in every column. The parser kept both, so a full rebuild produced 98 rows for that day and 2 duplicate `(date, hhmm)` pairs, which `validate.py` fails on. The committed file never showed this, because `append_study2()` runs `drop_duplicates(subset=["date", "hhmm"], keep="last")` after each append. The full rebuild path in `build_all.py` has no such step. It surfaced while testing the `study2_scada.csv` slimming change (see `study2_io_notes.md`).

The parser now keeps one row per time. That fixes both paths at the source, and for 2024-11-16 it keeps the same values the committed file already had. After the fix, a full File3 rebuild has 68,700 rows and no duplicates (see the verification note in `study2_io_notes.md`).

## Fix 2026-11-10: SCADA dropout zeros

NLDC writes 0 when a SCADA reading is missing. Two cases were stored as real zeros:

- **Frequency.** 14 slots had `freq_hz` = 0. Real values run from 49.41 to 50.48 Hz. 12 of them (2024-11-08 to 2025-11-25) were already blank in the committed file, from an earlier cleanup that never reached the parser. The parser kept writing 0, so the daily append added two more: 2026-10-05 18:15 and 2026-11-01 03:30. `validate.py` had been warning about them as "2 values outside [47, 52] Hz".
- **Generation.** In 5 slots (2025-01-28 12:00, 2025-03-15 13:15 and 13:30, 2025-11-13 16:00, 2026-03-25 15:45) every source and `total_gen_mw` read 0 while `demand_met_mw` was normal. In 2024-12-12 15:45, wind, hydro, gas and thermal read 0, and `total_gen_mw` (36,161 MW) was only the sum of the sources that reported. The lowest real thermal slot is about 57 GW, so `thermal_mw` = 0 always means the feed dropped out.

Why it mattered: Study 2 treats 0 Hz as a frequency violation. The 2026-11-01 zero made the 4 slots before it (02:30 to 03:15) count as "violation within the next hour", both as training labels and as the logged outcome in `Dataset/predictions/study2_risk.csv`. The zeros also fed fake jumps into `freq_hz_delta`, `solar_delta_mw` and `wind_delta_mw`, and pulled the dashboard's duck-curve averages down.

What changed:

- The parser blanks these values (`_blank_scada_dropouts()`). `demand_met_mw` and `net_trans_exchange_mw` come from other feeds and are kept; `net_trans_exchange_mw` is a genuine 0 in about 500 normal slots.
- The committed `study2_scada.csv` was corrected with the same function, which blanked 47 cells on 8 rows; no other cell changed. A fresh File3 rebuild now matches the committed file in rows, blank positions and values.
- In `study2_risk.csv`, `actual_violation` for 2026-11-01 02:30, 02:45, 03:00 and 03:15 was changed from 1.0 to 0.0. Those are the only logged outcomes that change: every other logged row matches the labels recomputed from the corrected data. The logged probabilities are left as they were, since they record what the model said at the time.
- Dashboard data was rebuilt: 7 day-view month files show gaps instead of zeros, and `renewables.json` and `models.json` changed slightly.
