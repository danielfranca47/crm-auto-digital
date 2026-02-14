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
        "agent_mode": "sdr_scheduler",
        "identity_mode": "human_agent",
        "handoff_policy": "keep_active_notify",
        "handoff_custom_text": None,
        "timezone": "UTC",
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

            for name, default in columns.items():
                if name in existing:
                    continue

                if default is None:
                    conn.execute(text(f"ALTER TABLE ai_profiles ADD COLUMN {name} TEXT"))
                else:
                    safe_default = str(default).replace("'", "''")
                    conn.execute(
                        text(
                            f"ALTER TABLE ai_profiles ADD COLUMN {name} TEXT DEFAULT '{safe_default}'"
                        )
                    )

                print(f"✅ coluna adicionada em ai_profiles: {name}")

            for name, default in columns.items():
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

            for name, default in columns.items():
                if name in existing:
                    continue

                if default is None:
                    conn.execute(text(f"ALTER TABLE ai_profiles ADD COLUMN {name} VARCHAR"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE ai_profiles ADD COLUMN {name} VARCHAR DEFAULT :default"),
                        {"default": default},
                    )

            for name, default in columns.items():
                if default is None:
                    continue
                conn.execute(
                    text(f"UPDATE ai_profiles SET {name} = :default WHERE {name} IS NULL"),
                    {"default": default},
                )
