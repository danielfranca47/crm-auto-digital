import unittest

from app.services import whatsapp_connections


class ConnectionStatusNormalizationTests(unittest.TestCase):
    def test_connected_maps_to_active(self):
        self.assertEqual(
            whatsapp_connections.normalize_connection_status_for_crm("connected"),
            "active",
        )

    def test_disconnected_maps_to_inactive(self):
        self.assertEqual(
            whatsapp_connections.normalize_connection_status_for_crm("disconnected"),
            "inactive",
        )


if __name__ == "__main__":
    unittest.main()
