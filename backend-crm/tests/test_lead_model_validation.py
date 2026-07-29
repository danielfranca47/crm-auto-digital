import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from pydantic import ValidationError

from models import Lead


class LeadModelValidationTests(unittest.TestCase):
    def test_both_names_missing_raises(self):
        with self.assertRaises(ValidationError):
            Lead(companyName=None, contactName=None, category="to-prospect")

    def test_both_names_blank_raises(self):
        with self.assertRaises(ValidationError):
            Lead(companyName="   ", contactName="   ", category="to-prospect")

    def test_only_company_name_is_valid(self):
        lead = Lead(companyName="ACME", contactName=None, category="to-prospect")
        self.assertEqual(lead.companyName, "ACME")
        self.assertIsNone(lead.contactName)

    def test_only_contact_name_is_valid(self):
        lead = Lead(companyName=None, contactName="Ana", category="to-prospect")
        self.assertIsNone(lead.companyName)
        self.assertEqual(lead.contactName, "Ana")

    def test_both_names_present_is_valid(self):
        lead = Lead(companyName="ACME", contactName="Ana", category="to-prospect")
        self.assertEqual(lead.companyName, "ACME")
        self.assertEqual(lead.contactName, "Ana")


if __name__ == "__main__":
    unittest.main()
