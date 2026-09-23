"""Persist model health and per-attempt cost evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_model_routing"
down_revision = "0007_mcp_tools"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("model_calls", sa.Column("cost_details", JSONB(), nullable=True))
    op.create_table(
        "model_health",
        sa.Column(
            "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("provider", sa.String(50), primary_key=True),
        sa.Column("model", sa.String(200), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("open_until", sa.DateTime(timezone=True)),
        sa.Column("probe_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(100)),
        sa.Column("last_observed_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("model_health")
    op.drop_column("model_calls", "cost_details")
