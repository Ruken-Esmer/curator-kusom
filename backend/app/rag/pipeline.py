"""
CURATOR — LangGraph RAG Pipeline
Four-agent graph: Router → Retrieval → Generation → Validation

State flows through:
  1. RouterAgent   — classifies query type and extracts key entities
  2. RetrievalNode — runs FAISS + BM25 + Neo4j in parallel; fuses with RRF
  3. GenerationAgent — builds prompt, calls LLM, cites sources
  4. ValidationNode  — checks hallucinations, ensures citations are grounded
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

try:  # LangGraph is optional; a sequential runner with identical semantics is used otherwise
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    StateGraph = END = None
    LANGGRAPH_AVAILABLE = False

from app.core.config import get_settings
from app.core.logging import logger
from app.graph.client import neo4j_client
from app.models.schemas import (
    Citation, Language, PathwayStep, QueryType,
    QueryResponse, RetrievedChunk,
)
from app.rag.llm import get_llm_client
from app.utils.bm25 import bm25_retriever
from app.utils.embeddings import vector_store

settings = get_settings()


#  Pipeline State

class PipelineState(TypedDict, total=False):
    query: str
    language: Language
    institution: str
    conversation_history: list[dict[str, str]]
    query_type: QueryType
    entities: list[str]
    retrieved_chunks: list[RetrievedChunk]
    graph_results: list[dict[str, Any]]
    fused_chunks: list[RetrievedChunk]
    answer: str
    citations: list[Citation]
    pathway: list[PathwayStep]
    validated: bool
    error: str | None
    start_time: float


#  Agent: Router

ROUTER_PROMPT = """You are a query classifier for a medical curriculum RAG system.

Classify the query into one of these types:
- factual:    asking about specific content, topics, or details of a block
- relational: asking how concepts/blocks/years connect or relate
- pathway:    asking about prerequisites, what to study before something, learning order
- advisory:   asking for study advice, recommendations, or review guidance

Also extract 1-5 key medical or curriculum entities (block IDs, topic names, year numbers).

Return ONLY valid JSON:
{"query_type": "<type>", "entities": ["entity1", "entity2"]}
"""


async def router_agent(state: PipelineState) -> PipelineState:
    llm = get_llm_client()
    try:
        response = await llm.complete(
            system=ROUTER_PROMPT,
            user=state["query"],
            max_tokens=100,
            temperature=0.0,
        )
        import json
        data = json.loads(response.strip())
        state["query_type"] = QueryType(data.get("query_type", "factual"))
        state["entities"] = data.get("entities", [])
    except Exception as exc:
        logger.warning("router.failed", error=str(exc))
        state["query_type"] = QueryType.FACTUAL
        state["entities"] = []
    return state


#  Agent: Retrieval (parallel fan-out)

async def _graph_retrieve(query: str, entities: list[str],
                          query_type: QueryType) -> list[dict[str, Any]]:
    results = []
    try:
        # Keyword / full-text search
        ft_results = await neo4j_client.fulltext_search(query, limit=settings.rag_top_k_graph)
        results.extend(ft_results)

        # For pathway queries, fetch prerequisite chains for each entity
        if query_type == QueryType.PATHWAY:
            for entity in entities:
                chains = await neo4j_client.get_prerequisites_chain(entity)
                results.extend(chains)

        # Block-level context for each recognised block ID
        for entity in entities:
            if len(entity) >= 4 and entity[0] == "Y" and entity[1].isdigit():
                ctx = await neo4j_client.get_block_context(entity)
                if ctx:
                    results.append(ctx)

        # Topic pathway search
        for entity in entities:
            pathway = await neo4j_client.get_learning_pathway(entity)
            results.extend(pathway)

    except Exception as exc:
        logger.warning("graph_retrieval.failed", error=str(exc))
    return results


def _graph_to_chunks(graph_results: list[dict[str, Any]]) -> list[RetrievedChunk]:
    """Turn Neo4j results into ranked block chunks so that the graph channel
    takes part in RRF (the original code fused only vector + BM25)."""
    corpus = {c["source"]: c for c in bm25_retriever._corpus if c.get("source_type") == "block"
              and c.get("metadata", {}).get("language", "en") == "en"}
    ids: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            v = x.get("id")
            if isinstance(v, str) and v[:1] in ("Y", "R") and v[1:2].isdigit():
                ids.append(v)
            for y in x.values():
                walk(y)
        elif isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
        elif hasattr(x, "get") and hasattr(x, "items"):
            walk(dict(x.items()))

    walk(graph_results)
    out, seen = [], set()
    for bid in ids:
        if bid in seen or bid not in corpus:
            continue
        seen.add(bid)
        c = corpus[bid]
        out.append(RetrievedChunk(id=c["id"], content=c["content"], source=bid, source_type="graph",
                                  score=1.0 / len(seen), metadata=c.get("metadata", {})))
    return out


def _rrf_fusion(
    vector_chunks: list[RetrievedChunk],
    bm25_chunks: list[RetrievedChunk],
    top_k: int,
    graph_chunks: list[RetrievedChunk] | None = None,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion over three channels: score = Σ 1/(k+rank), k=60."""
    K = 60
    scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}
    for channel in (vector_chunks, bm25_chunks, graph_chunks or []):
        for rank, chunk in enumerate(channel):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (K + rank + 1)
            chunk_map.setdefault(chunk.id, chunk)
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:top_k]
    fused = []
    for cid, score in ranked:
        c = chunk_map[cid].model_copy()
        c.score = score
        fused.append(c)
    return fused


async def retrieval_node(state: PipelineState) -> PipelineState:
    query = state["query"]
    entities = state.get("entities", [])
    query_type = state.get("query_type", QueryType.FACTUAL)

    # Fan-out: vector, BM25, graph run concurrently
    vector_task = asyncio.to_thread(vector_store.search, query, settings.rag_top_k_vector)
    bm25_task = asyncio.to_thread(bm25_retriever.search, query, settings.rag_top_k_bm25)
    graph_task = _graph_retrieve(query, entities, query_type)

    vector_chunks, bm25_chunks, graph_results = await asyncio.gather(
        vector_task, bm25_task, graph_task
    )

    graph_chunks = _graph_to_chunks(graph_results)
    fused = _rrf_fusion(vector_chunks, bm25_chunks, settings.rag_fusion_top_k, graph_chunks)

    state["retrieved_chunks"] = vector_chunks + bm25_chunks
    state["graph_results"] = graph_results
    state["fused_chunks"] = fused
    logger.info("retrieval.done",
                vector=len(vector_chunks), bm25=len(bm25_chunks),
                graph=len(graph_results), fused=len(fused))
    return state


#  Agent: Generation

SYSTEM_EN = """You are CURATOR, an AI curriculum advisor for Koç University School of Medicine.
Answer questions about the 6-year undergraduate medical program.

RULES:
- Ground every claim in the retrieved curriculum context below.
- Cite sources as [BlockID] (e.g. [Y2B1]) inline in your answer.
- For pathway questions, present a numbered learning sequence.
- Be concise but thorough. Max 4 paragraphs.
- If the context does not contain enough information, say so clearly.
- Do NOT hallucinate block names or topics.

CURRICULUM CONTEXT:
{context}
"""

SYSTEM_TR = """Sen Koç Üniversitesi Tıp Fakültesi için CURATOR AI müfredat danışmanısın.
6 yıllık lisans tıp programı hakkındaki soruları yanıtlıyorsun.

KURALLAR:
- Her iddiayı aşağıdaki alınan müfredat bağlamına dayandır.
- Kaynakları [BlokID] (örn. [Y2B1]) şeklinde yanıtında belirt.
- Yol soruları için numaralı öğrenme sırası sun.
- Özlü ama kapsamlı ol. Maksimum 4 paragraf.
- Bağlam yeterli bilgi içermiyorsa bunu açıkça belirt.

MÜFREDAT BAĞLAMI:
{context}
"""


def _build_context(chunks: list[RetrievedChunk], graph_results: list[dict]) -> str:
    lines = ["=== RETRIEVED CURRICULUM CHUNKS ==="]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"\n[{i}] Source: {chunk.source} (score: {chunk.score:.3f})")
        lines.append(chunk.content)

    if graph_results:
        lines.append("\n=== KNOWLEDGE GRAPH RESULTS ===")
        for item in graph_results[:5]:
            lines.append(str(item))

    return "\n".join(lines)


def _extract_citations(answer: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    """Parse [BlockID] references from the generated answer."""
    import re
    cited_ids = set(re.findall(r"\[([YR]\d[A-Z0-9]+)\]", answer))
    citations = []
    seen = set()
    for chunk in chunks:
        src = chunk.source
        if src in cited_ids and src not in seen:
            meta = chunk.metadata
            citations.append(Citation(
                block_id=src,
                block_name=meta.get("name_en", src),
                year=meta.get("year", 0),
                relevance=chunk.score,
            ))
            seen.add(src)
    return citations


def _extract_pathway(answer: str, chunks: list[RetrievedChunk]) -> list[PathwayStep]:
    """Extract ordered pathway steps from numbered lists in the answer."""
    import re
    steps = []
    matches = re.findall(r"(\d+)\.\s+(.+?)(?:\n|$)", answer)
    for order, text in matches[:8]:
        block_match = re.search(r"\[([YR]\d[A-Z0-9]+)\]", text)
        block_id = block_match.group(1) if block_match else ""
        year = int(block_id[1]) if block_id and block_id[1].isdigit() else 0
        chunk_name = next((c.metadata.get("name_en", "") for c in chunks if c.source == block_id), "")
        steps.append(PathwayStep(
            order=int(order),
            block_id=block_id,
            block_name=chunk_name or text[:60],
            year=year,
            reason=text,
        ))
    return steps


async def generation_agent(state: PipelineState) -> PipelineState:
    llm = get_llm_client()
    lang = state.get("language", Language.EN)
    fused = state.get("fused_chunks", [])
    graph_results = state.get("graph_results", [])
    history = state.get("conversation_history", [])

    context = _build_context(fused, graph_results)
    system_template = SYSTEM_TR if lang == Language.TR else SYSTEM_EN
    system = system_template.format(context=context)

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": state["query"]})

    answer = await llm.complete_with_history(
        system=system,
        messages=messages,
        max_tokens=settings.rag_max_tokens,
        temperature=settings.rag_temperature,
    )

    state["answer"] = answer
    state["citations"] = _extract_citations(answer, fused)
    state["pathway"] = _extract_pathway(answer, fused)
    return state


#  Node: Validation

async def validation_node(state: PipelineState) -> PipelineState:
    """
    Lightweight hallucination guard:
    checks that every cited [BlockID] exists in fused_chunks or graph_results.
    """
    answer = state.get("answer", "")
    fused = state.get("fused_chunks", [])
    known_ids = {c.source for c in fused}

    import re
    cited = set(re.findall(r"\[([YR]\d[A-Z0-9]+)\]", answer))
    unknown = cited - known_ids

    if unknown:
        logger.warning("validation.unknown_citations", ids=list(unknown))
        disclaimer = ("\n\n*Note: Some cited block IDs could not be verified "
                      "against the retrieved context.*")
        state["answer"] = answer + disclaimer

    state["validated"] = True
    return state


#  Build LangGraph

class _SequentialPipeline:
    """Fallback when LangGraph is not installed: same node order."""

    async def ainvoke(self, state: PipelineState) -> PipelineState:
        for node in (router_agent, retrieval_node, generation_agent, validation_node):
            state = await node(state)
        return state


def _build_graph():
    if not LANGGRAPH_AVAILABLE:
        return _SequentialPipeline()
    g = StateGraph(PipelineState)
    g.add_node("router", router_agent)
    g.add_node("retrieval", retrieval_node)
    g.add_node("generation", generation_agent)
    g.add_node("validation", validation_node)

    g.set_entry_point("router")
    g.add_edge("router", "retrieval")
    g.add_edge("retrieval", "generation")
    g.add_edge("generation", "validation")
    g.add_edge("validation", END)
    return g.compile()


_pipeline = _build_graph()


#  Public API

async def run_pipeline(
    query: str,
    language: Language = Language.EN,
    institution: str = "koc_university",
    conversation_history: list[dict[str, str]] | None = None,
) -> QueryResponse:
    start = time.monotonic()
    initial_state: PipelineState = {
        "query": query,
        "language": language,
        "institution": institution,
        "conversation_history": conversation_history or [],
        "start_time": start,
    }

    try:
        final_state = await _pipeline.ainvoke(initial_state)
    except Exception as exc:
        logger.error("pipeline.failed", error=str(exc))
        return QueryResponse(
            answer="An error occurred while processing your query. Please try again.",
            query_type=QueryType.UNKNOWN,
            language=language,
            processing_time_ms=0.0,
        )

    elapsed_ms = (time.monotonic() - start) * 1000

    return QueryResponse(
        answer=final_state.get("answer", ""),
        query_type=final_state.get("query_type", QueryType.UNKNOWN),
        citations=final_state.get("citations", []),
        pathway=final_state.get("pathway", []),
        retrieved_chunks=final_state.get("fused_chunks", []),
        language=language,
        processing_time_ms=round(elapsed_ms, 1),
    )
