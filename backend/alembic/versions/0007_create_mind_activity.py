"""create mind_activity

Revision ID: d8e9f0a1b2c3
Revises: a1b2c3d4e5f6
Create Date: 2026-08-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'mind_activity',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('ref_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mind_activity_created_at'), 'mind_activity', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mind_activity_created_at'), table_name='mind_activity')
    op.drop_table('mind_activity')