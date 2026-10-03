import os
import tempfile
import unittest

from sqlalchemy import create_engine, text

from app.db import Base, ensure_professional_availability_backfill
import app.db as core_db

FACTORY_SCHEDULE = (
    '{"mon":"09:00-18:00","tue":"09:00-18:00","wed":"09:00-18:00",'
    '"thu":"09:00-18:00","fri":"09:00-18:00","sat":"","sun":""}'
)


class ProfessionalAvailabilityBackfillTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self._old_engine = core_db.engine
        core_db.engine = self.engine

    def tearDown(self):
        core_db.engine = self._old_engine
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _insert_profile(self, profile_id, *, schedule, mode="24h", professional=None):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO ai_profiles (
                        id, user_id, template_key, name, brand_name, tone_of_voice, niche,
                        target_audience, offer_description, goals,
                        availability_schedule, availability_mode, professional_availability
                    ) VALUES (
                        :id, :id, 'hybrid_scheduler', 'Agent', 'Brand', 'profissional', 'Massagem',
                        'Adultos', 'Oferta', 'Objetivos',
                        :schedule, :mode, :professional
                    )
                    """
                ),
                {"id": profile_id, "schedule": schedule, "mode": mode, "professional": professional},
            )

    def _fetch(self, profile_id):
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT availability_schedule, availability_mode, professional_availability "
                    "FROM ai_profiles WHERE id = :id"
                ),
                {"id": profile_id},
            ).fetchone()
        return tuple(row)

    def test_weekday_grid_is_kept_and_copied_as_readable_text(self):
        self._insert_profile(1, schedule=FACTORY_SCHEDULE, mode="custom")

        ensure_professional_availability_backfill()

        self.assertEqual(self._fetch(1), (FACTORY_SCHEDULE, "custom", "Seg a Sex: 09:00–18:00"))

    def test_weekday_grid_with_gaps_and_different_hours(self):
        self._insert_profile(
            1,
            schedule='{"mon":"09:00-12:00","tue":"09:00-12:00","wed":"","thu":"14:00-18:00","sat":"10:00-13:00"}',
        )

        ensure_professional_availability_backfill()

        self.assertEqual(
            self._fetch(1)[2],
            "Seg a Ter: 09:00–12:00\nQui: 14:00–18:00\nSáb: 10:00–13:00",
        )

    def test_free_text_moves_to_new_field_and_custom_mode_becomes_24h(self):
        self._insert_profile(1, schedule="Seg-Sex: 14h, 16h, 18h\nSábado: 10h, 12h", mode="custom")

        ensure_professional_availability_backfill()

        self.assertEqual(self._fetch(1), (None, "24h", "Seg-Sex: 14h, 16h, 18h\nSábado: 10h, 12h"))

    def test_free_text_keeps_non_custom_mode(self):
        self._insert_profile(1, schedule="Ter e Qui: 14h, 16h", mode="business_hours")

        ensure_professional_availability_backfill()

        self.assertEqual(self._fetch(1), (None, "business_hours", "Ter e Qui: 14h, 16h"))

    def test_profiles_already_separated_or_empty_are_untouched(self):
        self._insert_profile(1, schedule=FACTORY_SCHEDULE, professional="Ter e Qui: 14h")
        self._insert_profile(2, schedule=FACTORY_SCHEDULE, professional="")
        self._insert_profile(3, schedule=None)
        self._insert_profile(4, schedule="   ")

        ensure_professional_availability_backfill()

        self.assertEqual(self._fetch(1), (FACTORY_SCHEDULE, "24h", "Ter e Qui: 14h"))
        self.assertEqual(self._fetch(2), (FACTORY_SCHEDULE, "24h", ""))
        self.assertEqual(self._fetch(3), (None, "24h", None))
        self.assertEqual(self._fetch(4), ("   ", "24h", None))

    def test_running_twice_changes_nothing(self):
        self._insert_profile(1, schedule=FACTORY_SCHEDULE)
        self._insert_profile(2, schedule="Seg-Sex: 14h, 16h", mode="custom")

        ensure_professional_availability_backfill()
        first = (self._fetch(1), self._fetch(2))
        ensure_professional_availability_backfill()

        self.assertEqual((self._fetch(1), self._fetch(2)), first)


if __name__ == "__main__":
    unittest.main()
