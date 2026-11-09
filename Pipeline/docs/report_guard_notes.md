# Notes: report_guard.py

**Script:** `Scrapings/report_guard.py`, with its list `Scrapings/known_report_labels.json`
**Purpose:** Notice the day NLDC changes its report, or the day a stored column breaks, instead of weeks later.

---

## In plain English

The parsers find each number by the words next to it in the report ("Energy Met (MU)", "Max OD (MW)"). When NLDC renames a row, adds one, or moves a table to a new sheet, a parser does not crash. It stores nothing, or stores the wrong number, and every run stays green. This script runs after each daily update and turns the run red, which emails you, when that happens.

## Why it exists

Three changes in 2026 went unnoticed, all found by hand on 2026-11-10:

| Report change | First day | Effect | Noticed after |
|---|---|---|---|
| Max OD printed as "OD/ UD", e.g. "1137/ -1136" | 2026-02-13 | `study3_states.max_od_mw` empty | 9 months |
| Shortage row relabelled "Shoratge (MW) during Evening Peak hr" | 2026-08-05 | `evening_peak_demand_*` held the shortage (often 0), `peak_shortage_*` empty | 3 months |
| Bulk consumers (RIL Jamnagar, BALCO, AMNSIL, Railways...) moved to a new sheet `MOP_E1`; regional "Bulk Consumer_*_ISTS" rows added to section C | 2026-09-29 | those entities dropped out of `study3_states` | 6 weeks |

## The two checks

**1. Label check.** Every text cell of every sheet in the new report is compared with `known_report_labels.json`. Numbers, times and dates are ignored, so what is left are row labels, column headers, entity names and footnotes. Any new sheet or any text never seen before is a finding. Removed labels are not reported here (they show up in the health check as an empty column or a missing entity).

**2. Column health.** The new data day is compared with the 30 days before it:
- a column with values on at least 90% of those days is now empty (every column, all three datasets; for `study3_states` and `study2_scada` it is the share of entities or slots with a value);
- a column non-zero on at least 90% of those days is now 0;
- a value is more than half a range-width outside the column's last-year range (needs 300 days of history);
- an entity present on at least 25 of the 30 days is missing.

The zero and range rules skip columns that legitimately sit at 0 or swing (`ir_*`, `xb_*`, `ie_*`, `trans_*`, `freq_pct_*`, shortages, OD/UD). With them included the replay below flagged 97 of 312 days.

## Tested by replaying 2026

- **Label check.** Learned from the reports before each change, then checked the following days. All three changes were flagged on their first day. Two other genuine changes were also flagged (a new line name in IR-Line on 2026-02-12, a winter footnote). Learned from 2026-09-30 to 10-15 and checked 10-16 to 11-09: no findings (no false alarms).
- **Health check**, on the data as it was before the 2026-11-10 repairs, 2026-01-01 to 2026-11-08: 23 of 312 days flagged. Each was one of the three bugs (from its first day), a report with the whole IR-Line sheet missing (2026-03-27, 2026-07-08), an implausible NER solar value (2026-04-01, 10.5 MU against a usual 0.2 to 2), or a real frequency disturbance (2026-10-03, FVI 0.355). The baseline adapts, so a broken column stops alarming after about 4 days; the first red run is what matters.

## How it runs

`update_live.py` calls `run_guard()` after validation passes, on every raw file it parsed and that file's data day. Findings print as `REPORT CHANGED:` or `DATA HEALTH:` lines; a crash in the guard prints `GUARD ERROR:`. The data is committed either way. The workflow step "Fail the run if the report changed or a column broke" turns the run red when the log has any of those lines.

## What to do when it fires

1. Open the failed run's log and read the lines.
2. If a parser is affected (a label it matches on changed, a table moved), fix the parser, re-parse the affected days, and note it in that parser's notes.
3. If the change is harmless (a footnote, "20:00hrs" becoming "19:00hrs"), accept it:
   ```
   python Scrapings/report_guard.py --accept Dataset/Raw/File2_Raw/DD.MM.YY_NLDC_PSP.xls
   ```
   and commit `Scrapings/known_report_labels.json`. Without this the run stays red every day.

Other commands:
```
python Scrapings/report_guard.py --check <file.xls>        # label check one report
python Scrapings/report_guard.py --health 2026-11-08       # health of one data day
python Scrapings/report_guard.py --seed --since 2026-09-30 # rebuild the list from reports
```

The list was seeded on 2026-11-10 from the 40 reports since 2026-09-30 (322 labels, 5 sheets).
