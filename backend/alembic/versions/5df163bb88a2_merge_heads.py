"""merge heads

Revision ID: 5df163bb88a2
Revises: 78eac99ae671, g9b3c4d5e6f7
Create Date: 2026-02-20 13:03:52.597044
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '5df163bb88a2'
down_revision: Union[str, None] = ('78eac99ae671', 'g9b3c4d5e6f7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
