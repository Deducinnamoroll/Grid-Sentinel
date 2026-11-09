"""
predict.py -- Daily inference for Study 1 (next-day national demand forecast).

Horizon (changed 2026-11-08): the forecast targets HORIZON_DAYS = 2 days after
the latest day in study1_daily.csv. NLDC publishes day D's report during D+1
and CI runs at 16:00 IST, so a "latest + 1" forecast came out on the very day
it predicted, two-thirds of the way through it. "Latest + 2" comes out the day
before its target, which is what a next-day forecast is for. See
make_ahead_target() in features.py.

Retrains the LightGBM baseline fresh on every run rather than loading a saved
model artifact. Training takes only a few seconds on this dataset size
(~2,700 rows), which sidesteps an open question the roadmap flagged and left
unresolved (how to version/store a trained model -- Git LFS? a GitHub release
asset? commit directly?) by not needing a stored artifact at all. A daily
retrain also means the model always reflects the latest data, with no risk of
a stale cached model silently drifting out of date.

Holiday correction (added 2026-11-09): the model's forecast is scaled by the
dip the same holiday showed in past years, for both the target day and the
made day. See HolidayCorrection in features.py for the method and backtest.

Maintains a persistent forecast/residual log at
Dataset/predictions/study1_forecast.csv:
  - Each run appends a new forecast row for the latest date currently in
    study1_daily.csv + HORIZON_DAYS (tomorrow, as seen on the day CI runs), if not
    already present. prediction_made_date is the latest data day used, not
    the day the run happened (that is one day later).
  - Each run also back-fills actual_mw/residual_mw for any earlier row whose
    target_date has since arrived in study1_daily.csv. This residual signal
    (actual - predicted) is what Phase 4 is designed to consume as an
    anomaly-detection input feature.

Safe to run more than once on the same day: if a forecast for that target
already exists in the log, it's left alone rather than duplicated or
overwritten (matches update_live.py's idempotency convention).

Usage:
    python ML/Study1/predict.py                      # latest data day + 2 (daily CI)
    python ML/Study1/predict.py --date 2026-10-05    # data through 2026-10-05 (forecasts 10-07)
    python ML/Study1/predict.py --from 2026-09-30    # every day from there to the latest
                                                     # whose forecast is missing from the log
                                                     # (--to caps the range)

A backfilled forecast only sees data through its --date day (the frame is cut
there before features and training), so it is what the live run would have output
that day, not a forecast informed by days that had not happened yet.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from features import build_feature_table, make_ahead_target, HolidayCorrection, TARGET  # noqa: E402

STUDY1_CSV = REPO_ROOT / "Dataset" / "study1_daily.csv"
FORECAST_LOG = REPO_ROOT / "Dataset" / "predictions" / "study1_forecast.csv"

# Days between the latest data day and the forecast target. 2 = the day after
# CI publishes the forecast (see the module docstring).
HORIZON_DAYS = 2

FORECAST_COLS = ["prediction_made_date", "target_date", "predicted_mw", "actual_mw", "residual_mw"]

FEATURE_PREFIXES = (f"{TARGET}_lag", f"{TARGET}_roll")
CALENDAR_COLS = ("dow", "month", "year", "is_weekend", "day_of_year")


def _load_log() -> pd.DataFrame:
    if FORECAST_LOG.exists():
        return pd.read_csv(FORECAST_LOG, parse_dates=["prediction_made_date", "target_date"])
    return pd.DataFrame(columns=FORECAST_COLS)


def _backfill_actuals(log: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Fill actual_mw/residual_mw for any past forecast whose target_date now has real data."""
    if log.empty:
        return log
    daily_lookup = daily.set_index("date")[TARGET]
    unresolved = log["actual_mw"].isna()
    for idx in log.index[unresolved]:
        tdate = log.at[idx, "target_date"]
        if tdate in daily_lookup.index:
            actual = daily_lookup.loc[tdate]
            log.at[idx, "actual_mw"] = actual
            log.at[idx, "residual_mw"] = actual - log.at[idx, "predicted_mw"]
    return log


def train_and_predict(df: pd.DataFrame):
    """Returns (forecast_mw, latest_data_date, target_date)."""
    feat_df = build_feature_table(df)
    feat_df = make_ahead_target(feat_df, horizon=HORIZON_DAYS)

    feature_cols = [c for c in feat_df.columns if
                     c.startswith(FEATURE_PREFIXES) or c in CALENDAR_COLS]

    trainable = feat_df.dropna(subset=[f"{TARGET}_lag365"]).reset_index(drop=True)
    train_rows = trainable[trainable[TARGET].notna()]
    predict_row = feat_df.iloc[[-1]]  # latest row: TARGET is NaN here (its target day is in the future)

    if predict_row[f"{TARGET}_lag365"].isna().any():
        raise RuntimeError("Not enough history for the latest row to build lag365 -- cannot predict.")

    # Time-aware holdout for early stopping only -- last 90 days of the trainable range.
    # Not a backtest split (that's what 03_baseline.ipynb is for); this is production
    # training that uses every available day to make the single live prediction.
    cutoff = train_rows["date"].max() - pd.Timedelta(days=90)
    tr = train_rows[train_rows["date"] <= cutoff]
    val = train_rows[train_rows["date"] > cutoff]

    X_train, y_train = tr[feature_cols], tr[TARGET] - tr[f"{TARGET}_today"]
    X_val, y_val = val[feature_cols], val[TARGET] - val[f"{TARGET}_today"]

    model = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, random_state=42, verbosity=-1)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )

    pred_delta = model.predict(predict_row[feature_cols])[0]
    forecast = pred_delta + predict_row[f"{TARGET}_today"].values[0]

    today = pd.Timestamp(predict_row["date"].values[0])
    target = today + pd.Timedelta(days=HORIZON_DAYS)

    # Holiday correction (added 2026-11-09): see HolidayCorrection in features.py.
    corr = HolidayCorrection(df.set_index("date")[TARGET])
    factor = corr.factor(today, target)
    if factor != 1.0:
        print(f"Holiday correction x{factor:.3f} (made day: {corr.key(today) or 'none'}, "
              f"target: {corr.key(target) or 'none'}); model alone said {forecast:,.1f} MW")
    forecast *= factor
    return forecast, today, target


def _select_made_dates(args, df: pd.DataFrame, log: pd.DataFrame) -> list:
    """Days the forecast is 'made on'. Default: the latest day in the data. --date:
    that one day. --from/--to: every data day in the range whose forecast
    (made_date + HORIZON_DAYS) is not in the log yet."""
    days = df["date"]
    latest = days.iloc[-1]
    if args.date:
        day = pd.Timestamp(args.date)
        if day not in set(days):
            print(f"ERROR: {day.date()} is not a day in study1_daily.csv.")
            sys.exit(1)
        return [day]
    if args.from_date:
        start = pd.Timestamp(args.from_date)
        end = pd.Timestamp(args.to_date) if args.to_date else latest
        logged_targets = set(log["target_date"]) if not log.empty else set()
        return [d for d in days
                if start <= d <= end and d + pd.Timedelta(days=HORIZON_DAYS) not in logged_targets]
    return [latest]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("Usage:")[0].strip())
    parser.add_argument("--date", help="Forecast as if run on this day (YYYY-MM-DD) instead of the latest.")
    parser.add_argument("--from", dest="from_date",
                        help="Backfill every day from here (YYYY-MM-DD) whose forecast is missing from the log.")
    parser.add_argument("--to", dest="to_date", help="With --from: last day to backfill (default: latest).")
    args = parser.parse_args()

    if not STUDY1_CSV.exists():
        print(f"ERROR: {STUDY1_CSV} not found. Run the daily scrape / build_all.py first.")
        sys.exit(1)

    df = pd.read_csv(STUDY1_CSV, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    log = _load_log()
    made_dates = _select_made_dates(args, df, log)
    if not made_dates:
        print("Nothing to forecast: every requested day is already in the log.")

    log = _backfill_actuals(log, df)
    for made_date in made_dates:
        forecast, today, target = train_and_predict(df[df["date"] <= made_date].reset_index(drop=True))
        print(f"Prediction made on data through {today.date()}")
        print(f"Forecast for {target.date()}: {forecast:,.1f} MW")

        already_predicted = (log["target_date"] == target).any() if not log.empty else False
        if already_predicted:
            print(f"Forecast for {target.date()} already exists in the log -- not duplicating.")
        else:
            new_row = pd.DataFrame([{
                "prediction_made_date": today,
                "target_date": target,
                "predicted_mw": forecast,
                "actual_mw": np.nan,
                "residual_mw": np.nan,
            }])
            log = pd.concat([log, new_row], ignore_index=True)

    # A backfilled forecast's target day is usually already in the data, so fill its actual now.
    log = _backfill_actuals(log, df)
    log = log.sort_values("target_date").reset_index(drop=True)
    # Rows appended to an empty log are plain Timestamps in an object column,
    # which to_csv writes as "YYYY-MM-DD 00:00:00". Always write bare dates.
    for c in ("prediction_made_date", "target_date"):
        log[c] = pd.to_datetime(log[c]).dt.strftime("%Y-%m-%d")
    FORECAST_LOG.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(FORECAST_LOG, index=False)

    n_backfilled = log["actual_mw"].notna().sum()
    print(f"Wrote {len(log)} row(s) -> {FORECAST_LOG} ({n_backfilled} with a known actual/residual)")


if __name__ == "__main__":
    main()
