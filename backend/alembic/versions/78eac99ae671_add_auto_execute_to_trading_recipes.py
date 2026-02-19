"""add_auto_execute_to_trading_recipes

Revision ID: 78eac99ae671
Revises: 137261e2e3fa
Create Date: 2026-02-19 11:45:14.595587
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '78eac99ae671'
down_revision: Union[str, None] = '137261e2e3fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trading_recipes', sa.Column('auto_execute', sa.Boolean(), server_default='false', nullable=False))
    # Add recipe_id FK to orders and trades if not already present
    op.add_column('orders', sa.Column('recipe_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_orders_recipe_id', 'orders', 'trading_recipes', ['recipe_id'], ['id'])
    op.add_column('trades', sa.Column('recipe_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_trades_recipe_id', 'trades', 'trading_recipes', ['recipe_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_trades_recipe_id', 'trades', type_='foreignkey')
    op.drop_column('trades', 'recipe_id')
    op.drop_constraint('fk_orders_recipe_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'recipe_id')
    op.drop_column('trading_recipes', 'auto_execute')
