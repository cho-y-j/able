"""add unique constraint on strategies (user_id, strategy_type, stock_code)

Revision ID: e7f1a4b5c6d8
Revises: d6e0f3a4b5c7
Create Date: 2026-02-15 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'e7f1a4b5c6d8'
down_revision: Union[str, None] = 'd6e0f3a4b5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicates first: keep the latest strategy per (user_id, strategy_type, stock_code)
    op.execute("""
        DELETE FROM strategies
        WHERE id NOT IN (
            SELECT DISTINCT ON (user_id, strategy_type, stock_code) id
            FROM strategies
            ORDER BY user_id, strategy_type, stock_code, created_at DESC
        )
    """)
    op.create_unique_constraint(
        'uq_strategy_user_type_stock', 'strategies',
        ['user_id', 'strategy_type', 'stock_code']
    )


def downgrade() -> None:
    op.drop_constraint('uq_strategy_user_type_stock', 'strategies', type_='unique')
