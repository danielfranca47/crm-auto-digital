"""Ecrã de registo — nome, email, senha, WhatsApp."""
from __future__ import annotations

import threading
import customtkinter as ctk


class RegisterScreen(ctk.CTkFrame):
    def __init__(self, master, on_register, on_login):
        super().__init__(master, fg_color="transparent")
        self._on_register = on_register
        self._on_login = on_login
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=20)
        card.pack(expand=True, padx=60, pady=30, fill="both")

        ctk.CTkLabel(card, text="🚀", font=ctk.CTkFont(size=40)).pack(pady=(32, 6))
        ctk.CTkLabel(
            card, text="Criar conta grátis",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="AutoDigital Pro",
            font=ctk.CTkFont(size=12),
            text_color="#6B7280",
        ).pack(pady=(2, 24))

        fields = [
            ("Nome completo", "João Silva", False, "_name"),
            ("Email", "seu@email.com", False, "_email"),
            ("Senha", "mínimo 6 caracteres", True, "_password"),
            ("WhatsApp (com DDD)", "11999999999", False, "_whatsapp"),
        ]

        for label, placeholder, is_password, attr in fields:
            ctk.CTkLabel(card, text=label, anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
            entry = ctk.CTkEntry(
                card,
                placeholder_text=placeholder,
                show="•" if is_password else "",
                height=40,
                corner_radius=8,
            )
            entry.pack(padx=44, pady=(4, 12), fill="x")
            setattr(self, attr, entry)

        self._whatsapp.bind("<Return>", lambda _: self._do_register())

        self._error = ctk.CTkLabel(
            card, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12), wraplength=340,
        )
        self._error.pack(padx=44, pady=(2, 2))

        self._btn = ctk.CTkButton(
            card, text="Criar conta", height=44, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._do_register,
        )
        self._btn.pack(padx=44, pady=(8, 8), fill="x")

        ctk.CTkButton(
            card,
            text="Já tem conta? Entrar",
            fg_color="transparent",
            hover_color="#2A2A3E",
            text_color="#60A5FA",
            font=ctk.CTkFont(size=13),
            command=self._on_login,
        ).pack(pady=(4, 32))

    def _do_register(self):
        from app.auth import register, AuthError

        name = self._name.get().strip()
        email = self._email.get().strip()
        password = self._password.get()
        whatsapp = self._whatsapp.get().strip()

        if not name or not email or not password:
            self._error.configure(text="Preencha nome, email e senha.")
            return
        if len(password) < 6:
            self._error.configure(text="A senha deve ter pelo menos 6 caracteres.")
            return

        self._set_loading(True)

        def _worker():
            try:
                result = register(name=name, email=email, password=password, whatsapp=whatsapp)
                self.after(0, lambda: self._on_register(result))
            except AuthError as e:
                self.after(0, lambda msg=str(e): self._error.configure(text=msg))
            finally:
                self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_loading(self, loading: bool):
        if loading:
            self._btn.configure(state="disabled", text="Criando conta...")
        else:
            self._btn.configure(state="normal", text="Criar conta")
