"""AS6 change-impact tracking."""
from __future__ import annotations

import random
from typing import Any, Sequence

from app.mimar.analysis import AnalysisConfig, LORecord, OverlapAnalysis, pair_key, split_key
from app.mimar.findings import ucep_correspondence

COVERED = {"explicit_link", "candidate_correspondence"}


def diff_versions(t0: Sequence[LORecord], t1: Sequence[LORecord]) -> dict[str, Any]:
    a = {lo.uid: lo for lo in t0}
    b = {lo.uid: lo for lo in t1}
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    modified, relinked, moved = [], [], []
    for u in sorted(set(a) & set(b)):
        x, y = a[u], b[u]
        if x.text.strip() != y.text.strip():
            modified.append(u)
        if sorted(x.ucep_links) != sorted(y.ucep_links) or sorted(x.competencies) != sorted(y.competencies):
            relinked.append(u)
        if (x.activity, x.course, x.year) != (y.activity, y.course, y.year):
            moved.append(u)
    return {"added": added, "removed": removed, "modified": modified, "relinked": relinked, "moved": moved,
            "changed_uids": sorted(set(added) | set(removed) | set(modified) | set(relinked) | set(moved))}


def impact_alerts(t0: Sequence[LORecord], t1: Sequence[LORecord], ucep: Sequence[dict[str, Any]],
                  cfg: AnalysisConfig, depth: int | None = None) -> dict[str, Any]:
    depth = depth or cfg.list_depth
    d = diff_versions(t0, t1)
    changed = set(d["changed_uids"])
    a0, a1 = OverlapAnalysis(t0, cfg), OverlapAnalysis(t1, cfg)
    h0 = {h["pair"]: h for h in a0.hybrid(depth=depth)}
    h1 = {h["pair"]: h for h in a1.hybrid(depth=depth)}
    texts0 = {lo.uid: lo.text for lo in t0}
    texts1 = {lo.uid: lo.text for lo in t1}
    alerts: list[dict[str, Any]] = []
    rank_shift_only: list[str] = []

    def involves(k: str) -> list[str]:
        return [u for u in split_key(k) if u in changed]

    for k in sorted(set(h1) - set(h0)):
        if involves(k):
            alerts.append({"type": "new_link", "entity": k, "cause": involves(k),
                           "evidence": {"t1_rank": h1[k]["rank"], "method_ranks": h1[k]["method_ranks"],
                                        "texts": [texts1.get(u) for u in split_key(k)]}})
        else:
            rank_shift_only.append(k)
    for k in sorted(set(h0) - set(h1)):
        if involves(k):
            alerts.append({"type": "removed_link", "entity": k, "cause": involves(k),
                           "evidence": {"t0_rank": h0[k]["rank"], "texts": [texts0.get(u) for u in split_key(k)]}})
        else:
            rank_shift_only.append(k)
    for k in sorted(set(h0) & set(h1)):
        if any(u in d["modified"] for u in split_key(k)):
            alerts.append({"type": "changed_link", "entity": k, "cause": [u for u in split_key(k) if u in d["modified"]],
                           "evidence": {"t0_rank": h0[k]["rank"], "t1_rank": h1[k]["rank"]}})

    u0 = {u["code"]: u for u in ucep_correspondence(a0, ucep)}
    u1 = {u["code"]: u for u in ucep_correspondence(a1, ucep)}
    for code in sorted(set(u0) | set(u1)):
        s0, s1 = u0.get(code, {}).get("status"), u1.get(code, {}).get("status")
        e0, e1 = set(u0.get(code, {}).get("explicit_links", [])), set(u1.get(code, {}).get("explicit_links", []))
        for lo in sorted(e1 - e0):
            alerts.append({"type": "ucep_link_added", "entity": f"{code}|{lo}", "cause": [lo],
                           "evidence": {"ucep": code}})
        for lo in sorted(e0 - e1):
            alerts.append({"type": "ucep_link_removed", "entity": f"{code}|{lo}", "cause": [lo],
                           "evidence": {"ucep": code}})
        if s0 in COVERED and s1 not in COVERED:
            alerts.append({"type": "coverage_lost", "entity": code, "cause": sorted(changed & set(
                [c["lo"] for c in u0[code]["candidates"]] + list(e0))), "evidence": {"t0": s0, "t1": s1}})
        elif s0 not in COVERED and s1 in COVERED:
            alerts.append({"type": "coverage_gained", "entity": code, "cause": sorted(changed & set(
                [c["lo"] for c in u1[code]["candidates"]] + list(e1))), "evidence": {"t0": s0, "t1": s1}})
    for i, a in enumerate(alerts, start=1):
        a["id"] = f"A{i:04d}"
        a["key"] = f"{a['type']}:{a['entity']}"
    return {"diff": d, "alerts": alerts, "rank_shift_only": rank_shift_only,
            "settings": {"depth": depth, "config_hash": cfg.hash()}}


def evaluate_alerts(alerts: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]],
                    alert_decisions: dict[str, bool] | None = None) -> dict[str, Any]:
    """expected: [{type, entity}]."""
    alert_decisions = alert_decisions or {}
    exp_keys = {f"{e['type']}:{e['entity']}" for e in expected}
    a_keys = {a["key"] for a in alerts}
    rows = []
    for a in alerts:
        if a["key"] in exp_keys:
            rows.append({"id": a["id"], "key": a["key"], "verified": True, "basis": "expected"})
        else:
            rows.append({"id": a["id"], "key": a["key"], "verified": bool(alert_decisions.get(a["id"], False)),
                         "basis": "evaluator_decision" if a["id"] in alert_decisions else "unreviewed_unexpected"})
    exp_rows = [{"key": k, "reported": k in a_keys} for k in sorted(exp_keys)]
    return {"alerts": rows, "expected": exp_rows,
            "verified_alerts": sum(r["verified"] for r in rows), "total_alerts": len(rows),
            "missed_expected": sum(not r["reported"] for r in exp_rows), "total_expected": len(exp_rows)}


#  Controlled scenarios on a separate test copy (≥ 24, ≥ 8 per type)

_VERB_SWAP = {"Describe": "Explain", "Explain": "Describe", "List": "Identify", "Identify": "List",
              "Discuss": "Describe", "Define": "Describe", "Compare": "Contrast", "Interpret": "Evaluate"}


def _paraphrase(text: str) -> str:
    first, _, rest = text.partition(" ")
    return f"{_VERB_SWAP.get(first, 'Describe')} {rest}" if rest else text


def controlled_scenarios(t0: Sequence[LORecord], ucep: Sequence[dict[str, Any]], cfg: AnalysisConfig,
                         per_type: int = 8, seed: int = 20260913, depth: int | None = None) -> list[dict[str, Any]]:
    """Generate add / remove / relink scenarios with pre-registered expected effects derived only from the…"""
    depth = depth or cfg.list_depth
    rng = random.Random(seed)
    base = OverlapAnalysis(t0, cfg)
    h0 = base.hybrid(depth=depth)
    partners: dict[str, list[str]] = {}
    all_links: dict[str, list[str]] = {}
    for h in h0:
        a, b = split_key(h["pair"])
        all_links.setdefault(a, []).append(b)
        all_links.setdefault(b, []).append(a)
    for h in h0[: depth // 2]:
        a, b = split_key(h["pair"])
        partners.setdefault(a, []).append(b)
        partners.setdefault(b, []).append(a)
    los = list(t0)
    by_uid = {lo.uid: lo for lo in los}
    activities = sorted({lo.activity for lo in los})
    candidates = sorted(partners)
    rng.shuffle(candidates)
    scenarios: list[dict[str, Any]] = []

    # add: paraphrased copy of an LO into another activity → new link with source
    for n, src in enumerate(candidates[:per_type], start=1):
        lo = by_uid[src]
        other = rng.choice([a for a in activities if a != lo.activity])
        new = LORecord(uid=f"SCN-ADD-{n:02d}", text=_paraphrase(lo.text), activity=other,
                       course=f"{lo.course} (test copy)", year=lo.year, discipline=lo.discipline)
        exp = [{"type": "new_link", "entity": pair_key(new.uid, src)}]
        # the copy is expected to inherit the source's existing links (other activities only)
        exp += [{"type": "new_link", "entity": pair_key(new.uid, p)} for p in all_links.get(src, [])
                if by_uid[p].activity != other]
        scenarios.append({"id": f"S-ADD-{n:02d}", "type": "add", "t1": los + [new], "expected": exp})
    # remove: an LO with strong partners → its strongest link disappears
    for n, src in enumerate(candidates[per_type:2 * per_type], start=1):
        t1 = [lo for lo in los if lo.uid != src]
        exp = [{"type": "removed_link", "entity": pair_key(src, p)} for p in all_links.get(src, [])]
        scenarios.append({"id": f"S-REM-{n:02d}", "type": "remove", "t1": t1, "expected": exp})
    # relink: add an explicit UÇEP link to an LO
    codes = [u["code"] for u in ucep if u.get("mskl_scope", True)]
    pool = [lo.uid for lo in los]
    rng.shuffle(pool)
    for n, uid in enumerate(pool[:per_type], start=1):
        code = rng.choice(codes) if codes else "NONE"
        lo = by_uid[uid]
        if code in lo.ucep_links:
            continue
        changed = LORecord(**{**lo.__dict__, "ucep_links": sorted(lo.ucep_links + [code])})
        t1 = [changed if x.uid == uid else x for x in los]
        scenarios.append({"id": f"S-REL-{n:02d}", "type": "relink", "t1": t1,
                          "expected": [{"type": "ucep_link_added", "entity": f"{code}|{uid}"}]})
    return scenarios


def run_controlled(t0: Sequence[LORecord], ucep: Sequence[dict[str, Any]], cfg: AnalysisConfig,
                   per_type: int = 8, seed: int = 20260913) -> dict[str, Any]:
    from app.mimar.metrics import h6_alert_metrics
    out = []
    for sc in controlled_scenarios(t0, ucep, cfg, per_type, seed):
        res = impact_alerts(t0, sc["t1"], ucep, cfg)
        ev = evaluate_alerts(res["alerts"], sc["expected"])
        out.append({"id": sc["id"], "type": sc["type"], "expected": ev["expected"], "alerts": ev["alerts"],
                    "n_alerts": len(res["alerts"])})
    by_type = {}
    for t in ("add", "remove", "relink"):
        sub = [s for s in out if s["type"] == t]
        by_type[t] = h6_alert_metrics(sub, B=500) if sub else None
    return {"scenarios": out, "overall": h6_alert_metrics(out), "by_type": by_type}
