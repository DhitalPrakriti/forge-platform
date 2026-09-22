"""Immutable workspace knowledge and version-bound document access."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_knowledge"
down_revision = "0008_model_routing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_knowledge_documents_organization_id", "knowledge_documents", ["organization_id"]
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "position"),
    )
    op.add_column(
        "agent_versions",
        sa.Column("knowledge_document_ids", JSONB(), nullable=False, server_default="[]"),
    )
    op.execute("""CREATE FUNCTION protect_knowledge() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Knowledge documents and chunks are immutable'; END; $$""")
    for table in ("knowledge_documents", "knowledge_chunks"):
        op.execute(
            f"CREATE TRIGGER immutable_knowledge BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION protect_knowledge()"
        )
        op.execute(
            f"CREATE TRIGGER no_truncate_knowledge BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION protect_knowledge()"
        )


def downgrade():
    op.drop_column("agent_versions", "knowledge_document_ids")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.execute("DROP FUNCTION protect_knowledge()")
