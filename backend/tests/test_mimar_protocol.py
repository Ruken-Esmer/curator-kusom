"""Protocol gates: freezing, pre-registration, blinding, independence."""
import pytest

from app.mimar.analysis import split_key
from app.mimar.security import IndependenceError
from app.mimar.service import ProtocolError
from app.mimar.fake_data import generate_mskl, simulated_label


@pytest.fixture
def world(svc, admin):
    U = {}
    for un, roles in [("tech", ["technical"]), ("rev1", ["reviewer"]), ("rev2", ["reviewer"]), ("adj", ["adjudicator"]),
                      ("exp", ["expert"]), ("std", ["standardizer"]), ("val1", ["validator"]), ("val2", ["validator"]),
                      ("coord", ["coordinator"])]:
        svc.create_user(admin, un, un, roles)
        U[un] = svc.store.get("user", un)
    data = generate_mskl()
    ds = svc.create_dataset(U["tech"], "MSKL", "MSKL", "T0", synthetic=True)
    svc.import_los(U["tech"], ds["id"], data["los"])
    svc.import_ucep(U["tech"], ds["id"], data["ucep"])
    cfg = svc.create_config(U["tech"], "c", {})
    return {"U": U, "ds": ds, "cfg": cfg, "truth": data["truth"], "admin": admin}


def test_analysis_requires_frozen_dataset(svc, world):
    with pytest.raises(ProtocolError):
        svc.run_analysis(world["U"]["tech"], world["ds"]["id"], world["cfg"]["id"])
    svc.freeze_dataset(world["admin"], world["ds"]["id"])
    with pytest.raises(ProtocolError):            # frozen versions are immutable
        svc.import_los(world["U"]["tech"], world["ds"]["id"], [])


def test_only_admin_can_freeze(svc, world):
    with pytest.raises(PermissionError):
        svc.freeze_dataset(world["U"]["tech"], world["ds"]["id"])


def _run(svc, world):
    svc.freeze_dataset(world["admin"], world["ds"]["id"])
    run = svc.run_analysis(world["U"]["tech"], world["ds"]["id"], world["cfg"]["id"])
    plan = svc.create_plan(world["admin"], run["id"], {"min_positives": 5, "bootstrap_B": 200})
    return run, plan


def _review_all(svc, world, sample_id):
    s = svc.store.get("sample", sample_id)
    inv = {v: k for k, v in s["codes"].items()}
    for rv, seed in (("rev1", 1), ("rev2", 2)):
        for it in svc.review_queue(world["U"][rv], sample_id)["items"]:
            a, b = split_key(inv[it["code"]])
            svc.decide(world["U"][rv], sample_id, it["code"], simulated_label(world["truth"], a, b, seed))
        svc.lock_decisions(world["U"][rv], sample_id)
    for c in svc.conflicts(sample_id):
        svc.adjudicate(world["U"]["adj"], sample_id, c["code"], "no_overlap")


def test_locked_test_requires_locked_plan_and_comparator(svc, world):
    run, plan = _run(svc, world)
    with pytest.raises(ProtocolError):
        svc.create_as1_sample(world["U"]["tech"], run["id"], "test")
    with pytest.raises(ProtocolError):
        svc.lock_plan(world["admin"], plan["id"])          # comparator not selected yet
    dev = svc.create_as1_sample(world["U"]["tech"], run["id"], "dev")
    svc.assign_reviewers(world["U"]["tech"], dev["id"], ["rev1", "rev2"], "adj")
    _review_all(svc, world, dev["id"])
    ev = svc.evaluate_sample(world["admin"], dev["id"])
    assert ev["comparator_selection"]["comparator"] in ("bm25", "embedding", "graph")
    assert ev["depth_selection"]["selected_depth_dev"] > 0
    plan = svc.lock_plan(world["admin"], plan["id"])
    assert plan["locked"] and len(plan["lock_hash"]) == 64
    with pytest.raises(ProtocolError):
        svc.update_plan(world["admin"], plan["id"], {"dev_n": 1})
    test = svc.create_as1_sample(world["U"]["tech"], run["id"], "test")
    with pytest.raises(ProtocolError):                     # test opened only once
        svc.create_as1_sample(world["U"]["tech"], run["id"], "test")
    svc.assign_reviewers(world["U"]["tech"], test["id"], ["rev1", "rev2"], "adj")
    _review_all(svc, world, test["id"])
    res = svc.evaluate_sample(world["admin"], test["id"])
    assert res["h1"]["verdict"] in ("supported", "not_supported", "inconclusive_insufficient_positives")
    assert res["plan_lock_hash"] == plan["lock_hash"]


def test_blinding_and_independence_in_review(svc, world):
    run, plan = _run(svc, world)
    dev = svc.create_as1_sample(world["U"]["tech"], run["id"], "dev")
    with pytest.raises(IndependenceError):                 # selector cannot review
        svc.assign_reviewers(world["U"]["tech"], dev["id"], ["tech", "rev1"], "adj")
    with pytest.raises(IndependenceError):
        svc.assign_reviewers(world["U"]["tech"], dev["id"], ["rev1", "rev2"], "rev1")
    svc.assign_reviewers(world["U"]["tech"], dev["id"], ["rev1", "rev2"], "adj")
    q1 = svc.review_queue(world["U"]["rev1"], dev["id"])
    q2 = svc.review_queue(world["U"]["rev2"], dev["id"])
    assert set(q1["items"][0]) == {"code", "text_a", "text_b", "decision", "rationale"}   # nothing else exposed
    assert [i["code"] for i in q1["items"]] != [i["code"] for i in q2["items"]]          # individual random order
    with pytest.raises(PermissionError):
        svc.review_queue(world["U"]["rev1"] | {"username": "val1"}, dev["id"])
    code = q1["items"][0]["code"]
    svc.decide(world["U"]["rev1"], dev["id"], code, "overlap")
    with pytest.raises(ProtocolError):
        svc.lock_decisions(world["U"]["rev1"], dev["id"])                                  # incomplete
    with pytest.raises(PermissionError):                   # admin is not a reviewer
        svc.decide(world["admin"], dev["id"], code, "overlap")


def test_locked_decisions_are_immutable_and_only_conflicts_adjudicated(svc, world):
    run, plan = _run(svc, world)
    dev = svc.create_as1_sample(world["U"]["tech"], run["id"], "dev")
    svc.assign_reviewers(world["U"]["tech"], dev["id"], ["rev1", "rev2"], "adj")
    for rv in ("rev1", "rev2"):
        for it in svc.review_queue(world["U"][rv], dev["id"])["items"]:
            svc.decide(world["U"][rv], dev["id"], it["code"], "no_overlap")
        svc.lock_decisions(world["U"][rv], dev["id"])
    code = svc.review_queue(world["U"]["rev1"], dev["id"])["items"][0]["code"]
    with pytest.raises(ProtocolError):
        svc.decide(world["U"]["rev1"], dev["id"], code, "overlap")
    with pytest.raises(ProtocolError):                     # full agreement → nothing to adjudicate
        svc.adjudicate(world["U"]["adj"], dev["id"], code, "overlap")
    assert svc.final_labels(dev["id"])["agreement_initial"]["percent"] == 1.0


def test_as2_seal_and_validator_independence(svc, world):
    run, _ = _run(svc, world)
    core = svc.generate_mimar_report(world["U"]["tech"], run["id"], "core")
    with pytest.raises(ProtocolError):                     # reports must be locked first
        svc.build_pool(world["U"]["std"], {"M": core["id"], "U": core["id"]})
    svc.lock_report(world["U"]["tech"], core["id"])
    exp = svc.import_expert_report(world["U"]["exp"], world["ds"]["id"],
                                   [{"category": "gap_ucep", "ucep": ["SYN-UCEP-U01"], "statement": "x"}])
    svc.lock_report(world["U"]["exp"], exp["id"])
    with pytest.raises(IndependenceError):                 # authors cannot standardise
        svc.build_pool(world["U"]["tech"] | {"roles": ["standardizer"]}, {"M": core["id"], "U": exp["id"]})
    pool = svc.build_pool(world["U"]["std"], {"M": core["id"], "U": exp["id"]})
    entries = svc.pool_entries(world["admin"], pool["id"])["entries"]
    assert all("sources" not in e and "evidence" not in e for e in entries)   # blinded
    with pytest.raises(IndependenceError):
        svc.assign_validators(world["admin"], pool["id"], ["std", "val1"], None)
    with pytest.raises(PermissionError):                   # validators never see source reports
        svc.report_findings(world["U"]["val1"], core["id"])
    svc.assign_validators(world["admin"], pool["id"], ["val1", "val2"], "adj")
    with pytest.raises(ProtocolError):                     # seal stays closed until all final
        svc.as2a_results(world["admin"], pool["id"])
    for v in ("val1", "val2"):
        for e in entries:
            svc.validate(world["U"][v], pool["id"], e["code"], "yes", "yes", "yes")
        svc.lock_validations(world["U"][v], pool["id"])
    res = svc.as2a_results(world["admin"], pool["id"], B=200)
    assert res["main"]["N_U"] == 1 and res["main"]["rate_U"] == 1.0
    assert svc.store.get("pool", pool["id"])["sealed"] is False


def test_as6_expected_effects_hidden_and_locked_first(svc, world):
    run, _ = _run(svc, world)
    t1 = svc.new_version(world["U"]["tech"], world["ds"]["id"], "T1")
    uid = svc.list_los(world["ds"]["id"])[0]["uid"]
    svc.apply_changes(world["U"]["tech"], t1["id"], [{"op": "remove", "uid": uid}])
    svc.freeze_dataset(world["admin"], t1["id"])
    cs = svc.create_changeset(world["U"]["tech"], world["ds"]["id"], t1["id"], world["cfg"]["id"])
    with pytest.raises(ProtocolError):
        svc.run_impact(world["U"]["tech"], cs["id"])
    svc.register_expected(world["U"]["coord"], cs["id"], [{"type": "removed_link", "entity": "x|y"}])
    with pytest.raises(PermissionError):
        svc.expected_effects(world["U"]["tech"], cs["id"])
    svc.lock_expected(world["U"]["coord"], cs["id"])
    rep = svc.run_impact(world["U"]["tech"], cs["id"])
    assert rep["diff"]["removed"] == [uid]
    with pytest.raises(ProtocolError):
        svc.register_expected(world["U"]["coord"], cs["id"], [{"type": "new_link", "entity": "a|b"}])
    ev = svc.evaluate_changeset(world["U"]["coord"], cs["id"])
    assert ev["total_expected"] == 1


def test_full_demo_runs_and_audit_chain_valid(svc, admin):
    from app.mimar.demo import run_full_demo
    s = run_full_demo(svc, admin, quick=True)
    assert s["audit"]["valid"]
    assert s["as1"]["h1"]["verdict"] in ("supported", "not_supported", "inconclusive_insufficient_positives")
    assert s["as2a"]["entries"] > 0 and s["as6_real"]["total_expected"] == 3
    assert s["dataset"]["qc"]["excluded"] == 3
