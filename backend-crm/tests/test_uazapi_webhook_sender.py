import unittest

import re


def _normalize_e164(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[\s\-()]+", "", str(value).strip())
    cleaned = re.sub(r"[^0-9+]+", "", cleaned)
    if cleaned.startswith("00") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+"):
        return cleaned
    digits = re.sub(r"[^0-9]+", "", cleaned)
    if not digits:
        return ""
    return f"+{digits}"


def resolve_sender_e164(payload: dict) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
    chat_phone = chat.get("phone")
    sender_phone = data.get("sender") or message.get("sender_pn")
    return _normalize_e164(chat_phone) or _normalize_e164(sender_phone)


class UazapiWebhookSenderTests(unittest.TestCase):
    def test_chat_phone_is_preferred(self):
        payload = {
            "chat": {"phone": "+55 47 9216-3692"},
            "message": {"sender_pn": "554792163692@s.whatsapp.net"},
        }
        self.assertEqual(resolve_sender_e164(payload), "+554792163692")

    def test_sender_pn_is_normalized(self):
        payload = {"message": {"sender_pn": "554792163692@s.whatsapp.net"}}
        self.assertEqual(resolve_sender_e164(payload), "+554792163692")

    def test_sender_lid_without_phone_returns_empty(self):
        payload = {"message": {"sender": "258831976235202@lid"}}
        self.assertEqual(resolve_sender_e164(payload), "")


if __name__ == "__main__":
    unittest.main()
