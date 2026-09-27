"""qualification_price_disclosure: o que o agente faz quando o lead pergunta o preço durante a
qualificação — "after_qualification" (predefinido: preço fica para a apresentação) ou
"on_request" (responde com a tabela). Ver docs/architecture/knowledge-base.md."""

import asyncio
import unittest

from fastapi import BackgroundTasks

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


class AIProfilePriceDisclosureTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        self.user = models.User(email="price-tests@example.com", password_hash="secret")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()

    def _create(self):
        return asyncio.run(
            create_or_replace_ai_profile(
                AIProfileCreate(
                    template_key="hybrid_scheduler",
                    name="Agent",
                    brand_name="Sensi Vitae",
                    tone_of_voice="caloroso",
                    niche="Massagens",
                    target_audience="Adultos",
                    offer_description="Massagens",
                    goals="Agendar sessões",
                    agent_mode="agenda",
                ),
                background_tasks=BackgroundTasks(),
                current_user=self.user,
                db=self.db,
            )
        )

    def test_default_keeps_price_for_presentation(self):
        self.assertEqual(self._create().qualification_price_disclosure, "after_qualification")

    def test_update_persists_on_request(self):
        self._create()
        asyncio.run(
            update_my_ai_profile(
                AIProfileUpdate(qualification_price_disclosure="on_request"),
                background_tasks=BackgroundTasks(),
                current_user=self.user,
                db=self.db,
            )
        )
        fetched = asyncio.run(get_my_ai_profile(current_user=self.user, db=self.db))
        self.assertEqual(fetched.qualification_price_disclosure, "on_request")


if __name__ == "__main__":
    unittest.main()
