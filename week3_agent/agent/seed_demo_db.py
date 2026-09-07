"""Rebuild ``week3_agent/data/demo.db`` from schema SQL + seed rows.

Deletes any existing database, applies ``sql/001_schema.sql``, then inserts
demo customers, products, and orders. Only this script should write to the DB;
the agent opens it read-only.

Run from AI-Internship repo root::

  uv run python week3_agent/agent/seed_demo_db.py

Or from inside ``week3_agent/``::

  uv run python agent/seed_demo_db.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEEK3_ROOT = HERE.parent
DB_PATH = WEEK3_ROOT / "data" / "demo.db"
SCHEMA_PATH = WEEK3_ROOT / "sql" / "001_schema.sql"

CUSTOMERS = [
    (1, "Ana Souza", "São Paulo", "2024-01-10"),
    (2, "Bruno Lima", "Rio de Janeiro", "2024-01-15"),
    (3, "Carla Mendes", "Belo Horizonte", "2024-02-01"),
    (4, "Diego Alves", "São Paulo", "2024-02-12"),
    (5, "Elena Costa", "Curitiba", "2024-03-05"),
    (6, "Felipe Rocha", "Porto Alegre", "2024-03-18"),
    (7, "Giulia Martins", "São Paulo", "2024-04-02"),
    (8, "Henrique Dias", "Rio de Janeiro", "2024-04-20"),
    (9, "Isabela Freitas", "Salvador", "2024-05-08"),
    (10, "João Pereira", "Brasília", "2024-05-22"),
    (11, "Karen Nunes", "Curitiba", "2024-06-01"),
    (12, "Lucas Barbosa", "Belo Horizonte", "2024-06-15"),
]

PRODUCTS = [
    (1, "Protein Whey 1kg", "supplements", 49.90),
    (2, "Yoga Mat Pro", "equipment", 35.00),
    (3, "Clinic Gloves Box", "supplies", 12.50),
    (4, "Resistance Bands Set", "equipment", 22.00),
    (5, "Vitamin D 60ct", "supplements", 18.75),
    (6, "Face Towels Pack", "supplies", 9.90),
    (7, "Smart Scale", "equipment", 89.00),
    (8, "Creatine 300g", "supplements", 27.50),
]

# (id, customer_id, product_id, amount_usd, status, created_at)
ORDERS = [
    (1, 1, 1, 49.90, "completed", "2024-06-01"),
    (2, 1, 5, 18.75, "completed", "2024-06-03"),
    (3, 2, 2, 35.00, "completed", "2024-06-05"),
    (4, 2, 7, 89.00, "cancelled", "2024-06-06"),
    (5, 3, 3, 12.50, "completed", "2024-06-08"),
    (6, 3, 6, 9.90, "completed", "2024-06-09"),
    (7, 4, 1, 49.90, "completed", "2024-06-10"),
    (8, 4, 8, 27.50, "completed", "2024-06-11"),
    (9, 4, 4, 22.00, "pending", "2024-06-12"),
    (10, 5, 2, 35.00, "completed", "2024-06-14"),
    (11, 5, 5, 18.75, "completed", "2024-06-15"),
    (12, 6, 7, 89.00, "completed", "2024-06-16"),
    (13, 6, 1, 49.90, "cancelled", "2024-06-17"),
    (14, 7, 1, 49.90, "completed", "2024-06-18"),
    (15, 7, 8, 27.50, "completed", "2024-06-19"),
    (16, 7, 5, 18.75, "completed", "2024-06-20"),
    (17, 8, 2, 35.00, "completed", "2024-06-21"),
    (18, 8, 4, 22.00, "pending", "2024-06-22"),
    (19, 9, 3, 12.50, "completed", "2024-06-23"),
    (20, 9, 6, 9.90, "completed", "2024-06-24"),
    (21, 10, 7, 89.00, "completed", "2024-06-25"),
    (22, 10, 1, 49.90, "cancelled", "2024-06-26"),
    (23, 11, 5, 18.75, "completed", "2024-06-27"),
    (24, 11, 2, 35.00, "completed", "2024-06-28"),
    (25, 12, 3, 12.50, "completed", "2024-06-29"),
    (26, 12, 8, 27.50, "completed", "2024-06-30"),
    (27, 1, 7, 89.00, "completed", "2024-07-01"),
    (28, 4, 7, 89.00, "completed", "2024-07-02"),
    (29, 7, 7, 89.00, "completed", "2024-07-03"),
    (30, 2, 8, 27.50, "completed", "2024-07-04"),
    (31, 5, 1, 49.90, "pending", "2024-07-05"),
    (32, 8, 1, 49.90, "completed", "2024-07-06"),
    (33, 3, 4, 22.00, "cancelled", "2024-07-07"),
    (34, 6, 5, 18.75, "completed", "2024-07-08"),
    (35, 9, 2, 35.00, "completed", "2024-07-09"),
    (36, 10, 4, 22.00, "completed", "2024-07-10"),
    (37, 11, 8, 27.50, "completed", "2024-07-11"),
    (38, 12, 1, 49.90, "completed", "2024-07-12"),
    (39, 1, 2, 35.00, "completed", "2024-07-13"),
    (40, 4, 5, 18.75, "cancelled", "2024-07-14"),
]


def main() -> None:
    """Create ``data/demo.db``, apply schema, insert seed rows, print counts."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema)
        conn.executemany(
            "INSERT INTO customers (id, name, city, created_at) VALUES (?, ?, ?, ?)",
            CUSTOMERS,
        )
        conn.executemany(
            "INSERT INTO products (id, name, category, price_usd) VALUES (?, ?, ?, ?)",
            PRODUCTS,
        )
        conn.executemany(
            "INSERT INTO orders (id, customer_id, product_id, amount_usd, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ORDERS,
        )
        conn.commit()

        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("customers", "products", "orders")
        }
    finally:
        conn.close()

    print(f"Created DB at {DB_PATH}")
    print(
        f"Seeded customers={counts['customers']} "
        f"products={counts['products']} "
        f"orders={counts['orders']}"
    )


if __name__ == "__main__":
    main()
