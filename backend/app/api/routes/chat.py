"""CURATOR — Chat / Query endpoint."""
import time

from fastapi import APIRouter, HTTPException
from langdetect import detect, LangDetectException

from app.core.logging import logger
from app.models.schemas import Language, PathwayStep, QueryRequest, QueryResponse, QueryType
from app.rag.pipeline import run_pipeline

router = APIRouter()


def _detect_language(text: str, hint: Language) -> Language:
    try:
        code = detect(text)
        return Language.TR if code == "tr" else Language.EN
    except LangDetectException:
        return hint


@router.post("/chat", response_model=QueryResponse, summary="Query the curriculum RAG pipeline")
async def chat(request: QueryRequest) -> QueryResponse:
    """
    Submit a natural language query about the KU SOM curriculum.
    Language is auto-detected from the query text.
    """
    lang = _detect_language(request.query, request.language)
    pw = _pathway_answer(request.query, lang)
    if pw is not None:
        return pw
    logger.info("chat.request", query=request.query[:80], lang=lang, institution=request.institution)

    try:
        response = await run_pipeline(
            query=request.query,
            language=lang,
            institution=request.institution,
            conversation_history=[m.model_dump() for m in request.conversation_history],
        )
    except Exception as exc:
        logger.error("chat.error", error=str(exc))
        raise HTTPException(status_code=500, detail="Pipeline error") from exc

    logger.info("chat.response",
                query_type=response.query_type,
                citations=len(response.citations),
                ms=response.processing_time_ms)
    return response


#  Learning pathways (shown directly; quality assured by expert review
#  during development — see app.pathway.review)

def _pathway_answer(query: str, lang: Language) -> QueryResponse | None:
    from app.api.routes.mimar import get_service
    from app.pathway.planner import build, default_engine, is_pathway_request, parse_request
    from app.pathway.review import ExpertReview, render_pathway

    if not is_pathway_request(query):
        return None
    t0 = time.monotonic()
    e = default_engine()
    parsed = parse_request(query, e.blocks, e.aliases)
    rev = ExpertReview(get_service().store)
    rev._refresh_engine()                       # apply expert decisions
    p = build(parsed, e)
    steps: list[PathwayStep] = []
    if p is None:
        answer = ("Öğrenme yolu hazırlayabilmem için hedefini belirtir misin? Örnekler:\n"
                  "- “Kardiyoloji stajına hazırlanmak istiyorum”\n"
                  + ("- “RESP 313 ve CARD 314 sınavına nasıl çalışmalıyım?”\n" if getattr(e, "source", "") == "kusom"
                     else "- “Y3B3 ve Y3B4 sınavına nasıl çalışmalıyım?”\n") +
                  "- “4. sınıf yıl planı öner”")
    else:
        released = rev.summary()["released"]
        answer = render_pathway(p, released)
        seen: list[str] = []
        for s in p["steps"]:
            if s["block_id"] not in seen:
                seen.append(s["block_id"])
                steps.append(PathwayStep(order=len(seen), block_id=s["block_id"], block_name=s["block_name"],
                                         year=s["year"], reason=s["label_tr"]))
    return QueryResponse(answer=answer, query_type=QueryType.PATHWAY, pathway=steps, language=lang,
                         processing_time_ms=round((time.monotonic() - t0) * 1000, 1))
