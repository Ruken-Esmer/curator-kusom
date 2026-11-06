"""AS1 overlap analysis orchestration."""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any, Sequence

import numpy as np

from app.mimar.rankers import (
    BM25PairRanker, BM25Params, ConceptGraphPairRanker, ConceptParams,
    EmbeddingPairRanker, EmbeddingParams, rank_pairs, rrf_fuse,
)
from app.mimar.text import DEFAULT_PREPROCESS, PreprocessConfig, normalized_key

METHODS = ("bm25", "embedding", "graph")
HYBRID = "hybrid"


def pair_key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


def split_key(k: str) -> tuple[str, str]:
    a, b = k.split("|", 1)
    return a, b


@dataclass
class AnalysisConfig:
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    bm25: BM25Params = field(default_factory=BM25Params)
    embedding: EmbeddingParams = field(default_factory=EmbeddingParams)
    concept: ConceptParams = field(default_factory=ConceptParams)
    per_query_k: int = 10            # neighbours retrieved per LO per method
    max_pairs_per_method: int = 5000
    list_depth: int = 150            # D – equal list depth for hybrid and single methods
    rrf_k: int = 60
    # content families / split
    family_cosine: float = 0.80
    family_concept_jaccard: float = 0.60
    test_fraction: float = 0.30
    seed: int = 20260913

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "AnalysisConfig":
        d = dict(d or {})
        cfg = cls()
        for k, v in d.items():
            if k == "preprocess" and isinstance(v, dict):
                cfg.preprocess = PreprocessConfig(**{**asdict(cfg.preprocess), **v})
            elif k == "bm25" and isinstance(v, dict):
                cfg.bm25 = BM25Params(**{**asdict(cfg.bm25), **v})
            elif k == "embedding" and isinstance(v, dict):
                cfg.embedding = EmbeddingParams(**{**asdict(cfg.embedding), **v})
            elif k == "concept" and isinstance(v, dict):
                cfg.concept = ConceptParams(**{**asdict(cfg.concept), **v})
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class LORecord:
    uid: str
    text: str
    activity: str
    course: str = ""
    year: int = 0
    discipline: str = ""
    mesh: list[str] = field(default_factory=list)
    ucep_links: list[str] = field(default_factory=list)
    competencies: list[str] = field(default_factory=list)
    context: str = ""          # permitted KuLearn material snippets (AS2b only)


class OverlapAnalysis:
    """Holds fitted rankers so that the same models can be reused for family construction, evidence, and UÇEP…"""

    def __init__(self, los: Sequence[LORecord], cfg: AnalysisConfig):
        if len(los) < 3:
            raise ValueError("At least 3 learning objectives are required.")
        self.los = list(los)
        self.cfg = cfg
        self.uids = [lo.uid for lo in self.los]
        self.index = {u: i for i, u in enumerate(self.uids)}
        texts = [lo.text for lo in self.los]
        groups = [lo.activity or lo.uid for lo in self.los]
        t0 = time.perf_counter()
        self.bm25 = BM25PairRanker(cfg.bm25, cfg.preprocess).fit(texts, groups)
        self.emb = EmbeddingPairRanker(cfg.embedding).fit(texts, groups)
        self.graph = ConceptGraphPairRanker(cfg.concept).fit(texts, groups)
        self.rankers = {"bm25": self.bm25, "embedding": self.emb, "graph": self.graph}
        # AS2b: a fourth, separate channel over LO text + permitted material
        # snippets.  The three core channels still use only the LO texts, so
        # the extended report differs from the core report only by this channel.
        if any(lo.context for lo in self.los):
            ctx = [f"{lo.text} {lo.context}".strip() for lo in self.los]
            self.material = EmbeddingPairRanker(cfg.embedding).fit(ctx, groups)
            self.rankers["material"] = self.material
        self.fit_seconds = time.perf_counter() - t0
        self._lists: dict[str, list[tuple[str, float]]] | None = None

    # --- global rankings -------------------------------------------------
    def method_lists(self) -> dict[str, list[tuple[str, float]]]:
        if self._lists is None:
            out: dict[str, list[tuple[str, float]]] = {}
            for name, r in self.rankers.items():
                scores = r.pair_scores(self.cfg.per_query_k)
                ranked = rank_pairs(scores, self.uids, self.cfg.max_pairs_per_method)
                out[name] = [(pair_key(self.uids[i], self.uids[j]), s) for (i, j), s in ranked]
            self._lists = out
        return self._lists

    def hybrid(self, allowed: set[str] | None = None, depth: int | None = None) -> list[dict[str, Any]]:
        """RRF over method lists, optionally restricted to a pair universe (e.g."""
        lists = self.restricted_lists(allowed)
        rank_lists = {m: [k for k, _ in lst] for m, lst in lists.items()}
        fused = rrf_fuse(rank_lists, k=self.cfg.rrf_k, keys=None)
        # deterministic tie-break on keys
        fused.sort(key=lambda t: (-t[1], t[0]))
        res = []
        score_maps = {m: dict(lst) for m, lst in lists.items()}
        for r, (k, s, ranks) in enumerate(fused, start=1):
            res.append({
                "pair": k, "rank": r, "rrf": round(s, 8), "method_ranks": ranks,
                "method_scores": {m: round(score_maps[m][k], 6) for m in ranks},
            })
        return res[:depth] if depth else res

    def restricted_lists(self, allowed: set[str] | None) -> dict[str, list[tuple[str, float]]]:
        lists = self.method_lists()
        if allowed is None:
            return lists
        return {m: [(k, s) for k, s in lst if k in allowed] for m, lst in lists.items()}

    def top_lists(self, allowed: set[str] | None, depth: int) -> dict[str, list[str]]:
        """Equal-depth candidate lists for every single method and the hybrid."""
        lists = self.restricted_lists(allowed)
        out = {m: [k for k, _ in lst[:depth]] for m, lst in lists.items()}
        out[HYBRID] = [h["pair"] for h in self.hybrid(allowed, depth)]
        return out

    # --- evidence ----------------------------------------------------------
    def evidence(self, key: str) -> dict[str, Any]:
        a, b = split_key(key)
        i, j = self.index[a], self.index[b]
        return {
            "cosine": round(self.emb.similarity(i, j), 4),
            "shared_concepts": self.graph.shared_concepts(i, j)[:8],
        }

    # --- content families ----------------------------------------------------
    def families(self) -> dict[str, str]:
        """Union–find over near-identical content."""
        n = len(self.uids)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        by_text: dict[str, int] = {}
        for i, lo in enumerate(self.los):
            k = normalized_key(lo.text)
            if k in by_text:
                union(i, by_text[k])
            else:
                by_text[k] = i
        emb_scores = self.emb.pair_scores(self.cfg.per_query_k)
        for (i, j), s in emb_scores.items():
            if s >= self.cfg.family_cosine:
                union(i, j)
        lc = self.graph.lo_concepts
        for (i, j) in self.graph.pair_scores(self.cfg.per_query_k):
            a, b = lc[i], lc[j]
            if a and b and len(a & b) / len(a | b) >= self.cfg.family_concept_jaccard:
                union(i, j)
        roots: dict[int, str] = {}
        fam: dict[str, str] = {}
        for i, u in enumerate(self.uids):
            r = find(i)
            if r not in roots:
                roots[r] = f"F{len(roots) + 1:05d}"
            fam[u] = roots[r]
        return fam


def split_by_family(families: dict[str, str], test_fraction: float, seed: int,
                    strata: dict[str, Any] | None = None) -> dict[str, str]:
    """Family-level random split."""
    members: dict[str, list[str]] = {}
    for u, f in families.items():
        members.setdefault(f, []).append(u)
    fam_stratum: dict[str, Any] = {}
    for f, us in members.items():
        if strata:
            vals = [strata.get(u) for u in us]
            fam_stratum[f] = max(set(vals), key=vals.count)
        else:
            fam_stratum[f] = "all"
    rng = random.Random(seed)
    split: dict[str, str] = {}
    for s in sorted(set(fam_stratum.values()), key=str):
        fams = sorted(f for f, v in fam_stratum.items() if v == s)
        rng.shuffle(fams)
        total = sum(len(members[f]) for f in fams)
        target = test_fraction * total
        acc = 0
        for f in fams:
            # include the family in test if doing so moves the share closer to target
            part = "test" if acc + len(members[f]) / 2 <= target else "dev"
            if part == "test":
                acc += len(members[f])
            for u in members[f]:
                split[u] = part
    return split


def split_pairs(keys: Sequence[str], split: dict[str, str]) -> dict[str, set[str]]:
    out = {"dev": set(), "test": set(), "cross": set()}
    for k in keys:
        a, b = split_key(k)
        sa, sb = split.get(a), split.get(b)
        out[sa if sa == sb and sa in ("dev", "test") else "cross"].add(k)
    return out


def eligible_universe_size(los: Sequence[LORecord], uids: set[str]) -> int:
    """Number of eligible (different-activity) pairs among ``uids``."""
    from collections import Counter
    sub = [lo for lo in los if lo.uid in uids]
    n = len(sub)
    c = Counter(lo.activity or lo.uid for lo in sub)
    return n * (n - 1) // 2 - sum(v * (v - 1) // 2 for v in c.values())


def lock_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def stability_check(los: Sequence[LORecord], cfg: AnalysisConfig, runs: int = 5,
                    top: int = 20, threshold: float = 0.90) -> dict[str, Any]:
    """Re-run the full analysis ``runs`` times with identical data and settings and report pairwise overlap of…"""
    tops: list[list[str]] = []
    timings = []
    for _ in range(runs):
        t0 = time.perf_counter()
        a = OverlapAnalysis(los, cfg)
        tops.append([h["pair"] for h in a.hybrid(depth=top)])
        timings.append(round(time.perf_counter() - t0, 3))
    overlaps = []
    for x, y in combinations(range(runs), 2):
        denom = max(1, min(len(tops[x]), len(tops[y])))
        overlaps.append(len(set(tops[x]) & set(tops[y])) / denom)
    stable_items = set.intersection(*(set(t) for t in tops)) if tops else set()
    changed = sorted(set().union(*(set(t) for t in tops)) - stable_items) if tops else []
    return {
        "runs": runs, "top": top, "threshold": threshold,
        "pairwise_overlap": [round(o, 4) for o in overlaps],
        "min_overlap": round(min(overlaps), 4) if overlaps else 1.0,
        "meets_criterion": (min(overlaps) if overlaps else 1.0) >= threshold,
        "stable_pairs": len(stable_items), "changed_pairs": changed,
        "seconds_per_run": timings,
    }
