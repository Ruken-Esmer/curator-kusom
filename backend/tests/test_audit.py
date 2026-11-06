"""Accreditation scenario: osteoarthritis across the programme."""
import pytest

from app.data.kusom import curriculum as kusom

pytestmark = pytest.mark.skipif(not kusom.available(), reason="KUSOM data not imported")

Q = ["Osteoartrit hangi sınıflarda, hangi bloklarda veya stajlarda öğretiliyor?",
     "Osteoartritle ilgili öğrenme hedefleri neler?",
     "Tekrar eden hedefler var mı? Varsa bu hedefleri, bulundukları sınıf ve blok/staj bilgileriyle yan yana göster.",
     "UÇEP’te osteoartrit için beklenen bilgi ve beceriler arasında, müfredatımızdaki öğrenme hedeflerinde karşılığı bulunmayanlar var mı?"]


def test_topic_is_found_by_longest_name():
    from app.audit.topic_audit import find_topic
    assert find_topic(Q[0])["no"] == 237            # osteoartrit, not "artrit"
    assert find_topic("Romatoid artrit nerede?")["no"] == 275
    assert find_topic("Kalp yetersizliği hangi sınıfta?")["no"] == 169


def test_where_taught():
    from app.audit.topic_audit import find_topic, where_taught
    w = where_taught(find_topic(Q[0]))
    assert w["years"] == [3, 5]
    assert {r["block"] for r in w["direct"]} == {"MSKL 303", "MSKL 503"}


def test_objectives_are_reported_missing_not_invented():
    from app.audit.topic_audit import find_topic, objectives
    o = objectives(find_topic(Q[0]))
    assert o["objectives"] == [] and o["teaching_blocks_without_objectives"] == ["MSKL 303", "MSKL 503"]


def test_repetitions_side_by_side():
    from app.audit.topic_audit import find_topic, repetitions
    r = repetitions(find_topic(Q[0]))
    rel = {(p["early"]["block"], p["late"]["block"], p["relation"]) for p in r["pairs"]}
    assert ("MSKL 303", "MSKL 503", "derinleşme") in rel
    assert ("MSKL 503", "MSKL 503", "pekiştirme") in rel
    assert ("MSKL 303", "IMED 410", "olası tekrar") in rel


def test_ucep_alignment():
    from app.audit.topic_audit import find_topic, ucep_alignment
    u = {r["level"]: r["status"] for r in ucep_alignment(find_topic(Q[0]))["rows"]}
    assert u == {"TT-tanı": "ders başlığında var", "TT-tedavi": "ders başlığında var", "K": "dolaylı",
                 "İ": "karşılığı bulunamadı"}


def test_scenario_in_chat_with_follow_up_questions(monkeypatch):
    from fastapi.testclient import TestClient
    import app.data.curriculum.source as src
    from app.main import app
    monkeypatch.setattr(src, "active_source", lambda: "kusom")
    c = TestClient(app)
    hist, answers = [], []
    for q in Q:
        out = c.post("/api/v1/chat", json={"query": q, "conversation_history": hist}).json()
        assert out["query_type"] == "audit", q
        answers.append(out["answer"])
        hist += [{"role": "user", "content": q}, {"role": "assistant", "content": out["answer"]}]
    assert "MSKL 303" in answers[0] and "yazılı bir hedef yok" in answers[1]
    assert "olası tekrar" in answers[2] and "izlem" in answers[3]


def test_topic_report_answers_the_four_questions_at_once(monkeypatch):
    from fastapi.testclient import TestClient
    import app.api.routes.audit as audit_routes
    from app.main import app
    monkeypatch.setattr(audit_routes, "active_source", lambda: "kusom")
    c = TestClient(app)
    r = c.get("/api/v1/audit/report", params={"q": "Osteoartrit"}).json()
    assert r["topic"]["no"] == 237 and r["topic"]["curated"]
    assert r["where"]["years"] == [3, 5]
    assert r["objectives"]["items"] == [] and r["objectives"]["missing_docs"] == ["MSKL 303", "MSKL 503"]
    assert r["repetitions"]["counts"]["olası tekrar"] == 1
    assert {x["level"]: x["status"] for x in r["ucep"]["rows"]}["İ"] == "karşılığı bulunamadı"
    assert c.get("/api/v1/audit/report", params={"q": "diyabet"}).json()["topic"]["name"].startswith("Diabetes")
    assert c.get("/api/v1/audit/report", params={"q": "yok böyle bir konu"}).status_code == 404
    assert any(t["name"] == "Osteoartrit" for t in c.get("/api/v1/audit/topics").json())


def test_plain_answers_are_short_turkish_sentences():
    from app.audit import topic_audit as ta
    p = ta.topic_report(ta.find_topic("Osteoartrit"))["plain"]
    assert p["where"]["text"].startswith("3. sınıfta MSKL 303")
    assert "eklem ağrısı olan hastaya yaklaşım" in p["repetitions"]["text"]
    assert "Uzun süreli izlem hiçbir derste yok" in p["ucep"]["text"] and p["ucep"]["flag"] == "1 eksik"
    # topics without a hand-made profile do not get repetition or UÇEP verdicts
    a = ta.topic_report(ta.find_topic("Astım"))["plain"]
    assert a["repetitions"]["flag"] == "incelenmedi" and a["ucep"]["flag"] == "hazırlanmadı"


def test_osteoarthritis_scenario_through_work_packages(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.routes import audit as audit_routes
    from app.main import app
    monkeypatch.setattr(audit_routes, "active_source", lambda: "kusom")
    d = TestClient(app).get("/api/v1/audit/scenario/osteoartrit").json()
    assert d["t0"]["topic"]["no"] == 237
    assert len(d["wp1"]["oa_titles"]) == 3
    # the pair from the hand-made match is not among the automatic results: the "expert only" case
    assert d["wp1"]["expert_pair_rank"] is None
    assert d["wp4"]["titles"] > d["wp1"]["titles"] and d["wp4"]["redundancy"] > 0
    assert d["wp4"]["diseases_with_profile"] == 1
