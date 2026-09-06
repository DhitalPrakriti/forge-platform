from enum import StrEnum

from forge.core.errors import DomainError


class Lifecycle(StrEnum):
    DRAFT = "DRAFT"
    STAGING = "STAGING"
    EVALUATING = "EVALUATING"
    APPROVED = "APPROVED"
    PRODUCTION = "PRODUCTION"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


TRANSITIONS = {
    Lifecycle.DRAFT: {Lifecycle.STAGING, Lifecycle.ARCHIVED},
    Lifecycle.STAGING: {Lifecycle.EVALUATING, Lifecycle.ARCHIVED},
    Lifecycle.EVALUATING: {Lifecycle.STAGING, Lifecycle.APPROVED},
    Lifecycle.APPROVED: {Lifecycle.PRODUCTION, Lifecycle.ARCHIVED},
    Lifecycle.PRODUCTION: {Lifecycle.DEPRECATED},
    Lifecycle.DEPRECATED: {Lifecycle.PRODUCTION, Lifecycle.ARCHIVED},
    Lifecycle.ARCHIVED: set(),
}


def validate_transition(current: Lifecycle, target: Lifecycle) -> None:
    if target not in TRANSITIONS[current]:
        raise DomainError(
            "INVALID_LIFECYCLE_TRANSITION", f"Cannot move from {current} to {target}.", 409
        )
