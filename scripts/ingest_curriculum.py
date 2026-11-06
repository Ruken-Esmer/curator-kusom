#!/usr/bin/env python3
"""
CURATOR — Curriculum Ingestion Script
======================================
Run this once (or whenever the curriculum data changes) to:
  1. Build and save the FAISS vector index
  2. Build the BM25 corpus
  3. Seed the Neo4j knowledge graph with Year / Block / Topic / Department nodes
  4. Optionally ingest PDFs from a directory

Usage:
    cd backend
    python ../scripts/ingest_curriculum.py [--pdf-dir /path/to/syllabi] [--reset]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure backend/app is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import get_settings
from app.core.logging import logger, setup_logging
from app.data.curriculum.koc_university import KUC_CURRICULUM, build_chunks
from app.graph.client import neo4j_client
from app.models.schemas import BlockNode, YearNode
from app.utils.bm25 import bm25_retriever
from app.utils.embeddings import vector_store

settings = get_settings()


#  Neo4j seeding

async def seed_neo4j(curriculum: list[dict], reset: bool = False) -> None:
    await neo4j_client.connect()
    await neo4j_client.create_constraints()

    if reset:
        logger.info("neo4j.clearing_all_nodes")
        async with neo4j_client.session() as s:
            await s.run("MATCH (n) DETACH DELETE n")

    total_blocks = 0
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
        logger.info("neo4j.year_upserted", year=year_data["year"])

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

            # Prerequisite relationships
            for pre_id in block_data.get("prerequisite_ids", []):
                await neo4j_client.create_prerequisite(pre_id, block_data["id"])

            # Department nodes
            for dept in block_data.get("departments", []):
                dept_id = dept.lower().replace(" ", "_").replace("&", "and").replace(",", "")
                await neo4j_client.upsert_department(dept_id, dept, block_data["id"])

            # Topic nodes
            for topic in block_data.get("topics", []):
                topic_id = f"{block_data['id']}_{topic[:25].lower().replace(' ', '_')}"
                await neo4j_client.upsert_topic(
                    topic_id, topic, "", block_data["id"],
                    department=block_data.get("departments", [""])[0],
                )

            total_blocks += 1
            logger.info("neo4j.block_upserted", block_id=block_data["id"])

    logger.info("neo4j.seed_complete", years=len(curriculum), blocks=total_blocks)
    await neo4j_client.close()


#  PDF ingestion (WP1 pipeline hook)

def ingest_pdfs(pdf_dir: Path) -> list[dict]:
    """
    Extract text from PDF syllabi and convert them into chunks.
    Requires: PyMuPDF  (pip install PyMuPDF)
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("pdf_ingestion.pymupdf_not_installed")
        return []

    chunks = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        doc = fitz.open(str(pdf_path))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()

        # Simple chunking: split on double newlines
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        stem = pdf_path.stem  # use filename as block_id hint
        for i, para in enumerate(paragraphs):
            chunks.append({
                "id": f"pdf_{stem}_{i}",
                "content": para,
                "source": stem,
                "source_type": "pdf",
                "metadata": {"file": pdf_path.name, "paragraph": i},
            })
        logger.info("pdf.ingested", file=pdf_path.name, chunks=len(paragraphs))

    return chunks


#  FAISS + BM25 build

def build_indexes(extra_chunks: list[dict] | None = None) -> None:
    logger.info("indexes.building")
    chunks = build_chunks(KUC_CURRICULUM)
    if extra_chunks:
        chunks.extend(extra_chunks)
        logger.info("indexes.extra_chunks_added", n=len(extra_chunks))

    # FAISS
    vector_store.build(chunks)
    vector_store.save()
    logger.info("faiss.saved", path=settings.faiss_index_path)

    # BM25 (no persistence: always rebuilds in memory)
    bm25_retriever.build(chunks)
    logger.info("bm25.built", n=len(chunks))

    logger.info("indexes.done", total_chunks=len(chunks))


#  Entry point

async def main(pdf_dir: Path | None, reset: bool) -> None:
    setup_logging(debug=True)
    logger.info("ingest.start",
                neo4j_uri=settings.neo4j_uri,
                vector_store=settings.vector_store)

    extra_chunks: list[dict] = []
    if pdf_dir and pdf_dir.is_dir():
        extra_chunks = ingest_pdfs(pdf_dir)
        logger.info("pdf.total_chunks", n=len(extra_chunks))

    # 1. Build vector/keyword indexes
    build_indexes(extra_chunks)

    # 2. Seed Neo4j
    try:
        await seed_neo4j(KUC_CURRICULUM, reset=reset)
    except Exception as exc:
        logger.warning("neo4j.seed_failed_continuing", error=str(exc))

    logger.info("ingest.complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CURATOR ingestion pipeline")
    parser.add_argument("--pdf-dir", type=Path, default=None,
                        help="Directory containing PDF syllabi to ingest")
    parser.add_argument("--reset", action="store_true",
                        help="Clear and re-seed Neo4j from scratch")
    args = parser.parse_args()

    asyncio.run(main(args.pdf_dir, args.reset))
