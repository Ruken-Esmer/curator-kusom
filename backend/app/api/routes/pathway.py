"""Expert review of the learning-pathway engine (prefix /api/v1/pathway/expert)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routes.mimar import current_user, get_service
from app.pathway.review import LINK_DECISIONS, PATH_DECISIONS, WRONG_KIND, ExpertReview

router = APIRouter(prefix="/pathway/expert", tags=["pathway-expert"])
REVIEW_ROLES = {"expert", "coordinator", "admin", "validator"}


def reviewer(user: dict = Depends(current_user)) -> dict:
    if not REVIEW_ROLES & set(user["roles"]):
        raise HTTPException(403, "yalnız uzmanlar değerlendirme yapabilir")
    return user


def svc() -> ExpertReview:
    return ExpertReview(get_service().store)


class LinkDecision(BaseModel):
    decision: str
    wrong_kind: str = ""
    note: str = ""


class PathDecision(BaseModel):
    decision: str
    note: str = ""


@router.get("/options")
def options():
    return {"link": LINK_DECISIONS, "path": PATH_DECISIONS, "wrong_kind": WRONG_KIND}


@router.get("/links")
def links(user: dict = Depends(reviewer)):
    return svc().link_queue(user["username"])


@router.post("/links/{link_id}")
def review_link(link_id: str, body: LinkDecision, user: dict = Depends(reviewer)):
    try:
        return svc().review_link(user["username"], link_id, body.decision, body.wrong_kind, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except KeyError:
        raise HTTPException(404, "bağlantı bulunamadı")


@router.get("/paths")
def paths(user: dict = Depends(reviewer)):
    return svc().path_queue(user["username"])


@router.post("/paths/{path_id}")
def review_path(path_id: str, body: PathDecision, user: dict = Depends(reviewer)):
    try:
        return svc().review_path(user["username"], path_id, body.decision, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except KeyError:
        raise HTTPException(404, "yol bulunamadı")


@router.get("/summary")
def summary(user: dict = Depends(reviewer)):
    return svc().summary()


@router.put("/thresholds")
def thresholds(body: dict[str, float], user: dict = Depends(current_user)):
    if "admin" not in user["roles"]:
        raise HTTPException(403, "eşikleri yalnız yönetici değiştirebilir")
    return svc().set_thresholds(user["username"], body)
