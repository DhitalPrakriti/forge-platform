"""Immutable MCP tool connection snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_mcp_tools"
down_revision = "0006_durability"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tools", sa.Column("connection_config", JSONB(), nullable=True))


def downgrade():
    op.drop_column("tools", "connection_config")
