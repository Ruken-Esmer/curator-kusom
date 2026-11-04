"""
CURATOR — Curriculum Service
Business logic for curriculum tree and block queries.
"""
from __future__ import annotations

from app.graph.client import neo4j_client
from app.models.schemas import CurriculumTreeResponse
from app.data.curriculum.source import active_curriculum


async def get_curriculum_tree_data(
    institution: str = "koc_university",
    language: str = "en",
) -> CurriculumTreeResponse:
    """
    Try Neo4j first; fall back to the static curriculum dict if the
    graph is not yet seeded or unavailable.
    """
    try:
        records = await neo4j_client.get_curriculum_tree(institution)
        if records:
            years = _format_graph_records(records, language)
            return CurriculumTreeResponse(institution=institution, years=years)
    except Exception:
        pass

    # Static fallback
    years = _format_static(active_curriculum(), language)
    return CurriculumTreeResponse(institution=institution, years=years)


def _format_graph_records(records: list[dict], language: str) -> list[dict]:
    years = []
    for rec in records:
        y = rec["y"]
        blocks_raw = rec.get("blocks", [])
        blocks = []
        for b in blocks_raw:
            name = b.get("name_tr") if language == "tr" else b.get("name_en")
            blocks.append({
                "id": b["id"],
                "name": name,
                "weeks": b.get("weeks", ""),
                "departments": b.get("departments", []),
            })
        name = y.get("name_tr") if language == "tr" else y.get("name_en")
        years.append({"year": y["year_number"], "name": name, "blocks": blocks})
    return years


def _format_static(curriculum: list[dict], language: str) -> list[dict]:
    result = []
    for y in curriculum:
        blocks = []
        for b in y["blocks"]:
            blocks.append({
                "id": b["id"],
                "name": b["name_tr"] if language == "tr" else b["name_en"],
                "weeks": b.get("weeks", ""),
                "departments": b.get("departments", []),
                "topics": b.get("topics", []),
                "prerequisite_ids": b.get("prerequisite_ids", []),
            })
        result.append({
            "year": y["year"],
            "name": y["name_tr"] if language == "tr" else y["name_en"],
            "blocks": blocks,
        })
    return result
