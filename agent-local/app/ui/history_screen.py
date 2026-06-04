"""Histórico de prospecções — log local para todos, CRM para assinantes."""
from __future__ import annotations

import csv
import threading
from pathlib import Path
from tkinter import filedialog
from typing import Any, Dict, List

import customtkinter as ctk

from app.session import is_subscriber, get_prospect_log


_ACTION_LABELS = {
    "manual_outbound": "Enviado (manual)",
    "sent":            "Enviado",
    "failed":          "Falhou",
    "queued":          "Enfileirado",
    "copied":          "Copy copiado",
}


class HistoryScreen(ctk.CTkToplevel):
    """Janela modal com o histórico de envios de prospecção."""

    def __init__(self, master, session: dict):
        super().__init__(master)
        self.title("📋 Histórico de Prospecções")
        self.geometry("620x480")
        self.resizable(True, True)
        self.grab_set()
        self.focus()

        self._session = session
        self._subscriber = is_subscriber(session)
        self._entries: List[Dict[str, Any]] = []

        self._build()
        self._load()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=0, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text="Histórico de Prospecções",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=16)

        ctk.CTkButton(
            hdr, text="📥 Exportar CSV",
            height=30, corner_radius=6,
            font=ctk.CTkFont(size=11),
            command=self._export_csv,
        ).pack(side="right", padx=12, pady=9)

        ctk.CTkButton(
            hdr, text="↺ Actualizar",
            height=30, corner_radius=6,
            fg_color="#2A2A3E", hover_color="#3A3A5E",
            font=ctk.CTkFont(size=11),
            command=self._load,
        ).pack(side="right", padx=(0, 4), pady=9)

        # Fonte de dados
        src_text = "Fonte: CRM (assinante)" if self._subscriber else "Fonte: log local"
        ctk.CTkLabel(
            self, text=src_text,
            font=ctk.CTkFont(size=10), text_color="#6B7280",
        ).pack(anchor="w", padx=16, pady=(6, 0))

        # Loading label
        self._loading_label = ctk.CTkLabel(
            self, text="A carregar…",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        )
        self._loading_label.pack(pady=12)

        # Tabela
        self._table_frame = ctk.CTkScrollableFrame(self, fg_color="#12121F", corner_radius=8)
        # (será populada após load)

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=8)
        ctk.CTkButton(
            footer, text="Fechar",
            width=100, command=self.destroy,
        ).pack()

    # ── Carregamento ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._loading_label.configure(text="A carregar…")
        self._table_frame.pack_forget()
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        if self._subscriber:
            try:
                from app.crm_client import get_prospect_history
                entries = get_prospect_history(self._session, limit=200)
            except Exception:
                entries = get_prospect_log(200)
        else:
            entries = get_prospect_log(200)

        self.after(0, lambda e=entries: self._render(e))

    def _render(self, entries: List[Dict]) -> None:
        self._entries = entries
        self._loading_label.pack_forget()

        for w in self._table_frame.winfo_children():
            w.destroy()

        if not entries:
            ctk.CTkLabel(
                self._table_frame,
                text="Sem registos de prospecção.",
                font=ctk.CTkFont(size=13), text_color="#6B7280",
            ).pack(pady=20)
            self._table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))
            return

        # Cabeçalho
        cols = ["Data/Hora", "Nome", "Telefone", "Estado", "Notas"]
        hdr = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(4, 4))
        hdr.columnconfigure([0, 1, 2, 3, 4], weight=1)
        for i, col in enumerate(cols):
            ctk.CTkLabel(
                hdr, text=col,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#9CA3AF", anchor="w",
            ).grid(row=0, column=i, sticky="w", padx=4)

        # Linhas
        for idx, entry in enumerate(entries):
            # Normaliza chaves CRM vs local
            ts = (entry.get("created_at") or entry.get("ts") or "")[:16].replace("T", " ")
            name = entry.get("lead_name") or entry.get("name") or "—"
            phone = entry.get("phone") or "—"
            action = entry.get("action") or entry.get("status") or "—"
            notes = entry.get("notes") or entry.get("reason") or ""

            action_label = _ACTION_LABELS.get(action, action)
            color = "#EF4444" if "fail" in action.lower() else "#10B981" if "sent" in action.lower() or action == "manual_outbound" else "#9CA3AF"

            row_color = "#1A1A2E" if idx % 2 == 0 else "#16162A"
            row = ctk.CTkFrame(self._table_frame, fg_color=row_color, corner_radius=4)
            row.pack(fill="x", padx=8, pady=1)
            row.columnconfigure([0, 1, 2, 3, 4], weight=1)

            for c_idx, val in enumerate([ts, name[:25], phone, action_label, notes[:30]]):
                text_color = color if c_idx == 3 else "#D1D5DB"
                ctk.CTkLabel(
                    row, text=str(val),
                    font=ctk.CTkFont(size=10), text_color=text_color, anchor="w",
                ).grid(row=0, column=c_idx, sticky="w", padx=(8 if c_idx == 0 else 4, 4), pady=5)

        self._table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    # ── Export CSV ────────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if not self._entries:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="historico_prospeccao.csv",
            title="Guardar histórico como…",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Data/Hora", "Nome", "Telefone", "Estado", "Notas"])
                for e in self._entries:
                    ts = (e.get("created_at") or e.get("ts") or "")[:16].replace("T", " ")
                    writer.writerow([
                        ts,
                        e.get("lead_name") or e.get("name") or "",
                        e.get("phone") or "",
                        e.get("action") or e.get("status") or "",
                        e.get("notes") or e.get("reason") or "",
                    ])
            popup = ctk.CTkToplevel(self)
            popup.title("Exportado!")
            popup.geometry("320x120")
            popup.grab_set()
            ctk.CTkLabel(popup, text=f"✅  {Path(path).name}",
                         font=ctk.CTkFont(size=13)).pack(pady=(24, 8))
            ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack()
        except Exception as exc:
            ctk.CTkMessagebox(title="Erro", message=str(exc))
