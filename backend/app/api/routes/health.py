"""Health check."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.graph.client import neo4j_client
from app.models.schemas import HealthResponse
from app.utils.embeddings import vector_store

settings = get_settings()
router = APIRouter()


def _effective_llm() -> str:
    if settings.active_llm == "anthropic" and settings.anthropic_api_key:
        return "anthropic"
    if settings.active_llm == "openai" and settings.openai_api_key:
        return "openai"
    return "offline"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        neo4j=await neo4j_client.is_healthy(),
        vector_store=vector_store.is_ready(),
        llm=_effective_llm(),
        version="1.1.0",
    )


@router.get("/")
async def root():
    return {"name": "CURATOR API", "version": "1.1.0", "docs": "/docs", "modules": ["curator-chat", "mimar"]}
