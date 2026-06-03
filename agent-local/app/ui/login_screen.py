"""Ecrã de login — email + senha."""
from __future__ import annotations

import threading
import customtkinter as ctk


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, on_login, on_register):
        super().__init__(master, fg_color="transparent")
        self._on_login = on_login
        self._on_register = on_register
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=20)
        card.pack(expand=True, padx=60, pady=40, fill="both")

        ctk.CTkLabel(card, text="🔍", font=ctk.CTkFont(size=48)).pack(pady=(40, 6))
        ctk.CTkLabel(
            card, text="Gerador de Leads",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="AutoDigital Pro",
            font=ctk.CTkFont(size=12),
            text_color="#6B7280",
        ).pack(pady=(2, 32))

        ctk.CTkLabel(card, text="Email", anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
        self._email = ctk.CTkEntry(card, placeholder_text="seu@email.com", height=42, corner_radius=8)
        self._email.pack(padx=44, pady=(4, 14), fill="x")

        ctk.CTkLabel(card, text="Senha", anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
        self._password = ctk.CTkEntry(card, placeholder_text="••••••••", show="•", height=42, corner_radius=8)
        self._password.pack(padx=44, pady=(4, 6), fill="x")
        self._password.bind("<Return>", lambda _: self._do_login())

        self._error = ctk.CTkLabel(
            card, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12), wraplength=340,
        )
        self._error.pack(padx=44, pady=(6, 2))

        self._btn = ctk.CTkButton(
            card, text="Entrar", height=44, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._do_login,
        )
        self._btn.pack(padx=44, pady=(8, 8), fill="x")

        ctk.CTkButton(
            card,
            text="Não tem conta? Criar conta grátis",
            fg_color="transparent",
            hover_color="#2A2A3E",
            text_color="#60A5FA",
            font=ctk.CTkFont(size=13),
            command=self._on_register,
        ).pack(pady=(4, 40))

    def _do_login(self):
        from app.auth import login, AuthError

        email = self._email.get().strip()
        password = self._password.get()
        if not email or not password:
            self._error.configure(text="Preencha email e senha.")
            return

        self._set_loading(True)

        def _worker():
            try:
                result = login(email, password)
                self.after(0, lambda: self._on_login(result))
            except AuthError as e:
                self.after(0, lambda msg=str(e): self._error.configure(text=msg))
            finally:
                self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_loading(self, loading: bool):
        if loading:
            self._btn.configure(state="disabled", text="Entrando...")
        else:
            self._btn.configure(state="normal", text="Entrar")
