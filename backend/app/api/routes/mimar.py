"""REST API (prefix /api/v1/mimar)."""
from __future__ import annotations

import csv
import io
import os
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.mimar import metrics as M
from app.mimar.qc import parse_table
from app.mimar.security import IndependenceError
from app.mimar.service import MimarService, NotFound, ProtocolError
from app.mimar.store import Store

router = APIRouter(prefix="/mimar", tags=["mimar"])
settings = get_settings()

_service: MimarService | None = None


def get_service() -> MimarService:
    global _service
    if _service is None:
        path = os.getenv("MIMAR_DB_PATH", settings.mimar_db_path)
        _service = MimarService(Store(path))
        _service.ensure_admin(os.getenv("MIMAR_ADMIN_TOKEN", settings.mimar_admin_token))
    return _service


def set_service(svc: MimarService) -> None:
    """Used by tests to inject an in-memory service."""
    global _service
    _service = svc


def current_user(authorization: str = Header(default=""), svc: MimarService = Depends(get_service)) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user = svc.authenticate(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return user


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotFound as e:
        raise HTTPException(404, str(e).strip("'\""))
    except IndependenceError as e:
        raise HTTPException(403, f"independence rule: {e}")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ProtocolError as e:
        raise HTTPException(409, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))


def csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


def public(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "token_hash"}


# models
class UserIn(BaseModel):
    username: str
    display_name: str = ""
    roles: list[str]


class DatasetIn(BaseModel):
    name: str
    scope: str = "MSKL"
    version_label: str = "T0"
    description: str = ""


class VersionIn(BaseModel):
    version_label: str
    description: str = ""


class ConfigIn(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class AnalysisIn(BaseModel):
    dataset_id: str
    config_id: str
    with_materials: bool = False
    label: str = ""


class SampleIn(BaseModel):
    part: str
    n: int | None = None


class AssignIn(BaseModel):
    reviewers: list[str]
    adjudicator: str | None = None


class DecisionIn(BaseModel):
    code: str
    value: str
    rationale: str = ""


class ReportIn(BaseModel):
    kind: str = "core"
    depth: int | None = None


class PoolIn(BaseModel):
    reports: dict[str, str]
    confirmed_matches: list[dict[str, Any]] = Field(default_factory=list)
    purpose: str = "as2a"


class MatchIn(BaseModel):
    mimar_report: str
    expert_report: str


class ValidationIn(BaseModel):
    code: str
    support: str
    meaningful: str
    category_ok: str
    suggested_category: str = ""
    rationale: str = ""


class ValAdjIn(BaseModel):
    code: str
    decision: dict[str, str]


class GuessIn(BaseModel):
    code: str
    guess: str
    confidence: int = 3


class EffortIn(BaseModel):
    activity: str
    hours: float
    context: str = ""
    note: str = ""


class AS5SampleIn(BaseModel):
    n_max: int = 300
    seed: int = 20260913


class AS5EvalIn(BaseModel):
    item: str
    meaningful: bool | None = None
    feasible: bool | None = None
    completed: bool = True
    rationale: str = ""


class ChangesetIn(BaseModel):
    t0: str
    t1: str
    config_id: str
    kind: str = "real"
    description: str = ""
    decision_ref: str = ""


class ExpectedIn(BaseModel):
    effects: list[dict[str, str]]


class AlertDecisionIn(BaseModel):
    verified: bool
    rationale: str = ""


class ControlledIn(BaseModel):
    config_id: str
    per_type: int = 8


class PowerIn(BaseModel):
    ns: list[int] = Field(default_factory=lambda: [60, 90, 120, 150, 200, 250, 300])
    p_true: float = 0.6
    delta_true_pp: float = 0.0
    shared_fraction: float = 0.2
    mean_family_size: float = 1.5
    margin_pp: float = -10.0
    sims: int = 1000


class AgreementIn(BaseModel):
    rater1: list[str | None]
    rater2: list[str | None]
    categories: list[str] | None = None


# identity
@router.get("/me")
def me(user: dict = Depends(current_user)):
    return public(user)


@router.get("/users")
def users(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_users()


@router.post("/users")
def create_user(body: UserIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.create_user, user, body.username, body.display_name or body.username, body.roles)


@router.post("/users/{username}/token")
def rotate(username: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.rotate_token, user, username)


# overview
@router.get("/overview")
def overview(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    st = svc.store
    analyses = svc.list_analyses()
    plans = st.list("plan")
    samples = svc.list_samples()
    return {
        "datasets": len(svc.list_datasets()), "frozen_datasets": sum(1 for d in svc.list_datasets() if d["status"] == "frozen"),
        "analyses": len(analyses), "plans_locked": sum(1 for p in plans if p.get("locked")),
        "as1_samples": {"dev": sum(1 for s in samples if s.get("part") == "dev"),
                        "test": sum(1 for s in samples if s.get("part") == "test"),
                        "evaluated": sum(1 for s in samples if s.get("status") == "evaluated")},
        "reports": len(svc.list_reports()), "pools": st.count("pool"),
        "changesets": len(svc.list_changesets()), "audit": st.verify_audit(),
        "effort": svc.effort_summary(),
        "demo_available": settings.app_env == "development" or os.getenv("MIMAR_ENABLE_DEMO") == "1",
    }


# datasets
@router.get("/datasets")
def datasets(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_datasets()


@router.post("/datasets")
def create_dataset(body: DatasetIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.create_dataset, user, body.name, body.scope, body.version_label, body.description)


@router.get("/datasets/{dataset_id}")
def dataset(dataset_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.dataset_detail, dataset_id)


@router.post("/datasets/{dataset_id}/los")
def import_los(dataset_id: str, rows: list[dict[str, Any]] = Body(...), user: dict = Depends(current_user),
         svc: MimarService = Depends(get_service)):
    return call(svc.import_los, user, dataset_id, rows)


@router.post("/datasets/{dataset_id}/los/upload")
async def import_los_upload(dataset_id: str, file: UploadFile = File(...), user: dict = Depends(current_user),
                      svc: MimarService = Depends(get_service)):
    rows = parse_table(await file.read(), file.filename or "upload.csv")
    return call(svc.import_los, user, dataset_id, rows)


@router.post("/datasets/{dataset_id}/ucep")
def import_ucep(dataset_id: str, rows: list[dict[str, Any]] = Body(...), user: dict = Depends(current_user),
         svc: MimarService = Depends(get_service)):
    return call(svc.import_ucep, user, dataset_id, rows)


@router.post("/datasets/{dataset_id}/ucep/upload")
async def import_ucep_upload(dataset_id: str, file: UploadFile = File(...), user: dict = Depends(current_user),
                      svc: MimarService = Depends(get_service)):
    rows = parse_table(await file.read(), file.filename or "upload.csv")
    return call(svc.import_ucep, user, dataset_id, rows)


@router.post("/datasets/{dataset_id}/materials")
def import_materials(dataset_id: str, rows: list[dict[str, Any]] = Body(...), user: dict = Depends(current_user),
         svc: MimarService = Depends(get_service)):
    return call(svc.import_materials, user, dataset_id, rows)


@router.post("/datasets/{dataset_id}/materials/upload")
async def import_materials_upload(dataset_id: str, file: UploadFile = File(...), user: dict = Depends(current_user),
                      svc: MimarService = Depends(get_service)):
    rows = parse_table(await file.read(), file.filename or "upload.csv")
    return call(svc.import_materials, user, dataset_id, rows)


@router.post("/datasets/{dataset_id}/freeze")
def freeze(dataset_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.freeze_dataset, user, dataset_id)


@router.post("/datasets/{dataset_id}/versions")
def new_version(dataset_id: str, body: VersionIn, user: dict = Depends(current_user),
                svc: MimarService = Depends(get_service)):
    return call(svc.new_version, user, dataset_id, body.version_label, body.description)


@router.post("/datasets/{dataset_id}/changes")
def apply_changes(dataset_id: str, changes: list[dict[str, Any]] = Body(...), user: dict = Depends(current_user),
                  svc: MimarService = Depends(get_service)):
    return call(svc.apply_changes, user, dataset_id, changes)


@router.get("/datasets/{dataset_id}/los")
def los(dataset_id: str, q: str = "", limit: int = Query(500, le=5000), user: dict = Depends(current_user),
        svc: MimarService = Depends(get_service)):
    return svc.list_los(dataset_id, q, limit)


@router.get("/datasets/{dataset_id}/ucep")
def ucep(dataset_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.ucep_rows(dataset_id)


@router.post("/datasets/{dataset_id}/controlled-test")
def controlled(dataset_id: str, body: ControlledIn, user: dict = Depends(current_user),
               svc: MimarService = Depends(get_service)):
    res = call(svc.controlled_test, user, dataset_id, body.config_id, body.per_type)
    return {k: v for k, v in res.items() if k != "scenarios"} | {
        "scenarios": [{k: v for k, v in s.items() if k in ("id", "type", "n_alerts")} |
                      {"verified": sum(a["verified"] for a in s["alerts"]),
                       "missed": sum(not e["reported"] for e in s["expected"]), "expected": len(s["expected"])}
                      for s in res["scenarios"]]}


# configs & analyses
@router.get("/configs")
def configs(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_configs()


@router.post("/configs")
def create_config(body: ConfigIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.create_config, user, body.name, body.params)


@router.get("/analyses")
def analyses(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_analyses()


@router.post("/analyses")
def run_analysis(body: AnalysisIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.run_analysis, user, body.dataset_id, body.config_id, body.with_materials, body.label)


@router.get("/analyses/{analysis_id}")
def analysis(analysis_id: str, top: int = Query(100, le=2000), split: str | None = None,
             user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.analysis_detail, analysis_id, top, split)


@router.post("/analyses/{analysis_id}/stability")
def stability(analysis_id: str, runs: int = 5, top: int = 20, user: dict = Depends(current_user),
              svc: MimarService = Depends(get_service)):
    return call(svc.stability, user, analysis_id, runs, top)


@router.get("/analyses/{analysis_id}/concepts")
def concepts(analysis_id: str, limit: int = 150, user: dict = Depends(current_user),
             svc: MimarService = Depends(get_service)):
    return call(svc.concept_graph, analysis_id, limit)


@router.get("/analyses/{analysis_id}/neo4j.cypher", response_class=PlainTextResponse)
def cypher(analysis_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.neo4j_cypher, analysis_id)


@router.post("/analyses/{analysis_id}/neo4j/push")
async def neo4j_push(analysis_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    from app.graph.client import neo4j_client
    if not await neo4j_client.is_healthy():
        raise HTTPException(503, "Neo4j is not reachable; download the Cypher script instead")
    script = call(svc.neo4j_cypher, analysis_id)
    n = 0
    async with neo4j_client.session() as s:
        for stmt in script.split(";\n"):
            stmt = stmt.strip().rstrip(";")
            if stmt:
                await s.run(stmt)
                n += 1
    svc.store.audit(user["username"], "analysis.neo4j_push", analysis_id, {"statements": n})
    return {"statements": n}


@router.get("/analyses/{analysis_id}/export.csv")
def export_analysis(analysis_id: str, top: int = 500, user: dict = Depends(current_user),
                    svc: MimarService = Depends(get_service)):
    d = call(svc.analysis_detail, analysis_id, top)
    rows = [{"rank": r["rank"], "lo_a": r["a"]["uid"], "lo_b": r["b"]["uid"], "rrf": r["rrf"],
             "rank_bm25": r["method_ranks"].get("bm25", ""), "rank_embedding": r["method_ranks"].get("embedding", ""),
             "rank_graph": r["method_ranks"].get("graph", ""), "cosine": r["evidence"]["cosine"],
             "shared_concepts": "; ".join(r["evidence"]["shared_concepts"]),
             "text_a": r["a"]["text"], "text_b": r["b"]["text"]} for r in d["top"]]
    return csv_response(rows, f"mimar_candidates_{analysis_id}.csv")


# plan
@router.post("/analyses/{analysis_id}/plan")
def create_plan(analysis_id: str, params: dict[str, Any] = Body(default={}), user: dict = Depends(current_user),
                svc: MimarService = Depends(get_service)):
    return call(svc.create_plan, user, analysis_id, params)


@router.get("/plans/{plan_id}")
def plan(plan_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc._get, "plan", plan_id)


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: str, params: dict[str, Any] = Body(...), user: dict = Depends(current_user),
                svc: MimarService = Depends(get_service)):
    return call(svc.update_plan, user, plan_id, params)


@router.post("/plans/{plan_id}/lock")
def lock_plan(plan_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.lock_plan, user, plan_id)


# AS1 samples & review
@router.post("/analyses/{analysis_id}/samples")
def create_sample(analysis_id: str, body: SampleIn, user: dict = Depends(current_user),
                  svc: MimarService = Depends(get_service)):
    return call(svc.create_as1_sample, user, analysis_id, body.part, body.n)


@router.get("/samples")
def samples(analysis_id: str | None = None, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_samples(analysis_id)


@router.get("/samples/mine")
def my_samples(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    out = []
    for s in svc.store.list("sample"):
        role = ("reviewer" if user["username"] in s.get("reviewers", []) else
                "adjudicator" if user["username"] == s.get("adjudicator") else None)
        if role:
            out.append({"id": s["id"], "part": s.get("part"), "kind": s.get("kind"), "n": s["n"], "role": role})
    for p in svc.store.list("pool"):
        role = ("validator" if user["username"] in p.get("validators", []) else
                "adjudicator" if user["username"] == p.get("adjudicator") else None)
        if role:
            out.append({"id": p["id"], "kind": "pool", "purpose": p["purpose"], "n": p["n_entries"], "role": role})
    if "coordinator" in user["roles"]:
        for s in svc.store.list("sample", kind="as5"):
            out.append({"id": s["id"], "kind": "as5", "n": s["n"], "role": "coordinator"})
    return out


@router.get("/samples/{sample_id}/progress")
def progress(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.sample_progress, sample_id)


@router.post("/samples/{sample_id}/assign")
def assign(sample_id: str, body: AssignIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.assign_reviewers, user, sample_id, body.reviewers, body.adjudicator)


@router.get("/samples/{sample_id}/queue")
def queue(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.review_queue, user, sample_id)


@router.post("/samples/{sample_id}/decisions")
def decide(sample_id: str, body: DecisionIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.decide, user, sample_id, body.code, body.value, body.rationale)


@router.post("/samples/{sample_id}/lock")
def lock_decisions(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.lock_decisions, user, sample_id)


@router.get("/samples/{sample_id}/adjudication")
def adjudication_queue(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.adjudication_queue, user, sample_id)


@router.post("/samples/{sample_id}/adjudications")
def adjudicate(sample_id: str, body: DecisionIn, user: dict = Depends(current_user),
               svc: MimarService = Depends(get_service)):
    return call(svc.adjudicate, user, sample_id, body.code, body.value, body.rationale)


@router.post("/samples/{sample_id}/evaluate")
def evaluate(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.evaluate_sample, user, sample_id)


@router.get("/samples/{sample_id}/labels.csv")
def labels_csv(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    if not ("admin" in user["roles"] or "technical" in user["roles"]):
        raise HTTPException(403, "only admin/technical can export labels")
    s = call(svc._get, "sample", sample_id)
    items = svc._sample_items(s)["items"]
    lab = svc.final_labels(sample_id)["labels"]
    rows = [{"pair": it["item"], "stratum": it["stratum"], "N_h": it["N_h"], "n_h": it["n_h"], "pi": it["pi"],
             "weight": it["weight"], "listed_in": ";".join(it["listed_in"]),
             "label": {1: "overlap", 0: "no_overlap", None: "insufficient"}.get(lab.get(it["item"]), "pending")}
            for it in items]
    return csv_response(rows, f"as1_labels_{sample_id}.csv")


# AS2 reports & pools
@router.get("/reports")
def reports(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_reports()


@router.post("/analyses/{analysis_id}/reports")
def mimar_report(analysis_id: str, body: ReportIn, user: dict = Depends(current_user),
                 svc: MimarService = Depends(get_service)):
    return call(svc.generate_mimar_report, user, analysis_id, body.kind, body.depth)


@router.post("/datasets/{dataset_id}/expert-reports")
def expert_report(dataset_id: str, rows: list[dict[str, Any]] = Body(...), authors: str = Query(default=""),
                  user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.import_expert_report, user, dataset_id, rows, [a for a in authors.split(",") if a])


@router.post("/datasets/{dataset_id}/expert-reports/upload")
async def expert_report_upload(dataset_id: str, file: UploadFile = File(...), authors: str = Form(default=""),
                               user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    rows = parse_table(await file.read(), file.filename or "upload.csv")
    return call(svc.import_expert_report, user, dataset_id, rows, [a for a in authors.split(",") if a])


@router.get("/reports/{report_id}")
def report(report_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.report_findings, user, report_id)


@router.post("/reports/{report_id}/lock")
def lock_report(report_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.lock_report, user, report_id)


@router.get("/reports/{report_id}/export.csv")
def export_report(report_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    d = call(svc.report_findings, user, report_id)
    rows = [{"key": f["key"], "category": f["category"], "los": ";".join(f["items"]["los"]),
             "ucep": ";".join(f["items"]["ucep"]), "statement": f["statement"], "rationale": f["rationale"]}
            for f in d["findings"]]
    return csv_response(rows, f"mimar_report_{report_id}.csv")


@router.post("/pools/matches")
def matches(body: MatchIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.propose_matches, user, body.mimar_report, body.expert_report)


@router.get("/pools")
def pools(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return [{k: v for k, v in p.items() if k != "seal_artifact"} for p in svc.store.list("pool")]


@router.post("/pools")
def build_pool(body: PoolIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.build_pool, user, body.reports, body.confirmed_matches, body.purpose)


@router.post("/pools/{pool_id}/assign")
def assign_validators(pool_id: str, body: AssignIn, user: dict = Depends(current_user),
                      svc: MimarService = Depends(get_service)):
    return call(svc.assign_validators, user, pool_id, body.reviewers, body.adjudicator)


@router.get("/pools/{pool_id}/entries")
def pool_entries(pool_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.pool_entries, user, pool_id)


@router.post("/pools/{pool_id}/validations")
def validate(pool_id: str, body: ValidationIn, user: dict = Depends(current_user),
             svc: MimarService = Depends(get_service)):
    return call(svc.validate, user, pool_id, body.code, body.support, body.meaningful, body.category_ok,
                body.suggested_category, body.rationale)


@router.post("/pools/{pool_id}/lock")
def lock_validations(pool_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.lock_validations, user, pool_id)


@router.get("/pools/{pool_id}/conflicts")
def pool_conflicts(pool_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    pool = call(svc._get, "pool", pool_id)
    if user["username"] != pool.get("adjudicator") and "admin" not in user["roles"]:
        raise HTTPException(403, "not the adjudicator")
    entries = {e["code"]: e for e in svc.store.get_artifact(pool["entries_artifact"])}
    return [{**c, "entry": {k: v for k, v in entries[c["code"]].items() if k != "family"}}
            for c in svc._pool_resolution(pool_id)["conflicts"]]


@router.post("/pools/{pool_id}/adjudications")
def validation_adjudicate(pool_id: str, body: ValAdjIn, user: dict = Depends(current_user),
                          svc: MimarService = Depends(get_service)):
    return call(svc.validation_adjudicate, user, pool_id, body.code, body.decision)


@router.get("/pools/{pool_id}/status")
def pool_status(pool_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.pool_status, pool_id)


@router.post("/pools/{pool_id}/as2a")
def as2a(pool_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.as2a_results, user, pool_id)


@router.post("/pools/{pool_id}/as2b")
def as2b(pool_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.as2b_results, user, pool_id)


@router.post("/pools/{pool_id}/guesses")
def guess(pool_id: str, body: GuessIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.source_guess, user, pool_id, body.code, body.guess, body.confidence)


# effort
@router.post("/effort")
def log_effort(body: EffortIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.log_effort, user, body.activity, body.hours, body.context, body.note)


@router.get("/effort")
def effort(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return {**svc.effort_summary(), "rows": svc.store.list("effort")}


# AS5
@router.post("/reports/{report_id}/as5-sample")
def as5_sample(report_id: str, body: AS5SampleIn, user: dict = Depends(current_user),
               svc: MimarService = Depends(get_service)):
    return call(svc.create_as5_sample, user, report_id, body.n_max, body.seed)


@router.get("/samples/{sample_id}/as5-queue")
def as5_queue(sample_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.as5_queue, user, sample_id)


@router.post("/samples/{sample_id}/as5-evaluations")
def as5_eval(sample_id: str, body: AS5EvalIn, user: dict = Depends(current_user),
             svc: MimarService = Depends(get_service)):
    return call(svc.as5_evaluate, user, sample_id, body.item, body.meaningful, body.feasible, body.completed,
                body.rationale)


@router.post("/samples/{sample_id}/as5-results")
def as5_results(sample_id: str, min_coordinators: int = 20, user: dict = Depends(current_user),
                svc: MimarService = Depends(get_service)):
    return call(svc.as5_results, user, sample_id, min_coordinators)


# AS6
@router.get("/changesets")
def changesets(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.list_changesets()


@router.post("/changesets")
def create_changeset(body: ChangesetIn, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.create_changeset, user, body.t0, body.t1, body.config_id, body.kind, body.description,
                body.decision_ref)


@router.get("/changesets/{cs_id}")
def changeset(cs_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.changeset_report, user, cs_id)


@router.get("/changesets/{cs_id}/expected")
def expected(cs_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.expected_effects, user, cs_id)


@router.post("/changesets/{cs_id}/expected")
def register_expected(cs_id: str, body: ExpectedIn, user: dict = Depends(current_user),
                      svc: MimarService = Depends(get_service)):
    return call(svc.register_expected, user, cs_id, body.effects)


@router.post("/changesets/{cs_id}/expected/lock")
def lock_expected(cs_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.lock_expected, user, cs_id)


@router.post("/changesets/{cs_id}/run")
def run_impact(cs_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.run_impact, user, cs_id)


@router.post("/changesets/{cs_id}/alerts/{alert_id}")
def decide_alert(cs_id: str, alert_id: str, body: AlertDecisionIn, user: dict = Depends(current_user),
                 svc: MimarService = Depends(get_service)):
    return call(svc.decide_alert, user, cs_id, alert_id, body.verified, body.rationale)


@router.post("/changesets/{cs_id}/evaluate")
def evaluate_changeset(cs_id: str, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return call(svc.evaluate_changeset, user, cs_id)


# playground (stateless input → output)
class PlaygroundIn(BaseModel):
    los: list[dict[str, Any]]
    ucep: list[dict[str, Any]] = Field(default_factory=list)
    depth: int = Field(default=10, ge=3, le=200)


@router.post("/playground/analyze")
def playground(body: PlaygroundIn, user: dict = Depends(current_user)):
    from app.mimar.service import playground_analyze
    if len(body.los) > 3000:
        raise HTTPException(413, "the playground accepts at most 3000 objectives")
    return call(playground_analyze, body.los, body.ucep, body.depth)


# integrated input → output (no research-question labels in the response)
class AnalyzeIn(BaseModel):
    los: list[dict[str, Any]]
    ucep: list[dict[str, Any]] = Field(default_factory=list)
    material: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/analyze")
def analyze(body: AnalyzeIn):
    """Stateless analysis used by the input/output screen."""
    from app.mimar.report import integrated_analysis
    if len(body.los) > 3000:
        raise HTTPException(413, "en fazla 3000 öğrenme hedefi gönderilebilir")
    return call(integrated_analysis, body.los, body.ucep, body.material)


# real KUSOM curriculum as analysis input
@router.get("/kusom/blocks")
def kusom_blocks():
    """Blocks of the imported KUSOM 2025–2026 data, for the input screen."""
    from app.data.kusom import curriculum as loader
    if not loader.available():
        return {"available": False, "blocks": []}
    return {"available": True, "blocks": [
        {"id": b["id"], "code": b["code"], "year": y["year"], "name": b["name_tr"],
         "topics": len(b["topics"]), "objectives": sum(len(d["objectives"]) for d in b["topic_details"])}
        for y in loader.kusom_curriculum() for b in y["blocks"]]}


@router.get("/kusom/los")
def kusom_los(blocks: str = Query(..., description="comma-separated block ids, e.g. CIRC204,CARD314")):
    """Learning objectives of the chosen blocks; a topic without written objectives is represented by its session…"""
    from app.data.kusom import curriculum as loader
    if not loader.available():
        raise HTTPException(404, "KUSOM verisi yüklü değil")
    want = {b.strip().upper().replace(" ", "") for b in blocks.split(",") if b.strip()}
    rows = []
    for y in loader.kusom_curriculum():
        for b in y["blocks"]:
            if b["id"] not in want:
                continue
            for d in b["topic_details"]:
                if d["objectives"]:
                    for i, o in enumerate(d["objectives"], start=1):
                        rows.append({"uid": f"{d['id']}-{i:02d}", "year": y["year"], "course": b["code"],
                                     "text": o, "topic": d["title"], "activity": d["id"], "discipline": d.get("kind", ""),
                                     "from": "öğrenim hedefi"})
                else:
                    rows.append({"uid": d["id"], "year": y["year"], "course": b["code"], "text": d["title"],
                                 "topic": d["title"], "activity": d["id"], "discipline": d.get("kind", ""),
                                 "from": "ders başlığı"})
    return {"rows": rows[:3000], "truncated": len(rows) > 3000, "total": len(rows)}


@router.get("/ucep2020")
def ucep2020(system: str = ""):
    """UÇEP-2020 core diseases / clinical problems (Tablo 2.2) as UÇEP rows."""
    from app.data.ucep.ucep_list import load, ucep_rows
    return {"meta": load()["meta"], "rows": ucep_rows([system] if system else None)}


@router.get("/kusom/ucep-coverage")
def kusom_ucep_coverage():
    """Where each UÇEP-2020 core disease appears in the KUSOM timetables and objectives."""
    from app.data.kusom import curriculum as loader
    from app.data.ucep.match_ucep import coverage
    from app.data.ucep.ucep_list import load
    if not loader.available():
        raise HTTPException(404, "KUSOM verisi yüklü değil")
    return coverage(loader.kusom_curriculum(), load()["items"], loader.phase_of)


# statistics utilities
@router.post("/stats/power")
def power(body: PowerIn, user: dict = Depends(current_user)):
    return M.power_curve_h2a(body.ns, p_true=body.p_true, delta_true_pp=body.delta_true_pp,
                             shared_fraction=body.shared_fraction, mean_family_size=body.mean_family_size,
                             margin_pp=body.margin_pp, sims=body.sims)


@router.post("/stats/agreement")
def agreement(body: AgreementIn, user: dict = Depends(current_user)):
    return M.agreement(body.rater1, body.rater2, body.categories)


# audit
@router.get("/audit")
def audit(limit: int = 200, offset: int = 0, user: dict = Depends(current_user),
          svc: MimarService = Depends(get_service)):
    if not ({"admin", "observer"} & set(user["roles"])):
        raise HTTPException(403, "audit log is restricted")
    return svc.store.audit_log(limit, offset)


@router.get("/audit/verify")
def audit_verify(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    return svc.store.verify_audit()


# demo (development only)
@router.post("/demo/run")
def demo_run(quick: bool = False, user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    if not (settings.app_env == "development" or os.getenv("MIMAR_ENABLE_DEMO") == "1"):
        raise HTTPException(403, "demo is disabled outside development")
    if "admin" not in user["roles"]:
        raise HTTPException(403, "admin only")
    from app.mimar.demo import run_full_demo
    return call(run_full_demo, svc, user, quick=quick)


@router.get("/demo/summary")
def demo_summary(user: dict = Depends(current_user), svc: MimarService = Depends(get_service)):
    s = svc.store.get("demo_summary", "latest")
    if not s:
        raise HTTPException(404, "no demo has been run")
    if "admin" not in user["roles"]:
        s = {k: v for k, v in s.items() if k != "users"}
    return s
