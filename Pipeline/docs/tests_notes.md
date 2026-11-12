# Notes: tests/

**Files:** `tests/test_parsers.py`, `tests/conftest.py`, workflow `.github/workflows/tests.yml`
**Purpose:** Catch a parser that changes behaviour before its output reaches the datasets.

---

## In plain English

Each parser is run on one real NLDC report from every era in which the report layout changed, and what it produces is compared with what the committed datasets already hold for that day. Those datasets were checked against the raw reports, so a difference means a code change broke a parser on that layout.

## What is tested

| Test | Reports | Compares with |
|---|---|---|
| `test_study1_parser_matches_dataset` | all 10 | the day's row in `study1_daily.csv`, every parsed column |
| `test_states_parser_matches_dataset` | all 10 | the day's entities and values in `study3_states.csv`, and that every entity has a region |
| `test_scada_parser_matches_dataset` | the 5 with a TimeSeries sheet | the day's 96 slots in `study2_scada.csv`, after `study2_io.slim` |
| `test_append_study1_restores_day_exactly` / `..._study3_...` | 29.09.26 | removes that day from a copy, re-appends it with `update_live.py`, requires the copy to be byte-identical |

Reports: 01.01.19, 15.06.20, 15.06.21, 15.06.22 (PDF, including run-together text), 01.06.23 (first XLS layout), 16.01.25, 13.02.26 (max OD as "OD/ UD"), 05.08.26 (relabelled shortage row), 29.09.26 (MOP_E1 sheet, blank rows in section C), 09.11.26 (current). The three 2026 layout changes are the ones that broke parsers silently; see `parse_psp_pdf_xls_notes.md` and `parse_psp_states_notes.md`.

The append tests guard the 2026-11-09 failure (a date stored with the wrong type crashed the new sort and the day was lost). Written on 2026-11-12, they also found that `append_study1` and `append_study3` read the CSV with pandas' default float parser and rewrote about 21 untouched lines with a different last digit on every append; both now read with `float_precision="round_trip"`, as `append_study2` already did.

## Running

```
python -m pytest tests -q
```
About 20 seconds locally. CI runs it on every push to `main` that touches `Scrapings/`, `Pipeline/study2_io.py` or `tests/` (the repo is public, so Actions minutes are free).

## When a test fails

- **After a parser change you meant to make:** re-parse the affected days into the datasets in the same commit (the 2026-11-10 repairs are examples), then the test passes again.
- **Otherwise:** the change broke that era's layout; the assertion names the report and the first differing columns or entities.
