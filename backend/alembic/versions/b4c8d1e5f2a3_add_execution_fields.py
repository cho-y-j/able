"""add execution fields to orders

Revision ID: b4c8d1e5f2a3
Revises: a3b7c9d2e4f1
Create Date: 2026-02-14 22:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b4c8d1e5f2a3'
down_revision: Union[str, None] = 'a3b7c9d2e4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('execution_strategy', sa.String(10), nullable=True))
    op.add_column('orders', sa.Column('parent_order_id', sa.UUID(), nullable=True))
    op.add_column('orders', sa.Column('expected_price', sa.Numeric(15, 2), nullable=True))
    op.add_column('orders', sa.Column('slippage_bps', sa.Float(), nullable=True))
    op.create_foreign_key(
        'fk_orders_parent_order_id',
        'orders', 'orders',
        ['parent_order_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_orders_parent_order_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'slippage_bps')
    op.drop_column('orders', 'expected_price')
    op.drop_column('orders', 'parent_order_id')
    op.drop_column('orders', 'execution_strategy')
