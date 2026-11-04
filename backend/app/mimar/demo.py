"""MİMAR — End-to-end demonstration with synthetic data and simulated raters."""
from __future__ import annotations

import random
from typing import Any

from app.mimar.analysis import split_key
from app.mimar.service import MimarService
from app.mimar.fake_data import (
    TOPICS, generate_mskl, simulated_expert_findings, simulated_label, simulated_validation, true_overlap,
)

DEMO_USERS = [
    ("tech", "Technical lead (demo)", ["technical"]),
    ("rev1", "AS1 reviewer 1 (demo)", ["reviewer"]),
    ("rev2", "AS1 reviewer 2 (demo)", ["reviewer"]),
    ("adj", "Adjudicator (demo)", ["adjudicator"]),
    ("expert1", "MSKL expert 1 (demo)", ["expert"]),
    ("expert2", "MSKL expert 2 (demo)", ["expert"]),
    ("std", "Standardisation (demo)", ["standardizer"]),
    ("val1", "Validator – preclinical (demo)", ["validator"]),
    ("val2", "Validator – clinical (demo)", ["validator"]),
    ("vadj", "Validation third person (demo)", ["adjudicator"]),
    ("impact", "Impact evaluator (demo)", ["impact_evaluator", "coordinator"]),
    ("observer", "Observer (demo)", ["observer"]),
] + [(f"coord{i:02d}", f"Coordinator {i:02d} (demo)", ["coordinator"]) for i in range(1, 21)]


def _users(svc: MimarService, admin: dict) -> dict[str, dict]:
    out = {}
    for un, dn, roles in DEMO_USERS:
        u = svc.store.get("user", un)
        if u is None:
            created = svc.create_user(admin, un, dn, roles)
            out[un] = {**svc.store.get("user", un), "token": created["token"]}
        else:
            tok = svc.rotate_token(admin, un)["token"]
            out[un] = {**svc.store.get("user", un), "token": tok}
    return out


def synthetic_materials(los: list[dict], truth: dict, seed: int = 11) -> list[dict]:
    """KuLearn-like slide texts (synthetic) for a subset of activities."""
    rng = random.Random(seed)
    by_act: dict[str, list[dict]] = {}
    for lo in los:
        by_act.setdefault(lo["activity"], []).append(lo)
    rows = []
    for i, (act, members) in enumerate(sorted(by_act.items())):
        if rng.random() < 0.55:
            g = truth["group_of"].get(members[0]["uid"], "")
            ti = int(g[1:3]) if g.startswith("G") and g[1:3].isdigit() else None
            extra = ""
            if ti is not None:
                top = TOPICS[ti]
                extra = f" Clinical correlation: {top['clin']}. Basic science link: {top['anat']}."
            rows.append({"activity": act, "title": f"Lecture slides {act}", "location": f"slides 1-{rng.randint(8, 30)}",
                         "text": " ".join(m["text"] for m in members) + extra,
                         "permission": "yes" if rng.random() < 0.85 else "no", "license": "KU internal (synthetic)",
                         "version": "2026-2027" if rng.random() < 0.95 else ""})
    return rows


def run_full_demo(svc: MimarService, admin: dict, seed: int = 20260913, quick: bool = False) -> dict[str, Any]:
    U = _users(svc, admin)
    data = generate_mskl(seed)
    truth = data["truth"]
    summary: dict[str, Any] = {"note": "Synthetic data and simulated raters — illustrative only."}

    # data preparation
    ds = svc.create_dataset(U["tech"], "MSKL (synthetic demo)", "MSKL", "T0",
                            "Synthetic MSKL learning objectives for workflow testing", synthetic=True)
    rows = data["los"] + [{"uid": "", "text": "Describe something.", "activity": "X", "source": "s"},
                          {"uid": "SYN-BAD-1", "text": "", "activity": "X", "source": "s"},
                          {"uid": "SYN-BAD-2", "text": "Explain bone.", "activity": "X", "source": "s"}]
    qc = svc.import_los(U["tech"], ds["id"], rows)
    svc.import_ucep(U["tech"], ds["id"], data["ucep"])
    svc.import_materials(U["tech"], ds["id"], synthetic_materials(data["los"], truth))
    svc.store.put("simulation_truth", {"dataset_id": ds["id"], **truth}, id=ds["id"])
    ds = svc.freeze_dataset(admin, ds["id"])
    summary["dataset"] = {"id": ds["id"], "content_hash": ds["content_hash"][:16], "qc": qc}

    # AS1
    cfg = svc.create_config(U["tech"], "default v1", {"list_depth": 150})
    run = svc.run_analysis(U["tech"], ds["id"], cfg["id"])
    if not quick:
        summary["stability"] = svc.stability(U["tech"], run["id"], runs=5, top=20)
    plan = svc.create_plan(admin, run["id"], {"dev_n": 300, "test_n": 1000, "min_positives": 15,
                                              "bootstrap_B": 1000 if quick else 2000})

    def review(sample):
        svc.assign_reviewers(U["tech"], sample["id"], ["rev1", "rev2"], "adj")
        for rv, rs in (("rev1", 1), ("rev2", 2)):
            q = svc.review_queue(U[rv], sample["id"])
            s_doc = svc.store.get("sample", sample["id"])
            inv = {v: k for k, v in s_doc["codes"].items()}
            for it in q["items"]:
                a, b = split_key(inv[it["code"]])
                svc.decide(U[rv], sample["id"], it["code"], simulated_label(truth, a, b, rs))
            svc.lock_decisions(U[rv], sample["id"])
            svc.log_effort(U[rv], "AS1 review", round(len(q["items"]) / 120, 2), sample["id"])
        s_doc = svc.store.get("sample", sample["id"])
        for c in svc.conflicts(sample["id"]):
            a, b = split_key(c["item"])
            svc.adjudicate(U["adj"], sample["id"], c["code"], "overlap" if true_overlap(truth, a, b) else "no_overlap")
        return svc.evaluate_sample(admin, sample["id"])

    dev = svc.create_as1_sample(U["tech"], run["id"], "dev")
    dev_eval = review(dev)
    plan = svc.lock_plan(admin, plan["id"])
    test = svc.create_as1_sample(U["tech"], run["id"], "test")
    test_eval = review(test)
    summary["as1"] = {"analysis_id": run["id"], "dev_sample": dev["id"], "test_sample": test["id"],
                      "comparator": plan["comparator"], "plan_lock_hash": plan["lock_hash"][:16],
                      "dev": {m: {k: v for k, v in x.items() if k in ("sensitivity", "ppv", "f1")}
                              for m, x in dev_eval["metrics"]["methods"].items()},
                      "test": {m: {k: v for k, v in x.items() if k in ("sensitivity", "ppv", "f1")}
                               for m, x in test_eval["metrics"]["methods"].items()},
                      "agreement": test_eval["agreement_initial"], "ppv_difference": test_eval["ppv_difference"],
                      "h1": test_eval["h1"]}

    # AS2a
    core = svc.generate_mimar_report(U["tech"], run["id"], "core")
    svc.lock_report(U["tech"], core["id"])
    svc.log_effort(U["tech"], "MİMAR–Core report run", 1.5, core["id"])
    expert_rows = simulated_expert_findings(truth, data["los"], seed=7)
    exp = svc.import_expert_report(U["expert1"], ds["id"], expert_rows, authors=["expert1", "expert2"])
    svc.lock_report(U["expert1"], exp["id"])
    svc.log_effort(U["expert1"], "Expert–Core individual review", 14.0, exp["id"])
    svc.log_effort(U["expert2"], "Expert–Core individual review", 12.5, exp["id"])
    svc.log_effort(U["expert1"], "Expert–Core consensus", 3.0, exp["id"])
    prop = svc.propose_matches(U["std"], core["id"], exp["id"])
    confirmed = prop["matches"] + [m for m in prop["suggestions"] if m["jaccard"] >= 0.66]
    pool = svc.build_pool(U["std"], {"M": core["id"], "U": exp["id"]}, confirmed)

    def validate(pool_doc, val_seed_offset=0):
        svc.assign_validators(admin, pool_doc["id"], ["val1", "val2"], "vadj")
        entries = svc.pool_entries(U["val1"], pool_doc["id"])["entries"]
        for vn, vs in (("val1", 101 + val_seed_offset), ("val2", 202 + val_seed_offset)):
            for e in entries:
                d = simulated_validation(truth, e, vs)
                svc.validate(U[vn], pool_doc["id"], e["code"], d["support"], d["meaningful"], d["category_ok"],
                             suggested_category="" if d["category_ok"] == "yes" else e["category"])
            svc.lock_validations(U[vn], pool_doc["id"])
            svc.log_effort(U[vn], "Validation board", round(len(entries) / 25, 2), pool_doc["id"])
        for c in svc._pool_resolution(pool_doc["id"])["conflicts"]:
            e = next(x for x in entries if x["code"] == c["code"])
            d = simulated_validation(truth, e, 303, error_rate=0.02)
            svc.validation_adjudicate(U["vadj"], pool_doc["id"], c["code"], d)
        return entries

    entries = validate(pool)
    rng = random.Random(5)
    seal = svc.store.get_artifact(svc.store.get("pool", pool["id"])["seal_artifact"])
    singles = [e for e in entries if len(seal[e["code"]]["sources"]) == 1]
    for e in rng.sample(singles, min(20, len(singles))):
        svc.source_guess(U["val1"], pool["id"], e["code"], rng.choice(["M", "U"]))
    as2a = svc.as2a_results(admin, pool["id"], B=1000 if quick else 2000)
    summary["as2a"] = {"pool_id": pool["id"], "entries": len(entries), **{k: as2a[k] for k in
                       ("main", "h2a", "shared_findings", "by_category", "blinding_check")},
                       "agreement_final_ac1": as2a["agreement"].get("final_verification", {}).get("ac1")}

    # AS2b
    run_ext = svc.run_analysis(U["tech"], ds["id"], cfg["id"], with_materials=True, label="MİMAR–Extended (KuLearn)")
    ext = svc.generate_mimar_report(U["tech"], run_ext["id"], "extended")
    svc.lock_report(U["tech"], ext["id"])
    pool_b = svc.build_pool(U["std"], {"C": core["id"], "E": ext["id"]}, purpose="as2b")
    if pool_b["n_entries"]:
        validate(pool_b, 50)
    summary["as2b"] = svc.as2b_results(admin, pool_b["id"])

    # AS5
    s5 = svc.create_as5_sample(U["tech"], core["id"], n_max=300)
    items = svc.as5_queue(U["coord01"], s5["id"])["items"]
    r5 = random.Random(9)
    for i, it in enumerate(items):
        coord = f"coord{(i % 20) + 1:02d}"
        if r5.random() < 0.08:
            svc.as5_evaluate(U[coord], s5["id"], it["item"], None, None, completed=False)
            continue
        e = {"code": it["item"], "category": it["category"],
             "items": {"los": [s.get("lo") for s in it["support"] if s.get("lo")],
                       "ucep": [s.get("ucep") for s in it["support"] if s.get("ucep")]}}
        v = simulated_validation(truth, e, 404 + i % 20)
        svc.as5_evaluate(U[coord], s5["id"], it["item"], v["meaningful"] == "yes", r5.random() < 0.88)
    summary["as5"] = svc.as5_results(admin, s5["id"])

    # AS6
    t1 = svc.new_version(U["tech"], ds["id"], "T1", "After approved CDCC changes (synthetic)")
    los = sorted(svc.store.list("lo", parent=ds["id"]), key=lambda r: r["uid"])
    hyb = svc._analysis_obj(run["id"]).hybrid(depth=40)
    a_rm, b_rm = split_key(hyb[0]["pair"])
    changes = [{"op": "remove", "uid": b_rm, "decision_ref": "CDCC-2027-01"},
               {"op": "relink", "uid": los[3]["uid"], "ucep_links": ["SYN-UCEP-U01"], "decision_ref": "CDCC-2027-02"},
               {"op": "add", "uid": "SYN-NEW-001", "text": "Explain the indications and technique of bone marrow aspiration.",
                "activity": "Y3-MSK-PATH-S01", "course": "Musculoskeletal Pathology", "year": 3, "decision_ref": "CDCC-2027-03"}]
    svc.apply_changes(U["tech"], t1["id"], changes)
    svc.freeze_dataset(admin, t1["id"])
    cs = svc.create_changeset(U["tech"], ds["id"], t1["id"], cfg["id"], "real", "Synthetic CDCC changes", "CDCC-2027")
    exp_eff = [{"type": "removed_link", "entity": hyb[0]["pair"]},
               {"type": "ucep_link_added", "entity": f"SYN-UCEP-U01|{los[3]['uid']}"},
               {"type": "coverage_gained", "entity": "SYN-UCEP-U01"}]
    svc.register_expected(U["impact"], cs["id"], exp_eff)
    svc.lock_expected(U["impact"], cs["id"])
    rep = svc.run_impact(U["tech"], cs["id"])
    ev = svc.evaluate_changeset(U["impact"], cs["id"])
    summary["as6_real"] = {"changeset_id": cs["id"], "diff": {k: len(v) for k, v in rep["diff"].items()},
                           "alerts": len(rep["alerts"]), "verified_alerts": ev["verified_alerts"],
                           "missed_expected": ev["missed_expected"], "total_expected": ev["total_expected"]}
    if not quick:
        ctl = svc.controlled_test(U["tech"], ds["id"], cfg["id"], per_type=8)
        summary["as6_controlled"] = ctl["overall"]
    summary["audit"] = svc.store.verify_audit()
    summary["users"] = {k: v["token"] for k, v in U.items()}
    svc.store.put("demo_summary", summary, id="latest")
    return summary
