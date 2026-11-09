"""
update_live.py -- Daily incremental update for Grid-Sentinel live pipeline.

Downloads today's PSP file from NLDC, parses it, and appends new rows to:
  - Dataset/study1_daily.csv   (one daily row)
  - Dataset/study2_scada.csv   (96 fifteen-minute rows, only if TimeSeries sheet present)
  - Dataset/study3_states.csv  (~37 state/UT/entity rows, section C)

Exit codes:
  0  -- success, CSVs updated
  1  -- file not published yet (safe to retry later)
  2  -- unexpected error

Usage:
  python Scrapings/update_live.py
  python Scrapings/update_live.py --date 2026-06-24   # override date (for backfill)
"""

import argparse
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ── Paths (relative to repo root) ────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = Path(__file__).resolve().parent
STUDY1_CSV   = REPO_ROOT / "Dataset" / "study1_daily.csv"
STUDY2_CSV   = REPO_ROOT / "Dataset" / "study2_scada.csv"
STUDY3_CSV   = REPO_ROOT / "Dataset" / "study3_states.csv"
FILE2_RAW    = REPO_ROOT / "Dataset" / "Raw" / "File2_Raw"
FILE3_RAW    = REPO_ROOT / "Dataset" / "Raw" / "File3_Raw"

sys.path.insert(0, str(SCRAPERS_DIR))


def download_today(target_date: date, out_dir: Path) -> Path | None:
    """
    Download the PSP file for target_date into out_dir.
    Tries in order:
      1. Old CDN direct URL (report.grid-india.in) -- no browser needed
      2. CDN S3 listing (webcdn.grid-india.in) -- no browser needed
      3. Playwright listing scrape -- fallback for local runs
    Returns the local file path on success, None if not found.
    """
    from download_psp_new import (
        stem, fetch_bytes, old_url, find_url_without_browser,
        download_range, NEW_CDN_START,
    )

    s = stem(target_date)

    # Return early if already downloaded
    existing = list(out_dir.glob(f"{s}_NLDC_PSP*"))
    if existing:
        print(f"  Already present: {existing[0].name}")
        return existing[0]

    # ── 1. Old CDN (requests only, always fast) ───────────────────────────────
    for ext in ("xls", "pdf"):
        url = old_url(target_date, ext)
        content = fetch_bytes(url)
        if content:
            dest = out_dir / f"{s}_NLDC_PSP.{ext}"
            dest.write_bytes(content)
            print(f"  Downloaded via old CDN: {dest.name} ({len(content):,} bytes)")
            return dest

    # ── 2. New CDN: browser-free S3 listing ──────────────────────────────────
    if target_date >= NEW_CDN_START:
        url = find_url_without_browser(target_date)
        if url:
            ext = url.rsplit(".", 1)[-1]
            content = fetch_bytes(url)
            if content:
                dest = out_dir / f"{s}_NLDC_PSP.{ext}"
                dest.write_bytes(content)
                print(f"  Downloaded via CDN listing: {dest.name} ({len(content):,} bytes)")
                return dest

        # ── 3. Playwright fallback (works locally, may fail in CI) ────────────
        print("  Trying Playwright listing scrape (may fail in CI)...")
        download_range(target_date, target_date, out_dir, delay=0)
        result = list(out_dir.glob(f"{s}_NLDC_PSP*"))
        if result:
            return result[0]

    print(f"  {s}: not found on any CDN.")
    return None


def append_study1(raw_file: Path) -> bool:
    """Parse raw_file, append one daily row to study1_daily.csv. Returns True if new row added."""
    from parse_psp_pdf_xls_file2 import parse_file

    row = parse_file(str(raw_file))
    if not row or not row.get("date"):
        print(f"  parse_file returned empty for {raw_file.name}")
        return False

    row_date = str(row["date"])
    existing = pd.read_csv(STUDY1_CSV)
    # NOTE: dates in this file are already clean ISO (YYYY-MM-DD). Do NOT use
    # dayfirst=True with format="mixed" here -- on pandas 3.x this misparses
    # valid ISO strings (e.g. "2026-06-12" silently becomes "2026-12-06").
    # This was confirmed as the actual root cause of widespread date corruption
    # in study2_scada.csv. Use an explicit ISO format instead.
    existing["date"] = pd.to_datetime(existing["date"], format="%Y-%m-%d").dt.strftime("%Y-%m-%d")

    if row_date in existing["date"].values:
        print(f"  study1_daily: {row_date} already present -- skipping.")
        return False

    new_row = pd.DataFrame([row])
    # Align columns -- add missing cols as NaN, drop extra cols
    for col in existing.columns:
        if col not in new_row.columns:
            new_row[col] = float("nan")
    new_row = new_row[existing.columns]
    # parse_file returns a datetime.date; the existing column is ISO strings.
    # Store the string so the column has one type and the sort below works.
    new_row["date"] = row_date

    updated = pd.concat([existing, new_row], ignore_index=True)
    # Keep date order even when a scan or backfill appends an older day after
    # newer ones (as the Oct 2026 backfill did), matching study2/study3.
    updated = updated.sort_values("date", kind="stable").reset_index(drop=True)
    updated.to_csv(STUDY1_CSV, index=False)
    print(f"  study1_daily: appended {row_date} ({sum(v is not None and str(v) != 'nan' for v in row.values())} non-null fields)")
    return True


def append_study3(raw_file: Path) -> bool:
    """Parse raw_file's section C states table, append new (date, state) rows to
    study3_states.csv. Uses the same static STATE_TO_REGION map and
    STATE_NAME_ALIASES as the full rebuild (parse_psp_states.py) so incremental
    appends stay consistent with a from-scratch build -- unlike the earlier
    majority-vote approach, the static map means a single day's rows can be
    resolved correctly without needing the whole archive present."""
    from parse_psp_states import (
        parse_file as parse_states_file, STATE_NAME_ALIASES,
        STATE_TO_REGION, UNRECOVERABLE_STATE_LABELS, COLS,
    )

    rows = parse_states_file(str(raw_file))
    if not rows:
        print(f"  study3_states: parse_file returned empty for {raw_file.name}")
        return False

    row_date = str(rows[0]["date"])
    existing = pd.read_csv(STUDY3_CSV)
    existing["date"] = pd.to_datetime(existing["date"], format="%Y-%m-%d").dt.strftime("%Y-%m-%d")

    if row_date in existing["date"].values:
        print(f"  study3_states: {row_date} already present -- skipping.")
        return False

    new_rows = pd.DataFrame(rows)
    new_rows["date"] = new_rows["date"].astype(str)
    new_rows = new_rows[~new_rows["state"].isin(UNRECOVERABLE_STATE_LABELS)]
    if new_rows.empty:
        print(f"  study3_states: all rows unrecoverable for {raw_file.name} -- skipping.")
        return False
    new_rows["state"] = new_rows["state"].replace(STATE_NAME_ALIASES)
    new_rows["region"] = new_rows["state"].map(STATE_TO_REGION)
    unmapped = new_rows.loc[new_rows["region"].isna(), "state"].unique().tolist()
    if unmapped:
        print(f"  study3_states: WARNING -- {len(unmapped)} state(s) not in STATE_TO_REGION, "
              f"row(s) will have a null region until the map is updated: {unmapped}")

    col_order = ["date", "region", "state"] + COLS
    new_rows = new_rows[col_order]

    updated = pd.concat([existing, new_rows], ignore_index=True)
    updated = updated.sort_values(["date", "region", "state"]).reset_index(drop=True)
    updated.to_csv(STUDY3_CSV, index=False)
    print(f"  study3_states: appended {len(new_rows)} row(s) for {row_date}")
    return True


def append_study2(raw_file: Path) -> bool:
    """Parse raw_file timeseries, append 96 rows to study2_scada.csv. Returns True if rows added."""
    from parse_psp_xls_pdf_file3 import build_timeseries_long

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_csv = Path(tmp.name)

    try:
        build_timeseries_long(str(raw_file), str(tmp_csv))
    except Exception as e:
        print(f"  study2_scada: parser error for {raw_file.name} -- {e}")
        tmp_csv.unlink(missing_ok=True)
        return False

    try:
        new_rows = pd.read_csv(tmp_csv)
    except (pd.errors.EmptyDataError, Exception) as e:
        print(f"  study2_scada: no TimeSeries data in {raw_file.name} -- {e}")
        tmp_csv.unlink(missing_ok=True)
        return False
    finally:
        tmp_csv.unlink(missing_ok=True)

    if new_rows.empty:
        print(f"  study2_scada: no TimeSeries sheet in {raw_file.name} -- skipping.")
        return False

    # Standardise date to ISO
    # NOTE: these dates are already clean ISO (YYYY-MM-DD) coming out of
    # build_timeseries_long(). Do NOT use dayfirst=True with format="mixed" --
    # on pandas 3.x this misparses valid ISO strings (e.g. "2026-06-12" silently
    # becomes "2026-12-06"). This was confirmed as the actual root cause of
    # widespread date corruption in study2_scada.csv. Use an explicit ISO format.
    new_rows["date"] = pd.to_datetime(new_rows["date"], format="%Y-%m-%d").dt.strftime("%Y-%m-%d")
    new_date = new_rows["date"].iloc[0]

    existing = pd.read_csv(STUDY2_CSV)
    existing["date"] = pd.to_datetime(existing["date"], format="%Y-%m-%d").dt.strftime("%Y-%m-%d")

    if new_date in existing["date"].values:
        print(f"  study2_scada: {new_date} already present -- skipping.")
        return False

    # Drop stub days (< 10 slots)
    if len(new_rows) < 10:
        print(f"  study2_scada: {new_date} has only {len(new_rows)} slots -- stub, skipping.")
        return False

    # Align columns
    for col in existing.columns:
        if col not in new_rows.columns:
            new_rows[col] = float("nan")
    new_rows = new_rows[existing.columns]

    updated = pd.concat([existing, new_rows], ignore_index=True)
    before = len(updated)
    updated = updated.drop_duplicates(subset=["date", "hhmm"], keep="last")
    if len(updated) < before:
        print(f"  study2_scada: dropped {before - len(updated)} duplicate rows.")
    updated = updated.sort_values(["date", "hhmm"]).reset_index(drop=True)
    updated.to_csv(STUDY2_CSV, index=False)
    print(f"  study2_scada: appended {len(new_rows)} rows for {new_date}")
    return True


def validate(study1_changed: bool, study2_changed: bool, study3_changed: bool = False):
    """Basic sanity checks on the updated CSVs."""
    errors = []

    if study1_changed:
        df1 = pd.read_csv(STUDY1_CSV)
        # dates are already clean ISO -- no dayfirst=True (see note above; on
        # pandas 3.x it silently corrupts valid ISO strings).
        df1["date"] = pd.to_datetime(df1["date"], format="%Y-%m-%d")
        dups = df1.duplicated("date").sum()
        if dups > 0:
            errors.append(f"study1_daily: {dups} duplicate dates after append")
        null_pct = df1.isnull().mean().mean()
        if null_pct > 0.35:
            errors.append(f"study1_daily: null % jumped to {null_pct:.1%} (threshold 35%)")

    if study2_changed:
        df2 = pd.read_csv(STUDY2_CSV)
        dups = df2.duplicated(["date", "hhmm"]).sum()
        if dups > 0:
            errors.append(f"study2_scada: {dups} duplicate (date, hhmm) rows after append")

    if study3_changed:
        df3 = pd.read_csv(STUDY3_CSV)
        dups = df3.duplicated(["date", "state"]).sum()
        if dups > 0:
            errors.append(f"study3_states: {dups} duplicate (date, state) rows after append")
        n_null_region = df3["region"].isna().sum()
        if n_null_region:
            errors.append(f"study3_states: {n_null_region} row(s) with no resolved region after append")

    if errors:
        for e in errors:
            print(f"  VALIDATION ERROR: {e}")
        return False

    print("  Validation passed.")
    return True


def _parse_file_date(path: Path) -> date | None:
    """Extract date from filename like 19.06.25_NLDC_PSP.xls -> date(2025, 6, 19)."""
    try:
        parts = path.name.split("_")[0].split(".")
        return date(2000 + int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        return None


DEFAULT_LOOKBACK_DAYS = 90


def _dates_in_all_csvs() -> set[str]:
    """ISO dates already present in study1_daily, study2_scada AND study3_states."""
    present = []
    for path in (STUDY1_CSV, STUDY2_CSV, STUDY3_CSV):
        present.append(set(pd.read_csv(path, usecols=["date"])["date"].astype(str)))
    return set.intersection(*present)


def scan_and_parse(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> tuple[bool, bool, bool]:
    """
    Parse raw files in FILE3_RAW dated within the last `lookback_days` days that are
    not yet reflected in the CSVs. Files whose date is already in all three CSVs are
    skipped without being parsed, so a long window is cheap -- and it is what makes a
    pipeline outage self-healing: once whatever broke is fixed, the next scan fills
    every missing day, not just the most recent few (a fixed 10-day window left a
    permanent hole after the Sept 30 - Nov 5 2026 outage).
    Returns (study1_changed, study2_changed, study3_changed).
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    all_files = sorted(FILE3_RAW.glob("*_NLDC_PSP*"))
    in_window = [f for f in all_files if (d := _parse_file_date(f)) and d >= cutoff]
    present = _dates_in_all_csvs()
    raw_files = [f for f in in_window if _parse_file_date(f).isoformat() not in present]

    if not raw_files:
        print(f"No unparsed raw files in Dataset/Raw/File3_Raw within the last {lookback_days} days "
              f"({len(in_window)} checked, all already in the CSVs).")
        return False, False, False

    print(f"Scanning {len(raw_files)} unparsed file(s) from {cutoff} onward "
          f"({len(in_window)} in window, {len(all_files)} total).")
    s1_any = False
    s2_any = False
    s3_any = False
    scan_errors = []
    for raw_file in raw_files:
        print(f"\nParsing {raw_file.name}...")
        try:
            s1 = append_study1(raw_file)
        except Exception as e:
            print(f"  study1_daily: ERROR processing {raw_file.name} -- {e!r} (skipping this file, continuing scan)")
            scan_errors.append((raw_file.name, "study1", repr(e)))
            s1 = False
        try:
            s2 = append_study2(raw_file)
        except Exception as e:
            print(f"  study2_scada: ERROR processing {raw_file.name} -- {e!r} (skipping this file, continuing scan)")
            scan_errors.append((raw_file.name, "study2", repr(e)))
            s2 = False
        try:
            s3 = append_study3(raw_file)
        except Exception as e:
            print(f"  study3_states: ERROR processing {raw_file.name} -- {e!r} (skipping this file, continuing scan)")
            scan_errors.append((raw_file.name, "study3", repr(e)))
            s3 = False
        s1_any = s1_any or s1
        s2_any = s2_any or s2
        s3_any = s3_any or s3

    if scan_errors:
        print(f"\n{len(scan_errors)} file(s) hit errors during scan (see above) -- "
              f"any rows successfully appended before/around them are still kept.")

    return s1_any, s2_any, s3_any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target data date (YYYY-MM-DD). Default: yesterday.")
    parser.add_argument("--scan", action="store_true",
                        help="Parse all unparsed files in Dataset/Raw/File3_Raw (used for push-triggered runs).")
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help="With --scan: only consider raw files dated within this many days "
                             f"(default {DEFAULT_LOOKBACK_DAYS}). Days already in the CSVs are skipped cheaply.")
    args = parser.parse_args()

    from download_psp_new import stem

    print(f"\n=== Grid-Sentinel daily update -- {date.today()} ===\n")

    FILE2_RAW.mkdir(exist_ok=True)
    FILE3_RAW.mkdir(exist_ok=True)

    # ── Scan mode: parse whatever is already in File3_Raw ────────────────────
    if args.scan:
        print(f"Scan mode: parsing all unparsed files in Dataset/Raw/File3_Raw "
              f"(last {args.lookback} days)...")
        s1_changed, s2_changed, s3_changed = scan_and_parse(lookback_days=args.lookback)
    else:
        # ── Download mode: fetch a specific or today's file ──────────────────
        if args.date:
            target_data_date = date.fromisoformat(args.date)
            file_dates_to_try = [target_data_date + timedelta(1), target_data_date]
        else:
            today = date.today()
            file_dates_to_try = [today, today - timedelta(1)]

        raw_file = None
        for file_date in file_dates_to_try:
            print(f"Trying file date: {stem(file_date)}")
            raw_file = download_today(file_date, FILE3_RAW)
            if raw_file:
                file2_dest = FILE2_RAW / raw_file.name
                if not file2_dest.exists():
                    shutil.copy2(raw_file, file2_dest)
                    print(f"  Copied to Dataset/Raw/File2_Raw: {raw_file.name}")
                break
        else:
            print("\nNo file available yet -- will retry at next scheduled run.")
            sys.exit(1)

        print(f"\nParsing {raw_file.name}...")
        s1_changed = append_study1(raw_file)
        s2_changed = append_study2(raw_file)
        s3_changed = append_study3(raw_file)

    if not s1_changed and not s2_changed and not s3_changed:
        print("\nNo new data added (already up to date).")
        sys.exit(0)

    print("\nRunning validation...")
    ok = validate(s1_changed, s2_changed, s3_changed)
    if not ok:
        sys.exit(2)

    print("\nDone. CSVs updated successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
