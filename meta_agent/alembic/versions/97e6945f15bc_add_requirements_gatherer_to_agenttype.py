"""add_requirements_gatherer_to_agenttype

Revision ID: 97e6945f15bc
Revises: eb0b779848e2
Create Date: 2026-03-14 12:04:34.330371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97e6945f15bc'
down_revision: Union[str, None] = 'eb0b779848e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TYPE agenttype ADD VALUE IF NOT EXISTS 'REQUIREMENTS_GATHERER'"))

def downgrade() -> None:
    # Can't remove enum values in PostgreSQL without recreating the type
    pass
