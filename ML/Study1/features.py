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


class HolidayCorrection:
    """
    Scales a forecast by how much demand dipped on the same holiday in past
    years. Added 2026-11-09 after the live forecast missed Diwali 2026 by
    12.4%: the model has no idea a festival is coming, and festivals that
    follow the lunar calendar move by up to three weeks a year.

    Why a correction and not model features: festivals are rare (one Diwali a
    year), and LightGBM will not split off fewer than 20 rows, so holiday
    features barely moved the trees. A walk-forward backtest over 2022 to
    2026 (1,747 forecasts, retrained weekly) gave, as MAPE:
        Diwali/Holi/Dussehra target days   12.2% -> 2.9%  (features: 10.2%)
        Diwali window (-3 to +5 days)       5.7% -> 2.9%  (features:  4.9%)
        all days                            2.48% -> 2.37%
        days with no holiday on either end  2.25% -> 2.25% (untouched)
    See Pipeline/docs/study1_predict_notes.md.

    Keys: days -3 to +5 around Diwali (the dip lasts several days: about
    -4%, -12%, -15%, -12%, -8% from the day before to three days after), then
    the gazetted holiday name, with Holi or Dussehra winning inside a combined
    name ("Dussehra; Mahatma Gandhi's Jayanti"). Dates come from the
    `holidays` package (India's gazetted central list).

    Effect of one past occurrence: demand / mean demand on the same weekday 1
    and 2 weeks either side (non-holiday days only), minus 1. 2020 is left out
    (lockdown). A key needs at least MIN_PAST occurrences, and only those whose
    reference days were known on the made day count, so a backfilled forecast
    sees what the live run would have seen.
    """

    DIWALI_WINDOW = (-3, 5)
    EXCLUDE_YEARS = (2020,)
    MIN_PAST = 2

    def __init__(self, series: pd.Series):
        """series: the target column indexed by date (all data up to the made day)."""
        import holidays  # imported here so the notebooks don't need it

        years = range(series.index.min().year - 1, series.index.max().year + 3)
        self.hol = {pd.Timestamp(d): n for d, n in holidays.India(years=years).items()}
        self.diwalis = sorted(d for d, n in self.hol.items() if "Diwali" in n)
        # Every keyed day, built once (about 20 a year). Looking keys up here,
        # instead of testing each of the ~2,800 days in the series, took the
        # constructor from about 2.3 s to a few ms (2026-11-12), which matters
        # with one correction per state per day. Diwali window first, so it wins
        # over a holiday on the same day, as before.
        lo, hi = self.DIWALI_WINDOW
        self._keys = {}
        for d in self.diwalis:
            for k in range(lo, hi + 1):
                self._keys.setdefault(d + pd.Timedelta(days=k), f"diwali{k:+d}")
        for t, name in self.hol.items():
            if t not in self._keys:
                fest = next((f for f in ("Holi", "Dussehra") if f in name), None)
                self._keys[t] = fest or name.split("; ")[0].split(" (")[0]
        rows = []
        valid = series.dropna()
        for t in sorted(self._keys):
            if t not in valid.index or t.year in self.EXCLUDE_YEARS:
                continue
            refs = [t + pd.Timedelta(days=j) for j in (-14, -7, 7, 14)]
            refs = [x for x in refs if x in series.index and x not in self._keys]
            ref_vals = series.reindex(refs).dropna()
            if len(ref_vals) >= 2:
                rows.append((self._keys[t], t, valid[t] / ref_vals.mean() - 1))
        self.occ = pd.DataFrame(rows, columns=["key", "t", "eff"])

    def key(self, t):
        return self._keys.get(pd.Timestamp(t))

    def expected(self, t, made) -> float:
        k = self.key(t)
        if not k:
            return 0.0
        past = self.occ[(self.occ.key == k) & (self.occ.t + pd.Timedelta(days=14) <= made)]
        return float(past.eff.mean()) if len(past) >= self.MIN_PAST else 0.0

    def factor(self, made, target) -> float:
        """Multiply the model's forecast by this. Divides out the made day's own
        dip too: the model forecasts a change from the made day, so a holiday
        anchor drags the forecast down (backtest: 3.25% vs 3.82% MAPE on days
        with a holiday at either end, against target-only)."""
        return (1 + self.expected(target, made)) / (1 + self.expected(made, made))


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


def build_feature_table(df: pd.DataFrame, col: str = TARGET) -> pd.DataFrame:
    """Full pipeline: assumes df sorted by date ascending, date column parsed as datetime.
    `col` is the series the lag/rolling features describe (the national peak by
    default; a regional peak for the regional forecast, added 2026-11-10).

    Does NOT shift the target for next-day prediction -- call
    make_next_day_target() on the result before training, so lag/rolling
    features here are always computed relative to the true historical
    target, never the shifted one.
    """
    df = drop_out_of_scope_cols(df)
    df = add_calendar_features(df)
    df = add_lag_features(df, col=col)
    df = add_rolling_features(df, col=col)
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
