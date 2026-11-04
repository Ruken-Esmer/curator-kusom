"""MİMAR — Pre-specified statistical estimators (application §2.7)."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Callable, Hashable, Iterable, Sequence

import numpy as np

#  Inter-rater agreement

def agreement(r1: Sequence[Hashable], r2: Sequence[Hashable],
              categories: Sequence[Hashable] | None = None) -> dict[str, Any]:
    """Percent agreement, Cohen's kappa (Cohen, 1960) and Gwet's AC1 (Gwet, 2008) for two raters and q nominal…"""
    pairs = [(a, b) for a, b in zip(r1, r2) if a is not None and b is not None]
    n = len(pairs)
    if n == 0:
        return {"n": 0, "percent": None, "kappa": None, "ac1": None}
    cats = list(categories) if categories else sorted({x for p in pairs for x in p}, key=str)
    q = len(cats)
    pa = sum(a == b for a, b in pairs) / n
    c1, c2 = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe_k = sum((c1[c] / n) * (c2[c] / n) for c in cats)
    kappa = (pa - pe_k) / (1 - pe_k) if pe_k < 1 else (1.0 if pa == 1 else 0.0)
    if q > 1:
        pi = {c: (c1[c] + c2[c]) / (2 * n) for c in cats}
        pe_g = sum(p * (1 - p) for p in pi.values()) / (q - 1)
        ac1 = (pa - pe_g) / (1 - pe_g) if pe_g < 1 else 1.0
    else:
        ac1 = 1.0
    return {"n": n, "categories": [str(c) for c in cats], "percent": round(pa, 4),
            "kappa": round(kappa, 4), "ac1": round(ac1, 4)}


#  Clustered bootstrap engine

def _cluster_sums(cluster_ids: Sequence[Hashable], cols: dict[str, np.ndarray]) -> tuple[list, dict[str, np.ndarray]]:
    uniq = sorted(set(cluster_ids), key=str)
    pos = {c: i for i, c in enumerate(uniq)}
    idx = np.array([pos[c] for c in cluster_ids], dtype=int)
    sums = {k: np.bincount(idx, weights=v, minlength=len(uniq)) for k, v in cols.items()}
    return uniq, sums


def cluster_bootstrap(cluster_ids: Sequence[Hashable], cols: dict[str, Sequence[float]],
                      stat: Callable[[dict[str, np.ndarray]], np.ndarray],
                      B: int = 2000, seed: int = 20260913, alpha: float = 0.05) -> dict[str, Any]:
    """Percentile CI of ``stat`` where ``stat`` maps a dict of (B,)-arrays of resampled column totals to a (B,)…"""
    if len(cluster_ids) == 0:
        return {"lo": None, "hi": None, "B": 0, "clusters": 0}
    arr = {k: np.asarray(v, dtype=float) for k, v in cols.items()}
    uniq, sums = _cluster_sums(cluster_ids, arr)
    C = len(uniq)
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(C, np.full(C, 1.0 / C), size=B)          # B × C
    tot = {k: counts @ s for k, s in sums.items()}
    with np.errstate(divide="ignore", invalid="ignore"):
        vals = np.asarray(stat(tot), dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"lo": None, "hi": None, "B": B, "clusters": C}
    return {"lo": float(np.quantile(vals, alpha / 2)), "hi": float(np.quantile(vals, 1 - alpha / 2)),
            "B": B, "clusters": C, "valid_replicates": int(vals.size)}


def _safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


def _r(x: float | None, d: int = 4) -> float | None:
    return None if x is None else round(float(x), d)


#  AS1 — detection metrics

def as1_metrics(items: Sequence[dict[str, Any]], labels: dict[str, int | None],
                lists: dict[str, Sequence[str]], ks: Sequence[int] = (10, 25, 50)) -> dict[str, Any]:
    """Sampling-weighted sensitivity, PPV, F1 and review burden for every candidate list (equal depth)."""
    rows = [it for it in items if it["item"] in labels]
    usable = [it for it in rows if labels[it["item"]] is not None]
    insufficient = [it for it in rows if labels[it["item"]] is None]
    w = np.array([it["weight"] for it in usable], dtype=float)
    y = np.array([labels[it["item"]] for it in usable], dtype=float)
    P_w = float((w * y).sum())
    P_raw = int(y.sum())
    out: dict[str, Any] = {"n_reviewed": len(rows), "n_usable": len(usable),
                           "n_insufficient": len(insufficient),
                           "insufficient_by_stratum": dict(Counter(it["stratum"] for it in insufficient)),
                           "positives_raw": P_raw, "positives_weighted": _r(P_w, 2), "methods": {}}
    for m, lst in lists.items():
        member = set(lst)
        rank = {k: r for r, k in enumerate(lst, start=1)}
        inl = np.array([it["item"] in member for it in usable], dtype=float)
        tp_w = float((w * y * inl).sum())
        listed_w = float((w * inl).sum())
        sens = _safe_div(tp_w, P_w)
        ppv = _safe_div(tp_w, listed_w)
        f1 = (2 * sens * ppv / (sens + ppv)) if sens and ppv else (0.0 if sens is not None and ppv is not None else None)
        tp_raw = int((y * inl).sum()); listed_raw = int(inl.sum())
        prec_at = {}
        for k in ks:
            sel = np.array([rank.get(it["item"], 10 ** 9) <= k for it in usable], dtype=float)
            prec_at[str(k)] = {"ppv": _r(_safe_div(float((w * y * sel).sum()), float((w * sel).sum()))),
                               "n_reviewed": int(sel.sum())}
        out["methods"][m] = {
            "depth": len(lst),
            "sensitivity": _r(sens), "ppv": _r(ppv), "f1": _r(f1),
            "miss_rate": _r(1 - sens) if sens is not None else None,
            "tp_per_100_reviews": _r(100 * ppv, 2) if ppv is not None else None,
            "reviews_per_true_pair": _r(1 / ppv, 2) if ppv else None,
            "raw": {"tp": tp_raw, "listed_reviewed": listed_raw,
                    "sensitivity": _r(_safe_div(tp_raw, P_raw)), "ppv": _r(_safe_div(tp_raw, listed_raw))},
            "precision_at_k": prec_at,
        }
    return out


def select_comparator(dev_metrics: dict[str, Any], singles: Sequence[str] = ("bm25", "embedding", "graph")) -> dict[str, Any]:
    """§3.3: best single method on development data by weighted PPV at equal list depth; ties broken by F1, then…"""
    cands = []
    for m in singles:
        mm = dev_metrics["methods"].get(m, {})
        cands.append((-(mm.get("ppv") or 0), -(mm.get("f1") or 0), m))
    cands.sort()
    best = cands[0][2]
    return {"comparator": best, "ranking": [c[2] for c in cands],
            "rule": "max weighted PPV at equal depth; tie → F1"}


def as1_ppv_difference(items: Sequence[dict[str, Any]], labels: dict[str, int | None],
                       lists: dict[str, Sequence[str]], a: str, b: str,
                       cluster_of: Callable[[str], Hashable], B: int = 2000, seed: int = 20260913) -> dict[str, Any]:
    usable = [it for it in items if labels.get(it["item"]) is not None]
    sa, sb = set(lists[a]), set(lists[b])
    w = np.array([it["weight"] for it in usable]); y = np.array([labels[it["item"]] for it in usable], float)
    ia = np.array([it["item"] in sa for it in usable], float); ib = np.array([it["item"] in sb for it in usable], float)
    cols = {"na": w * y * ia, "da": w * ia, "nb": w * y * ib, "db": w * ib, "pos": w * y}
    est_a = _safe_div(cols["na"].sum(), cols["da"].sum()); est_b = _safe_div(cols["nb"].sum(), cols["db"].sum())
    diff = None if est_a is None or est_b is None else est_a - est_b
    ci = cluster_bootstrap([cluster_of(it["item"]) for it in usable], cols,
                           lambda t: t["na"] / t["da"] - t["nb"] / t["db"], B=B, seed=seed)
    sens_ci = cluster_bootstrap([cluster_of(it["item"]) for it in usable], cols,
                                lambda t: t["na"] / t["pos"], B=B, seed=seed + 1)
    return {"a": a, "b": b, "ppv_a": _r(est_a), "ppv_b": _r(est_b), "difference": _r(diff),
            "ci95": [_r(ci["lo"]), _r(ci["hi"])], "bootstrap": ci,
            "sensitivity_a_ci95": [_r(sens_ci["lo"]), _r(sens_ci["hi"])]}


def h1_decision(test_metrics: dict[str, Any], diff: dict[str, Any], min_positives: int,
                sens_threshold: float = 0.80) -> dict[str, Any]:
    """H1: weighted sensitivity point estimate ≥ 0.80 AND lower 95 % CI of hybrid − comparator PPV difference > 0."""
    sens = test_metrics["methods"]["hybrid"]["sensitivity"]
    lo = diff["ci95"][0]
    adequate = test_metrics["positives_raw"] >= min_positives
    c1 = sens is not None and sens >= sens_threshold
    c2 = lo is not None and lo > 0
    if not adequate:
        verdict = "inconclusive_insufficient_positives"
    else:
        verdict = "supported" if (c1 and c2) else "not_supported"
    return {"criterion_sensitivity": {"estimate": sens, "threshold": sens_threshold, "met": c1},
            "criterion_ppv_difference": {"ci95_lower": lo, "met": c2, "comparator": diff["b"]},
            "positives_raw": test_metrics["positives_raw"], "min_positives": min_positives,
            "positives_adequate": adequate, "verdict": verdict}


#  AS2a — MİMAR vs expert verified-finding rates

def delta_mu(records: Sequence[dict[str, Any]], B: int = 2000, seed: int = 20260913,
             margins: Sequence[float] = (-10.0, -5.0, -15.0), primary_margin: float = -10.0,
             insufficient_as_unverified: bool = True) -> dict[str, Any]:
    """records: {sources: {'M','U'}, verified: bool|None, weight_M, weight_U, family} ΔMU = 100·[(V_M/N_M) −…"""
    def compute(recs, label):
        m = np.array(["M" in r["sources"] for r in recs], float)
        u = np.array(["U" in r["sources"] for r in recs], float)
        v = np.array([1.0 if r["verified"] else 0.0 for r in recs])
        wm = np.array([r.get("weight_M", 1.0) for r in recs]); wu = np.array([r.get("weight_U", 1.0) for r in recs])
        cols = {"vm": wm * m * v, "nm": wm * m, "vu": wu * u * v, "nu": wu * u}
        rm = _safe_div(cols["vm"].sum(), cols["nm"].sum()); ru = _safe_div(cols["vu"].sum(), cols["nu"].sum())
        est = None if rm is None or ru is None else 100 * (rm - ru)
        ci = cluster_bootstrap([r.get("family", i) for i, r in enumerate(recs)], cols,
                               lambda t: 100 * (t["vm"] / t["nm"] - t["vu"] / t["nu"]), B=B, seed=seed)
        return {"analysis": label, "n_records": len(recs),
                "N_M": int(m.sum()), "V_M": int((m * v).sum()), "rate_M": _r(rm),
                "N_U": int(u.sum()), "V_U": int((u * v).sum()), "rate_U": _r(ru),
                "delta_pp": _r(est, 2), "ci95": [_r(ci["lo"], 2), _r(ci["hi"], 2)], "clusters": ci.get("clusters")}

    main = compute(list(records), "main: insufficient = not verified")
    sens = compute([r for r in records if r["verified"] is not None], "sensitivity: insufficient excluded")
    lo = main["ci95"][0]
    decisions = {f"{mg:+.0f}pp": (lo is not None and lo > mg) for mg in margins}
    shared = sum(1 for r in records if {"M", "U"} <= set(r["sources"]))
    return {"main": main, "sensitivity_insufficient_excluded": sens,
            "h2a": {"primary_margin_pp": primary_margin,
                    "met": lo is not None and lo > primary_margin,
                    "margin_sensitivity": decisions},
            "shared_findings": shared}


def h2b_new_share(extended: Sequence[dict[str, Any]], target: float = 0.10) -> dict[str, Any]:
    """extended: unique candidates of the MİMAR-Extended report with ``new`` (absent from the locked core…"""
    total = len(extended)
    new = [r for r in extended if r.get("new")]
    reviewed_new = [r for r in new if r.get("reviewed")]
    sampled = any(r.get("pi", 1.0) < 1.0 for r in reviewed_new)
    direct_verified = sum(1 for r in reviewed_new if r.get("verified"))
    est_total_new_verified = sum((1.0 / r.get("pi", 1.0)) for r in reviewed_new if r.get("verified"))
    share = _safe_div(est_total_new_verified, total)
    return {"total_unique_candidates": total, "new_candidates": len(new),
            "new_reviewed": len(reviewed_new), "new_verified_direct": direct_verified,
            "new_verified_estimated_total": _r(est_total_new_verified, 2),
            "share": _r(share), "target": target, "sampled": sampled,
            "met_point_estimate": share is not None and share >= target}


def power_simulation_h2a(n_per_source: int, p_true: float = 0.6, delta_true_pp: float = 0.0,
                         shared_fraction: float = 0.2, mean_family_size: float = 1.5,
                         margin_pp: float = -10.0, sims: int = 2000, seed: int = 20260913) -> dict[str, Any]:
    """Monte Carlo power for the H2a decision rule under equal (or given) true verification rates."""
    rng = np.random.default_rng(seed)
    p_m = p_true + delta_true_pp / 100.0
    p_u = p_true
    n_sh = int(round(shared_fraction * n_per_source))
    n_m = n_per_source - n_sh
    n_u = n_per_source - n_sh
    n_tot = n_m + n_u + n_sh
    n_fam = max(1, int(round(n_tot / mean_family_size)))
    rejects = 0
    covers = 0
    for _ in range(sims):
        fam = rng.integers(0, n_fam, n_tot)
        fam_eff = rng.normal(0, 0.5, n_fam)[fam]
        base = np.r_[np.full(n_m, p_m), np.full(n_u, p_u), np.full(n_sh, (p_m + p_u) / 2)]
        logit = np.log(base / (1 - base)) + fam_eff
        v = rng.random(n_tot) < 1 / (1 + np.exp(-logit))
        is_m = np.r_[np.ones(n_m), np.zeros(n_u), np.ones(n_sh)].astype(bool)
        is_u = np.r_[np.zeros(n_m), np.ones(n_u), np.ones(n_sh)].astype(bool)
        # cluster-robust (linearisation) variance of the difference of ratios
        rm = v[is_m].mean(); ru = v[is_u].mean()
        zi = (is_m * (v - rm) / is_m.sum()) - (is_u * (v - ru) / is_u.sum())
        zf = np.bincount(fam, weights=zi, minlength=n_fam)
        se = math.sqrt((zf ** 2).sum() * n_fam / max(1, n_fam - 1))
        d = 100 * (rm - ru)
        lo = d - 1.96 * 100 * se
        hi = d + 1.96 * 100 * se
        rejects += lo > margin_pp
        covers += lo <= (p_m - p_u) * 100 <= hi
    return {"n_per_source": n_per_source, "p_true": p_true, "delta_true_pp": delta_true_pp,
            "shared_fraction": shared_fraction, "mean_family_size": mean_family_size,
            "margin_pp": margin_pp, "sims": sims,
            "power": round(rejects / sims, 4), "ci_coverage": round(covers / sims, 4)}


def power_curve_h2a(ns: Iterable[int], **kw) -> list[dict[str, Any]]:
    return [power_simulation_h2a(n, **kw) for n in ns]


#  AS5 — coordinator evaluation of whole-curriculum candidates

def h5_estimate(sample: Sequence[dict[str, Any]], target: float = 0.70, min_coordinators: int = 20,
                B: int = 2000, seed: int = 20260913) -> dict[str, Any]:
    """sample: {item, stratum, weight, completed: bool, meaningful: bool|None, feasible: bool|None, coordinator}."""
    by_h: dict[str, list] = defaultdict(list)
    for s in sample:
        by_h[s["stratum"]].append(s)
    adj_rows = []
    uncovered = []
    for h, rows in by_h.items():
        done = [r for r in rows if r.get("completed")]
        if not done:
            uncovered.append(h)
            continue
        f = sum(r["weight"] for r in rows) / sum(r["weight"] for r in done)
        for r in done:
            adj_rows.append({**r, "adj_weight": r["weight"] * f})
    w = np.array([r["adj_weight"] for r in adj_rows]);
    joint = np.array([bool(r.get("meaningful")) and bool(r.get("feasible")) for r in adj_rows], float)
    mean = np.array([bool(r.get("meaningful")) for r in adj_rows], float)
    feas = np.array([bool(r.get("feasible")) for r in adj_rows], float)
    est = _safe_div(float((w * joint).sum()), float(w.sum()))
    ci = cluster_bootstrap([r.get("coordinator") for r in adj_rows], {"n": w * joint, "d": w},
                           lambda t: t["n"] / t["d"], B=B, seed=seed) if adj_rows else {"lo": None, "hi": None}
    # extreme-case bounds over the whole selected sample using design weights
    allw = np.array([s["weight"] for s in sample])
    pos_done = np.array([1.0 if (s.get("completed") and s.get("meaningful") and s.get("feasible")) else 0.0 for s in sample])
    incomplete = np.array([0.0 if s.get("completed") else 1.0 for s in sample])
    lower = _safe_div(float((allw * pos_done).sum()), float(allw.sum()))
    upper = _safe_div(float((allw * (pos_done + incomplete)).sum()), float(allw.sum()))
    coords = {r.get("coordinator") for r in adj_rows if r.get("coordinator")}
    participation_ok = len(coords) >= min_coordinators and not uncovered
    return {"n_selected": len(sample), "n_completed": len(adj_rows),
            "completion_rate": _r(len(adj_rows) / len(sample)) if sample else None,
            "coordinators": len(coords), "min_coordinators": min_coordinators,
            "strata_without_completed_reviews": uncovered,
            "joint_rate": _r(est), "ci95": [_r(ci["lo"]), _r(ci["hi"])],
            "meaningful_rate": _r(_safe_div(float((w * mean).sum()), float(w.sum()))),
            "feasible_rate": _r(_safe_div(float((w * feas).sum()), float(w.sum()))),
            "extreme_case_bounds": [_r(lower), _r(upper)], "target": target,
            "participation_condition_met": participation_ok,
            "verdict": ("descriptive_only" if not participation_ok else
                        ("target_met_point_estimate" if est is not None and est > target else "target_not_met"))}


#  AS6 — change-impact alerts

def h6_alert_metrics(scenarios: Sequence[dict[str, Any]], verified_target: float = 0.70,
                     missed_target: float = 0.20, B: int = 2000, seed: int = 20260913) -> dict[str, Any]:
    """scenarios: {id, alerts: [{verified: bool}], expected: [{reported: bool}]}"""
    ids, va, ta, me, te = [], [], [], [], []
    for s in scenarios:
        ids.append(s["id"])
        va.append(sum(1 for a in s["alerts"] if a.get("verified")))
        ta.append(len(s["alerts"]))
        me.append(sum(1 for e in s["expected"] if not e.get("reported")))
        te.append(len(s["expected"]))
    cols = {"va": va, "ta": ta, "me": me, "te": te}
    v_rate = _safe_div(sum(va), sum(ta)); m_rate = _safe_div(sum(me), sum(te))
    ci_v = cluster_bootstrap(ids, cols, lambda t: t["va"] / t["ta"], B=B, seed=seed)
    ci_m = cluster_bootstrap(ids, cols, lambda t: t["me"] / t["te"], B=B, seed=seed + 1)
    c1 = v_rate is not None and v_rate > verified_target
    c2 = m_rate is not None and m_rate < missed_target
    unmet = [n for n, ok in (("verified_alert_rate", c1), ("missed_expected_rate", c2)) if not ok]
    return {"scenarios": len(scenarios), "alerts": int(sum(ta)), "expected_effects": int(sum(te)),
            "verified_alert_rate": _r(v_rate), "verified_ci95": [_r(ci_v["lo"]), _r(ci_v["hi"])],
            "missed_expected_rate": _r(m_rate), "missed_ci95": [_r(ci_m["lo"]), _r(ci_m["hi"])],
            "targets": {"verified_gt": verified_target, "missed_lt": missed_target},
            "met": c1 and c2, "unmet_criteria": unmet}


def binomial_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Wilson interval (used for the blinding source-guess check)."""
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(c - h, 4), round(c + h, 4)
