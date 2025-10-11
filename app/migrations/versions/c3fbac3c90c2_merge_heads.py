"""Merge heads

Revision ID: c3fbac3c90c2
Revises: c82ba83f5667, d0dc5c14dafd
Create Date: 2025-10-09 09:23:54.426987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3fbac3c90c2'
down_revision: Union[str, Sequence[str], None] = ('c82ba83f5667', 'd0dc5c14dafd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
