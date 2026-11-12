"""
Parser regression tests. Added 2026-11-12.

Each parser is run on one real NLDC report per format era (the reports are
already in Dataset/Raw/File2_Raw) and its output is compared with what the
committed datasets hold for that day. The committed datasets were checked
against the raw reports when they were built and repaired, so any difference
means a parser changed behaviour on that era's layout.

The eras chosen are the ones where the report layout changed and a parser has
broken before:
  2019 to 2022  PDFs, including the run-together-text ones (2020, 2021)
  2023          first XLS layout, no TimeSeries sheet yet
  2025          XLS with TimeSeries, max OD as a single number
  2026-02-13    max OD printed as "OD/ UD"            (fixed 2026-11-10)
  2026-08-05    shortage row relabelled "Shoratge..."  (fixed 2026-11-10)
  2026-09-29    bulk consumers moved to sheet MOP_E1,
                blank rows inside section C            (fixed 2026-11-10)
  2026-11-09    current layout

When a parser is fixed on purpose, re-parse the affected days into the
datasets in the same change; these tests then pass again.

Run:  python -m pytest tests -q
"""
import math
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

import parse_psp_pdf_xls_file2 as p2
import parse_psp_states as ps
import parse_psp_xls_pdf_file3 as p3
import study2_io

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "Dataset" / "Raw" / "File2_Raw"
DATASET = ROOT / "Dataset"

REPORTS = [
    "01.01.19_NLDC_PSP.pdf",
    "15.06.20_NLDC_PSP.pdf",
    "15.06.21_NLDC_PSP.pdf",
    "15.06.22_NLDC_PSP.pdf",
    "01.06.23_NLDC_PSP.xls",
    "16.01.25_NLDC_PSP.xls",
    "13.02.26_NLDC_PSP.xls",
    "05.08.26_NLDC_PSP.xls",
    "29.09.26_NLDC_PSP.xls",
    "09.11.26_NLDC_PSP.xls",
]
SCADA_REPORTS = [r for r in REPORTS if r.endswith(".xls") and not r.startswith("01.06.23")]


def _same(a, b) -> bool:
    if (a is None or (isinstance(a, float) and math.isnan(a))) and pd.isna(b):
        return True
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        return str(a) == str(b)


@pytest.fixture(scope="module")
def study1():
    return pd.read_csv(DATASET / "study1_daily.csv", float_precision="round_trip").set_index("date")


@pytest.fixture(scope="module")
def study3():
    return pd.read_csv(DATASET / "study3_states.csv", float_precision="round_trip")


@pytest.fixture(scope="module")
def study2():
    return pd.read_csv(DATASET / "study2_scada.csv", float_precision="round_trip")


@pytest.mark.parametrize("report", REPORTS)
def test_study1_parser_matches_dataset(report, study1):
    row = p2.parse_file(str(RAW / report))
    day = str(row["date"])
    assert day in study1.index, f"{day} not in study1_daily.csv"
    stored = study1.loc[day]
    common = [k for k in row if k != "date" and k in stored.index]
    assert len(common) >= 100, f"only {len(common)} columns parsed"
    diff = {k: (row[k], stored[k]) for k in common if not _same(row[k], stored[k])}
    assert not diff, f"{report}: {len(diff)} column(s) differ, e.g. {dict(list(diff.items())[:5])}"


@pytest.mark.parametrize("report", REPORTS)
def test_states_parser_matches_dataset(report, study3):
    rows = ps.parse_file(str(RAW / report))
    assert rows, "no section C rows parsed"
    day = str(rows[0]["date"])
    got = {ps.STATE_NAME_ALIASES.get(r["state"], r["state"]): r for r in rows}
    stored = study3[study3["date"] == day].set_index("state")
    assert set(got) == set(stored.index), (
        f"{report}: entities differ, only parsed {sorted(set(got) - set(stored.index))}, "
        f"only stored {sorted(set(stored.index) - set(got))}")
    bad = [s for s in got if not all(_same(got[s][c], stored.loc[s, c]) for c in ps.COLS)]
    assert not bad, f"{report}: values differ for {bad[:5]}"
    assert all(s in ps.STATE_TO_REGION for s in got), "an entity has no region in STATE_TO_REGION"


@pytest.mark.parametrize("report", SCADA_REPORTS)
def test_scada_parser_matches_dataset(report, study1, study2, tmp_path):
    out = tmp_path / "scada.csv"
    p3.build_timeseries_long(str(RAW / report), str(out))
    new = pd.read_csv(out, float_precision="round_trip")
    new = study2_io.slim(new, list(study1.reset_index().columns))
    day = str(new["date"].iloc[0])
    old = study2[study2["date"] == day].reset_index(drop=True)
    assert len(new) == len(old) and len(new) >= 90, f"{report}: {len(new)} slots parsed, {len(old)} stored"
    cols = [c for c in old.columns if c != "date"]
    assert list(new.columns) == list(old.columns)
    bad = [c for c in cols if not all(_same(a, b) for a, b in zip(new[c], old[c]))]
    assert not bad, f"{report}: columns differ {bad[:5]}"


def _append_roundtrip(monkeypatch, tmp_path, csv_name, attr, func_name, report):
    """Remove the report's day from a copy of the dataset, append it back with
    update_live, and require the copy to be byte-identical to the original."""
    import update_live

    src = DATASET / csv_name
    copy = tmp_path / csv_name
    shutil.copy(src, copy)
    df = pd.read_csv(copy, float_precision="round_trip", dtype={"date": str})
    day = update_live._parse_file_date(RAW / report).isoformat()
    assert (df["date"] == day).any()
    df[df["date"] != day].to_csv(copy, index=False)
    monkeypatch.setattr(update_live, attr, copy)
    assert getattr(update_live, func_name)(RAW / report) is True
    assert copy.read_bytes().replace(b"\r\n", b"\n") == src.read_bytes().replace(b"\r\n", b"\n"), \
        f"{csv_name} after re-appending {day} is not identical to the committed file"


def test_append_study1_restores_day_exactly(monkeypatch, tmp_path):
    # Guards the 2026-11-09 failure: the appended row's date had a different
    # type from the stored ones, so the date sort crashed and the day was lost.
    _append_roundtrip(monkeypatch, tmp_path, "study1_daily.csv", "STUDY1_CSV", "append_study1", "29.09.26_NLDC_PSP.xls")


def test_append_study3_restores_day_exactly(monkeypatch, tmp_path):
    _append_roundtrip(monkeypatch, tmp_path, "study3_states.csv", "STUDY3_CSV", "append_study3", "29.09.26_NLDC_PSP.xls")
