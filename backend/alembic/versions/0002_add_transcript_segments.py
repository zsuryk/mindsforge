"""add transcript_segments to jobs

Revision ID: 30ff986a5b1e
Revises: f33fde83ba9c
Create Date: 2026-08-12 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30ff986a5b1e'
down_revision: Union[str, Sequence[str], None] = 'f33fde83ba9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('transcript_segments', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'transcript_segments')