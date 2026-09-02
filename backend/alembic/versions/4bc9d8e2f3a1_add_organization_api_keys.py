"""add organization API keys

Revision ID: 4bc9d8e2f3a1
Revises: 0a0b6a5ea51e
"""
from alembic import op
import sqlalchemy as sa

revision = "4bc9d8e2f3a1"
down_revision = "0a0b6a5ea51e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_organization_api_keys_organization_id", "organization_api_keys", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_organization_api_keys_organization_id", table_name="organization_api_keys")
    op.drop_table("organization_api_keys")
