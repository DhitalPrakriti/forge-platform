"""initial_runtime

Revision ID: 0003_initial_runtime
Revises: 0002_agent_registry
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_initial_runtime"
down_revision = "0002_agent_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("model_calls_count", sa.Integer(), nullable=False),
        sa.Column("tool_calls_count", sa.Integer(), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("runtime_build_version", sa.String(length=100), nullable=False),
        sa.Column("execution_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('CREATED','QUEUED','RUNNING','WAITING_FOR_TOOL','WAITING_FOR_APPROVAL',"
            "'RETRYING','COMPLETED','FAILED','CANCELLED','TIMED_OUT')",
            name=op.f("ck_runs_status"),
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name=op.f("fk_runs_agent_id_agents")),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_runs_agent_version_id_agent_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_runs_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name=op.f("uq_runs_organization_id")
        ),
    )
    op.create_index("ix_runs_agent_created", "runs", ["agent_id", "created_at"], unique=False)
    op.create_index("ix_runs_status_created", "runs", ["status", "created_at"], unique=False)
    op.create_table(
        "model_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("actual_model", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_model_calls_run_id_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_calls")),
    )
    op.create_index(
        "ix_model_calls_run_created", "model_calls", ["run_id", "created_at"], unique=False
    )
    op.create_table(
        "run_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_run_events_run_id_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_events")),
        sa.UniqueConstraint("run_id", "sequence_number", name=op.f("uq_run_events_run_id")),
    )


def downgrade() -> None:
    op.drop_table("run_events")
    op.drop_index("ix_model_calls_run_created", table_name="model_calls")
    op.drop_table("model_calls")
    op.drop_index("ix_runs_status_created", table_name="runs")
    op.drop_index("ix_runs_agent_created", table_name="runs")
    op.drop_table("runs")
