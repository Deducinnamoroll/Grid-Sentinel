# Notes: ML/Study2/predict.py

**Script:** `ML/Study2/predict.py`
**Purpose:** Daily inference for Study 2 — produces a full 96-slot frequency-violation and ramp-shock risk timeline for the latest complete day, and maintains a running log of past predictions vs. what actually happened. Built and wired into CI 2026-07-11, closing Phase 4's last deferred item.

---

## In plain English

Study 1's forecast answers one question a day ("what will tomorrow's peak demand be?"). Study 2 is different: the grid can have a problem at any of the 96 fifteen-minute checkpoints in a day, not just once. So instead of one prediction, this script produces 96 of them — for each slot of the most recently completed day, "how likely was a frequency problem or a sudden demand swing in the hour after this slot?" That's the "today's risk timeline" the dashboard (Phase 5) is designed to show. Like Study 1, it goes back later and checks its own past predictions against what actually happened.

---

## Why it predicts a whole day, not just "right now"

The daily scrape (and this CI job) only runs once a day, and by the time it runs, the *entire* previous day's 96 slots have already arrived at once (SCADA data isn't streamed slot-by-slot into this pipeline — see `Scrapings/update_live.py`). So "predict the next slot" isn't meaningful here the way "predict tomorrow" is for Study 1. What the data actually supports is: take the most recently completed day, and for each of its 96 slots, ask what a model trained on everything *before* that day would have predicted for it. That's a genuine out-of-sample prediction (the model never sees the target day during training) and it produces the slot-by-slot timeline Phase 5's dashboard panel needs.

---

## Why it retrains instead of loading a saved model

Same rationale as `ML/Study1/predict.py`: training two LightGBM classifiers on ~57,000 rows takes only a few seconds, so both are retrained from scratch on every run rather than loading a stored artifact. No model file to version, no stale cached model.

---

## What it does

1. Loads `Dataset/study2_scada.csv` through `Pipeline/study2_io.load_study2()`, which joins `study1_daily`'s columns back on (the committed file is slim since 2026-11-10; see `study2_io_notes.md`). Predictions were checked identical before and after that change. It then builds the full feature table via `ML/Study2/features.py` (`build_feature_table`; see `study2_features_notes.md` for the contiguity-guard logic and the Study 1 residual backtest this pulls in).
2. Identifies `target_day` = the latest day that survived `drop_bad_days()` (i.e. wasn't one of the known corrupted-file days).
3. For each of the two targets (`violation_lead`, `ramp_lead`), trains a LightGBM classifier on all days **strictly before** `target_day` (with the last 45 days of that history held out purely for early stopping), then predicts probabilities for `target_day`'s 96 rows. `target_day` itself is never in the training set — these are genuinely out-of-sample predictions, not the model scoring data it was fit on. Training does **not** use `scale_pos_weight` (removed 2026-07-11 — see `study2_features_notes.md`'s `scale_pos_weight()` section: it was silently causing early stopping to stall after a single boosting round for `violation_lead`); early stopping uses `average_precision` as its metric instead of the default `binary_logloss`.
4. Reads the existing risk log (`Dataset/predictions/study2_risk.csv`), backfills `actual_violation`/`actual_ramp` for any past `(date, time)` row whose lead-time label has since become resolvable (enough later data now exists to know what actually happened), appends `target_day`'s new predictions (skipping any `(date, time)` slot already logged — safe to rerun), and saves.

---

## Output: `Dataset/predictions/study2_risk.csv`

| Column | Meaning |
|--------|---------|
| `date`, `time` | The slot being predicted for |
| `violation_prob` | Model's predicted probability of a frequency violation in the next 1-4 slots |
| `ramp_prob` | Model's predicted probability of a ramp-shock in the next 1-4 slots |
| `actual_violation` | Filled in once resolvable from later data; blank until then |
| `actual_ramp` | Filled in alongside `actual_violation` |

---

## Verified 2026-07-11

- Live run against real data: produced a 96-slot risk timeline for 2026-07-09 (peak `violation_prob` 0.156, peak `ramp_prob` 0.905 — both plausible, not degenerate all-zero or all-one outputs).
- Idempotency: running twice back-to-back does not duplicate the day's 96 rows.
- Backfill: on the second run, 95 of 96 slots already had their actual outcome resolved (only the very last slot, 23:45, remained unresolved — correctly, since its lookahead window reaches into the next day's data, which hadn't arrived yet).

---

## CI wiring

Runs as a step in `.github/workflows/daily_scrape.yml`, after Study 1's forecast step and before the commit step, so `study2_risk.csv` lands in the same commit as the day's data update. Uses `continue-on-error: true` for the same reason as Study 1's step — a model failure must never block the day's actual data from being committed. Not pushed to Kaggle (a live application output, not part of the published dataset) — Phase 5's dashboard reads it directly from the repo.

---

## Usage

```
python ML/Study2/predict.py                      # latest complete day (daily CI)
python ML/Study2/predict.py --date 2026-10-05    # one specific past day
python ML/Study2/predict.py --from 2026-09-30    # every day from there to the latest that is missing from the log (--to caps it)
```

### Backfilling (added 2026-11-08)

The daily run only ever predicts the latest day, so any day CI missed (the 2026-09-30 to 2026-11-05 outage) is simply absent from the log and from the dashboard's "Day" dropdown. `--from/--to/--date` fill those in. A backfilled day must be what the live run would have output that day, so it is not allowed to see the future: the scada table is cut at the target day (the last training day's trailing lead labels stay unresolved, as they are live) and Study 1's residual signal is masked from the target day onward (the residual at date d needs day d+1's actual demand). Verified by re-deriving 2026-09-29, which CI logged live: max absolute difference 0.000000 on all 96 slots for both models. Study 1's residual signal and the full feature table are built once per run and reused, so each extra day costs only a few seconds (3 days took 23 seconds total locally, including the one-off setup).

Depends on `pandas`, `numpy`, `lightgbm` (already in CI's pip install list, added when Study 1's `predict.py` was wired in).
