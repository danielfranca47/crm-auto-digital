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


class AIProfileAgentModeTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        self.user = models.User(email="agent-mode@example.com", password_hash="secret")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()

    def test_create_update_profile_persists_agent_mode(self):
        payload = AIProfileCreate(
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
            agent_mode="closer",
        )
        created = asyncio.run(
            create_or_replace_ai_profile(payload, current_user=self.user, db=self.db)
        )
        self.assertEqual(created.agent_mode, "closer")
        self.assertEqual(created.timezone, "Europe/Lisbon")

        updated = asyncio.run(
            update_my_ai_profile(
                AIProfileUpdate(agent_mode="sdr_scheduler", timezone="America/Sao_Paulo"),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(updated.agent_mode, "sdr_scheduler")
        self.assertEqual(updated.timezone, "America/Sao_Paulo")

        fetched = asyncio.run(get_my_ai_profile(current_user=self.user, db=self.db))
        self.assertEqual(fetched.agent_mode, "sdr_scheduler")
        self.assertEqual(fetched.timezone, "America/Sao_Paulo")

    def test_closer_template_defaults_agent_mode(self):
        payload = AIProfileCreate(
            template_key="closer_agressivo",
            name="Closer",
            brand_name="Auto Digital",
            tone_of_voice="direto",
            timezone="UTC",
            niche="CRM",
            target_audience="PMEs",
            offer_description="Automação de vendas",
            goals="Fechar vendas",
            custom_instructions=None,
            agent_mode=None,
        )
        created = asyncio.run(
            create_or_replace_ai_profile(payload, current_user=self.user, db=self.db)
        )
        self.assertEqual(created.agent_mode, "closer")

    def test_update_profile_allows_explicit_null_clear(self):
        created = asyncio.run(
            create_or_replace_ai_profile(
                AIProfileCreate(
                    template_key="sdr_padrao",
                    name="Agent",
                    brand_name="Auto Digital",
                    tone_of_voice="profissional",
                    timezone="UTC",
                    niche="CRM",
                    target_audience="PMEs",
                    offer_description="Automação de vendas",
                    goals="Agendar reuniões",
                    agent_mode="agenda",
                    presentation_variant="sales",
                    offer_pack={"items": [{"name": "Plano", "checkout_link": "https://exemplo.com/x"}]},
                ),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(created.presentation_variant, "sales")
        self.assertIsInstance(created.offer_pack, dict)

        updated = asyncio.run(
            update_my_ai_profile(
                AIProfileUpdate(
                    agent_mode="agenda",
                    presentation_variant=None,
                    offer_pack=None,
                ),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(updated.agent_mode, "agenda")
        self.assertIsNone(updated.presentation_variant)
        self.assertIsNone(updated.offer_pack)

    def test_direto_agent_presentation_variant_forced_to_sales(self):
        created = asyncio.run(
            create_or_replace_ai_profile(
                AIProfileCreate(
                    template_key="closer_agressivo",
                    name="Closer",
                    brand_name="Auto Digital",
                    tone_of_voice="direto",
                    timezone="UTC",
                    niche="CRM",
                    target_audience="PMEs",
                    offer_description="Automação de vendas",
                    goals="Fechar vendas",
                    agent_mode="direto",
                    presentation_variant="scheduler",
                ),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(created.presentation_variant, "sales")

        updated = asyncio.run(
            update_my_ai_profile(
                AIProfileUpdate(presentation_variant="scheduler"),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(updated.presentation_variant, "sales")

    def test_ensure_ai_profile_columns_adds_timezone_without_reset(self):
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
            col_names = {col["name"] for col in inspector.get_columns("ai_profiles")}
            self.assertIn("timezone", col_names)

            with legacy_engine.begin() as conn:
                row = conn.execute(text("SELECT timezone FROM ai_profiles WHERE id = 1")).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "UTC")
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_hybrid_scheduler_template_is_valid(self):
        created = asyncio.run(
            create_or_replace_ai_profile(
                AIProfileCreate(
                    template_key="hybrid_scheduler",
                    name="Hybrid",
                    brand_name="Auto Digital",
                    tone_of_voice="objetivo",
                    timezone="UTC",
                    niche="CRM",
                    target_audience="PMEs",
                    offer_description="Agendamento operacional",
                    goals="Agendar reuniões",
                    agent_mode="agenda",
                ),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(created.template_key, "hybrid_scheduler")


if __name__ == "__main__":
    unittest.main()
