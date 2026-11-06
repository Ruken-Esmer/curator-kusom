"""
CURATOR — Ingestion Service
Builds FAISS and BM25 indexes from the curriculum data at startup.
Also seeds Neo4j if the graph is empty.
"""
from __future__ import annotations

from app.core.logging import logger
from app.data.curriculum.source import active_curriculum
from app.data.curriculum.koc_university import build_chunks
from app.graph.client import neo4j_client
from app.models.schemas import BlockNode, YearNode
from app.utils.bm25 import bm25_retriever
from app.utils.embeddings import vector_store


async def ensure_indexes_ready() -> None:
    """
    Called at application startup.
    1. Try to load existing FAISS index from disk.
    2. If not found, build from static curriculum data and save.
    3. Build BM25 in memory (fast, no persistence needed).
    4. Seed Neo4j if it has no Year nodes yet.
    """
    chunks = build_chunks(active_curriculum())

    # FAISS
    loaded = vector_store.load()
    stale = loaded and [m.get("id") for m in vector_store._metadata] != [c["id"] for c in chunks]
    if not loaded or stale:     # first start, or the curriculum data changed
        logger.info("ingestion.building_faiss")
        vector_store.build(chunks)
        vector_store.save()

    # BM25 (always rebuild in memory: fast)
    bm25_retriever.build(chunks)
    logger.info("ingestion.bm25_ready", n=len(chunks))

    # Neo4j seed
    await _seed_neo4j_if_empty()


async def _seed_neo4j_if_empty() -> None:
    """Seed graph only if Year nodes are absent."""
    try:
        healthy = await neo4j_client.is_healthy()
        if not healthy:
            logger.warning("ingestion.neo4j_unavailable_skip_seed")
            return

        # Check if already seeded
        async with neo4j_client.session() as s:
            result = await s.run("MATCH (y:Year) RETURN count(y) AS cnt")
            record = await result.single()
            count = record["cnt"] if record else 0

        if count > 0:
            logger.info("ingestion.neo4j_already_seeded", year_nodes=count)
            return

        logger.info("ingestion.seeding_neo4j")
        await _seed_graph(active_curriculum())
        logger.info("ingestion.neo4j_seeded")

    except Exception as exc:
        logger.warning("ingestion.neo4j_seed_failed", error=str(exc))


async def _seed_graph(curriculum: list[dict]) -> None:
    for year_data in curriculum:
        year_node = YearNode(
            id=f"year_{year_data['year']}",
            year_number=year_data["year"],
            name_en=year_data["name_en"],
            name_tr=year_data["name_tr"],
            description_en=year_data.get("description_en", ""),
            description_tr=year_data.get("description_tr", ""),
        )
        await neo4j_client.upsert_year(year_node)

        for block_data in year_data["blocks"]:
            block_node = BlockNode(
                id=block_data["id"],
                year=year_data["year"],
                block_number=block_data.get("block_number", 0),
                name_en=block_data["name_en"],
                name_tr=block_data["name_tr"],
                weeks=block_data.get("weeks", ""),
                departments=block_data.get("departments", []),
                topics=block_data.get("topics", []),
                prerequisite_ids=block_data.get("prerequisite_ids", []),
                competencies=block_data.get("competencies", []),
                description_en=block_data.get("description_en", ""),
                description_tr=block_data.get("description_tr", ""),
            )
            await neo4j_client.upsert_block(block_node)

            # Prerequisite edges
            for pre_id in block_data.get("prerequisite_ids", []):
                await neo4j_client.create_prerequisite(pre_id, block_data["id"])

            # Department nodes
            for dept in block_data.get("departments", []):
                dept_id = dept.lower().replace(" ", "_").replace("&", "and")
                await neo4j_client.upsert_department(dept_id, dept, block_data["id"])

            # Topic nodes
            for topic in block_data.get("topics", []):
                topic_id = f"{block_data['id']}_{topic[:20].lower().replace(' ', '_')}"
                await neo4j_client.upsert_topic(
                    topic_id, topic, "", block_data["id"],
                    department=block_data.get("departments", [""])[0]
                )
