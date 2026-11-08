# Notes: ML/Study1/features.py

**Script:** `ML/Study1/features.py`
**Purpose:** Shared feature-engineering module for Study 1 (daily demand forecasting) — imported by all four notebooks in `ML/Study1/notebooks/` and (once built) `predict.py`, so training-time and inference-time feature logic can never drift apart.

> Documented here in `Pipeline/docs/` rather than an `ML/docs/` folder to keep all "how does a piece of this pipeline work" notes in one place, even though this specific file isn't part of the CSV-building pipeline — it's the ML side's equivalent.

---

## In plain English

Before a computer can learn to predict tomorrow's electricity demand, the raw daily numbers need to be turned into useful clues — things like "what was demand on this exact day last week" or "is today a weekend" (demand is lower on weekends). This file is where all of that clue-building logic lives, written once and reused both when we train the model and later when it makes real predictions — so the model is never trained one way and used a different way by accident.

---

## Why this file exists

Per the Phase 3 design (see `ROADMAP.md`), every reusable transform must live in `features.py`, never pasted inline into a notebook — this is what lets `03_baseline.ipynb`'s training-time feature construction and a future `predict.py`'s inference-time feature construction stay identical by construction instead of by discipline.

---

## What it does

| Function | Does |
|----------|------|
| `drop_out_of_scope_cols()` | Removes `ir_*`/`xb_*` corridor and cross-border columns — out of scope for Study 1's pure demand baseline (only populated from 2023+; reserved for Phase 4's corridor-aware classifier instead) |
| `add_calendar_features()` | `dow`, `month`, `year`, `is_weekend`, `day_of_year` from the `date` column |
| `add_lag_features()` | `{col}_lag1`, `_lag7`, `_lag365` — plain `.shift(lag)` on the target |
| `add_rolling_features()` | `{col}_roll7_mean/std`, `_roll30_mean/std` — `.shift(1).rolling(w)`, so the current day is always excluded from its own rolling stats |
| `build_feature_table()` | Runs the four functions above in order. Does **not** shift the target for next-day prediction — that's a separate, deliberately later step (see below) |
| `make_next_day_target()` | Shifts `TARGET` forward by one row for next-day prediction, added 2026-07-10 (see "Bug found and fixed"). Still used by the notebooks and by Study 2's residual signal |
| `make_ahead_target(df, horizon=2)` | Sets `TARGET` to the value `horizon` calendar days later, matched by date, added 2026-11-08 for the live forecast (see "Two-day horizon") |

---

## Bug found and fixed, 2026-07-10

`03_baseline.ipynb`'s first committed version shifted the target in-place (`feat_df[TARGET] = feat_df[TARGET].shift(-1)`) *after* calling `build_feature_table()`, then used `{TARGET}_lag1` as both the delta-training anchor and the naive-persistence comparison baseline. But `{TARGET}_lag1` was computed *before* that shift, relative to the original target — so after the shift, `lag1` ended up two days behind the new (shifted) target instead of one. This silently weakened the naive-persistence baseline used for comparison.

**Verified empirically** (re-running the pipeline against live data): a correctly-anchored 1-day-lag naive baseline (MAPE 0.0242) actually *beat* the originally-reported LightGBM model (MAPE 0.0247) — meaning the "model beats naive persistence" claim, as first committed, was false.

**Fix:** `make_next_day_target()` shifts the target *and* preserves today's true value as `{col}_today` in the same step, so the correct anchor can never again be silently destroyed by the in-place overwrite. Callers must use `{col}_today`, never `{col}_lag1`, as the naive-persistence baseline and the delta-reconstruction anchor. Re-verified after the fix: LightGBM MAPE 0.0175 vs. correct naive 0.0242 — model genuinely and comfortably wins, by a larger margin than originally (incorrectly) claimed.

**Ordering constraint that makes this correct:** `make_next_day_target()` must run *after* `build_feature_table()`, never before — if the target were shifted first, the lag/rolling features would be built from tomorrow's values instead of today's, which would be actual data leakage (not just a mis-anchored comparison). This is documented directly in the function's docstring so it can't be silently gotten backwards by a future editor.

---

## Usage

```python
from features import build_feature_table, make_next_day_target, TARGET

feat_df = build_feature_table(df)          # lag/rolling/calendar features, target untouched
feat_df = make_next_day_target(feat_df)    # NOW shift target; {TARGET}_today preserved

# Correct anchor for both the delta-target and the naive baseline:
y_train = train[TARGET] - train[f"{TARGET}_today"]
naive_preds = test[f"{TARGET}_today"]
```

No external dependencies beyond `pandas`.

---

## Two-day horizon (added 2026-11-08)

**Problem:** NLDC publishes day D's report during day D+1, and CI runs at 16:00 IST. A forecast for "latest + 1" was therefore published on the day it predicted, two-thirds of the way through it. It was a same-day estimate, not a next-day forecast.

**Fix:** `make_ahead_target(df, horizon=2)`, used by `predict.py`. The target is the demand 2 calendar days after each row, so the live forecast is for the day after it is published.

It matches by **date**, not by row. `study1_daily.csv` has 59 gaps (the latest: 2025-05-22 and 2025-05-23 are missing), and a row shift pairs a day with the wrong target around every gap. With the date match, a row whose target day is missing gets NaN and is dropped from training. `make_next_day_target()` keeps its original row shift so the notebooks and Study 2's `study1_residual_mw` feature reproduce exactly.

Same anchor and ordering rules as above: run it after `build_feature_table()`, anchor on `{TARGET}_today`.

**Cost in accuracy** (same split as `03_baseline.ipynb`: train to 2022, validate 2023, test 2024 onward, both horizons using the date-matched target):

| Horizon | Test days | Model MAPE | Naive (repeat latest day) | Days within 2% |
|---------|-----------|------------|---------------------------|----------------|
| 1 day | 1,038 | 1.77% | 2.44% | 67% |
| 2 days | 1,036 | 2.52% | 3.12% | 50% |

The extra day costs about 0.75 points of MAPE; the model still beats naive persistence at both horizons.
