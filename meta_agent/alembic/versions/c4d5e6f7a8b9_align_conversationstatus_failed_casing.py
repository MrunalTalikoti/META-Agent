"""align conversationstatus FAILED casing

Migration ``b2c3d4e5f6a7`` added the conversation status value as lowercase
``'failed'``, but SQLAlchemy persists the enum *member name* — i.e. ``'FAILED'``
(uppercase, like every other label: GATHERING / READY / EXECUTING / COMPLETED /
REFINING).  As a result, persisting ``ConversationStatus.FAILED`` would be
rejected by PostgreSQL because the label ``'FAILED'`` did not exist on the type.

This migration adds the correctly-cased ``'FAILED'`` label so failed
conversations can be stored.  No data backfill is needed: the mismatch meant no
row was ever written with the lowercase ``'failed'`` label, so it is left in
place as a harmless orphan (PostgreSQL cannot drop an enum value without
recreating the type).

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Idempotent + matches the style of the migration that introduced 'failed'.
    conn.execute(sa.text("ALTER TYPE conversationstatus ADD VALUE IF NOT EXISTS 'FAILED'"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the
    # type; the orphaned 'failed' label from b2c3d4e5f6a7 is likewise retained.
    pass
