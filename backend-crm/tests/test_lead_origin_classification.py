import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai_orchestrator.orchestrator import _classify_lead_origin


class TestClassifyLeadOrigin(unittest.TestCase):
    def _assert_inbound(self, origin_raw):
        is_outbound, lead_origin, lead_origin_label = _classify_lead_origin(origin_raw)
        self.assertFalse(is_outbound, f"esperava inbound para origin={origin_raw!r}")
        self.assertEqual(lead_origin, "inbound")
        self.assertEqual(lead_origin_label, "INBOUND (lead veio te procurar)")

    def _assert_outbound(self, origin_raw):
        is_outbound, lead_origin, lead_origin_label = _classify_lead_origin(origin_raw)
        self.assertTrue(is_outbound, f"esperava outbound para origin={origin_raw!r}")
        self.assertEqual(lead_origin, "outbound")
        self.assertEqual(lead_origin_label, "OUTBOUND (lead foi abordado — não te conhecia)")

    def test_whatsapp_inbound_is_inbound(self):
        # Bug real corrigido: valor gravado por find_or_create_lead_by_phone()
        # (services/whatsapp_inbound/guardrail.py) para todo lead novo via WhatsApp.
        self._assert_inbound("whatsapp_inbound")

    def test_formulario_website_is_inbound(self):
        # Bug real corrigido: valor gravado por routes/public.py para leads do
        # formulário de contato do site.
        self._assert_inbound("Formulário Website")

    def test_manual_is_inbound(self):
        self._assert_inbound("Manual")
        self._assert_inbound("manual")

    def test_planilha_is_inbound(self):
        self._assert_inbound("Planilha")
        self._assert_inbound("planilha")

    def test_empty_or_none_is_inbound(self):
        self._assert_inbound("")
        self._assert_inbound(None)

    def test_unknown_marketing_channel_defaults_to_inbound(self):
        # à prova de futuro: qualquer canal de aquisição livre nunca antes visto
        # continua caindo em inbound por default seguro.
        self._assert_inbound("Facebook Ads")
        self._assert_inbound("Indicação")
        self._assert_inbound("LinkedIn")

    def test_outbound_literal_is_outbound(self):
        self._assert_outbound("outbound")

    def test_outbound_is_case_and_whitespace_insensitive(self):
        self._assert_outbound("OUTBOUND")
        self._assert_outbound("  outbound  ")
        self._assert_outbound("Outbound")


if __name__ == "__main__":
    unittest.main()
