"""Graph visualisation endpoint."""
from fastapi import APIRouter, Query

from app.graph.client import neo4j_client
from app.models.schemas import GraphQueryResponse

router = APIRouter()


@router.get("/graph/subgraph/{node_id}", response_model=GraphQueryResponse,
            summary="Return subgraph centred on a node for visualisation")
async def subgraph(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=4),
) -> GraphQueryResponse:
    data = await neo4j_client.get_subgraph(node_id, depth)
    return GraphQueryResponse(
        nodes=data.get("nodes", []),
        edges=data.get("edges", []),
    )
