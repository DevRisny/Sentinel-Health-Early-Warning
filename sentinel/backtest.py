"""Back-test metrics: lead time, sensitivity, PPV and false alarms, with bootstrap CIs."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RANDOM_SEED
from .model import alert_episodes

DETECT_WINDOW_BEFORE_START = 2  # = the 48-hour horizon: an alert up to 2 days before onset counts


def score_alerts(df: pd.DataFrame, alert: np.ndarray, events: pd.DataFrame) -> dict:
    """Event-level and alert-level scores for one method on one period.

    * An event is DETECTED if an alert was issued on a day from (start - 2) to
      (peak - 1): a warning that arrives on or after the peak is too late to act on.
    * LEAD TIME = peak minus the first qualifying alert day, in hours.
    * An alert EPISODE is a TRUE alert if an event day falls between its first day
      and two days after its last day (the 48-hour horizon); otherwise it is a false alarm.
    """
    lo, hi = df["date"].min(), df["date"].max()
    ev = events[(events["peak"] >= lo + pd.Timedelta(days=DETECT_WINDOW_BEFORE_START)) & (events["peak"] <= hi)].copy()
    alert_s = pd.Series(alert.astype(bool), index=df.index)
    adays = {cl: set(g.loc[alert_s.loc[g.index], "date"]) for cl, g in df.groupby("cluster")}

    leads, detected, onset = [], [], []
    for _, e in ev.iterrows():
        window = pd.date_range(e["start"] - pd.Timedelta(days=DETECT_WINDOW_BEFORE_START), e["peak"] - pd.Timedelta(days=1))
        hits = [d for d in window if d in adays.get(e["cluster"], set())]
        detected.append(bool(hits))
        leads.append((e["peak"] - min(hits)).days * 24 if hits else np.nan)
        onset.append((e["start"] - min(hits)).days * 24 if hits else np.nan)
    ev["detected"], ev["lead_hours"], ev["onset_lead_hours"] = detected, leads, onset

    eps = alert_episodes(df, alert)
    ev_days = {}
    for _, e in events.iterrows():
        ev_days.setdefault(e["cluster"], []).append((e["start"], e["end"]))
    true_flags = []
    for _, a in eps.iterrows():
        a0, a1 = a["first"], a["last"] + pd.Timedelta(days=2)
        true_flags.append(any(s <= a1 and e >= a0 for s, e in ev_days.get(a["cluster"], [])))
    eps["true_alert"] = true_flags
    cm = df["cluster"].nunique() * ((hi - lo).days + 1) / 30.44
    n_fa = int((~eps["true_alert"]).sum()) if len(eps) else 0
    return {
        "events": ev,
        "episodes": eps,
        "n_events": int(len(ev)),
        "sensitivity": float(np.mean(detected)) if len(ev) else np.nan,
        "median_lead_hours": float(np.nanmedian(leads)) if np.any(~np.isnan(leads)) else np.nan,
        "mean_lead_hours": float(np.nanmean(leads)) if np.any(~np.isnan(leads)) else np.nan,
        "median_onset_lead_hours": float(np.nanmedian(onset)) if np.any(~np.isnan(onset)) else np.nan,
        "share_warned_before_onset": float(np.nanmean(np.array(onset, dtype=float) > 0)) if len(ev) else np.nan,
        "n_alert_episodes": int(len(eps)),
        "ppv": float(eps["true_alert"].mean()) if len(eps) else np.nan,
        "false_alarms_per_cluster_month": n_fa / cm,
        "alert_days_per_cluster_month": float(alert.sum()) / cm,
    }


def bootstrap_ci(res: dict, n: int = 2000, seed: int = RANDOM_SEED) -> dict:
    """95% bootstrap intervals, resampling whole events (and whole alert episodes)."""
    rng = np.random.default_rng(seed)
    ev, eps = res["events"], res["episodes"]
    out = {}
    if len(ev):
        det = ev["detected"].to_numpy(float)
        lead = ev["lead_hours"].to_numpy(float)
        sens, med = [], []
        for _ in range(n):
            i = rng.integers(0, len(ev), len(ev))
            sens.append(det[i].mean())
            li = lead[i]
            med.append(np.nanmedian(li) if np.any(~np.isnan(li)) else np.nan)
        out["sensitivity_ci"] = [float(np.nanpercentile(sens, 2.5)), float(np.nanpercentile(sens, 97.5))]
        out["median_lead_hours_ci"] = [float(np.nanpercentile(med, 2.5)), float(np.nanpercentile(med, 97.5))]
    if len(eps):
        t = eps["true_alert"].to_numpy(float)
        ppv = [t[rng.integers(0, len(t), len(t))].mean() for _ in range(n)]
        out["ppv_ci"] = [float(np.percentile(ppv, 2.5)), float(np.percentile(ppv, 97.5))]
    return out


def summarise(res: dict) -> dict:
    keys = ["n_events", "sensitivity", "median_lead_hours", "mean_lead_hours", "median_onset_lead_hours",
            "share_warned_before_onset", "n_alert_episodes", "ppv",
            "false_alarms_per_cluster_month", "alert_days_per_cluster_month"]
    return {k: (round(res[k], 3) if isinstance(res[k], float) else res[k]) for k in keys}
