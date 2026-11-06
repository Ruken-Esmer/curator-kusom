"""Data for the seven screens of the prototype, built from the latest osteoarthritis run.

Everything is read from the store; nothing here makes a decision. Records that only exist outside the
system (focus groups, committee meetings, faculty visits) are kept as short notes and are empty until
someone writes one.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.mimar.analysis import split_key
from app.mimar.service import MimarService

REASON_TR = {
    "not_reviewable_too_short": "başlık tek başına incelenemeyecek kadar kısa",
    "missing_text": "metin yok", "missing_uid": "kimlik yok", "duplicate_uid": "aynı kimlik iki kez",
    "version_unclear": "sürümü belli değil", "no_documented_permission": "kullanım izni belgelenmemiş",
    "activity_unknown": "hangi derse ait olduğu belli değil", "not_processable_empty_text": "metin boş",
}
CATEGORY_TR = {"redundancy": "Olası gereksiz tekrar", "integration": "Bağlanabilecek dersler", "gap_ucep": "UÇEP eksikliği"}
RECORD_KINDS = {"ucep_check", "term_check", "focus_group", "decision", "visit", "workshop"}
OA = ("osteoarth", "joint pain", "differential diagnosis of arthritis", "joint failure", "follow-up of a patient with osteo")


def _is_oa(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in OA)


def records(svc: MimarService, kind: str) -> list[dict[str, Any]]:
    return sorted(svc.store.list("proto_record", kind=kind), key=lambda r: (r["created_at"], r.get("key", "")))


def _ucep_name(code: str) -> str:
    from app.data.ucep.ucep_list import load
    it = next((i for i in load()["items"] if i["code"] == code), None)
    return f"{it['text_tr']} (UÇEP madde {it['no']})" if it else code


def add_record(svc: MimarService, user: dict, kind: str, data: dict[str, Any]) -> dict[str, Any]:
    if kind not in RECORD_KINDS:
        raise ValueError(f"unknown record kind '{kind}'")
    rec = svc.store.put("proto_record", {"kind": kind, "by": user["username"], "by_name": user.get("display_name", ""),
                                         "example": bool(data.pop("example", False)), **data})
    svc._audit(user, f"record.{kind}", rec["id"])
    return rec


def _names(svc: MimarService, t0: str, t1: str) -> dict[str, dict[str, Any]]:
    """T0 names win; T1 only adds what is new. Sessions dropped by quality control keep their timetable title."""
    from app.api.routes.mimar import kusom_los_rows
    from app.mimar.osteo_run import BLOCKS
    out: dict[str, dict[str, Any]] = {r["uid"]: {"year": r["year"], "course": r["course"], "text": r["text"], "excluded": True}
                                      for r in kusom_los_rows(BLOCKS)}
    for d in (t0, t1):
        for r in svc.store.list("lo", parent=d):
            if d == t0 or r["uid"] not in out or out[r["uid"]].get("excluded"):
                out[r["uid"]] = {"year": r["year"], "course": r["course"], "text": r["text"]}
    return out


def _approval(svc: MimarService, kind: str) -> dict[str, dict[str, Any]]:
    return {r["key"]: r for r in records(svc, kind)}


def view(svc: MimarService) -> dict[str, Any] | None:
    s = svc.store.get("osteo_run", "latest")
    if not s:
        return None
    admin = svc.store.get("user", "admin")
    t0 = svc.dataset_detail(s["ip1"]["dataset_id"])
    t1_id = s["ip5"]["t1"]
    t1 = svc.dataset_detail(t1_id)
    N = _names(svc, t0["id"], t1_id)
    lo = lambda u: N.get(u, {"year": None, "course": "", "text": u})
    oa_ids = s["oa"]

    # Veriler
    qc = t0["qc_report"]
    ucep_ok, term_ok = _approval(svc, "ucep_check"), _approval(svc, "term_check")
    ucep = [{"code": u["code"], "tr": u["text_tr"], "en": u.get("text_en", ""), "check": ucep_ok.get(u["code"])}
            for u in sorted(svc.ucep_rows(t0["id"]), key=lambda u: u["code"])]
    in_t0 = {r["uid"] for r in svc.store.list("lo", parent=t0["id"])}
    oa_all = sorted(({"uid": u, **v} for u, v in N.items() if _is_oa(v["text"]) and (u in in_t0 or v.get("excluded"))),
                    key=lambda r: (r["year"], r["course"], r["text"]))
    oa_rows = [r for r in oa_all if r["uid"] in in_t0]
    terms = [{"uid": r["uid"], **r, "suggested": "Osteoarthritis", "source": "UÇEP-2020 madde 237 İngilizce adı",
              "check": term_ok.get(r["uid"])} for r in oa_rows]
    data = {
        "versions": [{"label": d["version_label"], "name": d["name"], "count": d["counts"]["los"], "frozen": d["status"] != "draft",
                      "description": d.get("description", "")} for d in (t0, t1)],
        "received": qc["rows_received"], "included": qc["included"], "excluded": qc["excluded"],
        "by_year": qc.get("by_year", {}), "by_course": qc.get("by_course", {}),
        "reasons": [{"reason": REASON_TR.get(k, k), "n": v} for k, v in qc.get("exclusion_reasons", {}).items()],
        "excluded_examples": [x.get("text", "") for x in t0.get("qc_exclusions", [])][:12],
        "oa_rows": oa_all, "ucep": ucep, "terms": terms,
        "missing": ["MSKL 303 ve MSKL 503 yazılı öğrenim hedefi belgeleri", "Ders içerikleri (yalnız iki örnek metin var)"],
    }

    # Karşılaştırma
    a = svc._analysis_obj(s["ip1"]["analysis_id"])
    hyb = a.hybrid(depth=400)

    def pair(h):
        x, y = split_key(h["pair"])
        return {"rank": h["rank"], "a": lo(x), "b": lo(y), "methods": h.get("method_ranks", {})}
    top = [pair(h) for h in hyb[:8]]
    oa_pairs = [pair(h) for h in hyb if _is_oa(lo(split_key(h["pair"])[0])["text"]) or _is_oa(lo(split_key(h["pair"])[1])["text"])][:6]
    samples = {x["part"]: x for x in svc.store.list("sample", analysis_id=s["ip1"]["analysis_id"]) if x.get("kind") == "as1"}

    def sample_view(x):
        ev = x.get("evaluation", {})
        labels = svc.final_labels(x["id"])["labels"]
        pos = sum(1 for v in labels.values() if v)
        m = ev.get("metrics", {}).get("methods", {}).get("hybrid", {})
        return {"n": x["n"], "agreement": ev.get("agreement_initial", {}).get("percent"), "conflicts": len(svc.conflicts(x["id"])),
                "positives": pos, "sensitivity": m.get("sensitivity"), "ppv": m.get("ppv")}
    # a reviewed pair to show as a card: prefer one touching the osteoarthritis sessions
    dev = samples.get("dev")
    card = None
    if dev:
        inv = {v: k for k, v in dev["codes"].items()}
        decs = svc.store.list("decision", parent=dev["id"])
        by: dict[str, dict[str, Any]] = {}
        for d in decs:
            by.setdefault(d["code"], {})[d["reviewer"]] = d["value"]
        codes = sorted(by, key=lambda c: (not any(_is_oa(lo(u)["text"]) for u in split_key(inv[c])),
                                          not any(T in lo(u)["text"].lower() for u in split_key(inv[c]) for T in ("arthrit", "rheumat"))))
        if codes:
            x, y = split_key(inv[codes[0]])
            card = {"a": lo(x), "b": lo(y), "decisions": by[codes[0]]}
    compare = {"titles": len(a.los), "pairs": len(a.hybrid()), "top": top, "oa_pairs": oa_pairs, "oa_first_rank": oa_pairs[0]["rank"] if oa_pairs else None,
               "dev": sample_view(samples["dev"]) if "dev" in samples else None,
               "test": sample_view(samples["test"]) if "test" in samples else None, "card": card,
               "plan_locked": bool(s["ip1"].get("plan_lock"))}

    # Uzman incelemesi
    def findings(rid):
        return svc.report_findings(admin, rid)["findings"]
    seal = svc.store.get_artifact(svc.store.get("pool", s["ip2"]["pool"])["seal_artifact"])
    final = svc._pool_resolution(s["ip2"]["pool"])["final"]
    verified_by_key = {}
    for code, v in seal.items():
        for src, key in v["keys"].items():
            verified_by_key[(src, key)] = final.get(code, {}).get("verified")

    def fview(f, src):
        return {"category": CATEGORY_TR.get(f["category"], f["category"]), "statement": f["statement"],
                "sessions": [lo(u) for u in f["items"].get("los", [])], "ucep": [_ucep_name(c) for c in f["items"].get("ucep", [])],
                "verified": verified_by_key.get((src, f["key"]))}
    exp_f = [fview(f, "U") for f in findings(s["ip2"]["expert"])]
    sys_f = [fview(f, "M") for f in findings(s["ip2"]["core"])]
    main = s["ip2"]["main"]
    effort = svc.effort_summary()
    expert = {"expert": exp_f, "system_count": len(sys_f), "system_oa": [f for f in sys_f if any(_is_oa(x["text"]) for x in f["sessions"])],
              "system_examples": sys_f[:5], "shared": s["ip2"]["shared"],
              "validated": {"system": [main["V_M"], main["N_M"]], "expert": [main["V_U"], main["N_U"]]},
              "agreement": svc.pool_status(s["ip2"]["pool"])["agreement"]["final_verification"]["percent"],
              "kulearn": {**t0["materials_report"], "unusable_reasons": [{"reason": REASON_TR.get(k, k), "n": v} for k, v in
                                                                         t0["materials_report"].get("unusable_reasons", {}).items()],
                          **s["ip2"].get("kulearn", {})},
              "hours": effort["by_activity"], "hours_total": effort["total_person_hours"]}

    # Kurul kararları
    t1_doc = svc.store.get("dataset", t1_id)
    T1 = {r["uid"]: {"year": r["year"], "course": r["course"], "text": r["text"]} for r in svc.store.list("lo", parent=t1_id)}
    changes = [{"op": {"add": "eklendi", "modify": "metni değişti", "remove": "kaldırıldı", "relink": "UÇEP bağlantısı değişti"}[c["op"]],
                "ref": c.get("decision_ref", ""), "after": T1.get(c["uid"]), "before": N.get(c["uid"]) if c["op"] != "add" else None}
               for c in t1_doc.get("change_log", [])]
    t0_oa = oa_rows
    t1_oa = sorted(({"uid": r["uid"], "year": r["year"], "course": r["course"], "text": r["text"]}
                    for r in svc.store.list("lo", parent=t1_id) if _is_oa(r["text"])), key=lambda r: (r["year"], r["course"]))
    committee = {"focus_groups": records(svc, "focus_group"), "decisions": records(svc, "decision"), "changes": changes,
                 "t0": t0_oa, "t1": t1_oa,
                 "t0_followup": any("follow-up" in r["text"].lower() for r in t0_oa),
                 "t1_followup": any("follow-up" in r["text"].lower() for r in t1_oa)}

    # Tüm müfredat
    from app.audit.scenario import wp4
    w = wp4()
    as5 = svc.as5_results(admin, s["ip4"]["sample"])
    whole = {"years": [{"year": y, "present": y in w["years"]} for y in range(1, 7)],
             "titles": w["titles"], "redundancy": w["redundancy"], "integration": w["integration"], "high": w["high"],
             "seconds": w["seconds"], "diseases_with_sessions": w["diseases_with_sessions"], "diseases_with_profile": w["diseases_with_profile"],
             "coordinators": {"items": as5["n_selected"], "done": as5["n_completed"], "people": as5["coordinators"],
                              "meaningful": as5["meaningful_rate"], "feasible": as5["feasible_rate"], "both": as5["joint_rate"],
                              "target": as5["target"], "met": as5["verdict"] == "target_met"}}

    # Değişikliğin etkisi
    cs_id = s["ip5"]["changeset"]
    ev = svc.evaluate_changeset(admin, cs_id)
    rep = svc.changeset_report(admin, cs_id)["report"]
    TYPE = {"new_link": "yeni bağlantı", "removed_link": "kaldırılan bağlantı", "changed_link": "değişen bağlantı",
            "ucep_link_added": "UÇEP bağlantısı eklendi", "ucep_link_removed": "UÇEP bağlantısı kaldırıldı",
            "coverage_gained": "UÇEP maddesi karşılandı", "coverage_lost": "UÇEP maddesi karşılanmaz oldu"}

    def ent(key):
        typ, _, e = key.partition(":")
        parts = [(T1.get(u) or lo(u)) if not u.startswith("UCEP") else {"year": None, "course": "", "text": _ucep_name(u)} for u in e.split("|")]
        return {"type": TYPE.get(typ, typ), "items": parts}
    impact = {"description": svc.store.get("changeset", cs_id)["description"],
              "expected": [{**ent(r["key"]), "shown": r["reported"]} for r in ev["expected"]],
              "alerts": [{**ent(a["key"]), "verified": next(r["verified"] for r in ev["alerts"] if r["id"] == a["id"])} for a in rep["alerts"]],
              "missed": ev["missed_expected"], "total_expected": ev["total_expected"]}

    # Diğer fakülteler
    faculties = {"checklist": [
        {"item": "Her oturum için başlık, sınıf, blok ve tarih", "kusom": "var", "note": "2.–5. sınıf ders programları"},
        {"item": "1. ve 6. sınıf ders programları", "kusom": "eksik", "note": "henüz alınmadı"},
        {"item": "Her blok için yazılı öğrenim hedefi belgesi", "kusom": "kısmen", "note": "yalnız CIRC 204, ERUS 206, NUTI 205"},
        {"item": "Ders içerikleri (slayt, ders notu) ve kullanım izni", "kusom": "eksik", "note": "yalnız iki örnek metin"},
        {"item": "UÇEP-2020 maddeleriyle eşleştirme", "kusom": "var", "note": f"{w['diseases_with_sessions']} hastalık derslerde geçiyor"},
    ], "visits": records(svc, "visit"), "workshops": records(svc, "workshop")}

    return {"note": s["note"], "data": data, "compare": compare, "expert": expert, "committee": committee,
            "whole": whole, "impact": impact, "faculties": faculties, "oa": oa_ids}
