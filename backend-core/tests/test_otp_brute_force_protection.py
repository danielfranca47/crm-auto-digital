import asyncio
import unittest
import unittest.mock as mock
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.api.auth import (
    MAX_OTP_ATTEMPTS,
    RequestAccessRequest,
    VerifyOtpRequest,
    _generate_and_store_otp,
    request_access,
    verify_otp_endpoint,
)
from app.db import Base, ensure_auth_otp_lockouts_table, ensure_auth_otps_table
import app.db as core_db
import app.services.email_service as email_service
from fastapi import HTTPException


class OtpBruteForceProtectionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)

        old_engine = core_db.engine
        core_db.engine = engine
        try:
            ensure_auth_otps_table()
            ensure_auth_otp_lockouts_table()
        finally:
            core_db.engine = old_engine

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        self.user = models.User(email="otp-brute-force@example.com", password_hash="secret")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        # Não enviar email real de OTP durante os testes
        patcher = mock.patch.object(email_service, "send_email", lambda **kwargs: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.db.close()

    def _fail_verify(self, times: int, code: str = "000000") -> None:
        for _ in range(times):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(
                    verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code=code), db=self.db)
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_correct_code_succeeds(self):
        code = _generate_and_store_otp(self.user.email, self.db)
        result = asyncio.run(
            verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code=code), db=self.db)
        )
        self.assertIn("access_token", result)

    def test_wrong_code_below_limit_does_not_lock(self):
        _generate_and_store_otp(self.user.email, self.db)
        self._fail_verify(MAX_OTP_ATTEMPTS - 1)

        # ainda não bloqueado — request-access deveria funcionar normalmente
        result = asyncio.run(request_access(RequestAccessRequest(email=self.user.email), db=self.db))
        self.assertEqual(result["status"], "existing_user")

    def test_wrong_code_reaching_limit_locks_account(self):
        _generate_and_store_otp(self.user.email, self.db)
        self._fail_verify(MAX_OTP_ATTEMPTS)

        # bloqueado agora — mesmo o código certo (se soubesse) seria rejeitado com 429
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code="000000"), db=self.db)
            )
        self.assertEqual(ctx.exception.status_code, 429)

        # request-access também bloqueado — não deve gerar um novo código
        with self.assertRaises(HTTPException) as ctx2:
            asyncio.run(request_access(RequestAccessRequest(email=self.user.email), db=self.db))
        self.assertEqual(ctx2.exception.status_code, 429)

    def test_regenerating_otp_does_not_reset_failed_attempts(self):
        """Regressão: o contador de falhas vivia na linha do auth_otps antes desta
        correção. Pedir um OTP novo criava uma linha com o contador zerado, e um
        atacante conseguia errar sempre (MAX_OTP_ATTEMPTS - 1) vezes e pedir um
        código novo antes de bater no limite — nunca disparando o lockout. O
        contador agora vive em auth_otp_lockouts (por email), que sobrevive a
        pedidos de OTP novos."""
        _generate_and_store_otp(self.user.email, self.db)
        self._fail_verify(MAX_OTP_ATTEMPTS - 1)

        # pede um código novo antes de bater no limite — não deve resetar a contagem
        code = asyncio.run(request_access(RequestAccessRequest(email=self.user.email), db=self.db))
        self.assertEqual(code["status"], "existing_user")

        # a próxima tentativa errada é a que fecha o ciclo MAX_OTP_ATTEMPTS -> bloqueia
        self._fail_verify(1)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(request_access(RequestAccessRequest(email=self.user.email), db=self.db))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_lockout_expires_after_window(self):
        _generate_and_store_otp(self.user.email, self.db)
        self._fail_verify(MAX_OTP_ATTEMPTS)

        # simula o bloqueio já ter expirado
        self.db.execute(
            text("UPDATE auth_otp_lockouts SET locked_until = :past WHERE email = :email"),
            {"past": datetime.utcnow() - timedelta(minutes=1), "email": self.user.email},
        )
        self.db.commit()

        code = _generate_and_store_otp(self.user.email, self.db)
        result = asyncio.run(
            verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code=code), db=self.db)
        )
        self.assertIn("access_token", result)

    def test_successful_login_clears_failure_history(self):
        _generate_and_store_otp(self.user.email, self.db)
        self._fail_verify(MAX_OTP_ATTEMPTS - 2)

        code = _generate_and_store_otp(self.user.email, self.db)
        result = asyncio.run(
            verify_otp_endpoint(VerifyOtpRequest(email=self.user.email, code=code), db=self.db)
        )
        self.assertIn("access_token", result)

        # login bem-sucedido limpou o histórico — próximo erro não herda as falhas anteriores
        row = self.db.execute(
            text("SELECT failed_attempts FROM auth_otp_lockouts WHERE email = :email"),
            {"email": self.user.email},
        ).fetchone()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
