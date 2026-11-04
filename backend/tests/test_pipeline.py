"""Unit tests for the RAG pipeline components."""
import pytest
from app.data.curriculum.koc_university import KUC_CURRICULUM, build_chunks
from app.utils.bm25 import BM25Retriever
from app.models.schemas import Language, QueryType


def test_curriculum_has_six_years():
    assert len(KUC_CURRICULUM) == 6


def test_all_blocks_have_ids():
    for year in KUC_CURRICULUM:
        for block in year["blocks"]:
            assert "id" in block
            assert block["id"].startswith("Y")


def test_build_chunks_returns_list():
    chunks = build_chunks(KUC_CURRICULUM)
    assert len(chunks) > 50
    for chunk in chunks:
        assert "id" in chunk
        assert "content" in chunk
        assert "source" in chunk


def test_bm25_search():
    chunks = build_chunks(KUC_CURRICULUM)
    retriever = BM25Retriever()
    retriever.build(chunks)
    results = retriever.search("cardiovascular ECG heart failure", top_k=3)
    assert len(results) > 0
    assert any("Y2B1" in r.source for r in results)


def test_bm25_turkish_search():
    chunks = build_chunks(KUC_CURRICULUM)
    retriever = BM25Retriever()
    retriever.build(chunks)
    results = retriever.search("kardiyovasküler sistem", top_k=3)
    assert len(results) > 0


def test_prerequisite_chain_structure():
    """Verify that prerequisite IDs reference existing block IDs."""
    all_ids = {
        block["id"]
        for year in KUC_CURRICULUM
        for block in year["blocks"]
    }
    for year in KUC_CURRICULUM:
        for block in year["blocks"]:
            for pre in block.get("prerequisite_ids", []):
                assert pre in all_ids, f"{block['id']} references unknown prerequisite {pre}"


def test_rrf_fuses_three_channels():
    from app.models.schemas import RetrievedChunk
    from app.rag.pipeline import _rrf_fusion
    mk = lambda i: RetrievedChunk(id=i, content=i, source=i, source_type="block")
    fused = _rrf_fusion([mk("a"), mk("b")], [mk("b")], 3, graph_chunks=[mk("c"), mk("b")])
    assert fused[0].id == "b"                     # appears in all three channels
    assert {c.id for c in fused} == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_offline_llm_router_and_generation():
    from app.rag.llm import OfflineExtractiveClient
    from app.rag.pipeline import ROUTER_PROMPT
    c = OfflineExtractiveClient()
    import json
    out = json.loads(await c.complete(ROUTER_PROMPT, "What should I study before Y2B1?"))
    assert out["query_type"] == "pathway" and out["entities"] == ["Y2B1"]
    ans = await c.complete_with_history("CONTEXT\n[1] Source: Y2B1 (score: 0.1)\nBlock Y2B1: Cardio", [{"role": "user", "content": "q"}])
    assert "[Y2B1]" in ans
