"""Creates tables and inserts fake data. Run from backend/:  python -m app.db.seed"""
from app.db.database import engine, SessionLocal, Base
from app.db import models  # noqa: F401  (registers tables)
from app.db.models import Customer, Order


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Customer).count() > 0:
            print("Data already exists, skipping seed.")
            return

        customers = [
            Customer(id=1, name="Ali Khan", email="ali@example.com", phone="0300-1111111"),
            Customer(id=2, name="Sara Ahmed", email="sara@example.com", phone="0321-2222222"),
            Customer(id=3, name="Usman Raza", email="usman@example.com", phone="0333-3333333"),
        ]
        orders = [
            Order(id=1001, customer_id=1, item="Wireless Earbuds", amount=45.0, status="shipped",
                  eta="2 days", shipping_address="DHA Phase 6, Karachi"),
            Order(id=1002, customer_id=1, item="Phone Case", amount=12.0, status="delivered",
                  eta="-", shipping_address="DHA Phase 6, Karachi"),
            Order(id=1003, customer_id=2, item="Laptop Stand", amount=30.0, status="processing",
                  eta="5 days", shipping_address="Gulshan, Karachi"),
            Order(id=1004, customer_id=2, item="Smart Watch", amount=250.0, status="delivered",
                  eta="-", shipping_address="Gulshan, Karachi"),  # large amount -> escalation test
            Order(id=1005, customer_id=3, item="Bluetooth Speaker", amount=60.0, status="cancelled",
                  eta="-", shipping_address="Clifton, Karachi"),
        ]
        db.add_all(customers)
        db.add_all(orders)
        db.commit()
        print(f"Seeded {len(customers)} customers and {len(orders)} orders.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
