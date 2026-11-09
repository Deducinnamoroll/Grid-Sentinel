# Notes: parse_psp_states.py

**Script:** `Scrapings/parse_psp_states.py`
**Purpose:** Extract NLDC's section C "Power Supply Position in States" table into `Dataset/study3_states.csv` — one row per state/UT/entity per day, long format.

---

## In plain English

Every day's report from the grid operator includes a table breaking down power supply numbers state-by-state (Punjab, Maharashtra, Tamil Nadu, and so on — about 40 entities). Nothing in this project was reading that table before — this script's entire job is to pull it out of each day's report and save it as its own dataset (`study3_states.csv`), so anyone interested in state-level detail, not just the national picture, has something to work with.

---

## Why this file exists

Section C of every NLDC daily PSP report lists ~40 state/UT/grid-entity rows (max demand met, shortage, energy met, drawal schedule, OD/UD, max OD, energy shortage). It was never parsed by the main pipeline — `parse_psp_pdf_xls_file1.py`/`file2.py` only cover Sections A, B, D-H. Built 2026-07-10 to close out Phase 2's remaining low-priority task.

Deliberately a separate, self-contained script rather than a new function bolted onto `parse_psp_pdf_xls_file2.py`, because it produces a fundamentally different shape: every other parser in this repo returns **one dict per file** (one row per day); this one returns **a list of ~37-40 dicts per file** (one row per state per day). Reusing the existing single-row-per-file `build_dataset()` pattern would have meant awkwardly overloading it; a small independent script with its own `build_dataset()` was simpler than forcing a shared abstraction.

---

## What it does

Supports both report eras, since Section C is present and structurally identical in both:

| Era | Method |
|-----|--------|
| PDF (2019-2022) | `pdfplumber.extract_tables()`, locates the table whose header row has `"states"` in column 1 |
| XLS (2023+) | Reads the `MOP_E` sheet directly with `pandas`/`xlrd`, locates the `"power supply position in states"` section by scanning column 0 |

Both eras render the table at the same 9-column offset: `region, state, max_demand_met_mw, shortage_max_demand_mw, energy_met_mu, drawal_schedule_mu, od_ud_mu, max_od_mw, energy_shortage_mu`.

### Two real data-quality problems solved here, not upstream

1. **Region resolution.** The `region` label (NR/WR/SR/ER/NER) is a merged cell in NLDC's source template, rendered on whichever row a fixed group-size calculation happens to land on — not consistently the first row of its group. Tried per-file forward/backward-fill first; wrong, because the label's position turned out to be a deterministic template artifact, not something more data resolves. Verified across the full 2,722-file archive: only 12 of 43 canonical entities ever had a label anywhere. Fixed with `STATE_TO_REGION`, a static lookup built from the 12 that did resolve via majority vote plus direct verification against raw file dumps for the other 31 — this is the **primary** source of truth for region, not a fallback. `_resolve_regions()` falls back to cross-date majority voting only for a state name not yet in that static map (e.g. a genuinely new entity NLDC starts reporting in the future).
2. **State-name fragmentation.** The same real-world entity extracts under different spellings across report eras: concatenated-text PDFs drop spaces (`"TamilNadu"`), some cells wrap across two table rows (`"J&K(UT) &"` / `"Ladakh(UT)"`), and naming genuinely changed (J&K's Aug 2019 split into J&K + Ladakh UTs; Puducherry's older "Pondy" abbreviation). Left unhandled, this both under-counts a state's true row total and starves the region majority-vote of samples. Fixed with `STATE_NAME_ALIASES`, applied before region resolution — consolidated 59 raw variants down to 43 canonical entities.

One row where the state name itself extracted as the literal string `"0"` (2023-12-04) is dropped via `UNRECOVERABLE_STATE_LABELS` — the same header-corruption pattern found in the main gen/outage parser fix, but here corrupting a state name instead of a column header. Which state it actually was can't be recovered without opening that file by hand.

---

## Known residual gap

`10.05.19_NLDC_PSP.pdf` is rendered entirely in Hindi/Devanagari — the only report in the whole archive like this. The English-language `"states"` header match can't find it, so that file's date has no `study3_states` row. **Correction, 2026-07-11:** the missing date is **2019-05-09**, not 2019-05-10 as previously stated here — confirmed from the PDF's own English-language subject line ("Sub: Daily PSP Report for the date 09.05.2019"), which differs from its filename date due to the same filename-vs-data-date offset documented elsewhere in this project. `study1_daily`/`study1_hourly` are unaffected since their parsers don't depend on this same text match. Not worth a Hindi-specific fix for one date.

---

## Usage

```
python Scrapings/parse_psp_states.py Dataset/Raw/File2_Raw/ Dataset/study3_states.csv
python Scrapings/parse_psp_states.py single_file.pdf     # prints parsed rows, doesn't write a CSV
python Scrapings/parse_psp_states.py single_file.xls
```

Called as step 3 of `Pipeline/build_all.py` (subprocess), and incrementally by `append_study3()` in `Scrapings/update_live.py` for the daily pipeline — see that script's notes file.

Depends on `pdfplumber` (PDF era), `pandas` + `xlrd` (XLS era). No dependency on `parse_psp_pdf_xls_file1.py`/`file2.py` — fully self-contained, including its own date-extraction helpers, so it doesn't create a cross-file coupling to either of those (they're themselves a byte-identical pair, see `parse_psp_pdf_xls_notes.md`).

---

**New entities do happen, and an unmapped one stalls the pipeline.** On 2026-09-30 NLDC began publishing `Bulk Consumer_WR/SR/ER/NER ISTS` rows (previously only the NR one). Unmapped, they have a null region, which fails the incremental validation and blocks the whole day's commit. Added to `STATE_TO_REGION` on 2026-11-08 (the suffix names the region). When a new name shows up, CI now turns the run red with a message pointing here; add the name to the map and re-run, and the 90-day scan fills the days that were skipped. See `update_live_notes.md` for the full incident.

## Output schema

`date, region, state, max_demand_met_mw, shortage_max_demand_mw, energy_met_mu, drawal_schedule_mu, od_ud_mu, max_od_mw, energy_shortage_mu` — 10 columns, long format. Chosen over wide (one row per date, ~40 states × 7 metrics ≈ 280 columns) because long format matches how a per-entity time series is actually queried or joined.

Verification (2026-07-10): `Pipeline/validate.py --only study3` passes all 6 checks; 5 state/date combinations spot-checked by hand against raw source (2 PDF-era, 3 XLS-era) — all match exactly. 99,208 rows total, 2018-12-31 → present.

## Fix 2026-11-10: max OD printed as "OD/ UD" (from Feb 2026)

From mid-February 2026 most reports print the max OD column as a pair, "max OD/ max UD (MW)", for example "1137/ -1136", instead of a single number. `_to_float` returned None for it, so `max_od_mw` was empty for almost every row from 2026-02-13 (2026 coverage had fallen to 14%). `_to_float` now takes the number before the slash, so `max_od_mw` keeps its meaning (maximum over-drawal). The 10,508 empty values from December 2025 on were re-parsed and filled; the 2,886 values already present all matched the fixed parser.

## Fix 2026-11-10: bulk consumers moved to sheet MOP_E1 (from 2026-09-29)

From the 2026-09-29 report NLDC moved the individual ISTS bulk consumers (Railways_NR ISTS, Hindustan Zinc Ltd. Daripa, AMNSIL, BALCO, RIL Jamnagar, Welspun, Railways_ER ISTS) out of section C into a new sheet, `MOP_E1` (section J, same eight-column layout). Section C kept one `Bulk Consumer_<region> ISTS` row per region, and these are the **sums** of that region's entities (energy adds up exactly, e.g. WR 9.7 + 20.9 + 7.1 + 0.7 = 38.4 MU). The parser read only `MOP_E`, so from 2026-09-29 the individual entities were missing and only the sums were stored. The note above about the 2026-09-30 rows is corrected by this: they are regional totals, not new entities.

On the same day NLDC left three blank rows inside WR where those entities had been. `_xls_states` treated the first blank row as the end of the table, so 2026-09-29 stopped after Goa (16 rows instead of about 40).

Changes:
- `parse_xls` also reads `MOP_E1` when present, keeps its entities and drops the `Bulk Consumer_*` sum rows, so nothing is counted twice and the series matches how bulk consumers were stored before.
- `_xls_states` skips up to three blank rows and stops at the next section heading ("D. ..."); rows with no numbers are skipped.
- From 2026-06-01 to 09-28 section C had one `Bulk Consumer_NR ISTS` row that was a single plant, Hindustan Zinc (about 110 MW, 1.3 MU a day, matching its MOP_E1 row afterwards). It is now stored as `Hindustan Zinc`, the same name the MOP_E1 rows get (`STATE_NAME_ALIASES`), so the plant is one continuous series. This is a judgment call based on the matching magnitudes; the raw label is in the reports.
- `Hindustan Zinc` (NR) and `Welspun` (WR, new) are in `STATE_TO_REGION`; `Pipeline/build_dashboard_data.py` treats both as non-states.

Repair of `study3_states.csv`: 120 rows renamed, 201 regional-sum rows dropped, 306 rows added (41 days x 7 entities, plus the 19 states lost on 2026-09-29). Every 2026 row on a date with a parsed report now matches the fixed parser exactly. Found by the replay of `Scrapings/report_guard.py`, which flags this change on its first day.
