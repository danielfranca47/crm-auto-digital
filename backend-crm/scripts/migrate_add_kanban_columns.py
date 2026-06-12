import sqlite3

DB = r"C:\crm-auto-digital\backend-crm\database\crm.db"

def has_column(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)

with sqlite3.connect(DB) as conn:
    if not has_column(conn, "leads", "kanban_highlight"):
        conn.execute("ALTER TABLE leads ADD COLUMN kanban_highlight TEXT")
        print("Added leads.kanban_highlight")

    if not has_column(conn, "leads", "kanban_highlight_at"):
        conn.execute("ALTER TABLE leads ADD COLUMN kanban_highlight_at DATETIME")
        print("Added leads.kanban_highlight_at")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS lead_outcomes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lead_id INTEGER NOT NULL,
      user_id INTEGER,
      outcome TEXT,
      highlight TEXT,
      reason TEXT,
      source_job_id INTEGER,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Ensured lead_outcomes table")

print("OK")
