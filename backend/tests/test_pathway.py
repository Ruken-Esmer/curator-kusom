"""Learning-pathway engine, chat integration and expert review / release gate."""
import pytest
from fastapi.testclient import TestClient

from app.api.routes import mimar as mimar_routes
from app.main import app
from app.pathway.planner import GEREKLI, TAZELE, TEKRAR, build, default_engine, parse_request


def test_parse_three_goal_types():
    b = default_engine().blocks
    assert parse_request("Kardiyoloji stajına hazırlanmak istiyorum", b) == {"kind": "blok", "block": "Y5R1", "student_year": None}
    assert parse_request("Y3B3 ve Y3B4 sınavına nasıl çalışmalıyım?", b)["blocks"] == ["Y3B3", "Y3B4"]
    assert parse_request("4. sınıf yıl planı öner", b) == {"kind": "yıl", "year": 4}


def test_block_pathway_labels_and_order():
    e = default_engine(); e.set_reviews(set(), set())
    r = build(parse_request("Kardiyoloji stajına hazırlanmak istiyorum", e.blocks), e)
    assert {s["label"] for s in r["steps"]} <= {GEREKLI, TAZELE, TEKRAR}
    first = next(i for i, s in enumerate(r["steps"]) if s["block_id"] == "Y5R1")
    assert all(s["label"] == TAZELE for s in r["steps"][:first])
    assert any(s["topic"] == "stroke" for s in r["steps"] if s["label"] == TAZELE)


@pytest.fixture
def client(svc):
    svc.ensure_admin("dev-admin-token")
    mimar_routes.set_service(svc)
    default_engine().set_reviews(set(), set())
    with TestClient(app) as c:
        yield c, svc
    default_engine().set_reviews(set(), set())
    mimar_routes.set_service(None)


def _experts(c):
    A = {"Authorization": "Bearer dev-admin-token"}
    toks = []
    for u in ("uzman1", "uzman2"):
        toks.append({"Authorization": "Bearer " + c.post("/api/v1/mimar/users", headers=A,
                     json={"username": u, "display_name": u, "roles": ["expert"]}).json()["token"]})
    return toks


def test_pathway_is_shown_directly_as_preview(client):
    c, _ = client
    r = c.post("/api/v1/chat", json={"query": "Kardiyoloji stajına hazırlanmak istiyorum"}).json()
    assert r["query_type"] == "pathway" and "Önce tazele" in r["answer"] and "Önizleme" in r["answer"] and r["pathway"]


def test_rejected_link_disappears_from_pathway(client):
    c, _ = client
    E1, E2 = _experts(c)
    links = c.get("/api/v1/pathway/expert/links", headers=E1).json()
    target = next(l for l in links if l["late"]["block"].startswith("Y5R1") and l["early"]["topic"] == "stroke")
    before = c.post("/api/v1/chat", json={"query": "Kardiyoloji stajına hazırlanmak istiyorum"}).json()["answer"]
    assert "- stroke [Y3B1]" in before
    assert c.post(f"/api/v1/pathway/expert/links/{target['id']}", headers=E1,
                  json={"decision": "uygun_degil", "wrong_kind": "ilgisiz", "note": "test"}).status_code == 200
    mid = c.post("/api/v1/chat", json={"query": "Kardiyoloji stajına hazırlanmak istiyorum"}).json()["answer"]
    assert "- stroke [Y3B1]" in mid                 # one expert alone does not decide
    assert c.post(f"/api/v1/pathway/expert/links/{target['id']}", headers=E2,
                  json={"decision": "uygun_degil", "wrong_kind": "ilgisiz", "note": "test"}).status_code == 200
    after = c.post("/api/v1/chat", json={"query": "Kardiyoloji stajına hazırlanmak istiyorum"}).json()["answer"]
    assert "- stroke [Y3B1]" not in after
    assert c.post(f"/api/v1/pathway/expert/links/{target['id']}", headers=E1,
                  json={"decision": "uygun_degil"}).status_code == 422          # kind required


def test_release_gate(client):
    c, _ = client
    E1, E2 = _experts(c)
    s = c.get("/api/v1/pathway/expert/summary", headers=E1).json()
    assert not s["released"] and set(s["conditions"]) == {"links", "critical", "paths", "agreement"}
    links = c.get("/api/v1/pathway/expert/links", headers=E1).json()
    for E in (E1, E2):
        for i, l in enumerate(links):
            dec = "uygun" if i % 12 else "uygun_degil"           # ~92 % agree
            c.post(f"/api/v1/pathway/expert/links/{l['id']}", headers=E,
                   json={"decision": dec, "wrong_kind": "ilgisiz" if dec != "uygun" else ""})
        for p in c.get("/api/v1/pathway/expert/paths", headers=E).json():
            c.post(f"/api/v1/pathway/expert/paths/{p['id']}", headers=E, json={"decision": "uygun"})
    s = c.get("/api/v1/pathway/expert/summary", headers=E1).json()
    assert s["agreement"]["ac1"] == 1.0 and s["paths"]["ok_rate"] == 1.0
    assert s["conditions"]["paths"] and s["conditions"]["agreement"] and s["conditions"]["critical"]
    r = c.post("/api/v1/chat", json={"query": "4. sınıf yıl planı öner"}).json()
    assert ("Uzman değerlendirmesinden geçmiş" in r["answer"]) == s["released"]


def test_rejected_repetition_is_explained_and_shown_first():
    from app.pathway.planner import default_engine, build, parse_request, GEREKLI
    from app.pathway.review import render_pathway
    e = default_engine()
    link = next(l for l in e.all_links() if l["type"] == "tekrar")
    early, late = link["early"], link["late"]
    e.set_reviews({frozenset((early.id, late.id))}, set())
    try:
        lab, why, _ = e._classify(late)
        assert lab == GEREKLI and "Uzman değerlendirmesine göre" in why
        p = build({"kind": "blok", "block": late.block_id, "student_year": None}, e)
        txt = render_pathway(p, False)
        g = txt.split("2) Gerekli")[1]
        assert g.index(late.text) < g.index("ilk kez bu blokta") if "ilk kez bu blokta" in g else True
    finally:
        e.set_reviews(set(), set())


def test_every_repetition_is_reviewed_first(monkeypatch):
    from app.mimar.service import MimarService
    from app.mimar.store import Store
    from app.pathway.planner import default_engine
    from app.pathway.review import ExpertReview
    rev = ExpertReview(MimarService(Store(":memory:")).store)
    q = rev.link_queue("uzman")
    n_rep = sum(1 for l in default_engine().all_links() if l["type"] == "tekrar")
    assert [l["type"] for l in q[:n_rep]] == ["tekrar"] * n_rep          # all repetitions, first
    assert all(l["origin"] == "tam" for l in q[:n_rep])
    assert any(l["origin"] == "örnek yol" for l in q)
    assert rev.summary()["per_type"]["ilişkili"]["sampled"] <= 30


def test_after_release_unreviewed_suggestions_are_labelled():
    from app.pathway.planner import build, default_engine
    e = default_engine()
    p0 = build({"kind": "blok", "block": "Y3B1", "student_year": None}, e)
    ref = [s for s in p0["steps"] if s["label"] == "once_tazele"]
    assert ref and not any("uzman onayı yok" in s["reason"] for s in ref)
    e.released = True
    try:
        p1 = build({"kind": "blok", "block": "Y3B1", "student_year": None}, e)
        assert all("uzman onayı yok" in s["reason"] for s in p1["steps"] if s["label"] == "once_tazele")
    finally:
        e.released = False
