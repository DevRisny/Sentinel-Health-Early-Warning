"""Fused risk model, calibration, alert policy and the two comparison baselines."""
from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from .config import (
    ALERT_BUDGET_PER_CLUSTER_MONTH,
    COOLDOWN_DAYS,
    RANDOM_SEED,
    TRAIN_END,
    VALID_END,
)
from .features import FEATURE_GROUP, feature_columns

LGB_PARAMS = dict(
    n_estimators=450,
    learning_rate=0.03,
    num_leaves=15,
    max_depth=5,
    min_child_samples=40,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=2.0,
    random_state=RANDOM_SEED,
    verbose=-1,
)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-5, 1 - 1e-5)
    return np.log(p / (1 - p)).reshape(-1, 1)


def split(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "train": df["date"] <= VALID_END,
        "valid": (df["date"] > "2024-12-31") & (df["date"] <= VALID_END),
        "test": df["date"] > VALID_END,
    }


def threshold_for_budget(score: np.ndarray, n_cluster_months: float,
                         budget: float = ALERT_BUDGET_PER_CLUSTER_MONTH) -> float:
    """Smallest threshold whose alert-day count stays within the budget."""
    s = np.sort(score[~np.isnan(score)])[::-1]
    k = int(round(budget * n_cluster_months))
    k = min(max(k, 1), len(s))
    return float(s[k - 1])


def cluster_months(df: pd.DataFrame) -> float:
    return df["cluster"].nunique() * (df["date"].max() - df["date"].min()).days / 30.44


@dataclass
class SentinelModel:
    model: lgb.LGBMClassifier
    calibrator: LogisticRegression
    threshold: float
    warning: float
    danger: float
    features: list[str]
    fallback: "SentinelModel | None" = None

    def raw(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X[self.features])[:, 1]

    def degraded(self, X: pd.DataFrame) -> np.ndarray:
        """True where the weather/dust feed is missing, so the fallback model is used."""
        if "fc_wbgt_max" not in self.features:
            return np.zeros(len(X), dtype=bool)
        return X["fc_wbgt_max"].isna().to_numpy() & X["wbgt"].isna().to_numpy()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        p = self.calibrator.predict_proba(_logit(self.raw(X)))[:, 1]
        if self.fallback is not None:
            d = self.degraded(X)
            if d.any():
                p[d] = self.fallback.predict(X[d])
        return p

    def severity(self, p: np.ndarray) -> np.ndarray:
        sev = np.full(len(p), "", dtype=object)
        sev[p >= self.threshold] = "Watch"
        sev[p >= self.warning] = "Warning"
        sev[p >= self.danger] = "Danger"
        return sev


# Domain knowledge as constraints: more heat, dust or excess illness can only raise
# risk. All-cause visits are left free so a vaccination-day spike is not read as heat.
MONOTONE_UP = {
    "fc_heat_load", "fc_wbgt_d1", "fc_wbgt_d2", "fc_wbgt_max", "wbgt", "wbgt_3d", "hot_streak",
    "log_pm10", "fc_logpm10_d1", "fc_logpm10_d2", "fc_logpm10_max",
    "hri_z_last", "hri_z_3d", "hri_cusum", "hri_z_7d", "district_hri_z",
    "resp_z_last", "resp_z_3d", "resp_cusum", "resp_z_7d", "district_resp_z",
    "incidents_z_last", "incidents_z_3d", "incidents_cusum",
    "absent_z_last", "absent_z_3d", "absent_cusum",
}


def _fit_lgb(X: pd.DataFrame, y: pd.Series, feats: list[str]) -> lgb.LGBMClassifier:
    pos = y.mean()
    clf = lgb.LGBMClassifier(**LGB_PARAMS, scale_pos_weight=float((1 - pos) / max(pos, 1e-6)) ** 0.5,
                             monotone_constraints=[1 if f in MONOTONE_UP else 0 for f in feats],
                             monotone_constraints_method="advanced")
    clf.fit(X[feats], y)
    return clf


def train_sentinel(df: pd.DataFrame, y: pd.Series, features: list[str] | None = None) -> SentinelModel:
    """Season-wise cross-fitting on 2024-2025, final fit on both; 2026 never touched.

    1. Fit on one season, predict the other (out-of-fold scores for every 2024-25 day).
    2. Platt-calibrate on those out-of-fold scores.
    3. Pick the alert threshold that meets the alert budget on out-of-fold 2025.
    4. Refit on both seasons for the deployed model.
    """
    feats = features or feature_columns()
    dev = (df["date"] <= VALID_END) & y.notna()
    year = df["date"].dt.year
    oof = pd.Series(np.nan, index=df.index)
    for yr in (2024, 2025):
        fit_rows, pred_rows = dev & (year != yr), dev & (year == yr)
        m = _fit_lgb(df[fit_rows], y[fit_rows], feats)
        oof[pred_rows] = m.predict_proba(df.loc[pred_rows, feats])[:, 1]
    cal = LogisticRegression(C=1.0)
    cal.fit(_logit(oof[dev].to_numpy()), y[dev])
    clf = _fit_lgb(df[dev], y[dev], feats)
    ref = dev & (year == 2025)
    p_ref = cal.predict_proba(_logit(oof[ref].to_numpy()))[:, 1]
    thr = threshold_for_budget(p_ref, cluster_months(df[ref]))
    above = p_ref[p_ref >= thr]
    warning = max(thr, float(np.quantile(above, 0.5))) if len(above) else thr
    danger = max(warning, float(np.quantile(above, 0.85))) if len(above) else warning
    model = SentinelModel(clf, cal, thr, warning, danger, feats)
    if features is None:
        # Safe degradation: a health-feed-only model takes over if weather/dust go missing.
        env_groups = {"Heat forecast", "Heat so far", "Dust"}
        fb_feats = [f for f in feats if FEATURE_GROUP[f] not in env_groups]
        model.fallback = train_sentinel(df, y, fb_feats)
    return model


# ----------------------------------------------------------------------------- baselines
DUST_FIXED_PM10 = 300.0  # ug/m3 daily mean, a common "very unhealthy dust" trigger


def baseline_a_score(df: pd.DataFrame) -> np.ndarray:
    """Today's practice: forecast heat index above a fixed line (or a fixed dust line).

    Returned as a single score so it can be thresholded at the same alert budget.
    """
    heat = df["fc_wbgt_max"].to_numpy()
    dust = np.expm1(df["fc_logpm10_max"].to_numpy())
    return np.where(dust >= DUST_FIXED_PM10, 99.0, heat)


def baseline_b_score(df: pd.DataFrame) -> np.ndarray:
    """Reactive surveillance: the largest seasonal z-score among the clinic feeds."""
    cols = ["hri_z_last", "resp_z_last", "allcause_z_last"]
    return np.nanmax(df[cols].to_numpy(dtype=float), axis=1)


# ------------------------------------------------------------------------- alert policy
def alert_episodes(df: pd.DataFrame, alert: np.ndarray, cooldown: int = COOLDOWN_DAYS) -> pd.DataFrame:
    """Merge alert days of one cluster separated by <= cooldown days into one episode."""
    rows = []
    a = pd.Series(alert.astype(bool), index=df.index)
    for cl, g in df.groupby("cluster"):
        days = g.loc[a.loc[g.index], "date"].sort_values().tolist()
        cur: list[pd.Timestamp] = []
        for d in days:
            if cur and (d - cur[-1]).days <= cooldown + 1:
                cur.append(d)
            else:
                if cur:
                    rows.append((cl, cur[0], cur[-1], len(cur)))
                cur = [d]
        if cur:
            rows.append((cl, cur[0], cur[-1], len(cur)))
    return pd.DataFrame(rows, columns=["cluster", "first", "last", "n_days"])


def group_contributions(shap_values: np.ndarray, features: list[str]) -> pd.DataFrame:
    """Sum SHAP values (log-odds) per human-readable signal group."""
    groups = sorted(set(FEATURE_GROUP[f] for f in features))
    out = np.zeros((shap_values.shape[0], len(groups)))
    for j, f in enumerate(features):
        out[:, groups.index(FEATURE_GROUP[f])] += shap_values[:, j]
    return pd.DataFrame(out, columns=groups)
