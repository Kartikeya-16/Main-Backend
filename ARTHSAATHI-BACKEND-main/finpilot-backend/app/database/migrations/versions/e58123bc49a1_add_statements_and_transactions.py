"""add statements and transactions tables

Revision ID: e58123bc49a1
Revises: d475229e011f
Create Date: 2026-09-19 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e58123bc49a1'
down_revision: Union[str, Sequence[str], None] = 'd475229e011f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add statements and transactions tables."""
    op.create_table(
        'statements',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('bank', sa.String(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('txn_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reconciled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'transactions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('statement_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('txn_date', sa.Date(), nullable=False),
        sa.Column('narration', sa.String(), nullable=False),
        sa.Column('ref_no', sa.String(), nullable=True),
        sa.Column('debit', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('credit', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('balance', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('category', sa.String(), nullable=False, server_default='uncategorized'),
        sa.Column('dedupe_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['statement_id'], ['statements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'dedupe_hash', name='uq_user_dedupe_hash')
    )
    op.create_index('ix_transactions_dedupe_hash', 'transactions', ['dedupe_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_transactions_dedupe_hash', table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('statements')
