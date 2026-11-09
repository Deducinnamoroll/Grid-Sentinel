# Notes: ML/Study1/predict.py

**Script:** `ML/Study1/predict.py`
**Purpose:** Daily inference for Study 1: produces the next day's national demand forecast (two days past the latest report, see "Horizon"), and maintains a running log of past forecasts vs. what actually happened. Built and wired into CI 2026-07-10, closing out the last deferred piece of Phase 3.

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
| `prediction_made_date` | The latest data day used to make this forecast. CI actually runs one day later, when that day's report is published |
| `target_date` | The date being forecast (always `prediction_made_date + 2` since 2026-11-08; `+ 1` before) |
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
python ML/Study1/predict.py --date 2026-10-05    # data through 2026-10-05 (forecasts 10-07)
python ML/Study1/predict.py --from 2026-09-30    # every day from there to the latest whose forecast is missing (--to caps it)
```

### Backfilling (added 2026-11-08)

Same reason as Study 2: days CI missed during the 2026-09-30 to 2026-11-05 outage have no forecast row. For each requested day the frame is cut at that day before features and training, so the forecast sees only data through that day. Actual and residual are filled in straight away because the target day is already in the data. Safe to repeat: a day whose forecast row exists is skipped. 35 days takes about 20 seconds.

Depends on `pandas`, `numpy`, `lightgbm` (added to CI's pip install list alongside the existing scraping dependencies).

---

## Horizon: two days past the latest report (changed 2026-11-08)

NLDC publishes day D's report during D+1 and CI runs at 16:00 IST, so the newest data on any run is yesterday's. Until 2026-11-08 the script forecast "latest + 1", which is today by the time it ran: published with two-thirds of the target day already gone. It now forecasts `latest + HORIZON_DAYS` (2), which is tomorrow on the day it is published. On 2026-11-08's run (data through 11-07) the forecast is for 11-09.

The target comes from `make_ahead_target()` in `features.py`, which matches target days by date so gaps in the data cannot mispair rows. Backtest cost, from that file's notes: MAPE 1.77% at one day, 2.52% at two days (naive persistence 2.44% and 3.12%).

**The log was rebuilt** at the new horizon so it does not mix two horizons: `python ML/Study1/predict.py --from 2026-07-08`, every forecast cut at its own data day as usual. 123 rows; 121 scored at 2.89% MAPE over 2026-07-10 to 2026-11-07. The old one-day log (104 rows, 1.89%) is in git history before this change.

**Date format fix:** rows appended to an empty log were written as `YYYY-MM-DD 00:00:00`; the script now always writes bare dates.

**Not changed:** Study 2's `study1_residual_mw` feature is built separately in `ML/Study2/features.py` from the one-day target, not from this log, so Study 2 is unaffected.

## Holiday correction (added 2026-11-09)

**Why:** the live forecast for Diwali 2026 (2026-11-08) was 219,919 MW against an actual 195,673 MW, a 12.4% miss. Diwali cuts national peak demand by 12 to 16% every year, and the model's calendar features (day of week, month, day of year) cannot place a festival that follows the lunar calendar. The three worst misses in the live log were all holidays (Diwali, Independence Day, and 14 Sep).

**What:** `HolidayCorrection` in `features.py`. After the model forecasts, the result is multiplied by `(1 + E[target day]) / (1 + E[made day])`, where E is the mean dip that day showed in past years. Each past occurrence is measured as demand against the mean of the same weekday one and two weeks either side. Days are keyed as -3 to +5 around Diwali (the dip lasts several days), else by gazetted holiday name from the `holidays` package (Holi or Dussehra win inside a combined name). 2020 is left out (lockdown); a key needs two past occurrences; only occurrences whose reference days were known on the made day count, so backfills see what the live run would have.

Measured effects (all years to 2026-11-08): Diwali -12.1%, Diwali+1 -14.6%, +2 -12.0%, +3 -7.8%, Holi -10.9%, Dussehra -9.0%, Independence Day -5.0%, Republic Day -4.3%, most others 0 to 3%, Christmas +2.9%.

**Backtest:** walk-forward, targets 2022-01-01 to 2026-11-08, 1,747 forecasts, retrained every 7 days with the live model's settings, training only on days whose outcome was known. MAPE:

| Days | Model alone | Holiday features in the model | Correction (shipped) |
|---|---:|---:|---:|
| All | 2.48 | 2.47 | 2.37 |
| No holiday on either end | 2.25 | 2.25 | 2.25 |
| Holiday at either end | 4.25 | 4.08 | 3.25 |
| Diwali/Holi/Dussehra target | 12.22 | 10.17 | 2.88 |
| Diwali window target | 5.67 | 4.90 | 2.92 |

Holiday features inside LightGBM (target-day and made-day holiday flags, major-festival flag, Diwali offset) were tried first and helped little: there are about four Diwalis in the training data and LightGBM will not split off fewer than 20 rows. A target-only correction (no made-day term) was also tried and lost on the deciding group (3.82% vs 3.25%), mainly two days after Diwali, when the model's anchor is the depressed Diwali day itself. The rule for choosing between the two was fixed before the comparison was run.

Live check with the shipped code: forecast made 2026-11-06 for Diwali gives 195,989 MW (model alone 219,919), actual 195,673. Logged forecasts made before this change were left as published.

**Limits:** regional festivals not on the central list (for example Ganesh Chaturthi, Pongal, Onam) get no correction, and the largest remaining misses are on days just after a holiday when the made day was the holiday.
