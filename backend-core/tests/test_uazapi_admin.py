import unittest

from app.services import uazapi_admin


class UazapiAdminExtractTests(unittest.TestCase):
    def test_extract_instance_details_prefers_name_over_dict_id(self):
        payload = {
            "id": {"id": "nested", "token": "secret"},
            "name": "instance-slug",
            "token": "tok123",
        }
        instance_id, instance_token, _phone = uazapi_admin.extract_instance_details(
            payload, fallback_instance_id="fallback"
        )
        self.assertEqual(instance_id, "instance-slug")
        self.assertEqual(instance_token, "tok123")

    def test_extract_connection_meta_normalizes_status_dict(self):
        payload = {
            "status": {"connected": False, "loggedIn": False},
        }
        status_value, _qr, _pair = uazapi_admin.extract_connection_meta(payload)
        self.assertEqual(status_value, "disconnected")


if __name__ == "__main__":
    unittest.main()
