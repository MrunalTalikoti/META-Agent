"""add_gathering_turn_count_and_failed_status

Adds turn counter to prevent infinite gathering loops,
and FAILED enum value for unrecoverable conversation errors.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column('gathering_turn_count', sa.Integer(), nullable=False, server_default='0'),
    )
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TYPE conversationstatus ADD VALUE IF NOT EXISTS 'failed'"))


def downgrade() -> None:
    op.drop_column('conversations', 'gathering_turn_count')
    # PostgreSQL does not support removing enum values without recreating the type
