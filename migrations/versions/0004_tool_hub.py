"""tool_hub

Revision ID: 0004_tool_hub
Revises: 0003_initial_runtime
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_tool_hub"
down_revision = "0003_initial_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_safe", sa.Boolean(), nullable=False),
        sa.Column("idempotency_supported", sa.Boolean(), nullable=False),
        sa.Column("handler_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_level IN ('LOW','MEDIUM','HIGH')", name=op.f("ck_tools_risk_level")
        ),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name=op.f("ck_tools_status")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_tools_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tools")),
        sa.UniqueConstraint(
            "organization_id", "name", "version", name=op.f("uq_tools_organization_id")
        ),
    )
    op.create_table(
        "agent_tools",
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_agent_tools_agent_version_id_agent_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["tools.id"], name=op.f("fk_agent_tools_tool_id_tools")
        ),
        sa.PrimaryKeyConstraint("agent_version_id", "tool_id", name=op.f("pk_agent_tools")),
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("model_call_id", sa.Uuid(), nullable=False),
        sa.Column("call_index", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=True),
        sa.Column("requested_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING','COMPLETED','DENIED','FAILED','TIMED_OUT')",
            name=op.f("ck_tool_calls_status"),
        ),
        sa.ForeignKeyConstraint(
            ["model_call_id"],
            ["model_calls.id"],
            name=op.f("fk_tool_calls_model_call_id_model_calls"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_tool_calls_run_id_runs")),
        sa.ForeignKeyConstraint(
            ["tool_id"], ["tools.id"], name=op.f("fk_tool_calls_tool_id_tools")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_tool_calls_idempotency_key")),
        sa.UniqueConstraint(
            "model_call_id", "call_index", name=op.f("uq_tool_calls_model_call_id")
        ),
    )
    op.create_index(
        "ix_tool_calls_run_created", "tool_calls", ["run_id", "created_at"], unique=False
    )
    op.create_table(
        "demo_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tool_call_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_demo_tickets_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["tool_call_id"],
            ["tool_calls.id"],
            name=op.f("fk_demo_tickets_tool_call_id_tool_calls"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_tickets")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_demo_tickets_idempotency_key")),
        sa.UniqueConstraint("tool_call_id", name=op.f("uq_demo_tickets_tool_call_id")),
    )
    op.execute("""
        CREATE FUNCTION forge_guard_tool() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
                RAISE EXCEPTION 'TOOL_IMMUTABLE';
            END IF;
            IF (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status') THEN
                RAISE EXCEPTION 'TOOL_IMMUTABLE';
            END IF;
            RETURN NEW;
        END; $$;
    """)
    op.execute("""
        CREATE TRIGGER guard_tool BEFORE UPDATE OR DELETE ON tools
            FOR EACH ROW EXECUTE FUNCTION forge_guard_tool();
    """)
    op.execute("""
        CREATE TRIGGER guard_tool_truncate BEFORE TRUNCATE ON tools
            FOR EACH STATEMENT EXECUTE FUNCTION forge_guard_tool();
    """)
    op.execute("""
        CREATE FUNCTION forge_guard_tool_binding() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'TOOL_BINDING_IMMUTABLE'; END IF;
            IF NOT EXISTS (
                SELECT 1 FROM agent_versions av JOIN agents a ON a.id = av.agent_id
                JOIN tools t ON t.id = NEW.tool_id AND t.organization_id = a.organization_id
                WHERE av.id = NEW.agent_version_id
                  AND av.tool_version_ids @> jsonb_build_array(NEW.tool_id::text)
            ) THEN RAISE EXCEPTION 'TOOL_BINDING_INVALID'; END IF;
            RETURN NEW;
        END; $$;
    """)
    op.execute("""
        CREATE TRIGGER guard_tool_binding BEFORE INSERT OR UPDATE OR DELETE ON agent_tools
            FOR EACH ROW EXECUTE FUNCTION forge_guard_tool_binding();
    """)
    op.execute("""
        CREATE TRIGGER guard_tool_binding_truncate BEFORE TRUNCATE ON agent_tools
            FOR EACH STATEMENT EXECUTE FUNCTION forge_guard_tool_binding();
    """)


def downgrade() -> None:
    op.drop_table("demo_tickets")
    op.drop_index("ix_tool_calls_run_created", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_table("agent_tools")
    op.drop_table("tools")
    op.execute("DROP FUNCTION forge_guard_tool_binding()")
    op.execute("DROP FUNCTION forge_guard_tool()")
