"""
study2_io.py -- read and write Dataset/study2_scada.csv in its slim (normalised) form.

Why this exists
---------------
study2_scada.csv used to carry every study1_daily column (144 of them: MOP_E daily
figures, inter-regional line aggregates, cross-border flows) repeated on all 96
fifteen-minute rows of each day. Those values are byte-for-byte the same as the
day's row in study1_daily.csv (verified on all 718 SCADA days on 2026-11-10), so
they were 85% of the file and added nothing. The broadcast copy pushed the file to
71 MB, and at ~100 KB a day it would have hit GitHub's 100 MB per-file limit around
September 2027 and blocked the daily bot commit.

The committed file now holds only the columns that are not in study1_daily.csv:
date, time, hhmm, the 12 SCADA slot columns, and the 6 time_max_demand_met_* columns
(daily, but study1_daily has no equivalent). That is ~10 MB, growing ~14 KB a day.

Every consumer reads the file through load_study2(), which re-joins study1_daily on
date and returns the same 164-column frame as before. The Kaggle push writes the
widened frame with write_wide(), so the published dataset keeps the full schema.

Functions
---------
  slim(wide_df, study1_cols)     drop the columns that study1_daily already holds
  widen(slim_df, study1_df)      re-join study1_daily on date (left join, 96 rows/day)
  load_study2(parse_dates=True)  read slim file + study1_daily, return the wide frame
  wide_columns()                 the wide column list, from the two CSV headers only
  write_wide(out_path)           write the wide file (used for the Kaggle upload)

CLI
---
  python Pipeline/study2_io.py --write-wide OUT.csv   # wide copy for Kaggle
  python Pipeline/study2_io.py --slim-in-place        # one-off migration of a wide file

Column order of the wide frame: the slim columns in file order, then the study1_daily
columns in study1_daily's order. Every consumer selects by name, so order is cosmetic.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT   = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "Dataset"
STUDY1_CSV  = DATASET_DIR / "study1_daily.csv"
STUDY2_CSV  = DATASET_DIR / "study2_scada.csv"

KEY = "date"


def _study1_cols(study1_path: Path = STUDY1_CSV) -> list[str]:
    return list(pd.read_csv(study1_path, nrows=0).columns)


def slim(wide_df: pd.DataFrame, study1_cols=None) -> pd.DataFrame:
    """Drop every column (except date) that study1_daily.csv also has."""
    if study1_cols is None:
        study1_cols = _study1_cols()
    drop = [c for c in wide_df.columns if c in set(study1_cols) and c != KEY]
    return wide_df.drop(columns=drop)


def widen(slim_df: pd.DataFrame, study1_df: pd.DataFrame) -> pd.DataFrame:
    """Left-join study1_daily's columns onto each slot row by date.

    The date column must have the same type on both sides (both ISO strings, or both
    datetime64). Columns already in slim_df are not taken from study1_df.
    """
    extra = [c for c in study1_df.columns if c != KEY and c not in slim_df.columns]
    return slim_df.merge(study1_df[[KEY] + extra], on=KEY, how="left", validate="many_to_one")


def wide_columns(study2_path: Path = STUDY2_CSV, study1_path: Path = STUDY1_CSV) -> list[str]:
    """Wide column list without reading any data rows."""
    s2 = list(pd.read_csv(study2_path, nrows=0).columns)
    return s2 + [c for c in _study1_cols(study1_path) if c != KEY and c not in s2]


def load_study2(parse_dates: bool = True, study2_path: Path = STUDY2_CSV,
                study1_path: Path = STUDY1_CSV, float_precision=None) -> pd.DataFrame:
    """study2_scada.csv joined with study1_daily.csv: the full slot-level frame.

    parse_dates=True gives a datetime64 date column (what the ML and dashboard code
    expect); False keeps the ISO strings as stored. float_precision is passed to
    read_csv; the default matches what consumers read before the file was slimmed.
    """
    pd_kw = {"parse_dates": [KEY]} if parse_dates else {}
    pd_kw["float_precision"] = float_precision
    s2 = pd.read_csv(study2_path, **pd_kw)
    s1 = pd.read_csv(study1_path, **pd_kw)
    return widen(s2, s1)


def write_wide(out_path: Path, study2_path: Path = STUDY2_CSV,
               study1_path: Path = STUDY1_CSV) -> pd.DataFrame:
    """Write the wide file (ISO date strings, as the committed CSVs use)."""
    # round_trip: every cell is written back as stored in the two committed CSVs.
    df = load_study2(parse_dates=False, study2_path=study2_path, study1_path=study1_path,
                     float_precision="round_trip")
    df.to_csv(out_path, index=False)
    return df


REL_TOL = 1e-9
ABS_TOL = 1e-9   # for values that should be 0 but carry float residue (e.g. -2e-14)


def mismatched_columns(a: pd.DataFrame, b: pd.DataFrame) -> list[str]:
    """Columns where two same-shaped frames disagree. Numbers may differ by REL_TOL
    (relative) or ABS_TOL (absolute; the two parsers sum some figures in a different order, so a fresh
    rebuild differs from study1_daily by ~1e-12 on a few hundred cells). Text and the
    position of empty cells must match exactly."""
    bad = []
    for c in a.columns:
        x, y = a[c], b[c]
        if not x.isna().equals(y.isna()):
            bad.append(c)
            continue
        keep = x.notna()
        x, y = x[keep], y[keep]
        if x.dtype.kind in "fiu" and y.dtype.kind in "fiu":
            if not np.allclose(x.to_numpy(float), y.to_numpy(float), rtol=REL_TOL, atol=ABS_TOL):
                bad.append(c)
        elif not x.astype(str).equals(y.astype(str)):
            bad.append(c)
    return bad


def _main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write-wide", metavar="OUT_CSV",
                   help="Write study2_scada joined with study1_daily to OUT_CSV.")
    g.add_argument("--slim-in-place", action="store_true",
                   help="Rewrite Dataset/study2_scada.csv without the study1_daily columns "
                        "(refuses if any dropped value disagrees with study1_daily).")
    args = ap.parse_args()

    if args.write_wide:
        df = write_wide(Path(args.write_wide))
        print(f"study2_io: wrote {len(df):,} rows x {len(df.columns)} cols -> {args.write_wide}")
        return

    # round_trip so the kept cells are written back exactly as they were read
    # (the default parser can be off by one unit in the last digit).
    wide = pd.read_csv(STUDY2_CSV, float_precision="round_trip")
    s1 = pd.read_csv(STUDY1_CSV, float_precision="round_trip")
    out = slim(wide, list(s1.columns))
    if len(out.columns) == len(wide.columns):
        print("study2_io: file is already slim -- nothing to do.")
        return
    # Lossless check: widening the slim frame must give back the dropped values.
    back = widen(out, s1)[wide.columns]
    bad = mismatched_columns(wide, back)
    if bad:
        sys.exit(f"study2_io: refusing to slim, {len(bad)} column(s) differ from study1_daily: {bad[:10]}")
    out.to_csv(STUDY2_CSV, index=False)
    print(f"study2_io: slimmed {len(wide.columns)} -> {len(out.columns)} cols, {len(out):,} rows")


if __name__ == "__main__":
    _main()
