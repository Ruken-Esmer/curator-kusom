"""KUSOM 2025–2026 curriculum importer."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

OUT_DEFAULT = Path(__file__).with_name("kusom_2025_2026.json")

# Sheets whose name matches this are never opened (they hold student names).
STUDENT_SHEET = re.compile(r"(öğrenci|ogrenci|student|distribution|dağılım|bedside|case discuss|liste|list)", re.I)

HOUR = re.compile(r"^\s*\d{1,2}[.:]\d{2}\s*[-–]\s*\d{1,2}[.:]\d{2}")
CODE = re.compile(r"\b([A-Z]{4})\s*-?\s*(\d{3})\b")

# Session kinds.  Non-content kinds are kept in the timetable (hours, load)
# but are not curriculum topics.
NON_CONTENT = [
    ("öğle arası", r"\b(lunch|break|recess|öğle)\b"),
    ("bireysel çalışma", r"(study time|self[- ]?study|free time|reading time|self study|bireysel çalışma|serbest)"),
    ("sınav", r"(\bmini[- ]?c-?ex\b|\bwpba\b|\bnbme\b|\bexams?\b|exam evaluation|examination day|osce|\bquiz\b|assessment exam|\bsınav|final|midterm|feedback session|survey|bps-psa)"),
    ("tatil", r"(bayram|holiday|tatil|new year|yılbaşı|cumhuriyet|republic day)"),
    ("idari", r"(get together|meet(ing)? (with|the)|coordinator|introduction (of|to) (the )?(block|research program|[A-Z]{4})|"
              r"welcome|orientation|block evaluation|transaction time|ice breaker|wrap[- ]?up|dean'?s office|course evaluation|"
              r"^recaps?$|^discussion session$|clinical rotations?|^g\d+\s*-|\bmeeting\b|^research( day)?$|^(neurosurgery )?or$|"
              r"^emergency case\s*-?\s*\d+$|^journal club$|^presentation of|^daily evaluation|research( ?/ ?rmhs)? time|"
              r"^(case )?discussions?$|^clinical day|^struct?u?red bedside$|^pro-con session|#ref!|visit to|council of .* visit|"
              r"student presentations|ward rounds?|^review\b.*discussion t[ıi]me|alternating groups|^clinical skil+s$|"
              r"zoom$|^(sens|neur|mskl|card|resp|circ|nuti|erus|erud|nrvs|gind|neop|iicr|medi|psyt|form|obgy|pedi|surg|imed)\s*\([a-z ]+\)$|general review|^review( session)?$|^recap|^q ?& ?a$|^tutorial$)"),
    ("klinik uygulama", r"^(bedside|ward rounds?|outpatient( clinic)?|clinical practice|polyclinic|night shift|on[- ]call|"
                        r"operating room|surgery practice|bedside\s*/\s*outpatient clinic)\b"),
]
KIND_RULES = [
    ("laboratuvar", r"^(lab\b|laboratory|practical)|\blab\s*[:\-]"),
    ("PDÖ", r"\b(pbl|probleme dayalı|problem based learning)\b"),
    ("vaka tartışması", r"(case discussion|case-based|\bcbl\b|\bcbd\b|vaka|case presentation|clinical case)"),
    ("ters yüz sınıf", r"flipped classroom"),
    ("diseksiyon", r"^dissection\b"),
    ("beceri", r"(skill|simulation|workshop|practice\b|suture|catheter|bls|basic life support)"),
    ("panel", r"\bpanel\b"),
    ("seminer", r"(seminar|journal club|conference)"),
]


def _s(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def classify(subject: str) -> str:
    low = subject.lower()
    for kind, rx in NON_CONTENT:
        if re.search(rx, low, re.I):
            return kind
    for kind, rx in KIND_RULES:
        if re.search(rx, low, re.I):
            return kind
    return "ders"


_PREFIX = re.compile(r"^(\(?[a-z ]+\)\s*)?(group [a-z0-9]{1,2}|lab(oratory)?|cbl|cbd|pbl|panel|(interactive |[a-z]+ )?case discussion( on)?|seminar|"
                     r"skill room|lecture( by [^:]+)?|panopto|flipped classroom|dissection( session)?|problem based learning[^:]*|"
                     r"experiment|panel session|pbl session|case-based group practice|student case discussions?|"
                     r"structured bedside|group [a-z0-9]{1,2}(\s*[+&]\s*[a-z0-9]{1,2})*|"
                     r"basic science\s*-\s*[a-z]+|interactive lecture|video presentation)\s*[:\-–]\s*", re.I)
_NOISE = re.compile(r"(\s*-\s*case-based small group discussion$|(?<!age)(?<!age )\s*[-(]?\s*gro?u?p\s*[a-z0-9]{0,3}(\s*(&|\+|and)\s*[a-z0-9]{0,3})*\s*\)?\s*$|\s*/\s*attendance is mandatory|\s*/\s*zoom meeting|\s*[-(]\s*group\s*[a-z0-9]{0,3}\s*\)?$|\s*\(\s*group\s*[a-z0-9]{1,3}\s*\)|"
                    r"\(\s*(physiology|anatomy|histology|biochemistry|pharmacology|pathology|microbiology)\s*\)\s*/?\s*)", re.I)
_TAIL = re.compile(r"(\s*[-–]\s*(panopto|pre-?recorded|online|zoom)\b.*$|\s*\((q&a|online|panopto)\)\s*$|\s+l{1,2}i?\s*$|\s+part\s+[ivx\d]+\s*$)", re.I)
_SUFFIX = re.compile(r"(\s*[-–(]?\s*\b(i{1,3}|iv|v|vi{0,3}|[1-9])\b\s*\)?)+\s*$", re.I)
_PARTS = re.compile(r"\s*[-–]?\s*\b(i{1,3}|iv)\s*([-–&,/]\s*(i{1,3}|iv))+\b\s*$", re.I)


def normalize_title(subject: str) -> str:
    t = _NOISE.sub("", _s(subject))
    t = _NOISE.sub("", t)
    for _ in range(2):
        t = _PREFIX.sub("", t)
    t = _TAIL.sub("", t)
    t = _PARTS.sub("", t)
    t = _SUFFIX.sub("", t)
    t = t.strip(" -–:.,;/(")
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8 and len(t) > 6:
        t = t[:1].upper() + t[1:].lower()     # "CNS INFECTIONS" → "Cns infections"
        t = re.sub(r"\b(cns|pns|ecg|eeg|emg|copd|ent|icu|sle|hiv|dna|rna|std|uti|ckd|aki|gcs|mri|ct)\b",
                   lambda m: m.group(1).upper(), t, flags=re.I)
    return t


def topic_key(title: str) -> str:
    t = title.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9çğıöşü ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _date(v: Any) -> str | None:
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    m = re.match(r"^\s*(\d{1,2})[./](\d{1,2})[./](\d{4})", _s(v))
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


def _year_from_name(name: str, code: str | None) -> int | None:
    m = re.search(r"YEAR\s*(\d)|(\d)\s*(?:rd|nd|th)?\s*YEAR|D[öo#U00f6]*nem[- ]?(\d)", name, re.I)
    if m:
        return int(next(g for g in m.groups() if g))
    if code:
        return int(code[-3])
    return None


#  Timetables

def read_workbook(path: Path) -> list[dict[str, Any]]:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows_out: list[dict[str, Any]] = []
    for ws in wb.worksheets:
        if STUDENT_SHEET.search(ws.title):
            continue
        rows = list(ws.iter_rows(values_only=True))
        sheet_rows: list[dict[str, Any]] = []
        sheet_code = CODE.search(ws.title.upper().replace("İ", "I"))
        hdr: dict[str, int] = {}
        cur_date, group = None, ""
        for r in rows:
            cells = [_s(v) for v in r]
            up = [c.upper() for c in cells]
            if not hdr and any(c in ("SUBJECT", "PROGRAM NAME") for c in up):
                for i, c in enumerate(up):
                    if c in ("SUBJECT", "PROGRAM NAME"):
                        hdr.setdefault("subject", i)
                    elif c in ("LECTURER", "LECTURERS", "INSTRUCTOR"):
                        hdr.setdefault("lecturer", i)
                    elif c == "FIELD":
                        hdr.setdefault("field", i)
                    elif c == "SUBJECT TYPE":
                        hdr.setdefault("stype", i)
                    elif c == "BLOCK":
                        hdr.setdefault("block", i)
                continue
            gm = re.search(r"GRO?UP\s*([IVX\d]+)", " ".join(up))
            if gm and sum(1 for c in cells if c) <= 2:
                group = gm.group(1)
            for v in r:
                d = _date(v)
                if d:
                    cur_date = d
                    break
            hi = next((i for i, c in enumerate(cells) if HOUR.match(c)), None)
            if hi is None:
                continue
            if "subject" in hdr:
                subj = cells[hdr["subject"]] if hdr["subject"] < len(cells) else ""
                lect = cells[hdr["lecturer"]] if "lecturer" in hdr and hdr["lecturer"] < len(cells) else ""
            else:  # no header row (e.g. PSYT 513): subject and lecturer follow the time cell
                rest = [c for c in cells[hi + 1:] if c]
                subj, lect = (rest + ["", ""])[:2]
            if not subj:
                continue
            code = None
            if "block" in hdr and hdr["block"] < len(cells):
                m = CODE.search(cells[hdr["block"]].upper())
                code = f"{m.group(1)} {m.group(2)}" if m else None
            if not code and sheet_code:
                code = f"{sheet_code.group(1)} {sheet_code.group(2)}"
            if not code:
                m = CODE.search(path.name.upper())
                code = f"{m.group(1)} {m.group(2)}" if m else None
            if not code:
                continue
            sheet_rows.append({
                "block": code, "date": cur_date, "hour": cells[hi], "subject": subj,
                "lecturer": lect if not HOUR.match(lect) else "",
                "field": cells[hdr["field"]] if "field" in hdr and hdr["field"] < len(cells) else "",
                "stype": cells[hdr["stype"]] if "stype" in hdr and hdr["stype"] < len(cells) else "",
                "group": group, "file": path.name, "sheet": ws.title,
            })
        _fix_codes(sheet_rows, sheet_code)
        rows_out += sheet_rows
    return rows_out


TYPO_FIXES: list[dict[str, Any]] = []
LECTURER_KEYS: set[str] = set()
CROSS_LISTED: list[dict[str, Any]] = []
DUPLICATE_SHEETS: list[dict[str, Any]] = []


def _fix_codes(rows: list[dict[str, Any]], sheet_code: Any) -> None:
    """A handful of rows carrying a sibling code of the sheet's own block (ERUS 207 inside the ERUS 206 sheet)…"""
    if not rows or not sheet_code:
        return
    own = f"{sheet_code.group(1)} {sheet_code.group(2)}"
    c = Counter(r["block"] for r in rows)
    if c.get(own, 0) == 0:
        other = c.most_common(1)[0][0]
        DUPLICATE_SHEETS.append({"sheet": own, "file": rows[0]["file"], "contains": other})
        rows.clear()
        return
    for code, n in c.items():
        if code != own and code.split()[0] == own.split()[0] and n <= max(3, 0.03 * len(rows)):
            for r in rows:
                if r["block"] == code:
                    r["block"] = own
            TYPO_FIXES.append({"file": rows[0]["file"], "sheet": own, "written": code, "rows": n, "used": own})


def read_rphm_pdf(path: Path) -> list[dict[str, Any]]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    m = CODE.search(path.name.upper())
    code = f"{m.group(1)} {m.group(2)}" if m else None
    day_title = re.search(r"DAY-\d+:\s*(.+?)\s*\(", text)
    dm = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    date = dt.date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1))).isoformat() if dm else None
    for line in text.splitlines():
        lm = re.match(r"^\s*Lecture(?: by [^:]+)?:\s*(.+)$", line.strip())
        if lm and code:
            out.append({"block": code, "date": date, "hour": "", "subject": lm.group(1).strip(), "lecturer": "",
                        "field": "PHARMACOLOGY", "stype": "Lecture", "group": "", "file": path.name, "sheet": "pdf"})
    if day_title and code:
        out.append({"block": code, "date": date, "hour": "", "subject": day_title.group(1).strip(), "lecturer": "",
                    "field": "PHARMACOLOGY", "stype": "Workshop", "group": "", "file": path.name, "sheet": "pdf"})
    return out


#  Learning objectives

DEPTS = {"ANATOMY", "HISTOLOGY", "HISTOLOGY & EMBRYOLOGY", "HISTOLOGY&EMBRYOLOGY", "BIOCHEMISTRY", "PHYSIOLOGY",
         "PHARMACOLOGY", "PATHOLOGY", "MICROBIOLOGY", "BIOPHYSICS", "MEDICAL GENETICS", "IMMUNOLOGY", "UROLOGY",
         "OBSTETRICS & GYNAECOLOGY", "PSYCHIATRY", "RADIOLOGY", "NEUROLOGY", "CARDIOLOGY", "PUBLIC HEALTH",
         "MEDICAL BIOLOGY", "INTERNAL MEDICINE", "NEUROSURGERY", "PEDIATRICS", "PSYCHIATRY & BEHAVIORAL SCIENCES"}


def read_objectives(path: Path) -> list[dict[str, Any]]:
    import docx
    d = docx.Document(path)
    m = CODE.search(path.name.upper()) or None
    code = f"{m.group(1)} {m.group(2)}" if m else None
    out, dept, session = [], "", ""
    for p in d.paragraphs:
        t = _s(p.text)
        if not t:
            continue
        if code is None:
            mm = CODE.search(t.upper())
            if mm:
                code = f"{mm.group(1)} {mm.group(2)}"
        pPr = p._p.pPr
        is_list = (pPr is not None and pPr.numPr is not None) or p.style.name.lower().startswith("list")
        bold = any(r.bold for r in p.runs if r.text.strip())
        if not is_list:
            if re.match(r"^(learning objectives|core\s*/|.*learning objectives$)", t, re.I) or CODE.search(t.upper()) and len(t) < 60:
                continue
            dm = re.match(r"^department:\s*(.+)$", t, re.I)
            if dm:
                dept = dm.group(1).strip().upper(); continue
            if t.upper() == t and len(t) < 50 or t.upper().strip() in DEPTS:
                dept = t.upper().strip(); continue
            if bold or len(t) < 120:
                session = t; continue
        if code:
            out.append({"block": code, "department": dept, "session": session, "text": t, "file": path.name})
    return out


#  Assemble

def _tok(s: str) -> set[str]:
    stop = {"of", "the", "and", "in", "to", "a", "an", "with", "for", "on", "its", "i", "ii", "iii", "iv"}
    return {w for w in topic_key(s).split() if w not in stop and len(w) > 1}


def assemble(raw_dir: Path) -> dict[str, Any]:
    files = sorted(p for p in raw_dir.rglob("*") if p.is_file())
    rows, objectives, used, skipped = [], [], [], []
    for p in files:
        suf = p.suffix.lower()
        try:
            if suf == ".xlsx":
                r = read_workbook(p); rows += r; used.append((p.name, len(r)))
            elif suf == ".docx":
                if re.search(r"(objective|LOs?\b|core)", p.name, re.I):
                    o = read_objectives(p); objectives += o; used.append((p.name, len(o)))
                elif re.search(r"\d{4}", p.name):  # ETPR-type programme tables
                    r = read_docx_programme(p); rows += r; used.append((p.name, len(r)))
                else:
                    skipped.append((p.name, "öğretim üyesi listesi — içerik değil"))
            elif suf == ".pdf" and "RPHM" in p.name.upper():
                r = read_rphm_pdf(p); rows += r; used.append((p.name, len(r)))
            elif suf == ".pdf":
                skipped.append((p.name, "aynı program Excel dosyasında var"))
        except Exception as exc:  # keep importing other files
            skipped.append((p.name, f"okunamadı: {exc}"))

    # parallel group activities written in one cell ("LAB: X (Group I)/ LAB: Y (Group II)")
    split_rows = []
    for r in rows:
        parts = re.split(r"\s*/\s*(?=LAB\s*:|GROUP\s+[A-Z0-9]{1,2}\s*:)", r["subject"], flags=re.I)
        for part in parts:
            split_rows.append({**r, "subject": part})
    rows = split_rows

    LECTURER_KEYS.clear()
    LECTURER_KEYS.update(topic_key(x) for r in rows for x in re.split(r"\s*(?:/|,|&| and | - |-)\s*", r["lecturer"] or "")
                         if len(x) > 6)

    # one row per (block, date, hour, subject): overview, block and group files overlap
    seen, sessions = set(), []
    for r in rows:
        r["kind"] = classify(r["subject"]) if not r["stype"] else classify(f"{r['stype']}: {r['subject']}") \
            if classify(r["subject"]) == "ders" else classify(r["subject"])
        k = (r["block"], r["date"], r["hour"], topic_key(r["subject"]), r["group"])
        if k in seen:
            continue
        seen.add(k); sessions.append(r)

    # one session written into two block sheets (a longitudinal course such as
    # ETPR inside the NEOP weeks): keep it once, under the longitudinal course
    LONGITUDINAL = ("ETPR", "RMHS", "PUBC")
    slot: dict[tuple, list[dict]] = defaultdict(list)
    for r in sessions:
        if r["date"] and r["hour"] and r["kind"] not in ("öğle arası", "bireysel çalışma", "sınav", "tatil", "idari"):
            slot[(r["block"].split()[1][0], r["date"], r["hour"][:5], topic_key(normalize_title(r["subject"])))].append(r)
    drop, cross = set(), []
    for k, rs in slot.items():
        codes = {r["block"] for r in rs}
        if len(codes) > 1:
            keep = next((c for c in sorted(codes) if c.startswith(LONGITUDINAL)), sorted(codes)[0])
            for r in rs:
                if r["block"] != keep:
                    drop.add(id(r))
            cross.append({"date": k[1], "subject": rs[0]["subject"], "blocks": sorted(codes), "kept": keep})
    sessions = [r for r in sessions if id(r) not in drop]
    CROSS_LISTED[:] = cross

    # blocks
    blocks: dict[str, dict[str, Any]] = {}
    for r in sessions:
        b = blocks.setdefault(r["block"], {"code": r["block"], "year": int(r["block"].split()[1][0]),
                                           "dates": [], "fields": Counter(), "files": set(), "groups": set(),
                                           "kinds": Counter()})
        if r["date"]:
            b["dates"].append(r["date"])
        if r["field"] and r["kind"] not in ("öğle arası", "bireysel çalışma", "idari", "sınav", "tatil"):
            b["fields"][r["field"].upper().replace("&", " & ").replace("  ", " ")] += 1
        b["files"].add(r["file"]); b["kinds"][r["kind"]] += 1
        if r["group"]:
            b["groups"].add(r["group"])

    # topics: distinct teaching content per block
    topics: dict[tuple[str, str], dict[str, Any]] = {}
    for r in sessions:
        if r["kind"] in ("öğle arası", "bireysel çalışma", "sınav", "tatil", "idari", "klinik uygulama"):
            continue
        title = normalize_title(r["subject"])
        if r["lecturer"] and topic_key(title) == topic_key(r["lecturer"]) or topic_key(title) in LECTURER_KEYS:
            continue                                   # a lecturer's name in the subject column
        if len(title) < 4 or not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3}", title):
            continue
        key = (r["block"], topic_key(title))
        t = topics.setdefault(key, {"block": r["block"], "title": title, "kinds": Counter(), "fields": Counter(),
                                    "lecturers": set(), "dates": set(), "sessions": 0, "objectives": []})
        t["kinds"][r["kind"]] += 1; t["sessions"] += 1
        if r["field"]:
            t["fields"][r["field"].upper()] += 1
        if r["lecturer"] and not re.search(r"(study|exam|evaluation)", r["lecturer"], re.I):
            t["lecturers"].add(r["lecturer"])
        if r["date"]:
            t["dates"].add(r["date"])

    # attach objectives to the matching topic of the same block
    by_block: dict[str, list[dict]] = defaultdict(list)
    for t in topics.values():
        by_block[t["block"]].append(t)
    unmatched = 0
    for o in objectives:
        cands = by_block.get(o["block"], [])
        st = _tok(normalize_title(o["session"]))
        best, score = None, 0.0
        for t in cands:
            tt = _tok(t["title"])
            if not st or not tt:
                continue
            j = len(st & tt) / len(st | tt)
            if o["session"].upper().startswith("LAB") and "laboratuvar" not in t["kinds"]:
                j *= 0.9
            if j > score:
                best, score = t, j
        if best is not None and score >= 0.5:
            best["objectives"].append(o["text"]); o["topic"] = best["title"]
        else:
            unmatched += 1
            # an objective whose session is not in the timetable still belongs to the block
            key = (o["block"], topic_key(normalize_title(o["session"]) or o["text"][:60]))
            t = topics.setdefault(key, {"block": o["block"], "title": normalize_title(o["session"]) or o["text"][:80],
                                        "kinds": Counter({"ders": 0}), "fields": Counter({o["department"]: 0}) if o["department"] else Counter(),
                                        "lecturers": set(), "dates": set(), "sessions": 0, "objectives": []})
            t["objectives"].append(o["text"]); o["topic"] = t["title"]
            if t not in by_block[o["block"]]:
                by_block[o["block"]].append(t)

    # order blocks by first teaching date within the year
    def first(b):
        return min(b["dates"]) if b["dates"] else "9999"
    ordered = sorted(blocks.values(), key=lambda b: (b["year"], first(b), b["code"]))
    out_blocks = []
    for i, b in enumerate(ordered):
        ds = sorted(b["dates"])
        weeks = ((dt.date.fromisoformat(ds[-1]) - dt.date.fromisoformat(ds[0])).days // 7 + 1) if ds else None
        n_topics = sum(1 for t in topics.values() if t["block"] == b["code"])
        out_blocks.append({
            "code": b["code"], "id": b["code"].replace(" ", ""), "year": b["year"], "order": i,
            "start": ds[0] if ds else None, "end": ds[-1] if ds else None, "weeks": weeks,
            "fields": [f for f, _ in b["fields"].most_common(8)], "groups": sorted(b["groups"]),
            "session_kinds": dict(b["kinds"]), "n_topics": n_topics,
            "n_objectives": sum(len(t["objectives"]) for t in topics.values() if t["block"] == b["code"]),
            "files": sorted(b["files"]),
        })
    border = {b["code"]: b["order"] for b in out_blocks}
    out_topics = []
    for t in sorted(topics.values(), key=lambda t: (border.get(t["block"], 99), min(t["dates"]) if t["dates"] else "9", t["title"])):
        out_topics.append({
            "id": f"{t['block'].replace(' ', '')}:{hashlib.sha1(topic_key(t['title']).encode()).hexdigest()[:6]}",
            "block": t["block"], "year": int(t["block"].split()[1][0]), "title": t["title"],
            "kind": t["kinds"].most_common(1)[0][0] if t["kinds"] else "ders",
            "fields": [f for f, _ in t["fields"].most_common(3) if f],
            "lecturers": sorted(t["lecturers"])[:6], "first_date": min(t["dates"]) if t["dates"] else None,
            "sessions": t["sessions"], "objectives": t["objectives"],
        })
    years = sorted({b["year"] for b in out_blocks})
    qc = {
        "files_used": [{"file": f, "records": n} for f, n in used],
        "files_skipped": [{"file": f, "reason": r} for f, r in skipped],
        "rows_read": len(rows), "sessions_unique": len(sessions),
        "session_kinds": dict(Counter(s["kind"] for s in sessions)),
        "topics": len(out_topics), "objectives": len(objectives), "objectives_unmatched_to_timetable": unmatched,
        "years_present": years, "years_missing": [y for y in range(1, 7) if y not in years],
        "blocks_without_objectives": [b["code"] for b in out_blocks if b["n_objectives"] == 0],
        "student_sheets_skipped": "Öğrenci listesi içeren sayfalar hiç açılmadı.",
        "code_typos_fixed": TYPO_FIXES,
        "cross_listed_sessions": CROSS_LISTED,
        "duplicate_sheets": DUPLICATE_SHEETS,
        "date_warnings": [{"block": b["code"], "start": b["start"], "note": "Blok başlangıcı akademik yılın dışında; tarih yılı yanlış yazılmış olabilir."}
                          for b in out_blocks if b["start"] and not ("2025-08-01" <= b["start"] <= "2026-08-31")],
    }
    return {
        "meta": {"source": "KUSOM 2025–2026 ders programları ve öğrenim hedefleri", "academic_year": "2025-2026",
                 "generated": dt.date.today().isoformat(), "importer": "app.data.kusom.parse_timetables"},
        "blocks": out_blocks, "topics": out_topics, "qc": qc,
        "sessions": [{k: s[k] for k in ("block", "date", "hour", "subject", "kind", "field", "group")} for s in sessions],
    }


def read_docx_programme(path: Path) -> list[dict[str, Any]]:
    """ETPR-style programme given as a Word table (DATE | ... | SUBJECT | PLACE)."""
    import docx
    d = docx.Document(path)
    year = _year_from_name(path.name, None) or 0
    code = f"ETPR {year}12" if year else None
    out = []
    for tbl in d.tables:
        hdr = [_s(c.text).upper() for c in tbl.rows[0].cells]
        if "SUBJECT" not in hdr:
            continue
        si = hdr.index("SUBJECT")
        for row in tbl.rows[1:]:
            cells = [_s(c.text) for c in row.cells]
            for part in re.split(r"\n| – \d", row.cells[si].text):
                s = _s(re.sub(r"[–-]\s*\d+[.,]?\d*\s*h\b", "", part))
                if s and code:
                    out.append({"block": code, "date": None, "hour": cells[0] + " " + (cells[1] if len(cells) > 1 else ""),
                                "subject": s, "lecturer": "", "field": "CLINICAL SKILLS", "stype": "Workshop",
                                "group": cells[2] if len(cells) > 2 else "", "file": path.name, "sheet": "docx"})
    return out


def main(argv: list[str]) -> None:
    raw = Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else OUT_DEFAULT
    data = assemble(raw)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    q = data["qc"]
    print(f"{len(data['blocks'])} blok, {q['topics']} konu, {q['objectives']} öğrenim hedefi, "
          f"{q['sessions_unique']} oturum → {out}")


if __name__ == "__main__":
    main(sys.argv)
