"""Which curriculum the application runs on (see Settings.curriculum_source)."""
from __future__ import annotations

from typing import Any, Callable


def active_source() -> str:
    from app.core.config import get_settings
    from app.data.kusom import curriculum as loader
    return "kusom" if get_settings().curriculum_source == "kusom" and loader.available() else "placeholder"


def active_curriculum() -> list[dict[str, Any]]:
    if active_source() == "kusom":
        from app.data.kusom.curriculum import kusom_curriculum
        return kusom_curriculum()
    from app.data.curriculum.koc_university import KUC_CURRICULUM
    return KUC_CURRICULUM


def active_aliases() -> dict:
    if active_source() == "kusom":
        from app.data.kusom.curriculum import ALIASES
        return ALIASES
    from app.pathway.planner import PLACEHOLDER_ALIASES
    return PLACEHOLDER_ALIASES


def active_phase_of() -> Callable[[int], str] | None:
    if active_source() == "kusom":
        from app.data.kusom.curriculum import phase_of
        return phase_of
    return None
