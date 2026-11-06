"""Osteoarthritis followed through the six work packages of the MİMAR application.

Only what can be computed from the data is computed here; steps that have not happened yet (expert
validation, committee decisions, visits) are described on the page and marked as examples.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from app.audit import topic_audit as ta
from app.data.kusom import curriculum as kusom
from app.mimar.analysis import AnalysisConfig, LORecord, OverlapAnalysis
from app.mimar.report import integrated_analysis

MSK_BLOCKS = ["MSKL 303", "MSKL 503", "IMED 410"]
EXPERT_PAIR = ("Approach to the patient with joint pain: Is it inflammatory?", "Differential diagnosis of arthritis")


def _rows(codes: list[str] | None) -> list[dict[str, Any]]:
    from app.api.routes.mimar import kusom_los_rows   # shared with /mimar/kusom/los
    return kusom_los_rows(codes)


def _records(rows: list[dict[str, Any]]) -> list[LORecord]:
    return [LORecord(uid=r["uid"], text=r["text"], activity=r.get("activity") or r["uid"], course=r["course"], year=r["year"])
            for r in rows]


@lru_cache(maxsize=1)
def wp1() -> dict[str, Any]:
    """The MSK blocks through the three ranking methods and their fusion."""
    rows = _rows(MSK_BLOCKS)
    text = {r["uid"]: r for r in rows}
    t = time.perf_counter()
    hybrid = OverlapAnalysis(_records(rows), AnalysisConfig()).hybrid()
    oa = []
    expert_rank = None
    for h in hybrid:
        a, b = (text[u] for u in h["pair"].split("|"))
        if {a["text"], b["text"]} == set(EXPERT_PAIR):
            expert_rank = h["rank"]
        if "steoarth" in a["text"] + b["text"]:
            oa.append({"rank": h["rank"], "a": f"{a['course']} · {a['text']}", "b": f"{b['course']} · {b['text']}",
                       "methods": sorted(h["method_ranks"])})
    report = integrated_analysis(rows)
    in_findings = any("steoarth" in str(f["objectives"]) for f in report["findings"])
    return {
        "blocks": MSK_BLOCKS, "titles": len(rows), "oa_titles": sorted({r["text"] for r in rows if "steoarth" in r["text"].lower()}),
        "hybrid_pairs": len(hybrid), "oa_pairs": oa[:5], "expert_pair": list(EXPERT_PAIR), "expert_pair_rank": expert_rank,
        "examined": int(report["summary"].split()[0]), "findings": len(report["findings"]), "oa_in_findings": in_findings, "summary": report["summary"],
        "seconds": round(time.perf_counter() - t, 1),
    }


@lru_cache(maxsize=1)
def wp4() -> dict[str, Any]:
    """The same screen over every imported block."""
    rows = _rows(None)
    t = time.perf_counter()
    report = integrated_analysis(rows)
    cats: dict[str, int] = {}
    for f in report["findings"]:
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    names = ta.topic_names()
    return {
        "titles": len(rows), "examined": int(report["summary"].split()[0]),
        "redundancy": cats.get("redundancy", 0), "integration": cats.get("integration", 0),
        "high": sum(1 for f in report["findings"] if f["priority"]["level"] == "yüksek"),
        "summary": report["summary"], "seconds": round(time.perf_counter() - t, 1),
        "diseases_with_sessions": len(names), "diseases_with_profile": sum(1 for n in names if n["code"] in ta.PROFILES),
        "years": sorted({y["year"] for y in kusom.kusom_curriculum()}),
    }


def scenario() -> dict[str, Any]:
    item = ta.find_topic("osteoartrit")
    return {"t0": ta.topic_report(item), "wp1": wp1(), "wp4": wp4()}
