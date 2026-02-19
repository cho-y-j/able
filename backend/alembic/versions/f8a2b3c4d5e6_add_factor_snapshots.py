"""add factor_snapshots table

Revision ID: f8a2b3c4d5e6
Revises: e7f1a4b5c6d8
Create Date: 2026-02-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "f8a2b3c4d5e6"
down_revision = "e7f1a4b5c6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("stock_code", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False, server_default="daily"),
        sa.Column("factor_name", sa.String(80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("metadata", JSONB, server_default="{}"),
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
        sa.UniqueConstraint(
            "snapshot_date",
            "stock_code",
            "timeframe",
            "factor_name",
            name="uq_factor_snapshot",
        ),
    )
    op.create_index(
        "ix_factor_date_stock", "factor_snapshots", ["snapshot_date", "stock_code"]
    )
    op.create_index(
        "ix_factor_name_date", "factor_snapshots", ["factor_name", "snapshot_date"]
    )
    op.create_index(
        "ix_factor_date_name_stock",
        "factor_snapshots",
        ["snapshot_date", "factor_name", "stock_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_factor_date_name_stock", table_name="factor_snapshots")
    op.drop_index("ix_factor_name_date", table_name="factor_snapshots")
    op.drop_index("ix_factor_date_stock", table_name="factor_snapshots")
    op.drop_table("factor_snapshots")
