"""002 Multi-Tenancy and Users

Revision ID: 002_multi_tenancy_and_users
Revises: 001_initial_schema
Create Date: 2026-09-07 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_multi_tenancy_and_users'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure Store #1 exists in DB before attaching FK constraints
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO stores (id, name, address, gstin, created_at, updated_at) "
            "SELECT 1, 'Lakshmi Kirana & General Store', 'Shop #4, Main Market, MG Road, Bengaluru', '29ABCDE1234F1Z5', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM stores WHERE id = 1)"
        )
    )

    # 2. users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='OPERATOR'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_store_id'), 'users', ['store_id'], unique=False)
    op.create_index(op.f('ix_users_telegram_user_id'), 'users', ['telegram_user_id'], unique=True)

    # 3. Add store_id to products
    op.add_column('products', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_products_store_id'), 'products', ['store_id'], unique=False)

    # 4. Add store_id to stock_movements
    op.add_column('stock_movements', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_stock_movements_store_id'), 'stock_movements', ['store_id'], unique=False)

    # 5. Add store_id to customers
    op.add_column('customers', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_customers_store_id'), 'customers', ['store_id'], unique=False)

    # 6. Add store_id to bills
    op.add_column('bills', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_bills_store_id'), 'bills', ['store_id'], unique=False)

    # 7. Add store_id to khata_transactions
    op.add_column('khata_transactions', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_khata_transactions_store_id'), 'khata_transactions', ['store_id'], unique=False)

    # 8. Add store_id to owner_preferences
    op.add_column('owner_preferences', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))

    # 9. Add store_id to agent_sessions
    op.add_column('agent_sessions', sa.Column('store_id', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('agent_sessions', 'store_id')
    op.drop_column('owner_preferences', 'store_id')
    op.drop_index(op.f('ix_khata_transactions_store_id'), table_name='khata_transactions')
    op.drop_column('khata_transactions', 'store_id')
    op.drop_index(op.f('ix_bills_store_id'), table_name='bills')
    op.drop_column('bills', 'store_id')
    op.drop_index(op.f('ix_customers_store_id'), table_name='customers')
    op.drop_column('customers', 'store_id')
    op.drop_index(op.f('ix_stock_movements_store_id'), table_name='stock_movements')
    op.drop_column('stock_movements', 'store_id')
    op.drop_index(op.f('ix_products_store_id'), table_name='products')
    op.drop_column('products', 'store_id')
    op.drop_index(op.f('ix_users_telegram_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_store_id'), table_name='users')
    op.drop_table('users')
