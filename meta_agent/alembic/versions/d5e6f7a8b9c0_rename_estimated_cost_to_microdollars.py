"""rename estimated_cost_usd to estimated_cost_microdollars

The ``agent_executions.estimated_cost_usd`` column has always stored the cost in
*microdollars* (USD x 1,000,000) — see the widening to BigInteger in
``a1b2c3d4e5f6``. The ``_usd`` suffix was therefore misleading: a reader would
reasonably assume the value is dollars and be off by a factor of one million.

This migration renames the column to ``estimated_cost_microdollars`` to match
what is actually stored. It is a pure rename — the data (already microdollars)
is untouched, so no backfill or scaling is required.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'agent_executions',
        'estimated_cost_usd',
        new_column_name='estimated_cost_microdollars',
        existing_type=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'agent_executions',
        'estimated_cost_microdollars',
        new_column_name='estimated_cost_usd',
        existing_type=sa.BigInteger(),
        existing_nullable=True,
    )
