"""UÇEP-2020 core diseases / clinical problems (Tablo 2.2), as MİMAR UÇEP rows."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PATH = Path(__file__).with_name("ucep2020_cekirdek_hastaliklar.json")


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(PATH.read_text(encoding="utf-8"))


def ucep_rows(systems: list[str] | None = None) -> list[dict[str, Any]]:
    """Rows in the shape MİMAR's UÇEP import expects (code, text_tr, text_en)."""
    out = []
    for it in load()["items"]:
        if systems and not any(s.lower() in it["system"].lower() for s in systems):
            continue
        out.append({"code": it["code"], "text_tr": it["text_tr"], "text_en": it["text_en"],
                    "level": "-".join(it["levels"]), "system": it["system"]})
    return out
