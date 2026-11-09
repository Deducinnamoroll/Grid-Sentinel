"""
build_data_dict.py -- Generate the Grid-Sentinel data dictionary.

Reads column names from the four output CSVs and writes
Dataset/data_dictionary.xlsx. The workbook has five sheets:

    study1_daily    -- 144 columns from File2_Raw parsings
    study2_scada    -- 164 columns from File3_Raw parsings (15-min slot level)
    study1_hourly   -- 151 columns (study1_daily PSP cols joined onto hourly load)
    study3_states   -- 10 columns, section C state-level power supply position (long format)
    master          -- Union of all unique column names across the four datasets

Each sheet has the columns:
    column_name, datasets, unit, source_section, schema_start_date, notes

Requires: pandas, openpyxl

Usage:
    python Pipeline/build_data_dict.py
    python Pipeline/build_data_dict.py --output path/to/custom.xlsx
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import study2_io  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "Dataset"

STUDY1_D = DATASET_DIR / "study1_daily.csv"
STUDY1_H = DATASET_DIR / "study1_hourly.csv"
STUDY2   = DATASET_DIR / "study2_scada.csv"
STUDY3   = DATASET_DIR / "study3_states.csv"
OUT_XLSX = DATASET_DIR / "data_dictionary.xlsx"

# ── Region/country abbreviation maps (for generated descriptions) ─────────────
REGIONS = {
    "nr": "Northern Region",
    "wr": "Western Region",
    "sr": "Southern Region",
    "er": "Eastern Region",
    "ner": "North-Eastern Region",
    "total": "All-India total",
}

XB_COUNTRIES = {
    "bhutan":     "Bhutan",
    "nepal":      "Nepal",
    "bangladesh": "Bangladesh",
    "myanmar":    "Myanmar",
}

# (first-named region, second region). NLDC's IR-Line sheet groups lines under
# "Import/Export of <A> (With <B>)" and reports import, export and net from A's
# side ("Import=(+ve) /Export =(-ve) for NET"), so a negative net means A sent
# energy to B. Verified 2026-11-08 against 13.03.24's IR-Line sheet and the data
# (ir_er_nr_net_mu is negative on 97% of days: ER exports to NR).
IR_CORRIDORS = {
    "ir_er_nr":  ("ER", "NR"),
    "ir_er_wr":  ("ER", "WR"),
    "ir_er_sr":  ("ER", "SR"),
    "ir_er_ner": ("ER", "NER"),
    "ir_ner_nr": ("NER", "NR"),
    "ir_wr_nr":  ("WR", "NR"),
    "ir_wr_sr":  ("WR", "SR"),
}

# ── Schema start dates ────────────────────────────────────────────────────────
# These are approximate. Columns exist from the first PSP file that contains
# the relevant section. Earlier files leave these columns null.
DATE_FULL       = "2018-12-31"   # first PSP in File2_Raw
DATE_IR_XB      = "2023-04-01"   # IR-Line and restructured XB sections (~FY2023-24)
DATE_SOLAR_HR   = "2023-04-01"   # solar/nonsolar peak-hour section
DATE_GODDA      = "2023-04-01"   # Adani Godda plant export to Bangladesh
DATE_SCADA      = "2024-11-04"   # first date in study2_scada
DATE_HOURLY     = "2019-01-01"   # first date in Kaggle hourly load file
DATE_STATES     = "2018-12-31"   # first date in study3_states

# ── Section labels from PSP report ────────────────────────────────────────────
SEC_A    = "Section A (National Overview)"
SEC_B    = "Section B (Inter-Regional)"
SEC_IR   = "IR-Line table (Section B appendix)"
SEC_XB   = "Cross-border table (Section B appendix)"
SEC_SCADA = "TimeSeries sheet (SCADA)"
SEC_KAGGLE = "Kaggle India Hourly Load dataset"
SEC_STATES = "Section C (Power Supply Position in States)"
SEC_ID   = "Identifier"

# ── Master knowledge table ────────────────────────────────────────────────────
# Each entry: column_name -> (unit, source_section, schema_start_date, notes)
# Entries not listed here get placeholders filled in by _infer().

KNOWN: dict[str, tuple[str, str, str, str]] = {}


def _add(col: str, unit: str, section: str, start: str, notes: str = "") -> None:
    KNOWN[col] = (unit, section, start, notes)


# Identifiers
_add("date",     "date (YYYY-MM-DD)", SEC_ID, DATE_FULL,
     "PSP report date. For XLS files this is the 'Date of Reporting' minus one day. "
     "For PDF files this is extracted from the subject line.")
_add("datetime", "datetime",          SEC_ID, DATE_HOURLY,
     "Full datetime string from the Kaggle hourly load file (study1_hourly only).")
_add("time",     "HH:MM",             SEC_ID, DATE_SCADA,
     "Time label for the 15-minute slot (study2_scada only). String, e.g. '00:00'.")
_add("hhmm",     "integer (HHMM)",    SEC_ID, DATE_SCADA,
     "Numeric time identifier for the slot: 0 = 00:00, 100 = 01:00, 1545 = 15:45 "
     "(study2_scada only). Useful for sorting and grouping.")

# Evening peak demand by region
for r, rname in REGIONS.items():
    _add(f"evening_peak_demand_{r}_mw", "MW", SEC_A, DATE_FULL,
         f"Evening peak demand met in {rname}.")

# Peak shortage by region
for r, rname in REGIONS.items():
    _add(f"peak_shortage_{r}_mw", "MW", SEC_A, DATE_FULL,
         f"Peak demand shortage in {rname}. Zero indicates no shortage.")

# Energy met by region
for r, rname in REGIONS.items():
    _add(f"energy_met_{r}_mu", "MU", SEC_A, DATE_FULL,
         f"Energy met (consumed) in {rname} over the reporting day.")

# Regional generation by source
for r, rname in REGIONS.items():
    _add(f"hydro_gen_{r}_mu",  "MU", SEC_A, DATE_FULL, f"Hydro generation in {rname}.")
    _add(f"wind_gen_{r}_mu",   "MU", SEC_A, DATE_FULL, f"Wind generation in {rname}.")
    _add(f"solar_gen_{r}_mu",  "MU", SEC_A, DATE_FULL, f"Solar generation in {rname}.")

# Energy shortage by region
for r, rname in REGIONS.items():
    _add(f"energy_shortage_{r}_mu", "MU", SEC_A, DATE_FULL,
         f"Energy shortage in {rname}. Positive values indicate unmet demand.")

# Max demand met by region
for r, rname in REGIONS.items():
    _add(f"max_demand_met_{r}_mw", "MW", SEC_A, DATE_FULL,
         f"Maximum demand met in {rname} during the day.")

# Time of max demand met (study2_scada only)
for r, rname in REGIONS.items():
    _add(f"time_max_demand_met_{r}", "HH:MM", SEC_SCADA, DATE_SCADA,
         f"Time at which maximum demand was met in {rname} (study2_scada only).")

# Frequency statistics
_add("freq_fvi",           "index", SEC_B, DATE_FULL,
     "Frequency Variation Index as printed by NLDC: a small dimensionless index of "
     "how far frequency strayed from 50 Hz over the day (0 = held at 50 Hz). Not a "
     "percentage; real days 2018-2026 range 0.01 to 0.43. Values outside [0, 5] are "
     "source typos and are nulled by the parser (2021-03-02 printed 49.215, a Hz value).")
_add("freq_pct_below_497", "%",    SEC_B, DATE_FULL,
     "Percentage of the day with frequency below 49.7 Hz.")
_add("freq_pct_497_498",   "%",    SEC_B, DATE_FULL,
     "Percentage of the day with frequency in the range [49.7, 49.8) Hz.")
_add("freq_pct_498_499",   "%",    SEC_B, DATE_FULL,
     "Percentage of the day with frequency in the range [49.8, 49.9) Hz.")
_add("freq_pct_below_499", "%",    SEC_B, DATE_FULL,
     "Cumulative percentage of the day with frequency below 49.9 Hz.")
_add("freq_pct_499_5005",  "%",    SEC_B, DATE_FULL,
     "Percentage of the day with frequency in the normal band [49.9, 50.05] Hz.")
_add("freq_pct_above_5005","%",    SEC_B, DATE_FULL,
     "Percentage of the day with frequency above 50.05 Hz.")

# Instantaneous frequency (study2_scada only)
_add("freq_hz", "Hz", SEC_SCADA, DATE_SCADA,
     "System frequency for the 15-minute slot (study2_scada only). "
     "NLDC nominal band: 49.7 to 50.2 Hz.")

# National generation mix
_add("gen_coal_mu",    "MU", SEC_B, DATE_FULL, "National coal thermal generation.")
_add("gen_lignite_mu", "MU", SEC_B, DATE_FULL, "National lignite thermal generation.")
_add("gen_hydro_mu",   "MU", SEC_B, DATE_FULL, "National hydro generation.")
_add("gen_nuclear_mu", "MU", SEC_B, DATE_FULL, "National nuclear generation.")
_add("gen_gas_mu",     "MU", SEC_B, DATE_FULL, "National gas-based generation.")
_add("gen_res_mu",     "MU", SEC_B, DATE_FULL,
     "National renewable energy source (RES) generation. Includes wind, solar, "
     "small hydro, biomass and other non-conventional sources.")
_add("gen_total_mu",   "MU", SEC_B, DATE_FULL, "Total national generation.")

# Share indicators
_add("share_res_pct",       "%", SEC_B, DATE_FULL,
     "Renewable energy share as a percentage of total generation "
     "(gen_res_mu / gen_total_mu * 100). Taken from the report's share row, but "
     "recomputed from the gen columns when the printed value is off by more than "
     "1 point (stale share rows in some NLDC files, e.g. 2024-03-12 printed 96.8%).")
_add("share_nonfossil_pct", "%", SEC_B, DATE_FULL,
     "Non-fossil fuel share (nuclear + hydro + RES) as a percentage of total generation "
     "((gen_hydro_mu + gen_nuclear_mu + gen_res_mu) / gen_total_mu * 100). Recomputed "
     "from the gen columns when the printed value is off by more than 1 point.")

# Outages by sector and region
for r, rname in REGIONS.items():
    _add(f"outage_central_{r}_mw", "MW", SEC_B, DATE_FULL,
         f"Central sector forced outages in {rname}.")
    _add(f"outage_state_{r}_mw",   "MW", SEC_B, DATE_FULL,
         f"State sector forced outages in {rname}.")
    _add(f"outage_total_{r}_mw",   "MW", SEC_B, DATE_FULL,
         f"Total forced outages (central + state) in {rname}.")

# Inter-regional exchange
for r, rname in REGIONS.items():
    _add(f"ie_schedule_{r}_mu", "MU", SEC_B, DATE_FULL,
         f"Scheduled inter-regional energy exchange for {rname}.")
    _add(f"ie_actual_{r}_mu",   "MU", SEC_B, DATE_FULL,
         f"Actual inter-regional energy exchange for {rname}.")
    _add(f"ie_odud_{r}_mu",     "MU", SEC_B, DATE_FULL,
         f"Over-drawal or under-drawal from the inter-regional exchange schedule "
         f"for {rname}. Positive = over-drawal.")

# Traditional transnational (legacy columns, pre-XB restructure)
_add("trans_bhutan_mu",           "MU", SEC_B, DATE_FULL,
     "Legacy transnational exchange with Bhutan. Superseded by xb_* columns from ~FY2023-24.")
_add("trans_nepal_mu",            "MU", SEC_B, DATE_FULL,
     "Legacy transnational exchange with Nepal. Superseded by xb_* columns from ~FY2023-24.")
_add("trans_bangladesh_mu",       "MU", SEC_B, DATE_FULL,
     "Legacy transnational exchange with Bangladesh. Superseded by xb_* columns from ~FY2023-24.")
_add("trans_godda_bangladesh_mu", "MU", SEC_XB, DATE_GODDA,
     "Energy exported from the Adani Godda ultra-supercritical plant to Bangladesh. "
     "Appears as a separate line in the cross-border section from approximately FY2023-24.")

# Diversity factors
_add("diversity_regional", "ratio", SEC_B, DATE_FULL,
     "All-India regional demand diversity factor. Ratio of the sum of regional peaks "
     "to the actual all-India peak. A value below 1 indicates that regional peaks "
     "do not coincide.")
_add("diversity_state",    "ratio", SEC_B, DATE_FULL,
     "All-India state demand diversity factor. Similar to diversity_regional but "
     "computed at the state level.")

# IR-Line corridor flows
for prefix, (a, b) in IR_CORRIDORS.items():
    _add(f"{prefix}_import_mu", "MU", SEC_IR, DATE_IR_XB,
         f"Energy {a} imported from {b} over the {a}-{b} inter-regional lines "
         f"(sum of all {a}-{b} lines, as seen from {a}'s side).")
    _add(f"{prefix}_export_mu", "MU", SEC_IR, DATE_IR_XB,
         f"Energy {a} exported to {b} over the {a}-{b} inter-regional lines "
         f"(sum of all {a}-{b} lines, as seen from {a}'s side).")
    _add(f"{prefix}_net_mu",    "MU", SEC_IR, DATE_IR_XB,
         f"Net {a}-{b} exchange from {a}'s side: import minus export. "
         f"Positive = {a} is a net importer from {b}; negative = net flow {a} to {b}.")

# Solar / nonsolar peak-hour statistics
_add("solar_hr_peak_mw",      "MW", SEC_A, DATE_SOLAR_HR,
     "Peak solar generation recorded during the solar peak hour of the day.")
_add("solar_hr_shortage_mw",  "MW", SEC_A, DATE_SOLAR_HR,
     "Demand shortage during the solar peak hour.")
_add("nonsolar_hr_peak_mw",   "MW", SEC_A, DATE_SOLAR_HR,
     "Peak demand in non-solar hours (i.e., excluding the solar peak window).")
_add("nonsolar_hr_shortage_mw","MW", SEC_A, DATE_SOLAR_HR,
     "Demand shortage during non-solar hours.")

# Cross-border exchange (restructured XB columns, ~FY2023-24 onward)
for key, cname in XB_COUNTRIES.items():
    _add(f"xb_export_{key}_mu", "MU", SEC_XB, DATE_IR_XB,
         f"Energy exported from India to {cname}.")
    _add(f"xb_import_{key}_mu", "MU", SEC_XB, DATE_IR_XB,
         f"Energy imported by India from {cname}.")
    _add(f"xb_net_{key}_mu",    "MU", SEC_XB, DATE_IR_XB,
         f"Net exchange with {cname} from India's perspective (import minus export). "
         f"Positive = net import by India.")

# SCADA real-time generation (study2_scada slot-level columns)
_add("demand_met_mw",        "MW", SEC_SCADA, DATE_SCADA,
     "National demand met in the 15-minute slot.")
_add("nuclear_mw",           "MW", SEC_SCADA, DATE_SCADA,
     "Nuclear generation in the slot.")
_add("wind_mw",              "MW", SEC_SCADA, DATE_SCADA,
     "Wind generation in the slot.")
_add("solar_mw",             "MW", SEC_SCADA, DATE_SCADA,
     "Solar generation in the slot.")
_add("hydro_mw",             "MW", SEC_SCADA, DATE_SCADA,
     "Hydro generation in the slot.")
_add("gas_mw",               "MW", SEC_SCADA, DATE_SCADA,
     "Gas-based generation in the slot.")
_add("thermal_mw",           "MW", SEC_SCADA, DATE_SCADA,
     "Thermal (coal + lignite) generation in the slot.")
_add("others_mw",            "MW", SEC_SCADA, DATE_SCADA,
     "Other generation sources in the slot (small hydro, biomass, etc.).")
_add("net_demand_met_mw",    "MW", SEC_SCADA, DATE_SCADA,
     "Net demand met after subtracting embedded renewables.")
_add("total_gen_mw",         "MW", SEC_SCADA, DATE_SCADA,
     "Total scheduled generation in the slot.")
_add("net_trans_exchange_mw","MW", SEC_SCADA, DATE_SCADA,
     "Net transmission exchange in the slot.")

# Kaggle hourly load columns (study1_hourly only)
_add("National Hourly Demand",           "MW", SEC_KAGGLE, DATE_HOURLY,
     "National hourly demand from the Kaggle India Hourly Load dataset. "
     "Covers 2019-01-01 to 2024-04-30.")
_add("Northern Region Hourly Demand",    "MW", SEC_KAGGLE, DATE_HOURLY,
     "Northern Region hourly demand from the Kaggle dataset.")
_add("Western Region Hourly Demand",     "MW", SEC_KAGGLE, DATE_HOURLY,
     "Western Region hourly demand from the Kaggle dataset.")
_add("Eastern Region Hourly Demand",     "MW", SEC_KAGGLE, DATE_HOURLY,
     "Eastern Region hourly demand from the Kaggle dataset.")
_add("Southern Region Hourly Demand",    "MW", SEC_KAGGLE, DATE_HOURLY,
     "Southern Region hourly demand from the Kaggle dataset.")
_add("North-Eastern Region Hourly Demand","MW", SEC_KAGGLE, DATE_HOURLY,
     "North-Eastern Region hourly demand from the Kaggle dataset.")

# study3_states columns (long format -- one row per state/UT/entity per day)
_add("region", "NR/WR/SR/ER/NER", SEC_STATES, DATE_STATES,
     "Region the state/UT/entity belongs to. Resolved from a static lookup table "
     "(Scrapings/parse_psp_states.py's STATE_TO_REGION), not read positionally from "
     "the source report -- the report's own region label is a merged cell that lands "
     "on an inconsistent row per group, so it can't be trusted directly.")
_add("state", "name", SEC_STATES, DATE_STATES,
     "State, UT, or grid entity name (also includes distinct bulk-consumer/railway "
     "drawal entities NLDC reports alongside states, e.g. 'Railways_NR ISTS'). "
     "Normalized to one canonical name per entity across the full time range even "
     "where the underlying administrative name changed (e.g. J&K's Aug 2019 split "
     "into J&K + Ladakh UTs, Puducherry's older 'Pondy' abbreviation) -- see "
     "STATE_NAME_ALIASES for the exact mapping.")
_add("max_demand_met_mw", "MW", SEC_STATES, DATE_STATES,
     "Maximum demand met by this state/entity during the day.")
_add("shortage_max_demand_mw", "MW", SEC_STATES, DATE_STATES,
     "Shortage during the state/entity's maximum demand.")
_add("energy_met_mu", "MU", SEC_STATES, DATE_STATES,
     "Energy met (consumed) by this state/entity over the reporting day.")
_add("drawal_schedule_mu", "MU", SEC_STATES, DATE_STATES,
     "Scheduled power drawal for this state/entity.")
_add("od_ud_mu", "MU", SEC_STATES, DATE_STATES,
     "Overdrawal(+)/Underdrawal(-) relative to the scheduled drawal.")
_add("max_od_mw", "MW", SEC_STATES, DATE_STATES,
     "Maximum overdrawal during the day.")
_add("energy_shortage_mu", "MU", SEC_STATES, DATE_STATES,
     "Energy shortage for this state/entity.")


# ── Inference fallback ────────────────────────────────────────────────────────

def _infer_unit(col: str) -> str:
    if col.endswith("_mw"):     return "MW"
    if col.endswith("_mu"):     return "MU"
    if col.endswith("_pct"):    return "%"
    if col.endswith("_hz"):     return "Hz"
    if col.endswith("_fvi"):    return "%"
    if col == "date":           return "date"
    if col == "datetime":       return "datetime"
    if col == "hhmm":           return "integer (HHMM)"
    if col == "time":           return "HH:MM"
    return ""


def _lookup(col: str) -> tuple[str, str, str, str]:
    """Return (unit, source_section, schema_start_date, notes) for a column."""
    if col in KNOWN:
        return KNOWN[col]
    return (_infer_unit(col), "", "", "")


# ── Sheet builder ─────────────────────────────────────────────────────────────

def _build_sheet(cols: list[str], datasets: list[str]) -> pd.DataFrame:
    rows = []
    dataset_str = ", ".join(datasets)
    for col in cols:
        unit, section, start, notes = _lookup(col)
        rows.append({
            "column_name":       col,
            "datasets":          dataset_str,
            "unit":              unit,
            "source_section":    section,
            "schema_start_date": start,
            "notes":             notes,
        })
    return pd.DataFrame(rows)


def _read_cols(path: Path) -> list[str]:
    import csv
    with open(path, newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


# ── Writer ────────────────────────────────────────────────────────────────────

def _col_widths(df: pd.DataFrame) -> dict[str, int]:
    """Compute reasonable column widths for Excel."""
    widths = {}
    for col in df.columns:
        max_data = df[col].astype(str).str.len().max() if len(df) else 0
        widths[col] = min(max(len(col), int(max_data)), 80)
    return widths


def write_xlsx(output: Path) -> None:
    missing = [p for p in [STUDY1_D, STUDY1_H, STUDY2, STUDY3] if not p.exists()]
    if missing:
        print(f"  ERROR: missing dataset file(s): {[str(p) for p in missing]}")
        print("  Run build_all.py first.")
        raise SystemExit(1)

    cols_d = _read_cols(STUDY1_D)
    cols_h = _read_cols(STUDY1_H)
    # study2_scada.csv is stored slim; document the columns as published and as
    # load_study2() returns them (slim file + study1_daily join).
    cols_2 = study2_io.wide_columns(STUDY2, STUDY1_D)
    cols_3 = _read_cols(STUDY3)

    df_d = _build_sheet(cols_d, ["study1_daily"])
    df_2 = _build_sheet(cols_2, ["study2_scada"])
    df_h = _build_sheet(cols_h, ["study1_hourly"])
    df_3 = _build_sheet(cols_3, ["study3_states"])

    # Master sheet: union of all unique columns, listing which datasets include each
    all_cols_ordered: list[str] = []
    seen: set[str] = set()
    for col in cols_d + cols_2 + cols_h + cols_3:
        if col not in seen:
            all_cols_ordered.append(col)
            seen.add(col)

    master_rows = []
    for col in all_cols_ordered:
        in_d = col in cols_d
        in_2 = col in cols_2
        in_h = col in cols_h
        in_3 = col in cols_3
        ds_list = []
        if in_d: ds_list.append("study1_daily")
        if in_2: ds_list.append("study2_scada")
        if in_h: ds_list.append("study1_hourly")
        if in_3: ds_list.append("study3_states")
        unit, section, start, notes = _lookup(col)
        master_rows.append({
            "column_name":       col,
            "datasets":          ", ".join(ds_list),
            "unit":              unit,
            "source_section":    section,
            "schema_start_date": start,
            "notes":             notes,
        })
    df_master = pd.DataFrame(master_rows)

    output.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in [
            ("study1_daily",  df_d),
            ("study2_scada",  df_2),
            ("study1_hourly", df_h),
            ("study3_states", df_3),
            ("master",        df_master),
        ]:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            ws = writer.sheets[sheet_name]
            widths = _col_widths(df)
            for i, col in enumerate(df.columns, start=1):
                ws.column_dimensions[
                    ws.cell(row=1, column=i).column_letter
                ].width = widths[col] + 2

            # Freeze the header row
            ws.freeze_panes = "A2"

        print(f"  Wrote {output}")
        for sheet_name, df in [
            ("study1_daily",  df_d),
            ("study2_scada",  df_2),
            ("study1_hourly", df_h),
            ("study3_states", df_3),
            ("master",        df_master),
        ]:
            filled = (df["notes"] != "").sum()
            print(f"    {sheet_name}: {len(df)} columns, {filled} with notes")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Dataset/data_dictionary.xlsx for Grid-Sentinel."
    )
    parser.add_argument(
        "--output", type=Path, default=OUT_XLSX,
        help=f"Output path (default: {OUT_XLSX})"
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Grid-Sentinel -- build_data_dict.py")
    print(f"{'='*60}\n")

    write_xlsx(args.output)

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
