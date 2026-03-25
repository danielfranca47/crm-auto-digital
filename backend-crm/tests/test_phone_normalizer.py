import importlib.util
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NORMALIZER_PATH = os.path.join(PROJECT_ROOT, "services", "phone_normalizer.py")
spec = importlib.util.spec_from_file_location("phone_normalizer_module", NORMALIZER_PATH)
phone_normalizer = importlib.util.module_from_spec(spec)
sys.modules["phone_normalizer_module"] = phone_normalizer
spec.loader.exec_module(phone_normalizer)

PhoneNormalizationError = phone_normalizer.PhoneNormalizationError
normalize_to_e164 = phone_normalizer.normalize_to_e164


class PhoneNormalizerTest(unittest.TestCase):
    def test_keeps_plus_number(self):
        self.assertEqual(normalize_to_e164("+55 (11) 99999-9999"), "+5511999999999")

    def test_converts_00_prefix(self):
        self.assertEqual(normalize_to_e164("00351912345678"), "+351912345678")

    def test_local_number_requires_country_code(self):
        with self.assertRaises(PhoneNormalizationError):
            normalize_to_e164("11999999999")

    def test_local_number_with_country_code(self):
        self.assertEqual(normalize_to_e164("4155552671", "US"), "+14155552671")

    def test_unknown_country_code(self):
        with self.assertRaises(PhoneNormalizationError):
            normalize_to_e164("123456789", "ZZ")

    def test_br_legacy_mobile_adds_nine_digit(self):
        self.assertEqual(normalize_to_e164("4792163692", "BR"), "+5547992163692")

    def test_br_mobile_already_nine_digit_stays_same(self):
        self.assertEqual(normalize_to_e164("47992163692", "BR"), "+5547992163692")

    def test_br_fixed_line_keeps_eight_digit_subscriber(self):
        self.assertEqual(normalize_to_e164("1123456789", "BR"), "+551123456789")

    def test_inbound_style_plus55_legacy_mobile_is_canonicalized(self):
        self.assertEqual(normalize_to_e164("+554792163692"), "+5547992163692")


if __name__ == "__main__":
    unittest.main()
