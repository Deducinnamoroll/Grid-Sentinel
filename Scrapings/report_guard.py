"""
report_guard.py -- notice when NLDC changes its report or a column breaks.
Added 2026-11-10.

Why: the parsers find values by their row labels and column headers. When NLDC
renames a row, adds one, or moves a table to a new sheet, a parser does not
crash; it quietly stores nothing or the wrong number. Three such changes went
unnoticed for weeks to months in 2026 (evening-peak shortage relabelled on
08-05, max OD printed as "OD/ UD" from 02-13, bulk-consumer entities moved to
a new sheet MOP_E1 on 09-29). Two checks catch that class of failure:

1. Label check (report side). Every text cell of every sheet in a new report
   is compared with Scrapings/known_report_labels.json. Any sheet or text the
   project has not seen before is reported. Numbers, times and dates are
   ignored, so only labels, headers and entity names count.
2. Column health (data side). The newly appended day is compared with the 30
   days before it. Reported: a column that had values on at least 90% of those
   days and is now empty; a column that was non-zero on at least 90% of them
   and is now 0; a value far outside the column's range over the last year;
   an entity (state, UT, bulk consumer) present on at least 25 of the 30 days
   and now missing.

Findings are printed as lines starting "REPORT CHANGED:" or "DATA HEALTH:".
They never block the append (the day's data still commits); the workflow's
alarm step turns the run red when the log contains either marker, which sends
the failed-run email.

When a report change is expected or harmless (for example "20:00hrs" becoming
"19:00hrs"), accept it with:
    python Scrapings/report_guard.py --accept Dataset/Raw/File2_Raw/<file>.xls
which adds that file's labels to known_report_labels.json (commit the change).

Other uses:
    python Scrapings/report_guard.py --seed --since 2026-09-30   # rebuild the list
    python Scrapings/report_guard.py --check <file>.xls          # label check only
    python Scrapings/report_guard.py --health 2026-11-08         # health of one day
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
KNOWN = Path(__file__).resolve().parent / "known_report_labels.json"
DATASET = ROOT / "Dataset"

_DATE = re.compile(r"^\d{1,2}[-/. ][a-z]{3,9}[-/. ]\d{2,4}$|^[a-z]{3,9} \d{1,2},? \d{4}$")
_NUMERIC = re.compile(r"^[-+]?[\d.,/: \-%()]+$")


def _norm(v) -> str:
    s = str(v).replace("�", "").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def report_labels(path) -> dict:
    """{sheet: sorted list of text cells} for one XLS report."""
    out = {}
    for sheet, df in pd.read_excel(path, sheet_name=None, header=None).items():
        seen = set()
        for v in df.values.ravel():
            s = _norm(v)
            if not s or s == "nan" or _NUMERIC.match(s) or _DATE.match(s) or not re.search(r"[a-z]", s):
                continue
            seen.add(s)
        out[sheet] = sorted(seen)
    return out


def load_known() -> dict:
    return json.loads(KNOWN.read_text(encoding="utf-8")) if KNOWN.exists() else {}


def save_known(known: dict):
    KNOWN.write_text(json.dumps({k: sorted(set(v)) for k, v in sorted(known.items())}, indent=1, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def check_labels(path, known=None) -> list:
    """Findings for one report: new sheets and text never seen before."""
    known = load_known() if known is None else known
    if not known:
        return []
    findings = []
    for sheet, labels in report_labels(path).items():
        if sheet not in known:
            findings.append(f"new sheet '{sheet}' ({len(labels)} labels), e.g. {labels[:3]}")
            continue
        new = [s for s in labels if s not in set(known[sheet])]
        for s in new:
            findings.append(f"sheet '{sheet}': new text '{s[:120]}'")
    return [f"{Path(path).name}: {f}" for f in findings]


# --- column health ----------------------------------------------------------

# Columns that legitimately sit at 0 or swing widely day to day (power flows,
# cross-border trade, schedules and deviations, shortages, frequency-band
# shares). Measured on 2026 history: with these included, the zero and range
# rules flagged 97 of 312 normal days. They still get the "went empty" rule.
_VOLATILE = re.compile(r"^(ir_|xb_|ie_|trans_|freq_pct_)|shortage|odud|od_ud")


def _range_ok(hist: pd.Series, v: float) -> bool:
    lo, hi = hist.min(), hist.max()
    span = hi - lo
    if not span or pd.isna(span):
        return True
    return lo - 0.5 * span <= v <= hi + 0.5 * span


def _daily_health(df: pd.DataFrame, day: pd.Timestamp, name: str, skip=()) -> list:
    df = df.set_index("date").sort_index()
    if day not in df.index:
        return []
    prev = df.loc[day - pd.Timedelta(days=30): day - pd.Timedelta(days=1)]
    year = df.loc[day - pd.Timedelta(days=365): day - pd.Timedelta(days=1)]
    if len(prev) < 20:
        return []
    today = df.loc[day]
    out = []
    for c in df.columns:
        if c in skip or not pd.api.types.is_numeric_dtype(df[c]):
            continue
        v = today[c]
        p = prev[c]
        if pd.isna(v):
            if p.notna().mean() >= 0.9:
                out.append(f"{name}.{c} is empty on {day.date()} (had values on {p.notna().mean():.0%} of the 30 days before)")
            continue
        if _VOLATILE.search(c):
            continue
        if v == 0 and (p.dropna() != 0).mean() >= 0.9 and p.notna().sum() >= 20:
            out.append(f"{name}.{c} is 0 on {day.date()} (non-zero on {(p.dropna() != 0).mean():.0%} of the 30 days before)")
            continue
        h = year[c].dropna()
        if len(h) >= 300 and not _range_ok(h, v):
            out.append(f"{name}.{c} = {v:g} on {day.date()}, far outside its last-year range {h.min():g} to {h.max():g}")
    return out


def load_frames() -> dict:
    sc = DATASET / "study2_scada.csv"
    return {
        "s1": pd.read_csv(DATASET / "study1_daily.csv", parse_dates=["date"]),
        "s3": pd.read_csv(DATASET / "study3_states.csv", parse_dates=["date"]),
        "s2": pd.read_csv(sc, parse_dates=["date"]) if sc.exists() else None,
    }


def check_health(day, frames=None) -> list:
    """Findings for one data day across the three daily datasets. `frames`
    (from load_frames) avoids re-reading the CSVs when checking many days."""
    day = pd.Timestamp(day)
    frames = frames or load_frames()
    out = []
    s1 = frames["s1"]
    out += _daily_health(s1, day, "study1_daily")

    s3 = frames["s3"]
    if (s3["date"] == day).any():
        prev = s3[(s3["date"] < day) & (s3["date"] >= day - pd.Timedelta(days=30))]
        present = prev.groupby("state")["date"].nunique()
        regular = set(present[present >= 25].index)
        today = set(s3.loc[s3["date"] == day, "state"])
        for st in sorted(regular - today):
            out.append(f"study3_states: '{st}' missing on {day.date()} (present on {present[st]} of the 30 days before)")
        # Per-column: share of entities with a value, as a daily series.
        if "s3_filled" not in frames:
            f = s3.drop(columns=["region", "state"]).set_index("date").notna().groupby(level=0).mean()
            frames["s3_filled"] = f.where(f > 0.5).reset_index()
        for line in _daily_health(frames["s3_filled"], day, "study3_states (share of entities with a value)"):
            if "is empty" in line:
                out.append(line)

    s2 = frames["s2"]
    if s2 is not None:
        if (s2["date"] == day).any():
            # One row per day: share of the day's slots with a value, per column.
            if "s2_filled" not in frames:
                f = s2.drop(columns=[c for c in ("time", "hhmm") if c in s2.columns]).set_index("date").notna().groupby(level=0).mean()
                frames["s2_filled"] = f.where(f > 0.5).reset_index()
            out += [l for l in _daily_health(frames["s2_filled"], day, "study2_scada (share of slots with a value)") if "is empty" in l]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("Other uses:")[0].strip())
    ap.add_argument("--seed", action="store_true", help="rebuild the known-label list from raw reports")
    ap.add_argument("--since", default="2026-09-30", help="with --seed: first report date to learn from")
    ap.add_argument("--accept", nargs="+", help="add these reports' labels to the known list")
    ap.add_argument("--check", nargs="+", help="label-check these reports")
    ap.add_argument("--health", nargs="+", help="health-check these data days (YYYY-MM-DD)")
    a = ap.parse_args()

    if a.seed:
        raw = DATASET / "Raw" / "File2_Raw"
        known = {}
        n = 0
        for f in sorted(raw.glob("*.xls*")):
            m = re.match(r"(\d\d)\.(\d\d)\.(\d\d)", f.name)
            if not m or pd.Timestamp(f"20{m.group(3)}-{m.group(2)}-{m.group(1)}") < pd.Timestamp(a.since):
                continue
            for sheet, labels in report_labels(f).items():
                known.setdefault(sheet, set()).update(labels)
            n += 1
        save_known({k: list(v) for k, v in known.items()})
        print(f"learned {sum(len(v) for v in known.values())} labels in {len(known)} sheets from {n} reports since {a.since}")
    if a.accept:
        known = {k: set(v) for k, v in load_known().items()}
        for f in a.accept:
            for sheet, labels in report_labels(f).items():
                known.setdefault(sheet, set()).update(labels)
        save_known({k: list(v) for k, v in known.items()})
        print(f"accepted labels from {len(a.accept)} report(s)")
    for f in a.check or []:
        for line in check_labels(f) or [f"{Path(f).name}: no new labels"]:
            print(line)
    for d in a.health or []:
        for line in check_health(d) or [f"{d}: healthy"]:
            print(line)


if __name__ == "__main__":
    sys.exit(main())
