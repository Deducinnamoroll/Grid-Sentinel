# Notes: study2_io.py

**Script:** `Pipeline/study2_io.py`
**Purpose:** Keep `Dataset/study2_scada.csv` small enough for GitHub by storing it without the columns that `study1_daily.csv` already holds, and give every reader one function that joins them back.

---

## In plain English

The 15-minute SCADA file used to repeat the whole day's summary (144 columns, copied from `study1_daily.csv`) on each of its 96 rows. That copy was 85% of the file. It had reached 71 MB and grew by about 100 KB a day, and GitHub refuses any file over 100 MB, so around September 2027 the daily bot commit would have been rejected and the pipeline would have stopped.

Now the committed file keeps only what is unique to it: the date, the slot time, the 12 real-time SCADA readings and the 6 "time of max demand" columns. That is about 10 MB, growing about 14 KB a day, which leaves well over a decade of headroom. Every script that needs the old wide table calls `load_study2()`, which joins the daily columns back on date. Kaggle still receives the full wide file, built at push time.

---

## Why this option (decided 2026-11-10)

| Option | Result |
|---|---|
| **Drop the broadcast columns, re-join on read (chosen)** | 74.4 MB to 10.3 MB, and growth falls from about 100 KB a day to about 14 KB. Lossless: on all 718 SCADA days the 144 shared columns were constant within the day and equal to that day's `study1_daily` row, checked with exact equality. One file and one schema, so readers change by one line. |
| Split by year (`study2_scada_2024.csv`, ...) | Each year is still about 36 MB, so the duplication stays. Every reader, the Kaggle file list, the README tables and the data dictionary would have to handle a growing set of files, and the Kaggle schema would change. |
| Compressed storage (`.csv.gz`) | About 10 MB, but git cannot delta-compress a gzip blob. Each daily commit would add a new ~10 MB object to history, so the repo (and every Actions checkout) would grow by about 300 MB a month. |
| Git LFS | GitHub Free includes 10 GiB of LFS storage and 10 GiB of bandwidth a month ([GitHub Docs](https://docs.github.com/billing/managing-billing-for-git-large-file-storage/about-billing-for-git-large-file-storage)). LFS keeps every version, and each daily version is about 71 MB, so storage fills in about 5 months. After that, pushes of LFS files fail. Does not fit. |

---

## What is in the committed file

21 columns: `date`, `time`, `hhmm`, `freq_hz`, `demand_met_mw`, `nuclear_mw`, `wind_mw`, `solar_mw`, `hydro_mw`, `gas_mw`, `thermal_mw`, `others_mw`, `net_demand_met_mw`, `total_gen_mw`, `net_trans_exchange_mw`, and `time_max_demand_met_{nr,wr,sr,er,ner,total}`.

The rule is not a fixed list. `slim()` drops every column, except `date`, whose name is also in `study1_daily.csv`. The six `time_max_demand_met_*` columns are daily values too, but `study1_daily` has no equivalent, so they stay. If the parser gains a new daily column that is not in `study1_daily`, it stays as well. Nothing is dropped unless it can be re-joined.

## Functions

| Function | What it does |
|---|---|
| `slim(wide_df, study1_cols)` | Drops the shared columns. |
| `widen(slim_df, study1_df)` | Left join of `study1_daily` on `date`, many-to-one (pandas checks that `study1_daily` has one row per date). |
| `load_study2(parse_dates=True)` | Reads both CSVs and returns the 164-column frame every consumer used before. |
| `wide_columns()` | The wide column list from the two headers only (no data read). Used by `build_data_dict.py` and `kaggle_metadata.py`. |
| `write_wide(out_path)` | Writes the wide file with ISO date strings, as the CSVs store them. |

The wide frame's column order is the slim columns, then `study1_daily`'s columns in `study1_daily`'s order. The parser's order put the daily columns between the SCADA columns and `time_max_demand_met_*`. No reader selects by position, so this is only cosmetic, but the Kaggle file's column order changed on 2026-11-10.

## CLI

```
python Pipeline/study2_io.py --write-wide OUT.csv   # used by the Kaggle push step
python Pipeline/study2_io.py --slim-in-place        # used by build_all.py after the File3 parse
```

`--slim-in-place` reads with `float_precision="round_trip"`, so kept cells are written back exactly. Before writing, it re-joins the slim result and compares it with the wide input (`mismatched_columns()`). Text and the positions of empty cells must match exactly. Numbers may differ by 1e-9 relative or 1e-9 absolute, because the File2 and File3 parsers sum some figures in a different order. On a fresh File3 rebuild, a few hundred cells in 24 columns differ from `study1_daily` by about 1e-12. If a rebuilt `study1_daily.csv` and a rebuilt SCADA file disagree by more than that, the build fails instead of silently replacing the SCADA copy's value. On a file that is already slim it does nothing.

`write_wide()` also reads with `round_trip`, so the Kaggle file has exactly the text of the two committed CSVs. `load_study2()` keeps pandas' default float parser by default, which is what every consumer used before, so their inputs did not change.

## Who uses it

| Consumer | Change |
|---|---|
| `Scrapings/update_live.py` `append_study2()` | Slims the parsed rows before appending. Skips the day if `study1_daily` has no row for it yet, and the next `--scan` retries it, because `_dates_in_all_csvs()` still reports the day missing. Warns if the parser's daily values differ from `study1_daily`'s (in that case `study1_daily`'s values are what readers get). |
| `ML/Study2/predict.py` | `load_study2()` instead of `read_csv`. |
| `Pipeline/build_dashboard_data.py` | Same, in both places it read the file. |
| `Pipeline/validate.py` | Runs every study2 check on the joined frame, plus two new checks on the committed file (see `validate_notes.md`). |
| `Pipeline/build_all.py` | Runs `--slim-in-place` after the File3 parse. |
| `Pipeline/build_data_dict.py` | Documents `wide_columns()`, so the study2 sheet still lists 164 columns. |
| `Pipeline/kaggle_metadata.py` | Reads headers from the push folder, where `study2_scada.csv` is the wide copy. With `--update-readme`, uses `wide_columns()`. |
| `.github/workflows/daily_scrape.yml` | The Kaggle step writes the wide file with `--write-wide` instead of copying the committed one. |
| `ML/Study2/notebooks/*` | Unchanged. They download from Kaggle, which still has the wide file. |

## Verification (2026-11-10)

All checks compare against runs on the original wide file with the same code and data.

- **Lossless.** `--write-wide` on the slim file reproduces the original 74.4 MB file's text exactly in every cell of all 68,700 rows x 164 columns. Only the column order differs. The 21 kept columns are also text-identical to the original.
- **`validate.py`.** Same output as on the wide file (45 PASS, 6 WARN, 1 FAIL, the known 3 corrupted SCADA days), plus the 2 new PASS lines.
- **Study 2 predictions.** Removed 2026-11-07 and 2026-11-08 from `study2_risk.csv` and re-ran `predict.py --from 2026-11-07`. The 10,080 rows were identical to the same re-run on the wide file, with a max absolute difference of 0.0 in every column.
- **Dashboard.** `build_dashboard_data.py` output under `dashboard/public/data/` was byte-identical.
- **Data dictionary.** `build_data_dict.py` produced the same content on every sheet. Only the study2 sheet's row order follows the new column order.
- **Kaggle prep.** `--write-wide` plus `kaggle_metadata.py` on a scratch push folder gave 164 columns, 68,700 rows and 469 column descriptions.
- **Daily append.** Removed 2026-11-08 from a scratch copy, then ran `append_study2()` on `08.11.26_NLDC_PSP.xls`. The result was byte-identical to the committed file, and no mismatch warning appeared. With that day also removed from a scratch `study1_daily`, it skipped the day as designed.
- **Full File3 rebuild.** `build_all.py --skip-file1 --skip-file2 --skip-states --skip-hourly` (3 minutes) parsed all 718 SCADA days and slimmed them. The first run failed safely on the exact-equality check that was there at first, because of the 1e-12 float residue described above. That is why the check now uses a tolerance. In the 21 kept columns, the rebuilt file differs from the committed one in ways that already existed before this change: 2 duplicate slots on 2024-11-16 (12:00 and 23:00), 12 `freq_hz` cells written as `0.0` that the committed file has blank, and last-digit text differences in about 230 cells from older incremental rewrites. These are not caused by slimming. The duplicate slots were fixed in the parser on 2026-11-10 (see `parse_psp_xls_pdf_file3_notes.md`); a rebuild after that fix has 68,700 rows and no duplicates. The `freq_hz` cells are still open.
