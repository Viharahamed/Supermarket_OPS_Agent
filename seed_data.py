# seed_data.py
"""Seed Script for Kirana AI Agent.

Populates the SQLite database with realistic Indian Kirana catalog items,
prices, GST rates, HSN codes, initial stock audit logs, sample Khata customers,
and store owner preferences.
"""

from decimal import Decimal
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

from app.db.database import init_db, get_db_context
from app.db.models import Product, Customer, StockMovement, OwnerPreference, Store, KhataTransaction



def seed_store_and_preferences(db):
    """Seed store profile and owner preferences."""
    print("  🏪 Seeding Store Profile & Preferences...")
    
    store = db.query(Store).filter_by(id=1).first()
    if not store:
        store = Store(
            id=1,
            name="Lakshmi Kirana & General Store",
            address="Shop #4, Main Market, MG Road, Bengaluru, Karnataka - 560001",
            gstin="29ABCDE1234F1Z5",
        )
        db.add(store)

    preferences = [
        ("currency_symbol", "₹"),
        ("currency_code", "INR"),
        ("default_tax_policy", "INTRA_STATE_GST"),
        ("store_name", "Lakshmi Kirana & General Store"),
        ("owner_name", "Vihar"),
        ("receipt_footer", "Thank you for shopping at Lakshmi Kirana! Visit again."),
    ]
    for key, val in preferences:
        pref = db.query(OwnerPreference).filter_by(key=key).first()
        if not pref:
            db.add(OwnerPreference(key=key, value=val))
    db.commit()


def seed_products(db):
    """Seed realistic Kirana products across multiple categories."""
    print("  📦 Seeding Kirana Product Catalog...")

    products_data = [
        {
            "sku": "AASH-ATTA-05K",
            "name": "Aashirvaad Shuddh Chakki Atta 5kg",
            "brand": "Aashirvaad",
            "category": "Staples",
            "unit": "pack",
            "pack_size": Decimal("5.00"),
            "cost_price": Decimal("210.00"),
            "selling_price": Decimal("245.00"),
            "mrp": Decimal("260.00"),
            "stock_quantity": Decimal("35.00"),
            "reorder_level": Decimal("10.00"),
            "gst_rate": Decimal("0.00"),
            "hsn_code": "1101",
        },
        {
            "sku": "FORT-OIL-01L",
            "name": "Fortune Sunlite Sunflower Oil 1L",
            "brand": "Fortune",
            "category": "Oils & Ghee",
            "unit": "pouch",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("110.00"),
            "selling_price": Decimal("135.00"),
            "mrp": Decimal("145.00"),
            "stock_quantity": Decimal("24.00"),
            "reorder_level": Decimal("8.00"),
            "gst_rate": Decimal("5.00"),
            "hsn_code": "1512",
        },
        {
            "sku": "MAGG-NOOD-70G",
            "name": "Maggi 2-Minute Masala Noodles 70g",
            "brand": "Maggi",
            "category": "Instant Food",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("10.00"),
            "selling_price": Decimal("14.00"),
            "mrp": Decimal("14.00"),
            "stock_quantity": Decimal("120.00"),
            "reorder_level": Decimal("25.00"),
            "gst_rate": Decimal("12.00"),
            "hsn_code": "1902",
        },
        {
            "sku": "AMUL-BUTT-500G",
            "name": "Amul Pasteurised Butter 500g",
            "brand": "Amul",
            "category": "Dairy",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("235.00"),
            "selling_price": Decimal("275.00"),
            "mrp": Decimal("275.00"),
            "stock_quantity": Decimal("15.00"),
            "reorder_level": Decimal("5.00"),
            "gst_rate": Decimal("12.00"),
            "hsn_code": "0405",
        },
        {
            "sku": "TATA-SALT-01K",
            "name": "Tata Salt Vacuum Evaporated 1kg",
            "brand": "Tata",
            "category": "Staples",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("20.00"),
            "selling_price": Decimal("28.00"),
            "mrp": Decimal("28.00"),
            "stock_quantity": Decimal("50.00"),
            "reorder_level": Decimal("15.00"),
            "gst_rate": Decimal("0.00"),
            "hsn_code": "2501",
        },
        {
            "sku": "MADH-SUGR-01K",
            "name": "Madhur Pure & Hygienic Sugar 1kg",
            "brand": "Madhur",
            "category": "Staples",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("40.00"),
            "selling_price": Decimal("48.00"),
            "mrp": Decimal("52.00"),
            "stock_quantity": Decimal("40.00"),
            "reorder_level": Decimal("10.00"),
            "gst_rate": Decimal("5.00"),
            "hsn_code": "1701",
        },
        {
            "sku": "TOOR-DAL-01K",
            "name": "Toor Dal Premium Cleaned 1kg",
            "brand": "Kirana Pure",
            "category": "Pulses",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("125.00"),
            "selling_price": Decimal("155.00"),
            "mrp": Decimal("165.00"),
            "stock_quantity": Decimal("6.00"),  # Low stock!
            "reorder_level": Decimal("10.00"),
            "gst_rate": Decimal("0.00"),
            "hsn_code": "0713",
        },
        {
            "sku": "DETT-SOAP-125G",
            "name": "Dettol Original Bathing Soap 125g",
            "brand": "Dettol",
            "category": "Personal Care",
            "unit": "bar",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("38.00"),
            "selling_price": Decimal("48.00"),
            "mrp": Decimal("50.00"),
            "stock_quantity": Decimal("30.00"),
            "reorder_level": Decimal("8.00"),
            "gst_rate": Decimal("18.00"),
            "hsn_code": "3401",
        },
        {
            "sku": "PARL-BISC-01K",
            "name": "Parle-G Gold Biscuits 1kg",
            "brand": "Parle",
            "category": "Snacks & Biscuits",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("110.00"),
            "selling_price": Decimal("130.00"),
            "mrp": Decimal("140.00"),
            "stock_quantity": Decimal("18.00"),
            "reorder_level": Decimal("5.00"),
            "gst_rate": Decimal("18.00"),
            "hsn_code": "1905",
        },
        {
            "sku": "TAJ-TEA-500G",
            "name": "Taj Mahal Tea 500g",
            "brand": "Brooke Bond",
            "category": "Beverages",
            "unit": "pack",
            "pack_size": Decimal("1.00"),
            "cost_price": Decimal("280.00"),
            "selling_price": Decimal("340.00"),
            "mrp": Decimal("360.00"),
            "stock_quantity": Decimal("4.00"),  # Low stock!
            "reorder_level": Decimal("5.00"),
            "gst_rate": Decimal("5.00"),
            "hsn_code": "0902",
        },
    ]

    seeded_products = []
    for pdata in products_data:
        existing = db.query(Product).filter_by(sku=pdata["sku"]).first()
        if not existing:
            product = Product(**pdata, active=True)
            db.add(product)
            db.commit()
            db.refresh(product)
            seeded_products.append(product)

            # Record initial RESTOCK movement log
            movement = StockMovement(
                product_id=product.id,
                movement_type="RESTOCK",
                quantity=product.stock_quantity,
                stock_after=product.stock_quantity,
                notes=f"Initial seed stock for {product.name}",
            )
            db.add(movement)
            db.commit()

    print(f"    Added {len(seeded_products)} catalog products with stock audit logs.")


def seed_customers_and_khata(db):
    """Seed sample Kirana Khata customers with ledger balances."""
    print("  📒 Seeding Khata Customers & Ledger Balances...")

    customers_data = [
        {
            "name": "Ramesh Kumar",
            "phone": "9876543210",
            "khata_balance": Decimal("450.00"),
        },
        {
            "name": "Sunita Sharma",
            "phone": "9876543211",
            "khata_balance": Decimal("120.00"),
        },
        {
            "name": "Anil Patel",
            "phone": "9876543212",
            "khata_balance": Decimal("0.00"),
        },
    ]

    for cdata in customers_data:
        existing = db.query(Customer).filter_by(phone=cdata["phone"]).first()
        if not existing:
            cust = Customer(
                name=cdata["name"],
                phone=cdata["phone"],
                khata_balance=cdata["khata_balance"],
            )
            db.add(cust)
            db.commit()
            db.refresh(cust)

            if cdata["khata_balance"] > Decimal("0.00"):
                tx = KhataTransaction(
                    customer_id=cust.id,
                    transaction_type="CREDIT",
                    amount=cdata["khata_balance"],
                    balance_after=cdata["khata_balance"],
                    notes="Opening Khata credit balance",
                )
                db.add(tx)
                db.commit()

    print("    Seeded 3 Khata customer accounts with initial credit histories.")


def main():
    print("=" * 60)
    print("  🌾 KIRANA AI AGENT — SEEDING DEMO DATA")
    print("=" * 60)
    
    init_db()
    with get_db_context() as db:
        seed_store_and_preferences(db)
        seed_products(db)
        seed_customers_and_khata(db)

    print("\n✅ Kirana store database seeded successfully!")
    print("You can now run 'python cli.py' to query items like Maggi, Sugar, Atta, Toor Dal, or Khata balances for Ramesh!")
    print("=" * 60)


if __name__ == "__main__":
    main()
