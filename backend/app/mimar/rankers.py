"""MİMAR — Three independent pairwise rankers and Reciprocal Rank Fusion."""
from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence

import numpy as np
from scipy import sparse

from app.mimar.text import (
    DEFAULT_PREPROCESS, PreprocessConfig, content_tokens_with_positions, tokenize,
)

try:  # FAISS is optional; exact numpy search is used as a fallback.
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    faiss = None
    FAISS_AVAILABLE = False

Pair = tuple[int, int]
BLOCK = 512


#  helpers

def _topk_rows(sim_block: np.ndarray, row_offset: int, groups: np.ndarray, k: int) -> dict[Pair, float]:
    """Top-k eligible neighbours for each row of a dense similarity block."""
    out: dict[Pair, float] = {}
    n = sim_block.shape[1]
    for r in range(sim_block.shape[0]):
        i = row_offset + r
        row = sim_block[r].astype(np.float64, copy=True)
        row[groups == groups[i]] = -np.inf          # same activity (includes self)
        kk = min(k, n - 1)
        if kk <= 0:
            continue
        idx = np.argpartition(-row, kk - 1)[:kk]
        for j in idx:
            s = row[j]
            if not np.isfinite(s) or s <= 0:
                continue
            a, b = (i, int(j)) if i < j else (int(j), i)
            if s > out.get((a, b), -np.inf):
                out[(a, b)] = float(s)
    return out


def rank_pairs(scores: dict[Pair, float], keys: Sequence[str], depth: int | None = None) -> list[tuple[Pair, float]]:
    """Deterministic global ranking: score desc, then by persistent LO ids."""
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], keys[kv[0][0]], keys[kv[0][1]]))
    return ordered[:depth] if depth else ordered


#  BM25 (sparse, exact)

@dataclass
class BM25Params:
    k1: float = 1.5
    b: float = 0.75


class BM25PairRanker:
    name = "bm25"

    def __init__(self, params: BM25Params | None = None, pre: PreprocessConfig = DEFAULT_PREPROCESS):
        self.params = params or BM25Params()
        self.pre = pre
        self.vocab: dict[str, int] = {}
        self.W: sparse.csr_matrix | None = None
        self.Q: sparse.csr_matrix | None = None
        self.groups: np.ndarray | None = None

    def _bin(self, docs: list[list[str]]) -> sparse.csr_matrix:
        rows, cols = [], []
        for r, toks in enumerate(docs):
            for t in set(toks):
                c = self.vocab.get(t)
                if c is not None:
                    rows.append(r); cols.append(c)
        return sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(docs), len(self.vocab)))

    def fit(self, texts: Sequence[str], groups: Sequence[str]) -> "BM25PairRanker":
        docs = [tokenize(t, self.pre) for t in texts]
        df: Counter[str] = Counter()
        for d in docs:
            df.update(set(d))
        self.vocab = {t: i for i, t in enumerate(sorted(df))}
        n = len(docs)
        avgdl = max(1e-9, float(np.mean([len(d) for d in docs])) if docs else 1.0)
        k1, b = self.params.k1, self.params.b
        rows, cols, vals = [], [], []
        for r, d in enumerate(docs):
            tf = Counter(d)
            dl = len(d)
            for t, f in tf.items():
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                w = idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
                rows.append(r); cols.append(self.vocab[t]); vals.append(w)
        self.W = sparse.csr_matrix((vals, (rows, cols)), shape=(n, len(self.vocab)))
        self.Q = self._bin(docs)
        self.groups = np.asarray(groups)
        return self

    def pair_scores(self, per_query_k: int = 10) -> dict[Pair, float]:
        assert self.W is not None and self.Q is not None
        n = self.W.shape[0]
        out: dict[Pair, float] = {}
        WT = self.W.T.tocsc()
        for start in range(0, n, BLOCK):
            blk = (self.Q[start:start + BLOCK] @ WT).toarray()
            # symmetric max(i→j, j→i): add the transpose contribution
            blk_t = (self.W[start:start + BLOCK] @ self.Q.T).toarray()
            blk = np.maximum(blk, blk_t)
            for p, s in _topk_rows(blk, start, self.groups, per_query_k).items():
                if s > out.get(p, -1):
                    out[p] = s
        return out

    def query(self, texts: Sequence[str]) -> np.ndarray:
        assert self.W is not None
        q = self._bin([tokenize(t, self.pre) for t in texts])
        return (q @ self.W.T).toarray()


#  Embedding ranker (sentence-transformers if installed, else TF-IDF + LSA)

@dataclass
class EmbeddingParams:
    backend: str = "tfidf-lsa"           # "tfidf-lsa" | "sentence-transformers"
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    lsa_components: int = 192
    char_ngrams: bool = True
    seed: int = 20260913


class EmbeddingPairRanker:
    name = "embedding"

    def __init__(self, params: EmbeddingParams | None = None):
        self.params = params or EmbeddingParams()
        self.E: np.ndarray | None = None
        self.groups: np.ndarray | None = None
        self._encoder = None
        self.index = None
        self.backend_used = ""

    # ---- encoders -------------------------------------------------------
    def _fit_encoder(self, texts: Sequence[str]) -> np.ndarray:
        p = self.params
        if p.backend == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                model = SentenceTransformer(p.model_name, device="cpu")
                self._encoder = lambda xs: model.encode(list(xs), normalize_embeddings=True,
                                                        convert_to_numpy=True)
                self.backend_used = f"sentence-transformers:{p.model_name}"
                return self._encoder(texts).astype("float32")
            except Exception:
                # documented fallback: deterministic local model
                pass
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import FeatureUnion, make_pipeline
        from sklearn.preprocessing import Normalizer

        word = TfidfVectorizer(tokenizer=tokenize, preprocessor=None, lowercase=False,
                               token_pattern=None, ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        feats = [("word", word)]
        if p.char_ngrams:
            feats.append(("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                                  sublinear_tf=True, min_df=1)))
        union = FeatureUnion(feats)
        X = union.fit_transform(list(texts))
        n_comp = max(2, min(p.lsa_components, X.shape[0] - 1, X.shape[1] - 1))
        svd = TruncatedSVD(n_components=n_comp, random_state=p.seed, algorithm="arpack")
        pipe = make_pipeline(svd, Normalizer(copy=False))
        E = pipe.fit_transform(X)
        self._encoder = lambda xs: pipe.transform(union.transform(list(xs)))
        self.backend_used = f"tfidf-lsa(d={n_comp})"
        return E.astype("float32")

    def fit(self, texts: Sequence[str], groups: Sequence[str]) -> "EmbeddingPairRanker":
        self.E = np.ascontiguousarray(self._fit_encoder(texts), dtype="float32")
        self.groups = np.asarray(groups)
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatIP(self.E.shape[1])
            self.index.add(self.E)
        return self

    def pair_scores(self, per_query_k: int = 10) -> dict[Pair, float]:
        assert self.E is not None
        n = self.E.shape[0]
        out: dict[Pair, float] = {}
        if self.index is not None:
            # exact search; enlarge k so that same-activity neighbours can be dropped
            max_group = max(Counter(self.groups.tolist()).values())
            kk = min(n, per_query_k + max_group + 1)
            D, I = self.index.search(self.E, kk)
            for i in range(n):
                taken = 0
                for s, j in zip(D[i], I[i]):
                    if j < 0 or self.groups[j] == self.groups[i]:
                        continue
                    if s <= 0:
                        break
                    a, b = (i, int(j)) if i < j else (int(j), i)
                    if s > out.get((a, b), -1):
                        out[(a, b)] = float(s)
                    taken += 1
                    if taken >= per_query_k:
                        break
            return out
        for start in range(0, n, BLOCK):
            blk = self.E[start:start + BLOCK] @ self.E.T
            for p, s in _topk_rows(blk, start, self.groups, per_query_k).items():
                if s > out.get(p, -1):
                    out[p] = s
        return out

    def query(self, texts: Sequence[str]) -> np.ndarray:
        assert self.E is not None and self._encoder is not None
        Q = np.asarray(self._encoder(texts), dtype="float32")
        return Q @ self.E.T

    def similarity(self, i: int, j: int) -> float:
        assert self.E is not None
        return float(self.E[i] @ self.E[j])


#  Concept-graph ranker

@dataclass
class ConceptParams:
    max_ngram: int = 3
    min_df: int = 2                 # a concept must link ≥ 2 LOs
    max_df_ratio: float = 0.15      # very generic concepts are dropped
    related_min_cooc: int = 2       # concept–concept RELATED_TO edge
    two_hop_weight: float = 0.35    # β for 2-hop (LO→concept→concept→LO) paths
    synonyms: dict[str, str] = field(default_factory=dict)  # optional lexicon (e.g. MeSH)


def extract_candidate_concepts(text: str, max_ngram: int = 3,
                               synonyms: dict[str, str] | None = None) -> set[str]:
    toks = content_tokens_with_positions(text, DEFAULT_PREPROCESS)
    out: set[str] = set()
    run: list[str] = []
    for t in toks + [None]:
        if t is None:
            for n in range(1, max_ngram + 1):
                for s in range(0, len(run) - n + 1):
                    out.add(" ".join(run[s:s + n]))
            run = []
        else:
            run.append(t)
    if synonyms:
        out = {synonyms.get(c, c) for c in out}
    return out


class ConceptGraphPairRanker:
    """LO–MENTIONS→Concept–RELATED_TO→Concept graph with weighted Adamic–Adar (1-hop) plus damped 2-hop…"""

    name = "graph"

    def __init__(self, params: ConceptParams | None = None):
        self.params = params or ConceptParams()
        self.concepts: list[str] = []
        self.lo_concepts: list[set[str]] = []
        self.A: sparse.csr_matrix | None = None      # LO × concept, binary
        self.w: np.ndarray | None = None              # concept weights (1/log(1+df))
        self.R: sparse.csr_matrix | None = None       # concept × concept relation (row-normalised)
        self.groups: np.ndarray | None = None
        self.related_edges: list[tuple[str, str, int]] = []

    def fit(self, texts: Sequence[str], groups: Sequence[str]) -> "ConceptGraphPairRanker":
        p = self.params
        raw = [extract_candidate_concepts(t, p.max_ngram, p.synonyms) for t in texts]
        df: Counter[str] = Counter()
        for cs in raw:
            df.update(cs)
        n = len(texts)
        max_df = max(p.min_df, int(p.max_df_ratio * n))
        keep = sorted(c for c, d in df.items() if p.min_df <= d <= max_df)
        cidx = {c: i for i, c in enumerate(keep)}
        self.concepts = keep
        self.lo_concepts = [{c for c in cs if c in cidx} for cs in raw]
        rows, cols = [], []
        for r, cs in enumerate(self.lo_concepts):
            for c in cs:
                rows.append(r); cols.append(cidx[c])
        self.A = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, len(keep)))
        self.w = np.array([1.0 / math.log(1 + df[c]) for c in keep]) if keep else np.zeros(0)
        # concept co-occurrence → RELATED_TO
        C = (self.A.T @ self.A).tocoo()
        r_rows, r_cols, r_vals = [], [], []
        self.related_edges = []
        for a, b, v in zip(C.row, C.col, C.data):
            if a < b and v >= p.related_min_cooc:
                # skip pure sub-phrase relations (e.g. "rotator" ⊂ "rotator cuff")
                ca, cb = keep[a], keep[b]
                if ca in cb or cb in ca:
                    continue
                r_rows += [a, b]; r_cols += [b, a]; r_vals += [v, v]
                self.related_edges.append((ca, cb, int(v)))
        R = sparse.csr_matrix((r_vals, (r_rows, r_cols)), shape=(len(keep), len(keep)))
        rs = np.asarray(R.sum(axis=1)).ravel()
        rs[rs == 0] = 1
        self.R = sparse.diags(1.0 / rs) @ R
        self.groups = np.asarray(groups)
        return self

    def _sim_block(self, rows: slice) -> np.ndarray:
        A, w = self.A, self.w
        Wd = sparse.diags(w)
        left = A[rows] @ Wd
        s1 = (left @ A.T).toarray()
        s2 = (left @ self.R @ Wd @ A.T).toarray()
        s = s1 + self.params.two_hop_weight * s2
        deg = np.asarray((A @ w)).ravel()
        deg[deg == 0] = 1
        return s / np.sqrt(np.outer(deg[rows], deg))

    def pair_scores(self, per_query_k: int = 10) -> dict[Pair, float]:
        assert self.A is not None
        n = self.A.shape[0]
        out: dict[Pair, float] = {}
        if self.A.shape[1] == 0:
            return out
        for start in range(0, n, BLOCK):
            blk = self._sim_block(slice(start, min(n, start + BLOCK)))
            for p, s in _topk_rows(blk, start, self.groups, per_query_k).items():
                if s > out.get(p, -1):
                    out[p] = s
        return out

    def query(self, texts: Sequence[str]) -> np.ndarray:
        assert self.A is not None
        cidx = {c: i for i, c in enumerate(self.concepts)}
        rows, cols = [], []
        for r, t in enumerate(texts):
            for c in extract_candidate_concepts(t, self.params.max_ngram, self.params.synonyms):
                if c in cidx:
                    rows.append(r); cols.append(cidx[c])
        Qm = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(texts), len(self.concepts)))
        Wd = sparse.diags(self.w)
        return (Qm @ Wd @ self.A.T).toarray()

    def shared_concepts(self, i: int, j: int) -> list[str]:
        return sorted(self.lo_concepts[i] & self.lo_concepts[j], key=lambda c: (-len(c), c))


#  Reciprocal Rank Fusion

def rrf_fuse(rank_lists: dict[str, list[Pair]], k: int = 60,
             keys: Sequence[str] | None = None) -> list[tuple[Pair, float, dict[str, int]]]:
    """RRF(p) = Σ_m 1 / (k + rank_m(p)), ranks are 1-based."""
    scores: dict[Pair, float] = defaultdict(float)
    ranks: dict[Pair, dict[str, int]] = defaultdict(dict)
    for m, lst in rank_lists.items():
        for r, p in enumerate(lst, start=1):
            scores[p] += 1.0 / (k + r)
            ranks[p][m] = r
    def tie(p: Pair):
        return (keys[p[0]], keys[p[1]]) if keys is not None else p
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], tie(kv[0])))
    return [(p, s, ranks[p]) for p, s in ordered]


def config_hash(obj) -> str:
    import json
    if hasattr(obj, "__dataclass_fields__"):
        obj = asdict(obj)
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]
