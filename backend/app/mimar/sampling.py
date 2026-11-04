"""MİMAR — Stratified random sampling with recorded inclusion probabilities."""
from __future__ import annotations

import random
from typing import Any, Hashable, Sequence

from app.mimar.analysis import HYBRID, pair_key


def allocate(sizes: dict[str, int], n_total: int, min_per_stratum: int = 10,
             fixed: dict[str, int] | None = None) -> dict[str, int]:
    """Proportional allocation with a per-stratum minimum, capped by N_h."""
    fixed = dict(fixed or {})
    alloc = {h: min(sizes[h], n) for h, n in fixed.items() if h in sizes}
    rest = {h: N for h, N in sizes.items() if h not in alloc and N > 0}
    budget = max(0, n_total - sum(alloc.values()))
    if not rest:
        return alloc
    for h, N in rest.items():
        alloc[h] = min(N, min_per_stratum)
    budget -= sum(alloc[h] for h in rest)
    # largest-remainder proportional distribution, repeated so that budget
    # freed by strata that hit their cap (N_h) is passed on to the others
    while budget > 0:
        open_ = {h: N for h, N in rest.items() if alloc[h] < N}
        if not open_:
            break
        total_open = sum(open_.values())
        shares = {h: budget * N / total_open for h, N in open_.items()}
        extra = {h: int(v) for h, v in shares.items()}
        rem = budget - sum(extra.values())
        for h in sorted(shares, key=lambda h: (-(shares[h] - extra[h]), h))[:rem]:
            extra[h] += 1
        given = 0
        for h in open_:
            add = min(open_[h] - alloc[h], extra[h])
            alloc[h] += add
            given += add
        if given == 0:
            break
        budget -= given
    return alloc


def stratified_sample(strata: dict[str, Sequence[Hashable]], alloc: dict[str, int],
                      seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out = []
    for h in sorted(strata):
        pool = sorted(strata[h], key=str)
        n = min(alloc.get(h, 0), len(pool))
        if n <= 0:
            continue
        chosen = rng.sample(pool, n)
        pi = n / len(pool)
        for item in chosen:
            out.append({"item": item, "stratum": h, "N_h": len(pool), "n_h": n,
                        "pi": pi, "weight": 1.0 / pi})
    return out


def rank_band(rank: int, depth: int) -> str:
    if rank <= max(1, depth // 5):
        return "r1"
    if rank <= max(1, depth // 2):
        return "r2"
    return "r3"


def as1_strata(top_lists: dict[str, list[str]], depth: int) -> dict[str, list[str]]:
    """Strata for listed pairs: best rank band × hybrid membership."""
    best: dict[str, int] = {}
    in_h: set[str] = set(top_lists.get(HYBRID, []))
    for m, lst in top_lists.items():
        for r, k in enumerate(lst, start=1):
            best[k] = min(best.get(k, 10 ** 9), r)
    strata: dict[str, list[str]] = {}
    for k, r in best.items():
        h = f"listed:{rank_band(r, depth)}:{'H' if k in in_h else 'noH'}"
        strata.setdefault(h, []).append(k)
    return strata


def sample_unlisted(uids: Sequence[str], activity: dict[str, str], listed: set[str],
                    n: int, seed: int, max_tries: int = 200000) -> list[str]:
    """Uniform random sample of eligible pairs that no method listed, by rejection sampling over random LO pairs."""
    rng = random.Random(seed + 7)
    uids = sorted(uids)
    got: set[str] = set()
    tries = 0
    while len(got) < n and tries < max_tries:
        tries += 1
        a, b = rng.sample(uids, 2)
        if activity.get(a, a) == activity.get(b, b):
            continue
        k = pair_key(a, b)
        if k in listed or k in got:
            continue
        got.add(k)
    return sorted(got)


def build_as1_sample(top_lists: dict[str, list[str]], depth: int, uids: Sequence[str],
                     activity: dict[str, str], universe_size: int, n_total: int,
                     unlisted_fraction: float = 0.2, min_per_stratum: int = 10,
                     seed: int = 20260913, exclude: set[str] | None = None) -> dict[str, Any]:
    """Return the sample design and items."""
    exclude = exclude or set()
    strata = {h: [k for k in v if k not in exclude] for h, v in as1_strata(top_lists, depth).items()}
    listed = set().union(*top_lists.values()) if top_lists else set()
    n_unlisted_universe = max(0, universe_size - len(listed) - len(exclude - listed))
    n_unl = int(round(n_total * unlisted_fraction)) if n_unlisted_universe else 0
    sizes = {h: len(v) for h, v in strata.items()}
    alloc = allocate(sizes, n_total - n_unl, min_per_stratum)
    items = stratified_sample(strata, alloc, seed)
    if n_unl:
        unl = sample_unlisted(uids, activity, listed | exclude, min(n_unl, n_unlisted_universe), seed)
        pi = len(unl) / n_unlisted_universe if n_unlisted_universe else 1.0
        for k in unl:
            items.append({"item": k, "stratum": "unlisted", "N_h": n_unlisted_universe,
                          "n_h": len(unl), "pi": pi, "weight": 1.0 / pi if pi else 0.0})
        sizes["unlisted"] = n_unlisted_universe
        alloc["unlisted"] = len(unl)
    membership = {m: set(v) for m, v in top_lists.items()}
    for it in items:
        it["listed_in"] = sorted(m for m, s in membership.items() if it["item"] in s)
    return {"strata_sizes": sizes, "allocation": alloc, "items": items,
            "universe_size": universe_size, "depth": depth, "seed": seed}
