import asyncio
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.api.ai_profiles import (
    AIProfileCreate,
    AIProfileUpdate,
    create_or_replace_ai_profile,
    get_my_ai_profile,
    update_my_ai_profile,
)
from app.db import Base


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

        updated = asyncio.run(
            update_my_ai_profile(
                AIProfileUpdate(agent_mode="sdr_scheduler"),
                current_user=self.user,
                db=self.db,
            )
        )
        self.assertEqual(updated.agent_mode, "sdr_scheduler")

        fetched = asyncio.run(get_my_ai_profile(current_user=self.user, db=self.db))
        self.assertEqual(fetched.agent_mode, "sdr_scheduler")

    def test_closer_template_defaults_agent_mode(self):
        payload = AIProfileCreate(
            template_key="closer_agressivo",
            name="Closer",
            brand_name="Auto Digital",
            tone_of_voice="direto",
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


if __name__ == "__main__":
    unittest.main()
