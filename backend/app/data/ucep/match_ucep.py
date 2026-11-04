"""Where is each UÇEP-2020 core disease taught in the KUSOM curriculum?"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

from app.mimar.text import tokenize

# words that do not identify a disease on their own
_WEAK = frozenset(tokenize(
    "disease diseases disorder disorders syndrome syndromes acute chronic common other related tumor tumors "
    "cancer infection infections problems injury injuries congenital primary secondary newborn neonatal child "
    "children childhood the of and in with type types including contact physical chemical system tract "
    "complications its due high risk"))
_KEEP_TOGETHER = ("head and neck", "fluid and electrolyte", "skin and soft tissue", "alcohol and substance",
                  "inguinal and abdominal", "vitamin b12 and folate", "sepsis and meningitis")


def alternatives(gloss: str) -> list[str]:
    g = gloss.lower()
    for k in _KEEP_TOGETHER:
        g = g.replace(k, k.replace(" and ", "_and_"))
    parts = re.split(r"\s*(?:\(|\)|:|,| and | or |/)\s*", g)
    return [p.replace("_and_", " and ").strip() for p in parts if p and p.strip()]


def _key(phrase: str) -> list[str]:
    """Distinctive words of a phrase."""
    allt = tokenize(phrase)
    strong = [t for t in allt if t not in _WEAK]
    if len(strong) == 1 and len(allt) > 1:
        return allt
    return strong or allt


def coverage(curriculum: list[dict[str, Any]], items: list[dict[str, Any]], phase_of=None) -> dict[str, Any]:
    topics = []
    for y in curriculum:
        for b in y["blocks"]:
            for d in b.get("topic_details") or [{"title": t} for t in b.get("topics", [])]:
                topics.append({"block": b["id"], "code": b.get("code", b["id"]), "year": y["year"], "title": d["title"],
                               "tt": set(tokenize(d["title"])),
                               "obj": [(o, set(tokenize(o))) for o in d.get("objectives", [])]})
    df = Counter(t for tp in topics for t in tp["tt"] | set().union(*[s for _, s in tp["obj"]] or [set()]))
    n = len(topics)

    out = []
    for it in items:
        alts = [a for a in alternatives(it["text_en"]) if _key(a)]
        hits, partial = [], []
        for tp in topics:
            for a in alts:
                k = set(_key(a))
                if k <= tp["tt"]:
                    hits.append({"where": "ders başlığı", "topic": tp["title"], "block": tp["code"], "year": tp["year"], "via": a})
                    break
                o = next((o for o, s in tp["obj"] if k <= s), None)
                if o:
                    hits.append({"where": "öğrenim hedefi", "topic": tp["title"], "objective": o, "block": tp["code"],
                                 "year": tp["year"], "via": a})
                    break
            else:
                # most of one alternative's distinctive words, including its head noun
                for a in alts:
                    k = _key(a)
                    w = {t: math.log((n + 1) / (df.get(t, 0) + 1)) for t in k}
                    tot = sum(w.values()) or 1
                    toks = tp["tt"] | set().union(*[s for _, s in tp["obj"]] or [set()])
                    got = [t for t in k if t in toks]
                    sc = sum(w[t] for t in got) / tot
                    rare = min(k, key=lambda t: df.get(t, 0) or 10 ** 6)
                    rare_in_title = 1 <= df.get(rare, 0) <= 5 and rare in tp["tt"]
                    if len(k) >= 2 and got and ((sc >= 0.6 and len(got) >= 2) or sc >= 0.75 or rare_in_title):
                        partial.append({"topic": tp["title"], "block": tp["code"], "year": tp["year"],
                                        "via": a, "score": round(sc, 2)})
                        break
        partial.sort(key=lambda p: -p["score"])
        hits.sort(key=lambda h: (h["where"] != "ders başlığı", h["year"]))
        years = sorted({h["year"] for h in hits})
        status = "doğrudan" if any(h["where"] == "ders başlığı" for h in hits) else \
                 "öğrenim hedefinde" if hits else "kısmi" if partial else "bulunamadı"
        out.append({"code": it["code"], "no": it.get("no"), "text_tr": it["text_tr"], "text_en": it["text_en"],
                    "levels": it.get("levels", []), "system": it.get("system", ""), "status": status,
                    "years": years, "blocks": sorted({h["block"] for h in hits}),
                    "phases": sorted({phase_of(y) for y in years}) if phase_of else [],
                    "hits": hits[:8], "partial": partial[:5]})
    st = Counter(r["status"] for r in out)
    by_sys: dict[str, Counter] = defaultdict(Counter)
    for r in out:
        by_sys[r["system"]][r["status"]] += 1
    return {"summary": dict(st), "by_system": {k: dict(v) for k, v in sorted(by_sys.items())}, "items": out,
            "topics_searched": n}
