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
