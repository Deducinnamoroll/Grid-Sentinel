"""ML/Study2/features.py — shared feature engineering, reused by notebooks + predict.py

Builds two lead-time binary targets from study2_scada.csv (15-min slots):
  - violation_lead: will freq_hz fall outside [FREQ_LOW, FREQ_HIGH] in any of the
    next LEAD_SLOTS slots?
  - ramp_lead: will |demand_met_mw slot-to-slot delta| exceed RAMP_THRESHOLD_MW in
    any of the next LEAD_SLOTS slots?

Both labels require genuine 15-minute contiguity to the slots being looked ahead
into -- see _add_lead_label()'s docstring for why this matters and how it's
enforced.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STUDY1_DIR = REPO_ROOT / "ML" / "Study1"

# Loaded under a distinct module name (not "features") to avoid colliding with this
# file's own module name in sys.modules -- both Study1 and Study2 have a features.py,
# and a plain `sys.path.insert` + `import features` would silently re-return
# whichever one got imported first instead of Study 1's.
_spec = importlib.util.spec_from_file_location("study1_features", STUDY1_DIR / "features.py")
study1_features = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(study1_features)

FREQ_LOW = 49.7
FREQ_HIGH = 50.2
LEAD_SLOTS = 4  # 1-4 slots ahead = 15-60 min lead time
SLOT_MINUTES = 15

# Empirically ~p95 of |slot-to-slot demand_met_mw delta| across the full archive (measured
# 2026-07-11: p95 = 3734 MW). Treated as a fixed operational threshold, like the NLDC
# frequency band above, not fit per train/val/test split -- avoids leaking split-specific
# statistics into the label definition.
RAMP_THRESHOLD_MW = 3500

# Days with fewer than 90 of the expected 96 slots -- corrupted/incomplete source files,
# not real grid behavior. Verified 2026-07-11 against the live dataset: 2024-11-20 and
# 2025-04-01 have exactly 1 slot each, 2025-10-02 has 63 (already documented in the
# roadmap). Slot-count outliers at 95/97/98 are kept -- those are DST/rounding edge cases
# with enough data to be usable, not corrupted files.
MIN_SLOTS_PER_DAY = 90


def drop_bad_days(df: pd.DataFrame) -> pd.DataFrame:
    counts = df.groupby("date")["date"].transform("size")
    return df[counts >= MIN_SLOTS_PER_DAY].copy()


def add_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """`hhmm` is HHMM as an integer (e.g. 145 = 01:45), not minutes-since-midnight
    -- use the `time` string column ("HH:MM") instead, which parses unambiguously."""
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    return df


def _add_lead_label(df: pd.DataFrame, event_col: str, out_col: str, lead_slots: int = LEAD_SLOTS) -> pd.DataFrame:
    """Label = did `event_col` happen in any of the next `lead_slots` slots?

    A naive df[event_col].shift(-k) silently bridges gaps: if a day is dropped
    (drop_bad_days) or the archive has a missing date, shift(-k) would pull in a
    value from a slot that is actually hours or days away, not `k` slots away.
    Guarded here by only accepting a shifted value when the datetime gap to it is
    exactly `k * SLOT_MINUTES` minutes -- otherwise that lookahead position is
    unknown (NaN), not "no event". Crossing a calendar-day boundary is fine and
    kept (the grid doesn't reset at midnight); crossing a data gap is not.
    """
    df = df.sort_values("datetime").reset_index(drop=True)
    fwd_cols = []
    for k in range(1, lead_slots + 1):
        shifted_dt = df["datetime"].shift(-k)
        gap_ok = (shifted_dt - df["datetime"]) == pd.Timedelta(minutes=SLOT_MINUTES * k)
        shifted_val = df[event_col].shift(-k)
        col = f"_{out_col}_fwd{k}"
        df[col] = np.where(gap_ok, shifted_val, np.nan)
        fwd_cols.append(col)
    # max() across the lookahead window: 1 if any known slot had the event, 0 if all
    # known slots didn't, NaN if every lookahead slot was unreachable (end of data /
    # right before a gap) -- those rows have an undefined label and must be dropped
    # before training, not treated as 0.
    df[out_col] = df[fwd_cols].max(axis=1, skipna=True)
    df = df.drop(columns=fwd_cols)
    return df


def add_violation_label(df: pd.DataFrame, lead_slots: int = LEAD_SLOTS) -> pd.DataFrame:
    """lead_slots is exposed (unlike add_ramp_label) because 03_violation_baseline.ipynb
    tests a shorter lead window as a real experiment -- see that notebook for the
    verified before/after comparison."""
    df = df.copy()
    df["violation"] = ((df["freq_hz"] < FREQ_LOW) | (df["freq_hz"] > FREQ_HIGH)).astype(float)
    df.loc[df["freq_hz"].isna(), "violation"] = np.nan
    return _add_lead_label(df, "violation", "violation_lead", lead_slots=lead_slots)


def add_ramp_label(df: pd.DataFrame) -> pd.DataFrame:
    """Ramp-shock event = |delta| > RAMP_THRESHOLD_MW between this slot and the
    previous one, only when that previous slot is genuinely 15 min behind (same
    contiguity guard as _add_lead_label, applied backward instead of forward)."""
    df = df.sort_values("datetime").reset_index(drop=True)
    prev_dt = df["datetime"].shift(1)
    gap_ok = (df["datetime"] - prev_dt) == pd.Timedelta(minutes=SLOT_MINUTES)
    delta = df["demand_met_mw"] - df["demand_met_mw"].shift(1)
    df["demand_delta_mw"] = np.where(gap_ok, delta, np.nan)
    df["ramp"] = (df["demand_delta_mw"].abs() > RAMP_THRESHOLD_MW).astype(float)
    df.loc[df["demand_delta_mw"].isna(), "ramp"] = np.nan
    return _add_lead_label(df, "ramp", "ramp_lead")


def add_slot_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Recent-history features computed the same contiguity-guarded way as the
    labels -- a lag/rolling feature built across a data gap would be silently
    wrong in the same way an unguarded label would be."""
    df = df.sort_values("datetime").reset_index(drop=True)
    for k in (1, 2, 3):
        prev_dt = df["datetime"].shift(k)
        gap_ok = (df["datetime"] - prev_dt) == pd.Timedelta(minutes=SLOT_MINUTES * k)
        df[f"freq_hz_lag{k}"] = np.where(gap_ok, df["freq_hz"].shift(k), np.nan)
        df[f"demand_met_mw_lag{k}"] = np.where(gap_ok, df["demand_met_mw"].shift(k), np.nan)

    # Solar-side volatility -- added 2026-07-11 after an explicit diagnostic check found
    # the originally-hypothesized signal for the violation target was wrong: demand-side
    # ramps (ramp_lead / demand_delta_mw) do NOT precede violations more than chance
    # (P(ramp_lead=1 | violation_lead=1) = 14.2%, actually BELOW the 15.1% unconditional
    # rate -- a real, negative result, not pursued further). Scanning every generation
    # source's slot-to-slot delta for correlation with violation_lead instead found solar
    # clearly ahead of the rest (corr 0.0785 vs wind 0.036, all others near zero, plain
    # demand delta near zero) -- consistent with violations clustering at 08:00-09:00 and
    # 13:00 (01_eda.ipynb), prime solar-ramp hours. Physically: a violation may be a
    # downstream consequence of fast-changing SOLAR generation outrunning reserves, not
    # fast-changing demand, which is a materially different (and better-supported)
    # hypothesis than the one originally proposed.
    prev_dt1 = df["datetime"].shift(1)
    gap_ok1 = (df["datetime"] - prev_dt1) == pd.Timedelta(minutes=SLOT_MINUTES)
    df["solar_delta_mw"] = np.where(gap_ok1, df["solar_mw"] - df["solar_mw"].shift(1), np.nan)

    # freq_hz's own delta and wind_delta_mw -- added 2026-07-11, the two next-highest
    # correlations with violation_lead from the same diagnostic scan that found
    # solar_delta_mw (freq_hz delta: 0.0978, actually the single highest of everything
    # scanned; wind_delta_mw: 0.0361, second among generation sources). Not added
    # alongside solar_delta_mw originally -- only added now after being asked to. Tested
    # empirically before being trusted, same as everything else in this file; see
    # study2_features_notes.md for the verified before/after result.
    df["freq_hz_delta"] = np.where(gap_ok1, df["freq_hz"] - df["freq_hz"].shift(1), np.nan)
    df["wind_delta_mw"] = np.where(gap_ok1, df["wind_mw"] - df["wind_mw"].shift(1), np.nan)

    # rolling stats over the last 8 slots (2 hours) -- only meaningful if the window is
    # actually contiguous, so require the 8th-lag slot to be exactly 8*15min behind.
    window = 8
    prev_dt_w = df["datetime"].shift(window - 1)
    window_ok = (df["datetime"] - prev_dt_w) == pd.Timedelta(minutes=SLOT_MINUTES * (window - 1))
    df["freq_hz_roll8_std"] = np.where(window_ok, df["freq_hz"].rolling(window).std(), np.nan)
    df["demand_delta_roll8_std"] = np.where(window_ok, df["demand_delta_mw"].rolling(window).std(), np.nan)
    df["solar_roll8_std"] = np.where(window_ok, df["solar_mw"].rolling(window).std(), np.nan)
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour"] = df["datetime"].dt.hour
    df["dow"] = df["datetime"].dt.dayofweek
    df["month"] = df["datetime"].dt.month
    df["is_weekend"] = df["dow"].isin([5, 6]).astype(int)
    df["is_solar_hr"] = df["hour"].between(6, 17).astype(int)  # 06:00-18:00 per NLDC's own convention
    return df


def build_study1_residual_signal() -> pd.DataFrame:
    """Backtests Study 1's LightGBM baseline the same way 03_baseline.ipynb does
    (train <=2022, val 2023, predict 2024+) and returns a date-indexed residual
    (actual - forecast). This covers study2_scada's entire Nov 2024-present range.

    Deliberately NOT the live Dataset/predictions/study1_forecast.csv log: that log
    only has real history going back to when predict.py started running
    (2026-07-10), nowhere near enough to cover Study 2's training window. This
    backtest is a single-cutoff approximation of what the live residual signal
    would have looked like over that window (trained once on pre-2024 data, not
    walk-forward retrained day by day) -- an approximation, not a strict
    reproduction of what predict.py would have output on each historical day, but
    the same model/feature pipeline and reusable without a stale committed file.
    """
    import lightgbm as lgb

    TARGET = study1_features.TARGET
    df = pd.read_csv(REPO_ROOT / "Dataset" / "study1_daily.csv", parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    feat_df = study1_features.build_feature_table(df)
    feat_df = study1_features.make_next_day_target(feat_df)

    feature_cols = [c for c in feat_df.columns if
                     c.startswith(f"{TARGET}_lag") or c.startswith(f"{TARGET}_roll") or
                     c in ("dow", "month", "year", "is_weekend", "day_of_year")]
    feat_df = feat_df.dropna(subset=[f"{TARGET}_lag365", TARGET]).reset_index(drop=True)

    train = feat_df[feat_df["year"] <= 2022]
    val = feat_df[feat_df["year"] == 2023]
    test = feat_df[feat_df["year"] >= 2024]

    X_train, y_train = train[feature_cols], train[TARGET] - train[f"{TARGET}_today"]
    X_val, y_val = val[feature_cols], val[TARGET] - val[f"{TARGET}_today"]

    model = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(30, verbose=False)])

    preds = model.predict(test[feature_cols]) + test[f"{TARGET}_today"].values
    out = test[["date"]].copy()
    out["study1_residual_mw"] = test[TARGET].values - preds
    return out.reset_index(drop=True)


def build_feature_table(scada_df: pd.DataFrame, study1_residual: pd.DataFrame = None,
                         violation_lead_slots: int = LEAD_SLOTS) -> pd.DataFrame:
    """Full pipeline: assumes scada_df is the wide study2 frame (the repo's slim
    study2_scada.csv joined with study1_daily by Pipeline/study2_io.load_study2(), or
    the Kaggle copy, which is already joined) with date parsed as datetime and hhmm
    as the minutes-since-midnight integer column.

    violation_lead_slots defaults to LEAD_SLOTS (4) but can be overridden -- used by
    03_violation_baseline.ipynb's shorter-lead-window experiment. ramp_lead's window
    is not similarly parameterized here since that target's baseline already performs
    well and wasn't part of the experiment."""
    df = drop_bad_days(scada_df)
    df = add_datetime(df)
    df = add_violation_label(df, lead_slots=violation_lead_slots)
    df = add_ramp_label(df)
    df = add_slot_lag_features(df)
    df = add_time_features(df)

    if study1_residual is None:
        study1_residual = build_study1_residual_signal()
    df = df.merge(study1_residual, on="date", how="left")

    return df


CORRIDOR_COLS = [c for c in [
    "ir_er_nr_net_mu", "ir_er_wr_net_mu", "ir_er_sr_net_mu", "ir_er_ner_net_mu",
    "ir_ner_nr_net_mu", "ir_wr_nr_net_mu", "ir_wr_sr_net_mu",
    "xb_net_bhutan_mu", "xb_net_nepal_mu", "xb_net_bangladesh_mu", "xb_net_myanmar_mu",
]]

# Kept as a named constant (used directly by 01_eda.ipynb's correlation analysis) even
# though it's excluded from FEATURE_COLS below -- see that exclusion's comment.
DAILY_BROADCAST_COLS = ["share_res_pct"] + CORRIDOR_COLS

FEATURE_COLS = [
    "freq_hz_lag1", "freq_hz_lag2", "freq_hz_lag3",
    "demand_met_mw_lag1", "demand_met_mw_lag2", "demand_met_mw_lag3",
    "freq_hz_roll8_std", "demand_delta_roll8_std", "demand_delta_mw",
    "solar_delta_mw", "solar_roll8_std", "freq_hz_delta", "wind_delta_mw",
    "hour", "dow", "month", "is_weekend", "is_solar_hr",
    "net_trans_exchange_mw", "study1_residual_mw",
]
# freq_hz_delta and wind_delta_mw added 2026-07-11 -- the two next-highest correlations
# with violation_lead from the diagnostic scan that originally found solar_delta_mw
# (freq_hz's own delta: 0.0978, the single highest of anything scanned; wind_delta_mw:
# 0.0361). Tested before adopting: violation_lead PR-AUC 0.1186 -> 0.1567 (+32%),
# ramp_lead PR-AUC 0.7446 -> 0.7486 (smaller but real gain). Both features have
# nonzero, meaningful feature-importance contribution in both models, not just noise
# that happened not to hurt.
# share_res_pct and CORRIDOR_COLS deliberately excluded, found 2026-07-11: both are
# whole-DAY aggregates broadcast identically to all 96 slots of that day (verified --
# every row of a given date has the exact same share_res_pct/ir_*/xb_* value, unlike
# freq_hz/demand_met_mw which genuinely vary per slot). That raised a real question --
# does a whole-day RES-share/corridor figure leak information from LATER in the same
# day into an earlier slot's prediction? Tested directly rather than assumed either way:
# removing these columns from the feature set IMPROVED both classifiers on every metric
# (violation_lead PR-AUC 0.0937 -> 0.1186, +27%; ramp_lead PR-AUC 0.7248 -> 0.7446) --
# so there was no leakage-driven inflation to worry about, and in fact these columns
# were adding noise rather than signal once genuine per-slot features are available.
# Not deleted from the codebase -- CORRIDOR_COLS is still the right tool for descriptive
# correlation work (01_eda.ipynb's corridor-flow-quintile analysis), just not for this
# feature set.


def scale_pos_weight(y: pd.Series) -> float:
    """LightGBM's scale_pos_weight for a binary target.

    NOT used by 03_violation_baseline.ipynb, 04_ramp_shock_baseline.ipynb, or
    predict.py as of 2026-07-11 -- kept here as a documented cautionary utility,
    not deleted, since the reasoning for trying it in the first place (chosen over
    SMOTE: tree boosting should handle class weighting natively, without inventing
    synthetic frequency/demand values) was sound, but empirically it backfired
    badly for the ~2-3% violation_lead target specifically: it caused LightGBM's
    early stopping to fire after a single boosting round (best_iteration_=1) in
    every configuration tested (with/without extra regularization, with/without
    is_unbalance, at multiple learning rates) -- effectively training a single
    shallow tree instead of the intended up-to-500-round ensemble. Removing it
    entirely raised the violation classifier's PR-AUC from 0.0614 to 0.0937 (a
    real, large jump, not noise) and gave a modest but consistent gain on
    ramp_lead too. If a future rare-event target needs class weighting again,
    verify best_iteration_ isn't collapsing to 1 before trusting the result --
    that's what this bug looked like from the outside (a plausible-looking
    PR-AUC, feature importances that were all suspiciously tiny single-digit
    split counts), not an obvious crash."""
    pos = y.sum()
    neg = len(y) - pos
    return float(neg / pos) if pos > 0 else 1.0
