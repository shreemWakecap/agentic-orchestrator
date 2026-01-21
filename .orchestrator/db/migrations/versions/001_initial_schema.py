"""initial_schema

Revision ID: 001_initial
Revises:
Create Date: 2026-01-21 23:02:58.500409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Initial schema - tables are created by SQLAlchemy models
    # This migration serves as the baseline
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
