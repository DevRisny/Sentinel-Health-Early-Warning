"""Core tests: physics helpers, privacy rules, leakage guards and the API."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel import config as C
from sentinel.api import app, suppress
from sentinel.environment import load_environment, wbgt_proxy
from sentinel.features import define_events, label_next_days
from sentinel.simulate import degrade_reporting, simulate


@pytest.fixture(scope="module")
def env():
    return load_environment()


@pytest.fixture(scope="module")
def sim(env):
    return simulate(env)


def test_wbgt_proxy_monotonic():
    assert wbgt_proxy(40, 20) > wbgt_proxy(35, 20)
    assert wbgt_proxy(35, 25) > wbgt_proxy(35, 15)


def test_environment_is_complete(env):
    assert set(env["district"]) == {d.code for d in C.DISTRICTS}
    assert env["wbgt"].notna().all()
    assert env["date"].min() == pd.Timestamp(C.START_DATE)


def test_simulation_is_reproducible(env):
    a, b = simulate(env), simulate(env)
    pd.testing.assert_frame_equal(a, b)


def test_heat_raises_heat_illness(sim, env):
    d = sim.merge(env[["date", "district", "wbgt"]], on=["date", "district"])
    hot = d[d["wbgt"] > d["wbgt"].quantile(0.9)]["hri"].mean()
    cool = d[d["wbgt"] < d["wbgt"].quantile(0.3)]["hri"].mean()
    assert hot > 3 * cool


def test_degraded_feed_keeps_truth(sim):
    rep = degrade_reporting(sim)
    assert rep["hri"].isna().mean() > 0.02
    assert rep["hri_true"].notna().all()


def test_labels_look_forward_only(sim):
    ev_days, _ = define_events(sim)
    y = label_next_days(ev_days)
    g = ev_days[ev_days["cluster"] == "AUH-C1"].reset_index()
    yy = y.loc[ev_days["cluster"] == "AUH-C1"].to_numpy()
    for i in range(len(g) - 2):
        assert yy[i] == int(g.loc[i + 1, "event_day"] or g.loc[i + 2, "event_day"])


def test_small_cell_suppression():
    assert suppress(0) == 0
    assert suppress(3) == "<5"
    assert suppress(5) == 5
    assert suppress(None) is None


@pytest.mark.skipif(not (C.WEB_DATA / "daily.json").exists(), reason="run the pipeline first")
class TestAPI:
    client = TestClient(app)

    def test_health(self):
        assert self.client.get("/health").json()["health_data"] == "synthetic"

    def test_regulator_sees_districts_only(self):
        r = self.client.get("/alerts", params={"date": "2026-08-09", "role": "regulator"}).json()
        assert "alerts" not in r and len(r["districts"]) == len(C.DISTRICTS)
        for d in r["districts"]:
            for v in d["counts"].values():
                assert v == 0 or v == "<5" or (isinstance(v, int) and v >= 5)

    def test_site_officer_scope(self):
        r = self.client.get("/alerts", params={"date": "2026-08-09", "role": "site"}).json()
        assert {x["c"] for x in r["all_clusters"]} == {"MUS-C1"}
        assert self.client.get("/clusters/AUH-C1/timeline", params={"role": "site"}).status_code == 403
        assert self.client.get("/clusters/AUH-C1/timeline", params={"role": "regulator"}).status_code == 403

    def test_no_raw_small_counts_leak(self):
        r = self.client.get("/alerts", params={"date": "2026-08-09", "role": "ohlead"}).json()
        for row in r["all_clusters"]:
            for k in ("hri", "resp", "abs", "inc"):
                v = row[k]
                assert v is None or v == 0 or v == "<5" or v >= 5
