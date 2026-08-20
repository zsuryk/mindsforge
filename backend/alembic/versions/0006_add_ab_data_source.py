"""add data_source to ab_experiments

Revision ID: c9d8e7f6a5b4
Revises: d8e9f0a1b2c3
Create Date: 2026-08-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ab_experiments',
        sa.Column(
            'data_source',
            sa.Enum('SIMULATED', 'MANUAL', name='abexperimentdatasource', native_enum=False),
            server_default='SIMULATED',
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ab_experiments', 'data_source')
