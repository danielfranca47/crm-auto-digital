from datetime import datetime, timedelta
import sqlite3

DB_PATH = "database/crm.db"   # ajuste se necessário

lead_id = 52  # ID do lead que quer testar

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

due_time = datetime.utcnow() - timedelta(minutes=5)

cur.execute(
    """
    UPDATE leads
    SET next_followup_at = ?
    WHERE id = ?
    """,
    (due_time.isoformat(), lead_id),
)

conn.commit()

print("Follow-up vencido forçado para lead:", lead_id)