import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from forge.agents.lifecycle import Lifecycle, validate_transition
from forge.agents.schemas import AgentPatch, VersionCreate
from forge.core.config import Settings
from forge.core.errors import DomainError
from forge.main import create_app

BASE = dict(version="v1", goal="Answer questions", instructions="Be helpful", primary_model="demo")


@pytest.mark.parametrize(
    "invalid",
    [
        {"instructions": "  "},
        {"version": ""},
        {"primary_model": "  "},
        {"runtime_config": {"max_steps": 0}},
        {"runtime_config": {"max_steps": True}},
        {"runtime_config": {"max_runtime_seconds": -1}},
        {"budget_config": {"max_cost_per_run_usd": "NaN"}},
        {"budget_config": {"max_cost_per_run_usd": 0}},
        {"fallback_models": ["demo"]},
        {"fallback_models": ["other", "other"]},
        {"lifecycle_status": "APPROVED"},
        {"unknown": True},
    ],
)
def test_version_configuration_rejects_invalid_input(invalid):
    with pytest.raises(ValidationError):
        VersionCreate(**(BASE | invalid))


@pytest.mark.parametrize(
    "invalid",
    [{}, {"name": None}, {"description": None}, {"slug": "changed"}, {"organization_id": "other"}],
)
def test_patch_cannot_change_identity_or_clear_required_fields(invalid):
    with pytest.raises(ValidationError):
        AgentPatch(**invalid)


def test_lifecycle_constraints():
    validate_transition(Lifecycle.DRAFT, Lifecycle.ARCHIVED)
    validate_transition(Lifecycle.EVALUATING, Lifecycle.STAGING)
    validate_transition(Lifecycle.DEPRECATED, Lifecycle.PRODUCTION)
    for current, target in [
        (Lifecycle.DRAFT, Lifecycle.PRODUCTION),
        (Lifecycle.PRODUCTION, Lifecycle.ARCHIVED),
        (Lifecycle.ARCHIVED, Lifecycle.DRAFT),
        (Lifecycle.DRAFT, Lifecycle.DRAFT),
    ]:
        with pytest.raises(DomainError) as error:
            validate_transition(current, target)
        assert error.value.code == "INVALID_LIFECYCLE_TRANSITION"


def test_registry_is_disabled_in_production_without_membership():
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+asyncpg://forge@127.0.0.1:1/test",
    )
    with TestClient(create_app(settings)) as client:
        for method, path in [
            ("get", "/agents"),
            ("post", "/organizations"),
            ("post", "/agents"),
            ("get", "/organizations/current"),
        ]:
            response = getattr(client, method)(f"/api/v1{path}")
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "REGISTRY_AUTH_REQUIRED"
        assert client.get("/api/v1/health/live").status_code == 200
