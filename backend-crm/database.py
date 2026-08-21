# backend/database.py
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

# =========================
# Caminho do banco
# =========================
# CRÍTICO: em produção (Railway), CRM_DB_PATH TEM de apontar para dentro do
# volume persistente montado no serviço (ex.: /data/crm.db) — nunca para um
# caminho relativo. O filesystem do container é recriado do zero a cada
# deploy/restart; só o volume sobrevive. Já perdemos leads em produção por
# esse motivo (ver docs/architecture/_mapa-sistema.md, secção "Persistência
# em produção") — não remover nem "simplificar" este fallback sem entender
# essa história.
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.environ.get("CRM_DB_PATH") or os.path.join(BASE_DIR, "database", "crm.db")
DB_DIR = os.path.dirname(DB_PATH)

if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("CRM_DB_PATH"):
    raise RuntimeError(
        "CRM_DB_PATH não está definida em produção "
        f"(RAILWAY_ENVIRONMENT={os.environ.get('RAILWAY_ENVIRONMENT')!r}). "
        "O banco de dados dos leads NÃO persiste entre deploys/restarts sem "
        "isso — defina CRM_DB_PATH apontando para o volume persistente do "
        "serviço (ex.: /data/crm.db). Ver docs/architecture/_mapa-sistema.md, "
        "secção 'Persistência em produção'."
    )


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


def backfill_leads_agent_type(conn: sqlite3.Connection) -> int:
    """Preenche leads.agent_type nulo com snapshot atual do AI Profile do usuário."""
    from services.agent_type import resolve_agent_type_for_user

    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT id, user_id
          FROM leads
         WHERE agent_type IS NULL OR trim(coalesce(agent_type, '')) = ''
        """
    ).fetchall()

    updated = 0
    for row in rows:
        lead_id = int(row["id"])
        user_id = row["user_id"]
        agent_type = resolve_agent_type_for_user(user_id=int(user_id)) if user_id else "agent_1"
        cur.execute(
            "UPDATE leads SET agent_type = ? WHERE id = ?",
            (agent_type, lead_id),
        )
        updated += 1
    return updated


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


def ensure_followup_reconcile_guard_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de guarda idempotente para enqueue de follow-up vencido."""

    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS followup_reconcile_guard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            due_at DATETIME NOT NULL,
            job_id INTEGER,
            status TEXT NOT NULL DEFAULT 'enqueued',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lead_id, due_at),
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_followup_guard_due ON followup_reconcile_guard(due_at, lead_id);
        CREATE INDEX IF NOT EXISTS idx_followup_guard_job ON followup_reconcile_guard(job_id);
        """
    )


def ensure_notifications_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de notificações in-app por usuário (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lead_id INTEGER,
            type TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read, created_at);
        CREATE INDEX IF NOT EXISTS idx_notifications_lead ON notifications(lead_id);
        """
    )
    ensure_column(conn, "notifications", "body", "body TEXT")


def ensure_unmatched_payment_events_table(conn: sqlite3.Connection) -> None:
    """Cria tabela para eventos de pagamento sem lead vinculado (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS unmatched_payment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gateway TEXT NOT NULL,
            raw_payload TEXT NOT NULL,
            buyer_email TEXT,
            buyer_phone TEXT,
            buyer_document TEXT,
            checkout_token TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_unmatched_payment_created ON unmatched_payment_events(created_at);
        """
    )


def ensure_spy_agent_tables(conn: sqlite3.Connection) -> None:
    """Cria tabelas do Agente Espião (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS spy_agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'observing'
                CHECK (status IN ('observing','analyzing','completed','failed')),
            modules_requested TEXT NOT NULL,
            use_optimized_strategy INTEGER NOT NULL DEFAULT 1,
            observation_days INTEGER NOT NULL DEFAULT 14,
            observation_start_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            observation_end_at DATETIME NOT NULL,
            analyzing_started_at DATETIME,
            completed_at DATETIME,
            leads_sampled INTEGER DEFAULT 0,
            messages_sampled INTEGER DEFAULT 0,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS spy_agent_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            module TEXT NOT NULL,
            suggestions_json TEXT,
            compatibility_json TEXT,
            applied INTEGER NOT NULL DEFAULT 0,
            applied_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES spy_agent_runs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_spy_runs_user ON spy_agent_runs(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_spy_runs_expiry ON spy_agent_runs(status, observation_end_at);
        CREATE INDEX IF NOT EXISTS idx_spy_reports_run ON spy_agent_reports(run_id);
        CREATE INDEX IF NOT EXISTS idx_spy_reports_user ON spy_agent_reports(user_id, module);

        CREATE TABLE IF NOT EXISTS spy_agent_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            spy_instance_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS spy_agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender_phone TEXT NOT NULL,
            body TEXT,
            message_type TEXT NOT NULL DEFAULT 'text',
            media_url TEXT,
            transcription TEXT,
            external_message_id TEXT,
            received_at TEXT NOT NULL,
            processed_at TEXT,
            UNIQUE(user_id, external_message_id)
        );

        CREATE INDEX IF NOT EXISTS idx_spy_config_user ON spy_agent_config(user_id);
        CREATE INDEX IF NOT EXISTS idx_spy_msgs_user ON spy_agent_messages(user_id, received_at);
        CREATE INDEX IF NOT EXISTS idx_spy_msgs_sender ON spy_agent_messages(user_id, sender_phone, received_at);
        """
    )


def ensure_business_info_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de informações gerais do negócio por usuário (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS business_info (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            field_key  TEXT NOT NULL,
            label      TEXT NOT NULL,
            value      TEXT,
            enabled    INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_business_info_user_key
            ON business_info(user_id, field_key);
        CREATE INDEX IF NOT EXISTS idx_business_info_user
            ON business_info(user_id, sort_order);
        """
    )


_BUSINESS_INFO_DEFAULTS = [
    ("horario",   "Horário de funcionamento", 0),
    ("telefone",  "Telefone para ligações",   1),
    ("email",     "E-mail de contato",        2),
    ("website",   "Website",                  3),
    ("endereco",  "Endereço",                 4),
    ("instagram", "Instagram",                5),
    ("facebook",  "Facebook",                 6),
    ("youtube",   "YouTube",                  7),
    ("whatsapp",  "WhatsApp de atendimento",  8),
]


def seed_business_info_defaults(conn: sqlite3.Connection, user_id: int) -> None:
    """Insere os campos padrão de business_info para um usuário, se ainda não existirem."""
    now = datetime.utcnow().isoformat()
    cur = conn.cursor()
    for field_key, label, sort_order in _BUSINESS_INFO_DEFAULTS:
        cur.execute(
            """
            INSERT OR IGNORE INTO business_info
                (user_id, field_key, label, value, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, NULL, 1, ?, ?, ?)
            """,
            (user_id, field_key, label, sort_order, now, now),
        )


def ensure_playground_training_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de exemplos de treino do playground (idempotente)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS playground_training_items (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT NOT NULL,
            ai_profile_id INTEGER NOT NULL,
            agent_mode    TEXT,
            phase         TEXT,
            mother_route  TEXT,
            lead_message  TEXT,
            bot_message   TEXT NOT NULL,
            rating        TEXT NOT NULL CHECK(rating IN ('ruim','regular','boa','excelente')),
            comment       TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_training_user_profile
            ON playground_training_items(user_id, ai_profile_id, agent_mode, phase);
        """
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
    ensure_column(conn, "knowledge_items", "category", "category TEXT NULL")
    ensure_column(conn, "knowledge_items", "active_in_funnel", "active_in_funnel INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "knowledge_items", "media_url", "media_url TEXT NULL")


def ensure_knowledge_item_media_table(conn: sqlite3.Connection) -> None:
    """Cria tabela de mídias por item de conhecimento (suporte a múltiplas mídias e idiomas)."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_item_media (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_item_id  INTEGER NOT NULL,
            media_url          TEXT NOT NULL,
            media_type         TEXT NOT NULL DEFAULT 'image'
                                   CHECK (media_type IN ('image','video','audio','pdf')),
            language           TEXT NOT NULL DEFAULT 'all'
                                   CHECK (language IN ('all','pt','en','es')),
            send_order         INTEGER NOT NULL DEFAULT 0,
            created_at         TEXT NOT NULL,
            FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_kim_item     ON knowledge_item_media(knowledge_item_id);
        CREATE INDEX IF NOT EXISTS idx_kim_item_ord ON knowledge_item_media(knowledge_item_id, send_order);
        """
    )


def ensure_knowledge_item_media_myaudio_type(conn: sqlite3.Connection) -> None:
    """Migration: adiciona 'myaudio' ao CHECK constraint de knowledge_item_media.media_type.
    SQLite não suporta ALTER COLUMN — recria a tabela preservando todos os dados."""
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='knowledge_item_media'")
    row = cur.fetchone()
    ddl = (row[0] if row else "") or ""
    if "myaudio" in ddl:
        return  # já migrado
    conn.executescript(
        """
        BEGIN;
        CREATE TABLE knowledge_item_media_new (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_item_id  INTEGER NOT NULL,
            media_url          TEXT NOT NULL,
            media_type         TEXT NOT NULL DEFAULT 'image'
                                   CHECK (media_type IN ('image','video','audio','pdf','myaudio','ptt')),
            language           TEXT NOT NULL DEFAULT 'all'
                                   CHECK (language IN ('all','pt','en','es')),
            send_order         INTEGER NOT NULL DEFAULT 0,
            created_at         TEXT NOT NULL,
            FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
        );
        INSERT INTO knowledge_item_media_new
            SELECT id, knowledge_item_id, media_url, media_type, language, send_order, created_at
              FROM knowledge_item_media;
        DROP TABLE knowledge_item_media;
        ALTER TABLE knowledge_item_media_new RENAME TO knowledge_item_media;
        CREATE INDEX IF NOT EXISTS idx_kim_item     ON knowledge_item_media(knowledge_item_id);
        CREATE INDEX IF NOT EXISTS idx_kim_item_ord ON knowledge_item_media(knowledge_item_id, send_order);
        COMMIT;
        """
    )


def ensure_knowledge_source_type_ai_extracted(conn: sqlite3.Connection) -> None:
    """Migration: adiciona 'ai_extracted' ao CHECK constraint de knowledge_items.source_type.

    SQLite não suporta ALTER COLUMN — recria a tabela preservando todos os dados.
    knowledge_item_media referencia knowledge_items com ON DELETE CASCADE e
    get_connection() liga PRAGMA foreign_keys=ON — o DROP TABLE precisa acontecer
    com FK OFF ou o cascade apagaria as mídias antes do rename.
    """
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='knowledge_items'")
    row = cur.fetchone()
    ddl = (row[0] if row else "") or ""
    if "ai_extracted" in ddl:
        return  # já migrado
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        CREATE TABLE knowledge_items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL CHECK(source_type IN ('manual','file','ai_extracted')),
            content_text TEXT NOT NULL,
            file_path TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            category TEXT NULL,
            active_in_funnel INTEGER NOT NULL DEFAULT 1,
            media_url TEXT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO knowledge_items_new
            (id, user_id, title, source_type, content_text, file_path,
             created_at, updated_at, category, active_in_funnel, media_url)
        SELECT id, user_id, title, source_type, content_text, file_path,
               created_at, updated_at, category, active_in_funnel, media_url
          FROM knowledge_items
        """
    )
    conn.execute("DROP TABLE knowledge_items")
    conn.execute("ALTER TABLE knowledge_items_new RENAME TO knowledge_items")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_user ON knowledge_items(user_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_user_created ON knowledge_items(user_id, created_at)"
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    print("✅ knowledge_items migration: source_type aceita 'ai_extracted'")


def migrate_knowledge_media_to_table(conn: sqlite3.Connection) -> None:
    """Migração idempotente: copia media_url existente de knowledge_items para knowledge_item_media."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ki.id, ki.media_url
          FROM knowledge_items ki
         WHERE ki.media_url IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM knowledge_item_media kim
                WHERE kim.knowledge_item_id = ki.id
           )
        """
    )
    rows = cur.fetchall()
    if not rows:
        return
    now_iso = datetime.utcnow().isoformat()
    for row in rows:
        item_id = row[0] if not hasattr(row, "keys") else row["id"]
        media_url = row[1] if not hasattr(row, "keys") else row["media_url"]
        ext = media_url.rsplit(".", 1)[-1].lower() if "." in media_url else ""
        if ext in {"mp4"}:
            media_type = "video"
        elif ext in {"pdf"}:
            media_type = "pdf"
        elif ext in {"mp3", "ogg", "opus"}:
            media_type = "myaudio"
        else:
            media_type = "image"
        cur.execute(
            """
            INSERT INTO knowledge_item_media
                (knowledge_item_id, media_url, media_type, language, send_order, created_at)
            VALUES (?, ?, ?, 'all', 0, ?)
            """,
            (item_id, media_url, media_type, now_iso),
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


def _migrate_appointments_lead_nullable(conn: sqlite3.Connection) -> None:
    """Torna lead_id nullable e adiciona user_id a appointments (para eventos Google sem lead)."""
    cur = conn.cursor()
    info = {row["name"]: row for row in cur.execute("PRAGMA table_info(appointments)").fetchall()}
    lead_col = info.get("lead_id")
    user_col = info.get("user_id")
    if lead_col and lead_col["notnull"] == 0 and user_col:
        return  # já migrado
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("""
        CREATE TABLE appointments_new (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            lead_id     INTEGER,
            title       TEXT NOT NULL,
            description TEXT,
            type        TEXT,
            start_at    DATETIME NOT NULL,
            end_at      DATETIME NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','completed','canceled')),
            location    TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            outcome     TEXT,
            outcome_note TEXT,
            outcome_at  DATETIME,
            google_event_id TEXT,
            source      TEXT NOT NULL DEFAULT 'crm',
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        INSERT INTO appointments_new
            (id, user_id, lead_id, title, description, type, start_at, end_at, status,
             location, created_at, updated_at, outcome, outcome_note, outcome_at,
             google_event_id, source)
        SELECT a.id, l.user_id, a.lead_id, a.title, a.description, a.type,
               a.start_at, a.end_at, a.status, a.location, a.created_at, a.updated_at,
               a.outcome, a.outcome_note, a.outcome_at, a.google_event_id, a.source
        FROM appointments a
        LEFT JOIN leads l ON a.lead_id = l.id
    """)
    conn.execute("DROP TABLE appointments")
    conn.execute("ALTER TABLE appointments_new RENAME TO appointments")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_lead ON appointments(lead_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_time ON appointments(lead_id, start_at, end_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user ON appointments(user_id, start_at)")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    print("✅ appointments migration: lead_id nullable + user_id adicionado")


def _migrate_leads_company_or_contact(conn: sqlite3.Connection) -> None:
    """Torna companyName nullable e adiciona CHECK garantindo companyName OU contactName preenchido.

    leads tem 7 tabelas filhas com ON DELETE CASCADE (messages, prospection_logs,
    lead_outcomes, message_selections, prospection_whatsapp_queue,
    lead_qualification_state, appointments) e PRAGMA foreign_keys=ON está ativo por
    padrão em get_connection() — por isso o DROP TABLE precisa acontecer com FK OFF,
    ou o cascade apagaria essas linhas antes do rename.
    """
    cur = conn.cursor()
    info = {row["name"]: row for row in cur.execute("PRAGMA table_info(leads)").fetchall()}
    company_col = info.get("companyName")
    if company_col and company_col["notnull"] == 0:
        return  # já migrado

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        CREATE TABLE leads_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT,
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
            priority INTEGER DEFAULT 1,
            bot_disabled INTEGER NOT NULL DEFAULT 0,
            bot_disabled_reason TEXT,
            agent_type TEXT,
            followup_contract TEXT,
            followup_status TEXT,
            next_followup_at DATETIME,
            followup_auto_trigger_last_fired_at DATETIME,
            checkout_token TEXT,
            is_playground INTEGER NOT NULL DEFAULT 0,
            detected_language TEXT NULL,
            phases_triggered TEXT NULL,
            triggers_fired TEXT NULL,
            CHECK (TRIM(COALESCE(companyName,'')) != '' OR TRIM(COALESCE(contactName,'')) != '')
        )
        """
    )
    conn.execute(
        """
        INSERT INTO leads_new (
            id, user_id, companyName, contactName, phone, email, origin, category,
            customMessage, observations, potentialValue, kanban_highlight, kanban_highlight_at,
            createdAt, lastMovement, priority, bot_disabled, bot_disabled_reason, agent_type,
            followup_contract, followup_status, next_followup_at, followup_auto_trigger_last_fired_at,
            checkout_token, is_playground, detected_language, phases_triggered, triggers_fired
        )
        SELECT
            id, user_id, companyName, contactName, phone, email, origin, category,
            customMessage, observations, potentialValue, kanban_highlight, kanban_highlight_at,
            createdAt, lastMovement, priority, bot_disabled, bot_disabled_reason, agent_type,
            followup_contract, followup_status, next_followup_at, followup_auto_trigger_last_fired_at,
            checkout_token, is_playground, detected_language, phases_triggered, triggers_fired
        FROM leads
        """
    )

    old_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    new_count = conn.execute("SELECT COUNT(*) FROM leads_new").fetchone()[0]
    if new_count != old_count:
        conn.execute("DROP TABLE leads_new")
        conn.execute("PRAGMA foreign_keys = ON")
        raise RuntimeError(f"Migração leads abortada: old={old_count} new={new_count}")

    conn.execute("DROP TABLE leads")
    conn.execute("ALTER TABLE leads_new RENAME TO leads")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_user ON leads(user_id, createdAt);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_leads_followup_due "
        "ON leads(followup_status, next_followup_at, bot_disabled, user_id);"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_playground ON leads(user_id, is_playground);")
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_user_phone ON leads(user_id, phone);")
    except sqlite3.IntegrityError:
        print("⚠️ não foi possível recriar ux_leads_user_phone: dados duplicados existentes")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    print("✅ leads migration: companyName nullable + CHECK companyName/contactName")


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

            CREATE TABLE IF NOT EXISTS lead_qualification_state (
                lead_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                stage TEXT DEFAULT 'qualification',
                agent_mode_normalized TEXT,
                playbook_key TEXT,
                playbook_version TEXT,
                data_json TEXT DEFAULT '{}',
                confidence_json TEXT DEFAULT '{}',
                last_questioned_field TEXT,
                attempts_json TEXT DEFAULT '{}',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_wq_status ON prospection_whatsapp_queue(status, enqueuedAt);
            CREATE INDEX IF NOT EXISTS idx_wq_lead ON prospection_whatsapp_queue(lead_id);
            CREATE INDEX IF NOT EXISTS idx_lqs_user_lead ON lead_qualification_state(user_id, lead_id);
            """
        )

        ensure_column(conn, "leads", "user_id", "INTEGER")
        ensure_column(conn, "leads", "bot_disabled", "bot_disabled INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "leads", "bot_disabled_reason", "bot_disabled_reason TEXT")
        ensure_column(conn, "leads", "agent_type", "agent_type TEXT")
        ensure_column(conn, "leads", "followup_contract", "followup_contract TEXT")
        ensure_column(conn, "leads", "followup_status", "followup_status TEXT")
        ensure_column(conn, "leads", "next_followup_at", "next_followup_at DATETIME")
        ensure_column(conn, "leads", "followup_auto_trigger_last_fired_at", "followup_auto_trigger_last_fired_at DATETIME")
        ensure_column(conn, "prospection_logs", "user_id", "INTEGER")
        ensure_column(conn, "prospection_logs", "email", "email TEXT")
        ensure_column(conn, "appointments", "outcome", "outcome TEXT")
        ensure_column(conn, "appointments", "outcome_note", "outcome_note TEXT")
        ensure_column(conn, "appointments", "outcome_at", "outcome_at DATETIME")
        ensure_column(conn, "appointments", "google_event_id", "google_event_id TEXT")
        ensure_column(conn, "appointments", "source", "source TEXT NOT NULL DEFAULT 'crm'")
        _migrate_appointments_lead_nullable(conn)
        ensure_column(conn, "lead_qualification_state", "asked_questions_json", "asked_questions_json TEXT DEFAULT '[]'")
        ensure_column(conn, "lead_qualification_state", "last_question_text", "last_question_text TEXT")
        ensure_column(conn, "lead_qualification_state", "power_score", "power_score INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "lead_qualification_state", "priority_score", "priority_score INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "lead_qualification_state", "price_score", "price_score INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "lead_qualification_state", "timing_score", "timing_score INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "lead_qualification_state", "qualification_total_score", "qualification_total_score INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "leads", "checkout_token", "checkout_token TEXT")
        ensure_column(conn, "leads", "is_playground", "is_playground INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "leads", "detected_language", "detected_language TEXT NULL")
        ensure_column(conn, "leads", "phases_triggered", "phases_triggered TEXT NULL")
        ensure_column(conn, "leads", "triggers_fired", "triggers_fired TEXT NULL")
        ensure_column(conn, "leads", "branches_selected", "branches_selected TEXT NULL")
        ensure_column(conn, "leads", "knowledge_categories_shown", "knowledge_categories_shown TEXT NULL")
        ensure_column(conn, "leads", "wa_display_name", "wa_display_name TEXT NULL")
        _migrate_leads_company_or_contact(conn)

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
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_followup_due "
            "ON leads(followup_status, next_followup_at, bot_disabled, user_id);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_playground "
            "ON leads(user_id, is_playground);"
        )
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

        # Guarda idempotente para evitar enqueue duplicado do reconciliador de follow-up
        ensure_followup_reconcile_guard_table(conn)

        # Notificações in-app
        ensure_notifications_table(conn)

        # Eventos de pagamento sem lead vinculado (Agent 2)
        ensure_unmatched_payment_events_table(conn)

        # Base de conhecimento por usuário
        ensure_knowledge_table(conn)
        ensure_knowledge_item_media_table(conn)
        ensure_business_info_table(conn)

        # Tabela de training do playground
        ensure_playground_training_table(conn)

        # Agente Espião
        ensure_spy_agent_tables(conn)
        ensure_column(conn, "spy_agent_messages", "from_me", "from_me INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "messages", "message_type", "message_type TEXT DEFAULT 'text'")

        # Migrações
        migrate_knowledge_media_to_table(conn)
        ensure_knowledge_item_media_myaudio_type(conn)
        ensure_knowledge_source_type_ai_extracted(conn)
        migrate_user_profile(conn)
        migrate_atividades_to_appointments(conn)  # popula appointments a partir do legado (normalizado)
        backfill_appointment_dates(conn)          # garante start/end
        normalize_appointment_timestamps(conn)    # normaliza ' ' -> 'T'
        updated_agent_type_rows = backfill_leads_agent_type(conn)
        if updated_agent_type_rows:
            print(f"✅ backfill agent_type concluído: {updated_agent_type_rows} lead(s) atualizados")

        conn.commit()
        print("✅ init_db concluído com sucesso.")
    finally:
        conn.close()
