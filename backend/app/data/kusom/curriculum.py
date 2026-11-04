"""Turns the imported KUSOM data set (kusom_2025_2026.json) into the curriculum structure the rest of CURATOR…"""
from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("kusom_2025_2026.json")

# code prefix + year digit → (Turkish, English) descriptive name
BLOCK_NAMES: dict[str, tuple[str, str]] = {
    "MEDI 201": ("Tıbbın Moleküler ve Hücresel Temelleri", "Molecular and Cellular Basis of Medicine"),
    "MSKL 202": ("Kas-İskelet Sistemi (temel)", "Musculoskeletal System (basic)"),
    "CIRC 204": ("Kan, Dolaşım ve Solunum Sistemleri (temel)", "Blood, Circulatory and Respiratory Systems (basic)"),
    "NUTI 205": ("Sindirim, Beslenme ve Metabolizma (temel)", "Digestion, Nutrition and Metabolism (basic)"),
    "ERUS 206": ("Endokrin, Üriner ve Üreme Sistemleri (temel)", "Endocrine, Urinary and Reproductive Systems (basic)"),
    "NRVS 207": ("Sinir Sistemi (temel)", "Nervous System (basic)"),
    "ETPR 212": ("Klinik Beceriler ve Mesleğe Hazırlık (2. sınıf)", "Clinical Skills and Professional Practice (Y2)"),
    "IICR 301": ("Enfeksiyon, Bağışıklık ve İnflamasyon", "Infection, Immunity and Inflammation"),
    "NEOP 302": ("Neoplazi", "Neoplasia"),
    "MSKL 303": ("Kas-İskelet Sistemi Hastalıkları", "Musculoskeletal Diseases"),
    "RESP 313": ("Solunum Sistemi Hastalıkları", "Respiratory Diseases"),
    "CARD 314": ("Kardiyovasküler Sistem Hastalıkları", "Cardiovascular Diseases"),
    "GIND 305": ("Gastrointestinal Sistem Hastalıkları", "Gastrointestinal Diseases"),
    "ERUD 306": ("Endokrin, Üriner ve Üreme Sistemi Hastalıkları", "Endocrine, Urinary and Reproductive Diseases"),
    "PUBC 307": ("Halk Sağlığı", "Public Health"),
    "RMHS 309": ("Araştırma Yöntemleri ve Biyoistatistik", "Research Methods and Biostatistics"),
    "ETPR 312": ("Klinik Beceriler ve Mesleğe Hazırlık (3. sınıf)", "Clinical Skills and Professional Practice (Y3)"),
    "IMED 410": ("İç Hastalıkları Stajı", "Internal Medicine Clerkship"),
    "PEDI 403": ("Çocuk Sağlığı ve Hastalıkları Stajı", "Paediatrics Clerkship"),
    "SURG 401": ("Genel Cerrahi ve Anesteziyoloji Stajı", "General Surgery and Anaesthesiology Clerkship"),
    "OBGY 404": ("Kadın Hastalıkları ve Doğum Stajı", "Obstetrics and Gynaecology Clerkship"),
    "RPHM 406": ("Akılcı Farmakoterapi", "Rational Pharmacotherapy"),
    "MSKL 503": ("Ortopedi ve Kas-İskelet Stajı", "Orthopaedics and Musculoskeletal Clerkship"),
    "SENS 506": ("Dermatoloji ve Kulak Burun Boğaz Stajı", "Dermatology and ENT Clerkship"),
    "NEUR 512": ("Nöroloji, Beyin Cerrahisi ve Göz Stajı", "Neurology, Neurosurgery and Ophthalmology Clerkship"),
    "FORM 511": ("Adli Tıp Stajı", "Forensic Medicine Clerkship"),
    "PSYT 513": ("Psikiyatri Stajı", "Psychiatry Clerkship"),
}

# Turkish / English words a student may use → block codes (earliest first).
ALIASES: dict[str, list[str]] = {
    "kardiyoloji": ["CARD314"], "kardiyovasküler": ["CARD314", "CIRC204"], "kalp": ["CARD314", "CIRC204"],
    "dolaşım": ["CIRC204"], "kan": ["CIRC204"], "hematoloji": ["CIRC204", "NEOP302"],
    "solunum": ["RESP313", "CIRC204"], "göğüs": ["RESP313"],
    "kas-iskelet": ["MSKL202", "MSKL303", "MSKL503"], "kas iskelet": ["MSKL202", "MSKL303", "MSKL503"],
    "ortopedi": ["MSKL503"], "sindirim": ["NUTI205", "GIND305"], "gastrointestinal": ["GIND305", "NUTI205"],
    "gastroenteroloji": ["GIND305"], "metabolizma": ["NUTI205"], "beslenme": ["NUTI205"],
    "endokrin": ["ERUD306", "ERUS206"], "üriner": ["ERUD306", "ERUS206"], "böbrek": ["ERUD306", "ERUS206"],
    "üreme": ["ERUS206", "ERUD306"], "sinir sistemi": ["NRVS207", "NEUR512"], "nöroloji": ["NEUR512", "NRVS207"],
    "beyin cerrahisi": ["NEUR512"], "göz": ["NEUR512"], "enfeksiyon": ["IICR301"], "bağışıklık": ["IICR301"],
    "immünoloji": ["IICR301"], "neoplazi": ["NEOP302"], "onkoloji": ["NEOP302"], "kanser": ["NEOP302"],
    "halk sağlığı": ["PUBC307"], "biyoistatistik": ["RMHS309"], "araştırma": ["RMHS309"],
    "dahiliye": ["IMED410"], "iç hastalıkları": ["IMED410"], "pediatri": ["PEDI403"], "çocuk": ["PEDI403"],
    "cerrahi": ["SURG401"], "anestezi": ["SURG401"], "kadın doğum": ["OBGY404"], "kadın hastalıkları": ["OBGY404"],
    "jinekoloji": ["OBGY404"], "farmakoterapi": ["RPHM406"], "akılcı ilaç": ["RPHM406"],
    "dermatoloji": ["SENS506"], "cildiye": ["SENS506"], "kbb": ["SENS506"], "kulak burun boğaz": ["SENS506"],
    "adli tıp": ["FORM511"], "psikiyatri": ["PSYT513"], "moleküler": ["MEDI201"], "hücre": ["MEDI201"],
    "klinik beceri": ["ETPR212", "ETPR312"],
}

_FIELD_NOISE = ("RESEARCH", "ATTENDANCE", "SALONU", "SCI ", "STUDY", "EXAM", "LUNCH", "COORDINATOR", "DEAN")


def available() -> bool:
    return DATA_PATH.exists()


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text())


def _fmt(d: str | None) -> str:
    if not d:
        return ""
    x = dt.date.fromisoformat(d)
    months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
    return f"{x.day} {months[x.month - 1]} {x.year}"


def _dept(f: str) -> str:
    f = f.replace("ORTHOPEADICS", "ORTHOPAEDICS").replace("SKILS", "SKILLS")
    return " ".join(w.capitalize() if w not in ("&", "/") else w for w in f.split())


@lru_cache(maxsize=1)
def kusom_curriculum() -> list[dict[str, Any]]:
    """Same shape as KUC_CURRICULUM, built from the real timetables."""
    d = load()
    topics_by: dict[str, list[dict]] = {}
    for t in d["topics"]:
        topics_by.setdefault(t["block"], []).append(t)
    years: dict[int, list[dict]] = {}
    for b in d["blocks"]:
        tps = topics_by.get(b["code"], [])
        if not tps:
            continue
        tr, en = BLOCK_NAMES.get(b["code"], (b["code"], b["code"]))
        depts = [_dept(f) for f in b["fields"] if not any(n in f for n in _FIELD_NOISE)][:6]
        n_obj = sum(len(t["objectives"]) for t in tps)
        kinds = sorted({t["kind"] for t in tps})
        years.setdefault(b["year"], []).append({
            "id": b["id"], "code": b["code"], "block_number": b["order"] + 1,
            "name_tr": tr, "name_en": en, "name_is_descriptive": True,
            "weeks": f"{_fmt(b['start'])} – {_fmt(b['end'])}" if b["start"] else "",
            "start": b["start"], "end": b["end"],
            "departments": depts, "topics": [t["title"] for t in tps], "topic_details": tps,
            "competencies": [], "prerequisite_ids": [],
            "description_tr": (f"{b['code']} bloğu, {b['year']}. sınıf, {_fmt(b['start'])} – {_fmt(b['end'])}. "
                               f"{len(tps)} konu ({', '.join(kinds)}); {n_obj} öğrenim hedefi. "
                               f"Bölümler: {', '.join(depts) or '—'}."),
            "description_en": (f"{b['code']} block, Year {b['year']}, {b['start']} – {b['end']}. "
                               f"{len(tps)} topics; {n_obj} learning objectives. Departments: {', '.join(depts) or '—'}."),
        })
    names = {2: ("2. Yıl — Organ Sistemleri (temel)", "Year 2 — Organ Systems (basic)"),
             3: ("3. Yıl — Hastalıkların Temelleri", "Year 3 — Basis of Disease"),
             4: ("4. Yıl — Klinik Stajlar I", "Year 4 — Clerkships I"),
             5: ("5. Yıl — Klinik Stajlar II", "Year 5 — Clerkships II")}
    out = []
    for y in sorted(years):
        tr, en = names.get(y, (f"{y}. Yıl", f"Year {y}"))
        out.append({"year": y, "name_tr": tr, "name_en": en,
                    "description_tr": "KUSOM 2025–2026 ders programlarından içe aktarıldı.",
                    "description_en": "Imported from the KUSOM 2025–2026 timetables.",
                    "blocks": sorted(years[y], key=lambda b: b["block_number"])})
    return out


def phase_of(year: int) -> str:
    """Year 2 builds the normal body, year 3 the diseases, years 4–6 the clinic."""
    return "temel" if year <= 2 else ("hastalık" if year == 3 else "klinik")
