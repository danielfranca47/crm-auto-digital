import asyncio
import unittest
import unittest.mock as mock
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.api.auth import (
    MAX_OTP_SENDS,
    RegisterPasswordlessRequest,
    RequestAccessRequest,
    VerifyOtpRequest,
    _generate_and_store_otp,
    register_passwordless,
    request_access,
    verify_otp_endpoint,
)
from app.db import (
    Base,
    ensure_auth_otp_lockouts_send_columns,
    ensure_auth_otp_lockouts_table,
    ensure_auth_otps_table,
)
import app.db as core_db
import app.services.email_service as email_service
from fastapi import HTTPException


class OtpSpamSendProtectionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)

        old_engine = core_db.engine
        core_db.engine = engine
        try:
            ensure_auth_otps_table()
            ensure_auth_otp_lockouts_table()
            ensure_auth_otp_lockouts_send_columns()
        finally:
            core_db.engine = old_engine

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        self.user = models.User(email="otp-spam@example.com", password_hash="secret")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.sent_emails = []
        patcher = mock.patch.object(
            email_service, "send_email", lambda **kwargs: self.sent_emails.append(kwargs)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.db.close()

    def _request_access(self):
        return asyncio.run(request_access(RequestAccessRequest(email=self.user.email), db=self.db))

    def test_allows_up_to_max_sends_in_window(self):
        for _ in range(MAX_OTP_SENDS):
            result = self._request_access()
            self.assertEqual(result["status"], "existing_user")
        self.assertEqual(len(self.sent_emails), MAX_OTP_SENDS)

    def test_blocks_send_beyond_limit_and_does_not_send_email(self):
        for _ in range(MAX_OTP_SENDS):
            self._request_access()

        with self.assertRaises(HTTPException) as ctx:
            self._request_access()
        self.assertEqual(ctx.exception.status_code, 429)
        # nenhum email extra foi enviado na chamada bloqueada
        self.assertEqual(len(self.sent_emails), MAX_OTP_SENDS)

        # bloqueio também afeta verify-otp e register-passwordless (mesmo locked_until)
        with self.assertRaises(HTTPException) as ctx2:
            asyncio.run(
                verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code="000000"), db=self.db)
            )
        self.assertEqual(ctx2.exception.status_code, 429)

    def test_window_expiring_allows_sends_again(self):
        for _ in range(MAX_OTP_SENDS):
            self._request_access()
        with self.assertRaises(HTTPException):
            self._request_access()

        # simula a janela de envio (e o lockout) já tendo expirado
        self.db.execute(
            text(
                "UPDATE auth_otp_lockouts SET "
                "otp_send_window_started_at = :past, locked_until = :past "
                "WHERE email = :email"
            ),
            {"past": datetime.utcnow() - timedelta(minutes=60), "email": self.user.email},
        )
        self.db.commit()

        result = self._request_access()
        self.assertEqual(result["status"], "existing_user")

    def test_register_passwordless_existing_user_is_also_rate_limited(self):
        for _ in range(MAX_OTP_SENDS):
            result = asyncio.run(
                register_passwordless(
                    RegisterPasswordlessRequest(name="Teste", email=self.user.email), db=self.db
                )
            )
            self.assertEqual(result["status"], "ok")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                register_passwordless(
                    RegisterPasswordlessRequest(name="Teste", email=self.user.email), db=self.db
                )
            )
        self.assertEqual(ctx.exception.status_code, 429)

    def test_successful_login_clears_send_counter(self):
        code = None
        for _ in range(MAX_OTP_SENDS):
            self._request_access()
        code = _generate_and_store_otp(self.user.email, self.db)

        result = asyncio.run(
            verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code=code), db=self.db)
        )
        self.assertIn("access_token", result)

        row = self.db.execute(
            text("SELECT otp_send_count FROM auth_otp_lockouts WHERE email = :email"),
            {"email": self.user.email},
        ).fetchone()
        self.assertIsNone(row)

        # janela reiniciada — volta a permitir MAX_OTP_SENDS envios
        for _ in range(MAX_OTP_SENDS):
            result = self._request_access()
            self.assertEqual(result["status"], "existing_user")


if __name__ == "__main__":
    unittest.main()
