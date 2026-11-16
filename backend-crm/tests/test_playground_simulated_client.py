import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from pydantic import ValidationError

import routes.playground as playground_module
import services.playground_simulated_client as sim
from security_core import CurrentUser


def _user() -> CurrentUser:
    return CurrentUser(id=7, email="teste@example.com", token="tok")


def _body(**over):
    base = {
        "persona": "Quer marcar uma massagem no sábado; aceita a segunda proposta.",
        "agente": {"nome": "Lara", "negocio": "spa em Lisboa", "idioma": "português de Portugal"},
        "conversa": [{"de": "cliente", "texto": "Olá"}, {"de": "agente", "texto": "Olá! Em que posso ajudar?"}],
    }
    base.update(over)
    return playground_module.SimulatedClientRequest(**base)


class BuildPromptTest(unittest.TestCase):
    def test_prompt_has_persona_history_and_end_rule(self):
        p = sim.build_prompt("PERSONA X", "Lara", "spa", None, [("cliente", "Oi"), ("agente", "Olá!")])
        self.assertIn("PERSONA E OBJETIVO: PERSONA X", p)
        self.assertIn("CLIENTE: Oi\nLARA: Olá!", p)
        self.assertIn("em português", p)
        self.assertIn("responda exatamente FIM", p)
        self.assertTrue(p.endswith("CLIENTE:"))


class RouteTest(unittest.TestCase):
    def test_returns_message(self):
        with patch.object(sim, "next_message", return_value=("Pode ser sábado às 11h?", False)) as nm:
            r = playground_module.playground_simulated_client(_body(), current_user=_user())
        self.assertEqual(r.mensagem, "Pode ser sábado às 11h?")
        self.assertFalse(r.fim)
        self.assertIn("LARA: Olá! Em que posso ajudar?", nm.call_args.args[0])

    def test_end_flag(self):
        with patch.object(sim, "next_message", return_value=("FIM", True)):
            r = playground_module.playground_simulated_client(_body(), current_user=_user())
        self.assertTrue(r.fim)

    def test_without_key_is_503(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(HTTPException) as ctx:
                playground_module.playground_simulated_client(_body(), current_user=_user())
        self.assertEqual(ctx.exception.status_code, 503)

    def test_llm_error_is_502(self):
        with patch.object(sim, "next_message", side_effect=RuntimeError("boom")):
            with self.assertRaises(HTTPException) as ctx:
                playground_module.playground_simulated_client(_body(), current_user=_user())
        self.assertEqual(ctx.exception.status_code, 502)

    def test_limits(self):
        with self.assertRaises(ValidationError):
            _body(persona="x" * 4001)
        with self.assertRaises(ValidationError):
            _body(conversa=[{"de": "cliente", "texto": "a"}] * 41)
        with self.assertRaises(ValidationError):
            _body(conversa=[{"de": "outro", "texto": "a"}])


class NextMessageTest(unittest.TestCase):
    def test_fim_detection(self):
        class _Msg:  # resposta mínima no formato da OpenAI
            def __init__(self, c):
                self.choices = [type("C", (), {"message": type("M", (), {"content": c})()})()]

        class _Client:
            def __init__(self, api_key):
                self.chat = type("Ch", (), {"completions": type("Co", (), {"create": staticmethod(lambda **k: _Msg('"FIM"'))})()})()

        import types
        fake = types.ModuleType("openai")
        fake.OpenAI = _Client
        with patch.dict(sys.modules, {"openai": fake}), patch.dict(os.environ, {"OPENAI_API_KEY": "k"}):
            texto, fim = sim.next_message("p")
        self.assertEqual(texto, "FIM")
        self.assertTrue(fim)


if __name__ == "__main__":
    unittest.main()
