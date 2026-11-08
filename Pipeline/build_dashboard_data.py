"""Build the per-tab data files the Phase 5 dashboard (dashboard/) consumes.

The dashboard is a static React app with no backend, it fetches JSON
directly from the browser. study1_hourly.csv (36MB), study2_scada.csv
(60MB) and study3_states.csv are far too large to fetch client-side just to
show a monthly trend or a single day's timeline, so this script precomputes
the small aggregates each tab actually needs. Each tab gets its own JSON
file, fetched only when that tab is first opened, so the Overview tab never
pays for the Models tab's 15-min risk history. Re-run whenever the source
datasets update (wired into daily_scrape.yml).

Output: dashboard/public/data/<tab>.json, one file per dashboard tab:
  overview.json     -- latest two days of the slim daily columns (Live Grid
                        Status + generation mix), the full 2019-present
                        demand/RES-share history, and the Era 1 monthly ramp
                        and Era 2 corridor-correlation tables (Historical
                        Explorer).
  states.json       -- study3_states.csv: latest-day snapshot, a 365-day
                        summary per entity (the India map's metrics), and a
                        monthly per-entity history (the trend picker).
  flows.json        -- inter-regional corridor nets (ir_*, 2023 on) and
                        cross-border exchange (xb_*, mid-2023 on): daily nets,
                        latest-day detail and monthly import/export.
  renewables.json   -- monthly solar/wind/hydro generation and RES share
                        since 2019, yearly totals, regional split, and the
                        monthly-average 15-min "duck curve" from SCADA.
  reliability.json  -- daily frequency-band compliance, FVI, forced outages
                        and shortage since 2019, plus monthly regional
                        breakdowns and a per-year summary.
  models.json       -- Study 1 forecast log, Study 2 risk log (grouped by
                        day as arrays, about 4x smaller than records), live
                        calibration of the risk models, the Era 3 EDA
                        findings and freshly retrained feature importance.

Every file carries "asOf" (the latest date it covers). Long series are
"columnar" ({"date": [...], "x": [...]}) rather than row records, which
roughly halves their size; the frontend zips them back into rows.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "Dataset"
OUT_DIR = REPO_ROOT / "dashboard" / "public" / "data"
LEGACY_FILE = OUT_DIR / "dashboard.json"  # pre-tabs single file, removed on build

STUDY1_DIR = REPO_ROOT / "ML" / "Study1"
STUDY2_DIR = REPO_ROOT / "ML" / "Study2"

STUDY1_DAILY_SLIM_COLS = [
    "date",
    "max_demand_met_total_mw",
    "energy_met_total_mu",
    "share_res_pct",
    "gen_coal_mu",
    "gen_lignite_mu",
    "gen_hydro_mu",
    "gen_nuclear_mu",
    "gen_gas_mu",
    "gen_res_mu",
    "gen_total_mu",
    "freq_fvi",
    "freq_pct_below_499",
    "freq_pct_above_5005",
]


def _load_module(name, path):
    """Both ML/Study1/features.py and ML/Study2/features.py are literally
    named features.py -- a plain sys.path import would silently return
    whichever one Python happened to import first. Load each by explicit
    file path instead, same pattern ML/Study2/features.py itself uses to
    load Study 1's module for the residual signal."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_records(df):
    """NaN isn't valid JSON, convert to None so json.dump emits `null`."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def build_era1_monthly():
    """Reproduces 04_era1_ramp_characterization.ipynb's monthly aggregation
    from the 36MB study1_hourly.csv, without shipping that file to the browser."""
    hourly = pd.read_csv(DATASET_DIR / "study1_hourly.csv")
    hourly["datetime"] = pd.to_datetime(hourly["datetime"], format="%Y-%m-%d %H:%M:%S")
    hourly["date"] = hourly["datetime"].dt.normalize()
    daily = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])

    hourly = hourly[hourly["date"].dt.year.between(2019, 2022)].copy()
    daily_era1 = daily[daily["date"].dt.year.between(2019, 2022)][["date", "share_res_pct"]]

    DEMAND_COL = "National Hourly Demand"
    hourly = hourly.sort_values("datetime").reset_index(drop=True)
    hourly["ramp"] = hourly[DEMAND_COL].diff()

    daily_ramp = hourly.groupby(hourly["date"].dt.date)["ramp"].apply(lambda x: x.abs().max())
    daily_ramp = daily_ramp.reset_index()
    daily_ramp.columns = ["date", "ramp_magnitude"]
    daily_ramp["date"] = pd.to_datetime(daily_ramp["date"])

    threshold = hourly["ramp"].abs().quantile(0.9)
    daily_freq = hourly.groupby(hourly["date"].dt.date)["ramp"].apply(lambda x: (x.abs() > threshold).sum())
    daily_freq = daily_freq.reset_index()
    daily_freq.columns = ["date", "ramp_frequency"]
    daily_freq["date"] = pd.to_datetime(daily_freq["date"])

    merged = daily_ramp.merge(daily_freq, on="date").merge(daily_era1, on="date", how="left")
    merged["month"] = merged["date"].dt.to_period("M")
    monthly = merged.groupby("month").agg(
        ramp_magnitude=("ramp_magnitude", "mean"),
        ramp_frequency=("ramp_frequency", "mean"),
        share_res_pct=("share_res_pct", "mean"),
    ).reset_index()
    monthly["month"] = monthly["month"].dt.to_timestamp().dt.strftime("%Y-%m-%d")
    return clean_records(monthly)


def build_era2_corridor_corr():
    """Reproduces 00_era2_daily_correlation.ipynb's per-corridor/per-country
    correlation-vs-stress numbers as a small static table."""
    df = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    era2 = df[(df["date"] >= "2023-01-01") & (df["date"] <= "2024-10-31")].copy()
    IR_COLS = [c for c in df.columns if c.startswith("ir_") and c.endswith("_net_mu")]
    XB_COLS = [c for c in df.columns if c.startswith("xb_net_")]
    era2["stress_pct"] = era2["freq_pct_below_499"] + era2["freq_pct_above_5005"]

    ir_sub = era2.dropna(subset=IR_COLS + ["stress_pct"])
    ir_abs_sum = ir_sub[IR_COLS].abs().sum(axis=1)

    rows = []
    for c in IR_COLS:
        rows.append({"group": "corridor", "name": c, "corr": np.corrcoef(ir_sub[c].abs(), ir_sub["stress_pct"])[0, 1]})
    rows.append({"group": "corridor", "name": "ALL (summed |ir_net|)", "corr": np.corrcoef(ir_abs_sum, ir_sub["stress_pct"])[0, 1]})

    xb_win = era2[era2["date"] >= "2023-07-06"].copy()
    xb_sub = xb_win.dropna(subset=XB_COLS + ["stress_pct"])
    for c in XB_COLS:
        v = xb_sub[c].abs()
        corr = np.corrcoef(v, xb_sub["stress_pct"])[0, 1] if v.std() > 0 else float("nan")
        rows.append({"group": "cross_border", "name": c, "corr": corr})
    rows.append({
        "group": "cross_border", "name": "ALL (summed |xb_net|)",
        "corr": np.corrcoef(xb_sub[XB_COLS].abs().sum(axis=1), xb_sub["stress_pct"])[0, 1],
    })

    out_df = pd.DataFrame(rows).dropna(subset=["corr"])
    return clean_records(out_df)


def _load_study2_base_df(f):
    """Common Era-3 EDA setup shared by every finding below -- same four
    calls 01_eda.ipynb opens with."""
    scada = pd.read_csv(DATASET_DIR / "study2_scada.csv", parse_dates=["date"])
    scada = scada.sort_values(["date", "time"]).reset_index(drop=True)
    df = f.drop_bad_days(scada)
    df = f.add_datetime(df)
    df = f.add_violation_label(df)
    df = f.add_ramp_label(df)
    df = f.add_time_features(df)
    return df


def build_hour_dow_heatmap(df):
    """Reproduces 01_eda.ipynb's appendix cell: violations concentrate hardest
    on Sunday, while ramp-shocks show the OPPOSITE day-of-week pattern -- the
    decoupling finding."""
    viol = df.pivot_table(index="dow", columns="hour", values="violation", aggfunc="mean")
    ramp = df.pivot_table(index="dow", columns="hour", values="ramp", aggfunc="mean")
    return {
        "hours": [int(h) for h in viol.columns],
        "violation": viol.values.tolist(),
        "ramp": ramp.values.tolist(),
    }


def build_month_seasonality(df):
    by_month = df.groupby("month")[["violation", "ramp"]].mean().reset_index()
    return clean_records(by_month)


def build_solar_hour_rates(df):
    by_solar = df.groupby("is_solar_hr")[["violation", "ramp"]].mean()
    return {
        "nonSolar": {"violation": by_solar.loc[0, "violation"], "ramp": by_solar.loc[0, "ramp"]},
        "solar": {"violation": by_solar.loc[1, "violation"], "ramp": by_solar.loc[1, "ramp"]},
    }


def build_res_share_findings(df):
    """Reproduces two 01_eda.ipynb findings: (1) violation rate rises
    monotonically with RES share, pooled -- the project's strongest single
    piece of SCADA-resolution evidence for its central thesis; (2) the pooled
    ramp-rate-vs-RES-share relationship reverses sign once season is
    controlled for (rank RES share within each month first)."""
    df = df.copy()
    df["res_bin"] = pd.qcut(df["share_res_pct"], 5, duplicates="drop")
    pooled = df.groupby("res_bin", observed=True)[["violation", "ramp"]].mean().reset_index(drop=True)
    pooled.insert(0, "quintile", ["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"][: len(pooled)])

    df["res_rank_in_month"] = df.groupby("month")["share_res_pct"].rank(pct=True)
    df["res_bin_within_month"] = pd.cut(df["res_rank_in_month"], 5, labels=False)
    within_month = df.groupby("res_bin_within_month", observed=True)[["violation", "ramp"]].mean().reset_index(drop=True)
    within_month.insert(0, "quintile", ["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"][: len(within_month)])

    return {
        "pooledViolationByResShare": clean_records(pooled[["quintile", "violation"]]),
        "rampReversal": clean_records(
            pd.DataFrame({
                "quintile": pooled["quintile"],
                "pooled": pooled["ramp"],
                "withinMonth": within_month["ramp"],
            })
        ),
    }


def build_feature_importance(study2_f):
    """Freshly retrains all three models (same procedure as the baseline
    notebooks -- time-aware split, same hyperparameters) purely to extract
    feature_importances_. Training takes seconds on this data size (same
    rationale predict.py documents for retraining fresh on every run)."""
    import lightgbm as lgb

    study1_f = _load_module("study1_features", STUDY1_DIR / "features.py")

    # --- Study 1: next-day demand forecast ---
    daily = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])
    daily = daily.sort_values("date").reset_index(drop=True)
    feat_df = study1_f.build_feature_table(daily)
    feat_df = study1_f.make_next_day_target(feat_df)
    TARGET = study1_f.TARGET
    feature_cols = [
        c for c in feat_df.columns
        if c.startswith(f"{TARGET}_lag") or c.startswith(f"{TARGET}_roll")
        or c in ("dow", "month", "year", "is_weekend", "day_of_year")
    ]
    feat_df = feat_df.dropna(subset=[f"{TARGET}_lag365", TARGET]).reset_index(drop=True)
    train = feat_df[feat_df["year"] <= 2022]
    val = feat_df[feat_df["year"] == 2023]
    X_train, y_train = train[feature_cols], train[TARGET] - train[f"{TARGET}_today"]
    X_val, y_val = val[feature_cols], val[TARGET] - val[f"{TARGET}_today"]
    model1 = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
    model1.fit(X_train, y_train, eval_set=[(X_val, y_val)], callbacks=[lgb.early_stopping(30, verbose=False)])
    study1_importance = (
        pd.Series(model1.feature_importances_, index=feature_cols)
        .sort_values(ascending=False).head(10).reset_index()
    )
    study1_importance.columns = ["feature", "importance"]

    # --- Study 2: violation + ramp-shock classifiers ---
    scada = pd.read_csv(DATASET_DIR / "study2_scada.csv", parse_dates=["date"])
    scada = scada.sort_values(["date", "time"]).reset_index(drop=True)
    feat_df2 = study2_f.build_feature_table(scada)

    def train_classifier(target):
        df = feat_df2.dropna(subset=[target]).copy()
        train = df[(df["date"] >= "2024-11-04") & (df["date"] <= "2025-06-30")]
        val = df[(df["date"] >= "2025-07-01") & (df["date"] <= "2025-12-31")]
        model = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
        model.fit(
            train[study2_f.FEATURE_COLS], train[target],
            eval_set=[(val[study2_f.FEATURE_COLS], val[target])],
            eval_metric="average_precision",
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        imp = (
            pd.Series(model.feature_importances_, index=study2_f.FEATURE_COLS)
            .sort_values(ascending=False).head(10).reset_index()
        )
        imp.columns = ["feature", "importance"]

        # Best-F1 threshold selected on VAL, not on TEST/live data -- same
        # methodology-fix pattern as 03_violation_baseline.ipynb (2026-07-14):
        # picking the threshold on the same data it's later applied to is a
        # hindsight-optimistic leak. This is genuinely out-of-sample.
        proba_val = model.predict_proba(val[study2_f.FEATURE_COLS])[:, 1]
        precision_val, recall_val, thresh_val = precision_recall_curve(val[target], proba_val)
        f1s_val = 2 * precision_val * recall_val / (precision_val + recall_val + 1e-12)
        best_idx_val = np.nanargmax(f1s_val[:-1])
        best_threshold = float(thresh_val[best_idx_val])

        return imp, best_threshold

    violation_importance, violation_threshold = train_classifier("violation_lead")
    ramp_importance, ramp_threshold = train_classifier("ramp_lead")

    return {
        "study1Demand": clean_records(study1_importance),
        "study2Violation": clean_records(violation_importance),
        "study2Ramp": clean_records(ramp_importance),
        "thresholds": {"violation": violation_threshold, "ramp": ramp_threshold},
    }


# ---------------------------------------------------------------------------
# Per-tab builders (dashboard tabs, 2026-11-08)
# ---------------------------------------------------------------------------

REGIONS = ["nr", "wr", "sr", "er", "ner"]
CORRIDORS = ["er_nr", "er_wr", "er_sr", "er_ner", "ner_nr", "wr_nr", "wr_sr"]
XB_COUNTRIES = ["bhutan", "nepal", "bangladesh", "myanmar"]


def columnar(df, digits=None):
    """{"col": [values...]} with NaN -> None. `digits` maps column -> round()
    precision; 0 turns the column into ints. Columnar beats row records here
    because the key names are not repeated once per row."""
    digits = digits or {}
    out = {}
    for c in df.columns:
        s = df[c]
        if c in digits:
            s = s.round(digits[c])
        vals = s.tolist()
        if digits.get(c) == 0:
            out[c] = [None if pd.isna(v) else int(v) for v in vals]
        else:
            out[c] = [None if (isinstance(v, float) and np.isnan(v)) else v for v in vals]
    return out


def _fnum(v, nd=2):
    if v is None or pd.isna(v):
        return None
    return int(round(float(v))) if nd == 0 else round(float(v), nd)


def _load_daily():
    df = pd.read_csv(DATASET_DIR / "study1_daily.csv", parse_dates=["date"])
    # .copy() de-fragments the 180-column frame (pandas PerformanceWarning).
    df = df.sort_values("date").reset_index(drop=True).copy()
    return df


def _monthly_mean(df, cols):
    """Monthly mean of each column (a per-day average, so the current, still
    partial month is directly comparable to complete ones)."""
    m = df.set_index("date")[cols].resample("MS").mean().reset_index()
    m["month"] = m["date"].dt.strftime("%Y-%m")
    return m.drop(columns="date")[["month"] + cols]


# --- Overview ---------------------------------------------------------------

def build_overview(daily):
    slim = daily[STUDY1_DAILY_SLIM_COLS].copy()
    slim["date"] = slim["date"].dt.strftime("%Y-%m-%d")
    hist = daily[["date", "max_demand_met_total_mw", "share_res_pct"]].copy()
    hist["date"] = hist["date"].dt.strftime("%Y-%m-%d")
    hist.columns = ["date", "demand", "res"]
    return {
        "asOf": slim["date"].iloc[-1],
        "latest": clean_records(slim.tail(2)),
        "history": columnar(hist, {"demand": 0, "res": 2}),
        "era1Monthly": build_era1_monthly(),
        "era2CorridorCorr": build_era2_corridor_corr(),
    }


# --- States -----------------------------------------------------------------

# study3 labels -> display names. DD and DNH were separate rows until the
# 2022-06 merger into one DNHDDPDCL utility; summing the two older rows into
# the merged name keeps a single continuous series for the merged UT.
STATE_RENAME = {
    "HP": "Himachal Pradesh",
    "MP": "Madhya Pradesh",
    "UP": "Uttar Pradesh",
    "J&K(UT) & Ladakh(UT)": "J&K and Ladakh",
    "DD": "DNH and DD",
    "DNH": "DNH and DD",
    "DNHDDPDCL": "DNH and DD",
}
# Rows that are grid entities, not states/UTs: no polygon on the map, listed
# separately in the UI.
NON_STATE_PREFIXES = ("Bulk Consumer_", "Railways_")
NON_STATE_NAMES = {"DVC", "AMNSIL", "BALCO", "Essar steel", "RIL JAMNAGAR"}


def _is_state(name):
    return not (name in NON_STATE_NAMES or name.startswith(NON_STATE_PREFIXES))


def build_states():
    df = pd.read_csv(DATASET_DIR / "study3_states.csv", parse_dates=["date"])
    df["state"] = df["state"].replace(STATE_RENAME)
    num = ["max_demand_met_mw", "shortage_max_demand_mw", "energy_met_mu", "energy_shortage_mu"]
    # Summing the pre-merger DD and DNH peaks overstates the merged peak a
    # little (they peak at different times), but it is the closest proxy and
    # only touches pre-2022-06 history of one small UT.
    df = df.groupby(["date", "region", "state"], as_index=False)[num].sum(min_count=1)

    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].sort_values("max_demand_met_mw", ascending=False)

    # Last 365 days vs the 365 before: the map's metrics.
    w1 = df[df["date"] > latest_date - pd.Timedelta(days=365)]
    w0 = df[(df["date"] <= latest_date - pd.Timedelta(days=365)) & (df["date"] > latest_date - pd.Timedelta(days=730))]
    g1 = w1.groupby("state").agg(
        region=("region", "last"),
        peak_mw=("max_demand_met_mw", "max"),
        energy_mu=("energy_met_mu", "sum"),
        shortage_mu=("energy_shortage_mu", "sum"),
        shortage_days=("energy_shortage_mu", lambda x: int((x > 0).sum())),
        days=("date", "nunique"),
    )
    g0 = w0.groupby("state").agg(energy_prev_mu=("energy_met_mu", "sum"), days_prev=("date", "nunique"))
    summary = g1.join(g0, how="left")
    # Only compare like with like: both windows must be (nearly) complete,
    # otherwise an entity that started reporting mid-window shows fake growth.
    ok = (summary["days"] >= 360) & (summary["days_prev"] >= 360) & (summary["energy_prev_mu"] > 0)
    summary["growth_pct"] = np.where(ok, (summary["energy_mu"] / summary["energy_prev_mu"] - 1) * 100, np.nan)
    summary = summary.reset_index().sort_values("energy_mu", ascending=False)

    latest_by_state = latest.set_index("state")
    entities = []
    for r in summary.itertuples():
        lat = latest_by_state.loc[r.state] if r.state in latest_by_state.index else None
        entities.append({
            "name": r.state,
            "region": r.region,
            "isState": _is_state(r.state),
            "peakMw": _fnum(r.peak_mw, 0),
            "energyMu": _fnum(r.energy_mu, 1),
            "shortageMu": _fnum(r.shortage_mu, 2),
            "shortageDays": int(r.shortage_days),
            "growthPct": _fnum(r.growth_pct, 2),
            "latestDemandMw": _fnum(lat["max_demand_met_mw"], 0) if lat is not None else None,
            "latestShortageMw": _fnum(lat["shortage_max_demand_mw"], 0) if lat is not None else None,
        })

    # Monthly history per entity: peak demand (max), avg daily energy and
    # avg daily shortage (per-day averages so a partial month isn't a dip).
    df["month"] = df["date"].dt.to_period("M")
    months = pd.period_range(df["month"].min(), df["month"].max(), freq="M")
    monthly = df.groupby(["state", "month"]).agg(
        peak=("max_demand_met_mw", "max"),
        energy=("energy_met_mu", "mean"),
        shortage=("energy_shortage_mu", "mean"),
    )
    history = {}
    for state, g in monthly.groupby(level=0):
        g = g.droplevel(0).reindex(months)
        history[state] = columnar(g.reset_index(drop=True), {"peak": 0, "energy": 2, "shortage": 3})

    totals = {
        "totalDemand": float(latest["max_demand_met_mw"].sum()),
        "totalShortage": float(latest["shortage_max_demand_mw"].sum()),
        "stateCount": int(len(latest)),
        "statesWithShortage": int((latest["shortage_max_demand_mw"] > 0).sum()),
    }
    return {
        "asOf": latest_date.strftime("%Y-%m-%d"),
        "totals": totals,
        "entities": entities,
        "months": [str(m) for m in months],
        "history": history,
    }


# --- Power flows ------------------------------------------------------------

def _latest_detail(daily, keys, cols_for):
    """Latest day that has any of the given columns, as import/export/net
    per key. cols_for(key) -> [import_col, export_col, net_col]."""
    all_cols = [c for k in keys for c in cols_for(k)]
    rows = daily.dropna(subset=all_cols, how="all")
    if rows.empty:
        return None
    row = rows.iloc[-1]
    items = []
    for k in keys:
        imp, exp, net = cols_for(k)
        items.append({"key": k, "import": _fnum(row[imp]), "export": _fnum(row[exp]), "net": _fnum(row[net])})
    return {"date": row["date"].strftime("%Y-%m-%d"), "items": items}


def build_flows(daily):
    ir_net = [f"ir_{c}_net_mu" for c in CORRIDORS]
    xb_net = [f"xb_net_{c}_mu" for c in XB_COUNTRIES]
    sub = daily[daily["date"] >= "2023-01-01"][["date"] + ir_net + xb_net].copy()
    sub = sub.dropna(subset=ir_net + xb_net, how="all")
    sub.columns = ["date"] + CORRIDORS + XB_COUNTRIES
    sub["date"] = sub["date"].dt.strftime("%Y-%m-%d")

    ir_latest = _latest_detail(daily, CORRIDORS, lambda k: [f"ir_{k}_import_mu", f"ir_{k}_export_mu", f"ir_{k}_net_mu"])
    xb_latest = _latest_detail(daily, XB_COUNTRIES, lambda k: [f"xb_import_{k}_mu", f"xb_export_{k}_mu", f"xb_net_{k}_mu"])

    xb_cols = [f"xb_{d}_{c}_mu" for c in XB_COUNTRIES for d in ("import", "export")]
    xb_daily = daily.dropna(subset=xb_cols, how="all")
    xb_monthly = _monthly_mean(xb_daily, xb_cols)
    xb_monthly.columns = ["month"] + [c[len("xb_"):-len("_mu")] for c in xb_cols]

    ir_daily = daily.dropna(subset=ir_net, how="all")
    ir_monthly = _monthly_mean(ir_daily, ir_net)
    ir_monthly.columns = ["month"] + CORRIDORS

    return {
        "asOf": sub["date"].iloc[-1],
        "daily": columnar(sub, {**{c: 1 for c in CORRIDORS}, **{c: 2 for c in XB_COUNTRIES}}),
        "irMonthly": columnar(ir_monthly, {c: 1 for c in CORRIDORS}),
        "xbMonthly": columnar(xb_monthly, {c: 2 for c in xb_monthly.columns if c != "month"}),
        "irLatest": ir_latest,
        "xbLatest": xb_latest,
    }


# --- Renewables -------------------------------------------------------------

def build_renewables(daily, era3_df):
    cols = ["solar_gen_total_mu", "wind_gen_total_mu", "hydro_gen_total_mu", "gen_res_mu",
            "gen_total_mu", "share_res_pct", "share_nonfossil_pct"]
    monthly = _monthly_mean(daily, cols)
    monthly.columns = ["month", "solar", "wind", "hydro", "res", "total", "resShare", "nonFossilShare"]

    yearly = daily.assign(year=daily["date"].dt.year).groupby("year").agg(
        solar=("solar_gen_total_mu", "sum"), wind=("wind_gen_total_mu", "sum"),
        days=("date", "nunique"),
    ).reset_index()
    yearly = yearly[yearly["year"] >= 2019]

    latest_date = daily["date"].max()
    last365 = daily[daily["date"] > latest_date - pd.Timedelta(days=365)]
    regional = [
        {"region": r.upper(),
         "solar": _fnum(last365[f"solar_gen_{r}_mu"].sum(), 0),
         "wind": _fnum(last365[f"wind_gen_{r}_mu"].sum(), 0)}
        for r in REGIONS
    ]

    # Duck curve: average 15-min profile of each calendar month, from SCADA
    # (Era 3, 2024-11 on). era3_df already had drop_bad_days() applied, so
    # known-broken SCADA days don't distort the averages.
    sc = era3_df[["date", "time", "demand_met_mw", "solar_mw", "wind_mw"]].copy()
    sc["month"] = pd.to_datetime(sc["date"]).dt.strftime("%Y-%m")
    prof = sc.groupby(["month", "time"])[["demand_met_mw", "solar_mw", "wind_mw"]].mean()
    slots = sorted(sc["time"].unique())
    duck = {}
    for month, g in prof.groupby(level=0):
        g = g.droplevel(0).reindex(slots)
        duck[month] = {
            "demand": [None if pd.isna(v) else int(round(v)) for v in g["demand_met_mw"]],
            "solar": [None if pd.isna(v) else int(round(v)) for v in g["solar_mw"]],
            "wind": [None if pd.isna(v) else int(round(v)) for v in g["wind_mw"]],
        }

    best_res = daily.loc[daily["share_res_pct"].idxmax()]
    best_solar = daily.loc[daily["solar_gen_total_mu"].idxmax()]
    peak_slot = sc.loc[sc["solar_mw"].idxmax()]
    records = {
        "maxResShare": {"date": best_res["date"].strftime("%Y-%m-%d"), "value": _fnum(best_res["share_res_pct"])},
        "maxSolarDay": {"date": best_solar["date"].strftime("%Y-%m-%d"), "value": _fnum(best_solar["solar_gen_total_mu"], 1)},
        "maxSolarSlot": {"date": str(peak_slot["date"])[:10], "time": str(peak_slot["time"]), "value": _fnum(peak_slot["solar_mw"], 0)},
    }

    return {
        "asOf": latest_date.strftime("%Y-%m-%d"),
        "monthly": columnar(monthly, {"solar": 1, "wind": 1, "hydro": 1, "res": 1, "total": 0,
                                      "resShare": 2, "nonFossilShare": 2}),
        "yearly": [
            {"year": int(r.year), "solar": _fnum(r.solar, 0), "wind": _fnum(r.wind, 0), "days": int(r.days)}
            for r in yearly.itertuples()
        ],
        "regional": regional,
        "duck": {"slots": [str(s) for s in slots], "months": sorted(duck), "profiles": duck},
        "records": records,
    }


# --- Reliability ------------------------------------------------------------

def build_reliability(daily):
    keep = {
        "freq_fvi": "fvi", "freq_pct_below_499": "below", "freq_pct_499_5005": "inBand",
        "freq_pct_above_5005": "above", "outage_total_total_mw": "outage",
        "energy_shortage_total_mu": "shortageMu", "peak_shortage_total_mw": "peakShortageMw",
    }
    d = daily[["date"] + list(keep)].rename(columns=keep)
    d_out = d.copy()
    d_out["date"] = d_out["date"].dt.strftime("%Y-%m-%d")

    outage_cols = [f"outage_total_{r}_mw" for r in REGIONS] + ["outage_central_total_mw", "outage_state_total_mw"]
    short_cols = [f"energy_shortage_{r}_mu" for r in REGIONS]
    om = _monthly_mean(daily, outage_cols)
    om.columns = ["month"] + [r.upper() for r in REGIONS] + ["central", "state"]
    sm = _monthly_mean(daily, short_cols)
    sm.columns = ["month"] + [r.upper() for r in REGIONS]

    yr = d.assign(year=d["date"].dt.year)
    yr = yr[yr["year"] >= 2019].groupby("year").agg(
        inBand=("inBand", "mean"), fvi=("fvi", "mean"), outage=("outage", "mean"),
        shortageMu=("shortageMu", "sum"), days=("date", "nunique"),
    ).reset_index()

    return {
        "asOf": d_out["date"].iloc[-1],
        "daily": columnar(d_out, {"fvi": 3, "below": 2, "inBand": 2, "above": 2, "outage": 0,
                                  "shortageMu": 2, "peakShortageMw": 0}),
        "outageMonthly": columnar(om, {c: 0 for c in om.columns if c != "month"}),
        "shortageMonthly": columnar(sm, {c: 3 for c in sm.columns if c != "month"}),
        "yearly": [
            {"year": int(r.year), "inBand": _fnum(r.inBand), "fvi": _fnum(r.fvi, 3),
             "outage": _fnum(r.outage, 0), "shortageMu": _fnum(r.shortageMu, 1), "days": int(r.days)}
            for r in yr.itertuples()
        ],
    }


# --- Models -----------------------------------------------------------------

def compact_risk(risk):
    """Group the 15-min risk log by day: {date: {t, v, r, av, ar}} arrays.
    The frontend expands it back into the original row shape."""
    out = {}
    for date, g in risk.sort_values(["date", "time"]).groupby("date"):
        out[str(date)] = {
            "t": g["time"].tolist(),
            "v": [None if pd.isna(x) else round(float(x), 4) for x in g["violation_prob"]],
            "r": [None if pd.isna(x) else round(float(x), 4) for x in g["ramp_prob"]],
            "av": [None if pd.isna(x) else int(x) for x in g["actual_violation"]],
            "ar": [None if pd.isna(x) else int(x) for x in g["actual_ramp"]],
        }
    return out


def build_calibration(risk, thresholds):
    """How the live (logged, out-of-sample) risk predictions compare with
    what actually happened: decile reliability bins, plus precision/recall
    at each classifier's VAL-selected threshold."""
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    out = {}
    for name, prob_col, act_col in (("violation", "violation_prob", "actual_violation"),
                                    ("ramp", "ramp_prob", "actual_ramp")):
        d = risk.dropna(subset=[prob_col, act_col])
        if d.empty or d[act_col].nunique() < 2:
            out[name] = None
            continue
        y, p = d[act_col].astype(int), d[prob_col]
        bins = pd.qcut(p.rank(method="first"), 10, labels=False)
        rel = d.assign(bin=bins).groupby("bin").agg(
            predicted=(prob_col, "mean"), observed=(act_col, "mean"), n=(act_col, "size"),
        ).reset_index(drop=True)
        thr = thresholds.get(name)
        flagged = p >= thr
        n_flagged = int(flagged.sum())
        n_pos = int((y == 1).sum())
        tp = int((flagged & (y == 1)).sum())
        out[name] = {
            "n": int(len(d)),
            "positives": n_pos,
            "baseRate": _fnum(y.mean(), 4),
            "auc": _fnum(roc_auc_score(y, p), 3),
            "avgPrecision": _fnum(average_precision_score(y, p), 3),
            "brier": _fnum(brier_score_loss(y, p), 4),
            "threshold": _fnum(thr, 4),
            "flagged": n_flagged,
            "precision": _fnum(tp / n_flagged, 3) if n_flagged else None,
            "recall": _fnum(tp / n_pos, 3) if n_pos else None,
            "bins": [{"predicted": _fnum(r.predicted, 4), "observed": _fnum(r.observed, 4), "n": int(r.n)}
                     for r in rel.itertuples()],
        }
    return out


def build_models(era3_df, study2_f):
    forecast = pd.read_csv(DATASET_DIR / "predictions" / "study1_forecast.csv")
    risk = pd.read_csv(DATASET_DIR / "predictions" / "study2_risk.csv")
    fi = build_feature_importance(study2_f)
    return {
        "asOf": str(risk["date"].max()) if len(risk) else None,
        "forecast": clean_records(forecast),
        "risk": compact_risk(risk),
        "calibration": build_calibration(risk, fi["thresholds"]),
        "featureImportance": fi,
        "hourDowHeatmap": build_hour_dow_heatmap(era3_df),
        "monthSeasonality": build_month_seasonality(era3_df),
        "solarHourRates": build_solar_hour_rates(era3_df),
        "resShareFindings": build_res_share_findings(era3_df),
    }


def _write(name, payload):
    path = OUT_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), allow_nan=False)
    print(f"wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    study2_f = _load_module("study2_features", STUDY2_DIR / "features.py")
    era3_df = _load_study2_base_df(study2_f)
    daily = _load_daily()

    _write("overview", build_overview(daily))
    _write("states", build_states())
    _write("flows", build_flows(daily))
    _write("renewables", build_renewables(daily, era3_df))
    _write("reliability", build_reliability(daily))
    _write("models", build_models(era3_df, study2_f))

    if LEGACY_FILE.exists():
        LEGACY_FILE.unlink()
        print(f"removed legacy {LEGACY_FILE.relative_to(REPO_ROOT)}")
