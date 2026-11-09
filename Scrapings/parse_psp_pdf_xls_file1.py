"""
Parser for Grid-India / POSOCO Daily PSP Reports.

Supports:
  - PDF format (2019–2022 era, pdfplumber-based)
  - XLS format (2023+ era, xlrd/pandas-based)

New features vs. original parser
─────────────────────────────────
  ① Regional IE Schedule + OD/UD    (ie_schedule_*_mu, ie_odud_*_mu)
  ② Regional outage breakdown        (outage_central_nr/wr/… _mw, outage_state_*)
  ③ Diversity factors                (diversity_regional, diversity_state)
  ④ XLS-only: CrossBorder sheet      (xb_export_*, xb_import_*, xb_net_*)
  ⑤ XLS-only: Solar / Non-Solar peak (solar_hr_peak_mw, nonsolar_hr_peak_mw, …)

CrossBorder decision (item ④):
  Kept. It distinguishes mechanism-level cross-border flows (GNA/PPA, IDAM, RTM,
  exchange-wise) that are NOT visible in the simple transnational totals. Adds
  ~12 columns starting FY2024 only; PDF rows get NaN for these.

Solar/Non-Solar peak (item ⑤):
  Kept. A single daily indicator of solar-hour vs. non-solar-hour system stress.
  Very likely to help the grid-stress classifier. Adds 4 columns from FY2024; 
  PDF rows and earlier XLS rows get NaN.

Usage:
    python parse_psp.py /path/to/folder/ output.csv
    python parse_psp.py single_file.pdf
    python parse_psp.py single_file.xls
"""

import re
import sys
import glob
from pathlib import Path
from datetime import datetime

import pandas as pd


REGIONS = ["NR", "WR", "SR", "ER", "NER"]
COUNTRIES = ["bhutan", "nepal", "bangladesh"]

# Earliest date this dataset is documented to cover (see ROADMAP.md). A few
# older PDFs (pre-2021 template, no subject line) have a typo'd year in their
# own "Date of Reporting" field -- e.g. 15.08.20_NLDC_PSP.pdf literally prints
# "15-Aug-14" -- which the parser has no way to detect from that file alone
# (no subject line to cross-check against). Rows dated before this are source
# typos, not real data, and are dropped in build_dataset() rather than shipped
# as bogus all-null rows.
MIN_VALID_DATE = datetime(2018, 12, 1).date()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _to_float(val):
    if val is None:
        return None
    try:
        import pandas as pd
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip().replace(",", "").replace("----------", "")
    if s.lower() == "nan" or s == "":
        return None
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


# ═══════════════════════════════════════════════════════════════════════════════
# ── PDF PARSERS ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _pdf_extract_date(pdf):
    """
    Extract the data date from a PSP PDF.

    Source: Subject line only -- "Sub: Daily PSP Report for the date DD.MM.YYYY"
    This directly names the date the data covers, unlike 'Date of Reporting'
    which is the next day (when the report was published).

    Falls back to 'Date of Reporting' minus one day only if the subject
    line is absent (the report's data always covers the previous day).
    """
    # ── 1. Subject line: "for the date DD.MM.YYYY" ──────────────────────────
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

    # ── 2. Fallback (older PDFs without a subject line): 'Date of Reporting'
    #       is the publication date; the data covers the PREVIOUS day (-1).
    #       Space-stripped so it also works on concatenated-text PDFs. ───────
    from datetime import timedelta
    dor_re = re.compile(
        r"dateofreporting[:\s]*([0-9]{1,2}[-./][a-z0-9]{2,4}[-./][0-9]{2,4})",
        re.IGNORECASE,
    )
    for page in pdf.pages[:2]:
        text = (page.extract_text() or "").replace(" ", "").lower()
        m = dor_re.search(text)
        if m:
            d = _parse_date_str(m.group(1))
            if d:
                return d - timedelta(days=1)

    return None


def _pdf_regional_summary(tables):
    result = {}
    target = None
    for t in tables:
        if not t or len(t) < 2:
            continue
        headers = [str(c or "").strip() for c in t[0]]
        if "NR" in headers and "WR" in headers:
            target = t
            break
    if target is None:
        return result

    headers = [str(c or "").strip() for c in target[0]]
    col_idx = {r: headers.index(r) for r in REGIONS + ["Total", "TOTAL"] if r in headers}

    for row in target[1:]:
        if not row or row[0] is None:
            continue
        # Space-stripped so matching also works on the concatenated-text PDFs
        # (some 2019-2021 reports render without spaces between words).
        label = str(row[0]).strip().lower().replace(" ", "")
        if not label:
            continue

        def get(r):
            i = col_idx.get(r)
            return _to_float(row[i]) if i is not None and i < len(row) else None

        if "eveningpeak" in label or "(at1900" in label or "(at19:00" in label:
            for r in col_idx:
                result[f"evening_peak_demand_{r.lower()}_mw"] = get(r)
        elif "peakshortage" in label:
            for r in col_idx:
                result[f"peak_shortage_{r.lower()}_mw"] = get(r)
        elif "energymet" in label and "shortage" not in label:
            for r in col_idx:
                result[f"energy_met_{r.lower()}_mu"] = get(r)
        elif "hydrogen" in label:
            for r in col_idx:
                result[f"hydro_gen_{r.lower()}_mu"] = get(r)
        elif "windgen" in label:
            for r in col_idx:
                result[f"wind_gen_{r.lower()}_mu"] = get(r)
        elif "solargen" in label:
            for r in col_idx:
                result[f"solar_gen_{r.lower()}_mu"] = get(r)
        elif "energyshortage" in label:
            for r in col_idx:
                result[f"energy_shortage_{r.lower()}_mu"] = get(r)
        elif ("maximumdemandmet" in label or "demandmetduring" in label) and \
                not label.startswith("time") and "hour" not in label:
            for r in col_idx:
                result[f"max_demand_met_{r.lower()}_mw"] = get(r)

    return result


def _pdf_frequency(tables):
    result = {}
    for t in tables:
        if not t:
            continue
        header_idx = None
        for i, row in enumerate(t):
            if any(str(c or "").strip() == "FVI" for c in row):
                header_idx = i
                break
        if header_idx is None:
            continue
        for row in t[header_idx + 1:]:
            if "allindia" in str(row[0] or "").strip().lower().replace(" ", ""):
                result["freq_fvi"]            = _to_float(row[1]) if len(row) > 1 else None
                result["freq_pct_below_497"]  = _to_float(row[2]) if len(row) > 2 else None
                result["freq_pct_497_498"]    = _to_float(row[3]) if len(row) > 3 else None
                result["freq_pct_498_499"]    = _to_float(row[4]) if len(row) > 4 else None
                result["freq_pct_below_499"]  = _to_float(row[5]) if len(row) > 5 else None
                result["freq_pct_499_5005"]   = _to_float(row[6]) if len(row) > 6 else None
                result["freq_pct_above_5005"] = _to_float(row[7]) if len(row) > 7 else None
                break
        if result:
            break
    return result


def _pdf_generation(tables):
    result = {}
    source_map = {
        "coal": "gen_coal_mu", "lignite": "gen_lignite_mu", "hydro": "gen_hydro_mu",
        "nuclear": "gen_nuclear_mu", "gas": "gen_gas_mu", "res": "gen_res_mu",
        "total": "gen_total_mu",
    }
    for t in tables:
        if not t:
            continue
        headers = [str(c or "").strip().lower() for c in t[0]]
        ai_col = next((i for i, h in enumerate(headers)
                       if "all india" in h or "all\nindia" in h or "allindia" in h.replace(" ", "")), None)
        if ai_col is None:
            continue
        row_labels = [str(r[0] or "").lower() for r in t[1:]]
        if not any("coal" in l for l in row_labels):
            continue
        for row in t[1:]:
            label = str(row[0] or "").strip().lower()
            val = _to_float(row[ai_col]) if ai_col < len(row) else None
            for key, col_name in source_map.items():
                if label.startswith(key):
                    result[col_name] = val
                    break
        if "gen_coal_mu" in result:
            break

    for t in tables:
        if not t:
            continue
        for row in t:
            label = str(row[0] or "").strip().lower().replace(" ", "")
            val = _to_float(row[-1]) if row else None
            if "shareofres" in label:
                result["share_res_pct"] = val
            elif "shareofnon" in label:
                result["share_nonfossil_pct"] = val
    return result


def _pdf_outage(tables):
    """
    Extract regional outage breakdown (Central + State rows × NR/WR/SR/ER/NER/Total).
    Also retains legacy total-only keys for backward compat.
    """
    result = {}
    for t in tables:
        if not t:
            continue
        row_labels = [str(r[0] or "").strip().lower().replace(" ", "") for r in t]
        has_central = any(l.startswith("centralsector") for l in row_labels)
        has_state   = any(l.startswith("statesector")   for l in row_labels)
        if not (has_central and has_state):
            continue

        headers = [str(c or "").strip() for c in t[0]]
        # Build region column map
        reg_cols = {}
        for r in REGIONS + ["Total", "TOTAL"]:
            if r in headers:
                reg_cols[r] = headers.index(r)

        for row in t:
            label = str(row[0] or "").strip().lower().replace(" ", "")
            if label.startswith("centralsector"):
                prefix = "outage_central"
            elif label.startswith("statesector"):
                prefix = "outage_state"
            elif label == "total":
                prefix = "outage_total"
            else:
                continue
            for r, i in reg_cols.items():
                col_key = r.lower() if r not in ("Total", "TOTAL") else "total"
                result[f"{prefix}_{col_key}_mw"] = _to_float(row[i]) if i < len(row) else None

        if result:
            break
    return result


def _pdf_regional_ie(tables):
    """
    Extract Schedule, Actual, OD/UD rows from the regional IE section.
    """
    result = {}
    for t in tables:
        if not t:
            continue
        headers = [str(c or "").strip() for c in t[0]]
        if "NR" not in headers or "WR" not in headers:
            continue
        col_idx = {r: headers.index(r) for r in REGIONS + ["TOTAL", "Total"] if r in headers}

        for row in t[1:]:
            label = str(row[0] or "").strip().lower()
            if "schedule" in label:
                prefix = "ie_schedule"
            elif "actual" in label:
                prefix = "ie_actual"
            elif "o/d" in label or "od" in label:
                prefix = "ie_odud"
            else:
                continue
            for r, i in col_idx.items():
                col_key = r.lower() if r not in ("TOTAL", "Total") else "total"
                result[f"{prefix}_{col_key}_mu"] = _to_float(row[i]) if i < len(row) else None

        if any(k.startswith("ie_") for k in result):
            break
    return result


def _pdf_transnational(tables):
    result = {}
    for t in tables:
        if not t:
            continue
        headers_lower = [str(c or "").strip().lower() for c in t[0]]
        if "bhutan" not in headers_lower:
            continue
        for row in t[1:]:
            label = str(row[0] or "").strip().lower()
            if "actual" in label:
                for country in COUNTRIES:
                    try:
                        i = headers_lower.index(country)
                        result[f"trans_{country}_mu"] = _to_float(row[i])
                    except (ValueError, IndexError):
                        pass
                break
        if result:
            break
    return result


def _pdf_diversity(tables):
    """Extract the two diversity factor rows (Regional + State)."""
    result = {}
    for t in tables:
        if not t:
            continue
        for row in t:
            label = str(row[0] or "").strip().lower().replace(" ", "")
            # Diversity factors are often in a single-column-ish table
            # Look for the numeric value in col 1 or the last non-None cell
            vals = [_to_float(c) for c in row if _to_float(c) is not None]
            if not vals:
                continue
            val = vals[0]
            if "regional" in label and "diversity" not in label and val is None:
                continue
            if "basedonregional" in label:
                result["diversity_regional"] = val
            elif "basedonstate" in label:
                result["diversity_state"] = val
            elif "allindiademanddiversityfactor" in label and val is not None:
                # Older format (pre-2020) has a single combined factor only;
                # per the report's own formula it is the regional-based one.
                result.setdefault("diversity_regional", val)
        if result:
            break
    return result


def _pdf_gen_outage_text_fallback(pdf):
    """
    Last-resort fallback for Section F (Generation Outage) / Section G
    (Sourcewise generation) when pdfplumber's extract_tables() misses them
    entirely -- observed on 2021-era PDFs where these sections render with
    no visible gridlines, so no table is detected at all, even though
    extract_text() still returns the section as normal whitespace-delimited
    rows. Also recovers cases where a table IS detected but the "All India"
    header cell renders as a stray non-text value such as "0" (observed on
    some 2019 PDFs -- e.g. 29/30.03.19), since this works from extract_text()
    directly, bypassing table detection's column-header matching altogether.

    Row labels vary in whether they retain internal spaces across report eras
    (e.g. "Gas, Naptha & Diesel" vs "Gas,Naptha&Diesel"), so labels are matched
    by stripping everything but letters; data columns are matched positionally
    from the numbers found on the line, since a trailing %Share column is
    present in some report eras and absent in others.
    """
    result = {}
    full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    lines = full_text.split("\n")

    def _letters_only(s):
        return re.sub(r"[^a-z]", "", s.lower())

    outage_map = {"centralsector": "outage_central", "statesector": "outage_state", "total": "outage_total"}
    gen_map = {
        "coal": "gen_coal_mu", "lignite": "gen_lignite_mu", "hydro": "gen_hydro_mu",
        "nuclear": "gen_nuclear_mu", "gas": "gen_gas_mu", "res": "gen_res_mu",
        "total": "gen_total_mu",
    }

    f_idx = next((i for i, l in enumerate(lines) if _letters_only(l).startswith("fgenerationoutage")), None)
    if f_idx is not None:
        for line in lines[f_idx + 1: f_idx + 6]:
            label = _letters_only(line)
            prefix = next((v for k, v in outage_map.items() if label.startswith(k)), None)
            if prefix is None:
                continue
            nums = re.findall(r"-?\d+\.?\d*", line)
            if len(nums) < 6:
                continue
            for region, val in zip(REGIONS + ["total"], nums[:6]):
                key = region.lower() if region != "total" else "total"
                result.setdefault(f"{prefix}_{key}_mw", float(val))

    g_idx = next((i for i, l in enumerate(lines) if _letters_only(l).startswith("gsourcewisegeneration")), None)
    if g_idx is not None:
        for line in lines[g_idx + 1: g_idx + 9]:
            label = _letters_only(line)
            col_name = next((v for k, v in gen_map.items() if label.startswith(k)), None)
            if col_name is None:
                continue
            nums = re.findall(r"-?\d+\.?\d*", line)
            if len(nums) < 6:
                continue
            result.setdefault(col_name, float(nums[5]))

    return result


def parse_pdf(filepath):
    """Parse a single PSP PDF -> dict of daily features."""
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        date = _pdf_extract_date(pdf)
        if date is None:
            print(f"  WARNING: could not extract date from {Path(filepath).name}")
            return None

        tables = pdf.pages[1].extract_tables() if len(pdf.pages) > 1 else []

        row = {"date": date}
        _section_parsers = (_pdf_regional_summary, _pdf_frequency, _pdf_generation,
                            _pdf_outage, _pdf_regional_ie, _pdf_transnational,
                            _pdf_diversity)
        for _fn in _section_parsers:
            row.update(_fn(tables))

        # Fallback: PDF layouts vary -- a given section (A, frequency,
        # generation, outage, diversity ...) may sit on a page other than
        # page[1], or render without spaces. If ANY major block came back
        # empty, re-scan ALL pages and fill only the still-missing keys.
        # This pass never overwrites a value already parsed from page[1].
        if any(row.get(k) is None for k in (
                "evening_peak_demand_total_mw", "max_demand_met_total_mw",
                "freq_fvi", "gen_coal_mu", "diversity_regional",
                "outage_total_total_mw")):
            all_tables = [t for pg in pdf.pages for t in (pg.extract_tables() or [])]
            for _fn in _section_parsers:
                for _k, _v in _fn(all_tables).items():
                    if row.get(_k) is None:
                        row[_k] = _v

        # Text-based last resort: some PDFs never produce a detected table for
        # Section F/G at all (2021-era, no visible gridlines), or produce one
        # with a corrupted "All India" header cell (some 2019-era files) --
        # both bypass the table-based parsers above entirely.
        if row.get("gen_coal_mu") is None or row.get("outage_total_total_mw") is None:
            for _k, _v in _pdf_gen_outage_text_fallback(pdf).items():
                if row.get(_k) is None:
                    row[_k] = _v

    return row


# ═══════════════════════════════════════════════════════════════════════════════
# ── XLS PARSERS ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _xls_read_sheet(filepath, sheet):
    return pd.read_excel(filepath, sheet_name=sheet, engine="xlrd", header=None)


def _xls_find_date(df):
    """
    Scan for 'Date of Reporting' and return the data date (previous day).
    'Date of Reporting' is the publication date; the data covers the day before.
    """
    from datetime import timedelta
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


def _xls_col_map(df, row_idx):
    """
    Given a header row index, return {label_str: col_idx} for REGIONS + TOTAL/All India.
    """
    col_map = {}
    for j, cell in enumerate(df.iloc[row_idx]):
        s = str(cell).strip() if not pd.isna(cell) else ""
        if s in REGIONS or s in ("TOTAL", "Total", "All India", "All\nIndia"):
            col_map[s] = j
    return col_map


def _xls_parse_mop_e(df):
    """
    Parse the MOP_E sheet of an XLS file.
    Mirrors all the PDF section parsers but works on the flat DataFrame.
    Returns a dict of features.
    """
    result = {}
    nrows = len(df)

    # ── helper ──────────────────────────────────────────────────────────────
    def cell(r, c):
        return df.iloc[r, c] if r < nrows and c < df.shape[1] else None

    def fval(r, c):
        return _to_float(cell(r, c))

    # ── locate key structural rows ──────────────────────────────────────────
    # We scan col 0 for known labels (case-insensitive)
    label_rows = {}   # label_key -> row_index
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if lbl:
            label_rows[lbl] = i

    def find_row(substring):
        for lbl, idx in label_rows.items():
            if substring in lbl:
                return idx
        return None

    # ── Section A: regional summary ─────────────────────────────────────────
    # Header row has NR/WR/SR/ER/NER/TOTAL in it; find it
    header_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row if not pd.isna(v)]
        if "NR" in vals and "WR" in vals and "SR" in vals:
            header_row = i
            break

    if header_row is not None:
        col_map = _xls_col_map(df, header_row)

        def get_region(row_idx, r):
            j = col_map.get(r) or col_map.get("TOTAL") if r in ("TOTAL", "Total") else col_map.get(r)
            return fval(row_idx, j) if j is not None else None

        for i in range(header_row + 1, min(header_row + 20, nrows)):
            lbl = str(df.iloc[i, 0]).strip().lower() if not pd.isna(df.iloc[i, 0]) else ""
            if not lbl:
                continue

            def gr(r):
                j = col_map.get(r)
                return fval(i, j) if j is not None else None

            # Shortage first: since 2026-08-05 NLDC labels it "Shoratge (MW) during Evening
            # Peak hr" (sic), which also contains "evening peak". Checked second, it was
            # written into evening_peak_demand_* and peak_shortage_* stayed empty.
            is_shortage = "shortage" in lbl or "shoratge" in lbl
            if is_shortage and "peak" in lbl:
                for r in list(col_map):
                    result[f"peak_shortage_{r.lower()}_mw"] = gr(r)
            elif "evening peak" in lbl or "(at 19:00" in lbl or "(at 1900" in lbl:
                for r in list(col_map):
                    result[f"evening_peak_demand_{r.lower()}_mw"] = gr(r)
            elif "energy met" in lbl and "shortage" not in lbl:
                for r in list(col_map):
                    result[f"energy_met_{r.lower()}_mu"] = gr(r)
            elif "hydro gen" in lbl:
                for r in list(col_map):
                    result[f"hydro_gen_{r.lower()}_mu"] = gr(r)
            elif "wind gen" in lbl:
                for r in list(col_map):
                    result[f"wind_gen_{r.lower()}_mu"] = gr(r)
            elif "solar gen" in lbl:
                for r in list(col_map):
                    result[f"solar_gen_{r.lower()}_mu"] = gr(r)
            elif "energy shortage" in lbl:
                for r in list(col_map):
                    result[f"energy_shortage_{r.lower()}_mu"] = gr(r)
            elif ("maximum demand met" in lbl or "demand met during" in lbl) and \
                    not lbl.lstrip().startswith("time") and "hour" not in lbl:
                for r in list(col_map):
                    result[f"max_demand_met_{r.lower()}_mw"] = gr(r)

    # ── Section B: frequency ─────────────────────────────────────────────────
    freq_header = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row if not pd.isna(v)]
        if "FVI" in vals:
            freq_header = i
            break
    if freq_header is not None:
        for i in range(freq_header + 1, min(freq_header + 5, nrows)):
            lbl = str(df.iloc[i, 0]).strip().lower() if not pd.isna(df.iloc[i, 0]) else ""
            if "all india" in lbl:
                row = df.iloc[i]
                result["freq_fvi"]            = _to_float(row.iloc[1]) if len(row) > 1 else None
                result["freq_pct_below_497"]  = _to_float(row.iloc[2]) if len(row) > 2 else None
                result["freq_pct_497_498"]    = _to_float(row.iloc[3]) if len(row) > 3 else None
                result["freq_pct_498_499"]    = _to_float(row.iloc[4]) if len(row) > 4 else None
                result["freq_pct_below_499"]  = _to_float(row.iloc[5]) if len(row) > 5 else None
                result["freq_pct_499_5005"]   = _to_float(row.iloc[6]) if len(row) > 6 else None
                result["freq_pct_above_5005"] = _to_float(row.iloc[7]) if len(row) > 7 else None
                break

    # ── Section D: transnational ─────────────────────────────────────────────
    for i, row in df.iterrows():
        vals_lower = [str(v).strip().lower() for v in row if not pd.isna(v)]
        if "bhutan" in vals_lower:
            # This is the header row; actual row is below
            bhutan_col  = next((j for j, v in enumerate(row) if str(v).strip().lower() == "bhutan"), None)
            nepal_col   = next((j for j, v in enumerate(row) if str(v).strip().lower() == "nepal"), None)
            bd_col      = next((j for j, v in enumerate(row) if "bangladesh" in str(v).strip().lower()), None)
            godda_col   = next((j for j, v in enumerate(row) if "godda" in str(v).strip().lower()), None)
            # scan next rows for "actual"
            for k in range(i + 1, min(i + 5, nrows)):
                lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                if "actual" in lbl:
                    result["trans_bhutan_mu"]     = fval(k, bhutan_col) if bhutan_col else None
                    result["trans_nepal_mu"]       = fval(k, nepal_col) if nepal_col else None
                    result["trans_bangladesh_mu"]  = fval(k, bd_col) if bd_col else None
                    # Godda -> Bangladesh (new in 2024)
                    if godda_col:
                        result["trans_godda_bangladesh_mu"] = fval(k, godda_col)
                    break
            break

    # ── Section E: regional import/export ───────────────────────────────────
    ie_header = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "import/export by regions" in lbl or "e. import/export" in lbl:
            ie_header = i
            break

    if ie_header is not None:
        # Find the NR/WR/… header row right below
        for i in range(ie_header + 1, min(ie_header + 4, nrows)):
            vals = [str(v).strip() for v in df.iloc[i] if not pd.isna(v)]
            if "NR" in vals and "WR" in vals:
                ie_col_map = _xls_col_map(df, i)
                # Scan the next ~6 rows for Schedule/Actual/OD
                for k in range(i + 1, min(i + 7, nrows)):
                    lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                    if "schedule" in lbl:
                        prefix = "ie_schedule"
                    elif "actual" in lbl:
                        prefix = "ie_actual"
                    elif "o/d" in lbl or "od" in lbl:
                        prefix = "ie_odud"
                    else:
                        continue
                    for r, j in ie_col_map.items():
                        col_key = r.lower() if r not in ("TOTAL", "Total") else "total"
                        result[f"{prefix}_{col_key}_mu"] = fval(k, j)
                break

    # ── Section F: generation outage ─────────────────────────────────────────
    out_header = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "generation outage" in lbl:
            out_header = i
            break

    if out_header is not None:
        for i in range(out_header + 1, min(out_header + 4, nrows)):
            vals = [str(v).strip() for v in df.iloc[i] if not pd.isna(v)]
            if "NR" in vals and "WR" in vals:
                out_col_map = _xls_col_map(df, i)
                for k in range(i + 1, min(i + 6, nrows)):
                    lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                    if "central sector" in lbl:
                        prefix = "outage_central"
                    elif "state sector" in lbl:
                        prefix = "outage_state"
                    elif lbl == "total":
                        prefix = "outage_total"
                    else:
                        continue
                    for r, j in out_col_map.items():
                        col_key = r.lower() if r not in ("TOTAL", "Total") else "total"
                        result[f"{prefix}_{col_key}_mw"] = fval(k, j)
                break

    # ── Section G: sourcewise generation ─────────────────────────────────────
    gen_header = None
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "sourcewise generation" in lbl:
            gen_header = i
            break

    if gen_header is not None:
        for i in range(gen_header + 1, min(gen_header + 4, nrows)):
            vals = [str(v).strip() for v in df.iloc[i] if not pd.isna(v)]
            if "NR" in vals and "All India" in vals:
                gen_col_map = _xls_col_map(df, i)
                ai_col = gen_col_map.get("All India")
                if ai_col is None:
                    break
                source_map = {
                    "coal": "gen_coal_mu", "lignite": "gen_lignite_mu",
                    "hydro": "gen_hydro_mu", "nuclear": "gen_nuclear_mu",
                    "gas": "gen_gas_mu", "res": "gen_res_mu", "total": "gen_total_mu",
                }
                for k in range(i + 1, min(i + 10, nrows)):
                    lbl = str(df.iloc[k, 0]).strip().lower() if not pd.isna(df.iloc[k, 0]) else ""
                    val = fval(k, ai_col)
                    for key, col_name in source_map.items():
                        if lbl.startswith(key):
                            result[col_name] = val
                            break
                break

    # Share rows -- All India value is the last non-NaN numeric in the row
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "share of res" in lbl:
            vals = [_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None]
            result["share_res_pct"] = vals[-1] if vals else None
        elif "share of non" in lbl:
            vals = [_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None]
            result["share_nonfossil_pct"] = vals[-1] if vals else None

    # ── Section H: diversity factors ─────────────────────────────────────────
    for i, row in df.iterrows():
        lbl = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
        if "based on regional" in lbl:
            # value sits in col 2 in XLS (col 1 is NaN)
            val = next((_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None), None)
            result["diversity_regional"] = val
        elif "based on state" in lbl:
            val = next((_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None), None)
            result["diversity_state"] = val
        elif "all india demand diversity factor" in lbl:
            # Older single-factor layout: map combined value to regional.
            val = next((_to_float(v) for v in row.iloc[1:] if _to_float(v) is not None), None)
            if val is not None:
                result.setdefault("diversity_regional", val)

    # ── Section I (2024+): solar / non-solar peak ────────────────────────────
    # Structure: row with "Solar hr" in col 4, max-demand in col 5, shortage in col 8
    for i, row in df.iterrows():
        for j, cell in enumerate(row):
            lbl = str(cell).strip().lower() if not pd.isna(cell) else ""
            if lbl == "solar hr":
                result["solar_hr_peak_mw"]     = _to_float(row.iloc[j + 1]) if j + 1 < len(row) else None
                result["solar_hr_shortage_mw"] = _to_float(row.iloc[j + 4]) if j + 4 < len(row) else None
            elif lbl == "non-solar hr":
                result["nonsolar_hr_peak_mw"]     = _to_float(row.iloc[j + 1]) if j + 1 < len(row) else None
                result["nonsolar_hr_shortage_mw"] = _to_float(row.iloc[j + 4]) if j + 4 < len(row) else None

    return result


def _xls_parse_crossborder(df):
    """
    Parse the CrossBorder sheet (present from FY2024 onwards).
    Extracts total export/import/net per country from the TOTAL column (col 12).
    Returns dict with keys: xb_export_*, xb_import_*, xb_net_*
    """
    result = {}
    country_map = {
        "bhutan": "bhutan", "nepal": "nepal",
        "bangladesh": "bangladesh", "myanmar": "myanmar",
    }

    # TOTAL is the last column in the CrossBorder sheet (col 12)
    total_col = df.shape[1] - 1

    # Identify section blocks
    sections = {}
    for i, row in df.iterrows():
        lbl = " ".join(str(v).lower() for v in row if not pd.isna(v))
        if "export from india" in lbl:
            sections["export"] = i
        elif "import by india" in lbl:
            sections["import"] = i
        elif "net from india" in lbl:
            sections["net"] = i

    # Bound each section's scan window so it stops before the NEXT section
    # starts. Without this, a country row from a later section (e.g. Import)
    # gets picked up while still scanning the earlier section (e.g. Export),
    # silently overwriting the correct value.
    starts_sorted = sorted(sections.values())
    section_end = {}
    for name, start in sections.items():
        later_starts = [s for s in starts_sorted if s > start]
        section_end[name] = min(later_starts) if later_starts else len(df)

    for section_name, section_start in sections.items():
        end = section_end[section_name]
        for i in range(section_start, end):
            row_label = str(df.iloc[i, 0]).strip().lower() if not pd.isna(df.iloc[i, 0]) else ""
            for country_key, country_name in country_map.items():
                if row_label == country_key:
                    result[f"xb_{section_name}_{country_name}_mu"] = _to_float(df.iloc[i, total_col])
    return result


def _xls_parse_ir_line(df):
    """
    Parse the IR-Line sheet -- inter-regional exchange aggregated to region pairs.

    Reads the pre-summed subtotal rows the sheet provides (cols: 0=pair label,
    6=import MU, 7=export MU, 9=net MU). Present from FY2023 onwards.
    Emits ir_<pair>_import_mu / _export_mu / _net_mu  (e.g. ir_er_nr_import_mu).
    """
    PAIR_LABELS = {"ER-NR", "ER-WR", "ER-SR", "ER-NER", "NER-NR", "WR-NR", "WR-SR"}
    result = {}
    for _, row in df.iterrows():
        label = str(row.iloc[0]).strip()
        if label not in PAIR_LABELS:
            continue
        key = label.replace("-", "_").lower()
        result[f"ir_{key}_import_mu"] = _to_float(row.iloc[6]) if len(row) > 6 else None
        result[f"ir_{key}_export_mu"] = _to_float(row.iloc[7]) if len(row) > 7 else None
        result[f"ir_{key}_net_mu"]    = _to_float(row.iloc[9]) if len(row) > 9 else None
    return result


def parse_xls(filepath):
    """Parse a single PSP XLS file -> dict of daily features."""
    xl = pd.ExcelFile(filepath, engine="xlrd")
    sheets = xl.sheet_names

    row = {}

    # MOP_E sheet (always present)
    if "MOP_E" in sheets:
        df_mop = _xls_read_sheet(filepath, "MOP_E")
        date = _xls_find_date(df_mop)
        if date is None:
            print(f"  WARNING: could not extract date from {Path(filepath).name}")
            return None
        row["date"] = date
        row.update(_xls_parse_mop_e(df_mop))
    else:
        print(f"  WARNING: no MOP_E sheet in {Path(filepath).name}")
        return None

    # CrossBorder sheet (FY2024+, optional)
    if "CrossBorder" in sheets:
        df_cb = _xls_read_sheet(filepath, "CrossBorder")
        row.update(_xls_parse_crossborder(df_cb))

    # IR-Line sheet (inter-regional corridor flows; FY2023+, optional)
    if "IR-Line" in sheets:
        df_ir = _xls_read_sheet(filepath, "IR-Line")
        row.update(_xls_parse_ir_line(df_ir))

    return row


# ═══════════════════════════════════════════════════════════════════════════════
# ── SOURCE-ERROR RECONCILIATION ───────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# NLDC's own reports sometimes print a "Share of RES" / "Share of Non-fossil" row
# that disagrees with the sourcewise generation table right above it (stale share
# rows in the 2022 PDFs; formula cells with outdated cached values in the XLS era,
# e.g. 12.03.24 prints 96.76% RES). The gen rows sum to their Total on those days,
# so the share is recomputed from them when the printed value is off by more than
# SHARE_TOL_PP. Verified 2026-11-08 against the raw files, see
# Pipeline/docs/parse_psp_pdf_xls_notes.md.
SHARE_TOL_PP = 1.0

# FVI (frequency variation index) is a small dimensionless number (all other days
# 2018-2026 are below 0.43). 02.03.2021 prints 49.215 in the FVI cell, a frequency
# in Hz typed into the wrong column. Anything outside [0, FVI_MAX] cannot be an FVI
# and is nulled rather than shipped. Pipeline/validate.py enforces the same bound.
FVI_MAX = 5.0


def _reconcile_daily(row):
    """Fix known source-side inconsistencies in a parsed daily row, in place."""
    if not row:
        return row
    tag = row.get("date", "?")

    def num(key):
        v = row.get(key)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return None if v != v else v

    total = num("gen_total_mu")
    if total and total > 0:
        res, hyd, nuc = num("gen_res_mu"), num("gen_hydro_mu"), num("gen_nuclear_mu")
        targets = []
        if res is not None:
            targets.append(("share_res_pct", res / total * 100))
            if hyd is not None and nuc is not None:
                targets.append(("share_nonfossil_pct", (hyd + nuc + res) / total * 100))
        for key, calc in targets:
            printed = num(key)
            if printed is None or abs(printed - calc) > SHARE_TOL_PP:
                row[key] = round(calc, 2)
                if printed is not None:
                    print(f"  {tag}: {key} {printed} disagrees with gen table, "
                          f"recomputed {round(calc, 2)}")

    fvi = num("freq_fvi")
    if fvi is not None and not (0 <= fvi <= FVI_MAX):
        print(f"  {tag}: freq_fvi {fvi} outside [0, {FVI_MAX}], nulled (source typo)")
        row["freq_fvi"] = None
    return row


# ═══════════════════════════════════════════════════════════════════════════════
# ── DISPATCHER ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def parse_file(filepath):
    """Dispatch to PDF or XLS parser based on extension."""
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return _reconcile_daily(parse_pdf(str(filepath)))
    elif ext in (".xls", ".xlsx"):
        return _reconcile_daily(parse_xls(str(filepath)))
    else:
        print(f"  WARNING: unsupported extension '{ext}' -- {Path(filepath).name}")
        return None


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
                rows.append(r)
            else:
                errors.append((f.name, "could not extract"))
        except Exception as e:
            errors.append((f.name, str(e)))

    print(f"\nProcessed {len(files)}: {len(rows)} OK, {len(errors)} failed.")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for name, e in errors:
            print(f"  {name}: {e}")

    if not rows:
        pd.DataFrame().to_csv(output_csv, index=False)
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Drop rows with an implausibly early date -- these are source-level
    # typos in the raw PDF's own date field (see MIN_VALID_DATE), not real
    # data. Only affects PDFs old enough to lack a subject line to cross-check.
    if "date" in df.columns:
        bad_date_mask = df["date"] < MIN_VALID_DATE
        if bad_date_mask.any():
            bad_dates = sorted(df.loc[bad_date_mask, "date"].astype(str).tolist())
            print(f"Dropped {bad_date_mask.sum()} row(s) with implausible date (source typo): {bad_dates}")
            df = df.loc[~bad_date_mask].reset_index(drop=True)

    # Dedup: a date may appear twice (PDF + XLS for the same day, or era
    # overlap). Keep the richest row (most non-null fields).
    if "date" in df.columns and df["date"].duplicated().any():
        n_dup = int(df["date"].duplicated().sum())
        df["_nonnull"] = df.notna().sum(axis=1)
        df = (df.sort_values(["date", "_nonnull"])
                .drop_duplicates("date", keep="last")
                .drop(columns="_nonnull"))
        print(f"Deduplicated {n_dup} duplicate-date row(s).")
    df = df.sort_values("date").reset_index(drop=True)
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
            for k, v in r.items():
                print(f"{k}: {v}")
        else:
            print("Failed to parse -- see warnings above.")
    else:
        print("Usage: python parse_psp.py INPUT_DIR OUTPUT_CSV")
        print("   or: python parse_psp.py single_file.pdf")
        print("   or: python parse_psp.py single_file.xls")
