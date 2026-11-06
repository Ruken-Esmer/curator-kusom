"""Data import and quality control (application §2.1–2.2)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from typing import Any

from app.mimar.text import normalized_key, tokenize

LO_ALIASES = {
    "uid": ["uid", "lo_id", "id", "objective_id", "hedef_id", "kimlik"],
    "text": ["text", "objective", "learning_objective", "lo_text", "hedef", "hedef_metni", "ogrenme_hedefi"],
    "course": ["course", "block", "ders", "blok", "course_name"],
    "session": ["session", "session_title", "oturum", "oturum_basligi", "ders_oturum"],
    "activity": ["activity", "activity_id", "etkinlik", "etkinlik_id"],
    "year": ["year", "class_year", "sinif", "yil", "grade"],
    "term": ["term", "period", "donem", "academic_term"],
    "source": ["source", "kaynak", "record_source"],
    "discipline": ["discipline", "department", "disiplin", "anabilim_dali"],
    "mesh": ["mesh", "mesh_terms", "mesh_terimleri"],
    "mesh_verified": ["mesh_verified", "mesh_dogrulandi"],
    "ucep_codes": ["ucep_codes", "ucep", "ucep_kodlari"],
    "competencies": ["competencies", "yetkinlikler"],
    "updated_at": ["updated_at", "guncelleme", "last_updated"],
}

UCEP_ALIASES = {
    "code": ["code", "kod", "ucep_code", "id"],
    "text_tr": ["text_tr", "metin_tr", "turkce", "tr"],
    "text_en": ["text_en", "metin_en", "english", "en"],
    "domain": ["domain", "alan", "kategori", "category"],
    "mskl_scope": ["mskl_scope", "mskl", "in_scope", "kapsam"],
}

MIN_CONTENT_TOKENS = 3


def _norm_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_").replace("-", "_") \
        .replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")


def _map_row(row: dict[str, Any], aliases: dict[str, list[str]]) -> dict[str, Any]:
    normed = {_norm_header(k): v for k, v in row.items()}
    out: dict[str, Any] = {}
    for field, names in aliases.items():
        for n in names:
            if n in normed and normed[n] not in (None, ""):
                out[field] = normed[n]
                break
    return out


def _split_list(v: Any) -> list[str]:
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace("|", ";").split(";") if x.strip()]


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "evet", "y", "e", "x"}


def parse_table(content: bytes, filename: str) -> list[dict[str, Any]]:
    """CSV, TSV, XLSX or JSON (list of objects) → list of dict rows."""
    name = filename.lower()
    if name.endswith(".json"):
        data = json.loads(content.decode("utf-8-sig"))
        return data if isinstance(data, list) else data.get("rows", [])
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(h) if h is not None else "" for h in rows[0]]
        return [dict(zip(header, r)) for r in rows[1:] if any(c is not None for c in r)]
    text = content.decode("utf-8-sig")
    dialect = "excel-tab" if name.endswith(".tsv") else csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


def prepare_learning_objectives(rows: list[dict[str, Any]], default_source: str = "",
                                min_tokens: int = MIN_CONTENT_TOKENS) -> dict[str, Any]:
    """Map, validate and QC raw rows."""
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_in_activity: dict[tuple[str, str], str] = {}
    cross_activity_dups: dict[str, list[str]] = defaultdict(list)
    mesh_dropped = 0

    for idx, raw in enumerate(rows, start=1):
        r = _map_row(raw, LO_ALIASES)
        text = str(r.get("text") or "").strip()
        uid = str(r.get("uid") or "").strip()
        rec = {
            "row": idx, "uid": uid, "text": text,
            "course": str(r.get("course") or "").strip(),
            "session": str(r.get("session") or "").strip(),
            "activity": str(r.get("activity") or "").strip(),
            "year": int(float(r["year"])) if str(r.get("year") or "").strip().replace(".", "", 1).isdigit() else 0,
            "term": str(r.get("term") or "").strip(),
            "source": str(r.get("source") or default_source).strip(),
            "discipline": str(r.get("discipline") or "").strip(),
            "ucep_links": _split_list(r.get("ucep_codes")),
            "competencies": _split_list(r.get("competencies")),
            "updated_at": str(r.get("updated_at") or "").strip(),
        }
        mesh = _split_list(r.get("mesh"))
        if mesh and "mesh_verified" in r and not _truthy(r["mesh_verified"]):
            mesh_dropped += len(mesh)
            mesh = []
        elif mesh and "mesh_verified" not in r:
            mesh_dropped += len(mesh)       # unverified by default → not used
            mesh = []
        rec["mesh"] = mesh
        if not rec["activity"] and rec["session"]:
            rec["activity"] = hashlib.sha1(f"{rec['course']}|{rec['session']}".encode()).hexdigest()[:10]
            warnings.append({"row": idx, "uid": uid, "warning": "activity_derived_from_course_session"})

        reason = None
        if not text:
            reason = "empty_text"
        elif not uid:
            reason = "missing_persistent_id"
        elif uid in seen_ids:
            reason = "duplicate_id"
        elif not rec["source"]:
            reason = "missing_source"
        elif not rec["activity"]:
            reason = "missing_activity"
        elif len(tokenize(text)) < min_tokens:
            reason = "not_reviewable_too_short"
        else:
            key = (rec["activity"], normalized_key(text))
            if key in seen_in_activity:
                reason = "duplicate_text_in_same_activity"
                rec["duplicate_of"] = seen_in_activity[key]
        if reason:
            excluded.append({**rec, "reason": reason})
            continue
        seen_ids.add(uid)
        seen_in_activity[(rec["activity"], normalized_key(text))] = uid
        cross_activity_dups[normalized_key(text)].append(uid)
        included.append(rec)

    identical_across = {k: v for k, v in cross_activity_dups.items() if len(v) > 1}
    report = {
        "rows_received": len(rows),
        "included": len(included),
        "excluded": len(excluded),
        "exclusion_reasons": dict(Counter(e["reason"] for e in excluded)),
        "warnings": dict(Counter(w["warning"] for w in warnings)),
        "unverified_mesh_terms_dropped": mesh_dropped,
        "identical_text_across_activities_kept": sum(len(v) for v in identical_across.values()),
        "by_year": dict(sorted(Counter(r["year"] for r in included).items())),
        "by_course": dict(Counter(r["course"] for r in included).most_common()),
        "activities": len({r["activity"] for r in included}),
        "note": "Similar objectives in different courses are retained (§2.2).",
    }
    return {"included": included, "excluded": excluded, "warnings": warnings, "report": report}


def prepare_ucep(rows: list[dict[str, Any]]) -> dict[str, Any]:
    included, excluded = [], []
    seen = set()
    for idx, raw in enumerate(rows, start=1):
        r = _map_row(raw, UCEP_ALIASES)
        code = str(r.get("code") or "").strip()
        rec = {"row": idx, "code": code, "text_tr": str(r.get("text_tr") or "").strip(),
               "text_en": str(r.get("text_en") or "").strip(), "domain": str(r.get("domain") or "").strip(),
               "mskl_scope": _truthy(r.get("mskl_scope", "1"))}
        if not code:
            excluded.append({**rec, "reason": "missing_code"})
        elif code in seen:
            excluded.append({**rec, "reason": "duplicate_code"})
        elif not rec["text_tr"]:
            excluded.append({**rec, "reason": "missing_original_turkish_text"})
        else:
            if not rec["text_en"]:
                rec["translation_status"] = "missing_expert_checked_english"
            seen.add(code)
            included.append(rec)
    return {"included": included, "excluded": excluded,
            "report": {"rows_received": len(rows), "included": len(included), "excluded": len(excluded),
                       "missing_english": sum(1 for r in included if not r["text_en"]),
                       "mskl_scope": sum(1 for r in included if r["mskl_scope"])}}
