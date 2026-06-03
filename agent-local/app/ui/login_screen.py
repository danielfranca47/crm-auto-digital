"""Ecrã de acesso — entrada por email (sem senha)."""
from __future__ import annotations

import threading
import customtkinter as ctk


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, on_existing_user, on_new_user):
        """
        on_existing_user(email) — utilizador registado, ir para OTP
        on_new_user(email)      — email desconhecido, ir para registo
        """
        super().__init__(master, fg_color="transparent")
        self._on_existing = on_existing_user
        self._on_new = on_new_user
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=20)
        card.pack(expand=True, padx=60, pady=60, fill="both")

        ctk.CTkLabel(card, text="🔍", font=ctk.CTkFont(size=48)).pack(pady=(40, 6))
        ctk.CTkLabel(
            card, text="Gerador de Leads",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="Digital Pro",
            font=ctk.CTkFont(size=12), text_color="#6B7280",
        ).pack(pady=(2, 32))

        ctk.CTkLabel(card, text="O seu email", anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
        self._email = ctk.CTkEntry(card, placeholder_text="seu@email.com", height=42, corner_radius=8)
        self._email.pack(padx=44, pady=(4, 6), fill="x")
        self._email.bind("<Return>", lambda _: self._do_continue())

        self._error = ctk.CTkLabel(
            card, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12), wraplength=340,
        )
        self._error.pack(padx=44, pady=(6, 2))

        self._btn = ctk.CTkButton(
            card, text="Continuar →", height=44, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._do_continue,
        )
        self._btn.pack(padx=44, pady=(8, 40), fill="x")

    def _do_continue(self):
        from app.auth import request_access, AuthError

        email = self._email.get().strip().lower()
        if not email or "@" not in email:
            self._error.configure(text="Introduza um email válido.")
            return

        self._set_loading(True)

        def _worker():
            try:
                result = request_access(email)
                if result.get("status") == "existing_user":
                    self.after(0, lambda: self._on_existing(email))
                else:
                    self.after(0, lambda: self._on_new(email))
            except AuthError as e:
                self.after(0, lambda msg=str(e): self._error.configure(text=msg))
            finally:
                self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_loading(self, loading: bool):
        if loading:
            self._btn.configure(state="disabled", text="Verificando...")
        else:
            self._btn.configure(state="normal", text="Continuar →")
