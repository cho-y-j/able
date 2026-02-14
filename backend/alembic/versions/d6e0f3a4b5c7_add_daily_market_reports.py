"""add daily_market_reports table

Revision ID: d6e0f3a4b5c7
Revises: c5d9e2f3a4b6
Create Date: 2026-02-15 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd6e0f3a4b5c7'
down_revision: Union[str, None] = 'c5d9e2f3a4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('daily_market_reports',
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('market_data', postgresql.JSONB(), nullable=False),
        sa.Column('themes', postgresql.JSONB(), nullable=False),
        sa.Column('ai_summary', postgresql.JSONB(), nullable=False),
        sa.Column('ai_raw_text', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_daily_market_reports_date', 'daily_market_reports', ['report_date'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_daily_market_reports_date', table_name='daily_market_reports')
    op.drop_table('daily_market_reports')
