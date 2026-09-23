"""agent_registry

Revision ID: 0002_agent_registry
Revises: 0001_foundation
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_agent_registry"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
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
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f("ck_agents_status")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agents_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sa.UniqueConstraint("organization_id", "slug", name=op.f("uq_agents_organization_id")),
    )
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("primary_model", sa.String(length=200), nullable=False),
        sa.Column("fallback_models", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("runtime_template_revision", sa.String(length=100), nullable=False),
        sa.Column("runtime_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_version_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_version_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluation_suite_version_id", sa.Uuid(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','STAGING','EVALUATING','APPROVED',"
            "'PRODUCTION','DEPRECATED','ARCHIVED')",
            name=op.f("ck_agent_versions_lifecycle_status"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], name=op.f("fk_agent_versions_agent_id_agents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_versions")),
        sa.UniqueConstraint("agent_id", "version", name=op.f("uq_agent_versions_agent_id")),
    )

    op.execute("""
        CREATE FUNCTION forge_guard_agent_version() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
                RAISE EXCEPTION 'VERSION_IMMUTABLE';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.lifecycle_status <> 'DRAFT' THEN
                    RAISE EXCEPTION 'INVALID_LIFECYCLE_TRANSITION';
                END IF;
                RETURN NEW;
            END IF;
            IF (to_jsonb(NEW) - 'lifecycle_status') IS DISTINCT FROM
               (to_jsonb(OLD) - 'lifecycle_status') THEN
                RAISE EXCEPTION 'VERSION_IMMUTABLE';
            END IF;
            IF NEW.lifecycle_status IS DISTINCT FROM OLD.lifecycle_status AND NOT (
                (OLD.lifecycle_status = 'DRAFT'
                 AND NEW.lifecycle_status IN ('STAGING','ARCHIVED')) OR
                (OLD.lifecycle_status = 'STAGING'
                 AND NEW.lifecycle_status IN ('EVALUATING','ARCHIVED')) OR
                (OLD.lifecycle_status = 'EVALUATING'
                 AND NEW.lifecycle_status IN ('STAGING','APPROVED')) OR
                (OLD.lifecycle_status = 'APPROVED'
                 AND NEW.lifecycle_status IN ('PRODUCTION','ARCHIVED')) OR
                (OLD.lifecycle_status = 'PRODUCTION' AND NEW.lifecycle_status = 'DEPRECATED') OR
                (OLD.lifecycle_status = 'DEPRECATED'
                 AND NEW.lifecycle_status IN ('PRODUCTION','ARCHIVED'))
            ) THEN
                RAISE EXCEPTION 'INVALID_LIFECYCLE_TRANSITION';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER guard_agent_version
        BEFORE INSERT OR UPDATE OR DELETE ON agent_versions
        FOR EACH ROW EXECUTE FUNCTION forge_guard_agent_version();
    """)
    op.execute("""
        CREATE TRIGGER guard_agent_version_truncate
        BEFORE TRUNCATE ON agent_versions
        FOR EACH STATEMENT EXECUTE FUNCTION forge_guard_agent_version();
    """)


def downgrade() -> None:
    op.drop_table("agent_versions")
    op.execute("DROP FUNCTION forge_guard_agent_version()")
    op.drop_table("agents")
    op.drop_table("organizations")
