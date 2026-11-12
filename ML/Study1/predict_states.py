"""
predict_states.py -- Daily peak-demand forecast for every state and UT.
Added 2026-11-12.

Same model, horizon (two days past the latest report) and holiday correction
as predict.py and predict_regional.py, one model per state, retrained on every
run, from study3_states.csv's max_demand_met_mw. States use the dashboard's
names (Pipeline/build_dashboard_data.py's STATE_RENAME; DD, DNH and DNHDDPDCL
are summed as "DNH and DD", as the dashboard does), and only states and UTs
are forecast, not bulk consumers or DVC. Logs to
Dataset/predictions/state_forecast.csv, one row per state per target day,
and fills actual_mw / residual_mw once the target day arrives. A state whose
latest day is missing is skipped for that day.

Usage:
    python ML/Study1/predict_states.py                     # latest data day + 2
    python ML/Study1/predict_states.py --date 2026-10-05
    python ML/Study1/predict_states.py --from 2026-09-01   # backfill missing days
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "Pipeline"))

from predict import HORIZON_DAYS, REPO_ROOT, train_and_predict  # noqa: E402
from build_dashboard_data import STATE_RENAME, _is_state  # noqa: E402

STUDY3_CSV = REPO_ROOT / "Dataset" / "study3_states.csv"
LOG = REPO_ROOT / "Dataset" / "predictions" / "state_forecast.csv"
COLS = ["prediction_made_date", "target_date", "state", "predicted_mw", "actual_mw", "residual_mw"]
TARGET = "max_demand_met_mw"


def load_state_series() -> pd.DataFrame:
    """Wide frame: date plus one column of daily peak demand per state/UT."""
    df = pd.read_csv(STUDY3_CSV, parse_dates=["date"])
    df["state"] = df["state"].replace(STATE_RENAME)
    df = df[df["state"].map(_is_state)]
    wide = df.groupby(["date", "state"])[TARGET].sum(min_count=1).unstack("state")
    return wide.sort_index()


def _load_log():
    if LOG.exists():
        return pd.read_csv(LOG, parse_dates=["prediction_made_date", "target_date"])
    return pd.DataFrame(columns=COLS)


def forecast(wide: pd.DataFrame, state: str, made: pd.Timestamp):
    s = wide[state].loc[:made]
    if s.empty or pd.isna(s.iloc[-1]) or s.index[-1] != made:
        return None
    df = pd.DataFrame({"date": s.index, TARGET: s.values})
    f, _, _ = train_and_predict(df, target_col=TARGET)
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("Usage:")[0].strip())
    ap.add_argument("--date")
    ap.add_argument("--from", dest="from_date")
    ap.add_argument("--to", dest="to_date")
    args = ap.parse_args()

    wide = load_state_series()
    days = wide.index
    if args.date:
        made_dates = [pd.Timestamp(args.date)]
    elif args.from_date:
        end = pd.Timestamp(args.to_date) if args.to_date else days[-1]
        made_dates = [d for d in days if pd.Timestamp(args.from_date) <= d <= end]
    else:
        made_dates = [days[-1]]

    log = _load_log()
    have = set(zip(pd.to_datetime(log["target_date"]), log["state"])) if len(log) else set()
    new = []
    for made in made_dates:
        target = made + pd.Timedelta(days=HORIZON_DAYS)
        n = 0
        for state in wide.columns:
            if (target, state) in have:
                continue
            f = forecast(wide, state, made)
            if f is None:
                continue
            new.append({"prediction_made_date": made, "target_date": target, "state": state,
                        "predicted_mw": f, "actual_mw": np.nan, "residual_mw": np.nan})
            n += 1
        print(f"{made.date()} -> {target.date()}: {n} state forecast(s)")

    if new:
        log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    # Fill actuals for any target day that has arrived.
    for i in log.index[log["actual_mw"].isna()]:
        t, st = pd.Timestamp(log.at[i, "target_date"]), log.at[i, "state"]
        if t in wide.index and st in wide.columns and pd.notna(wide.at[t, st]):
            log.at[i, "actual_mw"] = wide.at[t, st]
            log.at[i, "residual_mw"] = wide.at[t, st] - log.at[i, "predicted_mw"]
    log = log.sort_values(["target_date", "state"]).reset_index(drop=True)
    for c in ("prediction_made_date", "target_date"):
        log[c] = pd.to_datetime(log[c]).dt.strftime("%Y-%m-%d")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log[COLS].to_csv(LOG, index=False)
    print(f"Wrote {len(log)} row(s) -> {LOG} ({log['actual_mw'].notna().sum()} scored)")


if __name__ == "__main__":
    main()
