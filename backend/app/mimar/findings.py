"""AS2 candidate findings, UÇEP correspondence, matching and blinding."""
from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from typing import Any, Sequence

import numpy as np

from app.mimar.analysis import OverlapAnalysis, split_key
from app.mimar.rankers import rrf_fuse
from app.mimar.text import bloom_level, tokenize

# Clinical-task wording common to UÇEP items; it describes the expected
# competence, not the content, so it is ignored for content coverage.
UCEP_TASK_WORDS = frozenset(tokenize(
    "make preliminary diagnosis refer perform differential evaluate assess assessment management treat "
    "treatment emergency follow-up follow problem problems related indication indications musculoskeletal "
    "patient patients approach clinical basic knowledge level"))


def content_coverage(query: str, target: str) -> float:
    q = [t for t in tokenize(query) if t not in UCEP_TASK_WORDS]
    if not q:
        return 0.0
    tt = set(tokenize(target))
    return sum(1 for t in set(q) if t in tt) / len(set(q))

CATEGORIES = ("redundancy", "gap_ucep", "integration")


def finding_key(category: str, los: Sequence[str], ucep: Sequence[str] = ()) -> str:
    raw = f"{category}|{','.join(sorted(set(los)))}|{','.join(sorted(set(ucep)))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class _UF:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)

    def groups(self) -> dict[str, list[str]]:
        g: dict[str, list[str]] = defaultdict(list)
        for x in list(self.p):
            g[self.find(x)].append(x)
        return {k: sorted(v) for k, v in g.items()}


#  UÇEP correspondence

def ucep_correspondence(analysis: OverlapAnalysis, ucep: Sequence[dict[str, Any]], top_k: int = 5,
                        strong: float = 0.45, weak: float = 0.30, rrf_k: int = 60) -> list[dict[str, Any]]:
    """For every UÇEP item, retrieve candidate corresponding LOs with the same three channels fused by RRF."""
    items = [u for u in ucep if u.get("mskl_scope", True)]
    if not items:
        return []
    texts = [u.get("text_en") or u.get("text_tr") for u in items]
    mats = {name: r.query(texts) for name, r in analysis.rankers.items()}
    explicit: dict[str, list[str]] = defaultdict(list)
    for lo in analysis.los:
        for code in getattr(lo, "ucep_links", []) or []:
            explicit[code].append(lo.uid)
    out = []
    for qi, u in enumerate(items):
        lists = {}
        for name, M in mats.items():
            row = M[qi]
            order = np.argsort(-row, kind="stable")[: top_k * 3]
            lists[name] = [int(j) for j in order if row[j] > 0][: top_k * 2]
        fused = rrf_fuse(lists, k=rrf_k)
        cands = []
        for j, score, ranks in fused[:top_k]:
            cands.append({"lo": analysis.uids[j], "rrf": round(score, 6), "method_ranks": ranks,
                          "cosine": round(float(mats["embedding"][qi][j]), 4),
                          "coverage": round(content_coverage(texts[qi], analysis.los[j].text), 3)})
        best = max((c["cosine"] for c in cands), default=0.0)
        best_cov = max((c["coverage"] for c in cands), default=0.0)
        if explicit.get(u["code"]):
            status = "explicit_link"
        elif best >= strong and best_cov >= 0.5:
            status = "candidate_correspondence"
        elif best >= weak and best_cov > 0:
            status = "weak_correspondence"
        else:
            status = "no_clear_correspondence"
        out.append({"code": u["code"], "text_tr": u.get("text_tr", ""), "text_en": u.get("text_en", ""),
                    "domain": u.get("domain", ""), "status": status, "best_cosine": round(best, 4), "best_coverage": best_cov,
                    "explicit_links": explicit.get(u["code"], []), "candidates": cands})
    return out


#  MİMAR candidate findings (deterministic, template based)

def generate_mimar_findings(analysis: OverlapAnalysis, ucep_map: Sequence[dict[str, Any]],
                            depth: int = 100, integration_limit: int = 40,
                            integration_cos: tuple[float, float] = (0.15, 0.60)) -> dict[str, Any]:
    los = {lo.uid: lo for lo in analysis.los}
    findings: list[dict[str, Any]] = []
    spiral: list[dict[str, Any]] = []

    # redundancy: complete-linkage groups of top hybrid pairs.  A member
    #    joins a group only if it is linked to *every* member, which prevents
    #    chaining unrelated content into one finding; one situation = one finding.
    hybrid = analysis.hybrid(depth=depth)
    linked: set[str] = set()
    pair_info: dict[str, dict[str, Any]] = {}
    for h in hybrid:
        a, b = split_key(h["pair"])
        la, lb = los[a], los[b]
        first, second = (la, lb) if (la.year, la.uid) <= (lb.year, lb.uid) else (lb, la)
        b1, b2 = bloom_level(first.text), bloom_level(second.text)
        if second.year > first.year and b2 > b1:
            spiral.append({"pair": h["pair"], "years": [first.year, second.year], "bloom": [b1, b2],
                           "note": "Later objective at a higher cognitive level — possible spiral progression; not reported as redundancy."})
            continue
        linked.add(h["pair"])
        pair_info[h["pair"]] = h
    group_of: dict[str, int] = {}
    groups: list[list[str]] = []
    for k in sorted(pair_info, key=lambda k: pair_info[k]["rank"]):
        a, b = split_key(k)
        ga, gb = group_of.get(a), group_of.get(b)
        if ga is None and gb is None:
            group_of[a] = group_of[b] = len(groups)
            groups.append([a, b])
        elif (ga is None) != (gb is None):
            g, new_m = (ga, b) if ga is not None else (gb, a)
            if all(f"{min(new_m, m)}|{max(new_m, m)}" in linked for m in groups[g]):
                groups[g].append(new_m)
                group_of[new_m] = g
    for members in groups:
        members = sorted(members)
        pairs = [k for k in pair_info if split_key(k)[0] in members and split_key(k)[1] in members]
        courses = sorted({los[m].course for m in members})
        years = sorted({los[m].year for m in members})
        concepts: dict[str, int] = defaultdict(int)
        for k in pairs:
            for c in analysis.evidence(k)["shared_concepts"][:3]:
                concepts[c] += 1
        topic = max(concepts, key=lambda c: (concepts[c], len(c))) if concepts else "shared content"
        best_rank = min(pair_info[k]["rank"] for k in pairs)
        findings.append({
            "category": "redundancy",
            "items": {"los": members, "ucep": []},
            "statement": (f"Objectives in {len(courses)} course(s) ({', '.join(courses)}; year(s) "
                          f"{', '.join(map(str, years))}) appear to address the same content "
                          f"(“{topic}”) at a similar expected level."),
            "support": [{"lo": m, "course": los[m].course, "year": los[m].year, "text": los[m].text,
                         **({"material": los[m].context} if los[m].context else {})} for m in members],
            "rationale": ("Possible unnecessary repetition: the expected knowledge/skill level does not "
                          "appear to increase between occurrences. Experts should judge whether the "
                          "repetition reinforces learning or applies content in a new context."),
            "evidence": {"pairs": pairs, "best_hybrid_rank": best_rank,
                         "bloom_levels": {m: bloom_level(los[m].text) for m in members}},
        })

    # gaps relative to UÇEP
    for u in ucep_map:
        if u["status"] in ("weak_correspondence", "no_clear_correspondence"):
            cands = [c["lo"] for c in u["candidates"][:3]]
            weak = u["status"] == "weak_correspondence"
            findings.append({
                "category": "gap_ucep",
                "items": {"los": cands if weak else [], "ucep": [u["code"]]},
                "statement": (f"No clear corresponding objective was found in the examined records for "
                              f"UÇEP item {u['code']} (“{u['text_en'] or u['text_tr']}”)"
                              + ("; the closest objectives correspond only weakly." if weak else ".")),
                "support": [{"ucep": u["code"], "text_tr": u["text_tr"], "text_en": u["text_en"]}] +
                           [{"lo": c, "course": los[c].course, "year": los[c].year, "text": los[c].text} for c in cands],
                "rationale": ("A missing explicit correspondence in the records does not mean the topic is not "
                              "taught; experts should check whether the item is expected within the examined blocks and "
                              "whether existing objectives cover it adequately."),
                "evidence": {"best_cosine": u["best_cosine"], "status": u["status"]},
            })

    # integration opportunities: shared concept, different years & disciplines, not overlapping
    hybrid_top = {h["pair"] for h in hybrid}
    seen_concepts: set[str] = set()
    graph_scores = analysis.graph.pair_scores(analysis.cfg.per_query_k)
    ordered = sorted(graph_scores.items(), key=lambda kv: (-kv[1], analysis.uids[kv[0][0]], analysis.uids[kv[0][1]]))
    count = 0
    for (i, j), s in ordered:
        if count >= integration_limit:
            break
        a, b = analysis.uids[i], analysis.uids[j]
        la, lb = los[a], los[b]
        key = f"{a}|{b}" if a < b else f"{b}|{a}"
        if key in hybrid_top or la.year == lb.year or (la.discipline and la.discipline == lb.discipline):
            continue
        cos = analysis.emb.similarity(i, j)
        if not (integration_cos[0] <= cos <= integration_cos[1]):
            continue
        shared = [c for c in analysis.graph.shared_concepts(i, j) if c not in seen_concepts and " " in c]
        if not shared:
            continue
        concept = shared[0]
        seen_concepts.add(concept)
        early, late = (la, lb) if la.year < lb.year else (lb, la)
        findings.append({
            "category": "integration",
            "items": {"los": sorted([a, b]), "ucep": []},
            "statement": (f"“{concept}” is addressed in year {early.year} ({early.course}) and in year "
                          f"{late.year} ({late.course}) from different perspectives without a recorded link."),
            "support": [{"lo": x.uid, "course": x.course, "year": x.year, "text": x.text} for x in (early, late)],
            "rationale": ("An explicit link (e.g. a shared case or cross-reference) could strengthen "
                          "basic–clinical integration; mentioning the same topic alone is not sufficient."),
            "evidence": {"graph_score": round(s, 4), "cosine": round(cos, 4), "shared_concepts": shared[:5]},
        })
        count += 1

    # de-duplicate (§4.2): identical category + items counted once
    uniq: dict[str, dict[str, Any]] = {}
    for f in findings:
        f["key"] = finding_key(f["category"], f["items"]["los"], f["items"]["ucep"])
        uniq.setdefault(f["key"], f)
    return {"findings": list(uniq.values()), "spiral_progressions": spiral,
            "counts": {c: sum(1 for f in uniq.values() if f["category"] == c) for c in CATEGORIES}}


#  Matching, linked families, blinded pool

def _items_set(f: dict[str, Any]) -> set[str]:
    return set(f["items"].get("los", [])) | {f"U:{c}" for c in f["items"].get("ucep", [])}


def match_findings(mimar: Sequence[dict[str, Any]], expert: Sequence[dict[str, Any]],
                   suggest_threshold: float = 0.5) -> dict[str, Any]:
    """Automatic proposal: identical category and identical item set → match."""
    matches, suggestions = [], []
    used_e: set[str] = set()
    def iset(f):
        return {f"U:{c}" for c in f["items"].get("ucep", [])} if f["category"] == "gap_ucep" else _items_set(f)

    for m in mimar:
        ms = iset(m)
        best, best_j = None, 0.0
        for e in expert:
            if e["key"] in used_e or e["category"] != m["category"]:
                continue
            es = iset(e)
            j = len(ms & es) / len(ms | es) if ms | es else 0.0
            if j > best_j:
                best, best_j = e, j
        if best is not None and best_j == 1.0:
            matches.append({"mimar": m["key"], "expert": best["key"], "jaccard": 1.0, "status": "auto_matched"})
            used_e.add(best["key"])
        elif best is not None and best_j >= suggest_threshold:
            suggestions.append({"mimar": m["key"], "expert": best["key"], "jaccard": round(best_j, 3),
                                "status": "needs_confirmation"})
    return {"matches": matches, "suggestions": suggestions}


def linked_families(entries: Sequence[dict[str, Any]]) -> dict[str, str]:
    """Findings sharing an LO or UÇEP item (directly or indirectly) form a linked family — the clustering unit…"""
    uf = _UF()
    for e in entries:
        uf.find(e["code"])
        for it in _items_set(e):
            uf.union(e["code"], "ITEM:" + it)
    fam = {}
    names: dict[str, str] = {}
    for e in entries:
        r = uf.find(e["code"])
        names.setdefault(r, f"LF{len(names) + 1:04d}")
        fam[e["code"]] = names[r]
    return fam


def build_blinded_pool(reports: dict[str, Sequence[dict[str, Any]]], confirmed_matches: Sequence[dict[str, str]],
                       seed: int) -> dict[str, Any]:
    """Merge locked reports into unique entries, remove source identifiers, model names and technical scores,…"""
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for src, fs in reports.items():
        for f in fs:
            by_key[(src, f["key"])] = f
    merged: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()
    for mt in confirmed_matches:
        km, ke = ("M", mt["mimar"]), ("U", mt["expert"])
        if km in by_key and ke in by_key and km not in used and ke not in used:
            f = by_key[km]
            merged.append({"sources": ["M", "U"], "keys": {"M": mt["mimar"], "U": mt["expert"]}, "f": f})
            used |= {km, ke}
    for (src, key), f in sorted(by_key.items()):
        if (src, key) not in used:
            merged.append({"sources": [src], "keys": {src: key}, "f": f})
    rng = random.Random(seed)
    rng.shuffle(merged)
    entries, seal = [], {}
    for n, m in enumerate(merged, start=1):
        code = f"B-{n:04d}"
        f = m["f"]
        entries.append({
            "code": code, "category": f["category"],
            "items": f["items"], "statement": f["statement"],
            "support": [{k: v for k, v in s.items() if k in ("lo", "ucep", "course", "year", "text", "text_tr", "text_en")}
                        for s in f.get("support", [])],
            "rationale": f.get("rationale", ""),
        })
        seal[code] = {"sources": m["sources"], "keys": m["keys"]}
    fam = linked_families(entries)
    for e in entries:
        e["family"] = fam[e["code"]]
    return {"entries": entries, "seal": seal}


def resolve_validation(decisions: Sequence[dict[str, Any]], adjudications: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Combine two primary validators' locked decisions and any adjudication into a final record per pool code."""
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in decisions:
        by_code[d["code"]].append(d)
    adj = {a["code"]: a for a in adjudications}
    final, conflicts = {}, []
    dims = ("support", "meaningful", "category_ok")
    for code, ds in by_code.items():
        ds = sorted(ds, key=lambda d: d["validator_id"])[:2]
        if len(ds) < 2:
            final[code] = {"status": "awaiting_second_validator"}
            continue
        merged = {}
        disagree = []
        for dim in dims:
            if ds[0][dim] == ds[1][dim]:
                merged[dim] = ds[0][dim]
            elif code in adj and dim in adj[code]:
                merged[dim] = adj[code][dim]
            else:
                disagree.append(dim)
        if disagree:
            conflicts.append({"code": code, "dimensions": disagree})
            final[code] = {"status": "awaiting_adjudication", "dimensions": disagree}
            continue
        if "insufficient" in (merged["support"], merged["meaningful"]):
            verified = None
        else:
            verified = merged["support"] == "yes" and merged["meaningful"] == "yes" and merged["category_ok"] == "yes"
        final[code] = {"status": "final", **merged, "verified": verified,
                       "category_corrected": merged["category_ok"] == "no"}
    return {"final": final, "conflicts": conflicts}
