"""Passive health and a persisted closed/open/single-probe circuit breaker."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from forge.model_router.models import ModelHealth

TRANSIENT = {"MODEL_TIMEOUT", "MODEL_PROVIDER_UNAVAILABLE", "MODEL_OUTCOME_UNKNOWN"}
THRESHOLD = 3
COOLDOWN_SECONDS = 30


async def locked(session, org, provider, model):
    await session.execute(
        insert(ModelHealth)
        .values(
            organization_id=org,
            provider=provider,
            model=model,
            failures=0,
            generation=0,
            state="CLOSED",
        )
        .on_conflict_do_nothing()
    )
    return await session.scalar(
        select(ModelHealth)
        .where(
            ModelHealth.organization_id == org,
            ModelHealth.provider == provider,
            ModelHealth.model == model,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def acquire(session, org, provider, model, lease_seconds):
    row = await locked(session, org, provider, model)
    now = datetime.now(UTC)
    if row.state == "OPEN" and row.open_until and row.open_until > now:
        return None
    if row.state == "HALF_OPEN" and row.probe_until and row.probe_until > now:
        return None
    if row.state != "CLOSED":
        row.state = "HALF_OPEN"
        row.generation += 1
        row.probe_until = now + timedelta(seconds=lease_seconds + 5)
    return row.generation


async def observe(session, org, provider, model, generation, failure):
    row = await locked(session, org, provider, model)
    # Late completions cannot override a newer open/probe generation.
    if row.generation != generation:
        return
    row.last_error, row.last_observed_at = failure, datetime.now(UTC)
    if failure in TRANSIENT:
        row.failures += 1
        if row.failures >= THRESHOLD or row.state == "HALF_OPEN":
            row.state = "OPEN"
            row.generation += 1
            row.open_until = datetime.now(UTC) + timedelta(seconds=COOLDOWN_SECONDS)
            row.probe_until = None
    else:
        row.failures = 0
        row.state = "CLOSED"
        row.open_until = row.probe_until = None


async def listing(session, org):
    return list(
        await session.scalars(
            select(ModelHealth)
            .where(ModelHealth.organization_id == org)
            .order_by(ModelHealth.provider, ModelHealth.model)
            .limit(100)
        )
    )
