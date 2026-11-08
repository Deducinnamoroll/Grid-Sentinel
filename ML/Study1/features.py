"""ML/Study1/features.py — shared feature engineering, reused by notebooks + predict.py"""

import pandas as pd

TARGET = "max_demand_met_total_mw"

# Corridor/cross-border cols excluded from Phase 3 baseline (only populated from 2023+,
# out of scope for pure demand forecasting — revisit only if feature importance calls for it)
EXCLUDE_PREFIXES = ("ir_", "xb_")


def drop_out_of_scope_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if not c.startswith(EXCLUDE_PREFIXES)]
    return df[cols]


def add_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df["dow"] = df[date_col].dt.dayofweek
    df["month"] = df[date_col].dt.month
    df["year"] = df[date_col].dt.year
    df["is_weekend"] = df["dow"].isin([5, 6]).astype(int)
    df["day_of_year"] = df[date_col].dt.dayofyear
    return df


def add_lag_features(df: pd.DataFrame, col: str = TARGET, lags=(1, 7, 365)) -> pd.DataFrame:
    df = df.copy()
    for lag in lags:
        df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, col: str = TARGET, windows=(7, 30)) -> pd.DataFrame:
    df = df.copy()
    for w in windows:
        df[f"{col}_roll{w}_mean"] = df[col].shift(1).rolling(w).mean()
        df[f"{col}_roll{w}_std"] = df[col].shift(1).rolling(w).std()
    return df


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    """Full pipeline: assumes df sorted by date ascending, date column parsed as datetime.

    Does NOT shift the target for next-day prediction -- call
    make_next_day_target() on the result before training, so lag/rolling
    features here are always computed relative to the true historical
    target, never the shifted one.
    """
    df = drop_out_of_scope_cols(df)
    df = add_calendar_features(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    return df


def make_next_day_target(df: pd.DataFrame, col: str = TARGET) -> pd.DataFrame:
    """
    Prepares a next-day forecasting target. Must run AFTER build_feature_table(),
    since it destructively overwrites `col` -- if lag/rolling features were
    computed after this call instead of before, they'd be built from tomorrow's
    values instead of today's.

    Preserves today's actual value as f"{col}_today" before overwriting `col`
    with tomorrow's value. f"{col}_today" is the correct anchor for both the
    naive-persistence baseline and for reconstructing an absolute prediction
    from a delta-target model (pred = model_output + {col}_today).

    Do NOT use f"{col}_lag1" for either purpose here: lag1 was computed
    relative to the *original* (pre-shift) target, so once `col` itself has
    been shifted forward by one day, lag1 ends up two days behind the new
    target instead of one -- silently weakening any naive-persistence
    comparison and mis-anchoring any delta-target reconstruction. This bug
    was found and fixed in Study 1's baseline (2026-07-10): the naive
    persistence baseline computed via lag1 was actually *beaten* by a
    correctly-anchored naive baseline, invalidating the original "model
    beats naive persistence" result until this fix.
    """
    df = df.copy()
    df[f"{col}_today"] = df[col]
    df[col] = df[col].shift(-1)
    return df


def make_ahead_target(df: pd.DataFrame, horizon: int = 2, col: str = TARGET,
                      date_col: str = "date") -> pd.DataFrame:
    """
    Like make_next_day_target(), but `horizon` calendar days ahead, matched
    by DATE rather than by row. Used by predict.py for the live forecast
    (added 2026-11-08).

    Why a horizon of 2: NLDC publishes day D's report during day D+1, and
    the daily CI run (16:00 IST) only sees it then. A forecast for D+1 is
    therefore published on D+1 itself, with most of that day already gone.
    Forecasting D+2 makes the published number a genuine next-day forecast:
    on the day it appears, its target is tomorrow.

    Why by date: study1_daily.csv has 59 gaps (the latest: 2025-05-22 and
    2025-05-23 are missing). shift(-horizon) would pair a row with whatever row happens
    to sit `horizon` places later, i.e. the wrong day around every gap.
    Here a row whose target day is missing simply gets NaN and drops out of
    training. make_next_day_target() keeps its row-based shift unchanged so
    the notebooks and Study 2's residual signal reproduce exactly.

    Same anchor rule as make_next_day_target(): run AFTER
    build_feature_table(), and anchor on f"{col}_today", never on lag1.
    """
    df = df.copy()
    df[f"{col}_today"] = df[col]
    by_date = df.set_index(date_col)[col]
    df[col] = (df[date_col] + pd.Timedelta(days=horizon)).map(by_date).values
    return df
