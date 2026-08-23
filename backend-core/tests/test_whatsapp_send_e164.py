import unittest

from app.api.whatsapp_send import _is_valid_e164_digits, _sanitize_number


class E164ValidationTests(unittest.TestCase):
    def test_valid_br_number_passes(self):
        self.assertTrue(_is_valid_e164_digits(_sanitize_number("+55 (11) 99999-9999")))

    def test_valid_us_number_passes(self):
        self.assertTrue(_is_valid_e164_digits(_sanitize_number("+1 415-555-2671")))

    def test_empty_string_is_invalid(self):
        self.assertFalse(_is_valid_e164_digits(_sanitize_number("")))

    def test_none_is_invalid(self):
        self.assertFalse(_is_valid_e164_digits(_sanitize_number(None)))

    def test_letters_are_invalid(self):
        self.assertFalse(_is_valid_e164_digits(_sanitize_number("abc123def")))

    def test_too_short_is_invalid(self):
        self.assertFalse(_is_valid_e164_digits(_sanitize_number("+551199")))

    def test_too_long_is_invalid(self):
        self.assertFalse(_is_valid_e164_digits(_sanitize_number("+" + "1" * 16)))

    def test_leading_zero_is_invalid(self):
        self.assertFalse(_is_valid_e164_digits(_sanitize_number("+0511999999999")))

    def test_boundary_8_digits_is_valid(self):
        self.assertTrue(_is_valid_e164_digits(_sanitize_number("+15551234")))

    def test_boundary_15_digits_is_valid(self):
        self.assertTrue(_is_valid_e164_digits(_sanitize_number("+" + "1" * 15)))


if __name__ == "__main__":
    unittest.main()
