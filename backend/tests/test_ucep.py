"""UÇEP-2020 core disease list and its coverage in the KUSOM curriculum."""
import pytest

from app.data.kusom import curriculum as kusom
from app.data.ucep.match_ucep import _key, alternatives, coverage
from app.data.ucep.ucep_list import load, ucep_rows


def test_list_is_complete_and_well_formed():
    d = load()
    items = d["items"]
    assert len(items) == 342 and [i["no"] for i in items] == list(range(1, 343))
    assert all(i["text_tr"] and i["text_en"] and i["levels"] for i in items)
    assert set(l for i in items for l in i["levels"]) <= {"ÖnT", "T", "TT", "A", "K", "İ"}
    assert next(i for i in items if i["no"] == 169)["text_tr"] == "Kalp yetersizliği"
    assert len(ucep_rows()) == 342 and all(r["code"].startswith("UCEP2020-H") for r in ucep_rows())


def test_alternatives_and_keys():
    assert alternatives("Acute coronary syndromes and myocardial infarction") == ["acute coronary syndromes", "myocardial infarction"]
    assert alternatives("Head and neck tumors") == ["head and neck tumors"]
    assert len(_key("conversion disorder")) == 2      # a lone distinctive word keeps its context


@pytest.mark.skipif(not kusom.available(), reason="KUSOM data not imported")
def test_coverage_on_kusom():
    r = coverage(kusom.kusom_curriculum(), load()["items"], kusom.phase_of)
    by = {x["no"]: x for x in r["items"]}
    assert by[169]["status"] == "doğrudan" and "CARD 314" in by[169]["blocks"]      # heart failure
    assert by[123]["status"] == "doğrudan" and by[123]["years"] == [5]                # glaucoma, NEUR 512
    assert sum(r["summary"].values()) == 342
    assert r["summary"]["doğrudan"] > 120
