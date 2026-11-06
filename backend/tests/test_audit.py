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
