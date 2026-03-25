from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_whatsapp_connections_table() -> None:
    """Ensure whatsapp_connections exists without requiring migrations."""

    sqlite_table_sql = """
    CREATE TABLE IF NOT EXISTS whatsapp_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        provider VARCHAR NOT NULL DEFAULT 'uazapi',
        instance_id VARCHAR NOT NULL,
        phone_e164 VARCHAR,
        instance_token_encrypted TEXT NOT NULL,
        status VARCHAR NOT NULL DEFAULT 'active',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """

    postgres_table_sql = """
    CREATE TABLE IF NOT EXISTS whatsapp_connections (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        provider VARCHAR NOT NULL DEFAULT 'uazapi',
        instance_id VARCHAR NOT NULL,
        phone_e164 VARCHAR,
        instance_token_encrypted TEXT NOT NULL,
        status VARCHAR NOT NULL DEFAULT 'active',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    table_sql = sqlite_table_sql if engine.dialect.name == "sqlite" else postgres_table_sql

    index_sql = [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_connections_instance_id ON whatsapp_connections(instance_id)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_connections_user_id ON whatsapp_connections(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_connections_instance_id ON whatsapp_connections(instance_id)",
    ]

    with engine.begin() as conn:
        conn.execute(text(table_sql))
        for statement in index_sql:
            conn.execute(text(statement))


def ensure_ai_profile_columns() -> None:
    columns = {
        "agent_mode": {"default": "sdr_scheduler", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "presentation_variant": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "hybrid_flow_style": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "offer_pack": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "identity_mode": {"default": "human_agent", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "handoff_policy": {"default": "keep_active_notify", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "handoff_custom_text": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "timezone": {"default": "UTC", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "requires_handoff": {"default": False, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
        "human_in_loop": {"default": False, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
        "followup_cadence": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "followup_max_attempts": {"default": None, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "followup_first_offset": {"default": None, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "followup_allowed_hours": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "origin_inbound_opener": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "origin_outbound_opener": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
    }

    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            # ✅ NEW: don't crash on empty DB where ai_profiles doesn't exist yet
            table_row = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_profiles'"
                )
            ).fetchone()
            if not table_row:
                print("ℹ️ ai_profiles table not found; skipping ensure_ai_profile_columns()")
                return

            result = conn.execute(text("PRAGMA table_info(ai_profiles)"))
            existing = {row[1] for row in result.fetchall()}

            for name, config in columns.items():
                if name in existing:
                    continue

                default = config.get("default")
                sqlite_type = config.get("sqlite_type", "TEXT")
                if default is None:
                    conn.execute(text(f"ALTER TABLE ai_profiles ADD COLUMN {name} {sqlite_type}"))
                else:
                    if isinstance(default, bool):
                        sql_default = "1" if default else "0"
                    else:
                        sql_default = "'" + str(default).replace("'", "''") + "'"
                    conn.execute(
                        text(
                            f"ALTER TABLE ai_profiles ADD COLUMN {name} {sqlite_type} DEFAULT {sql_default}"
                        )
                    )

                print(f"✅ coluna adicionada em ai_profiles: {name}")

            for name, config in columns.items():
                default = config.get("default")
                if default is None:
                    continue
                conn.execute(
                    text(f"UPDATE ai_profiles SET {name} = :default WHERE {name} IS NULL"),
                    {"default": default},
                )
                print(f"✅ backfill ai_profiles.{name} com default")

        else:
            # ✅ NEW: don't crash if ai_profiles doesn't exist yet
            exists = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_name = 'ai_profiles'
                    )
                    """
                )
            ).scalar()
            if not exists:
                print("ℹ️ ai_profiles table not found; skipping ensure_ai_profile_columns()")
                return

            result = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'ai_profiles'
                    """
                )
            )
            existing = {row[0] for row in result.fetchall()}

            for name, config in columns.items():
                if name in existing:
                    continue

                default = config.get("default")
                pg_type = config.get("pg_type", "VARCHAR")
                if default is None:
                    conn.execute(text(f"ALTER TABLE ai_profiles ADD COLUMN {name} {pg_type}"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE ai_profiles ADD COLUMN {name} {pg_type} DEFAULT :default"),
                        {"default": default},
                    )

            for name, config in columns.items():
                default = config.get("default")
                if default is None:
                    continue
                conn.execute(
                    text(f"UPDATE ai_profiles SET {name} = :default WHERE {name} IS NULL"),
                    {"default": default},
                )
