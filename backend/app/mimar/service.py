"""Workflow service."""
from __future__ import annotations

import random
import threading
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Any

from app.mimar import metrics as M
from app.mimar.analysis import (
    HYBRID, METHODS, AnalysisConfig, LORecord, OverlapAnalysis, eligible_universe_size,
    lock_hash, pair_key, split_by_family, split_key, split_pairs, stability_check,
)
from app.mimar.findings import (
    build_blinded_pool, finding_key, generate_mimar_findings, match_findings,
    resolve_validation, ucep_correspondence,
)
from app.mimar.impact import evaluate_alerts, impact_alerts, run_controlled
from app.mimar.qc import prepare_learning_objectives, prepare_ucep
from app.mimar.sampling import allocate, build_as1_sample, stratified_sample
from app.mimar.security import IndependenceError, Role, can, hash_token, new_token
from app.mimar.store import Store, now_iso, sha256

DECISIONS_AS1 = ("overlap", "no_overlap", "insufficient")
LABEL = {"overlap": 1, "no_overlap": 0, "insufficient": None}
TRI = ("yes", "no", "insufficient")


def material_context(los: list[dict], materials: list[dict], per_lo: int = 2) -> dict[str, str]:
    """For each LO pick the ``per_lo`` most related sentences from the permitted materials of its own activity…"""
    import re
    from app.mimar.text import tokenize
    by_act: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for m in materials:
        for sent in re.split(r"(?<=[.!?])\s+", m["text"]):
            if sent.strip():
                by_act[m["activity"]].append((sent.strip(), f"{m.get('title', '')} {m.get('location', '')}".strip()))
    out: dict[str, str] = {}
    for lo in los:
        t = set(tokenize(lo["text"]))
        scored = []
        for sent, ref in by_act.get(lo["activity"], []):
            st = set(tokenize(sent))
            if not st or not t:
                continue
            j = len(t & st) / len(t | st)
            if j >= 0.9:
                continue
            scored.append((j, sent, ref))
        scored.sort(key=lambda x: (-x[0], x[1]))
        if scored:
            out[lo["uid"]] = " ".join(f"{s} [{r}]" for _, s, r in scored[:per_lo])
    return out


class NotFound(KeyError):
    pass


class ProtocolError(ValueError):
    """Raised when an operation would violate the pre-specified protocol."""


class MimarService:
    def __init__(self, store: Store):
        self.store = store
        self._cache: dict[str, OverlapAnalysis] = {}
        self._lock = threading.RLock()

    #  helpers
    def _get(self, coll: str, id: str) -> dict[str, Any]:
        d = self.store.get(coll, id)
        if d is None:
            raise NotFound(f"{coll} '{id}' not found")
        return d

    def _audit(self, user: dict | None, action: str, entity: str | None = None, **details: Any) -> None:
        self.store.audit(user["username"] if user else "system", action, entity, details)

    @staticmethod
    def _need(user: dict, capability: str) -> None:
        if not can(user.get("roles", []), capability):
            raise PermissionError(f"'{user.get('username')}' lacks capability '{capability}'")

    #  users
    def ensure_admin(self, token: str, username: str = "admin") -> dict[str, Any]:
        existing = self.store.list("user", username=username)
        if existing:
            return existing[0]
        u = self.store.put("user", {"username": username, "display_name": "Proje yöneticisi",
                                    "roles": [Role.ADMIN.value], "token_hash": hash_token(token), "active": True},
                           id=username)
        self._audit(None, "user.bootstrap_admin", username)
        return u

    def create_user(self, actor: dict, username: str, display_name: str, roles: list[str]) -> dict[str, Any]:
        self._need(actor, "users.manage")
        for r in roles:
            Role(r)
        if self.store.get("user", username):
            raise ProtocolError(f"user '{username}' already exists")
        token = new_token()
        u = self.store.put("user", {"username": username, "display_name": display_name, "roles": roles,
                                    "token_hash": hash_token(token), "active": True}, id=username)
        self._audit(actor, "user.create", username, roles=roles)
        return {**self._public_user(u), "token": token}

    def rotate_token(self, actor: dict, username: str) -> dict[str, Any]:
        self._need(actor, "users.manage")
        self._get("user", username)
        token = new_token()
        self.store.update("user", username, {"token_hash": hash_token(token)})
        self._audit(actor, "user.rotate_token", username)
        return {"username": username, "token": token}

    def authenticate(self, token: str) -> dict[str, Any] | None:
        h = hash_token(token)
        for u in self.store.list("user"):
            if u.get("token_hash") == h and u.get("active", True):
                return u
        return None

    @staticmethod
    def _public_user(u: dict) -> dict[str, Any]:
        return {k: v for k, v in u.items() if k != "token_hash"}

    def list_users(self) -> list[dict[str, Any]]:
        return [self._public_user(u) for u in self.store.list("user")]

    #  datasets, import, QC, freezing, versions
    def create_dataset(self, actor: dict, name: str, scope: str = "MSKL", version_label: str = "T0",
                       description: str = "", parent_id: str | None = None, synthetic: bool = False) -> dict:
        self._need(actor, "data.write")
        ds = self.store.put("dataset", {"name": name, "scope": scope, "version_label": version_label,
                                        "description": description, "status": "draft", "parent_id": parent_id,
                                        "synthetic": synthetic, "created_by": actor["username"],
                                        "counts": {"los": 0, "ucep": 0, "materials": 0}})
        self._audit(actor, "dataset.create", ds["id"], name=name, scope=scope, version=version_label)
        return ds

    def _draft(self, dataset_id: str) -> dict:
        ds = self._get("dataset", dataset_id)
        if ds["status"] != "draft":
            raise ProtocolError("dataset version is frozen; create a new version to change it")
        return ds

    def import_los(self, actor: dict, dataset_id: str, rows: list[dict], default_source: str = "",
                   replace: bool = True) -> dict[str, Any]:
        self._need(actor, "data.write")
        ds = self._draft(dataset_id)
        res = prepare_learning_objectives(rows, default_source)
        if replace:
            for lo in self.store.list("lo", parent=dataset_id):
                self.store.delete("lo", lo["id"])
        self.store.put_many("lo", [{**r, "id": f"{dataset_id}:{r['uid']}", "dataset_id": dataset_id}
                                   for r in res["included"]], parent=dataset_id)
        qc_hash = self.store.put_artifact("qc", {"excluded": res["excluded"], "warnings": res["warnings"],
                                                 "report": res["report"]})
        self.store.update("dataset", dataset_id, {
            "qc_report": res["report"], "qc_artifact": qc_hash,
            "counts": {**ds["counts"], "los": self.store.count("lo", parent=dataset_id)}})
        self._audit(actor, "dataset.import_los", dataset_id, included=len(res["included"]),
                    excluded=len(res["excluded"]), qc_artifact=qc_hash)
        return res["report"]

    def import_ucep(self, actor: dict, dataset_id: str, rows: list[dict]) -> dict[str, Any]:
        self._need(actor, "data.write")
        ds = self._draft(dataset_id)
        res = prepare_ucep(rows)
        for u in self.store.list("ucep", parent=dataset_id):
            self.store.delete("ucep", u["id"])
        self.store.put_many("ucep", [{**r, "id": f"{dataset_id}:{r['code']}"} for r in res["included"]],
                            parent=dataset_id)
        self.store.update("dataset", dataset_id, {"ucep_report": res["report"],
                                                  "counts": {**ds["counts"], "ucep": len(res["included"])}})
        self._audit(actor, "dataset.import_ucep", dataset_id, included=len(res["included"]))
        return res["report"]

    def import_materials(self, actor: dict, dataset_id: str, rows: list[dict]) -> dict[str, Any]:
        """KuLearn course materials for the MİMAR-Extended report (§2.4, §4.6)."""
        self._need(actor, "data.write")
        ds = self._draft(dataset_id)
        usable, unusable = [], []
        for i, r in enumerate(rows, start=1):
            rec = {"activity": str(r.get("activity", "")).strip(), "title": str(r.get("title", "")).strip(),
                   "location": str(r.get("location", "")).strip(), "text": str(r.get("text", "")).strip(),
                   "permission": str(r.get("permission", "")).strip().lower() in ("1", "true", "yes", "evet"),
                   "license": str(r.get("license", "")).strip(), "version": str(r.get("version", "")).strip()}
            reason = None
            if not rec["permission"]:
                reason = "no_documented_permission"
            elif not rec["activity"]:
                reason = "activity_unknown"
            elif not rec["text"]:
                reason = "not_processable_empty_text"
            elif not rec["version"]:
                reason = "version_unclear"
            if reason:
                unusable.append({**{k: v for k, v in rec.items() if k != "text"}, "reason": reason})
            else:
                usable.append({**rec, "id": f"{dataset_id}:M{i:05d}"})
        for m in self.store.list("material", parent=dataset_id):
            self.store.delete("material", m["id"])
        self.store.put_many("material", usable, parent=dataset_id)
        rep = {"rows": len(rows), "usable": len(usable), "unusable": len(unusable),
               "unusable_reasons": dict(Counter(u["reason"] for u in unusable)),
               "activities_with_material": len({u["activity"] for u in usable})}
        self.store.update("dataset", dataset_id, {"materials_report": rep, "materials_unusable":
                                                  self.store.put_artifact("materials_unusable", unusable),
                                                  "counts": {**ds["counts"], "materials": len(usable)}})
        self._audit(actor, "dataset.import_materials", dataset_id, **{k: v for k, v in rep.items() if k != "unusable_reasons"})
        return rep

    def _content(self, dataset_id: str) -> dict[str, Any]:
        los = sorted(self.store.list("lo", parent=dataset_id), key=lambda r: r["uid"])
        ucep = sorted(self.store.list("ucep", parent=dataset_id), key=lambda r: r["code"])
        mats = sorted(self.store.list("material", parent=dataset_id), key=lambda r: r["id"])
        strip = lambda d: {k: v for k, v in d.items() if k not in ("created_at", "id", "dataset_id", "row")}
        return {"los": [strip(x) for x in los], "ucep": [strip(x) for x in ucep], "materials": [strip(x) for x in mats]}

    def freeze_dataset(self, actor: dict, dataset_id: str) -> dict[str, Any]:
        self._need(actor, "data.freeze")
        ds = self._draft(dataset_id)
        if not ds["counts"].get("los"):
            raise ProtocolError("cannot freeze an empty dataset")
        content = self._content(dataset_id)
        h = self.store.put_artifact("dataset_snapshot", content)
        ds = self.store.update("dataset", dataset_id, {"status": "frozen", "content_hash": h,
                                                       "frozen_at": now_iso(), "frozen_by": actor["username"]})
        self._audit(actor, "dataset.freeze", dataset_id, content_hash=h)
        return ds

    def new_version(self, actor: dict, dataset_id: str, version_label: str, description: str = "") -> dict:
        """Copy a frozen dataset into a new draft version (e.g. T1)."""
        self._need(actor, "data.write")
        src = self._get("dataset", dataset_id)
        ds = self.create_dataset(actor, src["name"], src["scope"], version_label, description,
                                 parent_id=dataset_id, synthetic=src.get("synthetic", False))
        for coll in ("lo", "ucep", "material"):
            rows = self.store.list(coll, parent=dataset_id)
            key = {"lo": "uid", "ucep": "code"}.get(coll)
            self.store.put_many(coll, [{**r, "id": f"{ds['id']}:{r[key]}" if key else f"{ds['id']}:{r['id'].split(':')[-1]}",
                                        "dataset_id": ds["id"]} for r in rows], parent=ds["id"])
        counts = {"los": self.store.count("lo", ds["id"]), "ucep": self.store.count("ucep", ds["id"]),
                  "materials": self.store.count("material", ds["id"])}
        return self.store.update("dataset", ds["id"], {"counts": counts})

    def apply_changes(self, actor: dict, dataset_id: str, changes: list[dict]) -> dict[str, Any]:
        """Apply approved curriculum changes to a draft version."""
        self._need(actor, "data.write")
        self._draft(dataset_id)
        log = []
        for ch in changes:
            op, uid = ch["op"], ch["uid"]
            did = f"{dataset_id}:{uid}"
            if op == "add":
                rec = {"uid": uid, "text": ch["text"], "course": ch.get("course", ""), "session": ch.get("session", ""),
                       "activity": ch["activity"], "year": int(ch.get("year", 0)), "term": ch.get("term", ""),
                       "source": ch.get("source", "curriculum change record"), "discipline": ch.get("discipline", ""),
                       "ucep_links": ch.get("ucep_links", []), "competencies": ch.get("competencies", []),
                       "mesh": [], "dataset_id": dataset_id}
                self.store.put("lo", rec, id=did, parent=dataset_id)
            elif op == "remove":
                self._get("lo", did)
                self.store.delete("lo", did)
            elif op == "modify":
                self.store.update("lo", did, {"text": ch["text"]})
            elif op == "relink":
                self.store.update("lo", did, {k: ch[k] for k in ("ucep_links", "competencies") if k in ch})
            else:
                raise ProtocolError(f"unknown change op '{op}'")
            log.append({"op": op, "uid": uid, "decision_ref": ch.get("decision_ref", "")})
        ds = self._get("dataset", dataset_id)
        self.store.update("dataset", dataset_id, {"counts": {**ds["counts"], "los": self.store.count("lo", dataset_id)},
                                                  "change_log": ds.get("change_log", []) + log})
        self._audit(actor, "dataset.apply_changes", dataset_id, n=len(log))
        return {"applied": log}

    def list_datasets(self) -> list[dict]:
        return self.store.list("dataset")

    def dataset_detail(self, dataset_id: str) -> dict[str, Any]:
        ds = self._get("dataset", dataset_id)
        qc = self.store.get_artifact(ds["qc_artifact"]) if ds.get("qc_artifact") else None
        return {**ds, "qc_exclusions": qc["excluded"][:500] if qc else [],
                "qc_warnings": qc["warnings"][:200] if qc else []}

    def list_los(self, dataset_id: str, q: str = "", limit: int = 500) -> list[dict]:
        rows = self.store.list("lo", parent=dataset_id)
        if q:
            ql = q.lower()
            rows = [r for r in rows if ql in r["text"].lower() or ql in r["uid"].lower() or ql in r["course"].lower()]
        return sorted(rows, key=lambda r: (r["year"], r["course"], r["uid"]))[:limit]

    def los_records(self, dataset_id: str, with_materials: bool = False) -> list[LORecord]:
        rows = sorted(self.store.list("lo", parent=dataset_id), key=lambda r: r["uid"])
        ctx: dict[str, str] = {}
        if with_materials:
            ctx = material_context(rows, self.store.list("material", parent=dataset_id))
        return [LORecord(uid=r["uid"], text=r["text"], activity=r["activity"], course=r.get("course", ""),
                         year=int(r.get("year") or 0), discipline=r.get("discipline", ""), mesh=r.get("mesh", []),
                         ucep_links=r.get("ucep_links", []), competencies=r.get("competencies", []),
                         context=ctx.get(r["uid"], ""))
                for r in rows]

    def ucep_rows(self, dataset_id: str) -> list[dict]:
        return sorted(self.store.list("ucep", parent=dataset_id), key=lambda r: r["code"])

    #  configuration registry
    def create_config(self, actor: dict, name: str, params: dict | None = None) -> dict:
        self._need(actor, "analysis.run")
        cfg = AnalysisConfig.from_dict(params)
        doc = self.store.put("config", {"name": name, "params": cfg.to_dict(), "hash": cfg.hash(),
                                        "locked": False, "created_by": actor["username"]})
        self._audit(actor, "config.create", doc["id"], hash=doc["hash"])
        return doc

    def list_configs(self) -> list[dict]:
        return self.store.list("config")

    def _cfg(self, config_id: str) -> AnalysisConfig:
        return AnalysisConfig.from_dict(self._get("config", config_id)["params"])

    #  AS1: analysis run, split, stability
    def _analysis_obj(self, analysis_id: str) -> OverlapAnalysis:
        with self._lock:
            if analysis_id not in self._cache:
                run = self._get("analysis", analysis_id)
                los = self.los_records(run["dataset_id"], with_materials=run.get("with_materials", False))
                self._cache[analysis_id] = OverlapAnalysis(los, self._cfg(run["config_id"]))
            return self._cache[analysis_id]

    def run_analysis(self, actor: dict, dataset_id: str, config_id: str, with_materials: bool = False,
                     label: str = "") -> dict[str, Any]:
        self._need(actor, "analysis.run")
        ds = self._get("dataset", dataset_id)
        if ds["status"] != "frozen":
            raise ProtocolError("analyses run only on frozen dataset versions")
        cfg_doc = self._get("config", config_id)
        cfg = AnalysisConfig.from_dict(cfg_doc["params"])
        los = self.los_records(dataset_id, with_materials=with_materials)
        a = OverlapAnalysis(los, cfg)
        lists = a.method_lists()
        hybrid = a.hybrid()
        fam = a.families()
        strata = {lo.uid: lo.year for lo in los}
        split = split_by_family(fam, cfg.test_fraction, cfg.seed, strata)
        split_lock = lock_hash({"split": split, "seed": cfg.seed, "families": fam, "dataset": ds["content_hash"]})
        all_keys = {k for lst in lists.values() for k, _ in lst}
        sp = split_pairs(sorted(all_keys), split)
        art = {"methods": {m: lst for m, lst in lists.items()}, "hybrid": hybrid}
        run = self.store.put("analysis", {
            "label": label or f"{ds['name']} {ds['version_label']} · {cfg_doc['name']}",
            "dataset_id": dataset_id, "dataset_hash": ds["content_hash"], "config_id": config_id,
            "config_hash": cfg_doc["hash"], "with_materials": with_materials,
            "backend": {"embedding": a.emb.backend_used, "faiss": bool(a.emb.index is not None),
                        "concepts": len(a.graph.concepts), "related_edges": len(a.graph.related_edges)},
            "fit_seconds": round(a.fit_seconds, 3), "n_los": len(los),
            "lists_artifact": self.store.put_artifact("as1_lists", art),
            "families_artifact": self.store.put_artifact("families", fam),
            "split_artifact": self.store.put_artifact("split", split), "split_lock_hash": split_lock,
            "split_counts": {"los": dict(Counter(split.values())),
                             "listed_pairs": {k: len(v) for k, v in sp.items()},
                             "families": len(set(fam.values()))},
            "created_by": actor["username"], "status": "complete"})
        with self._lock:
            self._cache[run["id"]] = a
        self._audit(actor, "analysis.run", run["id"], dataset=dataset_id, config_hash=cfg_doc["hash"],
                    split_lock=split_lock)
        return run

    def list_analyses(self) -> list[dict]:
        return self.store.list("analysis")

    def analysis_detail(self, analysis_id: str, top: int = 100, split: str | None = None) -> dict[str, Any]:
        run = self._get("analysis", analysis_id)
        a = self._analysis_obj(analysis_id)
        allowed = self._split_universe(run, split) if split else None
        hyb = a.hybrid(allowed, depth=top)
        los = {lo.uid: lo for lo in a.los}
        rows = []
        for h in hyb:
            x, y = split_key(h["pair"])
            rows.append({**h, "a": {"uid": x, "text": los[x].text, "course": los[x].course, "year": los[x].year},
                         "b": {"uid": y, "text": los[y].text, "course": los[y].course, "year": los[y].year},
                         "evidence": a.evidence(h["pair"])})
        return {"analysis": run, "top": rows}

    def _split(self, run: dict) -> dict[str, str]:
        return self.store.get_artifact(run["split_artifact"])

    def _families(self, run: dict) -> dict[str, str]:
        return self.store.get_artifact(run["families_artifact"])

    def _split_universe(self, run: dict, part: str) -> set[str]:
        a = self._analysis_obj(run["id"])
        split = self._split(run)
        keys = {k for lst in a.method_lists().values() for k, _ in lst}
        return split_pairs(sorted(keys), split)[part]

    def stability(self, actor: dict, analysis_id: str, runs: int = 5, top: int = 20) -> dict[str, Any]:
        self._need(actor, "analysis.run")
        run = self._get("analysis", analysis_id)
        res = stability_check(self.los_records(run["dataset_id"], run.get("with_materials", False)),
                              self._cfg(run["config_id"]), runs=runs, top=top)
        self.store.update("analysis", analysis_id, {"stability": res})
        self._audit(actor, "analysis.stability", analysis_id, min_overlap=res["min_overlap"],
                    meets=res["meets_criterion"])
        return res

    def concept_graph(self, analysis_id: str, limit: int = 200) -> dict[str, Any]:
        a = self._analysis_obj(analysis_id)
        g = a.graph
        deg = Counter(c for cs in g.lo_concepts for c in cs)
        top = [c for c, _ in deg.most_common(limit)]
        ts = set(top)
        edges = [{"source": x, "target": y, "weight": w} for x, y, w in g.related_edges if x in ts and y in ts]
        return {"nodes": [{"id": c, "degree": deg[c]} for c in top], "edges": edges,
                "totals": {"concepts": len(g.concepts), "related_edges": len(g.related_edges)}}

    def neo4j_cypher(self, analysis_id: str) -> str:
        """Cypher script that materialises the LO–Concept graph in Neo4j…"""
        a = self._analysis_obj(analysis_id)
        esc = lambda s: s.replace("\\", "\\\\").replace("'", "\\'")
        lines = ["CREATE CONSTRAINT lo_uid IF NOT EXISTS FOR (l:LearningObjective) REQUIRE l.uid IS UNIQUE;",
                 "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE;"]
        for lo, cs in zip(a.los, a.graph.lo_concepts):
            lines.append(f"MERGE (l:LearningObjective {{uid:'{esc(lo.uid)}'}}) SET l.year={lo.year}, "
                         f"l.course='{esc(lo.course)}', l.activity='{esc(lo.activity)}';")
            for c in sorted(cs):
                lines.append(f"MATCH (l:LearningObjective {{uid:'{esc(lo.uid)}'}}) MERGE (c:Concept {{name:'{esc(c)}'}}) "
                             f"MERGE (l)-[:MENTIONS]->(c);")
        for x, y, w in a.graph.related_edges:
            lines.append(f"MATCH (a:Concept {{name:'{esc(x)}'}}),(b:Concept {{name:'{esc(y)}'}}) "
                         f"MERGE (a)-[r:RELATED_TO]-(b) SET r.cooccurrence={w};")
        return "\n".join(lines)

    #  analysis plan (pre-registration)
    def create_plan(self, actor: dict, analysis_id: str, params: dict | None = None) -> dict[str, Any]:
        self._need(actor, "plan.lock")
        run = self._get("analysis", analysis_id)
        cfg = self._cfg(run["config_id"])
        p = {"depth_per_lo": cfg.list_depth / max(1, run["n_los"]), "dev_n": 300, "test_n": 1000,
             "test_n_if_rare": 1500, "rare_threshold": 0.02, "unlisted_fraction": 0.2, "min_per_stratum": 10,
             "min_positives": 30, "sens_threshold": 0.80, "ac1_threshold": 0.60, "bootstrap_B": 2000,
             "seed": cfg.seed, **(params or {})}
        split = self._split(run)
        n_dev = sum(v == "dev" for v in split.values()); n_test = sum(v == "test" for v in split.values())
        p["depth_dev"] = max(5, round(p["depth_per_lo"] * n_dev))
        p["depth_test"] = max(5, round(p["depth_per_lo"] * n_test))
        plan = self.store.put("plan", {"analysis_id": analysis_id, "params": p, "comparator": None,
                                       "locked": False, "created_by": actor["username"]})
        self.store.update("analysis", analysis_id, {"plan_id": plan["id"]})
        self._audit(actor, "plan.create", plan["id"], analysis=analysis_id)
        return plan

    def update_plan(self, actor: dict, plan_id: str, params: dict) -> dict:
        self._need(actor, "plan.lock")
        plan = self._get("plan", plan_id)
        if plan["locked"]:
            raise ProtocolError("plan is locked")
        return self.store.update("plan", plan_id, {"params": {**plan["params"], **params}})

    def lock_plan(self, actor: dict, plan_id: str) -> dict:
        self._need(actor, "plan.lock")
        plan = self._get("plan", plan_id)
        if plan["locked"]:
            raise ProtocolError("plan already locked")
        if not plan.get("comparator"):
            raise ProtocolError("select the single-method comparator on development data before locking")
        run = self._get("analysis", plan["analysis_id"])
        payload = {"params": plan["params"], "comparator": plan["comparator"], "config_hash": run["config_hash"],
                   "dataset_hash": run["dataset_hash"], "split_lock_hash": run["split_lock_hash"]}
        h = lock_hash(payload)
        plan = self.store.update("plan", plan_id, {"locked": True, "lock_hash": h, "locked_at": now_iso(),
                                                   "locked_by": actor["username"]})
        self.store.update("config", run["config_id"], {"locked": True})
        self._audit(actor, "plan.lock", plan_id, lock_hash=h, comparator=plan["comparator"])
        return plan

    #  AS1 samples, blinded review, adjudication
    def create_as1_sample(self, actor: dict, analysis_id: str, part: str, n: int | None = None) -> dict:
        self._need(actor, "sample.create")
        if part not in ("dev", "test"):
            raise ProtocolError("part must be 'dev' or 'test'")
        run = self._get("analysis", analysis_id)
        plan = self._get("plan", run.get("plan_id") or "") if run.get("plan_id") else None
        if plan is None:
            raise ProtocolError("create the analysis plan first")
        p = plan["params"]
        if part == "test":
            if not plan["locked"]:
                raise ProtocolError("the locked test cannot be opened before the analysis plan is locked")
            if self.store.list("sample", analysis_id=analysis_id, part="test"):
                raise ProtocolError("test sample already drawn")
        a = self._analysis_obj(analysis_id)
        split = self._split(run)
        depth = p["depth_test"] if part == "test" else p["depth_dev"]
        universe = self._split_universe(run, part)
        top = a.top_lists(universe, depth)
        uids = [u for u, s in split.items() if s == part]
        activity = {lo.uid: lo.activity for lo in a.los}
        usize = eligible_universe_size(a.los, set(uids))
        if n is None:
            if part == "dev":
                n = p["dev_n"]
            else:
                dev_rate = None
                for s in self.store.list("sample", analysis_id=analysis_id, part="dev"):
                    lab = self.final_labels(s["id"])["labels"]
                    vals = [v for v in lab.values() if v is not None]
                    dev_rate = (sum(vals) / len(vals)) if vals else None
                n = p["test_n_if_rare"] if dev_rate is not None and dev_rate < p["rare_threshold"] else p["test_n"]
        exclude: set[str] = set()
        design = build_as1_sample(top, depth, uids, activity, usize, n, p["unlisted_fraction"],
                                  p["min_per_stratum"], seed=p["seed"] + (1 if part == "test" else 0), exclude=exclude)
        art = self.store.put_artifact("as1_sample", {**design, "lists": top})
        s = self.store.put("sample", {"analysis_id": analysis_id, "part": part, "kind": "as1", "n": len(design["items"]),
                                      "depth": depth, "design": {k: v for k, v in design.items() if k != "items"},
                                      "items_artifact": art, "created_by": actor["username"],
                                      "reviewers": [], "adjudicator": None, "status": "open"})
        self._audit(actor, "sample.create", s["id"], part=part, n=len(design["items"]), artifact=art)
        return s

    def _sample_items(self, sample: dict) -> dict[str, Any]:
        return self.store.get_artifact(sample["items_artifact"])

    def _independence_check(self, sample: dict, user_id: str) -> None:
        if user_id == sample["created_by"]:
            raise IndependenceError("the person who selected the pairs cannot review them")

    def assign_reviewers(self, actor: dict, sample_id: str, reviewers: list[str], adjudicator: str | None) -> dict:
        self._need(actor, "sample.create")
        s = self._get("sample", sample_id)
        if len(set(reviewers)) != 2:
            raise ProtocolError("exactly two independent primary reviewers are required")
        for r in reviewers:
            self._independence_check(s, r)
            if Role.REVIEWER.value not in self._get("user", r)["roles"]:
                raise ProtocolError(f"'{r}' does not hold the reviewer role")
        if adjudicator:
            if adjudicator in reviewers:
                raise IndependenceError("the adjudicator must be a third person")
            self._independence_check(s, adjudicator)
        items = [it["item"] for it in self._sample_items(s)["items"]]
        orders = {}
        for r in reviewers:
            rng = random.Random(f"{sample_id}|{r}")
            order = items[:]
            rng.shuffle(order)
            orders[r] = order
        codes = {it: f"P{n:04d}" for n, it in enumerate(sorted(items, key=lambda k: sha256([sample_id, k])), start=1)}
        s = self.store.update("sample", sample_id, {"reviewers": reviewers, "adjudicator": adjudicator,
                                                    "orders": orders, "codes": codes})
        self._audit(actor, "sample.assign", sample_id, reviewers=reviewers, adjudicator=adjudicator)
        return {k: v for k, v in s.items() if k not in ("orders", "codes")}

    def review_queue(self, user: dict, sample_id: str) -> dict[str, Any]:
        """Blinded queue: only the two LO texts."""
        s = self._get("sample", sample_id)
        if user["username"] not in s.get("reviewers", []):
            raise PermissionError("not assigned to this sample")
        a = self._analysis_obj(s["analysis_id"])
        texts = {lo.uid: lo.text for lo in a.los}
        mine = {d["item"]: d for d in self.store.list("decision", parent=sample_id, reviewer=user["username"])}
        out = []
        for k in s["orders"][user["username"]]:
            x, y = split_key(k)
            d = mine.get(k)
            out.append({"code": s["codes"][k], "text_a": texts[x], "text_b": texts[y],
                        "decision": d["value"] if d else None, "rationale": d.get("rationale", "") if d else ""})
        locked = any(d.get("locked") for d in mine.values())
        return {"sample_id": sample_id, "total": len(out), "done": sum(1 for o in out if o["decision"]),
                "locked": locked, "items": out, "choices": list(DECISIONS_AS1)}

    def _code_to_item(self, s: dict, code: str) -> str:
        inv = {v: k for k, v in s["codes"].items()}
        if code not in inv:
            raise NotFound(f"item code {code}")
        return inv[code]

    def decide(self, user: dict, sample_id: str, code: str, value: str, rationale: str = "") -> dict:
        self._need(user, "review.decide")
        s = self._get("sample", sample_id)
        if user["username"] not in s.get("reviewers", []):
            raise PermissionError("not assigned to this sample")
        if value not in DECISIONS_AS1:
            raise ProtocolError(f"decision must be one of {DECISIONS_AS1}")
        item = self._code_to_item(s, code)
        did = f"{sample_id}:{user['username']}:{item}"
        old = self.store.get("decision", did)
        if old and old.get("locked"):
            raise ProtocolError("decisions are locked")
        d = self.store.put("decision", {"sample_id": sample_id, "reviewer": user["username"], "item": item,
                                        "code": code, "value": value, "rationale": rationale, "locked": False},
                           id=did, parent=sample_id)
        return {"code": code, "value": d["value"]}

    def lock_decisions(self, user: dict, sample_id: str) -> dict:
        s = self._get("sample", sample_id)
        mine = self.store.list("decision", parent=sample_id, reviewer=user["username"])
        total = len(self._sample_items(s)["items"])
        if len(mine) < total:
            raise ProtocolError(f"{total - len(mine)} items still undecided")
        ts = now_iso()
        for d in mine:
            self.store.update("decision", d["id"], {"locked": True, "locked_at": ts})
        h = sha256(sorted((d["item"], d["value"]) for d in mine))
        self._audit(user, "review.lock", sample_id, n=len(mine), decisions_hash=h)
        return {"locked": len(mine), "hash": h, "locked_at": ts}

    def conflicts(self, sample_id: str) -> list[dict[str, Any]]:
        s = self._get("sample", sample_id)
        by_item: dict[str, dict[str, str]] = defaultdict(dict)
        for d in self.store.list("decision", parent=sample_id):
            if d.get("locked"):
                by_item[d["item"]][d["reviewer"]] = d["value"]
        out = []
        for item, ds in by_item.items():
            if len(ds) == 2 and len(set(ds.values())) > 1:
                out.append({"item": item, "code": s["codes"][item]})
        return sorted(out, key=lambda x: x["code"])

    def adjudication_queue(self, user: dict, sample_id: str) -> dict[str, Any]:
        s = self._get("sample", sample_id)
        if user["username"] != s.get("adjudicator"):
            raise PermissionError("not the adjudicator of this sample")
        a = self._analysis_obj(s["analysis_id"])
        texts = {lo.uid: lo.text for lo in a.los}
        adj = {x["item"]: x for x in self.store.list("adjudication", parent=sample_id)}
        items = []
        for c in self.conflicts(sample_id):
            x, y = split_key(c["item"])
            items.append({"code": c["code"], "text_a": texts[x], "text_b": texts[y],
                          "decision": adj.get(c["item"], {}).get("value")})
        return {"sample_id": sample_id, "items": items, "choices": list(DECISIONS_AS1)}

    def adjudicate(self, user: dict, sample_id: str, code: str, value: str, rationale: str = "") -> dict:
        self._need(user, "review.adjudicate")
        s = self._get("sample", sample_id)
        if user["username"] != s.get("adjudicator"):
            raise PermissionError("not the adjudicator of this sample")
        if value not in DECISIONS_AS1:
            raise ProtocolError("invalid decision")
        item = self._code_to_item(s, code)
        if item not in {c["item"] for c in self.conflicts(sample_id)}:
            raise ProtocolError("only disagreements are adjudicated; initial decisions are preserved")
        self.store.put("adjudication", {"sample_id": sample_id, "item": item, "code": code, "value": value,
                                        "rationale": rationale, "adjudicator": user["username"]},
                       id=f"{sample_id}:{item}", parent=sample_id)
        self._audit(user, "review.adjudicate", sample_id, code=code)
        return {"code": code, "value": value}

    def final_labels(self, sample_id: str) -> dict[str, Any]:
        s = self._get("sample", sample_id)
        by_item: dict[str, dict[str, str]] = defaultdict(dict)
        for d in self.store.list("decision", parent=sample_id):
            if d.get("locked"):
                by_item[d["item"]][d["reviewer"]] = d["value"]
        adj = {x["item"]: x["value"] for x in self.store.list("adjudication", parent=sample_id)}
        labels, pending = {}, []
        for item, ds in by_item.items():
            if len(ds) < 2:
                pending.append(item)
                continue
            vals = set(ds.values())
            if len(vals) == 1:
                labels[item] = LABEL[vals.pop()]
            elif item in adj:
                labels[item] = LABEL[adj[item]]
            else:
                pending.append(item)
        revs = s.get("reviewers", [])
        r1 = [by_item[i].get(revs[0]) if revs else None for i in sorted(by_item)]
        r2 = [by_item[i].get(revs[1]) if len(revs) > 1 else None for i in sorted(by_item)]
        agr = M.agreement(r1, r2, DECISIONS_AS1)
        return {"labels": labels, "pending": pending, "agreement_initial": agr}

    #  AS1 evaluation
    def _pair_cluster(self, run: dict):
        fam = self._families(run)
        def cl(k: str):
            a, b = split_key(k)
            return tuple(sorted((fam.get(a, a), fam.get(b, b))))
        return cl

    def evaluate_sample(self, actor: dict, sample_id: str) -> dict[str, Any]:
        self._need(actor, "metrics.read")
        s = self._get("sample", sample_id)
        run = self._get("analysis", s["analysis_id"])
        plan = self._get("plan", run["plan_id"])
        p = plan["params"]
        art = self._sample_items(s)
        fl = self.final_labels(sample_id)
        if fl["pending"]:
            raise ProtocolError(f"{len(fl['pending'])} items lack final labels (missing locks or adjudication)")
        lists = art["lists"]
        met = M.as1_metrics(art["items"], fl["labels"], lists)
        ac1 = fl["agreement_initial"]["ac1"]
        res: dict[str, Any] = {"sample_id": sample_id, "part": s["part"], "metrics": met,
                               "agreement_initial": fl["agreement_initial"],
                               "recalibration_required": ac1 is not None and ac1 < p["ac1_threshold"]}
        if s["part"] == "dev":
            # §3.3: list depth and comparator are selected on development data only.
            grid = sorted({max(5, round(s["depth"] * f)) for f in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)})
            table = []
            for d in grid:
                md = M.as1_metrics(art["items"], fl["labels"], {m: l[:d] for m, l in lists.items()})
                table.append({"depth": d, **{m: {k: md["methods"][m][k] for k in ("sensitivity", "ppv", "f1")}
                                             for m in md["methods"]}})
            best = max(table, key=lambda r: ((r[HYBRID]["f1"] or 0), -r["depth"]))
            met_best = M.as1_metrics(art["items"], fl["labels"], {m: l[:best["depth"]] for m, l in lists.items()})
            comp = M.select_comparator(met_best)
            res["depth_selection"] = {"grid": table, "selected_depth_dev": best["depth"],
                                      "rule": "max hybrid weighted F1 on development sample; tie → smaller depth"}
            res["metrics_at_selected_depth"] = met_best
            res["comparator_selection"] = comp
            if not plan["locked"]:
                split = self._split(run)
                n_dev = sum(v == "dev" for v in split.values()); n_test = sum(v == "test" for v in split.values())
                dpl = best["depth"] / max(1, n_dev)
                self.store.update("plan", plan["id"], {
                    "comparator": comp["comparator"], "dev_sample": sample_id, "dev_metrics_hash": sha256(met_best),
                    "params": {**p, "depth_per_lo": dpl, "depth_selected_dev": best["depth"],
                               "depth_test": max(5, round(dpl * n_test))}})
        else:
            if not plan["locked"]:
                raise ProtocolError("plan must be locked before test evaluation")
            diff = M.as1_ppv_difference(art["items"], fl["labels"], lists, HYBRID, plan["comparator"],
                                        self._pair_cluster(run), B=p["bootstrap_B"], seed=p["seed"])
            res["ppv_difference"] = diff
            res["h1"] = M.h1_decision(met, diff, p["min_positives"], p["sens_threshold"])
            res["plan_lock_hash"] = plan["lock_hash"]
        self.store.update("sample", sample_id, {"evaluation": res, "status": "evaluated"})
        self._audit(actor, "as1.evaluate", sample_id, part=s["part"],
                    verdict=res.get("h1", {}).get("verdict"))
        return res

    def list_samples(self, analysis_id: str | None = None) -> list[dict]:
        rows = self.store.list("sample")
        if analysis_id:
            rows = [r for r in rows if r.get("analysis_id") == analysis_id]
        return [{k: v for k, v in r.items() if k not in ("orders", "codes")} for r in rows]

    def sample_progress(self, sample_id: str) -> dict[str, Any]:
        s = self._get("sample", sample_id)
        total = s["n"]
        per = {}
        for r in s.get("reviewers", []):
            ds = self.store.list("decision", parent=sample_id, reviewer=r)
            per[r] = {"decided": len(ds), "locked": all(d.get("locked") for d in ds) and len(ds) == total}
        conf = self.conflicts(sample_id) if all(v["locked"] for v in per.values()) and per else []
        adj = self.store.count("adjudication", sample_id)
        return {"sample_id": sample_id, "total": total, "reviewers": per, "conflicts": len(conf),
                "adjudicated": adj, "evaluation": s.get("evaluation")}

    #  AS2: reports, findings, pools, validation
    def generate_mimar_report(self, actor: dict, analysis_id: str, kind: str = "core", depth: int | None = None) -> dict:
        self._need(actor, "report.mimar")
        run = self._get("analysis", analysis_id)
        a = self._analysis_obj(analysis_id)
        ucep = self.ucep_rows(run["dataset_id"])
        umap = ucep_correspondence(a, ucep)
        if depth is None:
            base_run = run
            if run.get("with_materials"):   # extended reports reuse the core run's locked operating point
                base_run = next((r for r in self.store.list("analysis", dataset_id=run["dataset_id"])
                                 if r.get("plan_id") and not r.get("with_materials")), run)
            plan = self.store.get("plan", base_run.get("plan_id") or "") if base_run.get("plan_id") else None
            depth = round(plan["params"]["depth_per_lo"] * len(a.los)) if plan and plan.get("locked") else a.cfg.list_depth
        gen = generate_mimar_findings(a, umap, depth=depth)
        src = {"core": "mimar_core", "extended": "mimar_extended"}[kind]
        rep = self.store.put("report", {"source": src, "dataset_id": run["dataset_id"], "analysis_id": analysis_id,
                                        "config_hash": run["config_hash"], "locked": False,
                                        "created_by": actor["username"], "authors": [actor["username"]],
                                        "counts": gen["counts"], "n_findings": len(gen["findings"]), "depth": depth,
                                        "spiral_progressions": len(gen["spiral_progressions"]),
                                        "ucep_artifact": self.store.put_artifact("ucep_map", umap),
                                        "spiral_artifact": self.store.put_artifact("spiral", gen["spiral_progressions"])})
        self.store.put_many("finding", [{**f, "id": f"{rep['id']}:{f['key']}", "report_id": rep["id"]}
                                        for f in gen["findings"]], parent=rep["id"])
        self._audit(actor, "report.generate", rep["id"], kind=kind, n=len(gen["findings"]))
        return rep

    def import_expert_report(self, actor: dict, dataset_id: str, rows: list[dict], authors: list[str] | None = None,
                             label: str = "Expert–Core") -> dict:
        self._need(actor, "report.expert")
        self._get("dataset", dataset_id)
        rep = self.store.put("report", {"source": "expert_core", "label": label, "dataset_id": dataset_id,
                                        "locked": False, "created_by": actor["username"],
                                        "authors": sorted(set((authors or []) + [actor["username"]]))})
        los = {r["uid"]: r for r in self.store.list("lo", parent=dataset_id)}
        fs = []
        for r in rows:
            cat = r.get("category", "")
            if cat not in ("redundancy", "gap_ucep", "integration"):
                raise ProtocolError(f"unknown category '{cat}'")
            lo_ids = r.get("los", []) if isinstance(r.get("los"), list) else [x.strip() for x in str(r.get("los", "")).split(";") if x.strip()]
            uc = r.get("ucep", []) if isinstance(r.get("ucep"), list) else [x.strip() for x in str(r.get("ucep", "")).split(";") if x.strip()]
            key = finding_key(cat, lo_ids, uc)
            fs.append({"id": f"{rep['id']}:{key}", "report_id": rep["id"], "key": key, "category": cat,
                       "items": {"los": sorted(lo_ids), "ucep": sorted(uc)}, "statement": r.get("statement", ""),
                       "support": [{"lo": u, "course": los.get(u, {}).get("course", ""), "year": los.get(u, {}).get("year", 0),
                                    "text": los.get(u, {}).get("text", "")} for u in lo_ids] + [{"ucep": c} for c in uc],
                       "rationale": r.get("rationale", "")})
        uniq = {f["key"]: f for f in fs}
        self.store.put_many("finding", list(uniq.values()), parent=rep["id"])
        rep = self.store.update("report", rep["id"], {"n_findings": len(uniq),
                                                      "counts": dict(Counter(f["category"] for f in uniq.values()))})
        self._audit(actor, "report.expert_import", rep["id"], n=len(uniq))
        return rep

    def lock_report(self, actor: dict, report_id: str) -> dict:
        rep = self._get("report", report_id)
        if actor["username"] not in rep.get("authors", []) and Role.ADMIN.value not in actor["roles"]:
            raise PermissionError("only authors or the administrator can lock a report")
        if rep["locked"]:
            raise ProtocolError("report already locked")
        fs = self.store.list("finding", parent=report_id)
        h = sha256(sorted((f["key"], f["category"], f["statement"]) for f in fs))
        rep = self.store.update("report", report_id, {"locked": True, "lock_hash": h, "locked_at": now_iso()})
        self._audit(actor, "report.lock", report_id, hash=h)
        return rep

    def list_reports(self) -> list[dict]:
        return self.store.list("report")

    def report_findings(self, user: dict, report_id: str) -> dict[str, Any]:
        rep = self._get("report", report_id)
        # independence: validators must not see source reports before pool validation is final
        if Role.VALIDATOR.value in user["roles"] and not can(user["roles"], "report.mimar"):
            raise PermissionError("validators see only the blinded pool")
        fs = self.store.list("finding", parent=report_id)
        out = {"report": rep, "findings": fs}
        if rep.get("ucep_artifact"):
            out["ucep_map"] = self.store.get_artifact(rep["ucep_artifact"])
        if rep.get("spiral_artifact"):
            out["spiral_progressions"] = self.store.get_artifact(rep["spiral_artifact"])
        return out

    def propose_matches(self, actor: dict, mimar_report: str, expert_report: str) -> dict[str, Any]:
        self._need(actor, "pool.standardize")
        m = self.store.list("finding", parent=mimar_report)
        e = self.store.list("finding", parent=expert_report)
        return match_findings(m, e)

    def build_pool(self, actor: dict, reports: dict[str, str], confirmed_matches: list[dict] | None = None,
                   purpose: str = "as2a", seed: int = 20260913) -> dict:
        """reports: {"M": report_id, "U": report_id} for AS2a, or {"E": report_id} (new extended findings) for AS2b."""
        self._need(actor, "pool.standardize")
        authors: set[str] = set()
        fsets: dict[str, list[dict]] = {}
        for src, rid in reports.items():
            rep = self._get("report", rid)
            if not rep["locked"]:
                raise ProtocolError(f"report {rid} must be locked before standardisation")
            authors |= set(rep.get("authors", []))
            fsets[src] = self.store.list("finding", parent=rid)
        if actor["username"] in authors:
            raise IndependenceError("report authors cannot standardise")
        if purpose == "as2b":
            core_id, ext_id = reports.get("C"), reports.get("E")
            if not core_id or not ext_id:
                raise ProtocolError("AS2b pools need {'C': core report, 'E': extended report}")
            core_keys = {f["key"] for f in fsets["C"]}
            fsets = {"E": [f for f in fsets["E"] if f["key"] not in core_keys]}
        pool = build_blinded_pool(fsets, confirmed_matches or [], seed)
        doc = self.store.put("pool", {"purpose": purpose, "reports": reports, "n_entries": len(pool["entries"]),
                                      "entries_artifact": self.store.put_artifact("pool_entries", pool["entries"]),
                                      "seal_artifact": self.store.put_artifact("pool_seal", pool["seal"]),
                                      "sealed": True, "report_authors": sorted(authors),
                                      "standardizer": actor["username"], "validators": [], "adjudicator": None,
                                      "created_by": actor["username"]})
        self._audit(actor, "pool.build", doc["id"], purpose=purpose, n=len(pool["entries"]))
        return doc

    def assign_validators(self, actor: dict, pool_id: str, validators: list[str], adjudicator: str | None) -> dict:
        self._need(actor, "users.manage")
        pool = self._get("pool", pool_id)
        banned = set(pool["report_authors"]) | {pool["standardizer"]}
        for v in validators + ([adjudicator] if adjudicator else []):
            if v in banned:
                raise IndependenceError(f"'{v}' prepared or standardised the reports and cannot validate")
        if len(set(validators)) != 2:
            raise ProtocolError("two primary validators are required")
        if adjudicator in validators:
            raise IndependenceError("adjudicator must be a third person")
        doc = self.store.update("pool", pool_id, {"validators": validators, "adjudicator": adjudicator})
        self._audit(actor, "pool.assign", pool_id, validators=validators, adjudicator=adjudicator)
        return doc

    def pool_entries(self, user: dict, pool_id: str) -> dict[str, Any]:
        pool = self._get("pool", pool_id)
        allowed = set(pool["validators"]) | {pool.get("adjudicator")} | {pool["standardizer"]}
        if user["username"] not in allowed and Role.ADMIN.value not in user["roles"]:
            raise PermissionError("not a member of this pool")
        entries = self.store.get_artifact(pool["entries_artifact"])
        mine = {d["code"]: d for d in self.store.list("validation", parent=pool_id, validator_id=user["username"])}
        for e in entries:
            e.pop("family", None)
            if e["code"] in mine:
                e["my_decision"] = {k: mine[e["code"]].get(k) for k in ("support", "meaningful", "category_ok",
                                                                         "suggested_category", "rationale", "locked")}
        return {"pool": {k: v for k, v in pool.items() if k not in ("seal_artifact",)}, "entries": entries}

    def validate(self, user: dict, pool_id: str, code: str, support: str, meaningful: str, category_ok: str,
                 suggested_category: str = "", rationale: str = "") -> dict:
        self._need(user, "validation.decide")
        pool = self._get("pool", pool_id)
        if user["username"] not in pool["validators"]:
            raise PermissionError("not a validator of this pool")
        if support not in TRI or meaningful not in TRI or category_ok not in ("yes", "no"):
            raise ProtocolError("invalid decision values")
        if category_ok == "no" and not suggested_category:
            raise ProtocolError("suggest the appropriate category when the category is not appropriate")
        did = f"{pool_id}:{user['username']}:{code}"
        old = self.store.get("validation", did)
        if old and old.get("locked"):
            raise ProtocolError("decisions are locked")
        self.store.put("validation", {"pool_id": pool_id, "code": code, "validator_id": user["username"],
                                      "support": support, "meaningful": meaningful, "category_ok": category_ok,
                                      "suggested_category": suggested_category, "rationale": rationale,
                                      "locked": False}, id=did, parent=pool_id)
        return {"code": code}

    def lock_validations(self, user: dict, pool_id: str) -> dict:
        pool = self._get("pool", pool_id)
        mine = self.store.list("validation", parent=pool_id, validator_id=user["username"])
        if len(mine) < pool["n_entries"]:
            raise ProtocolError(f"{pool['n_entries'] - len(mine)} entries still undecided")
        for d in mine:
            self.store.update("validation", d["id"], {"locked": True})
        self._audit(user, "validation.lock", pool_id, n=len(mine))
        return {"locked": len(mine)}

    def _pool_resolution(self, pool_id: str) -> dict[str, Any]:
        locked = [d for d in self.store.list("validation", parent=pool_id) if d.get("locked")]
        adj = self.store.list("validation_adj", parent=pool_id)
        return resolve_validation(locked, adj)

    def validation_adjudicate(self, user: dict, pool_id: str, code: str, decision: dict) -> dict:
        self._need(user, "validation.adjudicate")
        pool = self._get("pool", pool_id)
        if user["username"] != pool.get("adjudicator"):
            raise PermissionError("not the adjudicator of this pool")
        conf = {c["code"]: c["dimensions"] for c in self._pool_resolution(pool_id)["conflicts"]}
        if code not in conf:
            raise ProtocolError("only disagreements are adjudicated")
        rec = {"pool_id": pool_id, "code": code, "adjudicator": user["username"],
               **{d: decision[d] for d in conf[code]}}
        self.store.put("validation_adj", rec, id=f"{pool_id}:{code}", parent=pool_id)
        self._audit(user, "validation.adjudicate", pool_id, code=code)
        return rec

    def pool_status(self, pool_id: str) -> dict[str, Any]:
        pool = self._get("pool", pool_id)
        res = self._pool_resolution(pool_id)
        locked = [d for d in self.store.list("validation", parent=pool_id) if d.get("locked")]
        vals = pool["validators"]
        agr = {}
        if len(vals) == 2:
            by = defaultdict(dict)
            for d in locked:
                by[d["code"]][d["validator_id"]] = d
            codes = sorted(c for c in by if len(by[c]) == 2)
            for dim, cats in (("support", TRI), ("meaningful", TRI), ("category_ok", ("yes", "no"))):
                agr[dim] = M.agreement([by[c][vals[0]][dim] for c in codes], [by[c][vals[1]][dim] for c in codes], cats)
            fin = res["final"]
            def ver(d):
                return "insufficient" if "insufficient" in (d["support"], d["meaningful"]) else \
                    ("yes" if d["support"] == "yes" and d["meaningful"] == "yes" and d["category_ok"] == "yes" else "no")
            agr["final_verification"] = M.agreement([ver(by[c][vals[0]]) for c in codes],
                                                    [ver(by[c][vals[1]]) for c in codes], TRI)
        finals = [v for v in res["final"].values() if v.get("status") == "final"]
        ac1 = agr.get("final_verification", {}).get("ac1")
        return {"pool_id": pool_id, "entries": pool["n_entries"], "final": len(finals),
                "conflicts": res["conflicts"], "agreement": agr,
                "quality_threshold_met": None if ac1 is None else ac1 >= 0.60,
                "complete": len(finals) == pool["n_entries"]}

    def as2a_results(self, actor: dict, pool_id: str, B: int = 2000) -> dict[str, Any]:
        self._need(actor, "pool.unseal")
        pool = self._get("pool", pool_id)
        st = self.pool_status(pool_id)
        if not st["complete"]:
            raise ProtocolError("the seal is opened only after all validation decisions are final")
        seal = self.store.get_artifact(pool["seal_artifact"])
        entries = {e["code"]: e for e in self.store.get_artifact(pool["entries_artifact"])}
        final = self._pool_resolution(pool_id)["final"]
        records = [{"code": c, "sources": seal[c]["sources"], "verified": final[c]["verified"],
                    "family": entries[c]["family"], "category": entries[c]["category"]} for c in seal]
        res = M.delta_mu(records, B=B)
        by_cat = {}
        for cat in ("redundancy", "gap_ucep", "integration"):
            sub = [r for r in records if r["category"] == cat]
            by_cat[cat] = {"M_unique": sum(1 for r in sub if r["sources"] == ["M"]),
                           "U_unique": sum(1 for r in sub if r["sources"] == ["U"]),
                           "shared": sum(1 for r in sub if len(r["sources"]) == 2),
                           "verified": sum(1 for r in sub if r["verified"])}
        guesses = self.store.list("source_guess", parent=pool_id)
        g_ok = sum(1 for g in guesses if g["guess"] in seal.get(g["code"], {}).get("sources", []))
        res.update({"by_category": by_cat, "category_corrected": sum(1 for v in final.values() if v.get("category_corrected")),
                    "blinding_check": {"n": len(guesses), "correct": g_ok,
                                       "accuracy": round(g_ok / len(guesses), 4) if guesses else None,
                                       "ci95": M.binomial_ci(g_ok, len(guesses))},
                    "effort": self.effort_summary(), "agreement": st["agreement"]})
        self.store.update("pool", pool_id, {"sealed": False, "unsealed_at": now_iso(), "as2a": res})
        self._audit(actor, "pool.unseal", pool_id, delta=res["main"]["delta_pp"], h2a=res["h2a"]["met"])
        return res

    def as2b_results(self, actor: dict, pool_id: str) -> dict[str, Any]:
        self._need(actor, "pool.unseal")
        pool = self._get("pool", pool_id)
        if pool["purpose"] != "as2b":
            raise ProtocolError("not an AS2b pool")
        st = self.pool_status(pool_id)
        final = self._pool_resolution(pool_id)["final"]
        ext = self.store.list("finding", parent=pool["reports"]["E"])
        core_keys = {f["key"] for f in self.store.list("finding", parent=pool["reports"]["C"])}
        seal = self.store.get_artifact(pool["seal_artifact"])
        key_final: dict[str, dict] = {}
        for code, sl in seal.items():
            key_final[sl["keys"]["E"]] = final.get(code, {})
        rows = []
        for f in ext:
            fin = key_final.get(f["key"], {})
            rows.append({"key": f["key"], "new": f["key"] not in core_keys,
                         "reviewed": fin.get("status") == "final", "verified": bool(fin.get("verified")),
                         "pi": 1.0})
        lost = sorted(core_keys - {f["key"] for f in ext})
        res = M.h2b_new_share(rows)
        res.update({"core_candidates_lost_in_extended": len(lost), "pool_complete": st["complete"]})
        self.store.update("pool", pool_id, {"as2b": res})
        self._audit(actor, "as2b.results", pool_id, share=res["share"])
        return res

    def source_guess(self, user: dict, pool_id: str, code: str, guess: str, confidence: int = 3) -> dict:
        self._need(user, "validation.decide")
        if guess not in ("M", "U"):
            raise ProtocolError("guess must be 'M' or 'U'")
        self.store.put("source_guess", {"pool_id": pool_id, "code": code, "validator": user["username"],
                                        "guess": guess, "confidence": confidence},
                       id=f"{pool_id}:{user['username']}:{code}", parent=pool_id)
        return {"ok": True}

    # effort ---------------------------------------------------------------
    def log_effort(self, user: dict, activity: str, hours: float, context: str = "", note: str = "") -> dict:
        if hours <= 0 or hours > 24:
            raise ProtocolError("hours must be within (0, 24]")
        e = self.store.put("effort", {"user": user["username"], "activity": activity, "hours": float(hours),
                                      "context": context, "note": note})
        self._audit(user, "effort.log", e["id"], activity=activity, hours=hours)
        return e

    def effort_summary(self) -> dict[str, Any]:
        rows = self.store.list("effort")
        by = defaultdict(float)
        for r in rows:
            by[r["activity"]] += r["hours"]
        return {"total_person_hours": round(sum(by.values()), 2),
                "by_activity": {k: round(v, 2) for k, v in sorted(by.items())}, "entries": len(rows)}

    #  AS5: whole-curriculum candidate evaluation by coordinators
    def create_as5_sample(self, actor: dict, report_id: str, n_max: int = 300, seed: int = 20260913,
                          priority_top: int = 20) -> dict:
        self._need(actor, "sample.create")
        rep = self._get("report", report_id)
        if not rep["locked"]:
            raise ProtocolError("the final candidate pool (report) must be locked")
        fs = self.store.list("finding", parent=report_id)
        los = {r["uid"]: r for r in self.store.list("lo", parent=rep["dataset_id"])}
        strata: dict[str, list[str]] = defaultdict(list)
        for f in fs:
            years = sorted({los[u]["year"] for u in f["items"]["los"] if u in los}) or [0]
            band = "top" if f.get("evidence", {}).get("best_hybrid_rank", 999) <= 50 else "rest"
            strata[f"Y{years[0]}:{f['category']}:{band}"].append(f["key"])
        sizes = {h: len(v) for h, v in strata.items()}
        alloc = allocate(sizes, min(n_max, sum(sizes.values())), min_per_stratum=5)
        items = stratified_sample(strata, alloc, seed)
        priority = sorted(fs, key=lambda f: f.get("evidence", {}).get("best_hybrid_rank", 999))[:priority_top]
        s = self.store.put("sample", {"kind": "as5", "report_id": report_id, "n": len(items),
                                      "design": {"strata_sizes": sizes, "allocation": alloc, "seed": seed, "n_max": n_max},
                                      "items_artifact": self.store.put_artifact("as5_sample", {"items": items}),
                                      "priority_list": [f["key"] for f in priority],
                                      "created_by": actor["username"], "status": "open", "analysis_id": rep.get("analysis_id")})
        self._audit(actor, "as5.sample", s["id"], n=len(items))
        return s

    def as5_queue(self, user: dict, sample_id: str) -> dict[str, Any]:
        s = self._get("sample", sample_id)
        if s.get("kind") != "as5":
            raise ProtocolError("not an AS5 sample")
        fs = {f["key"]: f for f in self.store.list("finding", parent=s["report_id"])}
        mine = {e["item"]: e for e in self.store.list("as5_eval", parent=sample_id, coordinator=user["username"])}
        items = []
        for it in self._sample_items(s)["items"]:
            f = fs[it["item"]]
            items.append({"item": it["item"], "category": f["category"], "statement": f["statement"],
                          "support": f["support"], "rationale": f["rationale"], "my": mine.get(it["item"])})
        return {"sample_id": sample_id, "items": items}

    def as5_evaluate(self, user: dict, sample_id: str, item: str, meaningful: bool | None, feasible: bool | None,
                     completed: bool = True, rationale: str = "") -> dict:
        self._need(user, "as5.evaluate")
        s = self._get("sample", sample_id)
        if item not in {i["item"] for i in self._sample_items(s)["items"]}:
            raise NotFound("item not in sample")
        if completed and (meaningful is None or feasible is None):
            raise ProtocolError("completed evaluations record both meaningfulness and feasibility")
        rec = self.store.put("as5_eval", {"sample_id": sample_id, "item": item, "coordinator": user["username"],
                                          "meaningful": meaningful, "feasible": feasible, "completed": completed,
                                          "rationale": rationale}, id=f"{sample_id}:{item}", parent=sample_id)
        return rec

    def as5_results(self, actor: dict, sample_id: str, min_coordinators: int = 20) -> dict[str, Any]:
        self._need(actor, "metrics.read")
        s = self._get("sample", sample_id)
        evals = {e["item"]: e for e in self.store.list("as5_eval", parent=sample_id)}
        rows = []
        for it in self._sample_items(s)["items"]:
            e = evals.get(it["item"], {})
            rows.append({"item": it["item"], "stratum": it["stratum"], "weight": it["weight"],
                         "completed": bool(e.get("completed")), "meaningful": e.get("meaningful"),
                         "feasible": e.get("feasible"), "coordinator": e.get("coordinator")})
        res = M.h5_estimate(rows, min_coordinators=min_coordinators)
        self.store.update("sample", sample_id, {"evaluation": res})
        self._audit(actor, "as5.results", sample_id, rate=res["joint_rate"])
        return res

    #  AS6: change impact
    def create_changeset(self, actor: dict, t0: str, t1: str, config_id: str, kind: str = "real",
                         description: str = "", decision_ref: str = "") -> dict:
        self._need(actor, "impact.run")
        for d in (t0, t1):
            if self._get("dataset", d)["status"] != "frozen":
                raise ProtocolError("T0 and T1 must both be frozen versions")
        cs = self.store.put("changeset", {"t0": t0, "t1": t1, "config_id": config_id, "kind": kind,
                                          "description": description, "decision_ref": decision_ref,
                                          "expected_locked": False, "report": None, "created_by": actor["username"]})
        self._audit(actor, "impact.changeset", cs["id"], t0=t0, t1=t1)
        return cs

    def register_expected(self, user: dict, changeset_id: str, effects: list[dict]) -> dict:
        self._need(user, "impact.expected")
        cs = self._get("changeset", changeset_id)
        if cs["expected_locked"]:
            raise ProtocolError("expected effects are locked")
        if cs.get("report"):
            raise ProtocolError("expected effects must be registered before the system report")
        for e in effects:
            self.store.put("expected_effect", {"changeset_id": changeset_id, "type": e["type"], "entity": e["entity"],
                                               "rationale": e.get("rationale", ""), "recorded_by": user["username"]},
                           parent=changeset_id)
        return {"registered": len(effects)}

    def lock_expected(self, user: dict, changeset_id: str) -> dict:
        self._need(user, "impact.expected")
        eff = self.store.list("expected_effect", parent=changeset_id)
        h = sha256(sorted((e["type"], e["entity"]) for e in eff))
        self.store.update("changeset", changeset_id, {"expected_locked": True, "expected_hash": h,
                                                      "expected_count": len(eff)})
        self._audit(user, "impact.expected_lock", changeset_id, n=len(eff), hash=h)
        return {"locked": len(eff), "hash": h}

    def expected_effects(self, user: dict, changeset_id: str) -> list[dict]:
        if not can(user["roles"], "impact.expected") and Role.ADMIN.value not in user["roles"]:
            raise PermissionError("the technical team does not see the expected-effect list")
        return self.store.list("expected_effect", parent=changeset_id)

    def run_impact(self, actor: dict, changeset_id: str) -> dict:
        self._need(actor, "impact.run")
        cs = self._get("changeset", changeset_id)
        if not cs["expected_locked"]:
            raise ProtocolError("expected effects must be registered and locked first")
        cfg = self._cfg(cs["config_id"])
        t0 = self.los_records(cs["t0"]); t1 = self.los_records(cs["t1"])
        res = impact_alerts(t0, t1, self.ucep_rows(cs["t1"]), cfg)
        h = self.store.put_artifact("impact_report", res)
        self.store.update("changeset", changeset_id, {"report": h, "n_alerts": len(res["alerts"]),
                                                      "diff_counts": {k: len(v) for k, v in res["diff"].items()}})
        self._audit(actor, "impact.run", changeset_id, alerts=len(res["alerts"]), artifact=h)
        return res

    def decide_alert(self, user: dict, changeset_id: str, alert_id: str, verified: bool, rationale: str = "") -> dict:
        self._need(user, "impact.expected")
        rec = self.store.put("alert_decision", {"changeset_id": changeset_id, "alert_id": alert_id,
                                                "verified": verified, "rationale": rationale,
                                                "evaluator": user["username"]},
                             id=f"{changeset_id}:{alert_id}", parent=changeset_id)
        return rec

    def evaluate_changeset(self, user: dict, changeset_id: str) -> dict:
        cs = self._get("changeset", changeset_id)
        if not cs.get("report"):
            raise ProtocolError("run the impact report first")
        rep = self.store.get_artifact(cs["report"])
        exp = self.store.list("expected_effect", parent=changeset_id)
        dec = {d["alert_id"]: d["verified"] for d in self.store.list("alert_decision", parent=changeset_id)}
        ev = evaluate_alerts(rep["alerts"], exp, dec)
        ev["kind"] = cs["kind"]
        ev["note"] = ("Real changes are reported descriptively (no pass/fail thresholds)." if cs["kind"] == "real"
                      else "Controlled scenario.")
        self.store.update("changeset", changeset_id, {"evaluation": {k: v for k, v in ev.items() if k not in ("alerts", "expected")}})
        return ev

    def changeset_report(self, user: dict, changeset_id: str) -> dict:
        cs = self._get("changeset", changeset_id)
        rep = self.store.get_artifact(cs["report"]) if cs.get("report") else None
        return {"changeset": cs, "report": rep}

    def list_changesets(self) -> list[dict]:
        return self.store.list("changeset")

    def controlled_test(self, actor: dict, dataset_id: str, config_id: str, per_type: int = 8) -> dict:
        self._need(actor, "impact.run")
        if self._get("dataset", dataset_id)["status"] != "frozen":
            raise ProtocolError("controlled scenarios run on a copy of a frozen version")
        res = run_controlled(self.los_records(dataset_id), self.ucep_rows(dataset_id), self._cfg(config_id), per_type)
        doc = self.store.put("controlled_test", {"dataset_id": dataset_id, "config_id": config_id,
                                                 "overall": res["overall"], "by_type": res["by_type"],
                                                 "artifact": self.store.put_artifact("controlled", res)})
        self._audit(actor, "impact.controlled", doc["id"], met=res["overall"]["met"])
        return {**res, "id": doc["id"]}


def playground_analyze(lo_rows: list[dict], ucep_rows: list[dict], depth: int = 10) -> dict:
    """Stateless exploration: QC → three rankers + RRF → findings → UÇEP map."""
    import time
    from app.mimar.analysis import AnalysisConfig, LORecord, OverlapAnalysis
    t0 = time.perf_counter()
    qc = prepare_learning_objectives(lo_rows, default_source="deneme alanı")
    uq = prepare_ucep(ucep_rows) if ucep_rows else {"included": [], "excluded": [], "report": {}}
    los = [LORecord(uid=r["uid"], text=r["text"], activity=r["activity"], course=r["course"], year=r["year"],
                    discipline=r.get("discipline", ""), ucep_links=r.get("ucep_links", [])) for r in qc["included"]]
    out = {"qc": {**qc["report"], "excluded_rows": [{"row": e["row"], "uid": e["uid"], "reason": e["reason"],
                                                     "text": e["text"]} for e in qc["excluded"]]},
           "ucep_qc": uq["report"], "pairs": [], "findings": [], "ucep_map": [], "spiral": []}
    if len(los) < 3:
        out["message"] = "Analiz için kalite kontrolünden geçen en az 3 öğrenme hedefi gerekir."
        out["seconds"] = round(time.perf_counter() - t0, 3)
        return out
    cfg = AnalysisConfig(list_depth=depth, per_query_k=min(10, len(los) - 1))
    cfg.concept.max_df_ratio = 0.5 if len(los) < 60 else cfg.concept.max_df_ratio
    a = OverlapAnalysis(los, cfg)
    by = {lo.uid: lo for lo in los}
    for h in a.hybrid(depth=depth):
        x, y = split_key(h["pair"])
        out["pairs"].append({"rank": h["rank"], "rrf": h["rrf"], "method_ranks": h["method_ranks"],
                             "a": {"uid": x, "text": by[x].text, "course": by[x].course, "year": by[x].year},
                             "b": {"uid": y, "text": by[y].text, "course": by[y].course, "year": by[y].year},
                             "evidence": a.evidence(h["pair"])})
    umap = ucep_correspondence(a, uq["included"]) if uq["included"] else []
    gen = generate_mimar_findings(a, umap, depth=max(3, depth // 2))
    out["findings"] = [{k: f[k] for k in ("category", "items", "statement", "rationale")} for f in gen["findings"]]
    out["spiral"] = gen["spiral_progressions"]
    out["ucep_map"] = [{k: u[k] for k in ("code", "text_tr", "text_en", "status", "best_cosine", "best_coverage")} |
                       {"closest": u["candidates"][0]["lo"] if u["candidates"] else None} for u in umap]
    out["engine"] = {"embedding": a.emb.backend_used, "concepts": len(a.graph.concepts), "n_los": len(los)}
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out
