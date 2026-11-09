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
- **One row per time (since 2026-11-10).** If a time appears twice, only the first row is kept. An exact repeat is dropped silently. A repeat with different values prints `TimeSeries: slot HH:MM appears twice with different values -- keeping the first`.

## Fix 2026-11-10: repeated slot rows

The 2024-11-16 report's `TimeSeries` sheet lists 12:00 and 23:00 twice, with identical values in every column. The parser kept both, so a full rebuild produced 98 rows for that day and 2 duplicate `(date, hhmm)` pairs, which `validate.py` fails on. The committed file never showed this, because `append_study2()` runs `drop_duplicates(subset=["date", "hhmm"], keep="last")` after each append. The full rebuild path in `build_all.py` has no such step. It surfaced while testing the `study2_scada.csv` slimming change (see `study2_io_notes.md`).

The parser now keeps one row per time. That fixes both paths at the source, and for 2024-11-16 it keeps the same values the committed file already had. After the fix, a full File3 rebuild has 68,700 rows and no duplicates (see the verification note in `study2_io_notes.md`).
