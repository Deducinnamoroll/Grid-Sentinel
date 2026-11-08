# Notes: ML/Study1/predict.py

**Script:** `ML/Study1/predict.py`
**Purpose:** Daily inference for Study 1 — produces tomorrow's national demand forecast, and maintains a running log of past forecasts vs. what actually happened. Built and wired into CI 2026-07-10, closing out the last deferred piece of Phase 3.

---

## In plain English

Every day, once the newest grid report has been downloaded and added to the dataset, this script asks "based on everything we know up to today, what will tomorrow's peak electricity demand be?" — and writes that guess down. The next day, once the real number comes in, it goes back and checks how far off yesterday's guess was. Over time this builds up a track record of predictions vs. reality, which is useful both on its own (how good is the model, really?) and as an input signal for Phase 4's work (a demand forecast that's suddenly way off might itself be an early sign of grid stress).

---

## Why it retrains instead of loading a saved model

The roadmap originally flagged "how do we store a trained model artifact" (Git LFS? a GitHub release asset? commit it directly?) as an open decision. This script sidesteps that decision entirely: training the LightGBM baseline on the full `study1_daily.csv` history takes only a few seconds, so it just retrains from scratch on every run. No model file to version, no risk of a stale cached model quietly drifting out of date as new data arrives — the model is always trained on everything available as of today.

This is different from `03_baseline.ipynb`, which uses a fixed train/val/test split (2019-2022 / 2023 / 2024-2026) to *evaluate* how good the approach is on held-out data. `predict.py` isn't evaluating anything — it trains on every available day (with a 90-day tail held out purely for early stopping, not for scoring) to make the single best live prediction for tomorrow.

---

## What it does

1. Loads `Dataset/study1_daily.csv`, builds features via `ML/Study1/features.py` (`build_feature_table` + `make_next_day_target` — see that file's notes for why the target-shift ordering matters and the anchor bug that was fixed there).
2. The most recent row (today) has no target yet after the shift — that's the live input. Every earlier row with a known outcome becomes a training example.
3. Trains LightGBM with a 90-day validation tail for early stopping, predicts tomorrow, prints the forecast.
4. Reads the existing forecast log (`Dataset/predictions/study1_forecast.csv`), fills in `actual_mw`/`residual_mw` for any past row whose `target_date` now has real data in `study1_daily.csv`, appends today's new forecast (unless one for that date already exists — safe to rerun), and saves.

---

## Output: `Dataset/predictions/study1_forecast.csv`

| Column | Meaning |
|--------|---------|
| `prediction_made_date` | The date whose data was used to make this forecast |
| `target_date` | The date being forecast (always `prediction_made_date + 1`) |
| `predicted_mw` | The forecast, in MW |
| `actual_mw` | Filled in once `target_date` arrives in `study1_daily.csv`; blank until then |
| `residual_mw` | `actual_mw - predicted_mw`, filled in alongside `actual_mw` |

---

## Verified 2026-07-10

- Live run against real data: forecast of 230,889 MW for the next day, well within the range of the preceding 10 days' actuals (225,600–251,114 MW) — plausible, not a sanity-check failure.
- Idempotency: running twice on the same day does not duplicate the forecast row.
- Backfill logic: tested in isolation with a fabricated past prediction against a target date with real data — `residual_mw` computed correctly.

---

## CI wiring

Runs as a step in `.github/workflows/daily_scrape.yml`, after the daily scrape (needs fresh data) and before the commit step (so the forecast log lands in the same commit as the day's data update). Uses `continue-on-error: true` — a forecasting failure must never block the actual data from being committed; the log simply skips a day and catches up next successful run. Not pushed to Kaggle (it's a live application output, not part of the published dataset) — Phase 5's dashboard is expected to read it directly from the GitHub repo.

---

## Usage

```
python ML/Study1/predict.py                      # forecast for tomorrow (daily CI)
python ML/Study1/predict.py --date 2026-10-05    # as if run on 2026-10-05 (forecasts 10-06)
python ML/Study1/predict.py --from 2026-09-30    # every day from there to the latest whose forecast is missing (--to caps it)
```

### Backfilling (added 2026-11-08)

Same reason as Study 2: days CI missed during the 2026-09-30 to 2026-11-05 outage have no forecast row. For each requested day the frame is cut at that day before features and training, so the forecast sees only data through that day. Actual and residual are filled in straight away because the target day is already in the data. Safe to repeat: a day whose forecast row exists is skipped. 35 days takes about 20 seconds.

Depends on `pandas`, `numpy`, `lightgbm` (added to CI's pip install list alongside the existing scraping dependencies).
