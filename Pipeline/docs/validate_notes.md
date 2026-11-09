# Notes: validate.py

**Script:** `Pipeline/validate.py`
**Purpose:** Post-build integrity check for all four Grid-Sentinel output datasets. Run this after every full or partial rebuild to confirm no regressions were introduced.

---

## In plain English

After the datasets get rebuilt or updated, how do we know nothing broke? This script is the checkup. It looks for obvious red flags — a missing day, the same date appearing twice, numbers that should add up but don't, a value that's physically impossible — and gives a clear pass/warning/fail report. If it fails, the data shouldn't be trusted or published until the problem is fixed.

---

## When to run

Run after any call to `build_all.py` or `Scrapings/update_live.py`. Can also be run on demand to inspect the current state of the datasets without rebuilding them.

```
python Pipeline/validate.py              # check all four datasets
python Pipeline/validate.py --only study1
python Pipeline/validate.py --only study2
python Pipeline/validate.py --only study3
python Pipeline/validate.py --only hourly
```

Exit code 0 means no FAILs. Exit code 1 means at least one check failed.

---

## Check severity levels

| Level | Meaning |
|-------|---------|
| PASS | Check passed within expected bounds. |
| WARN | Something is unusual but not necessarily broken. Investigate if unexpected. |
| FAIL | A structural problem that indicates a parser regression or corrupted output. Datasets should not be used until resolved. |

---

## Checks run per dataset

`study1_daily`, `study2_scada` and `study1_hourly` also get the generation-share and FVI checks (added 2026-11-08, see the dated section further down); they are listed in each table.

All four datasets also get two checks not repeated in each table below (added 2026-07-11, see the dated section further down): a **date-gap check** against `Pipeline/known_gaps.json` (FAIL if a missing date isn't in that file) and a **null-drift check** against `Pipeline/null_baselines.json` (WARN if a column's null% rises more than 5 percentage points above its stored baseline).

### study1_daily

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 144 |
| Row count | FAIL | Must be >= 2,660 |
| Duplicate dates | FAIL | Zero allowed |
| Data freshness | WARN | Latest date must be within 5 days of today |
| `xb_export_*` non-negative | WARN | All four country export columns must be >= 0 |
| `xb_net = import - export` | WARN | Absolute difference <= 0.01 MU for all rows |
| `ir_*_net = import - export` | WARN | Absolute difference <= 0.01 MU for all rows, all 7 corridors |
| `share_res_pct` vs gen columns | FAIL | Within 1.0 point of `gen_res_mu / gen_total_mu * 100` |
| `share_nonfossil_pct` vs gen columns | FAIL | Within 1.0 point of `(gen_hydro_mu + gen_nuclear_mu + gen_res_mu) / gen_total_mu * 100` |
| `freq_fvi` range | FAIL outside [0, 5], WARN above 1 | Real days 2018-2026 are 0.01 to 0.43 |

The 7 IR corridors checked are: ER-NR, ER-WR, ER-SR, ER-NER, NER-NR, WR-NR, WR-SR.

### study2_scada

The committed file is slim (no `study1_daily` columns, see `study2_io_notes.md`). The first two checks look at the committed file. All the others run on the joined frame from `study2_io.widen()`, the same 164 columns every consumer sees, so their results did not change when the file was slimmed on 2026-11-10.

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Committed file is slim | FAIL | No column other than `date` may also be in `study1_daily.csv` (fix: `python Pipeline/study2_io.py --slim-in-place`) |
| Every SCADA date has a `study1_daily` row | FAIL | Otherwise that day's daily columns would join as empty |
| Column count | FAIL | Joined frame must have 164 |
| Row count | FAIL | Must be >= 55,068 |
| Duplicate (date, hhmm) pairs | FAIL | Zero allowed |
| Data freshness | WARN | Latest date must be within 5 days of today |
| Days with < 90 slots | FAIL | Zero allowed — corrupted source file (generalized 2026-07-11 from a 63-slot-only check; see below) |
| Days outside 95-98 slots | FAIL if > 10 days, WARN if <= 10 | Each day should have 96 fifteen-minute slots |
| Days not exactly 96 slots | WARN | Informational count only |
| `freq_hz` range | WARN | Values must be within [47, 52] Hz (the 2 zeros it caught were dropout readings, blanked on 2026-11-10, see `parse_psp_xls_pdf_file3_notes.md`) |
| `share_res_pct` vs gen columns | FAIL | Within 1.0 point of `gen_res_mu / gen_total_mu * 100` |
| `share_nonfossil_pct` vs gen columns | FAIL | Within 1.0 point of `(gen_hydro_mu + gen_nuclear_mu + gen_res_mu) / gen_total_mu * 100` |
| `freq_fvi` range | FAIL outside [0, 5], WARN above 1 | Real days 2018-2026 are 0.01 to 0.43 |

### study3_states

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 10 |
| Row count | FAIL | Must be >= 99,000 |
| Duplicate (date, state) pairs | FAIL | Zero allowed |
| Data freshness | WARN | Latest date must be within 5 days of today |
| Every row has a valid region | FAIL | `region` must be non-null and one of NR/WR/SR/ER/NER — a null here means `parse_psp_states.py`'s `STATE_TO_REGION` map is missing an entity, see its notes file |
| Consistent state count per day | WARN | Flags any day with more than 3 fewer states than the typical (mode) count — usually means that date's section C table wasn't fully parsed |

### study1_hourly

| Check | Level if triggered | Threshold |
|-------|--------------------|-----------|
| Column count | FAIL | Must equal 151 |
| Row count | FAIL | Must be >= 46,728 |
| Latest datetime | Informational | Printed but not a FAIL condition |
| `share_res_pct` vs gen columns | FAIL | Within 1.0 point of `gen_res_mu / gen_total_mu * 100` |
| `share_nonfossil_pct` vs gen columns | FAIL | Within 1.0 point of `(gen_hydro_mu + gen_nuclear_mu + gen_res_mu) / gen_total_mu * 100` |
| `freq_fvi` range | FAIL outside [0, 5], WARN above 1 | Real days 2018-2026 are 0.01 to 0.43 |

---

## Baseline values

The baselines (minimum row counts, exact column counts) are hardcoded in the script. They reflect the dataset state as of 2026-07-01 for the original three datasets, and 2026-07-10 for `study3_states` (added that day). As daily data accumulates, row counts will grow above these baselines. Column counts should remain fixed unless a parser is modified to add or remove fields.

If a parser change intentionally adds or removes columns, update `BASELINE_COLS` in `validate.py` to match.

---

## Checks not included

- Cross-dataset consistency (e.g., confirming that study2_scada covers the same date range as study1_daily post-2024).

(Null-percentage drift and gap-list continuity — previously listed here as not-yet-implemented — were both added 2026-07-11; see below.)

---

## Date-gap and null-drift checks, added 2026-07-11

**Date-gap check** (`_check_date_gaps`): for each dataset, computes the actual missing dates within its own min-max range and compares them against `Pipeline/known_gaps.json`. Any date missing from the CSV but NOT in that file gets a FAIL, naming the specific unexplained date(s). Replaces relying on a human noticing a new gap.

`known_gaps.json` itself was built 2026-07-11 by scanning each dataset's real, current missing dates from scratch — not reconstructed from the roadmap's old prose categories, which (worth noting) never actually summed to their own stated total (57 + 20 + 3 = 80, not 70 — an arithmetic error that had sat undetected). The fresh scan found:
- `study1_daily`: 69 missing dates (matches Phase 3's earlier independent count).
- `study3_states`: 70 (the same 69 plus one `study3_states`-only gap — see below).
- `study2_scada`: **17 fully-missing dates, none previously documented anywhere in the roadmap** (distinct from the 3 already-known corrupted-file days, which exist but with too few slots). Investigated all 17 directly against `Dataset/Raw/File3_Raw/`: 13 have only a PDF source published for that date (a PDF can't contain the `TimeSeries` sheet SCADA data comes from — a genuine NLDC format limitation), 2 (`2025-07-15`, `2025-08-20`) have an XLS with a `TimeSeries` sheet present but zero data rows (confirmed by direct inspection — header/disclaimer only), and 2 are the already-known 2025-05-22/23 gap.

Also found while re-deriving this list: the `study3_states`-only Hindi-PDF gap was previously documented as `2019-05-10`, but is actually `2019-05-09` — confirmed from the source PDF's own English-language subject line, which differs from the filename date (`10.05.19`) by the same filename-vs-data-date offset this project has hit before. Fixed in `parse_psp_states_notes.md` and `ROADMAP.md`.

**Resolved 2026-07-11 (night):** all 69 `study1_daily` gaps now have an individually-confirmed root cause in `known_gaps.json` — the remaining 65 (beyond the original 4: 2020-11-13, 2020-11-15, 2025-05-22, 2025-05-23) were re-derived by actually re-parsing the full raw archive for every affected month directly (835 files parsed via `parser.parse_file()`, not assumed from the old aggregate prose), then classifying each date by whether a duplicate-subject-line collision explains the gap or whether the archive itself has a genuine filename hole. Result: **49 confirmed duplicate NLDC republishes** (two files with the identical subject-line date, so the date in between never got its own report) and **16 confirmed genuine archive gaps** (no file under any nearby filename resolves to that date at all) — reassuringly close in proportion to the original, never-previously-verified "57 duplicate + 20 confirmed-unavailable" prose estimate, just now with real per-date evidence instead of an assumed category. Each `known_gaps.json` entry for these dates names the specific colliding filenames (for duplicates) or the surrounding coverage window (for genuine gaps), not a generic placeholder.

**Null-drift check** (`_check_null_drift`): compares each column's current null% against a stored baseline in `Pipeline/null_baselines.json`, WARNing if it rises more than 5 percentage points. Deliberately relative to a per-column baseline rather than an absolute rule — most columns are legitimately high-null by design (`ir_*`/`xb_*` only populated from 2023+, `wind_gen_er_mu`/`wind_gen_ner_mu` near 100% since ER/NER have no wind generation), so "any nulls = warning" would be constant noise.

Both checks were sanity-tested against a fabricated regression (a synthetic missing date not in the known-gaps file; a column forced to 50% null) before being trusted — both fired correctly, confirming the checks aren't vacuously passing.

---

## Generation-share and FVI checks, added 2026-11-08

`_check_gen_share_and_fvi()` runs on every dataset that carries the daily generation columns (`study1_daily`, `study2_scada`, `study1_hourly`; the latter two repeat the daily values on every slot, so failures are reported by date).

- **Shares vs gen columns (FAIL):** `share_res_pct` and `share_nonfossil_pct` must be within 1.0 point of the value recomputed from `gen_*_mu`. Before the fix this caught 8 RES days (2024-03-12 read 96.8%) and 12 non-fossil days.
- **FVI range (FAIL / WARN):** `freq_fvi` outside [0, 5] fails (2021-03-02 read 49.215); above 1 warns, since that is possible but far above anything seen so far.

Both bounds are the same constants the parsers use in `_reconcile_daily()` (`SHARE_TOL_PP`, `FVI_MAX`), so a FAIL means a new kind of source error the parser didn't catch, or a row written without going through the parser. Tested against the pre-fix `study1_daily.csv` from git: all three checks fired on exactly the expected dates. See `parse_psp_pdf_xls_notes.md` for the per-day evidence.

---

## Col count discrepancy — resolved 2026-07-10

Earlier roadmap prose (Phase 0, 2026-06-24) stated study2_scada has 165 columns while the actual file has 164; this note used to flag it as untraced. Resolved by direct column diff: `study2_scada` = all 144 `study1_daily` columns (verified present, none missing) + exactly 20 real-time-only columns (`time`, `hhmm`, `freq_hz`, `demand_met_mw`, per-source real-time generation, `net_demand_met_mw`, `total_gen_mw`, `net_trans_exchange_mw`, 6 `time_max_demand_met_*` columns) = 164 exactly. The "165" was a stale pre-build estimate, not a missing column — no action needed.

---

## Adversarial audit, 2026-07-10

Beyond running this script, the full pipeline was independently re-verified by re-deriving evidence rather than trusting prior documentation: 74 field-by-field checks against raw PDF/XLS source across 2 dates not covered by the original spot-check log (0 mismatches), 2 new confirmed-irreducible gap dates found while doing so, a real duplicate-date case traced and confirmed harmless, and all three `update_live.py` append functions independently tested by removing a date and re-appending. See `ROADMAP.md`'s "Audit: Phase 0-1 re-verification" section for the full account, including the one real bug this pass found (`build_data_dict.py` silently missing `study3_states`, since fixed).
