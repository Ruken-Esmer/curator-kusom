#!/usr/bin/env python3
"""
CURATOR — RAG Evaluation Script
=================================
Runs a benchmark suite against the live pipeline and reports:
  - Query classification accuracy
  - Citation presence rate
  - Pathway detection rate
  - Average response latency

Usage:
    cd backend
    python ../scripts/evaluate_rag.py [--save-report eval_report.json]
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.logging import setup_logging, logger
from app.models.schemas import Language, QueryType
from app.rag.pipeline import run_pipeline
from app.services.ingestion import ensure_indexes_ready

#  Test suite

TEST_CASES: list[dict[str, Any]] = [
    # Factual queries
    {
        "query": "What topics are covered in the Cardiovascular System block?",
        "lang": "en",
        "expected_type": QueryType.FACTUAL,
        "expected_citations": ["Y2B1"],
        "description": "Block-level topic lookup",
    },
    {
        "query": "Which departments teach the Nervous System block?",
        "lang": "en",
        "expected_type": QueryType.FACTUAL,
        "expected_citations": ["Y3B1"],
        "description": "Department query",
    },
    {
        "query": "Y1B4 bloğunda hangi konular işleniyor?",
        "lang": "tr",
        "expected_type": QueryType.FACTUAL,
        "expected_citations": ["Y1B4"],
        "description": "Turkish factual query",
    },
    # Pathway queries
    {
        "query": "What should I study before taking the Cardiovascular System block?",
        "lang": "en",
        "expected_type": QueryType.PATHWAY,
        "expected_citations": ["Y1B3", "Y1B4"],
        "description": "Prerequisite pathway EN",
    },
    {
        "query": "Nöroloji rotasyonu için hangi blokları tamamlamam gerekiyor?",
        "lang": "tr",
        "expected_type": QueryType.PATHWAY,
        "expected_citations": ["Y3B1"],
        "description": "Prerequisite pathway TR",
    },
    {
        "query": "Give me the full learning pathway to prepare for Year 4 clinical rotations.",
        "lang": "en",
        "expected_type": QueryType.PATHWAY,
        "expected_citations": ["Y3B1", "Y3B2", "Y3B3"],
        "description": "Multi-step pathway",
    },
    # Relational queries
    {
        "query": "How does biochemistry in Year 1 connect to clinical endocrinology?",
        "lang": "en",
        "expected_type": QueryType.RELATIONAL,
        "expected_citations": ["Y1B4", "Y3B3"],
        "description": "Cross-year relational query",
    },
    {
        "query": "How does anatomy teaching build across the 6 years?",
        "lang": "en",
        "expected_type": QueryType.RELATIONAL,
        "expected_citations": ["Y1B3"],
        "description": "Longitudinal relational query",
    },
    # Advisory queries
    {
        "query": "I'm struggling with diabetes in Year 3. What should I review?",
        "lang": "en",
        "expected_type": QueryType.ADVISORY,
        "expected_citations": ["Y3B3"],
        "description": "Student advisory EN",
    },
    {
        "query": "4. yıldan önce hangi temel biyokimya konularını gözden geçirmeliyim?",
        "lang": "tr",
        "expected_type": QueryType.ADVISORY,
        "expected_citations": ["Y1B4"],
        "description": "Student advisory TR",
    },
]


#  Evaluation runner

async def run_eval(save_path: Path | None = None) -> None:
    setup_logging(debug=False)
    logger.info("eval.start", n_cases=len(TEST_CASES))

    await ensure_indexes_ready()

    results = []
    passed = 0

    for i, tc in enumerate(TEST_CASES, 1):
        lang = Language.TR if tc["lang"] == "tr" else Language.EN
        t0 = time.monotonic()
        response = await run_pipeline(tc["query"], language=lang)
        latency = (time.monotonic() - t0) * 1000

        # Scoring
        type_match = response.query_type == tc["expected_type"]
        cited_ids = {c.block_id for c in response.citations}
        expected = set(tc.get("expected_citations", []))
        citation_match = bool(expected & cited_ids)  # at least one expected cited
        has_answer = len(response.answer) > 50

        ok = type_match and citation_match and has_answer
        if ok:
            passed += 1

        result = {
            "case": i,
            "description": tc["description"],
            "query": tc["query"][:80],
            "language": tc["lang"],
            "expected_type": tc["expected_type"].value,
            "actual_type": response.query_type.value,
            "type_match": type_match,
            "expected_citations": list(expected),
            "actual_citations": list(cited_ids),
            "citation_match": citation_match,
            "has_answer": has_answer,
            "answer_len": len(response.answer),
            "latency_ms": round(latency),
            "passed": ok,
        }
        results.append(result)

        status = "✓ PASS" if ok else "✗ FAIL"
        print(
            f"  [{i:02d}] {status}  {tc['description'][:45]:<45}  "
            f"type={'✓' if type_match else '✗'}  "
            f"cite={'✓' if citation_match else '✗'}  "
            f"{round(latency)}ms"
        )

    # Summary
    total = len(TEST_CASES)
    acc = passed / total * 100
    avg_latency = sum(r["latency_ms"] for r in results) / total

    print(f"\n{'─'*70}")
    print(f"  Results:  {passed}/{total} passed  ({acc:.1f}%)")
    print(f"  Avg latency: {avg_latency:.0f}ms")
    print(f"  Type accuracy:    {sum(r['type_match'] for r in results)}/{total}")
    print(f"  Citation accuracy: {sum(r['citation_match'] for r in results)}/{total}")

    if save_path:
        report = {
            "passed": passed,
            "total": total,
            "accuracy_pct": round(acc, 1),
            "avg_latency_ms": round(avg_latency),
            "cases": results,
        }
        save_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n  Report saved → {save_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CURATOR RAG evaluation")
    parser.add_argument("--save-report", type=Path, default=None)
    args = parser.parse_args()

    asyncio.run(run_eval(args.save_report))
