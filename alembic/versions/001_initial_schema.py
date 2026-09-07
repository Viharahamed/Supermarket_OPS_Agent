"""001 Initial Schema for Kirana AI Agent

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-07 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. stores
    op.create_table(
        'stores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('gstin', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. products
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('unit', sa.String(length=20), nullable=False, server_default='piece'),
        sa.Column('pack_size', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1.00'),
        sa.Column('is_loose', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('cost_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('selling_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('gst_rate', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        sa.Column('hsn_code', sa.String(length=20), nullable=True),
        sa.Column('stock_quantity', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('reorder_level', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('stock_quantity >= 0', name='ck_product_stock_quantity_non_negative'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_name'), 'products', ['name'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)

    # 3. stock_movements
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('movement_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('stock_after', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stock_movements_product_id'), 'stock_movements', ['product_id'], unique=False)

    # 4. customers
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('khata_balance', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_name'), 'customers', ['name'], unique=False)
    op.create_index(op.f('ix_customers_phone'), 'customers', ['phone'], unique=True)

    # 5. bills
    op.create_table(
        'bills',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bill_number', sa.String(length=100), nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('payment_status', sa.String(length=50), nullable=False, server_default='UNPAID'),
        sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('taxable_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('cgst_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('sgst_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('tax_total', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('rounding_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('grand_total', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bills_bill_number'), 'bills', ['bill_number'], unique=True)
    op.create_index(op.f('ix_bills_customer_id'), 'bills', ['customer_id'], unique=False)
    op.create_index(op.f('ix_bills_idempotency_key'), 'bills', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_bills_status'), 'bills', ['status'], unique=False)

    # 6. bill_items
    op.create_table(
        'bill_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bill_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('product_name_snapshot', sa.String(length=255), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('gst_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('hsn_code', sa.String(length=20), nullable=True),
        sa.Column('taxable_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('cgst', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('sgst', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bill_id'], ['bills.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bill_items_bill_id'), 'bill_items', ['bill_id'], unique=False)
    op.create_index(op.f('ix_bill_items_product_id'), 'bill_items', ['product_id'], unique=False)

    # 7. khata_transactions
    op.create_table(
        'khata_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('bill_id', sa.Integer(), nullable=True),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bill_id'], ['bills.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_khata_transactions_bill_id'), 'khata_transactions', ['bill_id'], unique=False)
    op.create_index(op.f('ix_khata_transactions_customer_id'), 'khata_transactions', ['customer_id'], unique=False)
    op.create_index(op.f('ix_khata_transactions_idempotency_key'), 'khata_transactions', ['idempotency_key'], unique=True)

    # 8. owner_preferences
    op.create_table(
        'owner_preferences',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    # 9. agent_sessions
    op.create_table(
        'agent_sessions',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('history_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('agent_sessions')
    op.drop_table('owner_preferences')
    op.drop_index(op.f('ix_khata_transactions_idempotency_key'), table_name='khata_transactions')
    op.drop_index(op.f('ix_khata_transactions_customer_id'), table_name='khata_transactions')
    op.drop_index(op.f('ix_khata_transactions_bill_id'), table_name='khata_transactions')
    op.drop_table('khata_transactions')
    op.drop_index(op.f('ix_bill_items_product_id'), table_name='bill_items')
    op.drop_index(op.f('ix_bill_items_bill_id'), table_name='bill_items')
    op.drop_table('bill_items')
    op.drop_index(op.f('ix_bills_status'), table_name='bills')
    op.drop_index(op.f('ix_bills_idempotency_key'), table_name='bills')
    op.drop_index(op.f('ix_bills_customer_id'), table_name='bills')
    op.drop_index(op.f('ix_bills_bill_number'), table_name='bills')
    op.drop_table('bills')
    op.drop_index(op.f('ix_customers_phone'), table_name='customers')
    op.drop_index(op.f('ix_customers_name'), table_name='customers')
    op.drop_table('customers')
    op.drop_index(op.f('ix_stock_movements_product_id'), table_name='stock_movements')
    op.drop_table('stock_movements')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_index(op.f('ix_products_name'), table_name='products')
    op.drop_table('products')
    op.drop_table('stores')
