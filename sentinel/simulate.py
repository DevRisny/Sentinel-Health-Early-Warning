"""Synthetic clinic, absence and incident feeds (clearly labelled SYNTHETIC).

The organisers provide no data, and real occupational-health records are personal
data. Sentinel therefore drives a documented generator with REAL weather and dust
data. Each relationship below is a simple, published-direction assumption (see
docs/DATA_SHEET.md), not a fitted clinical model.

Design goals of the generator:
  * heat illness rises non-linearly with heat stress, more for outdoor work, and
    more early in the season before workers acclimatise;
  * respiratory visits rise with dust (PM10) with a 0-1 day lag;
  * the UAE midday outdoor-work ban (15 Jun - 15 Sep) reduces exposure;
  * weekends and Eid holidays change who is at work and who reports;
  * hidden scenarios (config.EPISODES) add events the weather alone cannot explain,
    plus "look-alike" spikes that should NOT raise a heat/dust alert;
  * real-world mess: over-dispersion, missing days, a feed outage, reporting lag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    DUST_REF_PM10,
    EPISODES,
    HEAT_REF_WBGT,
    MIDDAY_BAN,
    MIDDAY_BAN_EXPOSURE_FACTOR,
    RANDOM_SEED,
    SITE_CLUSTERS,
)

# Approximate public-holiday dates (Eid al-Fitr / Eid al-Adha, +-1 day accuracy).
EID_STARTS = ["2024-04-09", "2024-06-15", "2025-03-30", "2025-06-05", "2026-03-19", "2026-05-26"]
EID_DAYS = 4

NB_SHAPE = 8.0  # gamma-Poisson over-dispersion (smaller = noisier)


def _holiday_mask(dates: pd.Series) -> np.ndarray:
    hol = np.zeros(len(dates), dtype=bool)
    for s in EID_STARTS:
        start = pd.Timestamp(s)
        hol |= ((dates >= start) & (dates < start + pd.Timedelta(days=EID_DAYS))).to_numpy()
    return hol


def _in_ban(dates: pd.Series) -> np.ndarray:
    (m1, d1), (m2, d2) = MIDDAY_BAN
    md = dates.dt.month * 100 + dates.dt.day
    return ((md >= m1 * 100 + d1) & (md <= m2 * 100 + d2)).to_numpy()


def _nb(rng: np.random.Generator, lam: np.ndarray) -> np.ndarray:
    lam = np.clip(lam, 1e-6, None)
    return rng.poisson(rng.gamma(NB_SHAPE, lam / NB_SHAPE))


def _episode_effects(dates: pd.Series, cluster: str, workforce: int):
    """Extra expected cases per day (additive) from the hidden scenarios.

    Effects are additive in cases, scaled gently with site size, because a scenario
    such as a new crew of 150 unacclimatised workers adds cases on top of the usual
    seasonal load rather than multiplying it.
    """
    n = len(dates)
    add = {k: np.zeros(n) for k in ("hri", "resp", "incidents")}
    allcause_mult = np.ones(n)
    absence_add = np.zeros(n)
    scale = np.sqrt(workforce / 4000.0)
    for ep in EPISODES:
        if ep.cluster != cluster:
            continue
        start = pd.Timestamp(ep.start)
        for k in range(-2, ep.days + 1):
            idx = np.flatnonzero((dates == start + pd.Timedelta(days=k)).to_numpy())
            if not len(idx):
                continue
            i, s = idx[0], ep.strength * scale
            ramp = min(1.0, max(0.0, (k + 1) / ep.days))  # slow build to a peak near the end
            inside = 0 <= k < ep.days
            if ep.kind == "new_intake":
                if k == -1:
                    add["hri"][i] += 0.8 * s          # first mild cases among new arrivals
                    add["incidents"][i] += 0.8 * s     # early first-aid reports
                elif inside:
                    add["hri"][i] += s * (1.5 + 5.0 * ramp)
                    add["incidents"][i] += s * (0.5 + 1.5 * ramp)
                    absence_add[i] += 0.004 * ep.strength * ramp
            elif ep.kind == "water_failure":
                if k == -1:
                    add["incidents"][i] += 2.5 * s     # supply / equipment complaints
                    add["hri"][i] += 1.0 * s
                elif inside:
                    add["hri"][i] += 6.0 * s
                    add["incidents"][i] += 2.0 * s
                    absence_add[i] += 0.006 * ep.strength
            elif ep.kind == "heat_vuln":
                if k == -1:
                    add["hri"][i] += 1.0 * s
                elif inside:
                    add["hri"][i] += s * (2.0 + 4.5 * ramp)
                    add["incidents"][i] += s * 1.0 * ramp
                    absence_add[i] += 0.004 * ep.strength * ramp
            elif ep.kind == "dust":
                if k == -1:
                    add["resp"][i] += 1.5 * s
                elif inside:
                    add["resp"][i] += s * (3.0 + 6.0 * ramp)
                    absence_add[i] += 0.004 * ep.strength * max(ramp, 0.3)
            elif ep.kind == "lookalike" and inside:
                allcause_mult[i] *= 1 + 1.4 * ep.strength
                absence_add[i] += 0.025 * ep.strength
    return add, allcause_mult, absence_add


def simulate(env: pd.DataFrame, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Simulate daily feeds for every site cluster from the real environment table."""
    rng = np.random.default_rng(seed)
    frames = []
    for sc in SITE_CLUSTERS:
        e = env[env["district"] == sc.district].sort_values("date").reset_index(drop=True)
        dates = e["date"]
        dow = dates.dt.dayofweek.to_numpy()  # Mon=0 .. Sun=6 (UAE weekend: Sat-Sun)
        holiday = _holiday_mask(dates)
        shift = np.where(dow == 5, 0.55, np.where(dow == 6, 0.35, np.where(dow == 4, 0.85, 1.0)))
        shift = np.where(holiday, 0.25, shift)
        on_shift = np.round(sc.workforce * shift).astype(int)

        exposure = sc.outdoor_share * np.where(_in_ban(dates), MIDDAY_BAN_EXPOSURE_FACTOR, 1.0)
        acclim = 1.0 + 0.9 * np.exp(-e["hot_days_ytd"].to_numpy() / 18.0)
        heat_x = np.clip(e["wbgt"].to_numpy() - HEAT_REF_WBGT, 0, None)
        heat_3d = np.clip(e["wbgt_3d"].to_numpy() - HEAT_REF_WBGT, 0, None)
        pm10 = e["pm10_mean"].to_numpy()
        pm_lag = (pm10 + np.r_[pm10[0], pm10[:-1]]) / 2  # 0-1 day lag
        dust_x = np.clip(np.log(np.clip(pm_lag, 1, None) / DUST_REF_PM10), 0, None)

        per10k = on_shift / 10_000
        lam_hri = per10k * (
            0.25 + 1.6 * exposure * sc.vulnerability * acclim * (np.exp(0.22 * heat_x + 0.08 * heat_3d) - 1)
        )
        lam_resp = per10k * (2.2 + 4.0 * (0.4 + sc.outdoor_share) * dust_x)
        lam_all = per10k * 14.0
        lam_inc = 0.18 * lam_hri + per10k * 0.15

        add, allcause_mult, absence_add = _episode_effects(dates, sc.code, sc.workforce)
        hri = _nb(rng, lam_hri + add["hri"])
        resp = _nb(rng, lam_resp + add["resp"])
        incidents = _nb(rng, lam_inc + add["incidents"])
        other = _nb(rng, lam_all * allcause_mult)
        allcause = other + hri + resp

        abs_rate = (
            0.021
            + 0.0009 * heat_x * sc.outdoor_share
            + 0.004 * dust_x
            + np.where(holiday, 0.01, 0.0)
            + absence_add
            + rng.normal(0, 0.002, len(dates))
        ).clip(0.005, 0.25)
        absent = rng.binomial(on_shift, abs_rate)

        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "cluster": sc.code,
                    "district": sc.district,
                    "on_shift": on_shift,
                    "hri": hri,
                    "resp": resp,
                    "allcause": allcause,
                    "absent": absent,
                    "incidents": incidents,
                    "holiday": holiday.astype(int),
                }
            )
        )
    sim = pd.concat(frames, ignore_index=True)
    sim["workforce"] = sim["cluster"].map({c.code: c.workforce for c in SITE_CLUSTERS})
    # Ground truth burden: heat-related + respiratory visits per 10,000 workers.
    sim["burden_rate"] = (sim["hri"] + sim["resp"]) / sim["workforce"] * 10_000
    return sim.sort_values(["cluster", "date"]).reset_index(drop=True)


def degrade_reporting(sim: pd.DataFrame, seed: int = RANDOM_SEED + 1) -> pd.DataFrame:
    """Make the REPORTED feeds messy: random missing days plus a 5-day outage per year.

    Ground-truth columns are kept (suffix ``_true``) for scoring only.
    """
    rng = np.random.default_rng(seed)
    rep = sim.copy()
    feeds = ["hri", "resp", "allcause", "absent", "incidents"]
    for f in feeds:
        rep[f + "_true"] = rep[f]
        miss = rng.random(len(rep)) < 0.025
        rep.loc[miss, f] = np.nan
    # one multi-day clinic-feed outage per cluster per year, at a random date
    for (cl, yr), idx in rep.groupby(["cluster", rep["date"].dt.year]).groups.items():
        idx = np.asarray(list(idx))
        if len(idx) < 30:
            continue
        s = rng.integers(0, len(idx) - 6)
        rep.loc[idx[s : s + 5], ["hri", "resp", "allcause"]] = np.nan
    return rep
