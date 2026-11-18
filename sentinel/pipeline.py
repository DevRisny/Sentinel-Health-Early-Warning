"""End-to-end run: data -> model -> back-test -> reports -> dashboard data.

    python -m sentinel.pipeline

Outputs
  reports/backtest_results.json   all metrics, curves, ablations, stress tests
  reports/figures/*.png           figures used in the technical documentation
  web/public/data/*.json          data the dashboard replays (2026 hold-out)
  data/processed/model.joblib     trained model, calibrator and thresholds
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from . import config as C
from .backtest import bootstrap_ci, score_alerts, summarise
from .environment import load_environment
from .explain import GROUP_ORDER, action_card, explain_row
from .features import (
    FEATURE_GROUP,
    SIGNAL_FAMILY,
    build_features,
    define_events,
    feature_columns,
    fit_expected,
    label_next_days,
)
from .model import (
    baseline_a_score,
    baseline_b_score,
    cluster_months,
    group_contributions,
    split,
    threshold_for_budget,
    train_sentinel,
)
from .simulate import degrade_reporting, simulate


def _log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def prepare(lag_override=None, drop_groups=(), rep_override=None, env=None, sim=None):
    env = load_environment() if env is None else env
    sim = simulate(env) if sim is None else sim
    rep = degrade_reporting(sim) if rep_override is None else rep_override
    expected = fit_expected(rep)
    ev_days, events = define_events(sim)
    df = build_features(env, rep, expected, lag_override=lag_override, drop_groups=drop_groups)
    df = df.merge(ev_days[["date", "cluster", "event_day", "event_id", "burden_rate", "event_thr"]],
                  on=["date", "cluster"])
    y = label_next_days(df)
    return env, sim, rep, df, y, events


def _wbgt_normal(env: pd.DataFrame) -> pd.Series:
    tr = env[env["date"] <= C.TRAIN_END].copy()
    tr["doy"] = tr["date"].dt.dayofyear
    norm = {}
    for d, g in tr.groupby("district"):
        s = g.groupby("doy")["wbgt"].mean().reindex(range(1, 367)).interpolate(limit_direction="both")
        s = pd.concat([s.iloc[-15:], s, s.iloc[:15]]).rolling(15, center=True).mean().iloc[15:-15]
        for doy, v in s.items():
            norm[(d, doy)] = v
    return pd.Series([norm[(d, doy)] for d, doy in zip(env["district"], env["date"].dt.dayofyear)], index=env.index)


def _recent_sums(df: pd.DataFrame) -> pd.DataFrame:
    lags = C.REPORTING_LAG
    lagmap = {"hri": lags["clinic"], "resp": lags["clinic"], "allcause": lags["clinic"],
              "incidents": lags["incidents"], "absent": lags["absence"]}
    g = df.groupby("cluster")
    for sig, k in lagmap.items():
        obs = g[sig].shift(k)
        exp = g[f"{sig}_exp"].shift(k).where(obs.notna())
        df[f"{sig}_obs3"] = obs.groupby(df["cluster"]).transform(lambda s: s.rolling(3, min_periods=1).sum())
        df[f"{sig}_exp3"] = exp.groupby(df["cluster"]).transform(lambda s: s.rolling(3, min_periods=1).sum())
    return df


def evaluate_all(df, y, model, events, label=""):
    sp = split(df)
    te, va = df[sp["test"]], df[sp["valid"]]
    p_te = model.predict(te)
    out = {"sentinel": score_alerts(te, p_te >= model.threshold, events)}
    for name, fn in [("baseline_a", baseline_a_score), ("baseline_b", baseline_b_score)]:
        s_va = np.nan_to_num(fn(va), nan=-99)
        thr = threshold_for_budget(s_va, cluster_months(va))
        out[name] = score_alerts(te, np.nan_to_num(fn(te), nan=-99) >= thr, events)
    return out, p_te


def budget_curves(te, scores, events, budgets=(1, 1.5, 2, 3, 4, 5, 6, 8)):
    cm = cluster_months(te)
    curves = {k: [] for k in scores}
    for b in budgets:
        for k, s in scores.items():
            s = np.nan_to_num(s, nan=-99)
            r = score_alerts(te, s >= threshold_for_budget(s, cm, b), events)
            curves[k].append({"budget": b, **summarise(r)})
    return curves


def reliability(y_true, p, bins=10):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, len(edges) - 2)
    rows = []
    for b in range(len(edges) - 1):
        m = idx == b
        if m.sum():
            rows.append({"pred": float(p[m].mean()), "obs": float(y_true[m].mean()), "n": int(m.sum())})
    return rows


def run(make_figures: bool = True) -> dict:
    t0 = time.time()
    C.REPORTS.mkdir(exist_ok=True)
    C.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    C.WEB_DATA.mkdir(parents=True, exist_ok=True)

    env, sim, rep, df, y, events = prepare()
    _log(f"data ready: {len(df):,} cluster-days, {len(events)} burden events", t0)

    model = train_sentinel(df, y)
    joblib.dump(model, C.DATA_PROCESSED / "model.joblib")
    _log(f"model trained, alert threshold p>={model.threshold:.3f}", t0)

    sp = split(df)
    te = df[sp["test"]].copy()
    res, p_te = evaluate_all(df, y, model, events)
    y_te = y[sp["test"]].to_numpy()

    results = {
        "generated": pd.Timestamp.now(tz=C.TIMEZONE).isoformat(timespec="seconds"),
        "periods": {"train": [C.START_DATE, C.TRAIN_END], "valid": [C.TRAIN_END, C.VALID_END],
                    "test": [C.VALID_END, C.END_DATE]},
        "policy": {"threshold": model.threshold, "warning": model.warning, "danger": model.danger,
                   "budget_per_cluster_month": C.ALERT_BUDGET_PER_CLUSTER_MONTH, "cooldown_days": C.COOLDOWN_DAYS},
        "headline": {k: {**summarise(v), **bootstrap_ci(v)} for k, v in res.items()},
        "discrimination": {
            "roc_auc": float(roc_auc_score(y_te, p_te)),
            "average_precision": float(average_precision_score(y_te, p_te)),
            "brier": float(brier_score_loss(y_te, p_te)),
            "base_rate": float(y_te.mean()),
            "reliability": reliability(y_te, p_te),
        },
    }
    _log("headline: " + json.dumps(results["headline"]["sentinel"]), t0)

    # ---- threshold / budget curves (matched alert rates) ----
    scores = {"sentinel": p_te, "baseline_a": baseline_a_score(te), "baseline_b": baseline_b_score(te)}
    results["budget_curves"] = budget_curves(te, scores, events)

    # ---- ablation: prove each signal family earns its place ----
    fam = {f: SIGNAL_FAMILY[FEATURE_GROUP[f]] for f in feature_columns()}
    ablation = []
    for name, keep in [("Environmental only", {"environmental", "context"}),
                       ("+ clinic/service data", {"environmental", "context", "service"}),
                       ("+ workplace data (full Sentinel)", {"environmental", "context", "service", "workplace"})]:
        feats = [f for f in feature_columns() if fam[f] in keep]
        m = train_sentinel(df, y, feats)
        p = m.predict(te)
        r = score_alerts(te, p >= threshold_for_budget(p, cluster_months(te)), events)
        ablation.append({"variant": name, "average_precision": float(average_precision_score(y_te, p)),
                         **summarise(r)})
    results["ablation"] = ablation
    _log("ablation done", t0)

    # ---- stress tests at inference time (model unchanged) ----
    stress = []
    rng = np.random.default_rng(11)
    variants = {
        "Normal operation": {},
        "Clinic feed lost (all clinic signals missing)": {"drop_groups": ("Heat-illness visits", "Respiratory visits", "All-cause visits")},
        "Reporting lag +2 days on every feed": {"lag_override": {"clinic": 3, "absence": 4, "incidents": 3}},
        "Weather/dust feed lost": {"drop_groups": ("Heat forecast", "Heat so far", "Dust")},
    }
    for name, kw in variants.items():
        _, _, _, d2, _, _ = prepare(env=env, sim=sim, **kw)
        t2 = d2[split(d2)["test"]]
        p = model.predict(t2)
        r = score_alerts(t2, p >= model.threshold, events)
        stress.append({"scenario": name, **summarise(r)})
    rep_m = rep.copy()
    feeds = ["hri", "resp", "allcause", "absent", "incidents"]
    mask = rng.random(len(rep_m)) < 0.30
    rep_m.loc[mask, feeds] = np.nan
    _, _, _, d3, _, _ = prepare(env=env, sim=sim, rep_override=rep_m)
    t3 = d3[split(d3)["test"]]
    p = model.predict(t3)
    stress.append({"scenario": "30% of reported days missing", **summarise(score_alerts(t3, p >= model.threshold, events))})
    results["stress_tests"] = stress
    _log("stress tests done", t0)

    # ---- fairness: performance by site size ----
    ev_te = res["sentinel"]["events"].copy()
    size = {c.code: c.workforce for c in C.SITE_CLUSTERS}
    ev_te["size_band"] = ev_te["cluster"].map(lambda c: "Small (<3,000 workers)" if size[c] < 3000 else "Large (>=3,000 workers)")
    eps = res["sentinel"]["episodes"].copy()
    eps["size_band"] = eps["cluster"].map(lambda c: "Small (<3,000 workers)" if size[c] < 3000 else "Large (>=3,000 workers)")
    results["by_site_size"] = [
        {"band": b, "events": int((ev_te["size_band"] == b).sum()),
         "sensitivity": float(ev_te.loc[ev_te["size_band"] == b, "detected"].mean()),
         "ppv": float(eps.loc[eps["size_band"] == b, "true_alert"].mean()) if (eps["size_band"] == b).any() else None}
        for b in sorted(ev_te["size_band"].unique())
    ]

    # ---- hidden scenarios in the test year: caught or not ----
    sc_rows = []
    for e in [e for e in C.EPISODES if e.start > C.VALID_END]:
        s = pd.Timestamp(e.start)
        sub = te[(te["cluster"] == e.cluster) & (te["date"] >= s - pd.Timedelta(days=2)) & (te["date"] <= s + pd.Timedelta(days=e.days))]
        pv = model.predict(sub)
        al = sub.loc[pv >= model.threshold, "date"]
        a_s = baseline_a_score(sub)
        thr_a = threshold_for_budget(np.nan_to_num(baseline_a_score(df[sp["valid"]]), nan=-99), cluster_months(df[sp["valid"]]))
        a_al = sub.loc[a_s >= thr_a, "date"]
        sc_rows.append({
            "key": e.key, "label": e.label, "cluster": e.cluster, "kind": e.kind, "start": e.start, "days": e.days,
            "expected": "no alert (look-alike)" if e.kind == "lookalike" else "alert",
            "sentinel_first_alert": al.min().strftime("%Y-%m-%d") if len(al) else None,
            "baseline_a_first_alert": a_al.min().strftime("%Y-%m-%d") if len(a_al) else None,
        })
    results["scenarios_test"] = sc_rows

    # ---- explanations for every test cluster-day ----
    explainer = shap.TreeExplainer(model.model)
    sv = explainer.shap_values(te[model.features])
    sv = sv[1] if isinstance(sv, list) else sv
    contrib = group_contributions(np.asarray(sv), model.features)
    gimp = contrib.abs().mean().sort_values(ascending=False)
    results["global_importance"] = [{"group": g, "mean_abs_shap": float(v), "family": SIGNAL_FAMILY[g]} for g, v in gimp.items()]

    env_n = env.copy()
    env_n["wbgt_normal"] = _wbgt_normal(env_n)
    full = _recent_sums(df.copy()).merge(env_n[["date", "district", "wbgt_normal"]], on=["date", "district"])
    full = full.set_index(df.index)
    te_full = full.loc[te.index]
    sev = model.severity(p_te)

    # ---- dashboard export ----
    va = df[sp["valid"]]
    base_flags = {}
    for key, fn in (("a", baseline_a_score), ("b", baseline_b_score)):
        thr = threshold_for_budget(np.nan_to_num(fn(va), nan=-99), cluster_months(va))
        base_flags[key] = np.nan_to_num(fn(te), nan=-99) >= thr
    export_dashboard(te_full, p_te, sev, contrib.set_index(te.index), events, model, results, env_n, base_flags,
                     model.degraded(te))
    _log("dashboard data exported", t0)

    # ---- serialisable results ----
    for k in ("sentinel", "baseline_a", "baseline_b"):
        results["headline"][k]["per_event"] = [
            {"event_id": r["event_id"], "cluster": r["cluster"], "start": r["start"].strftime("%Y-%m-%d"),
             "peak": r["peak"].strftime("%Y-%m-%d"), "detected": bool(r["detected"]),
             "lead_hours": None if pd.isna(r["lead_hours"]) else float(r["lead_hours"])}
            for _, r in res[k]["events"].iterrows()
        ]
    (C.REPORTS / "backtest_results.json").write_text(json.dumps(results, indent=2, default=str))
    if make_figures:
        from .figures import make_all
        make_all(results)
        _log("figures written", t0)
    return results


def export_dashboard(te, p, sev, contrib, events, model, results, env, base_flags, degraded):
    out = C.WEB_DATA
    clusters = [{"code": c.code, "district": c.district, "name": c.name, "sector": c.sector,
                 "workforce": c.workforce, "outdoor_share": c.outdoor_share,
                 "pooled_for_regulator": c.workforce < C.POOL_WORKFORCE_MIN} for c in C.SITE_CLUSTERS]
    districts = [{"code": d.code, "name": d.name, "lat": d.lat, "lon": d.lon} for d in C.DISTRICTS]
    dates = sorted(te["date"].dt.strftime("%Y-%m-%d").unique())
    di = {d: i for i, d in enumerate(dates)}

    rows = []
    for k, ((idx, r), pi, si) in enumerate(zip(te.iterrows(), p, sev)):
        c = contrib.loc[idx]
        sentence, drivers = explain_row(r, c)
        rec = {
            "d": di[r["date"].strftime("%Y-%m-%d")], "c": r["cluster"], "p": round(float(pi), 4), "s": si,
            "wbgt": round(float(r["wbgt"]), 1), "wbgtN": round(float(r["wbgt_normal"]), 1),
            "fcW": None if pd.isna(r["fc_wbgt_max"]) else round(float(r["fc_wbgt_max"]), 1),
            "pm10": round(float(r["pm10_mean"]), 0),
            "fcP": None if pd.isna(r["fc_logpm10_max"]) else round(float(np.expm1(r["fc_logpm10_max"])), 0),
            "hri": None if pd.isna(r["hri"]) else int(r["hri"]), "hriE": round(float(r["hri_exp"]), 2),
            "resp": None if pd.isna(r["resp"]) else int(r["resp"]), "respE": round(float(r["resp_exp"]), 2),
            "abs": None if pd.isna(r["absent"]) else int(r["absent"]), "absE": round(float(r["absent_exp"]), 1),
            "inc": None if pd.isna(r["incidents"]) else int(r["incidents"]),
            "shift": int(r["on_shift"]),
            "comp": None if pd.isna(r["clinic_completeness_7d"]) else round(float(r["clinic_completeness_7d"]), 2),
            "ev": int(r["event_day"]),
            "a": int(base_flags["a"][k]), "b": int(base_flags["b"][k]), "deg": int(degraded[k]),
            "g": {g: round(float(c[g]), 3) for g in GROUP_ORDER if g in c.index},
        }
        if si:
            rec["why"] = sentence
            rec["drv"] = drivers
            rec["act"] = action_card(si, drivers)
        rows.append(rec)

    ev = events[(events["peak"] >= pd.Timestamp(dates[0])) & (events["peak"] <= pd.Timestamp(dates[-1]))]
    meta = {
        "region": C.REGION_NAME, "dates": dates, "clusters": clusters, "districts": districts,
        "policy": results["policy"], "groups": GROUP_ORDER,
        "privacy": {"small_cell_min": C.SMALL_CELL_MIN, "pool_workforce_min": C.POOL_WORKFORCE_MIN},
        "events": [{"id": r["event_id"], "c": r["cluster"], "start": r["start"].strftime("%Y-%m-%d"),
                    "end": r["end"].strftime("%Y-%m-%d"), "peak": r["peak"].strftime("%Y-%m-%d")} for _, r in ev.iterrows()],
        "sources": {
            "weather": "Open-Meteo Historical Weather API (ERA5 / ERA5-Land reanalysis), CC BY 4.0",
            "air_quality": "Open-Meteo Air Quality API (CAMS global), CC BY 4.0",
            "health": "SYNTHETIC - generated by sentinel/simulate.py, documented in docs/DATA_SHEET.md",
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    (out / "daily.json").write_text(json.dumps(rows, separators=(",", ":")))
    trust = {k: results[k] for k in ("headline", "budget_curves", "ablation", "stress_tests", "by_site_size",
                                     "scenarios_test", "discrimination", "global_importance", "periods", "policy")}
    trust = json.loads(json.dumps(trust, default=str))
    for k in trust["headline"]:
        trust["headline"][k].pop("per_event", None)
    (out / "trust.json").write_text(json.dumps(trust, separators=(",", ":")))


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["headline"], indent=2, default=str)[:3000])
