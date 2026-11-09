# Notes: update_live.py

**Script:** `Scrapings/update_live.py`
**Purpose:** Daily incremental update for the live pipeline — downloads the newest PSP report, parses it, and appends to all four datasets without a full rebuild. This is what `.github/workflows/daily_scrape.yml` actually runs every day; `Pipeline/build_all.py` is for full/partial local rebuilds, not daily automation.

---

## In plain English

This is the script that keeps the dataset alive. Every day, without anyone touching a keyboard, a scheduled job runs this script — it goes to the grid operator's website, grabs that day's new report, and adds it to our four datasets. Without this, the dataset would be frozen at whatever day we last updated it by hand.

---

## Why this file exists

`build_all.py` re-parses the entire raw archive (~2,700+ files, growing daily) every time — 15-45 minutes per dataset. That's fine for a local rebuild after a parser fix, but far too slow to run on every CI trigger just to add one new day's data. `update_live.py` instead downloads and parses exactly one file, appends the resulting rows to the existing CSVs, and exits — seconds, not minutes.

---

## What it does

### Two run modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Download mode (default) | `workflow_dispatch` or scheduled cron | Downloads today's (or yesterday's, or a `--date`-specified) file from NLDC, parses it, appends one day's rows to all three CSVs that have per-file appends |
| Scan mode (`--scan`) | Triggered on `push` to `Dataset/Raw/File2_Raw` or `File3_Raw` (i.e. someone manually added raw files) | Parses every raw file in `File3_Raw` dated within the last `--lookback` days (default 90) whose date is not already in all three CSVs. Files already reflected are skipped without being parsed, so the long window is cheap. This is what makes an outage self-healing: once the cause is fixed, the next scan fills every missing day |

### Download fallback chain (`download_today()`)

Tries three methods in order, each covering a different NLDC CDN era:
1. **Old CDN** (`report.grid-india.in`) — plain `requests` GET, works for older dates, no browser needed. Uses `verify=False` internally since NLDC's site has a TLS cert issue.
2. **New CDN listing, browser-free** (`webcdn.grid-india.in`, dates ≥ `NEW_CDN_START` = 2025-05-28) — scrapes an S3-style file listing.
3. **Playwright fallback** — only reached if both of the above fail; works locally but may fail in CI (no browser available there by default).

### Three append functions, one per dataset

| Function | Appends to | Source parser |
|----------|-----------|---------------|
| `append_study1()` | `study1_daily.csv` (1 row) | `parse_psp_pdf_xls_file2.parse_file()` |
| `append_study2()` | `study2_scada.csv` (up to 96 rows, slim) | `parse_psp_xls_pdf_file3.build_timeseries_long()` |
| `append_study3()` | `study3_states.csv` (~37 rows) | `parse_psp_states.parse_file()`, added 2026-07-10 |

All three re-sort after appending (`study1_daily` by date, `study2_scada` by date and time, `study3_states` by date, region and state), so a scan or backfill that adds an older day after newer ones still leaves the file in order. `append_study1()` gained its sort on 2026-11-09, after the October 2026 backfill left 39 rows out of place; the committed file was re-sorted line by line at the same time, with every row byte-identical.

### `append_study2()` writes the slim file (since 2026-11-10)

The parser still returns the wide frame, with the day's `study1_daily` values on every slot row. `append_study2()` drops those columns with `study2_io.slim()` before appending, and every reader re-joins them (see `study2_io_notes.md` for why). Because of that:

- **The day must already be in `study1_daily.csv`.** `append_study1()` runs first on the same raw file, so normally it is. If it is not (`append_study1()` failed or found nothing), `append_study2()` skips the day and prints why. The next `--scan` picks it up again, because `_dates_in_all_csvs()` only counts a date as done when all three CSVs have it.
- **The two parsers are compared.** The broadcast values from `parse_psp_xls_pdf_file3` are checked against the `study1_daily` row (from `parse_psp_pdf_xls_file2`). They agreed on all 718 days when this was introduced. Any difference prints a WARNING with the column names and does not stop the append. Readers get `study1_daily`'s value.
- The existing file is read with `float_precision="round_trip"`, so rewriting it does not change the last digit of untouched cells. Before 2026-11-10 each daily rewrite changed a few dozen cells by one unit in the last place.

Each is independent: a failure in one (caught and logged, not raised) doesn't block the other two in scan mode. Each checks whether that date is already present before appending — running the script twice on the same day is a safe no-op, not a duplicate.

### `append_study3()` specifically

Uses the same static `STATE_TO_REGION` map and `STATE_NAME_ALIASES` as the full-rebuild path in `parse_psp_states.py`, imported directly rather than reimplemented — this is what makes a single day's incremental append resolvable correctly without needing the whole archive present for a majority vote. See `parse_psp_states_notes.md` for why the static map is the primary resolution method, not a fallback.

### Validation after append

`validate()` runs lightweight sanity checks (duplicate dates/keys, null-rate jump for study1) on whichever datasets actually changed. This is a fast subset of `Pipeline/validate.py`'s checks, run inline so a bad append fails the CI job immediately (exit code 2) rather than silently corrupting the committed CSV.

### Exit codes, and what CI does with them

| Code | Meaning | CI behaviour |
|------|---------|--------------|
| 0 | Ran fine (possibly nothing new) | Normal |
| 1 | File not published yet | Not an error, retry later |
| 2 | Validation failed, nothing committed | The run turns red (last workflow step) |

An uncaught exception also exits 1, so the workflow additionally greps the log for a `Traceback` and fails the run on one.

### Incident that shaped this (2026-09-30 to 2026-11-08)

On 2026-09-30 NLDC began publishing `Bulk Consumer_WR/SR/ER/NER ISTS` rows in section C (before that only the NR one existed). They were not in `STATE_TO_REGION`, so validation failed with exit 2 every day. The workflow then treated exit 2 like exit 1 ("not published yet"), so every run stayed green, no data was committed for five weeks, and the live dashboard fell behind. A second fault hid the damage: the scan only looked back 10 days, so after the mapping was fixed only the last 10 days were recovered and about 29 days in October stayed missing. Three changes came out of it:

1. The workflow captures the exit code and turns the run red on exit 2 or a crash.
2. A freshness step fails the run when the latest `study1_daily.csv` date is more than 5 days old (same threshold as `Pipeline/validate.py`'s `MAX_LAG_DAYS`).
3. The scan window is 90 days with cheap skipping of already-parsed dates, so any outage repairs itself.

A daily schedule (10:30 UTC, added 2026-11-08) is a watchdog, not a second data source. GitHub's runners cannot download NLDC files (checked 2026-11-08: the browser-free CDN route fails in CI and Playwright is not installed; the original crons were dropped on 2026-06-24 for this reason), so new days still arrive only through the local scheduler's raw-file push. The scheduled run's job is to reach the stale-data step, so a stopped local scheduler turns a run red within about 5 days instead of going unnoticed. Runs are serialized with a `concurrency` group, and the commit step rebases before pushing in case a raw-file push landed mid-run.

### Kaggle "About Dataset" text

The Kaggle push step runs `Pipeline/kaggle_metadata.py` on the upload folder (added 2026-11-09). It puts live row counts into the README, uses the README as the About text and adds per-column descriptions from `data_dictionary.xlsx`. Edit the README or dictionary, not the Kaggle page: hand edits on Kaggle get overwritten by the next push. See `kaggle_metadata_notes.md`.

---

## Verification (2026-07-10)

All three append functions independently tested by removing a known date from a test copy of its CSV, re-running the actual function against that copy, and diffing the result against the full-rebuild original. **All three byte-identical** — confirms the incremental path produces the same result as a from-scratch rebuild, not just "doesn't crash."

---

## Usage

```
python Scrapings/update_live.py                        # download today/yesterday, append
python Scrapings/update_live.py --date 2026-06-24       # backfill a specific date
python Scrapings/update_live.py --scan                  # catch up on unparsed raw files (last 90 days)
python Scrapings/update_live.py --scan --lookback 200   # reach further back after a very long outage
```

Depends on `download_psp_new.py` (same folder) for the CDN fetch logic, and imports `parse_file`/`build_timeseries_long`/`parse_file` from the three per-dataset parsers at call time (not at module load) to avoid unnecessary import cost when only one dataset needs updating.

### Report change and column health guard (added 2026-11-10)

After validation passes, `run_guard()` runs `Scrapings/report_guard.py` on every raw file the run parsed: a label check against `Scrapings/known_report_labels.json` and a health check of each new data day against the 30 days before it. Findings never block the commit; the workflow turns the run red on them. See `report_guard_notes.md`.
