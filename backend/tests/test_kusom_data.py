"""Real KUSOM 2025–2026 data: import, curriculum shape, pathways."""
import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.data.kusom import curriculum as loader
from app.data.kusom.parse_timetables import classify, normalize_title

pytestmark = pytest.mark.skipif(not loader.available(), reason="KUSOM data not imported")


@lru_cache(maxsize=1)
def engine():
    from app.pathway.planner import PathwayEngine, items_from_curriculum
    items, blocks = items_from_curriculum(loader.kusom_curriculum(), loader.phase_of)
    e = PathwayEngine(items, blocks)
    e.aliases, e.source = loader.ALIASES, "kusom"
    e.derive_prerequisites()
    return e


def test_title_cleaning_and_session_kinds():
    assert normalize_title("Red blood cells-I") == "Red blood cells"
    assert normalize_title("Hemostasis I – II") == "Hemostasis"
    assert normalize_title("LAB: (Histology) /The respiratory system (Group I)") == "The respiratory system"
    assert normalize_title("Global Health Challenges/ATTENDANCE IS MANDATORY") == "Global Health Challenges"
    assert classify("LUNCH") == "öğle arası" and classify("Study Time") == "bireysel çalışma"
    assert classify("CUMHURİYET BAYRAMI") == "tatil" and classify("MSKL exam evaluation") == "sınav"
    assert classify("CBD: Stuttering") == "vaka tartışması" and classify("LAB: ECG") == "laboratuvar"


def test_data_set_quality_report():
    d = loader.load()
    q = d["qc"]
    assert q["years_present"] == [2, 3, 4, 5] and q["years_missing"] == [1, 6]
    assert q["objectives"] > 900 and q["objectives_unmatched_to_timetable"] < 20
    assert {"sheet": "NRVD 308", "file": "YEAR 3-CURRICULUM 2025-2026.xlsx", "contains": "ERUD 306"} in q["duplicate_sheets"]
    # no student list is ever read
    assert all("Öğrenci" not in s["subject"] for s in d["sessions"][:50])
    text = json.dumps(d, ensure_ascii=False)
    assert "Öğrenci List" not in text and "Student Dist" not in text


def test_curriculum_shape_matches_application():
    cur = loader.kusom_curriculum()
    ids = [b["id"] for y in cur for b in y["blocks"]]
    assert {"CIRC204", "CARD314", "IMED410", "NEUR512"} <= set(ids)
    circ = next(b for y in cur for b in y["blocks"] if b["id"] == "CIRC204")
    assert circ["topics"] and any(d["objectives"] for d in circ["topic_details"])
    assert {"id", "name_tr", "name_en", "weeks", "departments", "topics", "prerequisite_ids"} <= set(circ)


def test_aliases_and_codes_on_real_blocks():
    from app.pathway.planner import parse_request
    e = engine()
    assert parse_request("İç hastalıkları stajına hazırlanmak istiyorum", e.blocks, e.aliases)["block"] == "IMED410"
    assert parse_request("CARD 314 bloğuna hazırlanmak istiyorum", e.blocks, e.aliases)["block"] == "CARD314"
    assert parse_request("5. sınıf kas iskelet stajına hazırlanmak istiyorum", e.blocks, e.aliases)["block"] == "MSKL503"
    p = parse_request("RESP 313 ve CARD 314 sınavına hazırlanmak istiyorum", e.blocks, e.aliases)
    assert p["kind"] == "sınav" and p["blocks"] == ["RESP313", "CARD314"]


def test_basic_science_seen_again_in_clinic_is_not_called_repetition():
    e = engine()
    nmj = next(i for i in e.items if i.block_id == "NEUR512" and "neuromuscular junction" in i.text.lower())
    from app.pathway.planner import GEREKLI
    label, why, refs = e._classify(nmj)
    assert label == GEREKLI and refs and refs[-1].block_id == "MSKL202"


def test_block_pathway_refreshes_year2_basis_for_cardiology():
    from app.pathway.planner import build, parse_request
    e = engine()
    p = build(parse_request("CARD 314 bloğuna hazırlanmak istiyorum", e.blocks, e.aliases), e)
    refresh = [s for s in p["steps"] if s["label"] == "once_tazele"]
    assert refresh and refresh[0]["block_id"] == "CIRC204"
    assert "CIRC204" in e.blocks["CARD314"]["prereq"]
    assert all(s["block_id"] == "CARD314" for s in p["steps"] if s["label"] != "once_tazele")


def test_mimar_kusom_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    bl = c.get("/api/v1/mimar/kusom/blocks").json()
    assert bl["available"] and any(b["id"] == "CIRC204" and b["objectives"] > 100 for b in bl["blocks"])
    rows = c.get("/api/v1/mimar/kusom/los", params={"blocks": "CIRC204,CARD314"}).json()["rows"]
    assert any(r["from"] == "öğrenim hedefi" for r in rows) and any(r["course"] == "CARD 314" for r in rows)
    out = c.post("/api/v1/mimar/analyze", json={"los": rows[:400]}).json()
    assert out["input_check"]["used"] > 300


def test_template_parallel_objectives_are_not_redundancy():
    from app.mimar.report import _parallel
    assert _parallel(["Calculate the normal filtered load of Na+.", "Calculate the normal filtered load of K+."])
    assert _parallel(["Describe the male genital system", "Describe the female genital system"]) == ["male", "female"]
    assert _parallel(["State and explain the glycogen storage diseases",
                      "Describe the various types of glycogen storage diseases"]) == []


def test_year2_objectives_give_few_credible_repetitions():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.mimar.report import integrated_analysis
    c = TestClient(app)
    rows = c.get("/api/v1/mimar/kusom/los", params={"blocks": "CIRC204,NUTI205,ERUS206"}).json()["rows"]
    out = integrated_analysis(rows)
    texts = [" | ".join(o["text"] for o in f["objectives"]) for f in out["findings"] if f["category"] == "redundancy"]
    assert 1 <= len(texts) <= 15
    assert any("glycogen storage" in t for t in texts)
    assert out["parallel"]                       # Na+/K+, male/female … recognised as different content


def test_same_year_clerkships_are_not_assumed_to_come_first():
    """Year-4 groups rotate through IMED, PEDI, SURG, OBGY in different orders."""
    from app.pathway.planner import TEKRAR, build, parse_request
    e = engine()
    p = build(parse_request("Pediatri stajına hazırlanmak istiyorum", e.blocks, e.aliases), e)
    assert not any(s["label"] == TEKRAR and "IMED410" in s["reason"] for s in p["steps"])
    assert any("rotasyon" in s["reason"] for s in p["steps"])
    assert not any(s["label"] == "once_tazele" and s["block_id"] in {"IMED410", "SURG401", "OBGY404"} for s in p["steps"])
