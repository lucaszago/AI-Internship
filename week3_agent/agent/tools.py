"""Real tools for the Week 3 ops revenue analyst agent.

ADK turns functions with type hints + docstrings into callable tools.
"""

from __future__ import annotations

import sqlite3

from config import DB_PATH, MAX_ROWS


def run_sql(sql: str) -> dict:
    """Run a read-only SELECT on the ops SQLite database and return rows.

    Use this tool for any business/KPI question about customers, products, or orders.
    Only a single SELECT statement is allowed (no INSERT/UPDATE/DELETE/DROP).

    Tables:
      - customers(id, name, city, created_at)
      - products(id, name, category, price_usd)
      - orders(id, customer_id, product_id, amount_usd, status, created_at)
        status is one of: completed, cancelled, pending

    Args:
        sql: One SQLite SELECT query (optionally ending with a semicolon).

    Returns:
        On success: {"status": "ok", "columns": [...], "rows": [...], "row_count": N}
        On failure: {"status": "error", "message": "..."}
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        return {"status": "error", "message": "Empty SQL."}

    # Reject stacked statements: "SELECT 1; DELETE FROM orders"
    if ";" in cleaned:
        return {
            "status": "error",
            "message": "Only a single SELECT statement is allowed.",
        }

    if not cleaned.upper().startswith("SELECT"):
        return {
            "status": "error",
            "message": "Only SELECT queries are allowed.",
        }

    if not DB_PATH.exists():
        return {
            "status": "error",
            "message": f"Database not found at {DB_PATH}. Run seed_demo_db.py first.",
        }

    conn: sqlite3.Connection | None = None
    try:
        # Read-only connection — writes fail even if SELECT check is bypassed
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.execute(cleaned)
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(MAX_ROWS)
        return {
            "status": "ok",
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
        }
    except sqlite3.Error as exc:
        return {"status": "error", "message": str(exc)}
    finally:
        if conn is not None:
            conn.close()


# --- Manual smoke test (optional) ---
# From repo root:
#   uv run python week3_agent/agent/tools.py
if __name__ == "__main__":
    example = """
    SELECT c.city, ROUND(SUM(o.amount_usd), 2) AS revenue
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    WHERE o.status = 'completed'
    GROUP BY c.city
    ORDER BY revenue DESC
    """
    print("SELECT example:", run_sql(example))
    print("Rejected write:", run_sql("DELETE FROM orders"))
