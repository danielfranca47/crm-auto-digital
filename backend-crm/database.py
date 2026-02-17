# backend/database.py
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

# =========================
# Caminho do banco
# =========================
BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "crm.db")


def ensure_db_dir() -> None:
    """Garante que a pasta do banco exista."""
    os.makedirs(DB_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Abre uma conexão com o SQLite já com algumas PRAGMAs úteis."""
    ensure_db_dir()
    print("🧭 Usando banco de dados:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # conn.execute("PRAGMA journal_mode = WAL")  # opcional
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Adiciona coluna se ela não existir (idempotente)."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def ensure_jobs_tables(conn: sqlite3.Connection) -> None:
    """Cria as tabelas de agentes e jobs (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            token TEXT,
            status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('offline','online','disabled')),
            capabilities TEXT,
            version TEXT,
            last_seen DATETIME,
            last_seen_at DATETIME,
            revoked_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','failed')),
            priority INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            assigned_agent_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            scheduled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            result TEXT,
            error TEXT,
            FOREIGN KEY (assigned_agent_id) REFERENCES agents(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status_type ON jobs(status, type, scheduled_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_assigned ON jobs(assigned_agent_id, status);
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
        """
    )

    ensure_column(conn, "agents", "user_id", "INTEGER")
    ensure_column(conn, "agents", "last_seen_at", "DATETIME")
    ensure_column(conn, "agents", "revoked_at", "DATETIME")
    ensure_column(conn, "jobs", "user_id", "INTEGER")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, status);")


def ensure_inbound_events_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de eventos inbound (idempotente) para idempotência de webhooks."""

    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS inbound_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            external_event_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider, instance_id, external_event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_inbound_events_user ON inbound_events(user_id);
        CREATE INDEX IF NOT EXISTS idx_inbound_events_instance ON inbound_events(instance_id);
        """
    )


def ensure_orion_conversations_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de conversas Orion (idempotente) para contagem mensal por telefone."""

    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS orion_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone_e164 TEXT NOT NULL,
            month_key TEXT NOT NULL,
            lead_id INTEGER NULL,
            first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, phone_e164, month_key)
        );

        CREATE INDEX IF NOT EXISTS idx_orion_conv_user_month ON orion_conversations(user_id, month_key);
        CREATE INDEX IF NOT EXISTS idx_orion_conv_user_phone ON orion_conversations(user_id, phone_e164);
        """
    )


def ensure_outbound_events_table(conn: sqlite3.Connection) -> None:
    """Cria tabela idempotente para registrar envios outbound e evitar duplicação."""

    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS outbound_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            provider_message_id TEXT NULL,
            in_reply_to_message_id TEXT NULL,
            message_id INTEGER NULL,
            status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved','sent','failed')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, in_reply_to_message_id)
        );

        CREATE INDEX IF NOT EXISTS idx_outbound_job ON outbound_events(job_id);
        CREATE INDEX IF NOT EXISTS idx_outbound_reply ON outbound_events(in_reply_to_message_id);
        CREATE INDEX IF NOT EXISTS idx_outbound_user ON outbound_events(user_id);
        """
    )
    ensure_column(conn, "outbound_events", "message_id", "message_id INTEGER NULL")
    ensure_column(
        conn,
        "outbound_events",
        "status",
        "status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved','sent','failed'))",
    )


def ensure_knowledge_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de knowledge base por usuário (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL CHECK(source_type IN ('manual','file')),
            content_text TEXT NOT NULL,
            file_path TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_user ON knowledge_items(user_id);
        CREATE INDEX IF NOT EXISTS idx_knowledge_user_created ON knowledge_items(user_id, created_at);
        """
    )


# =========================
# APPOINTMENTS HELPERS
# =========================
def ensure_appointments_table(conn: sqlite3.Connection) -> None:
    """Cria a tabela appointments e índices, se não existirem."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT,
            start_at DATETIME NOT NULL,
            end_at DATETIME NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','completed','canceled')),
            location TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_appointments_lead ON appointments(lead_id);")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_appointments_time ON appointments(lead_id, start_at, end_at);"
    )


def normalize_datetime_value(value: Optional[Any]) -> Optional[str]:
    """
    Converte valores aceitos (datetime ou string) para ISO 8601 com 'T'.
    Também converte 'Z' para '+00:00' para evitar ValueError do fromisoformat.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        value_str = str(value).strip()
        if not value_str:
            return None

        candidate = value_str.replace(" ", "T")
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(f"Formato de data/hora inválido: {value_str}") from exc

    return dt.isoformat()


def normalize_appointment_timestamps(conn: sqlite3.Connection) -> None:
    """Garante que start_at/end_at usem sempre o separador 'T' (ISO)."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE appointments
        SET
            start_at = REPLACE(start_at, ' ', 'T'),
            end_at = CASE
                WHEN end_at IS NOT NULL THEN REPLACE(end_at, ' ', 'T')
                ELSE NULL
            END
        WHERE
            (start_at IS NOT NULL AND INSTR(start_at, ' ') > 0)
            OR (end_at IS NOT NULL AND INSTR(end_at, ' ') > 0)
        """
    )


def backfill_appointment_dates(conn: sqlite3.Connection) -> None:
    """Garante que start_at e end_at estejam coerentes em registros existentes."""
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat()

    # Preenche start_at nulo
    cur.execute(
        """
        UPDATE appointments
        SET start_at = COALESCE(start_at, created_at, ?)
        WHERE start_at IS NULL
        """,
        (now_iso,),
    )

    # end_at nulo vira start_at (ou created_at); e corrige end_at < start_at
    cur.execute(
        """
        UPDATE appointments
        SET end_at = CASE
            WHEN end_at IS NULL THEN COALESCE(start_at, created_at, ?)
            WHEN end_at < start_at THEN start_at
            ELSE end_at
        END
        WHERE end_at IS NULL OR end_at < start_at
        """,
        (now_iso,),
    )


def migrate_atividades_to_appointments(conn: sqlite3.Connection) -> None:
    """
    Migra dados da tabela legado 'atividades' para 'appointments' (idempotente),
    normalizando timestamps e evitando duplicatas evidentes.
    """
    cur = conn.cursor()

    # Existe a tabela de atividades?
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='atividades'")
    if not cur.fetchone():
        return

    cur.execute(
        """
        SELECT id, lead_id, tipo, descricao, status, data_atividade
        FROM atividades
        WHERE lead_id IS NOT NULL
        """
    )
    rows = cur.fetchall()
    if not rows:
        return

    status_map = {
        "concluido": "completed",
        "concluído": "completed",
        "cancelado": "canceled",
        "pendente": "pending",
    }

    to_insert = []
    for row in rows:
        row_d = {k: row[k] for k in row.keys()} if isinstance(row, sqlite3.Row) else row

        start_iso = normalize_datetime_value(row_d.get("data_atividade")) or datetime.utcnow().isoformat()
        title = row_d.get("tipo") or "Atividade"
        raw_status = (row_d.get("status") or "").lower()
        status = status_map.get(raw_status, raw_status if raw_status in status_map.values() else "pending")
        description = row_d.get("descricao")
        created_at = start_iso

        # Evita duplicata óbvia (mesmo lead, mesma descrição e mesmo start)
        cur.execute(
            """
            SELECT 1
            FROM appointments
            WHERE lead_id = ?
              AND COALESCE(description,'') = COALESCE(?, '')
              AND datetime(start_at) = datetime(?)
            LIMIT 1
            """,
            (row_d.get("lead_id"), description, start_iso),
        )
        if cur.fetchone():
            continue

        to_insert.append(
            (
                row_d.get("lead_id"),
                title,
                description,
                row_d.get("tipo"),
                start_iso,
                start_iso,   # end_at = start_at para itens legados (sem duração)
                status,
                None,        # location
                created_at,
                created_at,
            )
        )

    if to_insert:
        cur.executemany(
            """
            INSERT INTO appointments (
                lead_id, title, description, type, start_at, end_at, status, location, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            to_insert,
        )


# =========================
# MIGRAÇÃO: USER PROFILE
# =========================
def migrate_user_profile(conn: sqlite3.Connection) -> None:
    """
    Cria a tabela user_profile (perfil único id=1) e garante o registro inicial.
    """
    cur = conn.cursor()
    cur.execute(
        """
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
        """
    )
    cur.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
    conn.commit()


def get_user_profile(conn: sqlite3.Connection) -> dict:
    """Retorna o perfil (id=1) como dict."""
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
    return {k: row[k] for k in row.keys()} if isinstance(row, sqlite3.Row) else row


def upsert_user_profile(conn: sqlite3.Connection, data: dict) -> dict:
    """Atualiza os campos presentes em `data` no registro id=1 e retorna o perfil atualizado."""
    allowed = [
        "sender_name",
        "sender_company",
        "sender_email",
        "sender_phone",
        "sender_site",
        "sender_signature",
        "default_tone",
        "default_language",
    ]
    fields, values = [], []
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


# =========================
# INIT
# =========================
def init_db() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Tabela leads
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                companyName TEXT NOT NULL,
                contactName TEXT,
                phone TEXT,
                email TEXT,
                origin TEXT DEFAULT 'Manual',
                category TEXT DEFAULT 'to-prospect',
                customMessage TEXT,
                observations TEXT,
                potentialValue REAL DEFAULT 0,
                kanban_highlight TEXT,
                kanban_highlight_at DATETIME,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP,
                priority INTEGER DEFAULT 1
            );
            """
        )

        # Tabela atividades (legado)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS atividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                tipo TEXT,
                descricao TEXT,
                status TEXT DEFAULT 'concluido',
                data_atividade DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """
        )

        # Nova tabela de compromissos
        ensure_appointments_table(conn)

        # Tabelas auxiliares / índices
        cur.executescript(
            """
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

            CREATE TABLE IF NOT EXISTS prospection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lead_id INTEGER NOT NULL,
                channel TEXT NULL,
                message_id INTEGER NULL,
                action TEXT NOT NULL,
                notes TEXT,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS lead_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                user_id INTEGER,
                outcome TEXT,
                highlight TEXT,
                reason TEXT,
                source_job_id INTEGER,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS message_selections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                selectedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (lead_id, channel),
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            );

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
            """
        )

        ensure_column(conn, "leads", "user_id", "INTEGER")
        ensure_column(conn, "leads", "bot_disabled", "bot_disabled INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "prospection_logs", "user_id", "INTEGER")
        ensure_column(conn, "appointments", "outcome", "outcome TEXT")
        ensure_column(conn, "appointments", "outcome_note", "outcome_note TEXT")
        ensure_column(conn, "appointments", "outcome_at", "outcome_at DATETIME")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_user ON leads(user_id, createdAt);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_prospection_logs_user ON prospection_logs(user_id, createdAt);"
        )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_lead_id ON messages(lead_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_lead_channel ON messages(lead_id, channel, createdAt);"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);")
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_user_phone ON leads(user_id, phone);")
        except sqlite3.IntegrityError:
            print("⚠️ não foi possível criar ux_leads_user_phone: dados duplicados existentes")

        # Novas tabelas de automação distribuída (agents/jobs)
        ensure_jobs_tables(conn)

        # Idempotência de webhooks inbound
        ensure_inbound_events_table(conn)

        # Contagem de conversas Orion por telefone/mês
        ensure_orion_conversations_table(conn)

        # Controle de envios outbound para evitar duplicação pelo executor
        ensure_outbound_events_table(conn)

        # Base de conhecimento por usuário
        ensure_knowledge_table(conn)

        # Migrações
        migrate_user_profile(conn)
        migrate_atividades_to_appointments(conn)  # popula appointments a partir do legado (normalizado)
        backfill_appointment_dates(conn)          # garante start/end
        normalize_appointment_timestamps(conn)    # normaliza ' ' -> 'T'

        conn.commit()
        print("✅ init_db concluído com sucesso.")
    finally:
        conn.close()
