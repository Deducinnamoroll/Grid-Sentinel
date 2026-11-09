"""Prepare the Kaggle upload folder's metadata before `kaggle datasets version`.

Does three things to the copies in the push folder (never to the committed files,
unless --update-readme is used):
  1. Rewrites the Rows/Cols cells of the README's Files table from the live CSVs.
  2. Sets the dataset subtitle, and the description (Kaggle's "About Dataset" text)
     to that README.
  3. Adds a `resources` entry per CSV with a file description and one description
     per column, taken from Dataset/data_dictionary.xlsx.

Usage:
  python Pipeline/kaggle_metadata.py /tmp/kaggle_push       # in CI, before the push
  python Pipeline/kaggle_metadata.py --update-readme         # refresh the repo README's counts
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "Dataset"

sys.path.insert(0, str(ROOT / "Pipeline"))
import study2_io  # noqa: E402

SUBTITLE = "Daily Indian national grid data from NLDC PSP reports, 2018 to present"

FILES = {
    "study1_daily.csv": "Daily national grid features from Dec 2018: generation mix, regional demand, outages, inter-regional flows, cross-border exchange and frequency statistics. One row per day.",
    "study1_hourly.csv": "Hourly load Jan 2019 to Apr 2024 with that day's PSP features joined on. One row per hour. Fixed end date: the hourly load source ends in Apr 2024.",
    "study2_scada.csv": "15-minute SCADA time series from Nov 2024 (NLDC TimeSeries sheet), with the day's study1_daily features (daily, inter-regional line and cross-border) joined onto each row. 96 rows per day.",
    "study3_states.csv": "Daily state-level power supply position from Dec 2018 (section C): peak demand met, shortages, energy met, drawal schedule and over/under drawal per state, UT or grid entity. One row per entity per day.",
}

MAX_COL_DESC = 1000  # keep well inside Kaggle's field limits


def header(name, base=None):
    """Column names of a CSV as published. base=None means the repo's Dataset/, where
    study2_scada.csv is stored slim, so its published (wide) header is rebuilt from
    the two headers. In the push folder study2_scada.csv is already the wide copy."""
    if base is None:
        if name == "study2_scada.csv":
            return study2_io.wide_columns()
        base = DATASET
    return list(pd.read_csv(Path(base) / name, nrows=0).columns)


def csv_shape(name, base=None):
    path = Path(base or DATASET) / name
    cols = len(header(name, base))
    with open(path, "rb") as fh:
        rows = sum(1 for _ in fh) - 1
    return rows, cols


def update_counts(readme_text, base=None):
    """Rewrite the Rows and Cols cells of each `| `file.csv` | rows | cols |` line."""
    out = readme_text
    for name in FILES:
        rows, cols = csv_shape(name, base)
        pattern = re.compile(r"^(\| `" + re.escape(name) + r"` \| )[\d,]+ \| \d+ \|", re.M)
        out, n = pattern.subn(lambda m: f"{m.group(1)}{rows:,} | {cols} |", out)
        if n != 1:
            sys.exit(f"README Files table: expected one row for {name}, found {n}")
    return out


def read_keep_eol(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write_keep_eol(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def column_description(row):
    parts = []
    for label, key in (("Unit", "unit"), ("Source", "source_section"), ("From", "schema_start_date")):
        val = row.get(key)
        if pd.notna(val) and str(val).strip():
            parts.append(f"{label}: {str(val).strip()}.")
    notes = row.get("notes")
    if pd.notna(notes) and str(notes).strip():
        parts.append(str(notes).strip())
    return " ".join(parts)[:MAX_COL_DESC]


def resources(base=None):
    sheets = pd.read_excel(DATASET / "data_dictionary.xlsx", sheet_name=None)
    res = []
    for name, desc in FILES.items():
        cols = header(name, base)
        d = sheets[name.removesuffix(".csv")].set_index("column_name")
        missing = [c for c in cols if c not in d.index]
        if missing:
            sys.exit(f"data_dictionary.xlsx has no entry for {name} columns: {missing[:10]}")
        # Fields in the CSV's own column order. No "type": Kaggle infers it.
        fields = [{"name": c, "description": column_description(d.loc[c])} for c in cols]
        res.append({"path": name, "description": desc, "schema": {"fields": fields}})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("push_dir", nargs="?", help="Kaggle upload folder holding README.md and dataset-metadata.json")
    ap.add_argument("--update-readme", action="store_true", help="Rewrite the counts in Dataset/README.md in place")
    args = ap.parse_args()

    if args.update_readme:
        p = DATASET / "README.md"
        write_keep_eol(p, update_counts(read_keep_eol(p)))
        print(f"Updated counts in {p}")
        return
    if not args.push_dir:
        ap.error("give the push folder, or --update-readme")

    push = Path(args.push_dir)
    readme = update_counts(read_keep_eol(push / "README.md"), base=push)
    write_keep_eol(push / "README.md", readme)

    meta_path = push / "dataset-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["subtitle"] = SUBTITLE
    meta["description"] = readme
    meta["resources"] = resources(base=push)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = sum(len(r["schema"]["fields"]) for r in meta["resources"])
    print(f"Metadata ready: {len(meta['resources'])} files, {cols} column descriptions")


if __name__ == "__main__":
    main()
