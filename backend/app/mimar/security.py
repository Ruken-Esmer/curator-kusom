"""MİMAR — Role-based access and independence rules (application §2.3, §2.5)."""
from __future__ import annotations

import hashlib
import secrets
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"                    # project lead / data steward
    TECHNICAL = "technical"            # runs analyses, produces MİMAR reports
    REVIEWER = "reviewer"              # AS1 independent technical reviewer
    ADJUDICATOR = "adjudicator"        # third person for disagreements
    EXPERT = "expert"                  # AS2 Expert–Core report authors
    STANDARDIZER = "standardizer"      # blinding / format standardisation only
    VALIDATOR = "validator"            # AS2 independent validation board
    COORDINATOR = "coordinator"        # AS5 evaluations, AS6 expected effects
    IMPACT_EVALUATOR = "impact_evaluator"
    OBSERVER = "observer"              # read-only


# Which roles may perform which capability.  ADMIN is intentionally NOT a
# wildcard for review/validation capabilities: independence must hold.
CAPABILITIES: dict[str, set[Role]] = {
    "data.write": {Role.ADMIN, Role.TECHNICAL},
    "data.freeze": {Role.ADMIN},
    "analysis.run": {Role.ADMIN, Role.TECHNICAL},
    "plan.lock": {Role.ADMIN},
    "sample.create": {Role.ADMIN, Role.TECHNICAL},
    "review.decide": {Role.REVIEWER},
    "review.adjudicate": {Role.ADJUDICATOR},
    "metrics.read": {Role.ADMIN, Role.TECHNICAL, Role.OBSERVER},
    "report.mimar": {Role.ADMIN, Role.TECHNICAL},
    "report.expert": {Role.EXPERT},
    "pool.standardize": {Role.STANDARDIZER},
    "validation.decide": {Role.VALIDATOR},
    "validation.adjudicate": {Role.ADJUDICATOR},
    "pool.unseal": {Role.ADMIN},
    "as5.evaluate": {Role.COORDINATOR},
    "impact.expected": {Role.COORDINATOR, Role.IMPACT_EVALUATOR},
    "impact.run": {Role.ADMIN, Role.TECHNICAL},
    "effort.log": set(Role),
    "users.manage": {Role.ADMIN},
    "audit.read": {Role.ADMIN, Role.OBSERVER},
    "read": set(Role),
}


def new_token() -> str:
    return "mmr_" + secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def can(roles: list[str] | set[str], capability: str) -> bool:
    allowed = CAPABILITIES.get(capability, set())
    return any(Role(r) in allowed for r in roles if r in Role._value2member_map_)


class IndependenceError(PermissionError):
    """Raised when a user would validate a result they prepared/applied."""
