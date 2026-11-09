"""
build_all.py -- Single-command rebuild for all Grid-Sentinel datasets.

Runs in order:
  1. Dataset/Raw/File1_Raw  -> tmp/f1_daily.csv                     (parse_psp_pdf_xls_file1.py)
  2. Dataset/Raw/File2_Raw  -> Dataset/study1_daily.csv             (parse_psp_pdf_xls_file2.py)
  3. Dataset/Raw/File2_Raw  -> Dataset/study3_states.csv            (parse_psp_states.py)
  4. Dataset/Raw/File3_Raw  -> Dataset/study2_scada.csv             (parse_psp_xls_pdf_file3.py long,
                                                                     then study2_io.py --slim-in-place)
  5. tmp/f1_daily.csv + Reference/hourlyLoadDataIndia.xlsx
               -> Dataset/study1_hourly.csv             (in-process pandas join)

Steps 1-4 run as subprocesses so each parser's stdout flows straight to the console.
Step 5 is in-process: left-joins f1_daily onto hourly rows (each daily PSP row
broadcasts onto all 24 hourly rows for that date).

After all steps, prints row x col counts, date range, overall null %, and the 8
worst-null columns for each output. Warns if any dataset falls below baseline row count.

Does NOT run the validation gate (validate.py -- roadmap sec.1b) or push to Kaggle
(that's daily_scrape.yml step 6). Does NOT download raw files (use local_download.py).

Expected run time: 15–45 min for a full rebuild over ~2,660 files.
Incremental rebuilds with --skip-file1/2 run in under a minute.

Usage:
  python Pipeline/build_all.py                    # full rebuild
  python Pipeline/build_all.py --skip-file1       # skip File1 parse (f1_daily.csv already exists)
  python Pipeline/build_all.py --skip-file2       # skip File2 parse
  python Pipeline/build_all.py --skip-file3       # skip File3 parse
  python Pipeline/build_all.py --skip-states      # skip study3_states parse
  python Pipeline/build_all.py --skip-hourly      # skip hourly join
  python Pipeline/build_all.py --only-hourly      # only redo the hourly join

  # Example: rebuilt only study2_scada (new files added to Dataset/Raw/File3_Raw):
  python Pipeline/build_all.py --skip-file1 --skip-file2 --skip-states
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# -- Paths ---------------------------------------------------------------------
REPO_ROOT    = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = REPO_ROOT / "Scrapings"
DATASET_DIR  = REPO_ROOT / "Dataset"

FILE1_RAW    = REPO_ROOT / "Dataset" / "Raw" / "File1_Raw"
FILE2_RAW    = REPO_ROOT / "Dataset" / "Raw" / "File2_Raw"
FILE3_RAW    = REPO_ROOT / "Dataset" / "Raw" / "File3_Raw"

TMP_DIR      = REPO_ROOT / "tmp"
F1_DAILY     = TMP_DIR / "f1_daily.csv"
HOURLY_SRC   = REPO_ROOT / "Reference" / "hourlyLoadDataIndia.xlsx"

OUT_STUDY1_D = DATASET_DIR / "study1_daily.csv"
OUT_STUDY1_H = DATASET_DIR / "study1_hourly.csv"
OUT_STUDY2   = DATASET_DIR / "study2_scada.csv"
OUT_STUDY3   = DATASET_DIR / "study3_states.csv"

# -- Expected baseline row counts (from roadmap) -------------------------------
# Allowed to grow (new daily data added), but never shrink below these.
BASELINES = {
    "study1_daily":  2660,
    "study1_hourly": 46728,
    "study2_scada":  55068,
    "study3_states": 99000,
}

# -- Helpers -------------------------------------------------------------------

def _run(cmd: list[str], label: str) -> bool:
    """Run a subprocess; return True on success."""
    print(f"\n{'-'*60}")
    print(f"  [{label}] Running: {' '.join(str(c) for c in cmd)}")
    print(f"{'-'*60}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"\n  X  [{label}] exited with code {result.returncode}")
        return False
    print(f"\n  OK  [{label}] done")
    return True


def _null_summary(df: pd.DataFrame, top_n: int = 8) -> str:
    """Return a compact null-% string for the worst columns."""
    null_pct = df.isnull().mean().sort_values(ascending=False)
    worst = null_pct[null_pct > 0].head(top_n)
    if worst.empty:
        return "    no nulls"
    lines = [f"    {col}: {pct:.1%}" for col, pct in worst.items()]
    return "\n".join(lines)


def _print_summary(label: str, path: Path):
    """Print row count and null summary for a CSV."""
    if not path.exists():
        print(f"  !  {label}: file not found at {path}")
        return
    df = pd.read_csv(path, low_memory=False)
    print(f"\n  {label}")
    print(f"    rows x cols : {len(df):,} x {len(df.columns)}")
    date_col = "date" if "date" in df.columns else ("datetime" if "datetime" in df.columns else None)
    if date_col:
        print(f"    date range  : {df[date_col].min()} -> {df[date_col].max()}")
    print(f"    overall null: {df.isnull().mean().mean():.1%}")
    print(f"    worst cols  :")
    print(_null_summary(df))

    # Baseline check
    key = path.stem  # e.g. "study1_daily"
    if key in BASELINES and len(df) < BASELINES[key]:
        print(f"\n  !  WARNING: {key} has {len(df):,} rows -- below baseline {BASELINES[key]:,}!")


# -- Step 4: hourly join -------------------------------------------------------

def build_study1_hourly():
    """
    Left-join f1_daily (PSP features, daily) onto hourlyLoadDataIndia (hourly load).
    Each daily PSP row broadcasts onto all 24 hourly rows for that date.
    Output: Dataset/study1_hourly.csv
    """
    print(f"\n{'-'*60}")
    print("  [hourly-join] Building study1_hourly.csv")
    print(f"{'-'*60}")

    if not F1_DAILY.exists():
        print(f"  X  f1_daily.csv not found at {F1_DAILY} -- run File1 parse first.")
        return False
    if not HOURLY_SRC.exists():
        print(f"  X  hourlyLoadDataIndia.xlsx not found at {HOURLY_SRC}")
        return False

    print("    Reading f1_daily.csv...")
    f1 = pd.read_csv(F1_DAILY, low_memory=False)
    # f1_daily.csv dates are already clean ISO (YYYY-MM-DD). Do NOT use
    # dayfirst=True with format="mixed" -- on pandas 3.x this misparses valid
    # ISO strings (e.g. "2026-06-12" silently becomes "2026-12-06"), which was
    # confirmed as the root cause of widespread date corruption elsewhere in
    # this pipeline.
    f1["date"] = pd.to_datetime(f1["date"], format="%Y-%m-%d").dt.strftime("%Y-%m-%d")

    print("    Reading hourlyLoadDataIndia.xlsx...")
    hourly = pd.read_excel(HOURLY_SRC)

    # The hourly file uses "datetime" (with time component); extract date only.
    if "datetime" not in hourly.columns:
        date_cols = [c for c in hourly.columns if "date" in c.lower()]
        if not date_cols:
            print("  X  hourlyLoadDataIndia.xlsx has no recognisable date column.")
            print(f"     Columns found: {list(hourly.columns)}")
            return False
        hourly.rename(columns={date_cols[0]: "datetime"}, inplace=True)
    hourly["date"] = pd.to_datetime(hourly["datetime"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")

    print(f"    Merging: {len(hourly):,} hourly rows x {len(f1):,} daily PSP rows...")
    merged = hourly.merge(f1, on="date", how="left", suffixes=("", "_psp"))
    dup_cols = [c for c in merged.columns if c.endswith("_psp")]
    if dup_cols:
        print(f"    Dropping {len(dup_cols)} duplicate suffix columns.")
        merged.drop(columns=dup_cols, inplace=True)
    # Put date + datetime first
    front = [c for c in ("date", "datetime") if c in merged.columns]
    merged = merged[front + [c for c in merged.columns if c not in front]]

    DATASET_DIR.mkdir(exist_ok=True)
    merged.to_csv(OUT_STUDY1_H, index=False)
    print(f"    OK  Wrote {len(merged):,} rows -> {OUT_STUDY1_H}")
    return True


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-file1",  action="store_true", help="Skip File1 -> f1_daily parse")
    parser.add_argument("--skip-file2",  action="store_true", help="Skip File2 -> study1_daily parse")
    parser.add_argument("--skip-file3",  action="store_true", help="Skip File3 -> study2_scada parse")
    parser.add_argument("--skip-states", action="store_true", help="Skip File2 -> study3_states parse")
    parser.add_argument("--skip-hourly", action="store_true", help="Skip f1_daily + hourly join")
    parser.add_argument("--only-hourly", action="store_true", help="Only run the hourly join (implies --skip-file1/2/3)")
    args = parser.parse_args()

    if args.only_hourly:
        args.skip_file1 = args.skip_file2 = args.skip_file3 = args.skip_states = True

    DATASET_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"  Grid-Sentinel -- build_all.py -- {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    errors = []

    # -- Step 1: File1 -> f1_daily ----------------------------------------------
    if not args.skip_file1:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_pdf_xls_file1.py"),
             str(FILE1_RAW), str(F1_DAILY)],
            "file1->f1_daily"
        )
        if not ok:
            errors.append("file1 parse failed")

    # -- Step 2: File2 -> study1_daily -----------------------------------------
    if not args.skip_file2:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_pdf_xls_file2.py"),
             str(FILE2_RAW), str(OUT_STUDY1_D)],
            "file2->study1_daily"
        )
        if not ok:
            errors.append("file2 parse failed")

    # -- Step 3: File2 -> study3_states -----------------------------------------
    if not args.skip_states:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_states.py"),
             str(FILE2_RAW), str(OUT_STUDY3)],
            "file2->study3_states"
        )
        if not ok:
            errors.append("states parse failed")

    # -- Step 4: File3 -> study2_scada -----------------------------------------
    if not args.skip_file3:
        ok = _run(
            [sys.executable, str(SCRAPERS_DIR / "parse_psp_xls_pdf_file3.py"),
             "long", str(FILE3_RAW), str(OUT_STUDY2)],
            "file3->study2_scada"
        )
        if not ok:
            errors.append("file3 parse failed")
        else:
            # The parser writes the wide frame (study1_daily's columns broadcast onto
            # every slot). Drop them so the committed file stays far below GitHub's
            # 100 MB limit; every reader re-joins them (Pipeline/study2_io.py). This
            # refuses, and the build fails, if any dropped value disagrees with
            # study1_daily.csv, so rebuild study1_daily first if File2 changed too.
            ok = _run(
                [sys.executable, str(REPO_ROOT / "Pipeline" / "study2_io.py"), "--slim-in-place"],
                "study2_scada slim"
            )
            if not ok:
                errors.append("study2_scada slim failed (daily columns disagree with study1_daily)")

    # -- Step 5: hourly join -----------------------------------------------------
    if not args.skip_hourly:
        ok = build_study1_hourly()
        if not ok:
            errors.append("hourly join failed")

    # -- Summary of all outputs ---------------------------------------------------
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    _print_summary("study1_daily", OUT_STUDY1_D)
    _print_summary("study2_scada", OUT_STUDY2)
    _print_summary("study1_hourly", OUT_STUDY1_H)
    _print_summary("study3_states", OUT_STUDY3)

    elapsed = datetime.now() - start
    print(f"\n{'='*60}")
    if errors:
        print(f"  DONE WITH ERRORS ({len(errors)}) in {elapsed}")
        for e in errors:
            print(f"    - {e}")
        print(f"{'='*60}\n")
        sys.exit(1)
    else:
        print(f"  DONE -- all steps completed in {elapsed}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
