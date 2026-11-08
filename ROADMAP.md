# Grid-Sentinel — Roadmap

_Last updated: 2026-07-19: dashboard deployed publicly on Vercel, live at [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/), closing Phase 5's last open item. Also: removed `Scrapings/download_psp_old.py` and `download_psp_both.py` (superseded, unreferenced-anywhere-else predecessors of `download_psp_new.py`); dropped the two in-app references to specific notebook filenames in the Historical Explorer's Era 1/Era 2 tabs (implementation detail, not something a visitor needs); added a root `README.md`; added Abhirami as a second author/collaborator (ML, Phase 3+)._

_Previous update, 2026-07-14 — added the model-diagnostic and table-to-chart visualizations Sagnik asked for across both studies (feature-importance bars, PR curves, confusion matrices, hour×dow heatmap, Era 2 corridor-correlation bars, month/solar-hour/RES-share bars), then, while deciding whether anything else was worth adding, found a real methodology bug: both Study 2 classifiers' "best-F1 operating point" and "recall at ≥95% precision" numbers were selected by scanning the TEST set's own precision-recall curve for its best point — reporting the best-in-hindsight threshold rather than an honestly out-of-sample one. Fixed by selecting the threshold on VAL and freezing it before applying to TEST. PR-AUC (threshold-free) is unaffected, but the operating-point numbers shifted: violation classifier's honest best-F1 is now 0.1843/precision 20.8%/recall 16.6% (was a hindsight-inflated 0.2035/17.7%/24.0%), and — the bigger finding — the ramp-shock classifier's previously-quoted "recall at ≥95% precision = 20.4%" collapses to 0.3% once evaluated honestly; that headline number was almost entirely a hindsight-overfitting artifact. See Phase 4's classifier sections below for full corrected numbers._

_Previous update, 2026-07-11 (past midnight) — while actually walking Sagnik through the Colab setup, two real things turned up: (1) a genuine security concern (a real Kaggle key almost got typed into a notebook cell headed for the public repo) — resolved by switching to Colab's Secrets manager instead of hardcoded credentials, documented in "ML Development Environment"; (2) built `study1_run_all.ipynb` / `study2_run_all.ipynb`, one-file-per-study convenience notebooks that concatenate each study's stages so a collaborator can open and run just one file — and while assembling Study 1's, found a real bug in `04_era1_ramp_characterization.ipynb` (wrong datetime format, would have crashed if actually run against live data, apparently never re-confirmed since Phase 3). Fixed and re-verified end to end._

_Previous update, 2026-07-11 (late night): pushed back on three things reported too passively, and did the actual work instead of explaining it: (1) all 69 `study1_daily` gap dates now individually root-caused (was 4 of 69) by re-parsing the full raw archive directly (835 files) — 49 confirmed duplicate NLDC republishes, 16 confirmed genuine archive gaps, every date backed by named evidence in `known_gaps.json`, not a generic placeholder; (2) confirmed `validate.py`'s current state plainly: 38 PASS / 4 WARN / 1 FAIL, zero unresolved bugs in the checker itself; (3) added `freq_hz_delta`/`wind_delta_mw` — real, verified gain: violation PR-AUC 0.1186 → 0.1567 (+32%), ramp-shock 0.7446 → 0.7486._

_Previous update, 2026-07-11 (night): did a real confidence audit of Phase 4 rather than just re-reading the docs. Found that `share_res_pct` and all 11 `ir_*`/`xb_*` corridor columns are whole-DAY aggregates broadcast identically to every 15-min slot of that day, raising a leakage question — tested rather than assumed, and removing them **improved both targets** (violation PR-AUC 0.0937 → 0.1186, ramp-shock 0.7248 → 0.7446), so there was no leakage inflation, just noise being removed._

_Previous update, 2026-07-11 (late evening): two things: (1) Phase 6's paper framing rewritten to lead with the project's actual strongest material (the dataset, the season-controlled Era 3 RES-share finding, the day-of-week decoupling finding) instead of the weak violation classifier — see Phase 6's "Central claim" and "Paper structure" below, both marked as rewritten with the old framing kept visible for context; (2) found and fixed a real Colab-readiness bug in all 5 `ML/Study2` notebooks (an inconsistent `sys.path.insert` left over from earlier drafting, which assumed a different working directory than the `data/...` paths in the same cells) and made the previously-unwritten concrete Colab setup steps explicit in "ML Development Environment"._

_Previous update, 2026-07-11 (evening): investigated whether the two-stage ramp→violation idea (flagged as future work) could improve the weak violation classifier. It couldn't, on the evidence: a diagnostic check found ramp-shocks don't actually precede violations more than chance, so the idea was abandoned rather than built on a falsified premise. Chasing a better-supported alternative (solar-generation volatility, not demand-side ramps) led to a bigger find: **`scale_pos_weight` was silently causing LightGBM's early stopping to fire after a single boosting round** for the violation target, capping it at close to one shallow tree. Fixing that (and adding the solar features) raised the violation classifier's PR-AUC from 0.0614 to 0.0937 (+53%) and best-F1 from 0.1297 to 0.1712, with a smaller but real gain on the already-strong ramp-shock classifier too (PR-AUC 0.7140 → 0.7248). Both baseline notebooks, `features.py`, and the live `predict.py` were all updated and re-verified._

_Previous update, 2026-07-11 (afternoon): closed out the open items from Phase 0-4's post-build audit, all goal-driven not just cosmetic: (1) violation classifier lead-window experiment (1/2/3/4 slots) added to 03_violation_baseline.ipynb; (2) hour×day-of-week heatmap + a month-controlled re-analysis added to 01_eda.ipynb, which reverses the earlier "RES-share vs ramp rate" finding once season is properly controlled for; (3) Pipeline/known_gaps.json built from a fresh, complete re-scan of every dataset's actual missing dates (not the old prose-only list), wired into validate.py, and it caught two real, previously-undocumented issues along the way — a 1-day date error (2019-05-10 → 2019-05-09) and 17 previously-undocumented missing dates in study2_scada; (4) a null-%-drift check added to validate.py._

_Previous update, 2026-07-11 (morning): Phase 4 built and verified end-to-end: ML/Study2/features.py, all 5 notebooks (Era 2 daily correlation, Era 3 EDA, feature table, violation baseline, ramp-shock baseline), and ML/Study2/predict.py, wired into CI — closing Phase 4's only deferred item (owner). Every notebook's embedded numbers were independently re-executed against live data and matched exactly, not just written and assumed correct._

_Previous update, 2026-07-10: Phase 2 fully complete: merged-blob fix, 2014 bogus-date bug, and new study3_states.csv all built and verified; Phase 3 naive-persistence anchor bug found, fixed, and re-verified, plus ML/Study1/predict.py built and wired into CI closing Phase 3's last deferred item; Phase 0-1 adversarially re-audited — 164/165 discrepancy resolved, build_data_dict.py gap found and fixed, data_dictionary.xlsx committed and added to the Kaggle push, a real gap in daily_scrape.yml where study3_states.csv was never being committed found and fixed, and the original 8-date spot-check fully re-derived from scratch — ~280 field comparisons, 0 mismatches._

---

## What this project is

Grid-Sentinel is a machine learning project for **predicting and detecting stress on the Indian power grid**, built entirely on NLDC (National Load Despatch Centre) daily Power System Performance (PSP) reports scraped from the NLDC/Grid-India CDN.

### End goals

1. **Dashboard** (public, live at [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/), deployed on Vercel): a real-time web dashboard that shows both live NLDC data as it comes in and model predictions overlaid. Also includes an interactive explorer of the full historical dataset (2019–present). Intended as a portfolio/résumé artefact.
2. **Research paper** (conditional) — if model results are strong enough, publish to an IEEE Power & Energy conference or a journal like *Electric Power Systems Research*. Decision deferred until Phase 3/4 outputs are in hand.
3. **Kaggle dataset** (ongoing) — four cleaned CSVs published and auto-updated daily (a fourth, `study3_states.csv`, added in Phase 2), serving as a public resource for the broader community.

### Two studies

| Study | Dataset | Target | Rows | Date range |
|-------|---------|--------|------|------------|
| **Study 1 — Daily load forecasting** | `study1_daily.csv` | Next-day peak demand (MW) / energy met (MU) | 2,660 × 144 | 2018-12-31 → present |
| **Study 2 — 15-min frequency-violation classifier** | `study2_scada.csv` | Binary: frequency violation in a 15-min slot? | 55,000+ × 164 | 2024-11-04 → present |

Study 1 also has an hourly variant (`study1_hourly.csv`, 46,728 rows × 151 cols, 2019-01-01 → 2024-04-30) joining PSP daily features with the Kaggle India hourly load data.

A fourth dataset, `study3_states.csv` (99,208 rows × 10 cols, long format — one row per state/UT/entity per day, 2018-12-31 → present), was added in Phase 2 (2026-07-10): NLDC's §C state-level power supply position, not tied to either study's modelling target but published as a standalone resource.

---

## Repository structure

```
Grid-Sentinel/
├── Dataset/            Output CSVs + Kaggle metadata (auto-updated daily by CI)
│   ├── data_dictionary.xlsx   Generated by Pipeline/build_data_dict.py, committed manually
│   └── Raw/
│       ├── File1_Raw/  Historical PSP PDFs + early XLS (pre-2023)
│       ├── File2_Raw/  Full-history PSP files (2019-present), used for study1_daily + study3_states
│       └── File3_Raw/  FY2025+ XLS files with TimeSeries sheet, used for study2_scada
├── ML/                 Modelling work (Phase 3+)
│   ├── environment.yml     Conda env for Colab/local notebook use
│   ├── Study1/
│   │   ├── features.py         Shared feature engineering, imported by notebooks + predict.py
│   │   ├── predict.py           Daily next-day demand forecast, wired into CI
│   │   └── notebooks/          01_eda, 02_features, 03_baseline, 04_era1_ramp_characterization,
│   │                          study1_run_all (all 4 stages combined, one file to open/run/share)
│   └── Study2/
│       ├── features.py         Shared feature engineering (labels, lag/rolling slot features,
│       │                       Study1 residual backtest), imported by notebooks + predict.py
│       ├── predict.py           Daily 96-slot violation/ramp-shock risk timeline, wired into CI
│       └── notebooks/          00_era2_daily_correlation, 01_eda, 02_features,
│                               03_violation_baseline, 04_ramp_shock_baseline,
│                               study2_run_all (all 5 stages combined, one file to open/run/share)
├── Pipeline/           Build, validate, and data-dictionary scripts
│   ├── build_all.py        Full rebuild of all four datasets
│   ├── validate.py         Post-build integrity checks
│   ├── build_data_dict.py  Generates Dataset/data_dictionary.xlsx
│   └── docs/               One notes.md per Pipeline/Scrapings script -- see below
├── Reference/          External source data (hourlyLoadDataIndia.xlsx from Kaggle)
├── Scrapings/          Parsers and download scripts
│   ├── local_download.py   Run locally (scheduled via run_download.bat)
│   ├── update_live.py      Incremental append — called by GitHub Actions daily
│   ├── parse_psp_pdf_xls_file1.py
│   ├── parse_psp_pdf_xls_file2.py
│   ├── parse_psp_xls_pdf_file3.py
│   └── parse_psp_states.py     study3_states.csv (§C state-level table, Phase 2)
├── logs/               local_download.py run logs (gitignored)
├── tmp/                Disposable build intermediates (gitignored, e.g. tmp/f1_daily.csv)
├── .github/workflows/  daily_scrape.yml — CI pipeline
├── ROADMAP.md
└── run_download.bat    Windows Task Scheduler entry (runs at 12pm and 8pm)
```

`Pipeline/docs/` holds one `*_notes.md` per script covering why it exists, what it does, the procedure, and what it depends on — for every script in `Pipeline/` and `Scrapings/`, regardless of which folder the script itself lives in. Keep these current when a script's behavior changes materially, the same way `ROADMAP.md` is kept current for project-level state.

---

## Dataset inventory

| File | Rows | Cols | Date range | Source |
|------|------|------|------------|--------|
| `Dataset/study1_daily.csv` | 2,679 | 144 | 2018-12-31 → present | `Dataset/Raw/File2_Raw/` |
| `Dataset/study1_hourly.csv` | 46,728 | 151 | 2019-01-01 → 2024-04-30 | `Dataset/Raw/File1_Raw/` + `hourlyLoadDataIndia.xlsx` |
| `Dataset/study2_scada.csv` | 56,988 | 164 | 2024-11-04 → present | `Dataset/Raw/File3_Raw/` |
| `Dataset/study3_states.csv` | 99,208 | 10 | 2018-12-31 → present | `Dataset/Raw/File2_Raw/` |

_Row counts as of 2026-07-11 — grow daily via the automated pipeline, so treat as a snapshot, not a live figure._

### Build commands

```bash
# Full rebuild (all four datasets)
python Pipeline/build_all.py

# Partial rebuild — only File3_Raw changed
python Pipeline/build_all.py --skip-file1 --skip-file2 --skip-states

# Validate after any rebuild
python Pipeline/validate.py

# Regenerate data dictionary
python Pipeline/build_data_dict.py

# Re-download missing raw files
python Scrapings/local_download.py
```

---

## Phase 0 — Correct datasets ✅ COMPLETE (2026-06-24)

Everything here is done and verified. Datasets are as clean as the source data allows.

| Task | Status |
|------|--------|
| Parser fixes: diversity cols, max_demand_met, xb_export/import, concatenated-text PDFs, all-pages fallback | ✅ |
| IR-Line backport to file1/file2 — 21 `ir_*` corridor cols now emitted for every XLS with an IR-Line sheet | ✅ |
| Dedup by date (keep richest row) | ✅ |
| Date handling: PDF → subject-line date; XLS → "Date of Reporting" − 1 day | ✅ |
| Regenerate all three datasets | ✅ |
| Re-run downloader over full range — 70 gaps confirmed irreducible (source-level, not parser failures) | ✅ |
| Spot-check 8 dates × 44 fields (2019–2025) — 0 mismatches | ✅ |
| study1_hourly IR cols: 0 → 21 | ✅ |
| study2_scada: 2 stub rows dropped, dates normalised to ISO | ✅ |
| Live pipeline: `update_live.py` + GitHub Actions auto-push daily | ✅ |
| `run_download.bat` scheduled locally (12pm + 8pm) to catch up if GitHub Actions misses a day | ✅ |
| **Fallback extended to 5 days** — `local_download.py` now checks today through today−4 so missed days are caught even after the laptop is off for a weekend | ✅ |

### Known irreducible gaps in study1_daily (69 total, all individually root-caused 2026-07-11)

**Correction, 2026-07-11 afternoon:** the category table below (57 + 20 + 3 = 80) never actually summed to its own stated "70 total" — an arithmetic error that sat undetected since this table was first written, because the categorization was prose, not re-derived from the live data. Replaced with a real, current, complete count: **69 missing dates**, computed directly from `study1_daily.csv`'s actual date range (matches Phase 3's independent audit). The full enumerated list now lives in `Pipeline/known_gaps.json`, checked automatically by `validate.py` — see 1b below.

**Fully root-caused, 2026-07-11 night, after being asked "should be verified better."** Initially only 4 of the 69 had an individually-confirmed reason; the rest carried a generic placeholder. Closed that gap for real: re-parsed the full raw archive directly (835 files, every month touching one of the 65 remaining dates, via `parser.parse_file()` — not assumed from old prose) and classified each date by hard evidence. Result:

| Category | Count | Evidence |
|----------|-------|----------|
| Confirmed duplicate NLDC republish | 49 | Two files carry the identical subject-line date (e.g. `27.01.19_NLDC_PSP.pdf` and `28.01.19_NLDC_PSP.pdf` both say "for the date 26.01.2019") — the date in between never got its own report. |
| Confirmed genuine archive gap | 16 | No file under any nearby filename resolves to that date at all — a real hole in what NLDC published, not a duplicate-collision side effect. |
| Already individually confirmed (Phase 0 audit) | 4 | 2020-11-13, 2020-11-15, 2025-05-22, 2025-05-23. |

**69 total** — reassuringly close in proportion to the original, never-previously-verified "~57 duplicate + ~20 confirmed-unavailable" prose estimate (kept below for rough historical context only), just now with a named, checkable reason for every single date instead of an assumed category:

| Category (old, rough, superseded by the table above) | Count |
|----------|-------|
| Duplicate subject-line dates (NLDC publishing irregularities, mostly 2020 COVID era) | ~57 |
| Confirmed unavailable from NLDC server (public holidays) | ~20 |
| Edge cases (2018-12-31, 2025-05-22/23) | ~3 |

Treat with forward-fill or time-series-aware imputation at model time.

**New finding, 2026-07-11:** `study2_scada.csv` has its own, previously undocumented set of **17 fully-missing dates** (distinct from the 3 already-documented corrupted-file days below, which exist but with too few slots). Investigated all 17 directly against `Dataset/Raw/File3_Raw/`: 2 are the already-known 2025-05-22/23 NLDC-wide gap; 13 have only a PDF source file published for that date (no `TimeSeries` sheet is possible in a PDF, so no SCADA rows can be extracted — a genuine NLDC format limitation, not a parser bug); 2 (`2025-07-15`, `2025-08-20`) have an XLS file with a `TimeSeries` sheet present but containing zero data rows (header/disclaimer only, confirmed by direct inspection) — also a genuine source-side gap. Full list and per-date reasons in `Pipeline/known_gaps.json`.

### Residual parser gap ✅ CLOSED (2026-07-10)

**Originally measured 2026-07-09** as 12 rows (2019–2022) missing `gen_*`/`outage_*`. Root cause turned out to be two distinct bugs, not one "merged-text blob" as first assumed — see Phase 2 below for the fix. All 12 rows now have `gen_*`/`outage_*` fully populated, verified against the raw PDF text by hand.

| Date | Year |
|------|------|
| 2019-03-29, 2019-03-30 | 2019 |
| 2019-11-18, 2019-11-19 | 2019 |
| 2021-04-22, 2021-05-31, 2021-06-01, 2021-07-10, 2021-09-05, 2021-09-21, 2021-10-15 | 2021 |
| 2022-06-01 | 2022 |

---

## Phase 1 — Feature tables ready for modelling ✅ COMPLETE (2026-07-01)

**Goal:** one command rebuilds everything; automated validation catches regressions; data dictionary published.

### 1a. `build_all.py` — single-command pipeline ✅ COMPLETE (Abhi, 2026-06-29)

Script written and verified. Lives at `Pipeline/build_all.py`.

Implements all 4 steps:
- `Dataset/Raw/File1_Raw` → `f1_daily.csv` (subprocess)
- `Dataset/Raw/File2_Raw` → `Dataset/study1_daily.csv` (subprocess)
- `Dataset/Raw/File3_Raw` → `Dataset/study2_scada.csv` (subprocess)
- `f1_daily` + `hourlyLoadDataIndia.xlsx` → `Dataset/study1_hourly.csv` (in-process join)

Flags: `--skip-file1/2/3`, `--skip-hourly`, `--only-hourly`

Post-run prints row × col counts, date range, overall null %, 8 worst-null cols, and warns if any dataset falls below baseline row count. Does **not** run the validation gate (1b) or push to Kaggle — those are separate.

> **Bug fixed on deploy:** original had `HOURLY_SRC = REPO_ROOT / "hourlyLoadDataIndia.xlsx"` — corrected to `Reference/hourlyLoadDataIndia.xlsx` where the file actually lives. Also fixes `_print_summary` to handle `datetime` col in `study1_hourly.csv`.

### 1b. Validation gate ✅ COMPLETE (2026-07-01)

Script: `Pipeline/validate.py`. Run after every rebuild. Exits 0 on all pass, 1 on any FAIL.

| Check | Dataset | Level if triggered |
|-------|---------|-------------------|
| Column count unchanged | all three | FAIL |
| Row count >= baseline | all three | FAIL |
| No duplicate dates / (date, hhmm) pairs | all three | FAIL |
| Data freshness (latest date within 5 days) | study1_daily, study2_scada | WARN |
| `xb_export_*` >= 0 | study1_daily | WARN |
| `xb_net_* = import − export` per country (abs diff < 0.01) | study1_daily | WARN |
| `ir_*_net = import − export` per corridor (abs diff < 0.01) | study1_daily | WARN |
| Days with < 90 slots (corrupted source file) | study2_scada | **FAIL** |
| Days with slot count outside {95, 96, 97, 98}: > 10 days | study2_scada | FAIL |
| Days with slot count outside {95, 96, 97, 98}: <= 10 days | study2_scada | WARN |
| `freq_hz` outside [47, 52] Hz | study2_scada | WARN |
| Date gaps not in `Pipeline/known_gaps.json` (new/unexplained) | all four | **FAIL** |
| Column null% risen >5pp above `Pipeline/null_baselines.json` | all four | WARN |

Both checks added 2026-07-11, closing what was previously listed here as "not yet implemented":
- **Known-gaps check:** `Pipeline/known_gaps.json` replaces the prose-only gap list with a real, machine-readable enumeration — built from a fresh, complete scan of each dataset's actual missing dates (not reconstructed from the old prose categories, which turned out to not even sum correctly — see the Phase 0 section above). Any gap not in that file hard-FAILs, on the theory that an unexplained new hole is either a real regression or a real new NLDC-side gap that needs the same individual verification the existing entries got, not something to wave through.
- **Null-drift check:** `Pipeline/null_baselines.json` stores each column's current null% as a baseline; a column whose null% rises more than 5 percentage points above it gets a WARN. Deliberately relative to a stored baseline, not an absolute threshold — most columns are legitimately high-null by design (`ir_*`/`xb_*` only populated from 2023+, `wind_gen_er_mu`/`wind_gen_ner_mu` near 100% since those regions have no wind generation), so an absolute "no nulls" rule would be constant noise. Both checks were sanity-tested against a synthetic regression (a fabricated new gap date, a column forced to 50% null) before being trusted — both fired correctly.

> **Col count note — resolved 2026-07-10:** study2_scada's 164 columns are exactly `study1_daily`'s 144 columns (fully present, none missing — verified by direct diff) plus exactly 20 real-time/SCADA-specific columns (`time`, `hhmm`, `freq_hz`, `demand_met_mw`, per-source real-time generation, `net_demand_met_mw`, `total_gen_mw`, `net_trans_exchange_mw`, and 6 `time_max_demand_met_*` columns). 144 + 20 = 164 exactly, no gap. The "165" in earlier roadmap prose was a stale estimate written before the dataset was actually built and counted — not a missing column.

> **Two bugs found and fixed 2026-07-11, while re-verifying Phase 4's work against the full pipeline (not just re-reading docs):**
> 1. `check_study1_hourly()` parsed its date column with `format="mixed", dayfirst=True` — wrong for this column, since both `date` and `datetime` are uniformly ISO (`YYYY-MM-DD[ HH:MM:SS]`), verified against all 46,728 rows. `dayfirst=True` still silently swapped month/day for at least one real row (`2024-04-12` → misreported as `2024-12-04`), making the printed "latest datetime" wrong even though the underlying data was always correct (true latest = `2024-04-30`, matching this doc's own dataset-inventory table the whole time). Fixed by parsing with the exact known format instead of guessing.
> 2. The 63-slot-day check in `check_study2_scada()` only special-cased that one literal value by name. Two more severely-corrupted days — `2024-11-20` and `2025-04-01`, 1 slot each — were found while building `ML/Study2/features.py` (2026-07-11) but had only ever been falling into the generic "slot count outside 96" WARN, indistinguishable from a benign 95-slot DST day. Generalized the check to hard-FAIL any day under 90 slots (matching the `MIN_SLOTS_PER_DAY` threshold already used in `ML/Study2/features.py`), and it now names all 3 bad days explicitly. `validate.py` correctly reports this as a FAIL — that's by design for a known-but-uncorrectable source issue, not a regression; `Pipeline/build_all.py` does not currently invoke `validate.py`, so this has no effect on the automated CI pipeline.
>
> Also confirmed (not a bug, a genuine source-data finding, same category as the 2022-08-11 hydro mismatch below): the `xb_net` WARN fires for 2024-08-08 (Bhutan diff 28.19 MU, Nepal diff 2.63 MU) because NLDC's own source file (`08.08.24_NLDC_PSP.xls`) has an internal inconsistency — their own published "Net" row doesn't arithmetically equal their own Import − Export rows in the same file. Confirmed directly against the raw XLS; the parser is faithfully reporting NLDC's own numbers, not miscalculating. The other ~24 flagged rows (mostly Nepal, sitting right at the 0.01 MU tolerance boundary) are floating-point-scale rounding in NLDC's own published figures, not a parser issue.

### 1c. Data dictionary ✅ COMPLETE (2026-07-01; updated 2026-07-10)

Script: `Pipeline/build_data_dict.py`. Generates `Dataset/data_dictionary.xlsx`.

Five sheets: `study1_daily` (144 cols), `study2_scada` (164 cols), `study1_hourly` (151 cols), `study3_states` (10 cols, added 2026-07-10 — see audit note below), `master` (union of all unique columns, 180). Fields: `column_name`, `datasets`, `unit`, `source_section`, `schema_start_date`, `notes`. All columns across all five sheets have unit and source section populated.

> **Bug found and fixed during the 2026-07-10 audit:** `build_data_dict.py` was never updated when `study3_states.csv` was built earlier that same day — it silently generated a 4-sheet dictionary missing the new dataset entirely, with no error. Fixed: added `study3_states` as a fifth sheet, added its 9 new column definitions, folded it into the `master` union (171 → 180 columns).
>
> **Resolved 2026-07-10:** `Dataset/data_dictionary.xlsx` is now committed to the repo and added to the Kaggle push list. Reasoning: unlike `f1_daily.csv` (a disposable build intermediate no one should need to look at), this file *is* the deliverable — it's what makes 180 cryptic column names legible to a collaborator or a stranger on Kaggle. It only changes when the schema changes (new dataset/columns — rare, deliberate), so it's not wired into daily automation; regenerate and recommit it manually (`python Pipeline/build_data_dict.py`) whenever that happens. Note this was also a functional fix, not just a documentation one: `daily_scrape.yml`'s Kaggle push step does `cp Dataset/data_dictionary.xlsx ...` against a freshly-checked-out repo in CI — that `cp` would have failed once added if the file weren't actually committed, since CI has no access to a locally-generated-but-uncommitted file.

### 1d. Kaggle publish ✅ COMPLETE

Five files (`study1_daily.csv`, `study1_hourly.csv`, `study2_scada.csv`, `study3_states.csv` — the fourth CSV added in Phase 2, 2026-07-10 — plus `data_dictionary.xlsx`, added 2026-07-10) auto-pushed to Kaggle on every daily update via GitHub Actions (`kaggle datasets version`). `KAGGLE_USERNAME` / `KAGGLE_KEY` secrets are set and working.

---

## Audit: Phase 0-1 re-verification (2026-07-10)

After finding real bugs in Phase 2 and Phase 3 by actually re-testing their claims instead of trusting the write-ups, Phase 0 and Phase 1 were put through the same adversarial check — not just re-reading their documentation, but independently re-deriving evidence against raw source files and live code execution.

**What was checked and confirmed correct:**

- **164 vs 165 column count discrepancy** (previously flagged as unresolved prose): traced definitively. `study2_scada` = all 144 `study1_daily` columns (verified present via direct diff, none missing) + exactly 20 real-time SCADA-only columns = 164 exactly. The "165" was a stale pre-build estimate, not a bug.
- **Fresh field-by-field spot-check**, two dates never covered by the original 8-date check: **2022-03-10** (PDF era, 30 fields checked against raw text) and **2024-09-16** (XLS era, 44 fields including all 12 `xb_*` cross-border and IR-Line corridor values checked against raw sheets). **74 independent field checks, 0 mismatches** — this also directly confirms the diversity, max_demand_met, xb_export/import, and IR-Line backport fix claims.
- **Irreducible-gap claim**: while locating spot-check files, found a real, previously-unlisted-by-date example — `2020-11-13` and `2020-11-15` are both genuinely absent from the raw archive (no source file exists under any name), consistent with the documented "duplicate subject-line dates" category. Confirms the gap category is real, not a parser failure being miscategorized.
- **Dedup-by-date logic**: found a real duplicate case in the same window (`17.11.20` and `18.11.20` both carry the subject-line date 2020-11-17). Parsed both independently — zero differing field values between them (a genuine NLDC re-publish, not conflicting reports), so the "keep richest row" tie-break is safe here regardless of which one wins.
- **Incremental live-update logic**: `append_study1`, `append_study2`, and `append_study3` in `Scrapings/update_live.py` each independently tested by removing a known date from a test copy of its CSV, re-appending via the actual function, and diffing against the full-rebuild original. **All three byte-identical.**

**What was checked and found broken, then fixed:**

- `Pipeline/build_data_dict.py` had not been updated when `study3_states.csv` was built earlier the same day — silently produced a 4-sheet dictionary missing the new dataset, no error raised. Fixed (see 1c above).

**What was checked and found unresolved (flagged, not silently decided):**

- `Dataset/data_dictionary.xlsx` has never been committed to git and isn't part of the Kaggle push, despite Phase 1c calling it "published." Needs an explicit decision (see 1c above).

**Update, 2026-07-10 (later same day) — the original 8-date spot-check has now been fully re-derived from scratch, not just supplemented.** All 8 original dates (2019-03-15, 2020-06-07, 2021-03-22, 2022-08-11, 2023-02-18, 2023-10-06, 2024-01-02, 2025-01-21) were independently re-checked: for each, the correct raw source file was re-located (accounting for the subject-line-date vs. filename-date offset quirks documented elsewhere in this roadmap), the raw text/table dumped, and 29-44 comparable fields per date read by hand and checked against the CSV — not by re-running the parser and comparing its output to itself, but by reading the original PDF/XLS content directly. **Roughly 280 individual field comparisons across all 8 dates, zero mismatches.** Full detail in the updated "Appendix: Spot-check log" below.

One genuinely new finding along the way: the 2022-08-11 PDF has an internal inconsistency in NLDC's own source document — Section A's hydro generation total (766 MU) doesn't match Section G's hydro total (775 MU) for the same day. Confirmed the parser correctly preserves this distinction (`hydro_gen_total_mu` = 766 from Section A, `gen_hydro_mu` = 775 from Section G) rather than incorrectly reconciling the two — each field faithfully reflects its own source section, exactly as it should.

The full 70-gap enumeration was not re-derived exhaustively (that would mean checking all 70 dates individually) — but 2 additional gap dates (2020-11-13, 2020-11-15) were found and confirmed to match the documented category during this process, which is real corroborating evidence rather than an assumption.

---

## Phase 2 — Coverage expansion ✅ COMPLETE (2026-07-10)

**Owner:** Sagnik — this is scraper/parser work, same skillset as Phase 0/1, not delegated.

| Task | Priority | Status |
|------|----------|--------|
| Text-regex fallback for generation/outage on 12 merged-blob PDFs (last ~0.5% of rows) | Medium | ✅ Done |
| §C state-level table → `study3_states.csv` (~40 state entities, daily) | Low | ✅ Done |
| Backfill 2025-05-22/23 if NLDC re-publishes | Low | 🔲 Still blocked on NLDC (not actionable by us) |

### 2a. Merged-blob generation/outage fix

**What was actually wrong** (found by inspecting raw PDFs directly, not by re-reading the original theory): the "merged-text blob with no column grid" theory was wrong. Two distinct, unrelated bugs were found instead:

1. **Some 2019 PDFs (e.g. 29/30.03.19) DO have a well-structured Section G table** — `pdfplumber.extract_tables()` detects it fine — but the "All India" header cell renders as a stray `'0'` character. The parser's `_pdf_generation()` only matched by searching the header text for "all india", so it silently skipped an otherwise-perfectly-good table.
2. **Some 2021 PDFs never produce a detected table for Section F/G at all** (no visible gridlines in that part of the page), even though `extract_text()` returns the section as normal, cleanly whitespace-delimited rows.

**What was built:** a single new function, `_pdf_gen_outage_text_fallback()`, added to both `Scrapings/parse_psp_pdf_xls_file1.py` and `parse_psp_pdf_xls_file2.py` (the two files are byte-identical, so both got the same edit). It works directly on `extract_text()` output — bypassing `extract_tables()`'s column-header matching entirely — and matches row labels by stripping everything but letters (handles labels that gain/lose internal spaces across report eras, e.g. "Gas, Naptha & Diesel" vs "Gas,Naptha&Diesel"), then pulls data columns *positionally* from the numbers found on each line, since a trailing %Share column exists in some report eras and not others. Wired into `parse_pdf()` as a last resort, only filling keys still missing after the existing table-based passes — never overwrites a correctly-parsed value.

**Bonus fix, found along the way:** rebuilding surfaced two new all-null rows dated 2014-08-14/17 that hadn't existed in the previously-committed dataset. Root cause: `15.08.20_NLDC_PSP.pdf` and `18.08.20_NLDC_PSP.pdf` are old enough to lack a subject line, so the parser falls back to the PDF's own "Date of Reporting" field — which itself has a genuine NLDC-side typo, literally printing "15-Aug-**14**" instead of "15-Aug-**20**". Added a `MIN_VALID_DATE` guard (2018-12-01, the dataset's documented start) in `build_dataset()` that drops any row dated earlier and logs what it dropped, since such a date can only be a source/parse artifact.

**Verification:** all 12 originally-affected dates confirmed populated (`gen_total_mu`, `outage_total_total_mw`, and individual `gen_coal_mu` etc.), cross-checked by hand against raw PDF text for 3 dates. The 2 bogus 2014 rows confirmed dropped; `study1_daily`'s date range is back to the documented 2018-12-31 start.

### 2b. New dataset: `Dataset/study3_states.csv` — §C state-level table

**Goal:** extract NLDC's §C "Power Supply Position in States" section — ~40 state/UT/entity rows per day (max demand met, shortage, energy met, drawal schedule, OD/UD, max OD, energy shortage) — into a fourth published dataset, long format (one row per state per day).

**New parser:** `Scrapings/parse_psp_states.py`, self-contained (not built on file1/file2, since it needs a fundamentally different multi-row-per-file output shape). Supports both PDF (2019-2022, `pdfplumber` table detection) and XLS (2023+, MOP_E sheet) eras — both render §C as the same 9-column table at the same offsets.

**Two real data-quality problems found and solved, both needing whole-archive visibility to fix correctly (not fixable per-file):**

1. **Region label (NR/WR/SR/ER/NER) is a merged cell in the source template**, rendered on whichever row a fixed group-size calculation happens to land on. Initial assumption was that this varied by date and could be recovered with per-file forward/backward-fill — wrong: verified across the full 2,722-file archive that only 12 of 43 canonical state entities ever had a region label anywhere, because the label's position is a deterministic template artifact, not something that varies with more data. Fixed with a static `STATE_TO_REGION` map (built from the states that did resolve via majority vote, plus direct verification against raw file dumps for the other 31) as the **primary** source of truth, with cross-date majority voting kept only as a fallback for any future entity not yet in that map.
2. **State names extract inconsistently across report eras** — concatenated-text PDFs drop spaces ("TamilNadu"), some cells wrap across two table rows ("J&K(UT) &" / "Ladakh(UT)"), and naming genuinely changed over time (J&K's Aug 2019 split into J&K + Ladakh UTs; Puducherry's old "Pondy" abbreviation). Without normalizing these first, the same real-world entity fragmented into up to 6 different `state` strings, which also starved the majority vote of enough samples per variant. Fixed with a `STATE_NAME_ALIASES` map applied before region resolution — consolidated 59 raw variants down to 43 canonical entities.

One row (`state` literally extracted as `"0"`, 2023-12-04) is the same header-corruption pattern as fix 2a but corrupting a state name instead of a column header — dropped rather than guessed, since which state it was can't be recovered without manually opening that file.

**Known residual gap:** `10.05.19_NLDC_PSP.pdf` is rendered entirely in Hindi/Devanagari (not NLDC's usual bilingual format) — the only PDF in the whole archive like this. The English-language "States" section-header match can't find it, so that file's date has no §C data. `study1_daily`/`study1_hourly` aren't affected (their parsers don't depend on that text match). **Date correction, 2026-07-11:** the missing row is for **2019-05-09**, not 2019-05-10 as previously stated here — confirmed directly from the PDF's own (English-language) subject line, "Sub: Daily PSP Report for the date 09.05.2019," despite the file being named `10.05.19` (the filename-date-vs-data-date offset this project has documented elsewhere). Not worth a Hindi-specific fix for one file; treated the same as the other rare, low-value gaps documented in Phase 0.

**Schema:** `date, region, state,` then 7 metrics (`max_demand_met_mw`, `shortage_max_demand_mw`, `energy_met_mu`, `drawal_schedule_mu`, `od_ud_mu`, `max_od_mw`, `energy_shortage_mu`). Long format chosen over wide (one row per date) because ~40 states × 7 metrics would mean ~280 columns — long format matches how a per-entity time series is actually queried/joined.

**Verification:** `Pipeline/validate.py --only study3` passes all 6 checks (column/row counts, no duplicate (date, state) pairs, freshness, every row has a valid region, consistent ~36-state-per-day count). Spot-checked 5 state/date combinations by hand against raw source files (2 PDF-era, 3 XLS-era) — all match exactly. Final dataset: **99,208 rows × 10 columns**, 2018-12-31 → present.

### Still open (both low priority, unchanged — this was never expected to fully close)

1. 2025-05-22/23 backfill — not actionable until/unless NLDC re-publishes those dates on their own end. Re-checked directly on 2026-07-10 using the actual production downloader (`download_psp_new.old_url()` + `fetch_bytes()`, which already handles NLDC's TLS cert issue via `verify=False` — no tooling limitation this time): both the `.xls` and `.pdf` URLs for both dates return clean 404s, not errors. Cross-checked against the raw archive's filename sequence — `01.05.25` through `21.05.25` are present with no gaps, then it jumps straight to `24.05.25` with no offset or renamed file hiding in between. This is a genuine, confirmed 2-day hole in what NLDC published, not a scraper or tooling gap on our end.
2. `10.05.19` Hindi-only PDF gap in `study3_states.csv` (missing date: 2019-05-09, corrected 2026-07-11) — see above, low value to fix for one date.

### Where the code lives

- Merged-blob fix: `Scrapings/parse_psp_pdf_xls_file1.py`, `parse_psp_pdf_xls_file2.py` (identical files, both patched)
- States parser: `Scrapings/parse_psp_states.py` (new, self-contained)
- Pipeline entry point: `Pipeline/build_all.py` (new `--skip-states` flag, new step 3)
- Validation: `Pipeline/validate.py` (new `check_study3_states()`, new `--only study3`)

### Environment

Local Python, same as the existing `Scrapings`/`Pipeline` scripts — no Colab/ML environment needed, this is pure data engineering, not modelling.

---

## ML Development Environment

This section covers decisions made for how the ML work across Phase 3 and Phase 4 will be developed, shared, and deployed. These decisions account for two collaborators working on the same codebase.

### Environment choice: GitHub + Google Colab

Development will be done in Google Colab, with notebooks version-controlled in this repository. This was chosen over local development for two reasons: the project has two collaborators, and local development requires both to maintain identical environments and hardware. Colab eliminates that friction entirely. Anyone with access to the repository can open a notebook in Colab and run it immediately with no setup.

Local development was considered and rejected as the primary environment despite adequate hardware (Ryzen 9 8945HS, RTX 4060, 16GB RAM) because the collaboration requirement outweighs the hardware advantage. The datasets are small enough (study1_daily: 2,660 rows; study2_scada: 55,068 rows) that Colab's free T4 GPU is sufficient for all models planned, including LSTM. Training times are expected to be in the range of seconds to a few minutes for both studies.

Kaggle notebooks were also considered. They were rejected as the primary development environment because collaboration between two accounts on Kaggle is awkward (notebooks fork rather than share a single source), and the 30 GPU hours per week quota becomes limiting during active iteration. Kaggle will instead be used as a public mirror: once a notebook is complete and clean, it will be uploaded to the existing Kaggle dataset page so that dataset users can find the accompanying analysis. This serves the portfolio goal without making Kaggle the development bottleneck.

### Workflow

```
GitHub repo (ML/ folder)
    |-- open notebook in Colab from GitHub
    |-- load dataset via Kaggle API (one line, credentials already set up)
    |-- develop, train, iterate
    |-- commit updated notebook back to repo via git
    |-- on merge: GitHub Actions runs predict.py to generate daily inference output (CSV, not JSON -- see Phase 3)
    |-- Kaggle: upload clean finished notebooks as dataset companion notebooks (portfolio)
```

**Concrete Colab setup, made explicit 2026-07-11** (this was previously only described at the "open notebook in Colab" level above — never spelled out precisely, which meant it had never actually been verified end-to-end). Every notebook in both `ML/Study1/notebooks/` and `ML/Study2/notebooks/` assumes the working directory is the **study folder itself** (`ML/Study1/` or `ML/Study2/`), not the `notebooks/` subfolder the `.ipynb` file lives in — that's what makes a bare `import features` and a relative `data/study1_daily.csv` / `data/study2_scada.csv` path resolve correctly, matching the convention Study 1's notebooks were already built with:

```
!git clone https://github.com/Deducinnamoroll/Grid-Sentinel.git
%cd Grid-Sentinel/ML/Study1        # or ML/Study2 -- NOT .../notebooks
!kaggle datasets download -d halcyonvector/india-power-grid-nldc-daily-psp-reports -p data --unzip
# then open/run the desired notebook from ML/Study1/notebooks/ or ML/Study2/notebooks/
```

**Study 2 has one new requirement Study 1 doesn't:** `ML/Study2/features.py`'s `build_study1_residual_signal()` loads `ML/Study1/features.py` directly off disk (via `importlib`, resolved relative to Study 2's own file location — see `study2_features_notes.md`), so **the full repo must be cloned**, not just the `ML/Study2/` folder on its own — downloading a single folder or uploading just `features.py` to a Colab session will fail with a `FileNotFoundError` looking for `ML/Study1/features.py`. `!git clone` (as above) already satisfies this; it's only a problem if someone tries to shortcut the setup.

**Verified 2026-07-11:** all 5 `ML/Study2` notebooks were fixed (removed a leftover `sys.path.insert(0, "..")` that assumed a different, inconsistent working directory than the `data/...` paths in the same cells — a real bug that would have broken for whoever actually tried running them in Colab) and re-executed end to end with the working directory set to `ML/Study2/` and a real `data/study2_scada.csv` in place (simulating exactly what the Kaggle download step produces) — all numbers matched exactly. This session's actual work was done locally against the cloned repo's `Dataset/` folder directly, not in Colab (no Colab/Google access in this environment) — chosen for fast iteration and direct verification against live data, but every notebook was engineered and tested to match the Colab-ready convention above, not the local shortcut used to verify it.

**Credentials — use Colab Secrets, not a hardcoded key, 2026-07-11.** The original `01_eda.ipynb` header had `os.environ["KAGGLE_KEY"] = "enter your kaggle api token..."` as a placeholder meant to be filled in and run interactively, never committed back with a real value in it. That's a real risk given this repo is public — a real key typed into that line and then committed (or "Save a copy in GitHub"-ed) would be visible to anyone and would stay in git history even after being removed later. Use Colab's **Secrets** manager instead (key icon in the left sidebar): add `KAGGLE_USERNAME` and `KAGGLE_KEY` there once (toggle "Notebook access" on), then in any cell:
```python
import os
from google.colab import userdata
os.environ["KAGGLE_USERNAME"] = userdata.get("KAGGLE_USERNAME")
os.environ["KAGGLE_KEY"] = userdata.get("KAGGLE_KEY")
```
No secret value ever appears in a cell that gets saved or committed. `01_eda.ipynb`'s own placeholder lines were left as-is (they're what the notebook's original author wrote, still only a placeholder, not a live risk on their own) — the two new `*_run_all.ipynb` notebooks below use the Secrets pattern from the start.

**One-file-per-study convenience notebooks, added 2026-07-11** (Sagnik asked for a way to open one file instead of hunting through 4-5 separate ones per study, since each Colab "Open from GitHub" spawns its own fresh runtime): `ML/Study1/notebooks/study1_run_all.ipynb` and `ML/Study2/notebooks/study2_run_all.ipynb` concatenate each study's notebooks in their documented run order, with one shared Secrets-based setup cell at the top (clone, cd, pip install, credentials, Kaggle download). The original per-stage notebooks are **not replaced** — they're still the source of truth for each individual stage; these are wrappers for convenience and for sharing a single runnable file with a collaborator. Verified end to end locally (all cells, in sequence, against real data) before committing.

**Real bug found while building the Study 1 combined notebook:** `04_era1_ramp_characterization.ipynb` parsed `study1_hourly.csv`'s `datetime` column with `format="%d-%m-%Y %H:%M"` — the actual data is ISO format (`%Y-%m-%d %H:%M:%S`), confirmed directly against the live file. This would have crashed the notebook if anyone actually ran it against current data, despite this notebook being reported as already run and verified during Phase 3 (its Era 1 correlation results were reported as real numbers) — never re-confirmed since then, apparently. Fixed; re-verified the corrected notebook reproduces essentially the same correlation finding (-0.418/-0.371 vs. the originally reported -0.429/-0.367 — same direction and magnitude, small natural drift, not a discrepancy worth chasing further).

### Code format

Jupyter notebooks for EDA and model training. Python scripts for the production inference pipeline that GitHub Actions runs daily. The split is intentional: notebooks allow interactive exploration and visualisation during development; scripts are reproducible, testable, and CI-friendly.

Feature engineering logic that is shared between training notebooks and the inference script lives in a standalone Python module (`ML/Study1/features.py`, `ML/Study2/features.py`) so that the same transformations are applied at train time and inference time without duplication.

### Repository structure for ML work

```
ML/
├── Study1/
│   ├── notebooks/
│   │   ├── 01_eda.ipynb                        EDA: demand trends, seasonality, generation mix, missing data
│   │   ├── 02_features.ipynb                   Feature engineering: lags, rolling stats, seasonality encoding
│   │   ├── 03_baseline.ipynb                   LightGBM baseline, time-aware split, metrics, feature importance
│   │   └── 04_era1_ramp_characterization.ipynb Era 1 intra-day ramp analysis (2019-2022) vs RES share
│   ├── features.py                 Shared feature engineering module (used by notebooks and predict.py)
│   └── predict.py                  GitHub Actions inference script -- see below
└── Study2/
    ├── notebooks/
    │   ├── 00_era2_daily_correlation.ipynb  Era 2 corridor/cross-border vs frequency-stress correlation
    │   ├── 01_eda.ipynb                     Era 3 SCADA EDA: violation/ramp rate by hour/season/gen-mix
    │   ├── 02_features.ipynb                Feature table inspection + class balance
    │   ├── 03_violation_baseline.ipynb      LightGBM baseline, frequency-violation target
    │   └── 04_ramp_shock_baseline.ipynb     LightGBM baseline, ramp-shock target
    ├── features.py                 Shared feature engineering module (used by notebooks and predict.py)
    └── predict.py                  GitHub Actions inference script -- see below
```

**Resolved (2026-07-10/11), superseding earlier plans on this page:** neither `predict.py` loads a saved model or outputs JSON, and there is no `models/` directory in either `Study1/` or `Study2/` -- both scripts retrain their model fresh on every run instead (training takes seconds on these dataset sizes), which sidesteps the "how do we version/store a trained model artifact" question this section originally left open rather than answering it. Output is CSV, not JSON (`Dataset/predictions/study1_forecast.csv`, `Dataset/predictions/study2_risk.csv`) -- simpler to append to with pandas, and matches every other output format in this repo. See `Pipeline/docs/study1_predict_notes.md` / `study2_predict_notes.md` for the full reasoning.

### Environment file

`ML/environment.yml` defines the conda environment for reproducibility. Key dependencies: Python 3.11, pandas, numpy, scikit-learn, lightgbm, torch, matplotlib, plotly, kaggle, jupyterlab.

---

## Central research question (2026-07-09) — spans Phases 3, 4, 5, 6

**As India's grid monitoring granularity and renewable penetration have both increased 2019→2026, how has the observability and predictability of grid stress (demand ramps, frequency deviations) evolved — and once corridor/cross-border visibility exists in the data, do inter-regional congestion and cross-border exchange meaningfully predict short-term grid stress?**

This supersedes treating Study 1 and Study 2 as two unrelated baselines. It's answered across **three eras**, each analyzed using the dataset that actually covers it — all three CSVs are load-bearing, none is decorative:

| Era | Window | What's available | What it answers | Dataset(s) used |
|---|---|---|---|---|
| **1 — Pre-corridor** | 2019–2022 | Daily features (full range) + hourly demand curve | Intra-day ramp characteristics; RES-share growth trend; establishes the baseline "ramp shocks becoming more frequent" evidence | `study1_daily.csv` + `study1_hourly.csv` |
| **2 — Corridor-visible** | 2023–Oct 2024 | Daily features + IR-line (from 2023-01-01) + cross-border (from 2023-07-06) | Daily-resolution first pass: does corridor congestion / cross-border exchange correlate with daily frequency-band stress (`freq_pct_*`)? | `study1_daily.csv` |
| **3 — Live full-visibility** | Nov 2024–present | 15-min SCADA + full corridor/cross-border broadcast + real frequency violations | Live, high-resolution, early-warning (lead-time) classifier: corridor/cross-border-aware ramp-shock + frequency-violation prediction | `study2_scada.csv` |

**Why three eras, not one uniform model:** verified directly against the data (2026-07-09) — IR-line columns are null before 2023-01-01 (only 1,253 of 2,677 daily rows populated) and cross-border columns before 2023-07-06. There is no way to test the corridor/cross-border relationship across the full 2019–2026 span because the columns simply don't exist for most of it. Rather than pretending otherwise, the study is structured around what each era's data actually supports — this is a feature of the design, not a workaround.

**Cross-phase dependency (accepted 2026-07-09):** phases run sequentially where the research question requires it — Phase 4's Era 3 model consumes Phase 3's forecast-residual signal, and Era 2's findings inform Era 3's feature design. Both collaborators are fine waiting on each other where the design calls for it; this is no longer being avoided for parallelism's sake.

**Novelty check (verified via web search, 2026-07-09) — what already exists vs. what doesn't:**
- Corridor-congestion → frequency-stability modelling: **exists** for European grids (explainable-AI studies on Germany and three European synchronous areas) — established method, **not done for India**.
- Cross-border-exchange → grid-stability modelling: **only qualitative/policy discussion found** (e.g. the real April 2020 "9pm9minute" event, where neighbouring countries' hydro ramped up to help balance India's grid) — no quantitative model found for India or elsewhere in this specific form.
- RE-penetration driving rising Indian grid stress: **a macro-level claim already exists** — an EAC-PM policy paper reported 2026-07-07 (two days before this analysis) makes almost this exact claim. This project's contribution must be positioned as a **granular, reproducible, ML-based complement to that finding**, not a discovery claim.
- A three-era, evolving-observability design tied to one country's actual operational dataset: **no matching paper found** (related but distinct: PSML multi-scale benchmark dataset, Smart5Grid observability platform — neither is this specific design).
- Second, targeted search for "India + frequency violation + ramp event + corridor congestion + ML" returned **no matching papers** — this specific combination, for India, appears genuinely open.

---

## Phase 3 — Study 1: daily forecasting + Era 1 ramp characterization ✅

**Owner:** collaborator (handed off 2026-07-09, completed 2026-07-10).

**Datasets used:** `study1_daily.csv` (2,660 rows × 144 cols, 2019–present) for the forecasting model and the full-history RES-share trend; `study1_hourly.csv` (46,728 rows × 151 cols, 2019–2024, frozen) for the **Era 1** intra-day ramp characterization — this is a real analytical deliverable, not a dashboard-only afterthought.

**Targets:**
1. Next-day national demand/energy regression. **Note:** confirm the exact column before building — the CSV header currently has `max_demand_met_total_mw` / `evening_peak_demand_total_mw` and `energy_met_total_mu`, not `peak_demand_met_total_mw` as earlier prose in this doc said.
2. Era 1 (2019–2022) intra-day demand-ramp magnitude/frequency characterization from the hourly curve, correlated against `share_res_pct` — a historical analysis, not a live model.

### Goal

Predict next-day national (and ideally per-region) demand/energy from `study1_daily.csv`, output a forecast-residual signal for Phase 4 to consume, and produce the Era 1 historical ramp-characterization analysis from `study1_hourly.csv` that motivates the whole project's central research question.

### What already exists

`ML/environment.yml`, `ML/Study1/features.py`, all four notebooks (`01_eda.ipynb`, `02_features.ipynb`, `03_baseline.ipynb`, `04_era1_ramp_characterization.ipynb`) under `ML/Study1/notebooks/`, and `ML/Study1/predict.py` (built and wired into CI 2026-07-10 — see below) are all built and committed.

Confirmed target column: `max_demand_met_total_mw`.

### `predict.py` — built 2026-07-10

Retrains the LightGBM baseline fresh on every run rather than loading a saved model artifact (training takes seconds on this dataset size), sidestepping the "how do we version a model file" question this section originally left open. Produces tomorrow's forecast and maintains `Dataset/predictions/study1_forecast.csv` — a running log with `predicted_mw`, and `actual_mw`/`residual_mw` backfilled once each target date's real data arrives. That residual is the forecast-residual signal Phase 4 is designed to consume. Wired into `.github/workflows/daily_scrape.yml` as a CI step, gated so a forecasting failure can never block the day's actual data from committing. See `Pipeline/docs/study1_predict_notes.md` for the full design and verification (live run, idempotency check, isolated backfill test).

### Bug found and fixed (2026-07-10, after initial "done" claim)

The first committed version of `03_baseline.ipynb` had a real off-by-one bug: it used `TARGET_lag1` as both the delta-training anchor and the naive-persistence comparison baseline. But `TARGET_lag1` was computed from lag features built **before** the target got shifted forward to represent "tomorrow's demand" — so after the shift, `lag1` ended up anchored **two days** before the forecast date instead of one. This wasn't caught by re-reading the notebook; it was found by actually re-running the code against the live data.

**Verified empirically:** a correctly-anchored (1-day-lag) naive-persistence baseline (MAPE 0.0242, RMSE 6,978.5) actually **beat** the originally-reported LightGBM result (MAPE 0.0247, RMSE 7,387.8) — meaning the "model beats naive persistence" claim, as first reported, was not true; the comparison itself was broken.

**Fix:** added `make_next_day_target()` to `features.py` — a single function that shifts the target *and* preserves today's true value as `{TARGET}_today` before doing so, so the correct anchor can never again be silently destroyed by an in-place overwrite. `03_baseline.ipynb` updated to use it. Re-verified by re-running the corrected pipeline end-to-end against the live dataset:

**Corrected results (2026-07-10, verified):**
- LightGBM: **MAPE 0.0175, RMSE 5,242.9, MAE 3,800.8**
- Naive persistence (correct 1-day anchor): MAPE 0.0242, RMSE 6,978.5, MAE 5,258.4
- LightGBM genuinely and comfortably beats naive persistence — a *larger* margin than the original (invalid) comparison claimed.

Also fixed while verifying: `01_eda.ipynb` had its single cell's content accidentally duplicated ~15x (harmless but messy — deduped to one clean copy); `04_era1_ramp_characterization.ipynb` sorted the hourly frame by `"date"` alone before computing hour-to-hour deltas, which isn't guaranteed to preserve correct within-day hour order under an unstable sort — changed to sort by `"datetime"`.

Other results (unaffected by the bug above, verified sound on review):
- Era 1 ramp magnitude/frequency vs `share_res_pct`: correlation -0.367 / -0.429 respectively (monthly-aggregated, 2019–2022) — chart and `era1_ramp_vs_res_share.csv` produced. Note: both series share strong annual seasonality, so this correlation may be partly confounded by season rather than a clean RES-driven effect.
- 69 missing dates found in `study1_daily.csv` (vs ~70 expected — consistent with Phase 0 documentation).
- `ir_*`/`xb_*` corridor columns (only populated from 2023+) excluded from Study 1 features; revisit only if later feature importance suggests value.

### What needs to be built

```
ML/
├── environment.yml                        conda env: Python 3.11, pandas, numpy, scikit-learn,
│                                           lightgbm, torch, matplotlib, plotly, kaggle, jupyterlab
└── Study1/
    ├── notebooks/
    │   ├── 01_eda.ipynb                   Demand trends, seasonality, generation mix shift, missing data
    │   ├── 02_features.ipynb              Lag features, rolling stats, calendar/seasonality encoding
    │   ├── 03_baseline.ipynb              LightGBM baseline, time-aware split, metrics, feature importance
    │   └── 04_era1_ramp_characterization.ipynb   Intra-day ramp magnitude/frequency from study1_hourly
    │                                              (2019–2022), correlated against share_res_pct — the Era 1 deliverable
    ├── features.py                        Shared feature-engineering functions
    └── predict.py                         ✅ Built 2026-07-10. Outputs the next-day forecast AND the
                                            forecast-residual signal (actual − predicted) that Phase 4 consumes
```

### Where the data lives

`Dataset/study1_daily.csv` — one `date` column + 143 feature columns:

| Group | Example columns | Availability |
|-------|-------------|--------------|
| Regional demand/energy | `evening_peak_demand_*_mw`, `energy_met_*_mu`, `max_demand_met_*_mw` | Full range |
| Generation mix | `gen_coal_mu`, `gen_hydro_mu`, `gen_nuclear_mu`, `gen_res_mu`, `hydro_gen_*_mu`, `wind_gen_*_mu`, `solar_gen_*_mu` | Full range |
| Shortages | `peak_shortage_*_mw`, `energy_shortage_*_mu` | Full range |
| Frequency | `freq_fvi`, `freq_pct_below_497` … `freq_pct_above_5005` | Full range |
| IR-Line corridor flows | 21 `ir_*` cols (export/import/net per corridor) | From 2023-01-01 (verified) |
| Cross-border exchange | 12 `xb_*` cols (Bhutan/Nepal/Bangladesh/Myanmar) | From 2023-07-06 (verified) |
| Diversity / RES share | `diversity_regional`, `share_res_pct` | Full range |

`Dataset/study1_hourly.csv` — used specifically for Era 1 (2019–2022, though the file runs to April 2024):

| Group | Example columns | Notes |
|-------|-------------|-------|
| Hourly national + regional demand | `National Hourly Demand`, `Northern/Western/Eastern/Southern/North-Eastern Region Hourly Demand` | The only genuinely hourly signal in this file — everything else is `study1_daily`'s features broadcast across 24 rows |

70 daily rows have known irreducible gaps (documented under Phase 0) — forward-fill or exclude, don't blindly interpolate.

### Step by step

1. **`01_eda.ipynb`** — plot demand over time, check yearly/weekly/festival seasonality, quantify missingness, confirm the exact target column.
2. **`02_features.ipynb` + `features.py`** — lag features (t−1, t−7, t−365), 7-day/30-day rolling mean/std, calendar features. Every reusable transform goes into `features.py`, never pasted inline.
3. **`03_baseline.ipynb`** — time-aware split (2019–2022 train, 2023 val, 2024–2026 test). Train LightGBM/XGBoost. Compare against naive persistence. Compute and expose the forecast residual as a reusable artifact (needed by Phase 4).
4. **`04_era1_ramp_characterization.ipynb`** — using `study1_hourly.csv` restricted to 2019–2022: compute hour-to-hour demand deltas per region, define a ramp-magnitude metric, plot its trend over time against `share_res_pct` from `study1_daily`. This is the chart that establishes the project's central motivating claim and feeds Phase 6's introduction.
5. **(Stretch, later)** — LSTM or Temporal Fusion Transformer for the demand forecast, once the LightGBM baseline and its feature importances are understood.
6. **Metrics** — MAPE, RMSE, MAE for the forecast; magnitude/frequency trend statistics for the Era 1 ramp analysis.

### Outputs

- Next-day national + regional demand forecast, plus its residual signal (feeds Phase 4)
- Era 1 (2019–2022) ramp-characterization trend vs. RES-share growth (feeds Phase 5's "Era 1" dashboard tab and Phase 6's introduction)
- Feature importance ranking

### Environment

Google Colab (see "ML Development Environment" above) — notebooks committed to the repo, dataset loaded via the Kaggle API, `ML/environment.yml` created first. **Resolved 2026-07-10:** no model artifact is stored at all — `predict.py` retrains fresh on every run (see "Repository structure for ML work" above) — so the Git LFS / release-asset / direct-commit storage question this line originally left open never needed answering.

### Done when

~~`ML/environment.yml`, `ML/Study1/features.py`, and all four notebooks are committed; the baseline model beats naive persistence on MAPE/RMSE on the 2024–2026 test window; the Era 1 ramp-characterization trend is produced and charted.~~ ~~`predict.py` and GitHub Actions wiring can follow after.~~ **All done, including `predict.py` and CI wiring, as of 2026-07-10.** Phase 3 has no remaining deferred items.

---

## Phase 4 — Study 2: corridor-aware grid-stress early-warning classifier ✅ COMPLETE (2026-07-11)

**Owner:** Sagnik, built directly (2026-07-11) — the "owner TBD" open decision from 2026-07-10 was resolved by building it rather than waiting on collaborator assignment. Consumed Phase 3's forecast-residual signal as designed (see `build_study1_residual_signal()` below).

**Datasets used:** `study1_daily.csv` for the Era 2 (2023–Oct 2024) daily-resolution pre-check; `study2_scada.csv` (56,988 rows × 164 cols, 96 slots/day, Nov 2024–present) for the Era 3 live model.

**Targets (two, sharing most feature engineering):**
1. Binary — did a frequency violation (Hz outside [49.7, 50.2]) occur, predicted **1–4 slots (15–60 min) ahead**, not just classified retrospectively.
2. Binary — was there a "ramp shock" (a sudden, sharp swing in demand or net load between consecutive slots), same lead-time framing.

**Measured 2026-07-09 against the live data:** frequency-violation rate in `study2_scada.csv` is 0.88% (503 of 56,892 rows) — a workable, non-degenerate class balance for both targets.

### Goal

Answer the Era 2 + Era 3 parts of the central research question: does corridor congestion (`ir_*`) or cross-border exchange (`xb_*`) predict grid stress, first at daily resolution where only daily data has corridor visibility (Era 2), then live at 15-minute resolution with lead time once SCADA data exists (Era 3). The two binary targets are causally linked — a sudden generation-demand imbalance (ramp shock) is what produces a frequency deviation (violation) — so they're modelled together, not as separate studies, and Study 1's forecast-residual becomes an explicit input feature (an unusually large residual is itself a leading indicator of stress).

**Why this replaced the original `study1_hourly`-based ramp-shock idea:** classifying sudden demand swings was originally scoped against the frozen, hourly-only `study1_hourly.csv` (2019–2024). That dataset can't feed a live dashboard and is coarser than what's available live. `study2_scada` gives 15-minute resolution and updates daily from Nov 2024 onward — a strict upgrade for this target. `study1_hourly`'s ramp signal is retained in Phase 3 (Era 1 analysis) and Phase 5 (dashboard tab) as historical motivating evidence, not as a modelling deliverable.

### What already exists

Everything. `ML/Study2/features.py`, all 5 notebooks (`00_era2_daily_correlation.ipynb` through `04_ramp_shock_baseline.ipynb`), and `ML/Study2/predict.py` (wired into CI) are all built and committed. See `Pipeline/docs/study2_features_notes.md` and `Pipeline/docs/study2_predict_notes.md` for full design detail.

```
ML/Study2/
├── notebooks/
│   ├── 00_era2_daily_correlation.ipynb   ✅ Era 2 (2023–Oct 2024) pre-check on study1_daily
│   ├── 01_eda.ipynb                      ✅ Era 3 SCADA EDA
│   ├── 02_features.ipynb                 ✅ Feature table inspection + class balance
│   ├── 03_violation_baseline.ipynb       ✅ LightGBM baseline, frequency-violation target
│   └── 04_ramp_shock_baseline.ipynb      ✅ LightGBM baseline, ramp-shock target
├── features.py                           ✅ Shared feature-engineering functions
└── predict.py                            ✅ Daily 96-slot risk timeline, wired into CI
```

### Verified results (2026-07-11)

Every number below was independently re-executed against the live dataset (56,988 raw slots, 56,923 after dropping 3 corrupted-file days) and matched what's embedded in the corresponding notebook exactly — not just written into the notebook and assumed correct.

**Era 2 daily-resolution pre-check** (`00_era2_daily_correlation.ipynb`, `study1_daily.csv` 2023-01-01 to 2024-10-31, 670 rows): IR-line corridor congestion (sum of `|ir_*_net_mu|` across all 7 corridors) has a moderate **negative** correlation with same-day frequency-stress-band time (`freq_pct_below_499 + freq_pct_above_5005`): **-0.396**, strongest for WR↔NR (-0.418) and NER↔NR (-0.368). The lagged version (today's flow vs. tomorrow's stress) is similar (-0.428). Negative direction makes physical sense: corridors move power specifically to relieve regional imbalance, so higher utilization coincides with *lower* instability — corridors are evidence of the grid correcting stress, not causing it. Cross-border exchange shows close to no correlation (-0.014 overall; Myanmar's column is constant zero in this window, essentially unconnected). This calibrated expectations for Era 3: IR-line net flow (especially WR-NR, NER-NR) was carried forward as the more promising corridor signal; cross-border columns are included in the classifiers too but with low expectations, consistent with this daily-resolution finding.

**Era 3 EDA** (`01_eda.ipynb`, live `study2_scada.csv`, Nov 2024–present): overall violation rate 0.89%, ramp-shock rate 6.1%. Both cluster sharply and physically-explainably by time of day: violations peak 08:00-09:00 and 13:00 (up to 4.0%, solar variability hours), ramp-shocks peak at sunrise (05:00-09:00, up to 36% at 06:00) and sunset (17:00-20:00, up to 8.6%) — the two windows solar output changes fastest. Violation rate rises **monotonically** with RES-share quintile (0.33% → 1.92%) — direct SCADA-resolution evidence for the project's central "rising RES share stresses the grid" thesis. Ramp-shock rate vs. RES-share quintile goes the *other* direction in simple binning (8.3% → 2.8%) — flagged as a genuine, unresolved, likely season-confounded finding (RES share and ramp rate are both strongly seasonal independently), not smoothed over.

**Resolved, 2026-07-11** (appended to `01_eda.ipynb` as a second cell): the RES-share/ramp-rate finding above was tested for season confounding directly, not left as a caveat. Ranking RES share *within* each month first (instead of pooling across months) reverses the pooled finding: ramp rate **rises** from 5.3% to 7.0% across within-month RES-share quintiles, and the partial correlation (residualized on month) flips from -0.075 (pooled) to +0.026 (season-controlled) — small, but now the same direction as the violation-rate finding (+0.051) and the project's central thesis. The pooled number wasn't just imprecise, it was pointing the wrong way — season-controlling was necessary here, not just more rigorous.

**Hour × day-of-week heatmap** (same cell): violations concentrate hardest on **Sunday** — the single worst slot is Sunday 13:00 (7.0%), and Sunday's marginal violation rate (1.38%) is the week's highest, well above any weekday (0.62-0.99%). Ramp-shocks show the opposite day-of-week pattern: Sunday's marginal ramp rate (4.40%) is the week's *lowest*, while weekdays sit around 6.4-6.7%. That decoupling is a genuine, non-obvious finding: fewer large demand swings on Sunday (lower industrial/commercial load) but more frequency violations — consistent with the grid running a thinner online generation/reserve margin on a low-demand day, making frequency more sensitive to smaller disturbances.

**Frequency-violation classifier** (`03_violation_baseline.ipynb`, LightGBM, time-aware split 2024-11→2025-06 train / 2025-07→2025-12 val / 2026 test): **PR-AUC 0.1541** vs. a 0.0306 base-rate baseline (~5.0x lift) — up from 0.0614 originally (~2.5x, four rounds of real fixes total; PR-AUC drifts a little run-to-run since the live test window, `date >= 2026-01-01` with no upper bound, keeps growing as new SCADA data accumulates — this is a data-freshness effect, not a fix). F1 at a naive 0.5 threshold is near-zero (0.5 is the wrong lens for a ~3% positive rate).

**Methodology fix, 2026-07-14 (fifth pass):** the "best-F1 operating point" was previously selected by scanning the TEST set's own precision-recall curve for its best point — reporting the best-in-hindsight threshold rather than what a threshold fixed in advance would achieve on unseen data. Fixed: the threshold is now selected on VAL and frozen before being applied to TEST. Honest, out-of-sample best-F1 operating point: **F1 0.1843, precision 20.8%, recall 16.6%** — down from the hindsight-biased F1 0.2035/precision 17.7%/recall 24.0% (recall in particular was overstated). No VAL threshold reaches ≥95% precision, so that metric is no longer reported for this classifier. **Reported as a weak-but-real, and steadily improving, baseline — not oversold; PR-AUC, which never involved threshold selection, is unaffected by this fix.**

**Corrected 2026-07-11, after Sagnik asked whether the two-stage ramp→violation idea (flagged as future work above) was worth building.** Before building it, checked the premise empirically: does a ramp-shock actually precede a violation more than chance? It doesn't — `P(ramp_lead=1 | violation_lead=1)` = 14.2%, actually *below* the 15.1% unconditional rate, so the two-stage idea as originally conceived was abandoned rather than built on a falsified premise. Scanning every generation source's slot-to-slot delta for correlation with `violation_lead` instead found **solar volatility** clearly ahead of the rest (corr 0.0785 vs wind 0.036, demand ~0) — consistent with violations clustering at 08:00-09:00/13:00 (prime solar-ramp hours). Added `solar_delta_mw` and `solar_roll8_std` to `features.py`. Retraining surfaced a second, larger, unrelated problem: **`scale_pos_weight` was causing LightGBM's early stopping to fire after a single boosting round** (`best_iteration_=1`, in every configuration tried — extra regularization, `is_unbalance`, different learning rates) for the ~3% `violation_lead` target, silently limiting the model to something close to one shallow tree instead of the intended up-to-500-round ensemble. Removing it (switching the early-stopping metric to `average_precision` instead) was the larger of the two fixes — PR-AUC rose from 0.0614 to 0.0937, best-F1 from 0.1297 to 0.1712. Both fixes verified together and separately before adoption; see `03_violation_baseline.ipynb` for the full diagnostic trail, and `features.py`'s `scale_pos_weight()` docstring for how to recognize this failure mode again (suspiciously tiny single-digit feature-importance split counts is the tell).

**Corrected again, 2026-07-11 (same evening), while auditing confidence in Phase 4's results.** `share_res_pct` and every `ir_*`/`xb_*` corridor column turned out to be whole-DAY aggregates broadcast identically to all 96 slots of a day (verified directly: every row of a given date has the exact same value, unlike `freq_hz`/`demand_met_mw` which genuinely vary per slot). That raised a real question worth testing rather than assuming either way: does a whole-day RES-share/corridor figure leak information from *later* in the same day into an earlier slot's prediction? Removing these 12 columns from the classifiers' `FEATURE_COLS` (kept elsewhere as `DAILY_BROADCAST_COLS` for the still-valid Era 2/EDA correlation work) **improved rather than degraded both classifiers** — violation PR-AUC 0.0937 → **0.1186** (+27%), ramp-shock PR-AUC 0.7248 → **0.7446**. So there was no leakage-driven inflation to worry about; these columns were pure noise once genuine per-slot signals (frequency/demand lags, solar volatility, hour) are available. A clean, verified win with no downside — adopted immediately.

**Ramp-shock classifier** (`04_ramp_shock_baseline.ipynb`, same split/pipeline): **PR-AUC 0.7464** vs. a 0.1767 base-rate baseline (~4.2x lift) — a genuinely strong signal, stronger still after four rounds of real fixes (0.7140 → 0.7248 → 0.7446 → 0.7486; small run-to-run drift, same data-freshness reason as the violation classifier above). Best-F1 operating point, threshold now selected on VAL and frozen before being applied to TEST (same fix as the violation classifier, 2026-07-14): **F1 0.6771, precision 62.8%, recall 73.45%** — essentially unchanged from the old hindsight-selected numbers (F1 0.6803/precision 63.3%/recall 73.5%), because this classifier's larger, more stable event rate makes the VAL-optimal and TEST-optimal thresholds nearly identical. **Recall at ≥95% precision, however, collapses from the previously-reported 20.4% to 0.3%** once honestly evaluated out-of-sample — that number was almost entirely a hindsight-overfitting artifact of tuning the threshold on the same data used to report it, not a real operating capability, and should not be quoted anywhere going forward. This is the clearest evidence the fix mattered: it barely moves the ramp-shock classifier's headline F1, but it fully deflates a specific high-precision claim that was never real. Top features: `hour`, `demand_delta_mw`, `month`, `demand_met_mw_lag3`, `solar_delta_mw`, `solar_roll8_std` — solar and demand-trajectory features dominate, consistent with the EDA's sunrise/sunset clustering. `wind_delta_mw` (added alongside `freq_hz_delta` in the fourth round) contributes real, nonzero importance too; `freq_hz_delta` barely registers for this target — makes sense, it's a more direct signal for the frequency-adjacent violation target than for this demand-driven one. Corridor columns no longer appear at all (removed from `FEATURE_COLS`) — Era 2's daily-resolution corridor-flow finding remains a separate, valid, unaffected result, it just isn't what drives this live classifier.

**Honest takeaway:** ramp-shock lead-time prediction works well from this feature set; frequency-violation lead-time prediction is much harder, even after the fixes above — plausibly because a violation is a downstream, AGC/reserve-mediated consequence rather than a direct mechanical property of any single input signal. Both results and the gap between them are reported as-is.

**Lead-window experiment — run a FOURTH time, 2026-07-11**, each time on a meaningfully different (and better) feature set. `features.py`'s `add_violation_label()` and `build_feature_table()` are parameterized (`lead_slots` / `violation_lead_slots`, default unchanged at 4) to test this without disturbing the shipped baseline or the ramp-shock target.

| lead_slots | base rate | PR-AUC | lift over base rate | best-F1 | precision | recall |
|---|---|---|---|---|---|---|
| 4 (shipped, 15-60 min) | 3.06% | 0.1541 | 5.03x | 0.1843 | 20.8% | 16.6% |
| 3 (15-45 min) | 2.47% | 0.1596 | 6.47x | 0.2032 | 16.5% | 26.6% |
| 2 (15-30 min) | 1.82% | 0.2082 | 11.46x | 0.2213 | 36.3% | 15.9% |
| 1 (15 min only) | 1.11% | 0.2225 | 20.00x | 0.2976 | 37.9% | 24.5% |

**Methodology fix, 2026-07-14 (fifth pass):** re-run with the same VAL-selected, TEST-frozen threshold fix as both baseline notebooks above (best-F1 in this table is now an honest out-of-sample number, not the best point in hindsight on TEST). **PR-AUC and lift are unaffected by this fix (threshold-free) and remain cleanly monotonic as the window shrinks from 4 to 1 slot — this is the finding this appendix exists to support, and it stands.** Best-F1 also stays monotonic (0.1843 → 0.2032 → 0.2213 → 0.2976). Precision and recall *individually*, however, no longer move cleanly together once honestly evaluated — e.g. lead_slots=2 has notably higher precision but lower recall than lead_slots=3. The fourth pass's specific claim that "precision AND recall both improve together on every metric" doesn't survive the threshold-selection fix; that texture was itself partly an artifact of picking each window's best point in hindsight on the same test data being compared. The part of this finding that holds up is the PR-AUC/lift/F1 monotonic improvement, not a clean win on every individual metric.

Still not changing the shipped default without an explicit product decision — a 15-minute-only warning is a meaningfully different product than a 15-60-minute one, and this is the fourth different ranking shape across four passes (no clean winner → 2 clearly best → 1 best-F1 with 2 best-PR-AUC → now 1 clean winner on everything). One more round of stability (e.g. does this monotonic pattern hold under cross-validation, not just one time-aware split) would be worth having before treating it as settled — but this is the strongest evidence yet that a shorter window is worth shipping, and the case has gotten stronger with essentially every fix, not weaker.

### Where the data lives

`Dataset/study1_daily.csv` (Era 2 pre-check, 2023–Oct 2024 subset): `ir_*` (21 cols), `xb_*` (12 cols), `freq_pct_*` bands.

`Dataset/study2_scada.csv` (Era 3, one row per 15-min block):

| Group | Key columns | Notes |
|-------|-------------|-------|
| Timestamp | `date`, `time`, `hhmm` | |
| Real-time generation mix | `nuclear_mw`, `wind_mw`, `solar_mw`, `hydro_mw`, `gas_mw`, `thermal_mw`, `total_gen_mw` | Per 15-min slot |
| Demand | `demand_met_mw`, `net_demand_met_mw` | Per slot — ramp-shock label derives from the slot-to-slot delta of these |
| Net transmission | `net_trans_exchange_mw` | Per slot |
| Evening peak by region | NR/WR/SR/ER/NER | Broadcast from daily |
| IR-Line + cross-border | 21 `ir_*` + 12 `xb_*` cols | Broadcast from daily — fully populated for all of `study2_scada`'s Nov 2024–present range (verified 2026-07-09: corridor data has existed since 2023, before SCADA data starts) |
| Frequency | `freq_hz`, `freq_fvi`, `freq_pct_*` bands | Per slot — used to derive the violation label |
| Study 1 residual | *(new, produced by Phase 3's `predict.py`)* | Broadcast per day, same pattern as other daily-to-slot broadcasts |

Three known bad days must be dropped before training: **2025-10-02** (63 slots, a legacy parse error) plus **2024-11-20** and **2025-04-01** (1 slot each — found 2026-07-11 while building `ML/Study2/features.py`, added to `Pipeline/validate.py`'s check as a proper named FAIL rather than blending into the generic slot-count WARN). A handful of other days have 95/97/98 slots (DST/truncation edge cases, not corrupted files) — handle explicitly, don't silently drop or pad.

### Step by step

1. ~~**`00_era2_daily_correlation.ipynb`**~~ ✅ Done — see verified results above.
2. ~~Define the violation label~~ ✅ Done — `add_violation_label()` in `features.py`, 49.7–50.2 Hz band, 1–4-slot lead-time via `_add_lead_label()`.
3. ~~Define the ramp-shock label~~ ✅ Done — `add_ramp_label()`, 3,500 MW slot-to-slot delta threshold (≈p95, empirically derived), same lead-time framing.
4. ~~**`01_eda.ipynb`**~~ ✅ Done — see verified results above.
5. ~~**`02_features.ipynb` + `features.py`**~~ ✅ Done. Class imbalance handled via LightGBM's `scale_pos_weight` (chosen over SMOTE — see `study2_features_notes.md`), not SMOTE.
6. ~~**`03_violation_baseline.ipynb`**~~ ✅ Done — PR-AUC 0.1541 (corrected 2026-07-11, four rounds of real fixes; operating-point numbers further corrected 2026-07-14 for a threshold-selection methodology fix, see below).
7. ~~**`04_ramp_shock_baseline.ipynb`**~~ ✅ Done — PR-AUC 0.7464 (corrected 2026-07-11, four rounds of real fixes; operating-point numbers further corrected 2026-07-14 for a threshold-selection methodology fix, see below).
8. **(Stretch, not done)** — temporal CNN or LSTM over the 96-slot daily window. Not attempted; the LightGBM baselines are the deliverable for this phase.
9. ~~**Metrics**~~ ✅ Done — PR-AUC, recall@95%precision, F1 (best-threshold, not just @0.5) reported for both targets.

### Outputs

- ✅ Era 2 daily-resolution corridor/cross-border-vs-stress correlation findings
- ✅ 15–60-min-ahead frequency-violation probability — `ML/Study2/predict.py`, `Dataset/predictions/study2_risk.csv`
- ✅ 15–60-min-ahead ramp-shock probability — same output file
- ✅ Feature importance: which corridor / cross-border level / forecast-residual is most predictive of each — printed in `03`/`04`'s notebooks
- ✅ Risk heatmap analysis (time-of-day × day-of-week event frequency) — the underlying analysis is now in `01_eda.ipynb` (added 2026-07-11); rendering it as an interactive dashboard widget is still Phase 5 work
- ✅ Threshold analysis: precision-recall curve, best-F1 operating point, recall@95%precision — both targets

### Environment

Same as Phase 3 — Google Colab, `ML/environment.yml`, dataset via Kaggle API. (Built and verified locally this session using the same local Python environment as the rest of the repo — packages already present: pandas 3.0.2, numpy 2.4.4, scikit-learn 1.9.0, lightgbm 4.6.0.)

### Done when

~~`ML/Study2/features.py` and all 5 notebooks are committed; both classifiers have a reported baseline (PR-AUC, F1, recall@precision); `predict.py` and CI wiring exist.~~ **All done, as of 2026-07-11.** Phase 4 has no remaining deferred items. Note: results are honestly mixed (ramp-shock baseline is strong, violation baseline is weak) — "done" means the pipeline and honest evaluation are complete, not that both targets are production-ready.

---

## Phase 5 — Dashboard ✅ COMPLETE (built 2026-07-17, deployed 2026-07-19)

**Live at [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/).**

**Vision:** public site combining live data feed + model inference + historical explorer. Built in `dashboard/` as a React + Vite + Tailwind + Recharts app (not GitHub Pages/plain-JS as originally scoped below — Sagnik asked for a Vercel-deployable app matching the stack/visual design of another of his projects, [HalcyonVector/Utility-Based-Portfolio-Allocation-Agent](https://github.com/HalcyonVector/Utility-Based-Portfolio-Allocation-Agent): dark glass-card sections, radial-gradient hero, hover-lift micro-interactions. Grid-Sentinel uses its own sky-blue/amber "energy" accent rather than that project's rose, but the structural language matches).

### The Historical Explorer mirrors the three-era research design (2026-07-09)

Rather than one undifferentiated set of time-series charts, the Historical Explorer is structured around the same three eras used in Phases 3/4/6 — each tab uses the dataset that actually covers it, and each is a real analytical output from those phases, not raw unprocessed charting:

- **Era 1 tab (2019–2022, non-live):** intra-day ramp magnitude/frequency trend vs. rising `share_res_pct`, from Phase 3's `04_era1_ramp_characterization.ipynb`. Source: `study1_hourly.csv` (36MB) at data-prep time; the browser only ever sees the precomputed monthly aggregate — see "The client-fetch size problem" below. Framed explicitly as motivating evidence for the live Phase 4 classifier, not a prediction of its own.
- **Era 2 tab (2023–Oct 2024, non-live):** daily-resolution corridor/cross-border-vs-stress correlation, from Phase 4's `00_era2_daily_correlation.ipynb`. Source: `study1_daily.csv`.
- **Era 3 (live, this is the "Study 2 risk" panel below, not a Historical Explorer tab):** today's live corridor-aware risk timeline. Source: `Dataset/predictions/study2_risk.csv` (the daily model output, not the raw 60MB `study2_scada.csv`).

This means all three CSVs appear in the dashboard for the era each one actually covers — `study1_hourly` and the Era 2 daily subset are never presented as live or current, only as historical, clearly dated evidence.

### Panels (as actually built)

| Panel | Description | Data source | Notes vs. original scope |
|-------|-------------|-------------|---------------------------|
| **Live grid status** | Latest day's peak demand, RES share, frequency-band stability, generation-mix bar | `dailySlim` (latest row) | As scoped. |
| **Study 1 forecast** | Predicted-vs-actual demand chart + latest error + running MAPE | `forecast` | National only, no regional breakdown; no explicit confidence-interval band (only 6 logged predictions so far — a CI would be nearly meaningless on this little history; revisit once the log has more rows). |
| **Study 2 risk** | Today's 96-slot violation/ramp-shock risk timeline | `risk` | As scoped. |
| **Historical explorer** | Demand + RES-share trend, full 2019–present | `dailySlim` | Simplified to demand + RES share (the two series the rest of the project's findings hang on); IR-line/cross-border flows as raw time series were dropped in favor of the Era 2 correlation view below, which is the actual verified finding — a raw flow chart would just be more lines with no established interpretation. |
| ↳ *Era 1 tab* | Ramp magnitude vs. RES share, indexed 0–100, single axis | `era1Monthly` (precomputed) | As scoped, matches `04_era1_ramp_characterization.ipynb` exactly. |
| ↳ *Era 2 tab* | Corridor/cross-border flow vs. frequency-stress correlation, diverging bars | `era2CorridorCorr` (precomputed) | As scoped, matches `00_era2_daily_correlation.ipynb` exactly. |
| **Anomaly log** | Forecast misses ≥5% error, risk slots ≥50% probability | Derived client-side from `forecast` + `risk` | As scoped. |

### What already exists

`ML/Study1/predict.py` and `ML/Study2/predict.py` — both built, wired into CI, output `Dataset/predictions/study1_forecast.csv` and `study2_risk.csv` daily (see Phase 3/4). `dashboard/` — full React app, all 6 panels built, tested locally, deployed publicly on Vercel at [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/).

### The client-fetch size problem, and how it's solved

The original plan ("frontend reads the committed CSVs/JSON directly") undersold one real constraint: `study1_hourly.csv` is 36MB and `study2_scada.csv` is 60MB. Fetching either client-side on every page load — just to show a monthly aggregate or one day's slots — would be a genuinely broken product on a static host with no backend to pre-aggregate. `Pipeline/build_dashboard_data.py` (new, 2026-07-17) solves this: it precomputes everything the frontend actually needs — a slim ~15-column version of `study1_daily.csv` (144 cols → 15, ~2.1MB → a few hundred KB), the same monthly Era 1 aggregation `04_era1_ramp_characterization.ipynb` produces, and the same Era 2 correlation table `00_era2_daily_correlation.ipynb` produces — into one `dashboard/public/data/dashboard.json` (~1MB total, verified byte-for-byte against the already-confirmed notebook numbers). The browser never touches the 36MB/60MB files.

### Where the data/code lives

- Inference scripts: `ML/Study1/predict.py`, `ML/Study2/predict.py` (both done)
- Predictions output: `Dataset/predictions/study1_forecast.csv`, `Dataset/predictions/study2_risk.csv` (both done)
- Dashboard data prep: `Pipeline/build_dashboard_data.py` → `dashboard/public/data/dashboard.json` (new)
- Frontend: `dashboard/` (React + Vite + Tailwind + Recharts, see `dashboard/README.md`)
- CI: `.github/workflows/daily_scrape.yml` runs `ML/Study1/predict.py`, `ML/Study2/predict.py`, then `Pipeline/build_dashboard_data.py`, then commits all outputs together

### Step by step

1. ~~Once Phase 3's baseline model is trained, write `ML/Study1/predict.py`~~ **Done 2026-07-10.**
2. ~~Once Phase 4's baseline model is trained, write `ML/Study2/predict.py`~~ **Done 2026-07-11.**
3. ~~Build the dashboard~~ **Done 2026-07-17** — all 6 panels, tested locally.
4. ~~Deploy to Vercel~~ **Done 2026-07-19**, live at [grid-sentinel-vm.vercel.app](https://grid-sentinel-vm.vercel.app/).

### Technical stack (as built)

- **React 19 + Vite + Tailwind CSS + Recharts** — matches the stack of [HalcyonVector/Utility-Based-Portfolio-Allocation-Agent](https://github.com/HalcyonVector/Utility-Based-Portfolio-Allocation-Agent), per explicit request to keep this project's dashboards consistent.
- Deploy target: **Vercel**, not GitHub Pages (changed from the original plan below — Sagnik wants Vercel).
- Python model inference runs in GitHub Actions each day → outputs CSV predictions + `dashboard.json` committed to repo.
- No backend — Vercel serves the static Vite build; all data is baked into the repo at CI time, not fetched from a live API.

### Milestones

1. ~~Historical Explorer panel live~~ **Done 2026-07-17.**
2. ~~Phase 3 model done → export daily forecast~~ ✅ Done 2026-07-10.
3. ~~Phase 4 model done → export slot-level risk~~ ✅ Done 2026-07-11.
4. ~~Full dashboard consuming both + raw data~~ **Done 2026-07-17.**
5. ~~Launch publicly on Vercel~~ **Done 2026-07-19.**

---

## Phase 6 — Research paper (conditional) 🔲

**Decision gate:** after Phase 3 + 4 are complete, assess whether results are strong enough to publish. **Both are now complete (2026-07-11) — the gate has technically been reached.** Flagging, not deciding: Phase 4's results are mixed (ramp-shock baseline is strong at PR-AUC 0.7464; frequency-violation baseline is weak at PR-AUC 0.1541, ~2.5x the original 0.0614 across four rounds of real fixes) — whether that's "strong enough" is still Sagnik's call, not one made here. **Recommended framing, added 2026-07-11 (see "Central claim" and "Paper structure" below, rewritten from the original draft):** don't lead with the violation classifier — lead with the dataset and the season-controlled Era 3 findings, and report the classifiers (both of them, strong and weak) as the applied deliverable that motivated digging into the data as deeply as this project did. That framing makes the project's actual strongest material the headline, and turns the violation classifier's weakness into an honest, specific research question rather than a soft spot to explain away.

### Goal

Publish the dataset methodology and/or the two studies' modelling results, if results warrant it.

### What already exists

Nothing — no draft, no venue chosen, no writing environment set up. This phase can't meaningfully start until Phase 3/4 produce results to write about.

### Central claim (rewritten 2026-07-11)

**Old framing (superseded):** "shows, for the first time, that inter-regional corridor congestion and cross-border exchange have measurable predictive value for short-term grid stress" — this leads with the weakest piece of evidence (the violation classifier, PR-AUC 0.1541 as of the latest fix) and a cross-border/corridor result that, as of 2026-07-11, turned out not to hold up as a *live-classifier* feature at all (see Phase 4's `FEATURE_COLS` note — corridor columns were removed from the classifiers after being found to hurt rather than help). Doesn't reflect what the project actually found strongest.

**New framing:** using a novel, openly-published, rigorously-verified, multi-granularity NLDC dataset (7 years, three complementary resolutions), this project traces how the observability and predictability of Indian grid stress evolved as both monitoring granularity and renewable penetration increased — and, once SCADA-resolution visibility exists (Nov 2024 onward), provides the first granular, reproducible, **season-controlled** evidence that rising RES share correlates with increased grid stress at 15-minute resolution, directly complementing the EAC-PM's July 2026 macro-level finding rather than just restating it. Two secondary, physically-grounded findings support this: inter-regional corridor flow functions as a **stress-relief** signal, not a stress-causing one (moderate negative correlation with next-day frequency instability); and grid stress exhibits a genuine day-of-week decoupling (Sunday has the week's highest frequency-violation rate but its lowest ramp-shock rate, consistent with thinner online reserve margins on a low-demand day). The project also reports, honestly and including a documented dead-end (a demand-side "does a ramp precede a violation" hypothesis that the data itself falsified), a first attempt at live corridor-aware lead-time classification of both ramp-shocks (strong, PR-AUC 0.72) and frequency violations (real but modest, PR-AUC 0.09) — the sharp gap between the two is itself evidence that these are mechanistically different phenomena, not just two flavors of "grid stress."

### Where the material will come from

- Era 1 evidence: Phase 3's `04_era1_ramp_characterization.ipynb` (`study1_hourly.csv`, 2019–2022)
- Era 2 evidence: Phase 4's `00_era2_daily_correlation.ipynb` (`study1_daily.csv`, 2023–Oct 2024) — corridor-flow-as-relief-valve finding
- Era 3 EDA: Phase 4's `01_eda.ipynb` — the season-controlled RES-share finding (both the pooled-vs-controlled reversal and the partial-correlation numbers) and the day-of-week decoupling are the two strongest individual results in the whole project and should anchor the Era 3 section, not just support it
- Era 3 classifiers: `03_violation_baseline.ipynb` + `04_ramp_shock_baseline.ipynb` (`study2_scada.csv`, Nov 2024–present), informed by Phase 3's forecast-residual signal — report both results and the gap between them as a finding, plus the `scale_pos_weight` debugging story as a one-paragraph methods note (evidence of rigor, not a headline)
- Dataset methodology section: this roadmap's Phase 0 (parser fixes, spot-check log) and Phase 1 (validation gate, data dictionary, `known_gaps.json`/`null_baselines.json`) sections, plus `Dataset/README.md`
- Feature-importance / corridor-specific narrative: derived from Phase 4's per-corridor, per-country feature-importance rankings

### Related work / prior art (verified via web search, 2026-07-09 — starting point for the literature review, re-verify before submission since this is a fast-moving area)

| Claim | Status | Source |
|---|---|---|
| Corridor congestion predicts frequency stability | Done for European grids, not India | [Revealing drivers and risks for power grid frequency stability with explainable AI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8600233/); [Identifying drivers and mitigators for congestion in the German grid with XAI](https://www.sciencedirect.com/science/article/pii/S0306261923017154) |
| Cross-border exchange helps grid stability, India-specific | Only qualitative/policy evidence found (the April 2020 "9pm9minute" event), no quantitative model | [Cross-Border Electricity Cooperation in Southern Asia](https://www.mdpi.com/2227-9717/12/11/2324) |
| Rising RES share is stressing India's grid | Macro-level claim already made, very recently | [India's rising solar penetration is causing power grid stress: EAC-PM paper](https://www.business-standard.com/industry/news/india-s-rising-solar-penetration-is-causing-power-grid-stress-eac-pm-paper-126070701352_1.html) (reported 2026-07-07) |
| Multi-resolution / evolving-observability grid datasets | Exists in different form (PSML benchmark, Smart5Grid) — not this three-era, single-country design | [PSML multi-scale dataset](https://www.nature.com/articles/s41597-022-01455-7); [Smart5Grid observability](https://pmc.ncbi.nlm.nih.gov/articles/PMC10521069/) |
| India + frequency violation + ramp event + corridor congestion + ML (combined) | No matching paper found | Targeted search, 2026-07-09 — appears genuinely open |
| Plain gradient-boosting demand forecasting | Heavily saturated globally, including India-specific | [MANIT Bhopal-style India load forecasting work](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1408119/full) — this is why Study 1's forecast is positioned as infrastructure, not a novelty claim |

### If yes, target venues

- **IEEE NPSC (National Power Systems Conference) — still the top recommendation.** India-focused, applied/regional venue, the right level for a strong-dataset-plus-honestly-mixed-modelling contribution. Doesn't need the violation classifier to be a headline result to be a good fit here.
- **Consider a separate dataset/resource-track submission (new, 2026-07-11 suggestion)** — if NPSC or an adjacent venue/workshop has a dataset track, or as an arXiv companion, splitting the dataset contribution out from the modelling results decouples the two: the dataset stands on its own regardless of how the paper's classifier results are received, and a resource paper has a different (often lower) novelty bar than a full research contribution.
- *Electric Power Systems Research* (Elsevier) — broader journal, viable if the season-controlled Era 3 findings and the ramp-shock classifier carry the paper (they're strong enough to)
- IEEE Transactions on Power Systems — higher bar; only pursue if results substantially exceed baseline expectations, since the underlying techniques (LightGBM, SHAP-style feature importance) are not themselves novel

### Paper structure (rewritten 2026-07-11 to lead with the strongest material, not the weakest)

1. **Introduction:** why Indian grid forecasting matters (RE integration, frequency instability); central research question; explicitly position relative to the EAC-PM finding (complements it with granular, season-controlled ML evidence, doesn't claim to discover the phenomenon)
2. **Dataset:** novel contribution — NLDC PSP reports scraped 2019–present, three complementary resolutions, verification methodology (spot-checks, adversarial audits, machine-readable gap/null-drift tracking) presented as evidence of quality, gaps documented transparently rather than hidden
3. **Era 1:** `study1_hourly` ramp-shock evidence (2019–2022) vs. rising RES share — motivating, not a headline result
4. **Era 2:** daily-resolution corridor/cross-border-vs-stress correlation (2023–Oct 2024) — corridor flow as a stress-*relief* signal (physically grounded, not just a correlation number), cross-border shows no daily-resolution signal (an honest null result worth stating plainly, since it's the first quantitative check against the existing qualitative literature)
5. **Era 3, part A (the strongest section):** the season-controlled RES-share finding (lead with this — the pooled analysis was actively misleading and the season-controlled one flips the sign, a genuine methodological point) and the day-of-week decoupling finding
6. **Era 3, part B:** the two lead-time classifiers — ramp-shock (strong, PR-AUC 0.72) and frequency-violation (real but modest, PR-AUC 0.09) — presented together specifically *because* the gap between them is informative (mechanically direct vs. reserve-margin-mediated phenomena), not as two disconnected baselines. One paragraph on the `scale_pos_weight` debugging story as a rigor note, not a centerpiece.
7. **Discussion:** synthesize across eras; what the RES-share, corridor, and day-of-week findings mean together; comparison against the related work below
8. **Conclusion + future work:** the falsified two-stage-ramp hypothesis (worth a sentence — shows the project tests its own assumptions, not just reports whatever worked), the 2-vs-4-slot lead-window trade-off as an open deployment decision, state-level extension via `study3_states.csv`, sequence models over the 96-slot window

Dataset itself (NLDC PSP scraped + parsed, 7 years, three-resolution) is a secondary publishable contribution regardless of model results — strong enough to be worth a resource-track submission on its own if the full paper doesn't land at the first venue tried.

### Environment

Not yet decided — Overleaf (LaTeX) is the typical choice for IEEE/Elsevier venue templates; flagging as an open decision to make once this phase actually starts, not assuming it now.

---

## Appendix: Parser fixes log

| # | Symptom | Fix |
|---|---------|-----|
| 1 | Diversity cols empty pre-2020 | Single "All India Demand Diversity Factor" → `diversity_regional`; split kept for newer files |
| 2 | `max_demand_met_*` empty in 2019 PDFs | Time-row guard relaxed so "(MW) & time" row is kept |
| 3 | `xb_export`/`xb_import` had wrong values | Cross-border section scan bounded to its own block |
| 5a | Concatenated-text PDFs parsed empty | All PDF label matching is space-stripped |
| 5b | Section A on non-standard page | All-pages fallback in `parse_pdf` (fills only missing keys) |
| — | IR-Line not parsed for 2023–24 | `_xls_parse_ir_line` backported to file1/file2 → 21 `ir_*` cols now emitted for every XLS with an IR-Line sheet |
| — | Duplicate-date rows | `build_dataset` dedups by date, keeping richest (most non-null) row |

## Appendix: Spot-check log

**Original pass (Phase 0, 2026-06-24):** 8 dates × 44 field comparisons — 0 mismatches. Methodology not preserved in detail (this table only, no field-level breakdown).

**Full independent re-derivation (2026-07-10):** every date below re-checked from scratch — raw source file re-located, text/tables dumped and read by hand, ~29-44 comparable fields per date checked directly against the CSV (not against the parser's own output). ~280 total field comparisons, 0 mismatches.

| Date | Era | Fields checked | Result | Notes |
|------|-----|-----------------|--------|-------|
| 2019-03-15 | PDF | 29 | ✓ | |
| 2020-06-07 | PDF | 31 | ✓ | |
| 2021-03-22 | PDF | 31 | ✓ | |
| 2022-08-11 | PDF | 31 | ✓ | Source PDF itself has Section A vs. Section G hydro-total mismatch (766 vs. 775 MU) — confirmed the parser correctly preserves both, doesn't reconcile them |
| 2023-02-18 | XLS | 33 | ✓ | Pre-dates cross-border sheet onset — `xb_*` correctly null (no CrossBorder sheet exists in this file) |
| 2023-10-06 | XLS | 41 | ✓ | Includes full cross-border + IR-line era fields |
| 2024-01-02 | XLS | 37 | ✓ | |
| 2025-01-21 | XLS | 43 | ✓ | Includes full cross-border era fields |
