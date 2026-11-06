"""Topic report for accreditation reviewers (prefix /api/v1/audit)."""
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.audit import topic_audit as ta
from app.data.curriculum.source import active_source

router = APIRouter(prefix="/audit", tags=["audit"])


def _need_kusom() -> None:
    if active_source() != "kusom":
        raise HTTPException(409, "Konu incelemesi yalnız KUSOM verisiyle çalışır.")


@lru_cache(maxsize=1)
def _names() -> list[dict]:
    return ta.topic_names()


@router.get("/topics")
def topics():
    _need_kusom()
    return _names()


@router.get("/report")
def report(q: str):
    _need_kusom()
    item = ta.find_topic(q)
    if item is None:
        raise HTTPException(404, f"“{q}” UÇEP-2020 çekirdek hastalık listesinde bulunamadı.")
    return ta.topic_report(item)


@router.get("/scenario/osteoartrit")
def osteoarthritis_scenario():
    """Osteoarthritis through the six work packages: the computed parts (first call takes ~15 s, then cached)."""
    _need_kusom()
    from app.audit.scenario import scenario
    return scenario()
