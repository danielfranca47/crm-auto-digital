"""Ecrã de informações de negócio — usado pelo gerador de copy local (modo gratuito)."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from app.session import save_session

_FIELDS = [
    ("niche", "Nicho de mercado", "Ex.: clínica odontológica, loja de roupa, consultoria financeira"),
    ("offer_description", "Produto/Serviço (oferta)", "Ex.: implantes dentários, planos de assinatura mensal"),
    ("target_audience", "Público-alvo", "Ex.: pequenas empresas da zona, clínicas privadas"),
    ("brand_name", "Nome da empresa/marca", "Ex.: Sorriso & Cia"),
]


class BusinessProfileScreen(ctk.CTkToplevel):
    """Modal simples para o utilizador gratuito preencher o essencial do seu negócio.

    Não substitui o AI Profile pago — guarda apenas os campos necessários para o
    gerador local de copy montar um prompt ciente do nicho/oferta do utilizador.
    """

    def __init__(self, master, session_data: dict, on_save: Optional[Callable] = None):
        super().__init__(master)
        self._session = session_data
        self._on_save = on_save
        self._entries: dict[str, ctk.CTkEntry] = {}

        self.title("Informações de Negócio")
        self.geometry("480x520")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="📋  Informações de Negócio",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(24, 4))
        ctk.CTkLabel(
            self,
            text="Usadas pelo Assistente IA (modo gratuito) para gerar copys\n"
                 "alinhadas com o teu nicho — em vez de mensagens genéricas.",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF", justify="center",
        ).pack(pady=(0, 16))

        profile = self._session.get("local_business_profile") or {}

        form = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=12)
        form.pack(padx=24, fill="both", expand=True)

        for key, label, placeholder in _FIELDS:
            ctk.CTkLabel(form, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(14, 4))
            entry = ctk.CTkEntry(form, placeholder_text=placeholder, height=38, corner_radius=8)
            existing = profile.get(key) or ""
            if existing:
                entry.insert(0, existing)
            entry.pack(padx=16, fill="x")
            self._entries[key] = entry

        ctk.CTkLabel(
            form,
            text="🔒 Guardadas localmente — só tu tens acesso",
            font=ctk.CTkFont(size=10), text_color="#4B5563",
        ).pack(anchor="w", padx=16, pady=(8, 14))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=20, fill="x", padx=24)

        ctk.CTkButton(
            btn_frame, text="Cancelar", width=100,
            fg_color="#2A2A3E", hover_color="#3A3A5E",
            command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Guardar", width=120, height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save,
        ).pack(side="right")

    def _save(self) -> None:
        profile = {key: self._entries[key].get().strip() for key, _, _ in _FIELDS}
        self._session["local_business_profile"] = profile
        save_session(self._session)
        if self._on_save:
            self._on_save(profile)
        self.destroy()
