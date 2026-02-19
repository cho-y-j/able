"""add discovered_patterns table

Revision ID: g9b3c4d5e6f7
Revises: f8a2b3c4d5e6
Create Date: 2026-02-19 10:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "g9b3c4d5e6f7"
down_revision = "f8a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovered_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("feature_importance", JSONB, server_default="{}"),
        sa.Column("model_metrics", JSONB, server_default="{}"),
        sa.Column("rule_description", sa.Text()),
        sa.Column("rule_config", JSONB, server_default="{}"),
        sa.Column("validation_results", JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("sample_count", sa.Integer(), server_default="0"),
        sa.Column("event_count", sa.Integer(), server_default="0"),
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
    )


def downgrade() -> None:
    op.drop_table("discovered_patterns")
