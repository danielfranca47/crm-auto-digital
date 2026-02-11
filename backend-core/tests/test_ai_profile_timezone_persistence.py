import asyncio
import os
import tempfile
import unittest

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.api.ai_profiles import (
    AIProfileCreate,
    AIProfileUpdate,
    create_or_replace_ai_profile,
    get_my_ai_profile,
    update_my_ai_profile,
)
from app.db import Base, ensure_ai_profile_columns
import app.db as core_db


class AIProfileTimezonePersistenceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        self.user = models.User(email="timezone-tests@example.com", password_hash="secret")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()

    def test_create_update_get_persists_timezone(self):
        created = asyncio.run(
            create_or_replace_ai_profile(
                AIProfileCreate(
                    template_key="sdr_padrao",
                    name="Agent",
                    brand_name="Auto Digital",
                    tone_of_voice="profissional",
                    timezone="Europe/Lisbon",
                    niche="CRM",
                    target_audience="PMEs",
                    offer_description="Automação de vendas",
                    goals="Agendar reuniões",
                    custom_instructions=None,
                    agent_mode="sdr_scheduler",
                ),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(created.timezone, "Europe/Lisbon")

        updated = asyncio.run(
            update_my_ai_profile(
                AIProfileUpdate(timezone="America/Sao_Paulo"),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(updated.timezone, "America/Sao_Paulo")

        fetched = asyncio.run(get_my_ai_profile(current_user=self.user, db=self.db))
        self.assertEqual(fetched.timezone, "America/Sao_Paulo")

    def test_legacy_sqlite_without_timezone_gets_column_and_backfill(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            legacy_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
            with legacy_engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE ai_profiles (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            template_key VARCHAR NOT NULL,
                            name VARCHAR NOT NULL,
                            brand_name VARCHAR NOT NULL,
                            tone_of_voice VARCHAR NOT NULL,
                            niche VARCHAR NOT NULL,
                            target_audience VARCHAR NOT NULL,
                            offer_description VARCHAR NOT NULL,
                            goals VARCHAR NOT NULL,
                            custom_instructions VARCHAR,
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO ai_profiles (
                            id, user_id, template_key, name, brand_name, tone_of_voice,
                            niche, target_audience, offer_description, goals
                        ) VALUES (
                            1, 1, 'sdr_padrao', 'Agent', 'Brand', 'profissional',
                            'CRM', 'PMEs', 'Oferta', 'Objetivos'
                        )
                        """
                    )
                )

            old_engine = core_db.engine
            core_db.engine = legacy_engine
            try:
                ensure_ai_profile_columns()
            finally:
                core_db.engine = old_engine

            inspector = inspect(legacy_engine)
            column_names = {col["name"] for col in inspector.get_columns("ai_profiles")}
            self.assertIn("timezone", column_names)

            with legacy_engine.begin() as conn:
                pragma_rows = conn.execute(text("PRAGMA table_info(ai_profiles)")).fetchall()
                pragma_column_names = {row[1] for row in pragma_rows}
                self.assertIn("timezone", pragma_column_names)

                row = conn.execute(text("SELECT timezone FROM ai_profiles WHERE id = 1")).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "UTC")
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
