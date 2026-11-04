"""Statistical estimators against hand-computed values."""
import math

import numpy as np

from app.mimar import metrics as M


def test_agreement_hand_computed():
    r = M.agreement(["a", "a", "a", "b"], ["a", "a", "b", "b"], ["a", "b"])
    assert r["percent"] == 0.75
    assert r["kappa"] == 0.5
    assert math.isclose(r["ac1"], (0.75 - 0.46875) / (1 - 0.46875), abs_tol=1e-4)


def test_ac1_stable_under_prevalence_paradox():
    r1 = ["n"] * 95 + ["y", "y", "n", "n", "y"]
    r2 = ["n"] * 95 + ["y", "n", "y", "n", "n"]
    r = M.agreement(r1, r2, ["y", "n"])
    assert r["kappa"] < 0.5 < r["ac1"]


def _items():
    # 4 listed pairs (weight 1) and 2 unlisted pairs (weight 50)
    return [
        {"item": "p1", "weight": 1, "stratum": "L"}, {"item": "p2", "weight": 1, "stratum": "L"},
        {"item": "p3", "weight": 1, "stratum": "L"}, {"item": "p4", "weight": 1, "stratum": "L"},
        {"item": "u1", "weight": 50, "stratum": "U"}, {"item": "u2", "weight": 50, "stratum": "U"},
    ]


def test_weighted_sensitivity_and_ppv():
    labels = {"p1": 1, "p2": 1, "p3": 0, "p4": None, "u1": 0, "u2": 1}
    lists = {"hybrid": ["p1", "p2", "p3"], "bm25": ["p1", "p3", "p4"]}
    m = M.as1_metrics(_items(), labels, lists)
    h = m["methods"]["hybrid"]
    # positives weighted: p1 + p2 + 50·u2 = 52 ; hybrid TP = 2 ; listed (usable) = 3
    assert m["positives_weighted"] == 52.0 and m["n_insufficient"] == 1
    assert math.isclose(h["sensitivity"], round(2 / 52, 4))
    assert math.isclose(h["ppv"], round(2 / 3, 4))
    assert h["raw"]["sensitivity"] == round(2 / 3, 4)
    assert m["methods"]["bm25"]["ppv"] == 0.5       # p4 insufficient → excluded


def test_comparator_selection_tie_breaks_on_f1():
    dev = {"methods": {"bm25": {"ppv": 0.5, "f1": 0.4}, "embedding": {"ppv": 0.5, "f1": 0.45},
                       "graph": {"ppv": 0.3, "f1": 0.9}}}
    assert M.select_comparator(dev)["comparator"] == "embedding"


def test_cluster_bootstrap_keeps_clusters_together_and_is_deterministic():
    ids = ["a", "a", "b", "b", "c"]
    cols = {"n": [1, 1, 0, 0, 1], "d": [1, 1, 1, 1, 1]}
    r1 = M.cluster_bootstrap(ids, cols, lambda t: t["n"] / t["d"], B=500, seed=1)
    r2 = M.cluster_bootstrap(ids, cols, lambda t: t["n"] / t["d"], B=500, seed=1)
    assert r1 == r2 and r1["clusters"] == 3
    assert 0 <= r1["lo"] <= 0.6 <= r1["hi"] <= 1


def test_h1_decision_rules():
    met = {"methods": {"hybrid": {"sensitivity": 0.85}}, "positives_raw": 40}
    assert M.h1_decision(met, {"ci95": [0.01, 0.2], "b": "bm25"}, 30)["verdict"] == "supported"
    assert M.h1_decision(met, {"ci95": [-0.01, 0.2], "b": "bm25"}, 30)["verdict"] == "not_supported"
    met["positives_raw"] = 10
    assert M.h1_decision(met, {"ci95": [0.01, 0.2], "b": "bm25"}, 30)["verdict"].startswith("inconclusive")


def test_delta_mu_shared_findings_count_for_both_sources():
    recs = ([{"sources": ["M"], "verified": True, "family": f"m{i}"} for i in range(6)] +
            [{"sources": ["M"], "verified": False, "family": f"x{i}"} for i in range(4)] +
            [{"sources": ["U"], "verified": True, "family": f"u{i}"} for i in range(3)] +
            [{"sources": ["U"], "verified": None, "family": "u9"}] +
            [{"sources": ["M", "U"], "verified": True, "family": "s1"}])
    r = M.delta_mu(recs, B=300)
    assert r["main"]["N_M"] == 11 and r["main"]["V_M"] == 7
    assert r["main"]["N_U"] == 5 and r["main"]["V_U"] == 4
    assert math.isclose(r["main"]["delta_pp"], round(100 * (7 / 11 - 4 / 5), 2))
    assert r["sensitivity_insufficient_excluded"]["N_U"] == 4
    assert set(r["h2a"]["margin_sensitivity"]) == {"-10pp", "-5pp", "-15pp"}


def test_h2b_share():
    ext = [{"new": True, "reviewed": True, "verified": True}] * 2 + [{"new": True, "reviewed": True, "verified": False}] + \
          [{"new": False, "reviewed": False, "verified": False}] * 7
    r = M.h2b_new_share(ext)
    assert r["share"] == 0.2 and r["met_point_estimate"]


def test_h5_completion_adjustment_and_bounds():
    s = []
    for i in range(10):
        s.append({"stratum": "A", "weight": 2.0, "completed": i < 8, "meaningful": i < 6, "feasible": True,
                  "coordinator": f"c{i % 4}"})
    r = M.h5_estimate(s, min_coordinators=4, B=200)
    assert r["joint_rate"] == 0.75                   # 6/8 completed positives
    assert r["extreme_case_bounds"] == [0.6, 0.8]    # missing all negative / all positive
    assert r["participation_condition_met"]


def test_h6_alert_metrics():
    sc = [{"id": f"s{i}", "alerts": [{"verified": True}] * 3 + [{"verified": False}],
           "expected": [{"reported": True}] * 4 + [{"reported": i % 4 != 0}]} for i in range(8)]
    r = M.h6_alert_metrics(sc, B=200)
    assert r["verified_alert_rate"] == 0.75 and math.isclose(r["missed_expected_rate"], 2 / 40)
    assert r["met"]


def test_power_increases_with_n():
    lo = M.power_simulation_h2a(40, sims=400)["power"]
    hi = M.power_simulation_h2a(300, sims=400)["power"]
    assert hi > lo + 0.3
