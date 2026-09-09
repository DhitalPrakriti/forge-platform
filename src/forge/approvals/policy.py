from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from forge.approvals.models import Policy
from forge.core.errors import DomainError

RULES = {"currency": "USD", "allow_up_to": "100.00", "approval_up_to": "500.00"}


async def register_policy(session, organization_id):
    await session.execute(
        insert(Policy)
        .values(organization_id=organization_id, name="demo-refund", version="1.0.0", rules=RULES)
        .on_conflict_do_nothing()
    )
    await session.commit()
    return await session.scalar(
        select(Policy).where(
            Policy.organization_id == organization_id,
            Policy.name == "demo-refund",
            Policy.version == "1.0.0",
        )
    )


async def resolve_policy(session, organization_id, ids, *, required=False):
    if not ids and not required:
        return None
    if len(ids) != 1:
        raise DomainError(
            "REFUND_POLICY_REQUIRED", "Bind exactly one installed refund policy revision.", 409
        )
    policy = await session.get(Policy, UUID(str(ids[0])))
    if policy is None or policy.organization_id != organization_id:
        raise DomainError("POLICY_NOT_FOUND", "Policy revision not found.", 404)
    if policy.name != "demo-refund" or policy.version != "1.0.0" or policy.rules != RULES:
        raise DomainError(
            "POLICY_REVISION_UNAVAILABLE", "Policy implementation is unavailable.", 409
        )
    return policy


def refund_decision(arguments):
    amount = Decimal(arguments["amount_usd"])
    if amount <= Decimal("100"):
        return "ALLOW"
    return "REQUIRE_APPROVAL" if amount <= Decimal("500") else "DENY"
