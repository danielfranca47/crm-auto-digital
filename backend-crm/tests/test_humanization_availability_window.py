import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.humanization import apply_availability_window, next_available_at

# 03/10/2026 é sábado; 05/10/2026 é segunda. timezone UTC para o horário local = UTC.
SATURDAY_NOON = datetime(2026, 10, 3, 12, 0)
MONDAY_EARLY = datetime(2026, 10, 5, 7, 0)
MONDAY_NOON = datetime(2026, 10, 5, 12, 0)
MONDAY_EVENING = datetime(2026, 10, 5, 20, 0)

WEEKDAY_GRID = '{"mon":"10:00-16:00","tue":"10:00-16:00","wed":"","thu":"","fri":"","sat":"","sun":""}'
MONDAY_ONLY_GRID = '{"mon":"10:00-16:00","tue":"","wed":"","thu":"","fri":"","sat":"","sun":""}'


def _profile(mode, schedule=None):
    return {"availability_mode": mode, "availability_schedule": schedule, "timezone": "UTC"}


class AvailabilityWindowTests(unittest.TestCase):
    def test_24h_never_delays(self):
        self.assertIsNone(next_available_at(_profile("24h", WEEKDAY_GRID), SATURDAY_NOON))

    def test_business_hours_inside_window_does_not_delay(self):
        self.assertIsNone(next_available_at(_profile("business_hours"), MONDAY_NOON))

    def test_business_hours_on_weekend_waits_for_monday_opening(self):
        self.assertEqual(
            next_available_at(_profile("business_hours"), SATURDAY_NOON),
            datetime(2026, 10, 5, 9, 0),
        )

    def test_custom_grid_inside_window_does_not_delay(self):
        self.assertIsNone(next_available_at(_profile("custom", WEEKDAY_GRID), MONDAY_NOON))

    def test_custom_grid_after_closing_waits_for_next_open_day(self):
        self.assertEqual(
            next_available_at(_profile("custom", WEEKDAY_GRID), MONDAY_EVENING),
            datetime(2026, 10, 6, 10, 0),
        )

    def test_before_opening_waits_for_same_day_opening(self):
        self.assertEqual(
            next_available_at(_profile("custom", WEEKDAY_GRID), MONDAY_EARLY),
            datetime(2026, 10, 5, 10, 0),
        )
        self.assertEqual(
            next_available_at(_profile("business_hours"), MONDAY_EARLY),
            datetime(2026, 10, 5, 9, 0),
        )

    def test_single_day_grid_after_closing_waits_for_next_week(self):
        self.assertEqual(
            next_available_at(_profile("custom", MONDAY_ONLY_GRID), MONDAY_EVENING),
            datetime(2026, 10, 12, 10, 0),
        )

    def test_apply_window_keeps_instant_when_open(self):
        self.assertEqual(apply_availability_window(_profile("custom", WEEKDAY_GRID), MONDAY_NOON), MONDAY_NOON)
        self.assertEqual(apply_availability_window(_profile("24h", WEEKDAY_GRID), SATURDAY_NOON), SATURDAY_NOON)

    def test_apply_window_moves_to_opening_when_closed(self):
        self.assertEqual(
            apply_availability_window(_profile("custom", WEEKDAY_GRID), MONDAY_EARLY),
            datetime(2026, 10, 5, 10, 0),
        )

    def test_custom_without_readable_grid_does_not_delay(self):
        # A grade é só a da Janela de horário (JSON por dia da semana). Texto livre de
        # horários de atendimento vive em professional_availability e nunca é uma janela.
        self.assertIsNone(next_available_at(_profile("custom", "Seg-Sex: 14h, 16h, 18h"), SATURDAY_NOON))
        self.assertIsNone(next_available_at(_profile("custom", None), SATURDAY_NOON))


if __name__ == "__main__":
    unittest.main()
