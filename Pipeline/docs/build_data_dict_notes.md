# Notes: build_data_dict.py

**Script:** `Pipeline/build_data_dict.py`
**Purpose:** Generate `Dataset/data_dictionary.xlsx`, a human-readable reference for all columns across the four Grid-Sentinel datasets.

---

## In plain English

Our datasets have 180 columns total, with names like `ir_er_nr_import_mu` or `freq_pct_499_5005` — meaningless to anyone who didn't build the parser. This script produces a glossary: one row per column, explaining in plain terms what it measures, what unit it's in (megawatts? percent?), which report section it came from, and any quirks to know about. It's what makes the dataset usable by someone other than us — a Kaggle stranger, a future collaborator, or us in six months.

---

## Output

`Dataset/data_dictionary.xlsx` with five sheets:

| Sheet | Contents |
|-------|----------|
| `study1_daily` | All 144 columns from `study1_daily.csv` |
| `study2_scada` | All 164 columns of `study2_scada` as published on Kaggle and as `study2_io.load_study2()` returns it. Since 2026-11-10 the committed file has 21; the list comes from `study2_io.wide_columns()`, which adds `study1_daily`'s header. |
| `study1_hourly` | All 151 columns from `study1_hourly.csv` |
| `study3_states` | All 10 columns from `study3_states.csv` (added 2026-07-10) |
| `master` | Union of all unique column names across the four datasets (180) |

The output file is committed to git and pushed to Kaggle alongside the CSVs (decided 2026-07-10 — see "Distribution" below). It is **not** part of the daily automated pipeline: regenerate and recommit it manually whenever the schema changes (new dataset or column), not on every daily data refresh.

Each sheet has the following fields:

| Field | Description |
|-------|-------------|
| `column_name` | Exact column name as it appears in the CSV |
| `datasets` | Which CSV files contain this column |
| `unit` | Physical unit (MW, MU, %, Hz, ratio, or date) |
| `source_section` | Section of the PSP report or external source this column is parsed from |
| `schema_start_date` | Approximate date from which this column has non-null values in the dataset |
| `notes` | Additional context, derivation formula, or caveats |

---

## Unit conventions

| Abbreviation | Full form | Notes |
|---|---|---|
| MW | Megawatt | Instantaneous demand or capacity |
| MU | Million Units | 1 MU = 1 GWh = 1,000 MWh. Used for energy (generation, consumption, exchange). |
| % | Percentage | Frequency band percentages, RES share, diversity factors expressed as ratios are noted separately. |
| Hz | Hertz | Instantaneous system frequency (study2_scada only) |
| ratio | Dimensionless | Demand diversity factors |

---

## Source sections

Columns are parsed from the following sections of the NLDC PSP report:

| Section label | Location in PSP report |
|---|---|
| Section A (National Overview) | Page 1: daily demand, shortage, peak, regional generation by source |
| Section B (Inter-Regional) | Page 2: national generation mix, frequency stats, outages, IE schedule/actual/ODUD |
| IR-Line table (Section B appendix) | Appears as a separate table or XLS sheet. Inter-regional corridor flows. |
| Cross-border table (Section B appendix) | Cross-border exchange with Bhutan, Nepal, Bangladesh, Myanmar. |
| TimeSeries sheet (SCADA) | XLS sheet present from FY2025 onward. Contains 15-minute slot data for study2_scada. |
| Kaggle India Hourly Load dataset | External source joined in step 5 of `build_all.py`. Provides hourly load figures 2019 to 2024. |
| Section C (Power Supply Position in States) | Page 1, between Sections B and D: state/UT/entity-level demand, shortage, drawal. Parsed by `parse_psp_states.py`, not the main `study1_daily`/`study2_scada` parsers. |

---

## Schema start dates

Many columns are structurally present from the beginning of the dataset (2018-12-31) but contain null values in older files where that section was not yet part of the PSP format. The `schema_start_date` field records the approximate date from which values should be non-null in normal circumstances.

Key thresholds:

| Date | What changed |
|------|-------------|
| 2018-12-31 | First PSP file in the dataset. All Section A and B core columns are available from this date, though some may be null due to format variations. |
| 2023-04-01 | IR-Line corridor flows and restructured cross-border (xb_*) columns begin appearing. Earlier files have these columns but with null values. |
| 2023-04-01 | Solar and non-solar peak-hour statistics (solar_hr_peak_mw etc.) and the Godda Bangladesh export column begin. |
| 2024-11-04 | First date in study2_scada. All slot-level SCADA columns begin here. |

---

## How domain knowledge is populated

The script hardcodes a `KNOWN` dictionary mapping each column name to its unit, source section, schema start date, and notes. For columns not in `KNOWN`, the script infers the unit from the column name suffix (`_mw`, `_mu`, `_pct`, `_hz`) and leaves other fields blank.

As of 2026-07-10, all 180 columns across all four datasets (144 study1_daily, 164 study2_scada, 151 study1_hourly, 10 study3_states) have been populated with at least unit and source section — verified by checking `filled == len(df)` for every sheet after the 2026-07-10 fix (see "Bug found and fixed" below).

---

## Extending the dictionary

To add or correct an annotation, edit the `_add(...)` calls in `build_data_dict.py` and re-run the script. The xlsx is regenerated from scratch on each run; do not edit the xlsx directly.

If a new column is added to a parser, add a corresponding `_add(...)` call. If no `_add` entry exists, the column will appear in the xlsx with unit inferred from the name suffix and all other fields blank. **If a whole new dataset is added** (as `study3_states` was), you must also: add its path constant, add it to the `missing` file-existence check, call `_read_cols`/`_build_sheet` for it, add it to the sheet-writing loop, and add it to the `master` union loop — see the "Bug found and fixed" note below for what happens if this is missed.

---

## Bug found and fixed, 2026-07-10

`study3_states.csv` was built and committed earlier the same day this bug was found. `build_data_dict.py` was never updated to know about it — it silently generated a 4-sheet dictionary with no `study3_states` sheet and no error or warning of any kind. Found only by actually running the script and checking the printed sheet list against what was expected, not by reading the code. Fixed as described above; see `ROADMAP.md`'s Phase 0-1 audit section for the full account.

---

## Distribution — resolved 2026-07-10

`Dataset/data_dictionary.xlsx` previously sat generated-but-untracked: not committed to git, not in `.gitignore` either, and not part of the Kaggle push, despite the roadmap describing it as "published." Resolved: it's now committed to the repo and added to `daily_scrape.yml`'s Kaggle push file list. Reasoning: unlike `tmp/f1_daily.csv` (a disposable build intermediate nobody should need to open), this file *is* the deliverable — it's what makes 180 column names legible to a collaborator or a Kaggle stranger, directly serving the project's "public resource for the broader community" goal. It is committed rather than gitignored precisely because it doesn't change daily (see "Output" above) — no automation risk from committing something that would otherwise thrash on every CI run.

---

## Usage

```
python Pipeline/build_data_dict.py
python Pipeline/build_data_dict.py --output path/to/custom.xlsx
```

Requires `pandas` and `openpyxl`. Both are installed as part of the standard project dependencies (`pip install pandas openpyxl`).
