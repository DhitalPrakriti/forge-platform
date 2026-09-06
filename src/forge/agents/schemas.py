from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from forge.agents.lifecycle import Lifecycle

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)]
Revision = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class OrganizationCreate(Schema):
    name: Name
    slug: Slug


class OrganizationRead(OrganizationCreate):
    id: UUID
    created_at: datetime


class AgentCreate(Schema):
    name: Name
    slug: Slug
    description: str = Field(default="", max_length=10000)


class AgentPatch(Schema):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=10000)
    status: Literal["ACTIVE", "INACTIVE"] | None = None

    @model_validator(mode="after")
    def nonempty_patch(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null editable field")
        return self


class AgentRead(AgentCreate):
    id: UUID
    organization_id: UUID
    status: Literal["ACTIVE", "INACTIVE"]
    created_at: datetime
    updated_at: datetime


class RuntimeLimits(Schema):
    max_steps: int = Field(default=12, ge=1, le=1000, strict=True)
    max_runtime_seconds: int = Field(default=180, ge=1, le=86400, strict=True)


class BudgetLimits(Schema):
    max_cost_per_run_usd: Decimal = Field(
        default=Decimal("0.20"), gt=0, max_digits=12, decimal_places=6, allow_inf_nan=False
    )


class VersionCreate(Schema):
    version: Revision
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
    instructions: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100000)
    ]
    primary_model: Name
    fallback_models: list[Name] = Field(default_factory=list, max_length=10)
    runtime_template_revision: Revision = "standard-agent-v1"
    runtime_config: RuntimeLimits = Field(default_factory=RuntimeLimits)
    budget_config: BudgetLimits = Field(default_factory=BudgetLimits)
    tool_version_ids: list[UUID] = Field(default_factory=list, max_length=100)
    policy_version_ids: list[UUID] = Field(default_factory=list, max_length=100)
    evaluation_suite_version_id: UUID | None = None

    @model_validator(mode="after")
    def unique_bindings(self):
        for items in (self.fallback_models, self.tool_version_ids, self.policy_version_ids):
            if len(items) != len(set(items)):
                raise ValueError("Duplicate dependency references are not allowed")
        if self.primary_model in self.fallback_models:
            raise ValueError("Primary model cannot also be a fallback")
        return self


class VersionRead(VersionCreate):
    id: UUID
    agent_id: UUID
    lifecycle_status: Lifecycle
    created_at: datetime
