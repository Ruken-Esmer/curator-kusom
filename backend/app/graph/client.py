"""
CURATOR — Neo4j Knowledge Graph Client
Handles all graph database operations: seeding, querying, traversal.
"""
from __future__ import annotations

import contextlib
from typing import Any, Generator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.core.config import get_settings
from app.core.logging import logger
from app.models.schemas import BlockNode, YearNode, NodeType, RelationType

settings = get_settings()


class Neo4jClient:
    """Async Neo4j client with connection pooling."""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        await self._driver.verify_connectivity()
        logger.info("neo4j.connected", uri=settings.neo4j_uri)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    @contextlib.asynccontextmanager
    async def session(self) -> Generator[AsyncSession, None, None]:
        if not self._driver:
            raise RuntimeError("Neo4j driver not initialised. Call connect() first.")
        async with self._driver.session(database=settings.neo4j_database) as session:
            yield session

    async def is_healthy(self) -> bool:
        try:
            async with self.session() as s:
                await s.run("RETURN 1")
            return True
        except (ServiceUnavailable, RuntimeError, Neo4jError, OSError):
            return False

    # Schema Setup

    async def create_constraints(self) -> None:
        """Create uniqueness constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (y:Year) REQUIRE y.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Block) REQUIRE b.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Competency) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Department) REQUIRE d.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (b:Block) ON (b.year)",
            "CREATE FULLTEXT INDEX block_text IF NOT EXISTS FOR (b:Block) ON EACH [b.name_en, b.name_tr, b.description_en]",
            "CREATE FULLTEXT INDEX topic_text IF NOT EXISTS FOR (t:Topic) ON EACH [t.name_en, t.name_tr]",
        ]
        async with self.session() as s:
            for cql in constraints:
                await s.run(cql)
        logger.info("neo4j.constraints_created")

    # Node Upsert

    async def upsert_year(self, year: YearNode) -> None:
        cql = """
        MERGE (y:Year {id: $id})
        SET y += {
            year_number: $year_number,
            name_en: $name_en,
            name_tr: $name_tr,
            description_en: $description_en,
            description_tr: $description_tr,
            institution: $institution
        }
        """
        async with self.session() as s:
            await s.run(cql, **year.model_dump())

    async def upsert_block(self, block: BlockNode) -> None:
        cql = """
        MERGE (b:Block {id: $id})
        SET b += {
            year: $year,
            block_number: $block_number,
            name_en: $name_en,
            name_tr: $name_tr,
            weeks: $weeks,
            departments: $departments,
            topics: $topics,
            competencies: $competencies,
            description_en: $description_en,
            description_tr: $description_tr
        }
        WITH b
        MATCH (y:Year {year_number: $year})
        MERGE (y)-[:CONTAINS]->(b)
        """
        async with self.session() as s:
            await s.run(cql, **block.model_dump())

    async def create_prerequisite(self, from_id: str, to_id: str) -> None:
        """Create PREREQUISITE_OF edge: (from_id)-[:PREREQUISITE_OF]->(to_id)."""
        cql = """
        MATCH (a:Block {id: $from_id}), (b:Block {id: $to_id})
        MERGE (a)-[:PREREQUISITE_OF]->(b)
        """
        async with self.session() as s:
            await s.run(cql, from_id=from_id, to_id=to_id)

    async def upsert_topic(self, topic_id: str, name_en: str, name_tr: str,
                           block_id: str, department: str = "") -> None:
        cql = """
        MERGE (t:Topic {id: $topic_id})
        SET t.name_en = $name_en, t.name_tr = $name_tr, t.department = $department
        WITH t
        MATCH (b:Block {id: $block_id})
        MERGE (b)-[:COVERS_TOPIC]->(t)
        """
        async with self.session() as s:
            await s.run(cql, topic_id=topic_id, name_en=name_en,
                        name_tr=name_tr, block_id=block_id, department=department)

    async def upsert_department(self, dept_id: str, name: str,
                                block_id: str, category: str = "") -> None:
        cql = """
        MERGE (d:Department {id: $dept_id})
        SET d.name = $name, d.category = $category
        WITH d
        MATCH (b:Block {id: $block_id})
        MERGE (b)-[:TAUGHT_BY]->(d)
        """
        async with self.session() as s:
            await s.run(cql, dept_id=dept_id, name=name,
                        block_id=block_id, category=category)

    # Graph Queries

    async def get_curriculum_tree(self, institution: str = "koc_university") -> list[dict]:
        cql = """
        MATCH (y:Year {institution: $institution})-[:CONTAINS]->(b:Block)
        RETURN y, collect(b) as blocks
        ORDER BY y.year_number
        """
        async with self.session() as s:
            result = await s.run(cql, institution=institution)
            records = await result.data()
        return records

    async def get_block_context(self, block_id: str) -> dict[str, Any]:
        """Fetch a block with its prerequisites, topics, and successor blocks."""
        cql = """
        MATCH (b:Block {id: $block_id})
        OPTIONAL MATCH (pre:Block)-[:PREREQUISITE_OF]->(b)
        OPTIONAL MATCH (b)-[:PREREQUISITE_OF]->(nxt:Block)
        OPTIONAL MATCH (b)-[:COVERS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (b)-[:TAUGHT_BY]->(d:Department)
        RETURN b,
               collect(DISTINCT pre) AS prerequisites,
               collect(DISTINCT nxt) AS successors,
               collect(DISTINCT t)   AS topics,
               collect(DISTINCT d)   AS departments
        """
        async with self.session() as s:
            result = await s.run(cql, block_id=block_id)
            record = await result.single()
        return dict(record) if record else {}

    async def get_prerequisites_chain(self, block_id: str) -> list[dict]:
        """Traverse prerequisite chain recursively (up to 5 hops)."""
        cql = """
        MATCH path = (start:Block)-[:PREREQUISITE_OF*1..5]->(target:Block {id: $block_id})
        RETURN [n IN nodes(path) | {id: n.id, name_en: n.name_en, year: n.year}] AS chain
        ORDER BY length(path)
        """
        async with self.session() as s:
            result = await s.run(cql, block_id=block_id)
            return await result.data()

    async def get_learning_pathway(self, topic: str) -> list[dict]:
        """Find all blocks covering a topic, ordered by year."""
        cql = """
        MATCH (b:Block)-[:COVERS_TOPIC]->(t:Topic)
        WHERE toLower(t.name_en) CONTAINS toLower($topic)
           OR toLower(b.name_en) CONTAINS toLower($topic)
           OR ANY(tp IN b.topics WHERE toLower(tp) CONTAINS toLower($topic))
        RETURN b ORDER BY b.year, b.block_number
        """
        async with self.session() as s:
            result = await s.run(cql, topic=topic)
            return await result.data()

    async def fulltext_search(self, query: str, limit: int = 10) -> list[dict]:
        """Search blocks and topics using Neo4j full-text index."""
        cql = """
        CALL db.index.fulltext.queryNodes('block_text', $query)
        YIELD node, score
        RETURN node, score
        ORDER BY score DESC LIMIT $limit
        """
        async with self.session() as s:
            result = await s.run(cql, query=query, limit=limit)
            return await result.data()

    async def get_subgraph(self, node_id: str, depth: int = 2) -> dict[str, Any]:
        """Return nodes + edges for visualisation centred on node_id."""
        depth = max(1, min(int(depth), 4))      # variable-length bounds cannot be parameters
        cql = """
        MATCH path = (start {id: $node_id})-[*1..%d]-(connected)
        RETURN
            collect(DISTINCT {
                id:    coalesce(start.id, ''),
                label: labels(start)[0],
                name:  coalesce(start.name_en, start.name, '')
            }) +
            collect(DISTINCT {
                id:    coalesce(connected.id, ''),
                label: labels(connected)[0],
                name:  coalesce(connected.name_en, connected.name, '')
            }) AS nodes,
            collect(DISTINCT {
                source: startNode(relationships(path)[0]).id,
                target: endNode(relationships(path)[0]).id,
                type:   type(relationships(path)[0])
            }) AS edges
        """ % depth
        async with self.session() as s:
            result = await s.run(cql, node_id=node_id)
            record = await result.single()
        return dict(record) if record else {"nodes": [], "edges": []}


# Singleton instance
neo4j_client = Neo4jClient()
