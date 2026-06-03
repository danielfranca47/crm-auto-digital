"""Ecrã de configurações — chave Google Maps API para não-assinantes."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk
from app.session import is_subscriber


class SettingsScreen(ctk.CTkToplevel):
    def __init__(self, master, session_data: dict, on_save: Optional[Callable] = None):
        super().__init__(master)
        self._session = session_data
        self._on_save = on_save
        self.title("Configurações")
        self.geometry("480x420")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        subscriber = is_subscriber(self._session)

        ctk.CTkLabel(self, text="⚙  Configurações", font=ctk.CTkFont(size=18, weight="bold")).pack(
            pady=(24, 4)
        )
        ctk.CTkLabel(
            self, text="Gerador de Leads — AutoDigital",
            font=ctk.CTkFont(size=12), text_color="#6B7280",
        ).pack(pady=(0, 20))

        # Secção: conta
        account_frame = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=12)
        account_frame.pack(padx=24, fill="x")

        ctk.CTkLabel(account_frame, text="Conta", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(12, 4))

        email = self._session.get("email", "—")
        ctk.CTkLabel(account_frame, text=f"Email: {email}", font=ctk.CTkFont(size=13)).pack(
            anchor="w", padx=16, pady=(0, 4)
        )

        badge_text = "✓ Assinante" if subscriber else "Gratuito"
        badge_color = "#10B981" if subscriber else "#6B7280"
        ctk.CTkLabel(
            account_frame, text=badge_text,
            fg_color=badge_color, corner_radius=10,
            font=ctk.CTkFont(size=11), text_color="white",
            padx=8, pady=3,
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # Secção: API key (apenas para não-assinantes)
        if not subscriber:
            api_frame = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=12)
            api_frame.pack(padx=24, pady=(12, 0), fill="x")

            ctk.CTkLabel(api_frame, text="Chave Google Maps API",
                         font=ctk.CTkFont(size=12, weight="bold"), text_color="#9CA3AF").pack(
                anchor="w", padx=16, pady=(12, 4)
            )
            ctk.CTkLabel(
                api_frame,
                text="Configure a sua chave para pesquisas fiáveis.\nSem chave: usa modo Selenium (mais lento).",
                font=ctk.CTkFont(size=11), text_color="#6B7280", justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 8))

            self._api_key_entry = ctk.CTkEntry(
                api_frame,
                placeholder_text="AIza...",
                height=38, corner_radius=8,
                show="",
            )
            existing_key = self._session.get("google_maps_api_key", "")
            if existing_key:
                self._api_key_entry.insert(0, existing_key)
            self._api_key_entry.pack(padx=16, pady=(0, 8), fill="x")

            ctk.CTkLabel(
                api_frame,
                text="Obter chave: console.cloud.google.com → Places API",
                font=ctk.CTkFont(size=10), text_color="#4B5563",
            ).pack(anchor="w", padx=16, pady=(0, 12))
        else:
            ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=12).pack(padx=24, pady=(12, 0), fill="x")
            ctk.CTkLabel(
                self,
                text="✓  Chave Google Maps incluída na assinatura",
                font=ctk.CTkFont(size=12), text_color="#10B981",
            ).pack(pady=(8, 0))

        # Botões
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=24)

        ctk.CTkButton(
            btn_frame, text="Cancelar", width=100,
            fg_color="#2A2A3E", hover_color="#3A3A5E",
            command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Guardar", width=100,
            command=self._save,
        ).pack(side="right")

    def _save(self):
        updated = dict(self._session)
        if not is_subscriber(self._session) and hasattr(self, "_api_key_entry"):
            key = self._api_key_entry.get().strip()
            updated["google_maps_api_key"] = key or None

        if self._on_save:
            self._on_save(updated)
        self.destroy()
