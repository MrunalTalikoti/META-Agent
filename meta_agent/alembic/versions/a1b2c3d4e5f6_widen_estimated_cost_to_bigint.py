"""widen_estimated_cost_to_bigint

Integer (max ~$2,147) overflows for high-usage projects.
BigInteger supports up to ~$9.2 quadrillion in microdollars.

Revision ID: a1b2c3d4e5f6
Revises: f3a91c2d4e55
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a91c2d4e55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'agent_executions',
        'estimated_cost_usd',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'agent_executions',
        'estimated_cost_usd',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
