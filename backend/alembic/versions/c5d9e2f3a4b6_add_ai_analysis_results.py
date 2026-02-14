"""add ai_analysis_results table

Revision ID: c5d9e2f3a4b6
Revises: 6b0bf7889cf6
Create Date: 2026-02-15 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c5d9e2f3a4b6'
down_revision: Union[str, None] = '6b0bf7889cf6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_analysis_results',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('stock_code', sa.String(length=20), nullable=False),
        sa.Column('stock_name', sa.String(length=100), nullable=True),
        sa.Column('decision', sa.String(length=10), nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=False),
        sa.Column('news_sentiment', sa.String(length=10), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('risks', sa.Text(), nullable=True),
        sa.Column('full_result', postgresql.JSONB(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_analysis_results_user_id', 'ai_analysis_results', ['user_id'])
    op.create_index('ix_ai_analysis_results_stock_code', 'ai_analysis_results', ['stock_code'])
    op.create_index('ix_ai_analysis_results_user_stock', 'ai_analysis_results', ['user_id', 'stock_code'])


def downgrade() -> None:
    op.drop_index('ix_ai_analysis_results_user_stock', table_name='ai_analysis_results')
    op.drop_index('ix_ai_analysis_results_stock_code', table_name='ai_analysis_results')
    op.drop_index('ix_ai_analysis_results_user_id', table_name='ai_analysis_results')
    op.drop_table('ai_analysis_results')
