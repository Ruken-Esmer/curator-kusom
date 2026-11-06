"""Runs the whole MİMAR protocol once on real KUSOM sessions, following osteoarthritis.

Data are real: session titles of MSKL 303, MSKL 503 and IMED 410 from the 2025–26 timetables and the
musculoskeletal items of UÇEP-2020. People are not: reviewers, experts, validators and coordinators are
example accounts whose decisions follow the written rules below, so that every screen can be filled.
Every account name and record says "örnek".
"""
from __future__ import annotations

import hashlib
from typing import Any

from app.mimar.analysis import split_key
from app.mimar.service import MimarService

BLOCKS = ["MSKL 303", "MSKL 503", "IMED 410"]
DECISION = "CDCC-ÖRNEK"

USERS = [
    ("teknik", "Teknik sorumlu (örnek)", ["technical"]),
    ("hakem1", "Hakem 1 (örnek)", ["reviewer"]),
    ("hakem2", "Hakem 2 (örnek)", ["reviewer"]),
    ("hakem3", "Üçüncü hakem (örnek)", ["adjudicator"]),
    ("uzman1", "MSKL uzmanı 1 (örnek)", ["expert"]),
    ("uzman2", "MSKL uzmanı 2 (örnek)", ["expert"]),
    ("standart", "Standardizasyon sorumlusu (örnek)", ["standardizer"]),
    ("dogrulayici1", "Doğrulayıcı – temel bilimler (örnek)", ["validator"]),
    ("dogrulayici2", "Doğrulayıcı – klinik (örnek)", ["validator"]),
    ("dogrulayici3", "Doğrulama üçüncü kişi (örnek)", ["adjudicator"]),
    ("etki", "Etki değerlendiricisi (örnek)", ["impact_evaluator", "coordinator"]),
] + [(f"koordinator{i:02d}", f"Blok koordinatörü {i:02d} (örnek)", ["coordinator"]) for i in range(1, 21)]

# example decision rule: two sessions are "the same content" when they fall in the same topic group
TOPICS: list[tuple[str, tuple[str, ...]]] = [
    ("osteoartrit", ("osteoarthritis", "joint pain", "differential diagnosis of arthritis", "joint failure", "degenerative")),
    ("romatizmal", ("rheumat", "autoimmune", "lupus", "vasculitis", "gout", "spondyl", "inflammatory bone")),
    ("kırık", ("fracture", "dislocation")),
    ("omurga", ("spine", "spinal", "disc herniation", "vertebra")),
    ("enfeksiyon", ("infection", "osteomyelitis", "septic")),
    ("tümör", ("tumor", "tumour", "neoplasm")),
    ("osteoporoz", ("osteoporo", "bone turnover")),
    ("ağrı ve analjezi", ("nsaid", "analges", "opioid", "pain physiology", "eicosanoid")),
]


def topic(text: str) -> str | None:
    t = text.lower()
    for name, keys in TOPICS:
        if any(k in t for k in keys):
            return name
    return None


def _flip(*parts: str, every: int) -> bool:
    """Deterministic small disagreement so that adjudication has something to do."""
    return int(hashlib.sha1("|".join(parts).encode()).hexdigest(), 16) % every == 0


def _users(svc: MimarService, admin: dict) -> dict[str, dict]:
    out = {}
    for un, dn, roles in USERS:
        if svc.store.get("user", un) is None:
            tok = svc.create_user(admin, un, dn, roles)["token"]
        else:
            tok = svc.rotate_token(admin, un)["token"]
        out[un] = {**svc.store.get("user", un), "token": tok}
    return out


def _find(rows: list[dict], course: str, title: str) -> str:
    return next(r["uid"] for r in rows if r["course"] == course and r["text"] == title)


def run(svc: MimarService, admin: dict) -> dict[str, Any]:
    from app.api.routes.mimar import kusom_los_rows
    from app.data.ucep.ucep_list import ucep_rows

    U = _users(svc, admin)
    rows = [{**r, "source": "KUSOM 2025–26 ders programı"} for r in kusom_los_rows(BLOCKS)]
    text = {r["uid"]: r for r in rows}
    T = lambda u: topic(text[u]["text"]) if u in text else None
    oa = {
        "joint_pain": _find(rows, "MSKL 303", "Approach to the patient with joint pain: Is it inflammatory?"),
        "ddx": _find(rows, "IMED 410", "Differential diagnosis of arthritis"),
        "oa303": _find(rows, "MSKL 303", "Osteoarthritis and non-inflammatory arthritis"),
        "oa503": _find(rows, "MSKL 503", "Osteoarthritis: How to Deal With a Joint Failure"),
        "mgmt503": _find(rows, "MSKL 503", "Management of Osteoarthritis"),
        "nsaid303": _find(rows, "MSKL 303", "Eicosanoids & Nonsteroidal antiinflammatory drugs"),
        "nsaid503": _find(rows, "MSKL 503", "NSAIDS, OPIOIDS, Adjuvants for Analgesics"),
        "exercise": _find(rows, "MSKL 503", "How To Prescribe Exercise In A Patient With Musculoskeletal Disorder/Injury?"),
    }
    summary: dict[str, Any] = {"note": "Veri gerçek (KUSOM ders başlıkları, UÇEP-2020). Kişiler ve kararları örnek."}

    # İP1 · data
    ds = svc.create_dataset(U["teknik"], "MSKL ve romatoloji oturumları (KUSOM 2025–26)", "MSKL", "T0",
                            "MSKL 303, MSKL 503 ve IMED 410 oturum başlıkları; yazılı hedef belgeleri henüz yok")
    qc = svc.import_los(U["teknik"], ds["id"], rows)
    svc.import_ucep(U["teknik"], ds["id"], [{**u, "domain": "Hastalık", "mskl_scope": "1"} for u in ucep_rows(["Kas-İskelet"])])
    # KuLearn: only the osteoarthritis sessions, written as examples
    svc.import_materials(U["teknik"], ds["id"], [
        {"activity": oa["oa303"], "title": "Ders slaytları (örnek metin)", "location": "slayt 1-24", "version": "2025-2026",
         "permission": "yes", "license": "KU iç kullanım",
         "text": "Osteoarthritis risk factors, joint pain without inflammation, radiographic findings, exercise and weight loss, "
                 "paracetamol and NSAIDs, follow-up of function and pain in primary care."},
        {"activity": oa["ddx"], "title": "Ders slaytları (örnek metin)", "location": "slayt 1-30", "version": "2025-2026",
         "permission": "yes", "license": "KU iç kullanım",
         "text": "Inflammatory versus non-inflammatory joint pain, morning stiffness, osteoarthritis versus rheumatoid arthritis, "
                 "gout, septic arthritis, joint aspiration."},
        {"activity": oa["mgmt503"], "title": "Vaka metni (örnek)", "location": "vaka 1", "version": "",
         "permission": "yes", "license": "KU iç kullanım", "text": "A 64-year-old woman with knee osteoarthritis."},
    ])
    ds = svc.freeze_dataset(admin, ds["id"])
    summary["ip1"] = {"dataset_id": ds["id"], "qc": qc}

    cfg = svc.create_config(U["teknik"], "MSKL varsayılan v1", {"list_depth": 60})
    run_ = svc.run_analysis(U["teknik"], ds["id"], cfg["id"])
    plan = svc.create_plan(admin, run_["id"], {"dev_n": 60, "test_n": 120, "min_positives": 5, "min_per_stratum": 5,
                                                "bootstrap_B": 500})

    def review(sample):
        svc.assign_reviewers(U["teknik"], sample["id"], ["hakem1", "hakem2"], "hakem3")
        inv = {v: k for k, v in svc.store.get("sample", sample["id"])["codes"].items()}
        for rv, every in (("hakem1", 9), ("hakem2", 7)):
            for it in svc.review_queue(U[rv], sample["id"])["items"]:
                a, b = split_key(inv[it["code"]])
                same = T(a) is not None and T(a) == T(b)
                if _flip(rv, a, b, every=every):
                    same = not same
                svc.decide(U[rv], sample["id"], it["code"], "overlap" if same else "no_overlap",
                           "örnek karar: aynı konu grubu" if same else "örnek karar: farklı konu")
            svc.lock_decisions(U[rv], sample["id"])
        for c in svc.conflicts(sample["id"]):
            a, b = split_key(c["item"])
            svc.adjudicate(U["hakem3"], sample["id"], c["code"],
                           "overlap" if T(a) is not None and T(a) == T(b) else "no_overlap", "örnek karar")
        return svc.evaluate_sample(admin, sample["id"])

    dev = svc.create_as1_sample(U["teknik"], run_["id"], "dev")
    dev_eval = review(dev)
    plan = svc.lock_plan(admin, plan["id"])
    test = svc.create_as1_sample(U["teknik"], run_["id"], "test")
    test_eval = review(test)
    summary["ip1"].update({"analysis_id": run_["id"], "plan_lock": plan["lock_hash"][:12], "comparator": plan["comparator"],
                           "dev_n": dev["n"], "test_n": test["n"], "h1": test_eval.get("h1")})

    # İP2 · expert report vs MİMAR report, blind validation
    core = svc.generate_mimar_report(U["teknik"], run_["id"], "core")
    svc.lock_report(U["teknik"], core["id"])
    expert_rows = [
        {"category": "redundancy", "los": sorted([oa["joint_pain"], oa["ddx"]]),
         "statement": "Eklem ağrısına yaklaşım (3. sınıf) ile artritlerde ayırıcı tanı (4. sınıf) aynı içeriği işliyor olabilir.",
         "rationale": "İçerik karşılaştırılmalı; 4. sınıf dersi vaka temelli ve daha ileri düzeyde olmalı."},
        {"category": "integration", "los": sorted([oa["oa303"], oa["mgmt503"]]),
         "statement": "3. sınıf osteoartrit dersi ile 5. sınıf osteoartrit vaka tartışması açıkça bağlanabilir.",
         "rationale": "Aynı hasta vakası iki yılda kullanılabilir."},
        {"category": "redundancy", "los": sorted([oa["nsaid303"], oa["nsaid503"]]),
         "statement": "NSAİİ farmakolojisi 3. ve 5. sınıfta benzer düzeyde anlatılıyor olabilir.",
         "rationale": "5. sınıf dersi reçete ve yan etki yönetimine odaklanmalı."},
        {"category": "gap_ucep", "ucep": ["UCEP2020-H237"],
         "statement": "UÇEP osteoartrit maddesindeki izlem (İ) düzeyi hiçbir oturumda karşılanmıyor.",
         "rationale": "Birinci basamakta uzun süreli izlem için bir öğrenme hedefi gerekli."},
    ]
    exp = svc.import_expert_report(U["uzman1"], ds["id"], expert_rows, authors=["uzman1", "uzman2"])
    svc.lock_report(U["uzman1"], exp["id"])
    for un, act, h in (("teknik", "MİMAR raporu çalıştırma", 0.5), ("uzman1", "Uzman bireysel inceleme", 6.0),
                       ("uzman2", "Uzman bireysel inceleme", 5.5), ("uzman1", "Uzman uzlaşı toplantısı", 1.5)):
        svc.log_effort(U[un], act, h, exp["id"], "örnek süre")
    prop = svc.propose_matches(U["standart"], core["id"], exp["id"])
    pool = svc.build_pool(U["standart"], {"M": core["id"], "U": exp["id"]}, prop["matches"])

    def entry_ok(e: dict) -> bool:
        los, uc = e["items"].get("los", []), e["items"].get("ucep", [])
        if e["category"] == "gap_ucep":
            return uc == ["UCEP2020-H237"]
        ts = {T(u) for u in los}
        return len(los) >= 2 and len(ts) == 1 and None not in ts

    svc.assign_validators(admin, pool["id"], ["dogrulayici1", "dogrulayici2"], "dogrulayici3")
    entries = svc.pool_entries(U["dogrulayici1"], pool["id"])["entries"]
    for vn in ("dogrulayici1", "dogrulayici2"):
        for e in entries:
            ok = entry_ok(e) != _flip(vn, e["code"], every=8)
            svc.validate(U[vn], pool["id"], e["code"], "yes" if ok else "no", "yes" if ok else "no", "yes", rationale="örnek karar")
        svc.lock_validations(U[vn], pool["id"])
    for c in svc._pool_resolution(pool["id"])["conflicts"]:
        e = next(x for x in entries if x["code"] == c["code"])
        ok = entry_ok(e)
        svc.validation_adjudicate(U["dogrulayici3"], pool["id"], c["code"],
                                  {"support": "yes" if ok else "no", "meaningful": "yes" if ok else "no", "category_ok": "yes"})
    as2a = svc.as2a_results(admin, pool["id"], B=500)
    summary["ip2"] = {"core": core["id"], "expert": exp["id"], "pool": pool["id"], "entries": len(entries),
                      "main": as2a.get("main"), "shared": as2a.get("shared_findings")}

    # İP4 · coordinators judge the findings
    s5 = svc.create_as5_sample(U["teknik"], core["id"], n_max=60)
    items = svc.as5_queue(U["koordinator01"], s5["id"])["items"]
    for i, it in enumerate(items):
        e = {"category": it["category"], "items": {"los": [s.get("lo") for s in it["support"] if s.get("lo")],
                                                   "ucep": [s.get("ucep") for s in it["support"] if s.get("ucep")]}}
        coord = f"koordinator{(i % 20) + 1:02d}"
        svc.as5_evaluate(U[coord], s5["id"], it["item"], entry_ok(e), not _flip(coord, it["item"], every=6))
    summary["ip4"] = {"sample": s5["id"], "items": len(items)}

    # İP3 + İP5 · committee decision applied to a new version, expected effects registered first
    t1 = svc.new_version(U["teknik"], ds["id"], "T1", "Kurul kararı sonrası (örnek karar)")
    new_uid = "MSKL503:izlem-oa"
    svc.apply_changes(U["teknik"], t1["id"], [
        {"op": "add", "uid": new_uid, "activity": new_uid, "course": "MSKL 503", "year": 5,
         "text": "Plan the long-term follow-up of a patient with osteoarthritis in primary care: pain, function, exercise and weight loss.",
         "ucep_links": ["UCEP2020-H237"], "decision_ref": f"{DECISION}-01"},
        {"op": "modify", "uid": oa["ddx"], "text": "Case-based differential diagnosis of arthritis: osteoarthritis, rheumatoid arthritis, gout and septic arthritis",
         "decision_ref": f"{DECISION}-02"},
    ])
    svc.freeze_dataset(admin, t1["id"])
    cs = svc.create_changeset(U["teknik"], ds["id"], t1["id"], cfg["id"], "real",
                              "Osteoartrit: izlem hedefi eklendi, ayırıcı tanı dersi vaka temelli yapıldı (örnek karar)", DECISION)
    from app.mimar.analysis import pair_key
    svc.register_expected(U["etki"], cs["id"], [
        {"type": "ucep_link_added", "entity": f"UCEP2020-H237|{new_uid}"},
        {"type": "new_link", "entity": pair_key(new_uid, oa["oa303"])},
        {"type": "new_link", "entity": pair_key(new_uid, oa["exercise"])},
        {"type": "changed_link", "entity": pair_key(oa["joint_pain"], oa["ddx"])},
    ])
    svc.lock_expected(U["etki"], cs["id"])
    rep = svc.run_impact(U["teknik"], cs["id"])
    for a in rep["alerts"]:
        svc.decide_alert(U["etki"], cs["id"], a["id"], verified=any(c in (new_uid, oa["ddx"]) for c in a.get("cause", [])),
                         rationale="örnek karar")
    ev = svc.evaluate_changeset(U["etki"], cs["id"])
    summary["ip5"] = {"changeset": cs["id"], "alerts": len(rep["alerts"]), "diff": {k: len(v) for k, v in rep["diff"].items()},
                      "missed_expected": ev.get("missed_expected"), "total_expected": ev.get("total_expected")}
    summary["oa"] = oa
    summary["users"] = {k: v["token"] for k, v in U.items()}
    svc.store.put("osteo_run", summary, id="latest")
    return summary
