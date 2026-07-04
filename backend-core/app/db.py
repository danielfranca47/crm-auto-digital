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


def ensure_plan_limits_columns() -> None:
    """Add feature-gate columns to plan_limits without requiring migrations."""
    cols = {"follow_up_enabled": ("INTEGER", "BOOLEAN", "1"), "playground_monthly_limit": ("INTEGER", "INTEGER", None)}
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(text("PRAGMA table_info(plan_limits)"))
            existing = {row[1] for row in result.fetchall()}
            for col, (sqlite_type, _, default) in cols.items():
                if col not in existing:
                    sql = f"ALTER TABLE plan_limits ADD COLUMN {col} {sqlite_type}"
                    if default is not None:
                        sql += f" DEFAULT {default}"
                    conn.execute(text(sql))
                    print(f"✅ coluna adicionada em plan_limits: {col}")
        else:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='plan_limits'"))
            existing = {row[0] for row in result.fetchall()}
            for col, (_, pg_type, default) in cols.items():
                if col not in existing:
                    sql = f"ALTER TABLE plan_limits ADD COLUMN {col} {pg_type}"
                    if default is not None:
                        sql += f" DEFAULT {default}"
                    conn.execute(text(sql))


def ensure_subscription_columns() -> None:
    """Add trial_ends_at and expiry_warning_sent to subscriptions without requiring migrations."""
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(text("PRAGMA table_info(subscriptions)"))
            existing = {row[1] for row in result.fetchall()}
            if "trial_ends_at" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN trial_ends_at DATETIME"))
                print("✅ coluna adicionada em subscriptions: trial_ends_at")
            if "expiry_warning_sent" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN expiry_warning_sent INTEGER NOT NULL DEFAULT 0"))
                print("✅ coluna adicionada em subscriptions: expiry_warning_sent")
            if "expiry_warning_stage" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN expiry_warning_stage INTEGER"))
                print("✅ coluna adicionada em subscriptions: expiry_warning_stage")
            if "origin_offer" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN origin_offer TEXT"))
                print("✅ coluna adicionada em subscriptions: origin_offer")
        else:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='subscriptions'"))
            existing = {row[0] for row in result.fetchall()}
            if "trial_ends_at" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN trial_ends_at TIMESTAMP"))
            if "expiry_warning_sent" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN expiry_warning_sent BOOLEAN NOT NULL DEFAULT FALSE"))
            if "expiry_warning_stage" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN expiry_warning_stage INTEGER"))
            if "origin_offer" not in existing:
                conn.execute(text("ALTER TABLE subscriptions ADD COLUMN origin_offer VARCHAR"))


def ensure_user_columns() -> None:
    """Add optional columns to the users table without requiring full migrations."""
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(text("PRAGMA table_info(users)"))
            existing = {row[1] for row in result.fetchall()}
            if "name" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN name TEXT"))
                print("✅ coluna adicionada em users: name")
        else:
            result = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users'"
                )
            )
            existing = {row[0] for row in result.fetchall()}
            if "name" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR"))
                print("✅ coluna adicionada em users: name")


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
        "followup_auto_trigger_enabled": {"default": False, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
        "followup_auto_trigger_inactivity_days": {"default": 3, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "followup_checkin_auto_trigger_enabled": {"default": False, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
        "followup_checkin_inactivity_days": {"default": 30, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "origin_inbound_opener": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "origin_outbound_opener": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "followup_sdr_instructions":              {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "followup_recovery_instructions":         {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "followup_postsession_instructions":      {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "followup_checkin_instructions":          {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "followup_goal_instructions":             {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "cart_recovery_attempt_instructions":     {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "followup_outcome_instructions":          {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "objection_common": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "qualification_score_threshold": {"default": 6, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "nurture_vs_discard_rule": {"default": "discard", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "appointment_reminder_offsets": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "briefing_enabled": {"default": True, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
        "briefing_channel": {"default": "whatsapp", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "briefing_lead_time": {"default": 120, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "operator_whatsapp": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "payment_gateway": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "payment_webhook_secret": {"default": None, "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "buying_signal_keywords": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "calendar_integration": {"default": "none", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "warming_social_proof": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "warming_session_preview": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "appointment_mode": {"default": "exploratory", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "scheduling_offer_style": {"default": "offer_alternatives", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "default_session_duration_minutes": {"default": 30, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "meeting_management_enabled": {"default": True, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
        "language": {"default": "pt-BR", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "generated_prompt_parts": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "prompt_parts_generated_at": {"default": None, "sqlite_type": "TEXT", "pg_type": "TIMESTAMP"},
        "prompt_parts_version": {"default": 0, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "response_style": {"default": "active", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "qualification_required_fields": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "qualification_fields": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "custom_variables": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "enabled_extensions": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "availability_schedule": {"default": None, "sqlite_type": "TEXT", "pg_type": "TEXT"},
        "availability_mode": {"default": "24h", "sqlite_type": "TEXT", "pg_type": "VARCHAR"},
        "first_reply_delay_min_seconds": {"default": 0, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "first_reply_delay_max_seconds": {"default": 0, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "reply_delay_min_seconds": {"default": 0, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "reply_delay_max_seconds": {"default": 0, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "multi_message_buffer_seconds": {"default": 8, "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
        "sales_flow": {"default": None, "sqlite_type": "TEXT", "pg_type": "JSON"},
        "audio_transcription_enabled": {"default": False, "sqlite_type": "INTEGER", "pg_type": "BOOLEAN"},
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
        else:
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


def ensure_auth_otps_table() -> None:
    """Create auth_otps table for passwordless login flow."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at DATETIME NOT NULL,
                used INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))


def ensure_user_extra_columns() -> None:
    """Add whatsapp and sector columns to users (passwordless registration)."""
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(text("PRAGMA table_info(users)"))
            existing = {row[1] for row in result.fetchall()}
            for col in ("whatsapp", "sector"):
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TEXT"))
        else:
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
            ))
            existing = {row[0] for row in result.fetchall()}
            for col in ("whatsapp", "sector"):
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR"))


def ensure_google_calendar_columns() -> None:
    """Add Google Calendar OAuth columns to users table."""
    google_cols = [
        "google_access_token",
        "google_refresh_token",
        "google_token_expiry",
        "google_calendar_id",
        "google_email",
    ]
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(text("PRAGMA table_info(users)"))
            existing = {row[1] for row in result.fetchall()}
            for col in google_cols:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TEXT"))
                    print(f"✅ coluna adicionada em users: {col}")
        else:
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
            ))
            existing = {row[0] for row in result.fetchall()}
            for col in google_cols:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR"))
                    print(f"✅ coluna adicionada em users: {col}")
