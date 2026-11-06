"""Topic audit for accreditation reviewers: where a disease is taught, its objectives,
recurring sessions and the UÇEP-2020 competencies it should cover."""
from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from app.data.kusom import curriculum as kusom
from app.data.ucep.ucep_list import load as load_ucep

# Topic profiles.  "direct" finds sessions about the disease itself; "related"
# finds supporting sessions by the role they play.  Patterns are written by
# hand and shown to the reviewer, so every match can be checked.
PROFILES: dict[str, dict[str, Any]] = {
    "UCEP2020-H237": {
        "names": ["osteoartrit", "osteoarthritis", "osteoartroz", "osteoarthrosis", "gonartroz", "koksartroz",
                  "dejeneratif eklem"],
        "direct": [r"osteoarthrit", r"osteoarthros", r"gonarthros", r"coxarthros"],
        "related": {
            "temel bilim": [r"histology of cartilage", r"cartilage tissue", r"bones and joints of the lower limb",
                            r"lower limb bones"],
            "tanı": [r"approach to the patient with joint pain", r"degenerative .*joint", r"non-neoplastic bone and joint",
                     r"differential diagnosis of arthritis", r"examination of the (knee|hip)",
                     r"physical examination skills: (knee|hip)", r"joint aspiration"],
            "tedavi": [r"nsaids", r"prescription for analgesics", r"prescribe exercise"],
        },
    },
}

# What each UÇEP learning level asks of a graduate, and the words that show it in a session or objective.
LEVELS = {
    "ÖnT": ("Ön tanı koyup sevk edebilme", r"diagnos|approach to|examination|differential|radiolog|patholog|aspiration"),
    "T": ("Tanı koyabilme, tedavi hakkında bilgi sahibi olma", r"diagnos|approach to|examination|differential|radiolog|patholog|aspiration"),
    "TT": ("Tanı koyabilme ve tedavi edebilme", None),   # split into the two rows below
    "A": ("Acil durumu tanıyıp ilk tedavisini yapabilme", r"emergenc|acute|urgent"),
    "K": ("Korunma önlemlerini uygulayabilme", r"prevent|risk factor|protect|weight|obes"),
    "İ": ("Birinci basamakta uzun süreli izlem", r"follow.?up|monitor|long.?term|rehabilit|chronic care"),
}
TT_ROWS = [("TT-tanı", "Tanı koyabilme", LEVELS["T"][1]),
           ("TT-tedavi", "Tedavi edebilme", r"management|treatment|therap|nsaid|analges|prescri|arthroplast|joint failure|surger")]
# a match only through a general session (e.g. exercise prescription) supports, but does not prove, the competency
INDIRECT = {"K": r"exercise"}

PHASE_TR = {"temel": "temel bilim", "hastalık": "hastalık düzeyi", "klinik": "klinik düzey"}


def _block_names() -> dict[str, str]:
    return {b["code"]: b["name_tr"] for y in kusom.kusom_curriculum() for b in y["blocks"]}


# everyday Turkish names that differ from the UÇEP wording
ALIASES = {"diyabet": "diabetes mellitus", "şeker hastalığı": "diabetes mellitus", "kalp krizi": "akut koroner",
           "miyokard enfarktüsü": "akut koroner", "felç": "inme", "verem": "tüberküloz", "gut": "gut hastalığı"}


def find_topic(text: str) -> dict[str, Any] | None:
    """The UÇEP core disease a question is about (longest name wins: 'osteoartrit' before 'artrit')."""
    low = text.replace("İ", "i").replace("I", "ı").lower()
    for k, v in ALIASES.items():
        if re.search(rf"(?<![a-zçğıöşü]){k}(?![a-zçğıöşü])", low):
            low += " " + v
    best = None
    for it in load_ucep()["items"]:
        names = [it["text_tr"].lower(), it["text_en"].lower()] + PROFILES.get(it["code"], {}).get("names", [])
        names += [n.split(" ve ")[0] for n in names] + [n.split(" and ")[0] for n in names]
        for n in names:
            n = n.split(" (")[0].strip()
            if len(n) >= 4 and re.search(rf"(?<![a-zçğıöşü]){re.escape(n)}", low):
                if best is None or len(n) > best[0]:
                    best = (len(n), it)
    return best[1] if best else None


def _profile(item: dict[str, Any]) -> dict[str, Any]:
    if item["code"] in PROFILES:
        return PROFILES[item["code"]]
    stem = re.escape(item["text_en"].split(" (")[0].split(" and ")[0].lower())
    return {"direct": [stem], "related": {}}


def sessions(item: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    prof, names = _profile(item), _block_names()
    direct, related = [], []
    for t in kusom.load()["topics"]:
        text = t["title"] + " " + " ".join(t["objectives"])
        row = {"block": t["block"], "block_name": names.get(t["block"], t["block"]), "year": t["year"],
               "phase": kusom.phase_of(t["year"]), "title": t["title"], "kind": t["kind"], "date": t["first_date"],
               "fields": [f.title() for f in t["fields"][:2]], "objectives": t["objectives"]}
        if any(re.search(p, text, re.I) for p in prof["direct"]):
            direct.append({**row, "role": "doğrudan"})
            continue
        for role, pats in prof["related"].items():
            if any(re.search(p, t["title"], re.I) for p in pats):
                related.append({**row, "role": role})
                break
    key = lambda r: (r["year"], r["date"] or "", r["title"])
    return {"direct": sorted(direct, key=key), "related": sorted(related, key=key)}


def where_taught(item: dict[str, Any]) -> dict[str, Any]:
    s = sessions(item)
    years = sorted({r["year"] for r in s["direct"]})
    return {"topic": item, "direct": s["direct"], "related": s["related"], "years": years,
            "blocks": sorted({(r["year"], r["block"], r["block_name"]) for r in s["direct"]})}


def objectives(item: dict[str, Any]) -> dict[str, Any]:
    s = sessions(item)
    rows = [{"objective": o, **{k: r[k] for k in ("block", "block_name", "year", "title")}}
            for r in s["direct"] + s["related"] for o in r["objectives"]]
    lo_blocks = sorted({t["block"] for t in kusom.load()["topics"] if t["objectives"]})
    no_lo = sorted({r["block"] for r in s["direct"] if not r["objectives"]})
    return {"topic": item, "objectives": rows, "blocks_with_objective_docs": lo_blocks,
            "teaching_blocks_without_objectives": no_lo, "sessions": s["direct"]}


REASONING = r"approach to|differential diagnosis"


def _relation(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str]:
    rank = {"temel": 0, "hastalık": 1, "klinik": 2}
    if a["block"] != b["block"] and re.search(REASONING, a["title"], re.I) and re.search(REASONING, b["title"], re.I):
        return "olası tekrar", (f"İki oturum da ayırıcı tanıyı konu alıyor. {b['year']}. sınıftaki oturumun "
                                f"{a['year']}. sınıftakine ne kadar yeni içerik eklediğine bakılmalı.")
    if a["block"] == b["block"]:
        if a["kind"] != b["kind"]:
            return "pekiştirme", f"Aynı blokta önce {a['kind']}, sonra {b['kind']} olarak işleniyor. Bilinçli bir pekiştirme olabilir."
        return "olası tekrar", "Aynı blokta aynı türden iki oturum var. İçerikleri karşılaştırılmalı."
    if rank[b["phase"]] > rank[a["phase"]]:
        return "derinleşme", f"{a['year']}. sınıfta {PHASE_TR[a['phase']]}, {b['year']}. sınıfta {PHASE_TR[b['phase']]}. Beklenen sarmal yapıya uygun."
    if a["year"] == b["year"] and a["phase"] == "klinik":
        return "olası tekrar", "Aynı yılın iki stajında geçiyor ve öğrenci iki stajı da alıyor."
    return "olası tekrar", "Aynı düzeyde iki ayrı blokta geçiyor. İçerikleri karşılaştırılmalı."


def repetitions(item: dict[str, Any]) -> dict[str, Any]:
    s = sessions(item)
    pairs = []
    for a, b in combinations(s["direct"], 2):
        pairs.append((a, b))
    # two clinical-reasoning sessions on the same question in different blocks
    reasoning = [r for r in s["related"] if r["role"] == "tanı" and re.search(REASONING, r["title"], re.I)]
    for a, b in combinations(reasoning, 2):
        if a["block"] != b["block"]:
            pairs.append((a, b))
    out = []
    for a, b in pairs:
        a, b = sorted((a, b), key=lambda r: (r["year"], r["date"] or ""))
        rel, why = _relation(a, b)
        shared = [o for o in a["objectives"] if o in b["objectives"]]
        out.append({"early": a, "late": b, "relation": rel, "why": why, "shared_objectives": shared})
    return {"topic": item, "pairs": out, "objective_level_possible": any(r["objectives"] for r in s["direct"])}


def ucep_alignment(item: dict[str, Any]) -> dict[str, Any]:
    s = sessions(item)
    pool = [r for r in s["direct"] + s["related"] if r["phase"] != "temel"]
    rows = []
    levels = []
    for lv in item["levels"]:
        if lv == "TT":
            levels += [(code, label, rx, None) for code, label, rx in TT_ROWS]
        else:
            levels.append((lv, LEVELS[lv][0], LEVELS[lv][1], INDIRECT.get(lv)))
    for code, label, rx, indirect in levels:
        text = lambda r: r["title"] + " " + " ".join(r["objectives"])
        hits = [r for r in pool if re.search(rx, text(r), re.I)]
        weak = [r for r in pool if indirect and r not in hits and re.search(indirect, text(r), re.I)]
        in_lo = any(re.search(rx, o, re.I) for r in hits for o in r["objectives"])
        status = ("hedefte var" if in_lo else "ders başlığında var" if hits else
                  "dolaylı" if weak else "karşılığı bulunamadı")
        rows.append({"level": code, "expected": label, "status": status,
                     "sessions": [f"{r['block']} ({r['year']}. sınıf): {r['title']}" for r in (hits or weak)][:4]})
    return {"topic": item, "rows": rows,
            "missing": [r for r in rows if r["status"] in ("karşılığı bulunamadı", "dolaylı")]}


# Chat answers (Turkish markdown)

def _d(iso: str | None) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else ""


def _years(ys: list[int]) -> str:
    t = [f"{y}." for y in ys]
    return (", ".join(t[:-1]) + " ve " + t[-1] if len(t) > 1 else t[0]) + " sınıfta"


def answer_where(item: dict[str, Any]) -> str:
    w = where_taught(item)
    name = item["text_tr"]
    if not w["direct"]:
        return f"2025–2026 ders programlarında {name.lower()} başlıklı bir oturum bulunamadı."
    lines = [f"{name}, 2025–2026 programında {_years(w['years'])} ayrı bir oturum olarak işleniyor.", "",
             "| Sınıf | Blok / staj | Oturum | Tür | Tarih | Anabilim dalı |", "|---|---|---|---|---|---|"]
    for r in w["direct"]:
        lines.append(f"| {r['year']} | {r['block']} {r['block_name']} | {r['title']} | {r['kind']} | {_d(r['date'])} | {', '.join(r['fields'])} |")
    if w["related"]:
        lines += ["", f"Konuya doğrudan bağlı başka oturumlar da var. Bunlar başlıklarına göre seçildi; "
                      f"ilgili anabilim dallarıyla teyit edilmesi gerekir.", "",
                  "| Sınıf | Blok / staj | Oturum | Konuyla ilişkisi |", "|---|---|---|---|"]
        for r in w["related"]:
            lines.append(f"| {r['year']} | {r['block']} | {r['title']} | {r['role']} |")
    lines += ["", "Kaynak: KUSOM 2025–2026 ders programları, 2. ile 5. sınıflar. 1. ve 6. sınıf programları henüz eklenmedi."]
    return "\n".join(lines)


def answer_objectives(item: dict[str, Any]) -> str:
    o = objectives(item)
    name = item["text_tr"]
    if o["objectives"]:
        lines = [f"{name} ile ilgili yazılı öğrenim hedefleri:", "",
                 "| Sınıf | Blok | Oturum | Öğrenim hedefi |", "|---|---|---|---|"]
        lines += [f"| {r['year']} | {r['block']} | {r['title']} | {r['objective']} |" for r in o["objectives"]]
        return "\n".join(lines)
    blocks = " ve ".join(o["teaching_blocks_without_objectives"])
    lines = [f"Elimizdeki öğrenim hedefi belgelerinde {name.lower()} ile ilgili yazılı bir hedef yok.", "",
             f"Hedef belgeleri şu ana kadar yalnızca {', '.join(o['blocks_with_objective_docs'])} blokları için iletildi. "
             f"{name} {blocks} bloklarında işleniyor; bu blokların hedef belgeleri henüz elimizde değil.", "",
             "Hedefler gelene kadar konunun işlendiği oturumlar şunlar:", "",
             "| Sınıf | Blok | Oturum başlığı | Tür |", "|---|---|---|---|"]
    lines += [f"| {r['year']} | {r['block']} | {r['title']} | {r['kind']} |" for r in o["sessions"]]
    return "\n".join(lines)


def answer_repetitions(item: dict[str, Any]) -> str:
    r = repetitions(item)
    name = item["text_tr"]
    if not r["pairs"]:
        return f"{name} için birden fazla oturumda geçen bir içerik bulunamadı."
    n = {k: sum(1 for p in r["pairs"] if p["relation"] == k) for k in ("olası tekrar", "pekiştirme", "derinleşme")}
    lead = ("Yazılı hedef olmadığı için karşılaştırmayı hedefler yerine oturumlar üzerinden yaptık. "
            if not r["objective_level_possible"] else "")
    lead += (f"{n['olası tekrar']} olası tekrar, {n['pekiştirme']} pekiştirme ve {n['derinleşme']} derinleşme görünüyor. "
             "Derinleşmeler sarmal programın beklenen sonucu; asıl bakılması gereken olası tekrarlar.")
    lines = [lead, "",
             "| Önce | Oturum | Sonra | Oturum | Değerlendirme |", "|---|---|---|---|---|"]
    for p in r["pairs"]:
        a, b = p["early"], p["late"]
        lines.append(f"| {a['year']}. sınıf, {a['block']} | {a['title']} ({a['kind']}) | {b['year']}. sınıf, {b['block']} | "
                     f"{b['title']} ({b['kind']}) | **{p['relation']}**. {p['why']} |")
    lines += ["", "Olası tekrar ve pekiştirmelerin ders içerikleri üzerinden anabilim dallarıyla birlikte gözden geçirilmesi önerilir."]
    return "\n".join(lines)


def answer_ucep(item: dict[str, Any]) -> str:
    u = ucep_alignment(item)
    name = item["text_tr"]
    no_lo = all(r["status"] != "hedefte var" for r in u["rows"])
    miss = [r["expected"].lower() for r in u["missing"]]
    if no_lo:
        lead = (f"UÇEP-2020 {name.lower()} için {'-'.join(item['levels'])} düzeyini bekliyor (madde {item['no']}). "
                "Konunun işlendiği bloklarda yazılı hedef olmadığı için bu beklentilerin hiçbiri hedeflerde karşılanmış görünmüyor. "
                + (f"Ders başlıklarına bakıldığında ise {' ve '.join(miss)} eksik ya da yalnızca dolaylı olarak var."
                   if miss else "Ders başlıklarında ise hepsinin karşılığı var."))
    else:
        lead = (f"UÇEP-2020 {name.lower()} için {'-'.join(item['levels'])} düzeyini bekliyor. "
                + (f"Müfredatta {' ve '.join(miss)} için karşılık bulunamadı." if miss else "Hepsinin müfredatta karşılığı var."))
    lines = [lead, "",
             "| UÇEP düzeyi | Beklenen | Müfredatta | Nerede |", "|---|---|---|---|"]
    for r in u["rows"]:
        lines.append(f"| {r['level']} | {r['expected']} | **{r['status']}** | {'; '.join(r['sessions'])} |")
    lines += ["", "Not: Eşleştirme oturum başlıklarına dayanıyor. Bir başlığın bulunması konunun işlendiğini gösterir, "
                  "hedefin UÇEP düzeyinde yazıldığını göstermez. UÇEP'in semptom ve temel hekimlik uygulamaları listeleri "
                  "bu karşılaştırmaya henüz dahil değil."]
    return "\n".join(lines)


QUESTION_PATTERNS = [
    ("ucep", r"uçep|ucep|ulusal çekirdek"),
    ("repetition", r"tekrar"),
    ("objectives", r"(öğrenme|öğrenim) hedef|hedefleri"),
    ("where", r"hangi (sınıf|blok|staj|yıl|dönem)|nerede|öğretiliyor|işleniyor"),
]


def chat_answer(query: str, history_texts: list[str]) -> str | None:
    """Answer an accreditation question about a UÇEP disease; the topic may come from an earlier question."""
    low = query.lower()
    kind = next((k for k, rx in QUESTION_PATTERNS if re.search(rx, low)), None)
    if not kind:
        return None
    item = find_topic(query)
    if item is None:
        for h in reversed(history_texts):
            item = find_topic(h)
            if item:
                break
    if item is None:
        return None
    return {"where": answer_where, "objectives": answer_objectives, "repetition": answer_repetitions,
            "ucep": answer_ucep}[kind](item)


def _session(r: dict[str, Any]) -> dict[str, Any]:
    return {k: r[k] for k in ("year", "block", "block_name", "title", "kind", "date", "fields", "role")}


def topic_report(item: dict[str, Any]) -> dict[str, Any]:
    """The four accreditation questions about one topic, answered together for the report page."""
    w, o, r, u = where_taught(item), objectives(item), repetitions(item), ucep_alignment(item)
    n = {k: sum(1 for p in r["pairs"] if p["relation"] == k) for k in ("olası tekrar", "pekiştirme", "derinleşme")}
    unmet = [x for x in u["rows"] if x["status"] == "karşılığı bulunamadı"]
    indirect = [x for x in u["rows"] if x["status"] == "dolaylı"]
    return {
        "topic": {"code": item["code"], "no": item["no"], "name": item["text_tr"], "name_en": item["text_en"],
                  "curated": item["code"] in PROFILES,
                  "levels": item["levels"]},
        "summary": {
            "where": (_years(w["years"]) + " işleniyor") if w["years"] else "Ayrı bir oturum bulunamadı",
            "objectives": f"{len(o['objectives'])} yazılı hedef" if o["objectives"] else "Yazılı hedef yok",
            "repetitions": (f"{n['olası tekrar']} olası tekrar" if r["pairs"] else "Tekrar bulunamadı"),
            "ucep": (f"{len(unmet)} beklenti karşılanmıyor" if unmet else
                     f"{len(indirect)} beklenti yalnız dolaylı" if indirect else "Beklentilerin karşılığı var"),
        },
        "where": {"years": w["years"], "direct": [_session(x) for x in w["direct"]],
                  "related": [_session(x) for x in w["related"]]},
        "objectives": {"items": o["objectives"], "docs_for": o["blocks_with_objective_docs"],
                       "missing_docs": o["teaching_blocks_without_objectives"],
                       "sessions": [_session(x) for x in o["sessions"]]},
        "repetitions": {"by_objective": r["objective_level_possible"], "counts": n,
                        "pairs": [{"early": _session(p["early"]), "late": _session(p["late"]), "relation": p["relation"],
                                   "why": p["why"], "shared_objectives": p["shared_objectives"]} for p in r["pairs"]]},
        "ucep": {"rows": u["rows"], "in_objectives": any(x["status"] == "hedefte var" for x in u["rows"])},
        "source": "KUSOM 2025–2026 ders programları, 2.–5. sınıf",
    }


def topic_names() -> list[dict[str, Any]]:
    """Core diseases that have at least one session of their own, for the topic picker."""
    out = []
    for it in load_ucep()["items"]:
        if sessions(it)["direct"]:
            out.append({"code": it["code"], "name": it["text_tr"], "levels": it["levels"]})
    return out
