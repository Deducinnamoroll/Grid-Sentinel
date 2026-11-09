# Notes: build_all.py

**Script:** `Pipeline/build_all.py`
**Purpose:** Single-command full rebuild of all four Grid-Sentinel datasets from raw files on disk.

---

## In plain English

This is the "rebuild everything from scratch" button. We download the grid operator's daily reports (thousands of them, going back to 2018) and this script reads every single one and turns them into the four clean spreadsheet files that make up this project's public dataset. You'd run this after fixing a bug in how we read the reports, so the whole dataset gets corrected everywhere at once, not just for new days going forward.

---

## What it does

Runs five steps in sequence. Steps 1 through 4 call the parser scripts as subprocesses so their output flows directly to the console. Step 5 runs in-process.

| Step | Input | Output | Script called |
|------|-------|--------|---------------|
| 1 | `Dataset/Raw/File1_Raw/` | `tmp/f1_daily.csv` | `Scrapings/parse_psp_pdf_xls_file1.py` |
| 2 | `Dataset/Raw/File2_Raw/` | `Dataset/study1_daily.csv` | `Scrapings/parse_psp_pdf_xls_file2.py` |
| 3 | `Dataset/Raw/File2_Raw/` | `Dataset/study3_states.csv` | `Scrapings/parse_psp_states.py` |
| 4 | `Dataset/Raw/File3_Raw/` | `Dataset/study2_scada.csv` | `Scrapings/parse_psp_xls_pdf_file3.py long`, then `Pipeline/study2_io.py --slim-in-place` |
| 5 | `tmp/f1_daily.csv` + `Reference/hourlyLoadDataIndia.xlsx` | `Dataset/study1_hourly.csv` | in-process pandas join |

Step 4's second command (added 2026-11-10) removes the `study1_daily` columns that the parser broadcasts onto every slot, so the committed file stays far below GitHub's 100 MB limit (see `study2_io_notes.md`). It refuses, and the build fails, if any dropped value differs from `study1_daily.csv`. So if File2 parsing changed too, rebuild `study1_daily` (step 2) in the same run. The summary at the end shows the slim file (21 columns).

Step 5 is a left join: every daily PSP row in `tmp/f1_daily.csv` broadcasts onto all 24 hourly rows for that date in the Kaggle hourly load file.

Steps 2 and 3 read the same raw folder (`File2_Raw`) but run as two independent subprocess calls with two independent parsers (`parse_psp_pdf_xls_file2.py` and `parse_psp_states.py`) — they don't share a parse pass, so a file that fails one doesn't affect the other.

---

## Why subprocess for steps 1 to 4

The four parser scripts are standalone CLI tools with their own argument handling. Calling them as subprocesses means `build_all.py` does not import their internals and each parser's stdout and stderr reach the console without buffering. It also means partial rebuilds (via skip flags) cleanly skip only the subprocess call, not some internal function.

---

## `tmp/f1_daily.csv` — why it lives outside `Dataset/`

`f1_daily.csv` is a disposable intermediate: it exists purely to feed step 5's hourly join and has no independent value (unlike `Dataset/study1_daily.csv`, nobody should ever need to open it directly). It's written to the repo-root `tmp/` folder (gitignored) rather than `Dataset/` so it never gets confused with, or accidentally swept into, the four published datasets that folder actually holds. `TMP_DIR.mkdir(exist_ok=True)` runs before step 1 so a fresh clone doesn't need to create the folder manually. Moved here 2026-07-10 — it previously sat at the repo root directly, which cluttered the top-level listing.

---

## Output summary printed on completion

After all steps, the script prints for each dataset:

- Row and column count
- Date range (earliest and latest value in the date column)
- Overall null percentage across all cells
- The 8 columns with the highest null rate

If any dataset has fewer rows than the baseline defined in `BASELINES`, a warning is printed. The baselines are the minimum expected row counts at the time the script was written and are allowed to grow as new daily data arrives but should never decrease.

---

## Skip flags

| Flag | Effect |
|------|--------|
| `--skip-file1` | Skips step 1. Use when `tmp/f1_daily.csv` already exists and `Dataset/Raw/File1_Raw/` has not changed. |
| `--skip-file2` | Skips step 2. |
| `--skip-states` | Skips step 3 (`study3_states.csv`). |
| `--skip-file3` | Skips step 4. |
| `--skip-hourly` | Skips step 5. |
| `--only-hourly` | Skips steps 1-4. Runs only the hourly join. |

Example: only `Dataset/Raw/File3_Raw/` has new files and you want to rebuild `study2_scada.csv`:

```
python Pipeline/build_all.py --skip-file1 --skip-file2 --skip-states
```

---

## What this script does not do

- It does not run the validation gate. Run `validate.py` separately after a rebuild.
- It does not push to Kaggle. That is handled by `daily_scrape.yml` step 6.
- It does not download raw files. Use `Scrapings/local_download.py` for that.
- It does not regenerate `Dataset/data_dictionary.xlsx`. Run `Pipeline/build_data_dict.py` separately, and only when the schema actually changes (new dataset or column) — see its own notes file.

---

## Expected run time

A full rebuild over the entire history (approximately 2,700+ raw files, growing daily) takes between 15 and 45 minutes depending on hardware, plus a similar amount again for step 3 (`study3_states.csv`, which reparses the same File2_Raw archive independently). Incremental rebuilds using skip flags complete in under a minute.

---

## Known issues fixed at deployment (2026-07-01)

The original draft from Abhi had `HOURLY_SRC = REPO_ROOT / "hourlyLoadDataIndia.xlsx"`. The file is at `Reference/hourlyLoadDataIndia.xlsx`, not the repo root. This was corrected on deployment. The hourly join step would have silently failed otherwise.

## Changes 2026-07-10

- Added step 3 (`study3_states.csv` via `parse_psp_states.py`) and the `--skip-states` flag, as part of closing out Phase 2. See `parse_psp_states_notes.md`.
- Moved `f1_daily.csv` from the repo root into `tmp/` (see section above).
