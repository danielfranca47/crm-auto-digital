import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

# Caminho do banco: <raiz>/database/crm.db
BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "crm.db")

def ensure_db_dir():
    # Garante que a pasta exista (útil p/ onboard em outra máquina)
    os.makedirs(DB_DIR, exist_ok=True)

def get_connection():
    ensure_db_dir()
    print("🧭 Usando banco de dados:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Integridade referencial
    conn.execute("PRAGMA foreign_keys = ON")
    # Opcional: melhor para concorrência leitura/escrita no dev
    # conn.execute("PRAGMA journal_mode = WAL")
    return conn


# =========================
# MIGRAÇÃO: USER PROFILE
# =========================
def migrate_user_profile(conn: sqlite3.Connection) -> None:
    """
    Cria a tabela user_profile (perfil único id=1) e garante o registro inicial.
    """
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            sender_name TEXT,
            sender_company TEXT,
            sender_email TEXT,
            sender_phone TEXT,
            sender_site TEXT,
            sender_signature TEXT,
            default_tone TEXT,
            default_language TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        );
    """)
    # Garante existência do registro único
    cur.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
    conn.commit()


def get_user_profile(conn: sqlite3.Connection) -> dict:
    """
    Retorna o perfil (id=1) como dict. Se não existir, devolve campos vazios.
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_profile WHERE id = 1")
    row = cur.fetchone()
    if not row:
        return {
            "id": 1,
            "sender_name": None,
            "sender_company": None,
            "sender_email": None,
            "sender_phone": None,
            "sender_site": None,
            "sender_signature": None,
            "default_tone": None,
            "default_language": None,
            "created_at": None,
            "updated_at": None,
        }
    if isinstance(row, sqlite3.Row):
        return {k: row[k] for k in row.keys()}
    return row  # fallback (caso row_factory não seja Row)


def upsert_user_profile(conn: sqlite3.Connection, data: dict) -> dict:
    """
    Atualiza os campos presentes em `data` no registro id=1.
    Retorna o perfil atualizado.
    """
    allowed = [
        "sender_name", "sender_company", "sender_email", "sender_phone", "sender_site",
        "sender_signature", "default_tone", "default_language"
    ]
    fields = []
    values = []
    for k in allowed:
        if k in data:
            fields.append(f"{k} = ?")
            values.append(data[k])

    # sempre atualiza updated_at
    fields.append("updated_at = ?")
    values.append(datetime.utcnow().isoformat())

    if fields:
        sql = f"UPDATE user_profile SET {', '.join(fields)} WHERE id = 1"
        cur = conn.cursor()
        cur.execute(sql, tuple(values))
        conn.commit()

    return get_user_profile(conn)


def init_db():
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Tabela leads
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            companyName TEXT NOT NULL,
            contactName TEXT,
            phone TEXT,
            email TEXT,
            origin TEXT DEFAULT 'Manual',
            category TEXT DEFAULT 'to-prospect',
            customMessage TEXT,
            observations TEXT,
            potentialValue REAL DEFAULT 0,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP,
            priority INTEGER DEFAULT 1
        );
        """)

        # Tabela atividades
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            tipo TEXT,
            descricao TEXT,
            status TEXT DEFAULT 'concluido',
            data_atividade DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id)
        );
        """)

        # Tabela métricas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metricas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_referencia DATE,
            prospeccoes_realizadas INTEGER DEFAULT 0,
            reunioes_agendadas INTEGER DEFAULT 0,
            vendas_fechadas INTEGER DEFAULT 0,
            valor_vendas REAL DEFAULT 0,
            meta_prospeccoes INTEGER DEFAULT 10,
            meta_reunioes INTEGER DEFAULT 5,
            meta_vendas INTEGER DEFAULT 3
        );
        """)

        # messages (copys por canal)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            channel TEXT NOT NULL CHECK (channel IN ('email','whatsapp','instagram','call')),
            subject TEXT,
            body TEXT NOT NULL,
            model TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        );
        """)

        # --- PROSPECÇÃO: tabelas auxiliares (idempotentes) ---
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            channel TEXT NULL,               -- 'email'|'whatsapp'|'instagram'|'call'|NULL
            message_id INTEGER NULL,
            action TEXT NOT NULL,            -- 'copied'|'wa_opened'|'mail_opened'|'sent'|'replied'|'moved_stage'|'scheduled_followup'
            notes TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS message_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            channel TEXT NOT NULL,           -- 'email'|'whatsapp'|'instagram'|'call'
            message_id INTEGER NOT NULL,
            selectedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lead_id, channel),
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        );
        """)

        # --- Fila de envios WhatsApp (idempotente) ---
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS prospection_whatsapp_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed')),
            attempts INTEGER DEFAULT 0,
            lastError TEXT,
            enqueuedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            processedAt DATETIME NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_wq_status ON prospection_whatsapp_queue(status, enqueuedAt);
        CREATE INDEX IF NOT EXISTS idx_wq_lead ON prospection_whatsapp_queue(lead_id);
        """)

        # Índices úteis
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_lead_id ON messages(lead_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_lead_channel ON messages(lead_id, channel, createdAt);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);")

        # >>>>> MIGRAÇÃO DE USER PROFILE <<<<<
        migrate_user_profile(conn)

        conn.commit()
        print("✅ init_db concluído com sucesso.")
    finally:
        conn.close()
