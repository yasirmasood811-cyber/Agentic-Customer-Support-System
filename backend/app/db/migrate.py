"""Adds new columns to existing tables (create_all only creates missing TABLES).
Runs at every server start and is safe to run again."""
from sqlalchemy import inspect, text

from app.db.database import engine

NEW_COLUMNS = {
    "tickets": {
        "contact_email": "VARCHAR(150)",
        "resolution_note": "TEXT",
        "resolved_at": "TIMESTAMP",
    },
    "orders": {
        "payment_intent_id": "VARCHAR(100)",
    },
}


def ensure_columns() -> None:
    inspector = inspect(engine)
    for table, columns in NEW_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        with engine.begin() as conn:
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    print(f"[migrate] added {table}.{name}")

    # Old tickets: take the contact email from the linked customer
    if not inspector.has_table("tickets") or not inspector.has_table("customers"):
        return
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE tickets SET contact_email = "
            "(SELECT email FROM customers WHERE customers.id = tickets.customer_id) "
            "WHERE contact_email IS NULL AND customer_id IS NOT NULL"
        ))
