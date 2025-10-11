"""merge heads

Revision ID: d02249b05077
Revises: 2f1913b555de, c4a1008b1194
Create Date: 2025-09-26 15:03:30.689552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd02249b05077'
down_revision: Union[str, Sequence[str], None] = ('2f1913b555de', 'c4a1008b1194')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
