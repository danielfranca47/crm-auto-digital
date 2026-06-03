"""Ecrã principal — pesquisa de leads (Fase 2 implementa a pesquisa; Fase 1 é estrutura base)."""
from __future__ import annotations

import customtkinter as ctk
from app.session import is_subscriber


class MainScreen(ctk.CTkFrame):
    def __init__(self, master, session_data: dict, on_logout=None):
        super().__init__(master, fg_color="transparent")
        self._session = session_data
        self._on_logout = on_logout
        self._build()

    def _build(self):
        subscriber = is_subscriber(self._session)
        name = self._session.get("name", "Utilizador")

        # Header
        header = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=0, height=60)
        header.pack(fill="x", padx=0, pady=(0, 2))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🔍  Gerador de Leads",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=20, pady=15)

        badge_color = "#10B981" if subscriber else "#6B7280"
        badge_text = "✓ Assinante" if subscriber else "Gratuito"
        ctk.CTkLabel(
            header, text=badge_text,
            fg_color=badge_color, corner_radius=12,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            padx=10, pady=4,
        ).pack(side="right", padx=(0, 10), pady=15)

        ctk.CTkLabel(
            header, text=name,
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
        ).pack(side="right", padx=4, pady=15)

        # Body
        body = ctk.CTkFrame(self, fg_color="#12121F", corner_radius=0)
        body.pack(fill="both", expand=True)

        # Placeholder (Fase 2 substitui este bloco)
        ctk.CTkLabel(
            body,
            text="🔍",
            font=ctk.CTkFont(size=56),
        ).pack(pady=(60, 12))

        ctk.CTkLabel(
            body,
            text="Pesquisa de Leads em Construção",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            body,
            text="A funcionalidade de pesquisa estará disponível em breve.\nEsta é a Fase 1 — autenticação e estrutura base.",
            font=ctk.CTkFont(size=13),
            text_color="#6B7280",
            justify="center",
        ).pack(pady=(8, 40))

        # Non-subscriber upgrade prompt
        if not subscriber:
            promo = ctk.CTkFrame(body, fg_color="#1E1E2E", corner_radius=12)
            promo.pack(padx=60, fill="x")

            ctk.CTkLabel(
                promo,
                text="⚡  Torne-se Assinante",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#FBBF24",
            ).pack(pady=(16, 4))
            ctk.CTkLabel(
                promo,
                text="Assinantes usam a nossa chave Google Maps sem configuração\ne têm acesso a pesquisas ilimitadas.",
                font=ctk.CTkFont(size=12),
                text_color="#9CA3AF",
                justify="center",
            ).pack(pady=(0, 12))

        # Footer logout
        ctk.CTkButton(
            body,
            text="Sair da conta",
            fg_color="transparent",
            hover_color="#2A2A3E",
            text_color="#6B7280",
            font=ctk.CTkFont(size=11),
            command=self._logout,
        ).pack(pady=(20, 16))

    def _logout(self):
        from app.session import clear_session
        clear_session()
        if self._on_logout:
            self._on_logout()
