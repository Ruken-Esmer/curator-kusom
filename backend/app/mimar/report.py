"""Integrated input → output analysis."""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any

from app.mimar.analysis import AnalysisConfig, LORecord, OverlapAnalysis, split_key
from app.mimar.findings import generate_mimar_findings, ucep_correspondence
from app.mimar.impact import impact_alerts
from app.mimar.qc import prepare_learning_objectives, prepare_ucep
from app.mimar.text import bloom_level, tokenize

BLOOM_TR = {0: "belirsiz", 1: "hatırlama", 2: "anlama", 3: "uygulama", 4: "analiz", 5: "değerlendirme", 6: "planlama/yönetme"}
REASON_TR = {
    "empty_text": "boş metin", "missing_persistent_id": "kimlik yok", "duplicate_id": "yinelenen kimlik",
    "missing_source": "kaynak yok", "missing_activity": "eğitim etkinliği yok",
    "not_reviewable_too_short": "incelemeye yetecek içerik yok",
    "duplicate_text_in_same_activity": "aynı etkinlikte aynı metin",
}


def _cfg(n: int, depth: int) -> AnalysisConfig:
    cfg = AnalysisConfig(list_depth=depth, per_query_k=max(1, min(10, n - 1)))
    if n < 60:                       # small inputs: allow frequent concepts
        cfg.concept.max_df_ratio = 0.5
    return cfg


def _records(rows: list[dict], material: dict[str, str] | None = None) -> list[LORecord]:
    material = material or {}
    return [LORecord(uid=r["uid"], text=r["text"], activity=r["activity"], course=r.get("course", ""),
                     year=int(r.get("year") or 0), discipline=r.get("discipline", ""),
                     ucep_links=r.get("ucep_links", []), context=material.get(r["uid"], "")) for r in rows]


def _priority(f: dict, los: dict[str, LORecord], pair_ranks: dict[str, int], n_pairs: int) -> dict[str, Any]:
    """Transparent priority score (0–100) and feasibility from record features."""
    items = f["items"]["los"]
    courses = {los[u].course for u in items if u in los}
    years = {los[u].year for u in items if u in los}
    if f["category"] == "redundancy":
        best = min((pair_ranks.get(k, n_pairs) for k in f.get("evidence", {}).get("pairs", [])), default=n_pairs)
        strength = 1 - (best - 1) / max(1, n_pairs)
        same_level = len({bloom_level(los[u].text) for u in items if u in los}) == 1
        score = 50 * strength + 20 * (len(items) >= 3) + 15 * same_level + 15 * (len(years) == 1)
        why = [f"üç yöntemin ortak sıralamasında {best}. sırada"]
        if same_level:
            why.append("beklenen bilişsel düzey aynı")
        if len(years) == 1:
            why.append("aynı sınıfta tekrar ediyor")
    elif f["category"] == "gap_ucep":
        no_clear = not items
        score = 70 + 15 * no_clear
        why = ["incelenen kayıtlarda açık karşılığı yok" if no_clear else "yalnız zayıf karşılık var"]
    else:
        score = 35 + 10 * (len(years) > 1)
        why = ["temel ve klinik yıllar arasında kayıtlı bağlantı yok"]
    n_c = len(courses)
    feas = "kolay" if n_c <= 1 or f["category"] == "integration" else ("orta" if n_c == 2 else "zor")
    level = "yüksek" if score >= 70 else "orta" if score >= 45 else "düşük"
    return {"score": round(score), "level": level, "feasibility": feas,
            "feasibility_reason": f"{n_c} ders etkileniyor" if n_c else "yeni hedef eklenmesi gerekiyor",
            "why": why}


def _proposal(f: dict, los: dict[str, LORecord], ucep_by: dict[str, dict]) -> dict[str, Any]:
    items = [los[u] for u in f["items"]["los"] if u in los]
    if f["category"] == "redundancy":
        keep = sorted(items, key=lambda x: (x.year, x.uid))[0]
        others = [x for x in items if x.uid != keep.uid]
        return {"action": "birleştir_veya_düzey_yükselt",
                "text": (f"{keep.uid} ({keep.year}. sınıf, {keep.course}) temel hedef olarak kalsın; "
                         + ", ".join(f"{x.uid} ({x.year}. sınıf, {x.course})" for x in others)
                         + " ya kaldırılsın ya da uygulama/klinik karar düzeyine yükseltilerek yeniden yazılsın."),
                "remove": [x.uid for x in others]}
    if f["category"] == "gap_ucep":
        code = f["items"]["ucep"][0]
        u = ucep_by.get(code, {})
        host = items[0] if items else None
        return {"action": "hedef_ekle",
                "text": (f"{code} için açık bir öğrenme hedefi eklensin"
                         + (f"; en yakın içerik {host.uid} ({host.course}) olduğundan bu derste genişletilebilir." if host
                            else "; uygun ders koordinatörlerce belirlenmeli.")),
                "add": {"code": code, "text": u.get("text_en") or u.get("text_tr", ""),
                        "course": host.course if host else "", "activity": host.activity if host else f"NEW-{code}",
                        "year": host.year if host else 0}}
    a, b = sorted(items, key=lambda x: x.year)[:2] if len(items) >= 2 else (items + items)[:2]
    return {"action": "bağlantı_kur",
            "text": f"{a.uid} ({a.year}. sınıf) ile {b.uid} ({b.year}. sınıf) arasında ortak vaka veya çapraz atıf kurulsun."}


def _questions(f: dict, los: dict[str, LORecord]) -> dict[str, str]:
    items = [los[u] for u in f["items"]["los"] if u in los]
    courses = " ve ".join(sorted({x.course for x in items})) or "ilgili derslerde"
    topic = re.search(r"“(.+?)”", f["statement"])
    t = topic.group(1) if topic else "bu konu"
    if f["category"] == "redundancy":
        return {"öğrenci": f"“{t}” konusunu {courses} derslerinde gördüğünüzde ikinci kez yeni bir şey öğrendiniz mi, yoksa aynı içeriği mi tekrarladınız?",
                "öğretim_üyesi": f"{courses} dersleri arasında “{t}” içeriği nasıl paylaşılıyor; ikinci anlatım farklı bir amaç taşıyor mu?"}
    if f["category"] == "gap_ucep":
        return {"öğrenci": f"Bu UÇEP konusuyla ({f['items']['ucep'][0]}) eğitiminiz boyunca nerede karşılaştınız?",
                "öğretim_üyesi": "Bu konu programda kayıtlara yansımadan öğretiliyor mu; yansımıyorsa hangi derste ele alınmalı?"}
    return {"öğrenci": f"{courses} derslerinde “{t}” konusunun temel ve klinik yönlerini ilişkilendirebildiniz mi?",
            "öğretim_üyesi": "Bu iki dersi bağlayan ortak bir vaka veya etkinlik uygulanabilir mi?"}


def _statement_tr(f: dict, los: dict[str, LORecord], ucep_by: dict[str, dict]) -> tuple[str, str]:
    m = re.search(r"“(.+?)”", f["statement"])
    topic = m.group(1) if m else "ortak içerik"
    items = [los[u] for u in f["items"]["los"] if u in los]
    if f["category"] == "redundancy":
        courses = ", ".join(sorted({x.course for x in items}))
        years = ", ".join(str(y) for y in sorted({x.year for x in items}))
        return (f"{len(items)} hedef ({courses}; {years}. sınıf) aynı içeriği (“{topic}”) benzer beklenen düzeyde ele alıyor.",
                "Tekrar öğrenmeyi derinleştirmiyor görünüyor; uzmanlar pekiştirme mi yoksa gereksiz tekrar mı olduğunu değerlendirmeli.")
    if f["category"] == "gap_ucep":
        code = f["items"]["ucep"][0]
        u = ucep_by.get(code, {})
        weak = bool(items)
        return (f"{code} (“{u.get('text_tr') or u.get('text_en', '')}”) için incelenen hedeflerde "
                + ("yalnız zayıf bir karşılık var." if weak else "açık bir karşılık bulunamadı."),
                "Kayıtlarda karşılık olmaması konunun hiç öğretilmediği anlamına gelmez; incelenen bloklarda beklenip beklenmediği kontrol edilmeli.")
    a, b = (sorted(items, key=lambda x: x.year) + items)[:2]
    return (f"“{topic}” konusu {a.year}. sınıfta ({a.course}) ve {b.year}. sınıfta ({b.course}) farklı açılardan ele alınıyor; aralarında kayıtlı bağlantı yok.",
            "Ortak bir vaka veya çapraz atıf temel ve klinik bilgiyi birleştirebilir; aynı konudan söz edilmesi tek başına yeterli değildir.")


_ROUTINE = frozenset(tokenize("describe explain define identify list discuss know understand learn recognize "
                               "state outline compare classify name various types type role roles major some normal "
                               "important basic general relation related main"))


# words that name a process rather than an entity; two objectives that differ only by
# these ("regulation of calcium" / "control of serum calcium") teach the same thing
_PROCESS = frozenset(tokenize("regulation regulate regulates control controls controlled maintenance maintain "
                               "homeostasis serum plasma level levels"))


def _parallel(texts: list[str]) -> list[str]:
    """Objectives written on one template that differ by a specific entity ("filtered load of Na+" / "of K+";
    "male" / "female genital system"). Returns the distinguishing word of each, or [] if they are not of this kind."""
    sets = [{t for t in tokenize(x) if t not in _ROUTINE} | set(re.findall(r"\b(?:na|k|ca|cl|mg)\+?(?=\W|$)", x.lower()))
            for x in texts]
    own = []
    for i, st in enumerate(sets):
        others = set().union(*(sets[:i] + sets[i + 1:])) if len(sets) > 1 else set()
        own.append(st - others)
    content = [u - _PROCESS for u in own]
    # same objective in other words: one side differs only by a process word and the other by at most one more
    if any(not u for u in own) or (any(not c for c in content) and max(len(c) for c in content) <= 1):
        return []
    return [sorted(c or u)[0] for u, c in zip(own, content)]


_CLINICAL = re.compile(r"\b(examination|patient|patients|clinical|case|bedside|during .* (exam|assessment))\b", re.I)


def _clinical_step(items: list[LORecord]) -> bool:
    """A basic-science objective taken up again, at least two years later, inside a clinical task
    ("rotator cuff innervation" → "identify ... during shoulder examination") is spiral teaching."""
    if len(items) != 2:
        return False
    x, y = sorted(items, key=lambda r: r.year)
    return y.year - x.year >= 2 and bool(_CLINICAL.search(y.text)) and not _CLINICAL.search(x.text)


def integrated_analysis(lo_rows: list[dict], ucep_rows: list[dict] | None = None,
                        material_rows: list[dict] | None = None, max_items: int = 12) -> dict[str, Any]:
    t0 = time.perf_counter()
    # exploratory screen: two content words ("Explain agglutinogen and agglutinin") are enough;
    # the pre-registered study keeps its own threshold (MIN_CONTENT_TOKENS)
    qc = prepare_learning_objectives(lo_rows, default_source="kullanıcı girdisi", min_tokens=2)
    uq = prepare_ucep(ucep_rows or []) if ucep_rows else {"included": [], "excluded": [], "report": {}}
    rows = qc["included"]
    out: dict[str, Any] = {
        "input_check": {"received": qc["report"]["rows_received"], "used": len(rows),
                        "excluded": [{"uid": e["uid"] or f"satır {e['row']}", "reason": REASON_TR.get(e["reason"], e["reason"]),
                                      "text": e["text"]} for e in qc["excluded"]],
                        "ucep_used": len(uq["included"])},
    }
    if len(rows) < 3:
        out["summary"] = "Analiz için en az 3 geçerli öğrenme hedefi gerekir."
        out["seconds"] = round(time.perf_counter() - t0, 3)
        return out

    n = len(rows)
    depth = max(3, min(int(0.75 * n), 400))
    cfg = _cfg(n, depth)
    T0 = _records(rows)
    a = OverlapAnalysis(T0, cfg)
    los = {lo.uid: lo for lo in T0}
    hybrid = a.hybrid(depth=depth)
    pair_ranks = {h["pair"]: h["rank"] for h in hybrid}

    # overlapping content (with method agreement)
    overlaps = []
    for h in hybrid[:max_items]:
        x, y = split_key(h["pair"])
        agree = len(h["method_ranks"])
        overlaps.append({"a": {"uid": x, "text": los[x].text, "course": los[x].course, "year": los[x].year,
                               "level": BLOOM_TR[bloom_level(los[x].text)]},
                         "b": {"uid": y, "text": los[y].text, "course": los[y].course, "year": los[y].year,
                               "level": BLOOM_TR[bloom_level(los[y].text)]},
                         "agreement": f"{agree}/3 yöntem", "strength": "güçlü" if agree == 3 and h["rank"] <= max(3, depth // 4) else "orta" if agree >= 2 else "zayıf",
                         "shared": a.evidence(h["pair"])["shared_concepts"][:4]})
    # keep only meaningful candidates (≥ 2 methods agree)
    overlaps = [o for o in overlaps if o["strength"] != "zayıf"]
    # same template, different entity (Na+ / K+): shown separately, not as overlap
    overlaps = [o for o in overlaps if not _parallel([o["a"]["text"], o["b"]["text"]])]

    # educational reading
    umap = ucep_correspondence(a, uq["included"]) if uq["included"] else []
    gen = generate_mimar_findings(a, umap, depth=max(3, depth // 2), integration_limit=5)
    findings = gen["findings"]

    # extra evidence from course material (separate channel)
    material_note = None
    if material_rows:
        mat = {}
        for m in material_rows:
            uid = str(m.get("uid") or m.get("activity") or "").strip()
            if uid in los and str(m.get("text", "")).strip():
                mat[uid] = (mat.get(uid, "") + " " + str(m["text"]).strip()).strip()
        if mat:
            ext = OverlapAnalysis(_records(rows, mat), cfg)
            gen_ext = generate_mimar_findings(ext, ucep_correspondence(ext, uq["included"]) if uq["included"] else [],
                                              depth=max(3, depth // 2), integration_limit=5)
            core_keys = {f["key"] for f in findings}
            new = [f for f in gen_ext["findings"] if f["key"] not in core_keys]
            for f in new:
                f["from_material"] = True
            findings += new
            material_note = {"objectives_with_material": len(mat), "new_candidates": len(new)}

    ucep_by = {u["code"]: u for u in uq["included"]}
    n_pairs = max(1, len(hybrid))
    cards = []
    for f in findings:
        pr = _priority(f, los, pair_ranks, n_pairs)
        st_tr, ra_tr = _statement_tr(f, los, ucep_by)
        cards.append({"category": f["category"], "statement": st_tr, "rationale": ra_tr,
                      "objectives": [{"uid": u, "text": los[u].text, "course": los[u].course, "year": los[u].year}
                                     for u in f["items"]["los"] if u in los],
                      "ucep": [{"code": c, "text": ucep_by.get(c, {}).get("text_tr", "")} for c in f["items"]["ucep"]],
                      "priority": pr, "proposal": _proposal(f, los, ucep_by), "questions": _questions(f, los),
                      "from_material": f.get("from_material", False), "_los": [u for u in f["items"]["los"] if u in los]})
    # a lecture and its own laboratory / dissection session in the same block
    # restate the same objective on purpose: reinforcement, not redundancy
    PRACTICAL = {"laboratuvar", "diseksiyon", "beceri"}
    reinforcements, parallels, kept, clinical_steps = [], [], [], []
    for c in cards:
        us = c.pop("_los") if c["category"] == "redundancy" else c.pop("_los") and []
        kinds = {los[u].discipline for u in us}
        courses = {los[u].course for u in us}
        if us and len(courses) == 1 and kinds & PRACTICAL and kinds - PRACTICAL:
            reinforcements.append({"course": next(iter(courses)), "objectives": [los[u].text for u in us][:3]})
        elif us and _clinical_step([los[u] for u in us]):
            x, y = sorted((los[u] for u in us), key=lambda r: r.year)[:2]
            clinical_steps.append({"pair": f"{x.uid} → {y.uid}", "years": [x.year, y.year],
                                   "levels": [BLOOM_TR[bloom_level(x.text)], "klinik uygulama"]})
        elif us and _parallel([los[u].text for u in us]):
            parallels.append({"objectives": [f"{los[u].text} ({los[u].course})" for u in us][:4],
                              "differ_by": _parallel([los[u].text for u in us])})
        else:
            kept.append(c)
    cards = kept
    order = {"yüksek": 0, "orta": 1, "düşük": 2}
    cards.sort(key=lambda c: (order[c["priority"]["level"]], -c["priority"]["score"]))

    # simulated impact of the proposals
    impact = None
    removals = sorted({u for c in cards if c["category"] == "redundancy" and c["priority"]["level"] != "düşük"
                       for u in c["proposal"].get("remove", [])})
    additions = [c["proposal"]["add"] for c in cards if c["category"] == "gap_ucep" and "add" in c["proposal"]]
    if removals or additions:
        T1 = [lo for lo in T0 if lo.uid not in removals]
        for i, ad in enumerate(additions, start=1):
            T1.append(LORecord(uid=f"YENİ-{i:02d}", text=ad["text"], activity=f"{ad['activity']}-new{i}",
                               course=ad["course"], year=ad["year"], ucep_links=[ad["code"]]))
        res = impact_alerts(T0, T1, uq["included"], cfg)
        cnt = Counter(al["type"] for al in res["alerts"])
        lost = [al["entity"] for al in res["alerts"] if al["type"] == "coverage_lost"]
        impact = {
            "applied": {"removed_objectives": removals, "added_objectives": [f"YENİ-{i:02d} ({ad['code']})" for i, ad in enumerate(additions, 1)]},
            "removed_links": cnt.get("removed_link", 0), "new_links": cnt.get("new_link", 0),
            "ucep_gained": [al["entity"] for al in res["alerts"] if al["type"] == "coverage_gained"],
            "ucep_lost": lost,
            "warning": (f"Dikkat: önerilen kaldırmalar {', '.join(lost)} maddesinin karşılığını ortadan kaldırıyor; "
                        "bu hedef kaldırılmadan önce içeriği başka bir hedefe taşınmalı.") if lost else None,
            "objectives_before_after": [len(T0), len(T1)],
        }

    # reliability
    a2 = OverlapAnalysis(T0, cfg)
    top = [h["pair"] for h in hybrid[:20]]
    top2 = [h["pair"] for h in a2.hybrid(depth=20)]
    stability = len(set(top) & set(top2)) / max(1, len(top))
    agree3 = sum(1 for h in hybrid[:max_items] if len(h["method_ranks"]) == 3)

    cats = Counter(c["category"] for c in cards)
    high = [c for c in cards if c["priority"]["level"] == "yüksek"]
    found = [f"{n} {label}" for n, label in ((cats.get("redundancy", 0), "olası gereksiz tekrar"),
                                              (cats.get("gap_ucep", 0), "UÇEP karşılığı eksik madde"),
                                              (cats.get("integration", 0), "bütünleştirme fırsatı")) if n]
    summary = f"{len(rows)} öğrenme hedefi incelendi. "
    summary += (("Bulunanlar: " + ", ".join(found) + "." + (f" Bunların {len(high)} tanesi yüksek öncelikli." if high else ""))
                if found else "Gereksiz tekrar ya da eksik bulunmadı.")
    n_spiral = len(gen["spiral_progressions"]) + len(clinical_steps)
    if n_spiral:
        summary += f" {n_spiral} tekrar, sonraki sınıfta daha ileri düzeyde ya da klinik bağlamda ele alındığı için sorun sayılmadı."

    out.update({
        "summary": summary,
        "overlaps": overlaps,
        "findings": cards,
        "reinforcements": reinforcements[:max_items],
        "parallel": parallels[:max_items],
        "not_problems": [{"pair": s["pair"].replace("|", " → "), "years": s["years"],
                          "levels": [BLOOM_TR[b] for b in s["bloom"]]} for s in gen["spiral_progressions"]] + clinical_steps,
        "ucep": [{"code": u["code"], "text": u["text_tr"], "status": u["status"],
                  "closest": u["candidates"][0]["lo"] if u["candidates"] else None} for u in umap],
        "material": material_note,
        "impact": impact,
        "reliability": {"method_agreement": f"İlk {min(max_items, len(hybrid))} adayın {agree3} tanesini üç yöntem birlikte buldu.",
                        "stability": f"Aynı girdiyle tekrar çalıştırıldığında ilk 20 adayın %{round(100 * stability)}'i aynı kaldı.",
                        "note": "Bunlar adaydır; karar ilgili öğretim üyeleri ve Müfredat Geliştirme ve Koordinasyon Kurulu’nundur."},
        "seconds": round(time.perf_counter() - t0, 2),
    })
    return out
