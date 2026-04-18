"""
Testes de integração — Fase 3: _build_qualification_context + apply_mode_overrides

Verifica:
- _build_qualification_context constrói must_collect_with_questions e nice_to_collect
  corretamente a partir de qualification_fields
- Campos mode='off' são ignorados
- must_collect (lista de keys) é derivado para backward compat com executors
- Fallback para qualification_required_fields quando qualification_fields está ausente/vazio
- apply_mode_overrides injeta o contexto enriquecido no playbook
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from services.ai_orchestrator.orchestrator import (
    _build_qualification_context,
    apply_mode_overrides,
)

_SAMPLE_FIELDS = [
    {
        "key": "availability_window",
        "label": "Disponibilidade",
        "question": "Qual horário funciona?",
        "passive_hint": "Inferir se mencionar horário",
        "mode": "required",
    },
    {
        "key": "service_interest",
        "label": "Serviço",
        "question": "O que você busca?",
        "passive_hint": "Inferir pelo contexto",
        "mode": "optional",
    },
    {
        "key": "constraints",
        "label": "Restrições",
        "question": None,
        "passive_hint": None,
        "mode": "off",
    },
]


class BuildQualificationContextTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Com qualification_fields presente
    # ------------------------------------------------------------------

    def test_required_field_ends_in_must_collect_with_questions(self):
        ctx = _build_qualification_context({"qualification_fields": _SAMPLE_FIELDS})
        self.assertIn("must_collect_with_questions", ctx)
        keys = [f["key"] for f in ctx["must_collect_with_questions"]]
        self.assertEqual(keys, ["availability_window"])

    def test_optional_field_ends_in_nice_to_collect(self):
        ctx = _build_qualification_context({"qualification_fields": _SAMPLE_FIELDS})
        self.assertIn("nice_to_collect", ctx)
        keys = [f["key"] for f in ctx["nice_to_collect"]]
        self.assertEqual(keys, ["service_interest"])

    def test_off_field_is_ignored(self):
        ctx = _build_qualification_context({"qualification_fields": _SAMPLE_FIELDS})
        all_keys = (
            [f["key"] for f in ctx.get("must_collect_with_questions", [])]
            + [f["key"] for f in ctx.get("nice_to_collect", [])]
        )
        self.assertNotIn("constraints", all_keys)

    def test_must_collect_backward_compat_list_of_keys(self):
        """must_collect (lista de keys) deve ser derivado para backward compat."""
        ctx = _build_qualification_context({"qualification_fields": _SAMPLE_FIELDS})
        self.assertEqual(ctx.get("must_collect"), ["availability_window"])

    def test_question_and_passive_hint_are_preserved(self):
        ctx = _build_qualification_context({"qualification_fields": _SAMPLE_FIELDS})
        field = ctx["must_collect_with_questions"][0]
        self.assertEqual(field["key"], "availability_window")
        self.assertEqual(field["question"], "Qual horário funciona?")
        self.assertEqual(field["passive_hint"], "Inferir se mencionar horário")

    def test_multiple_required_fields(self):
        fields = [
            {"key": "availability_window", "label": "Disponibilidade", "mode": "required"},
            {"key": "service_interest",    "label": "Serviço",         "mode": "required"},
            {"key": "price_acceptance",    "label": "Preço",           "mode": "optional"},
        ]
        ctx = _build_qualification_context({"qualification_fields": fields})
        required_keys = [f["key"] for f in ctx["must_collect_with_questions"]]
        self.assertCountEqual(required_keys, ["availability_window", "service_interest"])
        optional_keys = [f["key"] for f in ctx["nice_to_collect"]]
        self.assertEqual(optional_keys, ["price_acceptance"])

    def test_all_off_returns_empty_context(self):
        fields = [{"key": "x", "label": "X", "mode": "off"}]
        ctx = _build_qualification_context({"qualification_fields": fields})
        self.assertNotIn("must_collect_with_questions", ctx)
        self.assertNotIn("nice_to_collect", ctx)
        self.assertNotIn("must_collect", ctx)

    def test_no_optional_fields_omits_nice_to_collect(self):
        fields = [{"key": "availability_window", "label": "Disponibilidade", "mode": "required"}]
        ctx = _build_qualification_context({"qualification_fields": fields})
        self.assertNotIn("nice_to_collect", ctx)

    def test_no_required_fields_omits_must_collect(self):
        fields = [{"key": "service_interest", "label": "Serviço", "mode": "optional"}]
        ctx = _build_qualification_context({"qualification_fields": fields})
        self.assertNotIn("must_collect", ctx)
        self.assertNotIn("must_collect_with_questions", ctx)

    def test_label_defaults_to_key_when_absent(self):
        fields = [{"key": "some_key", "mode": "required"}]
        ctx = _build_qualification_context({"qualification_fields": fields})
        field = ctx["must_collect_with_questions"][0]
        self.assertEqual(field["label"], "some_key")

    # ------------------------------------------------------------------
    # Fallback: sem qualification_fields
    # ------------------------------------------------------------------

    def test_fallback_to_qualification_required_fields(self):
        """Sem qualification_fields, deve usar a lista simples de keys."""
        ctx = _build_qualification_context({"qualification_required_fields": ["availability_window"]})
        self.assertEqual(ctx.get("must_collect"), ["availability_window"])
        self.assertNotIn("must_collect_with_questions", ctx)

    def test_fallback_empty_required_fields_returns_empty(self):
        ctx = _build_qualification_context({"qualification_required_fields": []})
        self.assertEqual(ctx, {})

    def test_no_fields_at_all_returns_empty(self):
        ctx = _build_qualification_context({})
        self.assertEqual(ctx, {})

    def test_none_profile_returns_empty(self):
        ctx = _build_qualification_context(None)
        self.assertEqual(ctx, {})

    def test_empty_qualification_fields_list_falls_back(self):
        """Lista vazia de qualification_fields → fallback para qualification_required_fields."""
        ctx = _build_qualification_context({
            "qualification_fields": [],
            "qualification_required_fields": ["service_interest"],
        })
        self.assertEqual(ctx.get("must_collect"), ["service_interest"])


class ApplyModeOverridesQualificationTests(unittest.TestCase):
    """Testa que apply_mode_overrides injeta corretamente o contexto enriquecido."""

    def _base_playbook(self):
        return {"template_key": "sdr_padrao", "default_next_action": "reply"}

    def test_agenda_mode_injects_must_collect_with_questions(self):
        profile = {"qualification_fields": _SAMPLE_FIELDS}
        result = apply_mode_overrides(self._base_playbook(), "agenda", ai_profile=profile)
        self.assertIn("must_collect_with_questions", result)
        self.assertIn("must_collect", result)

    def test_direto_mode_injects_qualification_context(self):
        profile = {"qualification_fields": _SAMPLE_FIELDS}
        result = apply_mode_overrides(self._base_playbook(), "direto", ai_profile=profile)
        self.assertIn("must_collect_with_questions", result)

    def test_consultivo_mode_injects_qualification_context(self):
        profile = {"qualification_fields": _SAMPLE_FIELDS}
        result = apply_mode_overrides(self._base_playbook(), "consultivo", ai_profile=profile)
        self.assertIn("must_collect_with_questions", result)

    def test_agenda_mode_without_qualification_fields_uses_required_fields(self):
        profile = {"qualification_required_fields": ["availability_window"]}
        result = apply_mode_overrides(self._base_playbook(), "agenda", ai_profile=profile)
        self.assertEqual(result.get("must_collect"), ["availability_window"])
        self.assertNotIn("must_collect_with_questions", result)

    def test_agenda_mode_empty_profile_no_must_collect(self):
        result = apply_mode_overrides(self._base_playbook(), "agenda", ai_profile={})
        self.assertNotIn("must_collect", result)

    def test_qualification_context_does_not_override_mode_settings(self):
        """Configurações de modo (max_chars, etc.) devem coexistir com qualification_context."""
        profile = {"qualification_fields": _SAMPLE_FIELDS}
        result = apply_mode_overrides(self._base_playbook(), "agenda", ai_profile=profile)
        self.assertEqual(result.get("max_chars"), 350)
        self.assertIn("must_collect_with_questions", result)

    def test_nice_to_collect_present_when_optional_fields_exist(self):
        profile = {"qualification_fields": _SAMPLE_FIELDS}
        result = apply_mode_overrides(self._base_playbook(), "agenda", ai_profile=profile)
        self.assertIn("nice_to_collect", result)
        keys = [f["key"] for f in result["nice_to_collect"]]
        self.assertEqual(keys, ["service_interest"])


if __name__ == "__main__":
    unittest.main()
