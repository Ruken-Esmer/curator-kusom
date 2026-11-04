"""Unit tests: preprocessing, rankers, RRF, QC, sampling, store."""
import math

import pytest

from app.mimar.analysis import AnalysisConfig, LORecord, OverlapAnalysis, pair_key, split_by_family, split_pairs
from app.mimar.qc import prepare_learning_objectives, prepare_ucep
from app.mimar.rankers import rrf_fuse
from app.mimar.sampling import allocate, build_as1_sample, stratified_sample
from app.mimar.store import Store
from app.mimar.fake_data import generate_mskl, true_overlap
from app.mimar.text import bloom_level, normalized_key, tokenize


def test_tokenize_removes_bloom_verbs_and_stopwords():
    toks = tokenize("Describe the muscles of the rotator cuff and their innervation.")
    assert "describe" not in toks and "the" not in toks
    assert "rotator" in toks and "cuff" in toks and "muscle" in toks   # light stemming


def test_turkish_casefold_and_bloom():
    assert normalized_key("İnsan KEMİĞİ") == "insan kemiği"
    assert bloom_level("Define and then evaluate the plan") == 6   # 'plan' (6) > evaluate (5)
    assert bloom_level("Describe gait") == 2


def test_rrf_formula_k60():
    fused = rrf_fuse({"a": ["x", "y"], "b": ["y", "x"], "c": ["y"]}, k=60)
    scores = {p: s for p, s, _ in fused}
    assert math.isclose(scores["y"], 1 / 62 + 1 / 61 + 1 / 61)
    assert math.isclose(scores["x"], 1 / 61 + 1 / 62)
    assert fused[0][0] == "y"
    assert fused[0][2] == {"a": 2, "b": 1, "c": 1}


def _small_los():
    texts = [
        ("A1", "Describe the muscles of the rotator cuff and their innervation.", "act1"),
        ("A2", "Identify the rotator cuff muscles and their nerve supply.", "act2"),
        ("A3", "Explain the regulation of calcium by parathyroid hormone and vitamin D.", "act3"),
        ("A4", "Describe the control of calcium by parathyroid hormone and vitamin D.", "act4"),
        ("A5", "Discuss ethical issues in sports medicine practice.", "act5"),
        ("A6", "Identify the rotator cuff muscles.", "act1"),   # same activity as A1 → never paired with A1
    ]
    return [LORecord(uid=u, text=t, activity=a, course=a, year=2) for u, t, a in texts]


def test_three_rankers_find_planted_pairs_and_respect_activity():
    a = OverlapAnalysis(_small_los(), AnalysisConfig(per_query_k=3, list_depth=5))
    lists = a.method_lists()
    for m in ("bm25", "embedding", "graph"):
        keys = [k for k, _ in lists[m]]
        assert pair_key("A1", "A6") not in keys            # same activity excluded
        assert keys[0] in (pair_key("A1", "A2"), pair_key("A3", "A4"), pair_key("A2", "A6"))
    top = [h["pair"] for h in a.hybrid(depth=3)]
    assert pair_key("A3", "A4") in top
    assert set(a.hybrid()[0]["method_ranks"]) <= {"bm25", "embedding", "graph"}


def test_graph_channel_is_independent_of_bm25_and_embedding():
    a = OverlapAnalysis(_small_los(), AnalysisConfig(per_query_k=3))
    # concept graph scores derive only from concepts; the ranker holds no reference to the others
    assert not hasattr(a.graph, "bm25") and not hasattr(a.graph, "emb")
    assert any("rotator cuff" in c for c in a.graph.concepts)


def test_family_split_keeps_families_together():
    data = generate_mskl()
    los = [LORecord(uid=r["uid"], text=r["text"], activity=r["activity"], year=r["year"]) for r in data["los"]]
    a = OverlapAnalysis(los, AnalysisConfig())
    fam = a.families()
    split = split_by_family(fam, 0.3, 1, {l.uid: l.year for l in los})
    for f in set(fam.values()):
        assert len({split[u] for u, ff in fam.items() if ff == f}) == 1
    share = sum(v == "test" for v in split.values()) / len(split)
    assert 0.22 <= share <= 0.38
    parts = split_pairs([pair_key(x.uid, y.uid) for x, y in zip(los, los[1:])], split)
    assert set(parts) == {"dev", "test", "cross"}


def test_qc_exclusions_with_reasons():
    rows = [
        {"uid": "1", "text": "Describe the anatomy of the knee joint.", "activity": "a", "source": "s"},
        {"uid": "2", "text": "", "activity": "a", "source": "s"},
        {"uid": "", "text": "Describe hip anatomy in detail.", "activity": "a", "source": "s"},
        {"uid": "1", "text": "Explain the knee biomechanics in gait.", "activity": "b", "source": "s"},
        {"uid": "4", "text": "Describe the anatomy of the knee joint.", "activity": "a", "source": "s"},
        {"uid": "5", "text": "Describe the anatomy of the knee joint.", "activity": "c", "source": "s"},
        {"uid": "6", "text": "Explain bone.", "activity": "c", "source": "s"},
        {"uid": "7", "text": "Explain bone remodeling by osteoclasts.", "activity": "", "source": "s"},
        {"uid": "8", "text": "Explain bone remodeling by osteoclasts.", "activity": "d", "source": ""},
        {"uid": "9", "text": "Explain bone remodeling by osteoclasts.", "activity": "d", "source": "s",
         "mesh": "Bone Remodeling", "mesh_verified": "no"},
    ]
    res = prepare_learning_objectives(rows)
    reasons = res["report"]["exclusion_reasons"]
    assert reasons == {"empty_text": 1, "missing_persistent_id": 1, "duplicate_id": 1,
                       "duplicate_text_in_same_activity": 1, "not_reviewable_too_short": 1,
                       "missing_activity": 1, "missing_source": 1}
    kept = {r["uid"] for r in res["included"]}
    assert kept == {"1", "5", "9"}                      # cross-activity similar text retained
    assert res["report"]["unverified_mesh_terms_dropped"] == 1
    assert next(r for r in res["included"] if r["uid"] == "9")["mesh"] == []


def test_ucep_qc_requires_turkish_original():
    res = prepare_ucep([{"code": "U1", "text_tr": "Gut", "text_en": ""}, {"code": "U2", "text_en": "x"},
                        {"code": "U1", "text_tr": "x"}])
    assert res["report"]["included"] == 1 and res["report"]["missing_english"] == 1
    assert {e["reason"] for e in res["excluded"]} == {"missing_original_turkish_text", "duplicate_code"}


def test_allocation_and_inclusion_probabilities():
    alloc = allocate({"a": 100, "b": 10, "c": 1000}, 120, min_per_stratum=10)
    assert sum(alloc.values()) == 120 and alloc["b"] == 10
    items = stratified_sample({"a": list(range(100)), "b": list(range(10)), "c": list(range(1000))}, alloc, 1)
    for h, N in (("a", 100), ("b", 10), ("c", 1000)):
        rows = [i for i in items if i["stratum"] == h]
        assert all(math.isclose(r["pi"], alloc[h] / N) for r in rows)
        assert math.isclose(sum(r["weight"] for r in rows), N)     # HT weights recover N_h


def test_as1_sample_includes_unlisted_stratum():
    lists = {"hybrid": ["a|b", "c|d"], "bm25": ["a|b", "e|f"], "embedding": ["c|d"], "graph": []}
    uids = list("abcdefghij")
    act = {u: u for u in uids}
    d = build_as1_sample(lists, 2, uids, act, universe_size=45, n_total=10, unlisted_fraction=0.5, min_per_stratum=1)
    st = {i["stratum"] for i in d["items"]}
    assert "unlisted" in st
    unl = [i for i in d["items"] if i["stratum"] == "unlisted"]
    assert all(i["item"] not in {"a|b", "c|d", "e|f"} for i in unl)
    assert math.isclose(unl[0]["N_h"], 42)


def test_audit_chain_detects_tampering():
    s = Store(":memory:")
    for i in range(5):
        s.audit("u", "act", str(i), {"i": i})
    assert s.verify_audit()["valid"]
    s._db.execute("UPDATE audit SET details='{\"i\": 99}' WHERE seq=3")
    v = s.verify_audit()
    assert not v["valid"] and v["broken_at"] == 3


def test_artifacts_are_content_addressed_and_checked():
    s = Store(":memory:")
    h = s.put_artifact("x", {"a": [1, 2]})
    assert s.get_artifact(h) == {"a": [1, 2]}
    s._db.execute("UPDATE artifacts SET data='{\"a\":[1,3]}' WHERE hash=?", (h,))
    with pytest.raises(ValueError):
        s.get_artifact(h)


def test_synthetic_truth_is_consistent():
    d = generate_mskl()
    g = d["truth"]["group_of"]
    pos = [(a, b) for a in g for b in g if a < b and true_overlap(d["truth"], a, b)]
    assert len(pos) > 40
    assert all(g[a] == g[b] for a, b in pos)
