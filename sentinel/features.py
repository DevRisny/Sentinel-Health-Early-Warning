"""Expected values, deviation scores, events and the model feature table.

Every feature for day t uses only what a health team would actually hold at the end
of day t: reported feeds arrive with a lag (config.REPORTING_LAG), and the next two
days of weather come from a forecast with realistic error, never from the future.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

from .config import (
    ALERT_HORIZON_DAYS,
    FORECAST_SD,
    RANDOM_SEED,
    REPORTING_LAG,
    SITE_CLUSTERS,
    TRAIN_END,
    HEAT_REF_WBGT,
)
from .simulate import _in_ban

SIGNALS = ["hri", "resp", "allcause", "incidents", "absent"]
EVENT_QUANTILE = 0.98
EVENT_MIN_COUNT = 8


# --------------------------------------------------------------------------- baselines
def _seasonal_design(df: pd.DataFrame) -> np.ndarray:
    doy = df["date"].dt.dayofyear.to_numpy() / 365.25
    dow = df["date"].dt.dayofweek.to_numpy()
    cols = [np.sin(2 * np.pi * doy), np.cos(2 * np.pi * doy), np.sin(4 * np.pi * doy), np.cos(4 * np.pi * doy)]
    cols += [(dow == d).astype(float) for d in range(1, 7)]
    cols.append(df["holiday"].to_numpy(dtype=float))
    return np.column_stack(cols)


def fit_expected(rep: pd.DataFrame) -> pd.DataFrame:
    """Learn what is NORMAL for each signal, cluster, season and weekday.

    A Poisson regression on the training period only (seasonal harmonics, weekday,
    holiday). It deliberately has no weather terms: deviations from it are what we
    want to detect. Returns expected counts and a robust spread for every row.
    """
    out = rep[["date", "cluster"]].copy()
    train_mask = rep["date"] <= TRAIN_END
    for sig in SIGNALS:
        exp_col = np.full(len(rep), np.nan)
        for cl, idx in rep.groupby("cluster").groups.items():
            idx = np.asarray(list(idx))
            sub = rep.loc[idx]
            X = _seasonal_design(sub)
            denom = sub["on_shift"].to_numpy(dtype=float)
            y = sub[sig].to_numpy(dtype=float) / denom
            fit_rows = train_mask.loc[idx].to_numpy() & ~np.isnan(y)
            m = PoissonRegressor(alpha=1e-4, max_iter=500)
            m.fit(X[fit_rows], y[fit_rows], sample_weight=denom[fit_rows])
            exp_col[np.searchsorted(rep.index, idx)] = m.predict(X) * denom
        out[f"{sig}_exp"] = exp_col
        # over-dispersion factor estimated on training residuals, per signal
        obs = rep[sig].to_numpy(dtype=float)
        resid = (obs - exp_col) / np.sqrt(np.clip(exp_col, 0.5, None))
        phi = np.nanvar(resid[train_mask.to_numpy()])
        out[f"{sig}_z"] = resid / np.sqrt(max(phi, 1.0))
    return out


# -------------------------------------------------------------------------------- events
def define_events(sim: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Health-burden events from TRUE (unmasked) counts.

    Burden = heat-illness + respiratory visits, summed over a centred 3-day window
    (smooths single-day noise). An event day has a burden rate above the cluster's
    98th percentile in the training period AND at least EVENT_MIN_COUNT visits in the
    window, so tiny sites cannot trigger "events" from one or two cases. Event days
    separated by at most 2 days form one event; its peak is the highest-burden day.
    """
    df = sim[["date", "cluster", "workforce", "hri", "resp"]].copy()
    cnt = df["hri"] + df["resp"]
    df["burden_3d"] = cnt.groupby(df["cluster"]).transform(lambda s: s.rolling(3, center=True, min_periods=1).sum())
    df["burden_rate"] = df["burden_3d"] / df["workforce"] * 10_000
    thr = df[df["date"] <= TRAIN_END].groupby("cluster")["burden_rate"].quantile(EVENT_QUANTILE).rename("event_thr")
    df = df.join(thr, on="cluster")
    df["event_day"] = ((df["burden_rate"] >= df["event_thr"]) & (df["burden_3d"] >= EVENT_MIN_COUNT)).astype(int)
    df["event_id"] = ""
    rows = []
    for cl, g in df.groupby("cluster"):
        days = g.loc[g["event_day"] == 1, "date"].sort_values().tolist()
        runs: list[list[pd.Timestamp]] = []
        for d in days:
            if runs and (d - runs[-1][-1]).days <= 3:
                runs[-1].append(d)
            else:
                runs.append([d])
        for i, run in enumerate(runs):
            eid = f"{cl}#{i:03d}"
            sub = g[(g["date"] >= run[0]) & (g["date"] <= run[-1])]
            peak = sub.loc[sub["burden_rate"].idxmax(), "date"]
            df.loc[sub.index, "event_id"] = eid
            df.loc[sub.index, "event_day"] = 1  # fill short gaps inside an event
            rows.append({"event_id": eid, "cluster": cl, "start": run[0], "end": run[-1], "peak": peak,
                         "peak_burden_rate": float(sub["burden_rate"].max())})
    return df, pd.DataFrame(rows)


def label_next_days(event_days: pd.DataFrame, horizon: int = ALERT_HORIZON_DAYS) -> pd.Series:
    """y(t) = 1 if an event day occurs in t+1 .. t+horizon (same cluster)."""
    y = pd.Series(0, index=event_days.index)
    for _, g in event_days.groupby("cluster"):
        ev = g["event_day"].to_numpy()
        fut = np.zeros(len(ev), dtype=int)
        for h in range(1, horizon + 1):
            fut = np.maximum(fut, np.r_[ev[h:], np.zeros(h, dtype=int)])
        y.loc[g.index] = fut
    return y


# ------------------------------------------------------------------------------ features
def _lag(g: pd.Series, k: int) -> pd.Series:
    return g.shift(k)


def build_features(env: pd.DataFrame, rep: pd.DataFrame, expected: pd.DataFrame,
                   seed: int = RANDOM_SEED + 7, lag_override: dict | None = None,
                   drop_groups: tuple[str, ...] = ()) -> pd.DataFrame:
    """Assemble the model table: one row per cluster and day."""
    rng = np.random.default_rng(seed)
    lags = {**REPORTING_LAG, **(lag_override or {})}

    # --- forecast of the next two days (true future + realistic forecast error) ---
    env = env.sort_values(["district", "date"]).copy()
    for h, sd_w, sd_p in [(1, FORECAST_SD["wbgt"][0], FORECAST_SD["pm10"][0]),
                          (2, FORECAST_SD["wbgt"][1], FORECAST_SD["pm10"][1])]:
        g = env.groupby("district")
        env[f"fc_wbgt_d{h}"] = g["wbgt"].shift(-h) + rng.normal(0, sd_w, len(env))
        env[f"fc_logpm10_d{h}"] = g["log_pm10"].shift(-h) + rng.normal(0, sd_p, len(env))
    env["fc_wbgt_max"] = env[["fc_wbgt_d1", "fc_wbgt_d2"]].max(axis=1)
    env["fc_logpm10_max"] = env[["fc_logpm10_d1", "fc_logpm10_d2"]].max(axis=1)

    df = rep.merge(expected, on=["date", "cluster"]).merge(
        env[["date", "district", "wbgt", "wbgt_3d", "hot_streak", "hot_days_ytd", "log_pm10", "pm10_mean",
             "tmax", "dewpoint_mean", "fc_wbgt_d1", "fc_wbgt_d2", "fc_wbgt_max", "fc_logpm10_d1",
             "fc_logpm10_d2", "fc_logpm10_max"]],
        on=["date", "district"],
    )
    df = df.sort_values(["cluster", "date"]).reset_index(drop=True)
    sc = {c.code: c for c in SITE_CLUSTERS}
    df["outdoor_share"] = df["cluster"].map({k: v.outdoor_share for k, v in sc.items()})
    df["log_workforce"] = np.log(df["workforce"])
    df["in_ban"] = _in_ban(df["date"]).astype(int)
    doy = df["date"].dt.dayofyear / 365.25
    df["season_sin"], df["season_cos"] = np.sin(2 * np.pi * doy), np.cos(2 * np.pi * doy)

    g = df.groupby("cluster", group_keys=False)
    feed_lag = {"hri": lags["clinic"], "resp": lags["clinic"], "allcause": lags["clinic"],
                "incidents": lags["incidents"], "absent": lags["absence"]}
    for sig, k in feed_lag.items():
        z = df[f"{sig}_z"]
        zl = g[f"{sig}_z"].shift(k)
        df[f"{sig}_z_last"] = zl
        df[f"{sig}_z_3d"] = zl.groupby(df["cluster"]).transform(lambda s: s.rolling(3, min_periods=1).mean())
        df[f"{sig}_z_slope"] = zl.groupby(df["cluster"]).transform(lambda s: s.diff(2))
        rate = df[sig] / df["on_shift"] * 10_000
        df[f"{sig}_rate_last"] = rate.groupby(df["cluster"]).shift(k)
        del z
    # Spatial signal: how unusual are the clinic feeds across the whole district?
    for sig in ("hri", "resp"):
        df[f"district_{sig}_z"] = df.groupby(["district", "date"])[f"{sig}_z_last"].transform("mean")
        df[f"{sig}_z_7d"] = df.groupby("cluster")[f"{sig}_z_last"].transform(lambda s: s.rolling(7, min_periods=2).mean())
    # CUSUM: the classic surveillance statistic that accumulates small, persistent
    # excesses (k = 0.5 SD allowance), so slow build-ups are seen before any single day is extreme.
    for sig in ("hri", "resp", "incidents", "absent"):
        zl = df[f"{sig}_z_last"].fillna(0).to_numpy()
        cus = np.zeros(len(df))
        cl = df["cluster"].to_numpy()
        for i in range(len(df)):
            prev = cus[i - 1] if i and cl[i] == cl[i - 1] else 0.0
            cus[i] = max(0.0, prev + zl[i] - 0.5)
        df[f"{sig}_cusum"] = cus
    # Heat exposure that matters: forecast heat above reference, scaled by outdoor work
    df["fc_heat_load"] = (df["fc_wbgt_max"] - HEAT_REF_WBGT).clip(lower=0) * df["outdoor_share"] * (1 - 0.3 * df["in_ban"])
    avail = df["hri"].notna().astype(float).groupby(df["cluster"]).shift(lags["clinic"])
    df["clinic_completeness_7d"] = avail.groupby(df["cluster"]).transform(lambda s: s.rolling(7, min_periods=1).mean())

    if drop_groups:
        for col in feature_columns():
            if FEATURE_GROUP[col] in drop_groups:
                df[col] = np.nan
        if "Heat so far" in drop_groups:
            df["wbgt"] = np.nan
    return df


FEATURE_GROUP: dict[str, str] = {
    "fc_heat_load": "Heat forecast", "fc_wbgt_d1": "Heat forecast", "fc_wbgt_d2": "Heat forecast", "fc_wbgt_max": "Heat forecast",
    "wbgt": "Heat so far", "wbgt_3d": "Heat so far", "hot_streak": "Heat so far",
    "hot_days_ytd": "Acclimatisation", "in_ban": "Acclimatisation",
    "season_sin": "Season", "season_cos": "Season",
    "log_pm10": "Dust", "fc_logpm10_d1": "Dust", "fc_logpm10_d2": "Dust", "fc_logpm10_max": "Dust",
    "hri_z_last": "Heat-illness visits", "hri_cusum": "Heat-illness visits", "hri_z_3d": "Heat-illness visits", "hri_z_slope": "Heat-illness visits",
    "hri_rate_last": "Heat-illness visits",
    "hri_z_7d": "Heat-illness visits", "district_hri_z": "Heat-illness visits",
    "resp_z_last": "Respiratory visits", "resp_cusum": "Respiratory visits", "resp_z_3d": "Respiratory visits", "resp_z_slope": "Respiratory visits",
    "resp_rate_last": "Respiratory visits",
    "resp_z_7d": "Respiratory visits", "district_resp_z": "Respiratory visits",
    "allcause_z_last": "All-cause visits", "allcause_z_3d": "All-cause visits",
    "incidents_z_last": "Incident reports", "incidents_cusum": "Incident reports", "incidents_z_3d": "Incident reports", "incidents_rate_last": "Incident reports",
    "absent_z_last": "Sickness absence", "absent_cusum": "Sickness absence", "absent_z_3d": "Sickness absence", "absent_z_slope": "Sickness absence",
    "outdoor_share": "Site profile", "log_workforce": "Site profile",
    "clinic_completeness_7d": "Data completeness",
}

SIGNAL_FAMILY = {
    "Heat forecast": "environmental", "Heat so far": "environmental", "Acclimatisation": "environmental",
    "Season": "environmental", "Dust": "environmental",
    "Heat-illness visits": "service", "Respiratory visits": "service", "All-cause visits": "service",
    "Incident reports": "workplace", "Sickness absence": "workplace",
    "Site profile": "context", "Data completeness": "context",
}


def feature_columns() -> list[str]:
    return list(FEATURE_GROUP)
