import os
import sqlite3
import sys
import unittest

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from automations.assistente_ia.processor import map_row_to_lead, find_existing_lead


def _row(data: dict) -> pd.Series:
    return pd.Series(data)


class MapRowToLeadTests(unittest.TestCase):
    def test_row_without_any_name_maps_to_none_instead_of_placeholder(self):
        lead = map_row_to_lead(_row({"telefone": "11999999999"}))
        self.assertIsNone(lead["companyName"])
        self.assertIsNone(lead["contactName"])

    def test_row_with_only_contact_keeps_company_none(self):
        lead = map_row_to_lead(_row({"contato": "Ana", "telefone": "11999999999"}))
        self.assertIsNone(lead["companyName"])
        self.assertEqual(lead["contactName"], "Ana")

    def test_row_with_company_is_unaffected(self):
        lead = map_row_to_lead(_row({"empresa": "ACME", "telefone": "11999999999"}))
        self.assertEqual(lead["companyName"], "ACME")

    def test_acquisition_channel_via_explicit_column_map(self):
        lead = map_row_to_lead(
            _row({"telefone": "11999999999", "origem marketing": "Facebook Ads"}),
            column_map={"acquisition_channel": "Origem Marketing"},
        )
        self.assertEqual(lead["acquisition_channel"], "Facebook Ads")

    def test_acquisition_channel_auto_detected_via_canal_column(self):
        lead = map_row_to_lead(_row({"telefone": "11999999999", "canal": "Indicação"}))
        self.assertEqual(lead["acquisition_channel"], "Indicação")

    def test_acquisition_channel_absent_stays_none(self):
        lead = map_row_to_lead(_row({"telefone": "11999999999"}))
        self.assertIsNone(lead["acquisition_channel"])


class FindExistingLeadTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                companyName TEXT,
                contactName TEXT,
                email TEXT,
                phone TEXT,
                CHECK (TRIM(COALESCE(companyName,'')) != '' OR TRIM(COALESCE(contactName,'')) != '')
            );
            """
        )
        self.conn.commit()
        self.user_id = 7

    def tearDown(self):
        self.conn.close()

    def test_none_company_does_not_crash_and_skips_company_match(self):
        self.conn.execute(
            "INSERT INTO leads (user_id, companyName, contactName, phone) VALUES (?, NULL, 'Ana', '11988887777')",
            (self.user_id,),
        )
        self.conn.commit()

        result = find_existing_lead(self.conn, None, None, None, user_id=self.user_id)
        self.assertIsNone(result)

    def test_matches_by_phone_even_when_company_is_none(self):
        cur = self.conn.execute(
            "INSERT INTO leads (user_id, companyName, contactName, phone) VALUES (?, NULL, 'Ana', '11988887777')",
            (self.user_id,),
        )
        self.conn.commit()
        lead_id = cur.lastrowid

        result = find_existing_lead(self.conn, None, None, "11988887777", user_id=self.user_id)
        self.assertEqual(result, lead_id)


if __name__ == "__main__":
    unittest.main()
