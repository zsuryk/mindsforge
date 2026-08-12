"""add variant_kind and error_message to ab_experiments

Revision ID: 7b3d1c9e4a2f
Revises: 30ff986a5b1e
Create Date: 2026-08-12 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b3d1c9e4a2f'
down_revision: Union[str, Sequence[str], None] = '30ff986a5b1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ab_experiments',
        sa.Column(
            'variant_kind',
            sa.Enum('TITLE', 'THUMBNAIL', name='abexperimentvariantkind', native_enum=False),
            server_default='TITLE',
            nullable=False,
        ),
    )
    op.add_column(
        'ab_experiments',
        sa.Column('error_message', sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ab_experiments', 'error_message')
    op.drop_column('ab_experiments', 'variant_kind')