"""Real environmental signals: heat stress and dust, per district and day.

Source: Open-Meteo Historical Weather API (ERA5 reanalysis) and Open-Meteo
Air-Quality API (CAMS global). Fetched by ``scripts/fetch_open_meteo.py``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_RAW, HOT_DAY_WBGT


def vapour_pressure_hpa(dew_point_c: pd.Series | np.ndarray) -> np.ndarray:
    """Actual vapour pressure from dew point (Magnus formula)."""
    td = np.asarray(dew_point_c, dtype=float)
    return 6.105 * np.exp(17.27 * td / (237.7 + td))


def wbgt_proxy(temp_c, dew_point_c) -> np.ndarray:
    """Simplified shade WBGT estimate (Australian Bureau of Meteorology formula).

    WBGT ~= 0.567 * T + 0.393 * e + 3.94, with e the vapour pressure in hPa.
    It uses only temperature and humidity, so it is a proxy: it ignores solar load
    and wind. We document this limit and treat it as a relative risk indicator.
    """
    t = np.asarray(temp_c, dtype=float)
    return 0.567 * t + 0.393 * vapour_pressure_hpa(dew_point_c) + 3.94


def load_environment(path=None) -> pd.DataFrame:
    """Return one row per district and day with heat and dust indicators."""
    path = path or DATA_RAW / "open_meteo_daily.csv"
    env = pd.read_csv(path, parse_dates=["date"])
    env = env.sort_values(["district", "date"]).reset_index(drop=True)
    # Daily maximum of the HOURLY WBGT proxy (temperature and dew point at the same
    # hour), computed at fetch time. Falls back to daily values if absent.
    if "wbgt_max_hourly" in env:
        env["wbgt"] = env["wbgt_max_hourly"].astype(float)
    else:
        env["wbgt"] = wbgt_proxy(env["tmax"], env["dewpoint_mean"]).round(2)
    env["log_pm10"] = np.log1p(env["pm10_mean"].clip(lower=0))
    g = env.groupby("district", group_keys=False)
    env["wbgt_3d"] = g["wbgt"].transform(lambda s: s.rolling(3, min_periods=1).mean())
    env["hot_day"] = (env["wbgt"] >= HOT_DAY_WBGT).astype(int)
    # consecutive hot-day streak (resets on a cooler day)
    env["hot_streak"] = g["hot_day"].transform(
        lambda s: s.groupby((s != s.shift()).cumsum()).cumsum() * s
    )
    # Acclimatisation: how many hot days so far this year. Early-season heat is
    # more dangerous because workers are not yet adapted.
    env["year"] = env["date"].dt.year
    env["hot_days_ytd"] = env.groupby(["district", "year"])["hot_day"].cumsum()
    return env.drop(columns=["year"])
