"""create clip_adaptations

Revision ID: 9c7e4d2f8b5a
Revises: 7b3d1c9e4a2f
Create Date: 2026-08-12 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c7e4d2f8b5a'
down_revision: Union[str, Sequence[str], None] = '7b3d1c9e4a2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'clip_adaptations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('clip_id', sa.String(length=36), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False),
        sa.Column(
            'surface',
            sa.Enum('SHORTS', 'LONG_FORM', 'POST', name='adaptationsurface', native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'GENERATING', 'READY', 'FAILED', name='adaptationstatus', native_enum=False),
            nullable=False,
        ),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('assets', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.String(length=2048), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clip_id', 'platform', 'surface', name='uq_clip_adaptations_clip_platform_surface'),
    )
    op.create_index(op.f('ix_clip_adaptations_clip_id'), 'clip_adaptations', ['clip_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_clip_adaptations_clip_id'), table_name='clip_adaptations')
    op.drop_table('clip_adaptations')