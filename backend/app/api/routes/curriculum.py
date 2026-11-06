"""Curriculum tree endpoint."""
from fastapi import APIRouter, Query

from app.graph.client import neo4j_client
from app.models.schemas import CurriculumTreeResponse
from app.services.curriculum_service import get_curriculum_tree_data

router = APIRouter()


@router.get("/curriculum/tree", response_model=CurriculumTreeResponse,
            summary="Return the full curriculum tree for an institution")
async def curriculum_tree(
    institution: str = Query(default="koc_university"),
    language: str = Query(default="en"),
) -> CurriculumTreeResponse:
    data = await get_curriculum_tree_data(institution, language)
    return data


@router.get("/curriculum/block/{block_id}", summary="Get detailed block information")
async def block_detail(block_id: str):
    try:
        ctx = await neo4j_client.get_block_context(block_id.upper())
    except Exception:
        ctx = None
    if ctx:
        return ctx
    static = _static_block(block_id)
    return static or {"error": f"Block {block_id} not found"}


def _static_block(block_id: str) -> dict | None:
    """Block details straight from the active curriculum data (no graph needed)."""
    from app.data.curriculum.source import active_curriculum, active_source
    bid = block_id.upper().replace(" ", "")
    for y in active_curriculum():
        for b in y["blocks"]:
            if b["id"] == bid:
                prereq = list(b.get("prerequisite_ids", []))
                if not prereq and active_source() == "kusom":
                    from app.pathway.planner import default_engine
                    prereq = default_engine().blocks.get(bid, {}).get("prereq", [])
                return {"id": b["id"], "code": b.get("code", b["id"]), "year": y["year"],
                        "name_tr": b["name_tr"], "name_en": b["name_en"],
                        "name_is_descriptive": b.get("name_is_descriptive", False),
                        "weeks": b.get("weeks", ""), "departments": b.get("departments", []),
                        "prerequisites": prereq,
                        "topics": [{"title": d["title"], "kind": d.get("kind", ""), "first_date": d.get("first_date"),
                                    "fields": d.get("fields", []), "objectives": d.get("objectives", [])}
                                   for d in b.get("topic_details", [{"title": t} for t in b.get("topics", [])])],
                        "source": active_source()}
    return None


@router.get("/curriculum/prerequisites/{block_id}",
            summary="Get prerequisite chain for a block")
async def prerequisites(block_id: str):
    chain = await neo4j_client.get_prerequisites_chain(block_id.upper())
    return {"block_id": block_id, "prerequisites": chain}
