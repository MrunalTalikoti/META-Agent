"""add_extended_agent_types

Revision ID: f3a91c2d4e55
Revises: 97e6945f15bc
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a91c2d4e55'
down_revision: Union[str, None] = '97e6945f15bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TYPE agenttype ADD VALUE IF NOT EXISTS 'frontend_generator'"))
    conn.execute(sa.text("ALTER TYPE agenttype ADD VALUE IF NOT EXISTS 'devops'"))
    conn.execute(sa.text("ALTER TYPE agenttype ADD VALUE IF NOT EXISTS 'security_auditor'"))
    conn.execute(sa.text("ALTER TYPE agenttype ADD VALUE IF NOT EXISTS 'performance_optimizer'"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type
    pass
