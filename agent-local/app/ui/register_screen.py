"""Ecrã de registo — nome, whatsapp e setor (sem senha)."""
from __future__ import annotations

import threading
import customtkinter as ctk

_SECTORS = [
    "Saúde e bem-estar",
    "Alimentação e restauração",
    "Beleza e estética",
    "Educação e formação",
    "Tecnologia e serviços digitais",
    "Construção e imobiliário",
    "Comércio e retalho",
    "Jurídico e contabilidade",
    "Outro",
]


class RegisterScreen(ctk.CTkFrame):
    def __init__(self, master, email: str, on_registered, on_back):
        """
        email       — pré-preenchido da tela anterior (imutável)
        on_registered(email) — conta criada, ir para OTP
        on_back()            — voltar ao ecrã de email
        """
        super().__init__(master, fg_color="transparent")
        self._email = email
        self._on_registered = on_registered
        self._on_back = on_back
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=20)
        card.pack(expand=True, padx=60, pady=28, fill="both")

        ctk.CTkLabel(card, text="🚀", font=ctk.CTkFont(size=40)).pack(pady=(28, 6))
        ctk.CTkLabel(
            card, text="Criar conta grátis",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text=self._email,
            font=ctk.CTkFont(size=12), text_color="#60A5FA",
        ).pack(pady=(4, 20))

        fields = [
            ("Nome completo", "João Silva", "_name"),
            ("WhatsApp (com DDD)", "11999999999", "_whatsapp"),
        ]
        for label, placeholder, attr in fields:
            ctk.CTkLabel(card, text=label, anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
            entry = ctk.CTkEntry(card, placeholder_text=placeholder, height=40, corner_radius=8)
            entry.pack(padx=44, pady=(4, 12), fill="x")
            setattr(self, attr, entry)

        ctk.CTkLabel(card, text="Setor de atuação", anchor="w", font=ctk.CTkFont(size=13)).pack(padx=44, fill="x")
        self._sector = ctk.CTkOptionMenu(
            card, values=_SECTORS, height=40, corner_radius=8,
        )
        self._sector.pack(padx=44, pady=(4, 6), fill="x")

        self._error = ctk.CTkLabel(
            card, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12), wraplength=340,
        )
        self._error.pack(padx=44, pady=(6, 2))

        self._btn = ctk.CTkButton(
            card, text="Criar conta e receber código →",
            height=44, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._do_register,
        )
        self._btn.pack(padx=44, pady=(8, 8), fill="x")

        ctk.CTkButton(
            card,
            text="← Voltar",
            fg_color="transparent", hover_color="#2A2A3E",
            text_color="#6B7280", font=ctk.CTkFont(size=12),
            command=self._on_back,
        ).pack(pady=(4, 24))

    def _do_register(self):
        from app.auth import register_passwordless, AuthError

        name = self._name.get().strip()
        whatsapp = self._whatsapp.get().strip()
        sector = self._sector.get()

        if not name:
            self._error.configure(text="Preencha o seu nome.")
            return

        self._set_loading(True)

        def _worker():
            try:
                register_passwordless(
                    name=name,
                    email=self._email,
                    whatsapp=whatsapp or None,
                    sector=sector,
                )
                self.after(0, lambda: self._on_registered(self._email))
            except AuthError as e:
                self.after(0, lambda msg=str(e): self._error.configure(text=msg))
            finally:
                self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_loading(self, loading: bool):
        if loading:
            self._btn.configure(state="disabled", text="Criando conta...")
        else:
            self._btn.configure(state="normal", text="Criar conta e receber código →")
