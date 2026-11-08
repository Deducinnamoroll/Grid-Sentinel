"""
Parser for the section C "Power Supply Position in States" table of Grid-India /
POSOCO Daily PSP Reports -> Dataset/study3_states.csv (long format: one row per
state/UT/entity per day, ~40 rows per day).

Supports:
  - PDF format (2019-2022 era, pdfplumber-based, table detection)
  - XLS format (2023+ era, xlrd/pandas-based, MOP_E sheet)

Both eras render section C as a 9-column table (region, state, max demand met,
shortage during max demand, energy met, drawal schedule, OD/UD, max OD, energy
shortage) at the same column offsets, so both extraction paths share the same
7-metric COLS mapping.

Two known data-quality quirks, both handled in build_dataset() rather than
per-file, since both need visibility across the whole archive to resolve
correctly:

1. The region label (NR/WR/SR/ER/NER) is a merged cell in the source template,
   rendered on whichever row a fixed group-size calculation happens to land
   on -- this is a template artifact, not something that varies by date, so
   most states NEVER get a label anywhere in the archive (verified: only 12
   of 43 canonical entities ever had one, across 2,722 files). _resolve_regions()
   therefore uses a static STATE_TO_REGION map as the primary source, with
   cross-date majority voting as a fallback only for entities not in that map.
2. State names occasionally extract inconsistently across report eras/files
   (concatenated-text PDFs drop spaces, e.g. "TamilNadu"; some cells wrap
   across two table rows, e.g. "J&K(UT) &" / "Ladakh(UT)"; naming changed
   after the Aug 2019 J&K reorganization and Puducherry's old "Pondy"
   abbreviation). STATE_NAME_ALIASES normalizes known variants to one
   canonical name before region resolution runs, so vote counts aren't split
   across spelling variants of the same entity.

Usage:
    python parse_psp_states.py /path/to/File2_Raw/ Dataset/study3_states.csv
    python parse_psp_states.py single_file.pdf
    python parse_psp_states.py single_file.xls
"""

import re
import sys
import glob
from pathlib import Path
from datetime import datetime, date, timedelta

import pandas as pd

REGIONS = ["NR", "WR", "SR", "ER", "NER"]

COLS = ["max_demand_met_mw", "shortage_max_demand_mw", "energy_met_mu",
        "drawal_schedule_mu", "od_ud_mu", "max_od_mw", "energy_shortage_mu"]

# Same rationale as parse_psp_pdf_xls_file1/file2.py's MIN_VALID_DATE: a few
# older PDFs without a subject line have a typo'd year in their own "Date of
# Reporting" field. Rows dated before this are source typos, not real data.
MIN_VALID_DATE = date(2018, 12, 1)

# Known state-name variants -> canonical name. Built empirically by running
# the parser across the full archive (2026-07-10) and inspecting every
# variant with a low row count / inconsistent with its likely canonical form.
STATE_NAME_ALIASES = {
    # Concatenated-text PDFs (Phase 0's known space-stripping issue) drop the
    # space in multi-word state names.
    "TamilNadu": "Tamil Nadu",
    "WestBengal": "West Bengal",
    "AndhraPradesh": "Andhra Pradesh",
    "ArunachalPradesh": "Arunachal Pradesh",
    "Essarsteel": "Essar steel",
    "Arunachal": "Arunachal Pradesh",  # truncated, single occurrence

    # J&K reorganized into two UTs (J&K and Ladakh) in Aug 2019. Tracked here
    # as one continuous entity across the boundary so the time series doesn't
    # fragment -- the underlying drawal/demand data is what's being modelled,
    # not the administrative label. Also covers wrapped-cell / punctuation
    # variants of the modern name.
    "J&K": "J&K(UT) & Ladakh(UT)",
    "J&K(UT) and Ladakh(UT)": "J&K(UT) & Ladakh(UT)",
    "J&K(UT)&Ladakh(UT)": "J&K(UT) & Ladakh(UT)",
    "J&K(UT) &": "J&K(UT) & Ladakh(UT)",
    "J&K(UT) &\nLadakh(UT)": "J&K(UT) & Ladakh(UT)",

    # Puducherry was still abbreviated "Pondy" (its pre-2006-rename name,
    # Pondicherry) in some older reports.
    "Pondy": "Puducherry",

    # Wrapped-cell / casing truncation artifacts, each confirmed against a
    # single specific date's row before merging (see task notes).
    "Railways_NR": "Railways_NR ISTS",
    "Railways_ER": "Railways_ER ISTS",
    "RIL Jamnagar": "RIL JAMNAGAR",
}

# A single row where the state name itself extracted as the literal string
# "0" (2023-12-04) -- the same header-corruption pattern found and fixed in
# Phase 2's gen/outage parser, but here it corrupted the state name instead
# of a column header. The underlying numeric data looks plausible but which
# state it belongs to can't be recovered without opening that specific source
# file by hand, so it's dropped rather than guessed.
UNRECOVERABLE_STATE_LABELS = {"0"}

# Authoritative region for every canonical entity observed across the full
# archive (2026-07-10, all 2,722 successfully-parsed files, post-normalization).
#
# This is the PRIMARY source of truth for region -- not a fallback. Initial
# design used only cross-date majority voting (see _resolve_regions), on the
# assumption that the region label's row position within its group varied
# date to date. Full-archive
# results disproved that: only 12 of 43 canonical entities ever had a region
# label anywhere in 2,722 files. The label's position is apparently a fixed
# function of the report template (same group sizes every year), so it
# deterministically lands on the same handful of states every single time --
# no amount of additional data would resolve the other 31 through voting
# alone. Hence a static map, cross-checked against majority vote for any
# entity not listed here (e.g. a genuinely new one appearing in future data).
STATE_TO_REGION = {
    # NR
    "Punjab": "NR", "Haryana": "NR", "Rajasthan": "NR", "Delhi": "NR",
    "UP": "NR", "Uttarakhand": "NR", "HP": "NR",
    "J&K(UT) & Ladakh(UT)": "NR", "Chandigarh": "NR",
    "Railways_NR ISTS": "NR", "Bulk Consumer_NR ISTS": "NR",
    # WR
    "Chhattisgarh": "WR", "Gujarat": "WR", "MP": "WR", "Maharashtra": "WR",
    "Goa": "WR", "DD": "WR", "DNH": "WR", "DNHDDPDCL": "WR",
    "Essar steel": "WR", "AMNSIL": "WR", "BALCO": "WR", "RIL JAMNAGAR": "WR",
    # SR
    "Andhra Pradesh": "SR", "Telangana": "SR", "Karnataka": "SR",
    "Kerala": "SR", "Tamil Nadu": "SR", "Puducherry": "SR",
    # ER
    "Bihar": "ER", "DVC": "ER", "Jharkhand": "ER", "Odisha": "ER",
    "West Bengal": "ER", "Sikkim": "ER", "Railways_ER ISTS": "ER",
    # NER
    "Arunachal Pradesh": "NER", "Assam": "NER", "Manipur": "NER",
    "Meghalaya": "NER", "Mizoram": "NER", "Nagaland": "NER", "Tripura": "NER",
    # Bulk-consumer ISTS rows that NLDC began publishing for the other four
    # regions (first seen 2026-09-30); the suffix names the region directly.
    "Bulk Consumer_WR ISTS": "WR", "Bulk Consumer_SR ISTS": "SR",
    "Bulk Consumer_ER ISTS": "ER", "Bulk Consumer_NER ISTS": "NER",
}


def _to_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "--", "----------", "nan", "NaN"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_str(raw):
    """Try several date formats; return datetime.date or None."""
    raw = str(raw).strip()
    for fmt in ["%d-%b-%y", "%d-%b-%Y", "%d %b %y", "%d %b %Y",
                "%d/%m/%Y", "%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_regions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace the per-row 'region' column with one authoritative value per
    unique 'state' string: STATE_TO_REGION first (see its docstring for why
    this is the primary source, not a fallback), then majority vote across
    every date in the archive for anything not in that static map -- e.g. a
    genuinely new entity appearing in future NLDC reports that this map
    hasn't been updated for yet.
    """
    voted = (df.groupby("state")["region"]
               .agg(lambda s: s.dropna().mode().iat[0] if not s.dropna().mode().empty else None))

    def resolve(state):
        if state in STATE_TO_REGION:
            return STATE_TO_REGION[state]
        return voted.get(state)

    resolved = {s: resolve(s) for s in df["state"].unique()}
    unresolved = [s for s, r in resolved.items() if r is None]
    if unresolved:
        print(f"WARNING: {len(unresolved)} state(s) not in STATE_TO_REGION and never had a region "
              f"label anywhere in the archive -- add them to STATE_TO_REGION in parse_psp_states.py: {unresolved}")
    df["region"] = df["state"].map(resolved)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# ── PDF PARSER ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _pdf_extract_date(pdf):
    """Same convention as parse_psp_pdf_xls_file2.py: subject-line date first,
    'Date of Reporting' minus one day as fallback for older PDFs without one."""
    sub_re = re.compile(
        r"for\s+the\s+date\s+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})",
        re.IGNORECASE,
    )
    for page in pdf.pages[:2]:
        text = page.extract_text() or ""
        m = sub_re.search(text)
        if m:
            d = _parse_date_str(m.group(1))
            if d:
                return d
    for page in pdf.pages[:2]:
        text = page.extract_text() or ""
        m = re.search(r"date of reporting[:\s]*([\d\-\./a-zA-Z]+)", text, re.IGNORECASE)
        if m:
            d = _parse_date_str(m.group(1).strip())
            if d:
                return d - timedelta(days=1)
    return None


def _pdf_states(tables):
    """Extract per-state rows from the section C table. Returns list of dicts
    (without 'date' -- caller attaches it)."""
    for t in tables:
        if not t:
            continue
        header_idx = next(
            (i for i, r in enumerate(t)
             if len(r) > 1 and str(r[1] or "").strip().lower() == "states"),
            None,
        )
        if header_idx is None:
            continue
        rows = []
        for row in t[header_idx + 1:]:
            if len(row) < 9:
                continue
            state = str(row[1] or "").strip()
            if not state:
                continue
            region = str(row[0] or "").strip()
            region = region if region in REGIONS else None
            vals = [_to_float(row[i]) for i in range(2, 9)]
            rows.append({"region": region, "state": state, **dict(zip(COLS, vals))})
        if rows:
            return rows
    return []


def parse_pdf(filepath):
    """Parse a single PSP PDF -> list of per-state dicts (each with 'date')."""
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        date_ = _pdf_extract_date(pdf)
        if date_ is None:
            print(f"  WARNING: could not extract date from {Path(filepath).name}")
            return []

        tables = pdf.pages[1].extract_tables() if len(pdf.pages) > 1 else []
        states = _pdf_states(tables)

        if not states:
            all_tables = [t for pg in pdf.pages for t in (pg.extract_tables() or [])]
            states = _pdf_states(all_tables)

        for s in states:
            s["date"] = date_
        return states


# ═══════════════════════════════════════════════════════════════════════════════
# ── XLS PARSER ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _xls_find_date(df):
    """'Date of Reporting' is the publication date; data covers the day before."""
    for _, row in df.iterrows():
        for j, cell in enumerate(row):
            if isinstance(cell, str) and "date of reporting" in cell.lower():
                for k in range(j + 1, len(row)):
                    val = row.iloc[k]
                    if pd.isna(val):
                        continue
                    d = _parse_date_str(str(val))
                    if d:
                        return d - timedelta(days=1)
    return None


def _xls_states(df):
    """Extract per-state rows from the section C table in the MOP_E sheet."""
    section_idx = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "power supply position in states" in lbl:
            section_idx = i
            break
    if section_idx is None:
        return []

    col_row = None
    for i in range(section_idx + 1, min(section_idx + 5, len(df))):
        cell = df.iloc[i, 1] if df.shape[1] > 1 else None
        if not pd.isna(cell) and str(cell).strip().lower() == "states":
            col_row = i
            break
    if col_row is None:
        return []

    rows = []
    for i in range(col_row + 1, len(df)):
        state_cell = df.iloc[i, 1] if df.shape[1] > 1 else None
        state = str(state_cell).strip() if not pd.isna(state_cell) else ""
        if not state:
            break  # blank row marks the end of the table
        reg_cell = df.iloc[i, 0]
        region = str(reg_cell).strip() if not pd.isna(reg_cell) else ""
        region = region if region in REGIONS else None
        vals = [_to_float(df.iloc[i, c]) if c < df.shape[1] else None for c in range(2, 9)]
        rows.append({"region": region, "state": state, **dict(zip(COLS, vals))})
    return rows


def parse_xls(filepath):
    xl = pd.ExcelFile(filepath, engine="xlrd")
    if "MOP_E" not in xl.sheet_names:
        print(f"  WARNING: no MOP_E sheet in {Path(filepath).name}")
        return []
    df = pd.read_excel(filepath, sheet_name="MOP_E", engine="xlrd", header=None)
    date_ = _xls_find_date(df)
    if date_ is None:
        print(f"  WARNING: could not extract date from {Path(filepath).name}")
        return []
    states = _xls_states(df)
    for s in states:
        s["date"] = date_
    return states


# ═══════════════════════════════════════════════════════════════════════════════
# ── DISPATCHER ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def parse_file(filepath):
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(str(filepath))
    elif ext in (".xls", ".xlsx"):
        return parse_xls(str(filepath))
    return []


def build_dataset(input_path, output_csv):
    p = Path(input_path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = sorted(p.rglob("*.pdf")) + sorted(p.rglob("*.xls")) + sorted(p.rglob("*.xlsx"))
        files = sorted(files, key=lambda f: f.name)
    else:
        files = [Path(f) for f in glob.glob(input_path)]

    if not files:
        print(f"ERROR: no files found at '{input_path}'")
        return pd.DataFrame()

    print(f"Found {len(files)} file(s).")
    rows, errors = [], []

    for f in files:
        try:
            r = parse_file(f)
            if r:
                rows.extend(r)
            else:
                errors.append((f.name, "could not extract"))
        except Exception as e:
            errors.append((f.name, str(e)))

    print(f"\nProcessed {len(files)}: {len(files) - len(errors)} OK, {len(errors)} failed.")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for name, e in errors:
            print(f"  {name}: {e}")

    if not rows:
        pd.DataFrame().to_csv(output_csv, index=False)
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    bad_date_mask = df["date"] < MIN_VALID_DATE
    if bad_date_mask.any():
        bad_dates = sorted(df.loc[bad_date_mask, "date"].astype(str).unique().tolist())
        print(f"Dropped {int(bad_date_mask.sum())} row(s) with implausible date (source typo): {bad_dates}")
        df = df.loc[~bad_date_mask].reset_index(drop=True)

    unrecoverable_mask = df["state"].isin(UNRECOVERABLE_STATE_LABELS)
    if unrecoverable_mask.any():
        print(f"Dropped {int(unrecoverable_mask.sum())} row(s) with an unrecoverable state label: "
              f"{sorted(df.loc[unrecoverable_mask, 'date'].astype(str).tolist())}")
        df = df.loc[~unrecoverable_mask].reset_index(drop=True)

    df["state"] = df["state"].replace(STATE_NAME_ALIASES)

    df = _resolve_regions(df)

    # Dedup: a (date, state) pair may appear twice (PDF + XLS era overlap).
    # Keep the richest row (most non-null fields).
    dup_key = ["date", "state"]
    if df.duplicated(dup_key).any():
        n_dup = int(df.duplicated(dup_key).sum())
        df["_nonnull"] = df.notna().sum(axis=1)
        df = (df.sort_values(dup_key + ["_nonnull"])
                .drop_duplicates(dup_key, keep="last")
                .drop(columns="_nonnull"))
        print(f"Deduplicated {n_dup} duplicate (date, state) row(s).")

    col_order = ["date", "region", "state"] + COLS
    df = df[col_order].sort_values(["date", "region", "state"]).reset_index(drop=True)
    df.to_csv(output_csv, index=False)
    print(f"\nSaved {len(df)} rows -> {output_csv}")
    print(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
    return df


if __name__ == "__main__":
    if len(sys.argv) == 3:
        build_dataset(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        r = parse_file(sys.argv[1])
        if r:
            for row in r:
                print(row)
        else:
            print("Failed to parse -- see warnings above.")
    else:
        print("Usage: python parse_psp_states.py INPUT_DIR OUTPUT_CSV")
        print("   or: python parse_psp_states.py single_file.pdf")
        print("   or: python parse_psp_states.py single_file.xls")
