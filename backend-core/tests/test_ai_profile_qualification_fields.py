"""
Testes de integração — Fase 3: qualification_fields

Verifica:
- qualification_fields é persistido corretamente
- qualification_required_fields é derivado automaticamente de qualification_fields
- campos com mode='off' ou mode='optional' NÃO entram em qualification_required_fields
- qualification_required_fields não é sobrescrito quando qualification_fields está ausente
- backward compat: registros sem qualification_fields continuam funcionando
"""
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


def _bg():
    return BackgroundTasks()


_BASE_PAYLOAD = dict(
    template_key="sdr_padrao",
    name="Test Agent",
    brand_name="Brand",
    tone_of_voice="profissional",
    timezone="UTC",
    niche="CRM",
    target_audience="PMEs",
    offer_description="Automação de vendas",
    goals="Agendar reuniões",
)

_SAMPLE_FIELDS = [
    {"key": "availability_window", "label": "Disponibilidade", "question": "Qual horário funciona?", "passive_hint": "Inferir se mencionar horário", "mode": "required"},
    {"key": "service_interest",    "label": "Serviço",         "question": "O que você busca?",     "passive_hint": "Inferir pelo contexto",         "mode": "optional"},
    {"key": "constraints",         "label": "Restrições",      "question": None,                    "passive_hint": None,                            "mode": "off"},
]


class QualificationFieldsPersistenceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = Session()
        self.user = models.User(email="qfields@example.com", password_hash="secret")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()

    def _create(self, **kwargs):
        return asyncio.run(create_or_replace_ai_profile(
            AIProfileCreate(**_BASE_PAYLOAD, **kwargs),
            _bg(),
            current_user=self.user,
            db=self.db,
        ))

    def _update(self, payload):
        return asyncio.run(update_my_ai_profile(
            payload,
            _bg(),
            current_user=self.user,
            db=self.db,
        ))

    # ------------------------------------------------------------------
    # Criação com qualification_fields
    # ------------------------------------------------------------------

    def test_create_persists_qualification_fields(self):
        profile = self._create(qualification_fields=_SAMPLE_FIELDS)
        self.assertEqual(len(profile.qualification_fields), 3)
        self.assertEqual(profile.qualification_fields[0]["key"], "availability_window")

    def test_create_derives_required_fields_from_qualification_fields(self):
        """Apenas campos mode='required' devem entrar em qualification_required_fields."""
        profile = self._create(qualification_fields=_SAMPLE_FIELDS)
        self.assertEqual(profile.qualification_required_fields, ["availability_window"])

    def test_create_with_multiple_required_fields(self):
        fields = [
            {"key": "availability_window", "label": "Disponibilidade", "mode": "required"},
            {"key": "service_interest",    "label": "Serviço",         "mode": "required"},
            {"key": "price_acceptance",    "label": "Preço",           "mode": "optional"},
        ]
        profile = self._create(qualification_fields=fields)
        self.assertCountEqual(
            profile.qualification_required_fields,
            ["availability_window", "service_interest"],
        )

    def test_create_all_optional_yields_empty_required(self):
        fields = [
            {"key": "service_interest", "label": "Serviço",    "mode": "optional"},
            {"key": "constraints",      "label": "Restrições", "mode": "off"},
        ]
        profile = self._create(qualification_fields=fields)
        self.assertEqual(profile.qualification_required_fields, [])

    # ------------------------------------------------------------------
    # Update com qualification_fields
    # ------------------------------------------------------------------

    def test_update_qualification_fields_rederives_required(self):
        self._create()
        updated = self._update(AIProfileUpdate(qualification_fields=_SAMPLE_FIELDS))
        self.assertEqual(updated.qualification_required_fields, ["availability_window"])
        self.assertEqual(len(updated.qualification_fields), 3)

    def test_update_changing_mode_updates_required_fields(self):
        self._create(qualification_fields=_SAMPLE_FIELDS)
        # Promover service_interest para required
        new_fields = [
            {"key": "availability_window", "label": "Disponibilidade", "mode": "required"},
            {"key": "service_interest",    "label": "Serviço",         "mode": "required"},
            {"key": "constraints",         "label": "Restrições",      "mode": "off"},
        ]
        updated = self._update(AIProfileUpdate(qualification_fields=new_fields))
        self.assertCountEqual(
            updated.qualification_required_fields,
            ["availability_window", "service_interest"],
        )

    # ------------------------------------------------------------------
    # Backward compat: sem qualification_fields
    # ------------------------------------------------------------------

    def test_create_without_qualification_fields_uses_mode_default(self):
        """Criação sem qualification_fields não gera qualification_fields automático."""
        profile = self._create(agent_mode="agenda")
        self.assertIsNone(profile.qualification_fields)
        # qualification_required_fields deve ter a sugestão por mode (Fase 1)
        self.assertIsNotNone(profile.qualification_required_fields)

    def test_update_without_qualification_fields_preserves_existing_required(self):
        """Update sem qualification_fields não deve alterar qualification_required_fields."""
        self._create(qualification_fields=_SAMPLE_FIELDS)
        # Faz update de outro campo sem tocar em qualification_fields
        updated = self._update(AIProfileUpdate(name="Novo Nome"))
        # required_fields deve manter o valor derivado antes
        self.assertEqual(updated.qualification_required_fields, ["availability_window"])

    # ------------------------------------------------------------------
    # Round-trip via GET
    # ------------------------------------------------------------------

    def test_get_returns_qualification_fields(self):
        self._create(qualification_fields=_SAMPLE_FIELDS)
        fetched = asyncio.run(get_my_ai_profile(current_user=self.user, db=self.db))
        self.assertIsNotNone(fetched.qualification_fields)
        self.assertEqual(len(fetched.qualification_fields), 3)

    def test_get_returns_correct_required_fields(self):
        self._create(qualification_fields=_SAMPLE_FIELDS)
        fetched = asyncio.run(get_my_ai_profile(current_user=self.user, db=self.db))
        self.assertEqual(fetched.qualification_required_fields, ["availability_window"])


if __name__ == "__main__":
    unittest.main()
