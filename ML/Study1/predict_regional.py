"""
predict_regional.py -- Daily peak-demand forecast for each of the five regions
(NR, WR, SR, ER, NER). Added 2026-11-10.

Same model, horizon and holiday correction as predict.py (it calls that
script's train_and_predict with a regional target column), one model per
region, retrained on every run. Logs to
Dataset/predictions/study1_regional_forecast.csv with one row per region per
target day, and fills actual_mw / residual_mw once the target day's data
arrives. Safe to run twice: an existing (target_date, region) row is kept.

Usage:
    python ML/Study1/predict_regional.py                     # latest data day + 2
    python ML/Study1/predict_regional.py --date 2026-10-05
    python ML/Study1/predict_regional.py --from 2026-09-01   # backfill missing days
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from predict import HORIZON_DAYS, REPO_ROOT, STUDY1_CSV, train_and_predict  # noqa: E402

REGIONS = ["nr", "wr", "sr", "er", "ner"]
LOG = REPO_ROOT / "Dataset" / "predictions" / "study1_regional_forecast.csv"
COLS = ["prediction_made_date", "target_date", "region", "predicted_mw", "actual_mw", "residual_mw"]


def _col(region):
    return f"max_demand_met_{region}_mw"


def _load_log():
    if LOG.exists():
        return pd.read_csv(LOG, parse_dates=["prediction_made_date", "target_date"])
    return pd.DataFrame(columns=COLS)


def _fill_actuals(log, df):
    by_date = df.set_index("date")
    for i in log.index[log["actual_mw"].isna()]:
        t, r = log.at[i, "target_date"], log.at[i, "region"]
        if t in by_date.index and pd.notna(by_date.at[t, _col(r.lower())]):
            a = by_date.at[t, _col(r.lower())]
            log.at[i, "actual_mw"] = a
            log.at[i, "residual_mw"] = a - log.at[i, "predicted_mw"]
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("Usage:")[0].strip())
    ap.add_argument("--date")
    ap.add_argument("--from", dest="from_date")
    ap.add_argument("--to", dest="to_date")
    args = ap.parse_args()

    df = pd.read_csv(STUDY1_CSV, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    log = _load_log()
    have = set(zip(pd.to_datetime(log["target_date"]), log["region"])) if len(log) else set()

    days = df["date"]
    if args.date:
        made_dates = [pd.Timestamp(args.date)]
    elif args.from_date:
        end = pd.Timestamp(args.to_date) if args.to_date else days.iloc[-1]
        made_dates = [d for d in days if pd.Timestamp(args.from_date) <= d <= end]
    else:
        made_dates = [days.iloc[-1]]

    new = []
    for made in made_dates:
        target = made + pd.Timedelta(days=HORIZON_DAYS)
        cut = df[df["date"] <= made].reset_index(drop=True)
        for r in REGIONS:
            if (target, r.upper()) in have:
                continue
            if pd.isna(cut[_col(r)].iloc[-1]):
                print(f"{r.upper()}: no data for {made.date()}, skipped")
                continue
            f, _, _ = train_and_predict(cut, target_col=_col(r))
            print(f"{r.upper()} forecast for {target.date()}: {f:,.0f} MW")
            new.append({"prediction_made_date": made, "target_date": target, "region": r.upper(),
                        "predicted_mw": f, "actual_mw": np.nan, "residual_mw": np.nan})

    if new:
        log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    log = _fill_actuals(log, df)
    log = log.sort_values(["target_date", "region"]).reset_index(drop=True)
    for c in ("prediction_made_date", "target_date"):
        log[c] = pd.to_datetime(log[c]).dt.strftime("%Y-%m-%d")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log[COLS].to_csv(LOG, index=False)
    print(f"Wrote {len(log)} row(s) -> {LOG} ({log['actual_mw'].notna().sum()} scored)")


if __name__ == "__main__":
    main()
