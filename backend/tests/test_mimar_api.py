"""HTTP-level tests of the MİMAR router (authentication, roles, workflow)."""
import pytest
from fastapi.testclient import TestClient

from app.api.routes import mimar as mimar_routes
from app.main import app


@pytest.fixture
def client(svc):
    svc.ensure_admin("dev-admin-token")
    mimar_routes.set_service(svc)
    with TestClient(app) as c:
        yield c
    mimar_routes.set_service(None)


A = {"Authorization": "Bearer dev-admin-token"}


def test_auth_required(client):
    assert client.get("/api/v1/mimar/me").status_code == 401
    assert client.get("/api/v1/mimar/me", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/v1/mimar/me", headers=A).json()["roles"] == ["admin"]


def test_demo_and_role_views(client):
    r = client.post("/api/v1/mimar/demo/run?quick=true", headers=A)
    assert r.status_code == 200, r.text
    users = r.json()["users"]
    rev = {"Authorization": f"Bearer {users['rev1']}"}
    tech = {"Authorization": f"Bearer {users['tech']}"}
    # reviewer sees tasks but not the audit log; technical cannot unseal pools
    assert any(t["role"] == "reviewer" for t in client.get("/api/v1/mimar/samples/mine", headers=rev).json())
    assert client.get("/api/v1/mimar/audit", headers=rev).status_code == 403
    pools = client.get("/api/v1/mimar/pools", headers=A).json()
    assert client.post(f"/api/v1/mimar/pools/{pools[0]['id']}/as2a", headers=tech).status_code == 403
    ov = client.get("/api/v1/mimar/overview", headers=A).json()
    assert ov["audit"]["valid"] and ov["as1_samples"]["test"] == 1


def test_upload_and_protocol_errors_map_to_http(client):
    etok = client.post("/api/v1/mimar/users", headers=A,
                       json={"username": "e", "display_name": "E", "roles": ["expert"]}).json()["token"]
    ds = client.post("/api/v1/mimar/datasets", headers={"Authorization": f"Bearer {etok}"}, json={"name": "x"})
    assert ds.status_code == 403                               # experts cannot write curriculum data
    tok = client.post("/api/v1/mimar/users", headers=A,
                      json={"username": "t", "display_name": "T", "roles": ["technical"]}).json()["token"]
    T = {"Authorization": f"Bearer {tok}"}
    ds = client.post("/api/v1/mimar/datasets", headers=T, json={"name": "x"}).json()
    csv = "uid,text,course,activity,year,source\nL1,Describe the anatomy of the rotator cuff muscles.,C1,a1,2,s\n" \
          "L2,Identify the rotator cuff muscles and their nerve supply.,C2,a2,2,s\nL3,Explain fracture healing stages.,C3,a3,3,s\n"
    r = client.post(f"/api/v1/mimar/datasets/{ds['id']}/los/upload", headers=T,
                    files={"file": ("los.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["included"] == 3
    cfg = client.post("/api/v1/mimar/configs", headers=T, json={"name": "c", "params": {}}).json()
    r = client.post("/api/v1/mimar/analyses", headers=T, json={"dataset_id": ds["id"], "config_id": cfg["id"]})
    assert r.status_code == 409 and "frozen" in r.json()["detail"]
    assert client.post(f"/api/v1/mimar/datasets/{ds['id']}/freeze", headers=A).status_code == 200
    r = client.post("/api/v1/mimar/analyses", headers=T, json={"dataset_id": ds["id"], "config_id": cfg["id"]})
    assert r.status_code == 200
    csvr = client.get(f"/api/v1/mimar/analyses/{r.json()['id']}/export.csv", headers=T)
    assert csvr.status_code == 200 and csvr.text.startswith("rank,lo_a,lo_b")


def test_stats_endpoints(client):
    p = client.post("/api/v1/mimar/stats/power", headers=A, json={"ns": [50, 200], "sims": 200}).json()
    assert p[1]["power"] >= p[0]["power"]
    a = client.post("/api/v1/mimar/stats/agreement", headers=A, json={"rater1": ["a", "b"], "rater2": ["a", "b"]}).json()
    assert a["ac1"] == 1.0


def test_playground_input_output(client):
    los = [{"uid": "A", "text": "Explain the mechanism of action and adverse effects of NSAIDs.", "activity": "a", "source": "s", "year": 3, "course": "Farm"},
           {"uid": "B", "text": "Describe the adverse effects and mechanism of action of NSAIDs.", "activity": "b", "source": "s", "year": 5, "course": "Rom"},
           {"uid": "C", "text": "Describe the boundaries and contents of the carpal tunnel.", "activity": "c", "source": "s", "year": 2, "course": "Anat"},
           {"uid": "D", "text": "", "activity": "d", "source": "s"}]
    r = client.post("/api/v1/mimar/playground/analyze", headers=A,
                    json={"los": los, "ucep": [{"code": "U1", "text_tr": "Gut", "text_en": "Diagnose gout"}], "depth": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["qc"]["excluded"] == 1 and d["pairs"][0]["a"]["uid"] in ("A", "B")
    assert any(u["status"] == "no_clear_correspondence" for u in d["ucep_map"])


def test_integrated_analyze_covers_all_questions_without_labels(client):
    L = [("A", 3, "Farm", "Explain the mechanism of action and adverse effects of NSAIDs."),
         ("B", 5, "Rom", "Describe the adverse effects and mechanism of action of NSAIDs."),
         ("C", 2, "Anat", "Describe the boundaries and contents of the carpal tunnel."),
         ("D", 5, "FTR", "Diagnose and manage carpal tunnel syndrome using clinical tests."),
         ("E", 2, "Fiz", "Explain the regulation of calcium by parathyroid hormone and vitamin D."),
         ("F", 3, "Pat", "Explain the control of serum calcium by parathyroid hormone and vitamin D.")]
    los = [{"uid": u, "year": y, "course": c, "text": t, "activity": u, "source": "s"} for u, y, c, t in L]
    r = client.post("/api/v1/mimar/analyze", json={"los": los, "ucep": [{"code": "U-GUT", "text_tr": "Gut", "text_en": "Make a preliminary diagnosis of gout"}]})
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("summary", "overlaps", "findings", "impact", "ucep", "reliability", "not_problems"):
        assert key in d
    cats = {f["category"] for f in d["findings"]}
    assert {"redundancy", "gap_ucep"} <= cats
    f0 = d["findings"][0]
    assert {"priority", "proposal", "questions"} <= set(f0)
    assert d["impact"]["ucep_gained"] == ["U-GUT"]
    txt = r.text
    assert not any(lbl in txt for lbl in ("AS1", "AS2", "AS3", "AS4", "AS5", "AS6", "H1", "H2a", "H5", "H6"))
