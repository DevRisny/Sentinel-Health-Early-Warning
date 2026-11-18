"""Sentinel REST API (aggregates only).

    uvicorn sentinel.api:app --reload

Serves the same outputs the dashboard replays, with role-based views and
small-cell suppression applied on the server, so no client ever receives a
count it is not allowed to see.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import POOL_WORKFORCE_MIN, SMALL_CELL_MIN, WEB_DATA

Role = Literal["regulator", "ohlead", "site"]
SITE_SCOPE = {"site": {"MUS-C1"}}  # demo: the site officer account is scoped to one cluster
COUNT_FIELDS = ("hri", "resp", "abs", "inc")

app = FastAPI(
    title="Sentinel API",
    version="1.0.0",
    description="Explainable 48-hour heat and dust early warning for workforce health. "
                "Health feeds in this prototype are SYNTHETIC; weather and dust are real (Open-Meteo).",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@lru_cache
def _load():
    meta = json.loads((WEB_DATA / "meta.json").read_text())
    daily = json.loads((WEB_DATA / "daily.json").read_text())
    trust = json.loads((WEB_DATA / "trust.json").read_text())
    return meta, daily, trust


def suppress(n: int | None) -> int | str | None:
    """Small-cell suppression: 1..SMALL_CELL_MIN-1 becomes '<5'."""
    if n is None or n == 0:
        return n
    return f"<{SMALL_CELL_MIN}" if n < SMALL_CELL_MIN else n


def _date_index(meta, date: str) -> int:
    try:
        return meta["dates"].index(date)
    except ValueError as e:
        raise HTTPException(404, f"date {date} not in replay period {meta['dates'][0]}..{meta['dates'][-1]}") from e


def _public_row(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k not in COUNT_FIELDS and k not in ("ev", "a", "b")}
    out.update({k: suppress(r.get(k)) for k in COUNT_FIELDS})
    return out


@app.get("/health")
def health():
    meta, daily, _ = _load()
    return {"status": "ok", "replay_days": len(meta["dates"]), "rows": len(daily),
            "health_data": "synthetic", "environment_data": "Open-Meteo (real)"}


@app.get("/alerts")
def alerts(date: str = Query(..., examples=["2026-08-09"]), role: Role = "ohlead"):
    """Alerts for one day, shaped for the caller's role."""
    meta, daily, _ = _load()
    d = _date_index(meta, date)
    rows = [r for r in daily if r["d"] == d]
    clusters = {c["code"]: c for c in meta["clusters"]}
    if role == "regulator":
        out = []
        for dist in meta["districts"]:
            rs = [r for r in rows if clusters[r["c"]]["district"] == dist["code"]]
            order = {"": 0, "Watch": 1, "Warning": 2, "Danger": 3}
            top = max(rs, key=lambda r: (order[r["s"]], r["p"]))
            totals = {k: sum((r.get(k) or 0) for r in rs) for k in COUNT_FIELDS}
            out.append({
                "district": dist["code"], "name": dist["name"], "severity": top["s"],
                "max_risk": top["p"], "clusters_on_alert": sum(1 for r in rs if r["s"]),
                "counts": {k: suppress(v) for k, v in totals.items()},
                "pooled_small_sites": [c for c, v in clusters.items()
                                       if v["district"] == dist["code"] and v["workforce"] < POOL_WORKFORCE_MIN],
            })
        return {"date": date, "role": role, "districts": out}
    scope = SITE_SCOPE.get(role)
    rows = [r for r in rows if scope is None or r["c"] in scope]
    return {"date": date, "role": role, "alerts": [_public_row(r) for r in rows if r["s"]],
            "all_clusters": [_public_row(r) for r in rows]}


@app.get("/clusters/{code}/timeline")
def timeline(code: str, role: Role = "ohlead", days: int = Query(42, ge=1, le=400), end: str | None = None):
    meta, daily, _ = _load()
    if role == "regulator":
        raise HTTPException(403, "Site-level timelines are not available to the regulator role.")
    if role in SITE_SCOPE and code not in SITE_SCOPE[role]:
        raise HTTPException(403, "This account can only see its own site cluster.")
    if code not in {c["code"] for c in meta["clusters"]}:
        raise HTTPException(404, "unknown site cluster")
    last = _date_index(meta, end) if end else len(meta["dates"]) - 1
    rows = [r for r in daily if r["c"] == code and last - days < r["d"] <= last]
    return {"cluster": code, "dates": meta["dates"][last - len(rows) + 1:last + 1], "rows": [_public_row(r) for r in rows]}


@app.get("/validation")
def validation():
    """Back-test summary on the frozen 2026 hold-out."""
    return _load()[2]
