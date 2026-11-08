"""
validate.py -- Post-build validation gate for Grid-Sentinel datasets.

Loads the three output CSVs and runs a fixed set of integrity checks.
Prints a result line (PASS / WARN / FAIL) for each check.
Exits with code 0 if no FAILs, code 1 if any check fails.

Usage:
    python Pipeline/validate.py                  # run all checks
    python Pipeline/validate.py --only study1    # run only study1_daily checks
    python Pipeline/validate.py --only study2    # run only study2_scada checks
    python Pipeline/validate.py --only study3    # run only study3_states checks
    python Pipeline/validate.py --only hourly    # run only study1_hourly checks
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "Dataset"
KNOWN_GAPS_FILE = REPO_ROOT / "Pipeline" / "known_gaps.json"
NULL_BASELINE_FILE = REPO_ROOT / "Pipeline" / "null_baselines.json"

# A column's null% has to rise by more than this many percentage points above its
# stored baseline to get flagged -- small fluctuations are expected as more rows
# accumulate; this is tuned to catch a structural degradation (a field going from
# "sometimes null" to "usually null"), not single-row noise.
NULL_DRIFT_THRESHOLD_PP = 5.0

STUDY1_D = DATASET_DIR / "study1_daily.csv"
STUDY1_H = DATASET_DIR / "study1_hourly.csv"
STUDY2   = DATASET_DIR / "study2_scada.csv"
STUDY3   = DATASET_DIR / "study3_states.csv"

# ── Baseline thresholds ───────────────────────────────────────────────────────
BASELINE_ROWS = {
    "study1_daily":  2660,
    "study1_hourly": 46728,
    "study2_scada":  56796,  # 2026-07-07: full rebuild from all raw XLS files after discovering ~40% of legacy date labels were wrong (day/month transposed)
    "study3_states": 99000,  # 2026-07-10: first full build, ~2678 dates x ~37 states/UTs/entities
}

BASELINE_COLS = {
    "study1_daily":  144,
    "study1_hourly": 151,
    "study2_scada":  164,
    "study3_states": 10,
}

REGIONS = ["NR", "WR", "SR", "ER", "NER"]

# Maximum days a dataset's latest date is allowed to lag behind today
# before a warning is raised. Accounts for weekends and the 1-day
# publication lag in NLDC reports.
MAX_LAG_DAYS = 5

# ── Inter-regional corridors checked for net = import - export ───────────────
IR_CORRIDORS = [
    "ir_er_nr",
    "ir_er_wr",
    "ir_er_sr",
    "ir_er_ner",
    "ir_ner_nr",
    "ir_wr_nr",
    "ir_wr_sr",
]

# ── Cross-border countries ────────────────────────────────────────────────────
XB_COUNTRIES = ["bhutan", "nepal", "bangladesh", "myanmar"]

# ── Result tracking ───────────────────────────────────────────────────────────
_results: list[tuple[str, str, str]] = []  # (status, dataset, message)


def _record(status: str, dataset: str, message: str) -> None:
    _results.append((status, dataset, message))
    tag = f"[{status:4s}]"
    print(f"  {tag}  {dataset}: {message}")


def ok(dataset: str, message: str)   -> None: _record("PASS", dataset, message)
def warn(dataset: str, message: str) -> None: _record("WARN", dataset, message)
def fail(dataset: str, message: str) -> None: _record("FAIL", dataset, message)


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load(path: Path, label: str) -> pd.DataFrame | None:
    if not path.exists():
        fail(label, f"file not found: {path}")
        return None
    df = pd.read_csv(path, low_memory=False)
    return df


def _load_known_gaps() -> dict:
    if not KNOWN_GAPS_FILE.exists():
        return {}
    with open(KNOWN_GAPS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        dataset: {entry["date"] for entry in entries}
        for dataset, entries in data.get("gaps", {}).items()
    }


_KNOWN_GAPS = _load_known_gaps()


def _load_null_baselines() -> dict:
    if not NULL_BASELINE_FILE.exists():
        return {}
    with open(NULL_BASELINE_FILE, encoding="utf-8") as fh:
        return json.load(fh).get("null_pct_baseline", {})


_NULL_BASELINES = _load_null_baselines()


def _check_null_drift(df: pd.DataFrame, label: str) -> None:
    """Flags a column whose null% has risen meaningfully above its stored baseline
    -- catches a source format change silently degrading one field (e.g. a section
    header the parser matches on shifting position) without needing every column to
    be non-null, which most legitimately aren't (see null_baselines.json's _meta)."""
    baseline = _NULL_BASELINES.get(label)
    if not baseline:
        return
    current = (df.isna().mean() * 100).round(2)
    drifted = []
    for col, base_pct in baseline.items():
        if col not in current.index:
            continue
        delta = current[col] - base_pct
        if delta > NULL_DRIFT_THRESHOLD_PP:
            drifted.append(f"{col} ({base_pct}% -> {current[col]}%)")
    if drifted:
        warn(label, f"{len(drifted)} column(s) with null% risen >{NULL_DRIFT_THRESHOLD_PP}pp above baseline: {drifted}")
    else:
        ok(label, "no column null% drifted above baseline")


def _check_date_gaps(df: pd.DataFrame, label: str, date_col: str = "date") -> None:
    """Compares the dataset's actual missing dates (within its own min-max range)
    against Pipeline/known_gaps.json. A gap not in that file is either a genuine new
    problem (scraper regression, parser bug) or a real new NLDC-side absence that
    just hasn't been individually verified and added yet -- either way, it shouldn't
    pass silently. See known_gaps.json's `_meta` block for how to regenerate it.
    """
    if date_col not in df.columns or not KNOWN_GAPS_FILE.exists():
        return
    dates = pd.to_datetime(df[date_col]).dt.date
    present = set(dates)
    full_range = pd.date_range(dates.min(), dates.max(), freq="D")
    missing = {d.date().isoformat() for d in full_range if d.date() not in present}
    known = _KNOWN_GAPS.get(label, set())
    unexplained = sorted(missing - known)
    if unexplained:
        fail(label, f"{len(unexplained)} date gap(s) not in known_gaps.json (new/unexplained): {unexplained}")
    else:
        ok(label, f"all {len(missing)} date gap(s) accounted for in known_gaps.json")


# Generation-mix and frequency sanity. Both bounds mirror the parsers'
# _reconcile_daily() (Scrapings/parse_psp_*.py: SHARE_TOL_PP, FVI_MAX), which fix
# these source-side errors at parse time, so a FAIL here means a new source quirk
# the parser didn't catch or a row written around the parser.
SHARE_TOL_PP = 1.0   # printed share vs. share recomputed from the gen table
FVI_MAX      = 5.0   # FVI is a small index; every real day 2018-2026 is < 0.43
FVI_WARN     = 1.0   # above this is possible but unusual -- worth eyeballing


def _check_gen_share_and_fvi(df: pd.DataFrame, label: str) -> None:
    """share_res_pct / share_nonfossil_pct must agree with the gen_* columns, and
    freq_fvi must be a plausible index value (49.215 on 2021-03-02 was a Hz value
    printed in the FVI cell). Rows broadcast to hourly/15-min grain are reported
    by date."""
    gen = ["gen_res_mu", "gen_total_mu", "gen_hydro_mu", "gen_nuclear_mu"]
    if all(c in df.columns for c in gen):
        total = df["gen_total_mu"].where(df["gen_total_mu"] > 0)
        targets = {
            "share_res_pct": df["gen_res_mu"] / total * 100,
            "share_nonfossil_pct": (df["gen_hydro_mu"] + df["gen_nuclear_mu"]
                                    + df["gen_res_mu"]) / total * 100,
        }
        for col, calc in targets.items():
            if col not in df.columns:
                continue
            bad = (df[col] - calc).abs() > SHARE_TOL_PP
            if bad.any():
                dates = sorted(df.loc[bad, "date"].astype(str).str[:10].unique())
                fail(label, f"{col}: {len(dates)} date(s) differ from gen columns by "
                            f">{SHARE_TOL_PP} pt: {dates}")
            else:
                ok(label, f"{col} agrees with gen columns (within {SHARE_TOL_PP} pt)")

    if "freq_fvi" in df.columns:
        fvi = df["freq_fvi"]
        out = fvi.notna() & ~fvi.between(0, FVI_MAX)
        high = fvi.between(FVI_WARN, FVI_MAX, inclusive="neither")
        if out.any():
            dates = sorted(df.loc[out, "date"].astype(str).str[:10].unique())
            fail(label, f"freq_fvi: {len(dates)} date(s) outside [0, {FVI_MAX}]: {dates}")
        elif high.any():
            dates = sorted(df.loc[high, "date"].astype(str).str[:10].unique())
            warn(label, f"freq_fvi: {len(dates)} date(s) above {FVI_WARN} (unusual): {dates}")
        else:
            ok(label, f"freq_fvi within [0, {FVI_WARN}]")


# ── study1_daily checks ───────────────────────────────────────────────────────

def check_study1_daily() -> None:
    label = "study1_daily"
    df = _load(STUDY1_D, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    _check_null_drift(df, label)
    _check_gen_share_and_fvi(df, label)

    # Duplicate dates
    dupes = df["date"].duplicated().sum() if "date" in df.columns else 0
    if dupes:
        fail(label, f"{dupes} duplicate date(s) found")
    else:
        ok(label, "no duplicate dates")

    # Date gaps vs. the known-gap list
    _check_date_gaps(df, label)

    # Data freshness
    # NOTE: dates here are clean ISO (YYYY-MM-DD), which is unambiguous. Do NOT
    # add dayfirst=True -- combined with format="mixed" it makes pandas misparse
    # valid ISO strings (e.g. "2026-06-12" gets read back as 2026-12-06).
    if "date" in df.columns:
        latest = pd.to_datetime(df["date"]).max().date()
        lag = (date.today() - latest).days
        if lag > MAX_LAG_DAYS:
            warn(label, f"latest date is {latest} ({lag} days ago)")
        else:
            ok(label, f"latest date = {latest} ({lag} day(s) lag)")

    # xb_export columns must be non-negative
    xb_export_cols = [f"xb_export_{c}_mu" for c in XB_COUNTRIES]
    existing_export = [c for c in xb_export_cols if c in df.columns]
    for col in existing_export:
        n_neg = (df[col] < 0).sum()
        if n_neg:
            warn(label, f"{col}: {n_neg} negative value(s)")
        else:
            ok(label, f"{col} >= 0")

    # xb_net = import - export
    for country in XB_COUNTRIES:
        imp_col  = f"xb_import_{country}_mu"
        exp_col  = f"xb_export_{country}_mu"
        net_col  = f"xb_net_{country}_mu"
        if not all(c in df.columns for c in [imp_col, exp_col, net_col]):
            continue
        sub = df[[imp_col, exp_col, net_col]].dropna()
        expected_net = sub[imp_col] - sub[exp_col]
        n_mismatch = (abs(sub[net_col] - expected_net) > 0.01).sum()
        if n_mismatch:
            warn(label, f"xb_net_{country}_mu: {n_mismatch} row(s) where net != import - export")
        else:
            ok(label, f"xb_net_{country}_mu identity holds")

    # ir_*_net = import - export
    for corridor in IR_CORRIDORS:
        imp_col = f"{corridor}_import_mu"
        exp_col = f"{corridor}_export_mu"
        net_col = f"{corridor}_net_mu"
        if not all(c in df.columns for c in [imp_col, exp_col, net_col]):
            continue
        sub = df[[imp_col, exp_col, net_col]].dropna()
        expected_net = sub[imp_col] - sub[exp_col]
        n_mismatch = (abs(sub[net_col] - expected_net) > 0.01).sum()
        if n_mismatch:
            warn(label, f"{net_col}: {n_mismatch} row(s) where net != import - export")
        else:
            ok(label, f"{net_col} identity holds")


# ── study2_scada checks ───────────────────────────────────────────────────────

def check_study2_scada() -> None:
    label = "study2_scada"
    df = _load(STUDY2, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    _check_null_drift(df, label)
    _check_gen_share_and_fvi(df, label)

    # Duplicate (date, hhmm) pairs
    if "date" in df.columns and "hhmm" in df.columns:
        dupes = df.duplicated(subset=["date", "hhmm"]).sum()
        if dupes:
            fail(label, f"{dupes} duplicate (date, hhmm) pair(s)")
        else:
            ok(label, "no duplicate (date, hhmm) pairs")

    # Date gaps vs. the known-gap list (fully-absent dates -- 0 slots -- distinct
    # from the <90-slot severely-incomplete check below, which covers dates that
    # exist but are corrupted)
    _check_date_gaps(df, label)

    # Data freshness
    # NOTE: dates here are clean ISO (YYYY-MM-DD), which is unambiguous. Do NOT
    # add dayfirst=True -- combined with format="mixed" it makes pandas misparse
    # valid ISO strings (e.g. "2026-06-12" gets read back as 2026-12-06).
    if "date" in df.columns:
        latest = pd.to_datetime(df["date"]).max().date()
        lag = (date.today() - latest).days
        if lag > MAX_LAG_DAYS:
            warn(label, f"latest date is {latest} ({lag} days ago)")
        else:
            ok(label, f"latest date = {latest} ({lag} day(s) lag)")
        if latest > date.today():
            fail(label, f"latest date {latest} is in the future -- likely corrupt/mislabeled rows in the source data")

    # Slots per day
    if "date" in df.columns:
        slots_per_day = df.groupby("date").size()

        # Severely incomplete days (< 90 of the expected 96 slots) are corrupted source
        # files, not real grid behavior -- e.g. 2025-10-02 (63 slots, a legacy parse
        # error) plus 2024-11-20 and 2025-04-01 (1 slot each), found 2026-07-11 while
        # building ML/Study2/features.py and confirmed via the same 90-slot threshold
        # used there (MIN_SLOTS_PER_DAY). Previously this script only special-cased the
        # 63-slot day by name, which meant the two 1-slot days -- far more severe, almost
        # a full day of missing data -- fell through into the generic "outside 96" WARN
        # below and looked no worse than a benign 95-slot DST day. Any day this thin
        # should always hard-fail, not blend into a soft warning.
        MIN_SLOTS = 90
        severely_incomplete = slots_per_day[slots_per_day < MIN_SLOTS]
        if len(severely_incomplete):
            fail(label, f"{len(severely_incomplete)} day(s) with < {MIN_SLOTS} slots "
                        f"(corrupted source file, not real data): {severely_incomplete.index.tolist()}")
        else:
            ok(label, f"no days with < {MIN_SLOTS} slots")

        # Expected: 96 slots. Allow 95/97/98 (clock-change or partial day) as warnings.
        allowed = {95, 96, 97, 98}
        bad_days = slots_per_day[~slots_per_day.isin(allowed)]
        if len(bad_days) > 10:
            fail(label, f"{len(bad_days)} day(s) with unexpected slot count (allowed: {sorted(allowed)})")
        elif len(bad_days):
            warn(label, f"{len(bad_days)} day(s) with slot count outside 96 (allowed: {sorted(allowed)})")
        else:
            ok(label, "all days have 95-98 slots")

        n_not_96 = (slots_per_day != 96).sum()
        if n_not_96:
            warn(label, f"{n_not_96} day(s) do not have exactly 96 slots")
        else:
            ok(label, "all days have exactly 96 slots")

    # Frequency range sanity check
    if "freq_hz" in df.columns:
        freq = df["freq_hz"].dropna()
        n_out = ((freq < 47) | (freq > 52)).sum()
        if n_out:
            warn(label, f"freq_hz: {n_out} value(s) outside plausible range [47, 52] Hz")
        else:
            ok(label, "freq_hz values within [47, 52] Hz")


# ── study1_hourly checks ──────────────────────────────────────────────────────

def check_study1_hourly() -> None:
    label = "study1_hourly"
    df = _load(STUDY1_H, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    _check_null_drift(df, label)
    _check_gen_share_and_fvi(df, label)

    # Datetime column
    # NOTE: previously parsed with format="mixed", dayfirst=True, which is wrong for this
    # column -- both `date` and `datetime` are uniformly ISO (YYYY-MM-DD[ HH:MM:SS]),
    # verified 2026-07-11 against all 46,728 rows, never ambiguous. dayfirst=True still
    # swapped month/day for at least one real row ("2024-04-12" -> "2024-12-04"),
    # silently reporting a wrong (and later) "latest datetime" than the data actually has.
    # Parsing with the exact known format avoids the ambiguity entirely instead of
    # guessing per-row.
    date_col = "datetime" if "datetime" in df.columns else ("date" if "date" in df.columns else None)
    if date_col:
        fmt = "%Y-%m-%d %H:%M:%S" if date_col == "datetime" else "%Y-%m-%d"
        latest = pd.to_datetime(df[date_col], format=fmt).max()
        ok(label, f"latest {date_col} = {latest.date()}")
    else:
        warn(label, "no date or datetime column found")


# ── study3_states checks ──────────────────────────────────────────────────────

def check_study3_states() -> None:
    label = "study3_states"
    df = _load(STUDY3, label)
    if df is None:
        return

    # Column count
    n_cols = len(df.columns)
    expected_cols = BASELINE_COLS[label]
    if n_cols != expected_cols:
        fail(label, f"column count changed: expected {expected_cols}, got {n_cols}")
    else:
        ok(label, f"column count = {n_cols}")

    # Row count
    n_rows = len(df)
    if n_rows < BASELINE_ROWS[label]:
        fail(label, f"row count {n_rows:,} is below baseline {BASELINE_ROWS[label]:,}")
    else:
        ok(label, f"row count = {n_rows:,}")

    _check_null_drift(df, label)

    # Duplicate (date, state) pairs
    if "date" in df.columns and "state" in df.columns:
        dupes = df.duplicated(subset=["date", "state"]).sum()
        if dupes:
            fail(label, f"{dupes} duplicate (date, state) pair(s)")
        else:
            ok(label, "no duplicate (date, state) pairs")

    # Date gaps vs. the known-gap list
    _check_date_gaps(df, label)

    # Data freshness
    if "date" in df.columns:
        latest = pd.to_datetime(df["date"]).max().date()
        lag = (date.today() - latest).days
        if lag > MAX_LAG_DAYS:
            warn(label, f"latest date is {latest} ({lag} days ago)")
        else:
            ok(label, f"latest date = {latest} ({lag} day(s) lag)")

    # Every state should resolve to a valid region -- if any are null, the
    # majority-vote resolver in parse_psp_states.py found no label anywhere
    # in the archive for that state name (see its warning output).
    if "region" in df.columns:
        n_null_region = df["region"].isna().sum()
        bad_region = df.loc[~df["region"].isin(REGIONS) & df["region"].notna(), "region"].unique()
        if n_null_region:
            fail(label, f"{n_null_region} row(s) with no resolved region")
        elif len(bad_region):
            fail(label, f"{len(bad_region)} row(s) with an invalid region value: {list(bad_region)}")
        else:
            ok(label, "all rows have a valid region")

    # States per day should be stable -- a day with far fewer states than
    # usual likely means the section C table wasn't fully parsed for that date.
    if "date" in df.columns and "state" in df.columns:
        per_day = df.groupby("date")["state"].nunique()
        typical = per_day.mode().iat[0] if not per_day.mode().empty else None
        if typical is not None:
            low_days = per_day[per_day < typical - 3]
            if len(low_days):
                warn(label, f"{len(low_days)} day(s) with fewer than {typical - 3} states (typical: {typical})")
            else:
                ok(label, f"all days have a consistent state count (typical: {typical})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Grid-Sentinel output datasets."
    )
    parser.add_argument(
        "--only",
        choices=["study1", "study2", "study3", "hourly"],
        help="Run checks for one dataset only.",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Grid-Sentinel -- validate.py")
    print(f"{'='*60}\n")

    if args.only == "study1":
        check_study1_daily()
    elif args.only == "study2":
        check_study2_scada()
    elif args.only == "study3":
        check_study3_states()
    elif args.only == "hourly":
        check_study1_hourly()
    else:
        check_study1_daily()
        print()
        check_study2_scada()
        print()
        check_study3_states()
        print()
        check_study1_hourly()

    # Summary
    n_pass = sum(1 for r in _results if r[0] == "PASS")
    n_warn = sum(1 for r in _results if r[0] == "WARN")
    n_fail = sum(1 for r in _results if r[0] == "FAIL")

    print(f"\n{'='*60}")
    print(f"  PASS: {n_pass}   WARN: {n_warn}   FAIL: {n_fail}")
    print(f"{'='*60}\n")

    if n_fail:
        print(f"  {n_fail} check(s) failed. Investigate before using the datasets.\n")
        sys.exit(1)
    elif n_warn:
        print(f"  All checks passed with {n_warn} warning(s).\n")
    else:
        print("  All checks passed.\n")


if __name__ == "__main__":
    main()
