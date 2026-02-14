"""add agent_memories table

Revision ID: a3b7c9d2e4f1
Revises: 66575a17a2c4
Create Date: 2026-02-14 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3b7c9d2e4f1'
down_revision: Union[str, None] = '66575a17a2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_memories',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('agent_name', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.Column('importance', sa.Float(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('session_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_memories_user_id', 'agent_memories', ['user_id'])
    op.create_index('ix_agent_memories_agent_name', 'agent_memories', ['agent_name'])
    op.create_index('ix_agent_memories_category', 'agent_memories', ['category'])
    op.create_index('ix_agent_memories_user_category', 'agent_memories', ['user_id', 'category'])
    op.create_index('ix_agent_memories_importance', 'agent_memories', ['importance'])


def downgrade() -> None:
    op.drop_index('ix_agent_memories_importance', table_name='agent_memories')
    op.drop_index('ix_agent_memories_user_category', table_name='agent_memories')
    op.drop_index('ix_agent_memories_category', table_name='agent_memories')
    op.drop_index('ix_agent_memories_agent_name', table_name='agent_memories')
    op.drop_index('ix_agent_memories_user_id', table_name='agent_memories')
    op.drop_table('agent_memories')
