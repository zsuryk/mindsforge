"""create todo_items

Revision ID: b3c4d5e6f7a8
Revises: d8e9f0a1b2c3
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    todo_type_enum = sa.Enum(
        'weekly_digest', 'clip_suggestion', 'experiment_result', 'trend_alert',
        name='todotype',
    )
    todo_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'todo_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('type', sa.Enum(
            'weekly_digest', 'clip_suggestion', 'experiment_result', 'trend_alert',
            name='todotype', native_enum=False,
        ), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('action_url', sa.String(length=512), nullable=True),
        sa.Column('action_label', sa.String(length=64), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_todo_items_type'), 'todo_items', ['type'], unique=False)
    op.create_index(op.f('ix_todo_items_created_at'), 'todo_items', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_todo_items_created_at'), table_name='todo_items')
    op.drop_index(op.f('ix_todo_items_type'), table_name='todo_items')
    op.drop_table('todo_items')
    sa.Enum(name='todotype').drop(op.get_bind(), checkfirst=True)
