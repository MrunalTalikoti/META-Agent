"""add_conversational_modes

Revision ID: eb0b779848e2
Revises: 20ba7ba12955
Create Date: 2026-03-13 18:36:42.164523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum


# revision identifiers, used by Alembic.
revision: str = 'eb0b779848e2'
down_revision: Union[str, None] = '20ba7ba12955'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create enums safely using PostgreSQL DO blocks (idempotent)
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE usertier AS ENUM ('FREE', 'PRO', 'ENTERPRISE');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE executionmode AS ENUM ('NORMAL', 'HARDCORE');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE conversationstatus AS ENUM ('GATHERING', 'READY', 'EXECUTING', 'COMPLETED', 'REFINING');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create conversations table
    op.create_table('conversations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('mode', PgEnum('NORMAL', 'HARDCORE', name='executionmode', create_type=False), nullable=False),
    sa.Column('status', PgEnum('GATHERING', 'READY', 'EXECUTING', 'COMPLETED', 'REFINING', name='conversationstatus', create_type=False), nullable=False),
    sa.Column('messages', sa.JSON(), nullable=False),
    sa.Column('gathered_requirements', sa.JSON(), nullable=True),
    sa.Column('final_prompt', sa.Text(), nullable=True),
    sa.Column('execution_task_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['execution_task_id'], ['tasks.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)

    # Add columns to users table
    op.add_column('users', sa.Column('tier', PgEnum('FREE', 'PRO', 'ENTERPRISE', name='usertier', create_type=False), server_default='FREE', nullable=False))
    op.add_column('users', sa.Column('requests_today', sa.Integer(), server_default='0', nullable=True))
    op.add_column('users', sa.Column('last_request_date', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('subscription_expires', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Drop columns first
    op.drop_column('users', 'subscription_expires')
    op.drop_column('users', 'last_request_date')
    op.drop_column('users', 'requests_today')
    op.drop_column('users', 'tier')
    
    # Drop table
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_table('conversations')
    
    # Drop enums LAST
    sa.Enum(name='conversationstatus').drop(op.get_bind())
    sa.Enum(name='executionmode').drop(op.get_bind())
    sa.Enum(name='usertier').drop(op.get_bind())