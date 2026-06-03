"""Onboarding wizard — placeholder para Fase 3.

Na Fase 1 apenas marca onboarding_done=True e avança para o ecrã principal.
A Fase 3 implementará o wizard educativo completo diferenciado por perfil.
"""
from __future__ import annotations

import customtkinter as ctk
from app.session import is_subscriber, save_session


class OnboardingScreen(ctk.CTkFrame):
    def __init__(self, master, session_data: dict, on_done):
        super().__init__(master, fg_color="transparent")
        self._session = session_data
        self._on_done = on_done
        self._build()

    def _build(self):
        subscriber = is_subscriber(self._session)
        name = self._session.get("name", "").split()[0] or "seja bem-vindo"

        card = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=20)
        card.pack(expand=True, padx=60, pady=60, fill="both")

        ctk.CTkLabel(card, text="👋", font=ctk.CTkFont(size=52)).pack(pady=(48, 8))
        ctk.CTkLabel(
            card, text=f"Olá, {name}!",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack()

        if subscriber:
            msg = "Conta verificada como Assinante.\nO onboarding completo estará disponível em breve."
            badge = ("✓ Assinante", "#10B981")
        else:
            msg = "Conta criada com sucesso!\nO onboarding completo estará disponível em breve."
            badge = ("Plano Gratuito", "#6B7280")

        ctk.CTkLabel(
            card, text=badge[0],
            fg_color=badge[1], corner_radius=12,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white", padx=12, pady=5,
        ).pack(pady=(12, 16))

        ctk.CTkLabel(
            card, text=msg,
            font=ctk.CTkFont(size=13),
            text_color="#9CA3AF",
            justify="center",
        ).pack(pady=(0, 40))

        ctk.CTkButton(
            card, text="Continuar →", height=46, corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._finish,
        ).pack(padx=60, pady=(0, 48), fill="x")

    def _finish(self):
        self._session["onboarding_done"] = True
        save_session(self._session)
        self._on_done()
