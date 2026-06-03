"""Ecrã de verificação OTP — código de 6 dígitos enviado por email."""
from __future__ import annotations

import threading
import customtkinter as ctk


class OtpScreen(ctk.CTkFrame):
    def __init__(self, master, email: str, on_verified, on_back):
        """
        email       — email para onde foi enviado o código
        on_verified(session_data) — OTP válido, navegar para main/onboarding
        on_back()                 — voltar ao ecrã anterior
        """
        super().__init__(master, fg_color="transparent")
        self._email = email
        self._on_verified = on_verified
        self._on_back = on_back
        self._resend_countdown = 0
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=20)
        card.pack(expand=True, padx=60, pady=60, fill="both")

        ctk.CTkLabel(card, text="📧", font=ctk.CTkFont(size=48)).pack(pady=(40, 6))
        ctk.CTkLabel(
            card, text="Verifique o seu email",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card,
            text=f"Enviámos um código de 6 dígitos para\n{self._email}",
            font=ctk.CTkFont(size=13), text_color="#9CA3AF",
            justify="center",
        ).pack(pady=(6, 28))

        ctk.CTkLabel(card, text="Código de acesso", anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
        self._code = ctk.CTkEntry(
            card,
            placeholder_text="123456",
            height=52, corner_radius=8,
            font=ctk.CTkFont(size=24, weight="bold"),
            justify="center",
        )
        self._code.pack(padx=44, pady=(4, 6), fill="x")
        self._code.bind("<Return>", lambda _: self._do_verify())

        self._error = ctk.CTkLabel(
            card, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12), wraplength=340,
        )
        self._error.pack(padx=44, pady=(6, 2))

        self._btn = ctk.CTkButton(
            card, text="Confirmar acesso", height=44, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._do_verify,
        )
        self._btn.pack(padx=44, pady=(8, 12), fill="x")

        self._resend_btn = ctk.CTkButton(
            card,
            text="Reenviar código",
            fg_color="transparent", hover_color="#2A2A3E",
            text_color="#60A5FA", font=ctk.CTkFont(size=12),
            command=self._resend,
        )
        self._resend_btn.pack(pady=(0, 4))

        ctk.CTkButton(
            card,
            text="← Voltar",
            fg_color="transparent", hover_color="#2A2A3E",
            text_color="#6B7280", font=ctk.CTkFont(size=11),
            command=self._on_back,
        ).pack(pady=(0, 32))

        # Auto-foco no campo de código
        self.after(200, self._code.focus_set)

    def _do_verify(self):
        from app.auth import verify_otp, AuthError

        code = self._code.get().strip().replace(" ", "")
        if len(code) != 6 or not code.isdigit():
            self._error.configure(text="O código deve ter 6 dígitos.")
            return

        self._set_loading(True)

        def _worker():
            try:
                session = verify_otp(self._email, code)
                self.after(0, lambda: self._on_verified(session))
            except AuthError as e:
                self.after(0, lambda msg=str(e): self._error.configure(text=msg))
                self.after(0, lambda: self._code.delete(0, "end"))
            finally:
                self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _resend(self):
        if self._resend_countdown > 0:
            return

        from app.auth import request_access, AuthError

        self._resend_btn.configure(state="disabled")
        self._error.configure(text="")

        def _worker():
            try:
                request_access(self._email)
                self.after(0, lambda: self._error.configure(
                    text="Novo código enviado!", text_color="#10B981"
                ))
                self._resend_countdown = 60
                self.after(0, self._tick_countdown)
            except AuthError as e:
                self.after(0, lambda msg=str(e): self._error.configure(
                    text=msg, text_color="#EF4444"
                ))
                self.after(0, lambda: self._resend_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _tick_countdown(self):
        if self._resend_countdown > 0:
            self._resend_btn.configure(
                text=f"Reenviar ({self._resend_countdown}s)",
                state="disabled",
            )
            self._resend_countdown -= 1
            self.after(1000, self._tick_countdown)
        else:
            self._resend_btn.configure(text="Reenviar código", state="normal")

    def _set_loading(self, loading: bool):
        if loading:
            self._btn.configure(state="disabled", text="Verificando...")
        else:
            self._btn.configure(state="normal", text="Confirmar acesso")
