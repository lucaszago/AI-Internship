-- Demo ops schema for the Week 3 revenue analyst agent (SQLite).
-- Applied by agent/seed_demo_db.py; the agent only runs SELECT via run_sql.

PRAGMA foreign_keys = ON;

CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price_usd REAL NOT NULL
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  amount_usd REAL NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('completed', 'cancelled', 'pending')),
  created_at TEXT NOT NULL
);