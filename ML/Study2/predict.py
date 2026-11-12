"""
predict.py -- Daily inference for Study 2 (frequency-violation + ramp-shock, 1-4-slot
lead-time risk).

Retrains both LightGBM classifiers fresh on every run, same rationale as Study 1's
predict.py: training takes only a few seconds on this dataset size (~57,000 rows),
which sidesteps model-versioning entirely rather than loading a saved artifact.

Unlike Study 1 (a single next-day point forecast), this produces a full 96-slot risk
timeline for the latest complete day in study2_scada.csv -- one violation_prob and
ramp_prob per 15-min slot, not a single number. This is what Phase 5's dashboard
"Study 2 risk" panel is designed to consume (today's slot-by-slot risk timeline).

The model is trained on all days strictly BEFORE the target day (never on the day
being predicted), with a holdout tail for early stopping -- so the target day's
predictions are genuinely out-of-sample, not fit-then-scored-on-itself.

Maintains Dataset/predictions/study2_risk.csv: one row per (date, time) slot with
violation_prob, ramp_prob, and (backfilled once resolvable from later data)
actual_violation, actual_ramp -- computed the same way features.py's lead labels
are computed (any event in the next 1-4 slots), so it stays consistent with how the
model was trained and evaluated in 03/04's baseline notebooks.

Safe to run more than once on the same day: rows for a (date, time) slot already in
the log are left alone rather than duplicated (matches predict.py / update_live.py's
existing idempotency convention).

Usage:
    python ML/Study2/predict.py                      # latest complete day (daily CI)
    python ML/Study2/predict.py --date 2026-10-05    # one specific past day
    python ML/Study2/predict.py --from 2026-09-30    # every day from there to the latest
                                                     # that is missing from the log
                                                     # (--to caps the range)

Backfilling a past day is meant to reproduce what the live run would have output on
that day, so it is not allowed to see anything the live run could not have seen:
the scada table is cut at the target day (so the trailing lead labels of the last
training day are unresolved, exactly as they are live), and Study 1's residual
signal is masked from the target day onward (that residual at date d needs day
d+1's actual demand, which does not exist yet on day d).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from features import build_feature_table, build_study1_residual_signal, fit_platt, FEATURE_COLS  # noqa: E402

# study2_scada.csv is stored slim; load_study2() re-joins study1_daily's columns.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "Pipeline"))
from study2_io import load_study2  # noqa: E402

STUDY2_CSV = REPO_ROOT / "Dataset" / "study2_scada.csv"
RISK_LOG = REPO_ROOT / "Dataset" / "predictions" / "study2_risk.csv"

RISK_COLS = ["date", "time", "violation_prob", "ramp_prob", "actual_violation", "actual_ramp"]

# Early-stopping holdout: last 45 days of the training window (roughly 2x Study 1's
# 90-day holdout in row-count terms, since this data has 96 rows/day).
VAL_DAYS = 45


def _load_log() -> pd.DataFrame:
    if RISK_LOG.exists():
        return pd.read_csv(RISK_LOG, parse_dates=["date"])
    return pd.DataFrame(columns=RISK_COLS)


def _backfill_actuals(log: pd.DataFrame, feat_df: pd.DataFrame) -> pd.DataFrame:
    """Fill actual_violation/actual_ramp for any past row whose lead-time label has
    since become resolvable (i.e. enough later data now exists to know what
    happened in the 1-4 slots after it)."""
    if log.empty:
        return log
    lookup = feat_df.set_index(["date", "time"])[["violation_lead", "ramp_lead"]]
    unresolved = log["actual_violation"].isna()
    for idx in log.index[unresolved]:
        key = (log.at[idx, "date"], log.at[idx, "time"])
        if key in lookup.index:
            row = lookup.loc[key]
            if pd.notna(row["violation_lead"]):
                log.at[idx, "actual_violation"] = row["violation_lead"]
                log.at[idx, "actual_ramp"] = row["ramp_lead"]
    return log


def train_and_predict_day(feat_df: pd.DataFrame, target_day: pd.Timestamp):
    """Trains both classifiers on all days strictly before target_day, predicts
    slot-level probabilities for target_day. Returns a DataFrame with columns
    date, time, violation_prob, ramp_prob."""
    history = feat_df[feat_df["date"] < target_day]
    target_rows = feat_df[feat_df["date"] == target_day]

    if target_rows.empty:
        raise RuntimeError(f"No usable rows for {target_day.date()} (likely a dropped bad day).")

    cutoff = history["date"].max() - pd.Timedelta(days=VAL_DAYS)
    results = {}
    for label_col, out_col in [("violation_lead", "violation_prob"), ("ramp_lead", "ramp_prob")]:
        labeled = history.dropna(subset=[label_col])
        tr = labeled[labeled["date"] <= cutoff]
        val = labeled[labeled["date"] > cutoff]

        # NOT using scale_pos_weight -- found 2026-07-11 (see features.py's
        # scale_pos_weight() docstring) to cause LightGBM's early stopping to fire
        # after a single boosting round for violation_lead specifically, silently
        # training close to a single shallow tree. Removing it and switching the
        # early-stopping metric to average_precision raised violation_lead's PR-AUC
        # from 0.0614 to 0.0937 in the offline baseline notebooks, and gave a
        # smaller but consistent gain on ramp_lead too.
        model = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
        model.fit(
            tr[FEATURE_COLS], tr[label_col],
            eval_set=[(val[FEATURE_COLS], val[label_col])],
            eval_metric="average_precision",
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        # Calibrated on this model's own holdout (the last VAL_DAYS days), so the
        # stated risk tracks the recent event rate. See fit_platt in features.py.
        calibrate = fit_platt(model.predict_proba(val[FEATURE_COLS])[:, 1], val[label_col])
        results[out_col] = calibrate(model.predict_proba(target_rows[FEATURE_COLS])[:, 1])

    out = target_rows[["date", "time"]].copy()
    out["violation_prob"] = results["violation_prob"]
    out["ramp_prob"] = results["ramp_prob"]
    return out.reset_index(drop=True)


def _select_targets(args, valid_days: pd.Series, log: pd.DataFrame) -> list:
    """Which days to predict. Default: just the latest valid day. --date: that one
    day. --from/--to: every valid day in the range that has no rows in the log."""
    latest = valid_days.iloc[-1]
    if args.date:
        day = pd.Timestamp(args.date)
        if day not in set(valid_days):
            print(f"ERROR: {day.date()} is not a usable day in study2_scada.csv "
                  f"(missing or dropped as a bad day).")
            sys.exit(1)
        return [day]
    if args.from_date:
        start = pd.Timestamp(args.from_date)
        end = pd.Timestamp(args.to_date) if args.to_date else latest
        logged = set(log["date"]) if not log.empty else set()
        return [d for d in valid_days if start <= d <= end and d not in logged]
    return [latest]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("Usage:")[0].strip())
    parser.add_argument("--date", help="Predict this one day (YYYY-MM-DD) instead of the latest.")
    parser.add_argument("--from", dest="from_date",
                        help="Backfill every day from here (YYYY-MM-DD) that is missing from the log.")
    parser.add_argument("--to", dest="to_date", help="With --from: last day to backfill (default: latest).")
    args = parser.parse_args()

    if not STUDY2_CSV.exists():
        print(f"ERROR: {STUDY2_CSV} not found. Run the daily scrape / build_all.py first.")
        sys.exit(1)

    scada = load_study2(parse_dates=True)
    scada = scada.sort_values(["date", "time"]).reset_index(drop=True)

    # Built once and reused for every target day: Study 1's residual signal trains its
    # own model, and it is a single-cutoff backtest (train <=2022), so it does not
    # change with how much recent data exists -- only which dates are visible does.
    study1_residual = build_study1_residual_signal()
    feat_df = build_feature_table(scada, study1_residual=study1_residual)  # full table

    valid_days = feat_df["date"].drop_duplicates().sort_values()
    if len(valid_days) < 2:
        print("ERROR: not enough valid days to train on.")
        sys.exit(1)

    log = _load_log()
    targets = _select_targets(args, valid_days, log)
    if not targets:
        print("Nothing to predict: every requested day is already in the log.")

    latest_day = valid_days.iloc[-1]
    new_frames = []
    for target_day in targets:
        if target_day == latest_day:
            day_feat = feat_df  # the live path, unchanged
        else:
            # Reproduce what the live run would have seen on target_day.
            resid = study1_residual.copy()
            resid.loc[resid["date"] >= target_day, "study1_residual_mw"] = np.nan
            day_feat = build_feature_table(scada[scada["date"] <= target_day], study1_residual=resid)

        n_prior = day_feat.loc[day_feat["date"] < target_day, "date"].nunique()
        print(f"Predicting risk timeline for {target_day.date()} (trained on {n_prior} prior days)")
        new_frames.append(train_and_predict_day(day_feat, target_day))

    log = _backfill_actuals(log, feat_df)

    existing_keys = set(zip(log["date"], log["time"])) if not log.empty else set()
    for day_preds in new_frames:
        target_day = day_preds["date"].iloc[0]
        new_rows = day_preds[~day_preds.apply(lambda r: (r["date"], r["time"]) in existing_keys, axis=1)].copy()
        if new_rows.empty:
            print(f"Risk timeline for {target_day.date()} already exists in the log -- not duplicating.")
        else:
            new_rows["actual_violation"] = np.nan
            new_rows["actual_ramp"] = np.nan
            log = pd.concat([log, new_rows[RISK_COLS]], ignore_index=True)
            existing_keys.update(zip(new_rows["date"], new_rows["time"]))

    # Fill actuals again: backfilled days are resolvable straight away.
    log = _backfill_actuals(log, feat_df)

    log = log.sort_values(["date", "time"]).reset_index(drop=True)
    # Rows appended to an empty log are Timestamps in an object column, which
    # to_csv writes as "YYYY-MM-DD 00:00:00" (seen 2026-11-12 when the log was
    # rebuilt from empty). Always write bare dates, as Study 1's log does.
    log["date"] = pd.to_datetime(log["date"]).dt.strftime("%Y-%m-%d")
    RISK_LOG.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(RISK_LOG, index=False)

    n_backfilled = log["actual_violation"].notna().sum()
    print(f"Wrote {len(log)} row(s) -> {RISK_LOG} ({n_backfilled} with a known actual outcome)")
    if new_frames:
        last = new_frames[-1]
        print(f"Last predicted day's peak violation_prob: {last['violation_prob'].max():.4f}, "
              f"peak ramp_prob: {last['ramp_prob'].max():.4f}")


if __name__ == "__main__":
    main()
