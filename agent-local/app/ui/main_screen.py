"""Ecrã principal — pesquisa de leads via Google Maps."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import customtkinter as ctk
from app.session import is_subscriber


class MainScreen(ctk.CTkFrame):
    def __init__(self, master, session_data: dict, on_logout=None):
        super().__init__(master, fg_color="transparent")
        self._session = session_data
        self._on_logout = on_logout
        self._results: List[Dict[str, Any]] = []
        self._searching = False
        self._build()

    def _build(self):
        subscriber = is_subscriber(self._session)
        name = self._session.get("name", "Utilizador")
        email = self._session.get("email", "")
        display_name = name if name and name != email else email.split("@")[0]

        # ── Header ─────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=0, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🔍  Gerador de Leads",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left", padx=16, pady=12)

        # Botão configurações (chave API)
        ctk.CTkButton(
            header, text="⚙", width=36, height=30,
            fg_color="#2A2A3E", hover_color="#3A3A5E",
            font=ctk.CTkFont(size=16),
            command=self._open_settings,
        ).pack(side="right", padx=(4, 12), pady=12)

        badge_color = "#10B981" if subscriber else "#6B7280"
        badge_text = "✓ Assinante" if subscriber else "Gratuito"
        ctk.CTkLabel(
            header, text=badge_text,
            fg_color=badge_color, corner_radius=10,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white", padx=8, pady=3,
        ).pack(side="right", padx=(0, 6), pady=12)

        ctk.CTkLabel(
            header, text=display_name,
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack(side="right", padx=4, pady=12)

        # ── Corpo ─────────────────────────────────────────────────────────
        body = ctk.CTkScrollableFrame(self, fg_color="#12121F", corner_radius=0)
        body.pack(fill="both", expand=True)

        # Formulário de pesquisa
        form = ctk.CTkFrame(body, fg_color="#1E1E2E", corner_radius=12)
        form.pack(padx=20, pady=16, fill="x")

        ctk.CTkLabel(form, text="Nova Pesquisa", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=16, pady=(14, 8)
        )

        fields_row = ctk.CTkFrame(form, fg_color="transparent")
        fields_row.pack(padx=16, pady=(0, 8), fill="x")
        fields_row.columnconfigure(0, weight=2)
        fields_row.columnconfigure(1, weight=2)
        fields_row.columnconfigure(2, weight=1)

        ctk.CTkLabel(fields_row, text="Nicho / Tipo de negócio", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 4)
        )
        ctk.CTkLabel(fields_row, text="Cidade / Região", font=ctk.CTkFont(size=12)).grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=(0, 4)
        )
        ctk.CTkLabel(fields_row, text="Limite", font=ctk.CTkFont(size=12)).grid(
            row=0, column=2, sticky="w", pady=(0, 4)
        )

        self._niche = ctk.CTkEntry(fields_row, placeholder_text="ex: dentistas", height=38, corner_radius=8)
        self._niche.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self._city = ctk.CTkEntry(fields_row, placeholder_text="ex: São Paulo, SP", height=38, corner_radius=8)
        self._city.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        self._limit_var = ctk.StringVar(value="20")
        self._limit = ctk.CTkOptionMenu(
            fields_row,
            values=["10", "20", "40", "60"],
            variable=self._limit_var,
            height=38, corner_radius=8,
        )
        self._limit.grid(row=1, column=2, sticky="ew")

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(padx=16, pady=(8, 14), fill="x")

        self._search_btn = ctk.CTkButton(
            btn_row, text="🔍  Pesquisar", height=40, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_search,
        )
        self._search_btn.pack(side="left")

        self._mode_label = ctk.CTkLabel(
            btn_row,
            text=self._mode_description(),
            font=ctk.CTkFont(size=11),
            text_color="#6B7280",
        )
        self._mode_label.pack(side="left", padx=12)

        # Barra de progresso (oculta inicialmente)
        self._progress_frame = ctk.CTkFrame(body, fg_color="#1E1E2E", corner_radius=12)
        self._progress_bar = ctk.CTkProgressBar(self._progress_frame, height=8, corner_radius=4)
        self._progress_bar.set(0)
        self._progress_bar.pack(padx=16, pady=(12, 4), fill="x")
        self._progress_label = ctk.CTkLabel(
            self._progress_frame, text="",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        )
        self._progress_label.pack(padx=16, pady=(0, 12))

        # Mensagem de erro
        self._error_label = ctk.CTkLabel(
            body, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12), wraplength=540,
        )

        # Área de resultados
        self._results_frame = ctk.CTkFrame(body, fg_color="#1E1E2E", corner_radius=12)

        # Footer (logout)
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(pady=(8, 12))
        ctk.CTkButton(
            footer, text="Sair da conta",
            fg_color="transparent", hover_color="#1E1E2E",
            text_color="#4B5563", font=ctk.CTkFont(size=11),
            command=self._logout,
        ).pack()

    # ── Pesquisa ──────────────────────────────────────────────────────────────

    def _start_search(self):
        if self._searching:
            return

        niche = self._niche.get().strip()
        city = self._city.get().strip()
        if not niche or not city:
            self._show_error("Preencha o nicho e a cidade.")
            return

        query = f"{niche} em {city}"
        limit = int(self._limit_var.get())

        self._searching = True
        self._search_btn.configure(state="disabled", text="Pesquisando...")
        self._error_label.configure(text="")
        self._error_label.pack_forget()
        self._results_frame.pack_forget()
        self._show_progress(True)

        def _worker():
            from app.maps_client import search_leads, SearchError
            try:
                results = search_leads(
                    query=query,
                    limit=limit,
                    session=self._session,
                    progress_callback=self._on_progress,
                )
                self.after(0, lambda r=results: self._show_results(r))
            except SearchError as e:
                self.after(0, lambda msg=str(e): self._show_error(msg))
            finally:
                self.after(0, self._reset_search_btn)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_progress(self, current: int, total: int, message: str):
        def _update():
            pct = (current / total) if total > 0 else 0
            self._progress_bar.set(min(pct, 1.0))
            self._progress_label.configure(text=message)
        self.after(0, _update)

    def _show_progress(self, visible: bool):
        if visible:
            self._progress_frame.pack(padx=20, pady=(0, 8), fill="x")
            self._progress_bar.set(0)
            self._progress_label.configure(text="Iniciando...")
        else:
            self._progress_frame.pack_forget()

    def _reset_search_btn(self):
        try:
            self._searching = False
            self._search_btn.configure(state="normal", text="🔍  Pesquisar")
            self._show_progress(False)
        except Exception:
            pass

    # ── Resultados ────────────────────────────────────────────────────────────

    def _show_results(self, results: List[Dict]):
        self._results = results

        # Limpar frame de resultados
        for w in self._results_frame.winfo_children():
            w.destroy()

        # Header da tabela
        count_text = f"{len(results)} lead{'s' if len(results) != 1 else ''} encontrado{'s' if len(results) != 1 else ''}"
        header = ctk.CTkFrame(self._results_frame, fg_color="transparent")
        header.pack(padx=16, pady=(12, 8), fill="x")

        ctk.CTkLabel(header, text=count_text, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        if results:
            ctk.CTkButton(
                header, text="📥  Exportar Excel",
                height=34, corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self._export_excel,
            ).pack(side="right")

        if not results:
            ctk.CTkLabel(
                self._results_frame,
                text="Nenhum resultado encontrado. Tente um nicho ou cidade diferente.",
                text_color="#6B7280", font=ctk.CTkFont(size=13),
            ).pack(pady=20)
        else:
            subscriber = is_subscriber(self._session)
            # Assinante: 6 colunas (4 dados + 📱 + 💾). Gratuito: 5 (4 dados + 📱)
            total_cols = 6 if subscriber else 5

            # Tabela de resultados
            table_frame = ctk.CTkScrollableFrame(
                self._results_frame, fg_color="transparent", height=300
            )
            table_frame.pack(padx=16, pady=(0, 12), fill="x")

            table_frame.columnconfigure([0, 1, 2, 3], weight=1)
            for i in range(4, total_cols):
                table_frame.columnconfigure(i, weight=0)

            # Cabeçalho
            for c_idx, col in enumerate(["Nome", "Telefone", "Website", "Avaliação"]):
                ctk.CTkLabel(
                    table_frame, text=col,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#9CA3AF",
                ).grid(row=0, column=c_idx, sticky="w", padx=(0, 8), pady=(0, 6))

            # Linhas
            for r_idx, item in enumerate(results[:60]):
                row_color = "#1A1A2E" if r_idx % 2 == 0 else "#16162A"
                row_frame = ctk.CTkFrame(table_frame, fg_color=row_color, corner_radius=6, height=36)
                row_frame.grid(row=r_idx + 1, column=0, columnspan=total_cols, sticky="ew", pady=1)
                row_frame.grid_columnconfigure([0, 1, 2, 3], weight=1)
                for i in range(4, total_cols):
                    row_frame.grid_columnconfigure(i, weight=0)
                row_frame.grid_propagate(False)

                values = [
                    item.get("name", "") or "",
                    item.get("phone", "") or "",
                    item.get("website", "") or "",
                    f"⭐ {item.get('rating', '')}" if item.get("rating") else "",
                ]
                for c_idx, val in enumerate(values):
                    ctk.CTkLabel(
                        row_frame,
                        text=str(val)[:45] + ("…" if len(str(val)) > 45 else ""),
                        font=ctk.CTkFont(size=11),
                        anchor="w",
                    ).grid(row=0, column=c_idx, sticky="w", padx=(8, 4), pady=4)

                # Botão de prospecção WhatsApp
                ctk.CTkButton(
                    row_frame,
                    text="📱",
                    width=36, height=26,
                    fg_color="#1D4ED8", hover_color="#1E40AF",
                    font=ctk.CTkFont(size=13),
                    corner_radius=6,
                    command=lambda it=item: self._open_prospect_dialog(it),
                ).grid(row=0, column=4, padx=(2, 4), pady=5)

                # Botão "Guardar no CRM" — só visível para assinantes
                if subscriber:
                    ctk.CTkButton(
                        row_frame,
                        text="💾",
                        width=36, height=26,
                        fg_color="#065F46", hover_color="#047857",
                        font=ctk.CTkFont(size=13),
                        corner_radius=6,
                        command=lambda it=item: self._save_lead_to_crm(it),
                    ).grid(row=0, column=5, padx=(0, 8), pady=5)

        self._results_frame.pack(padx=20, pady=(0, 8), fill="x")

    def _open_prospect_dialog(self, lead_data: dict) -> None:
        from app.ui.prospect_dialog import ProspectDialog
        ProspectDialog(self, lead_data=lead_data, session=self._session)

    def _save_lead_to_crm(self, lead_data: dict) -> None:
        """Guarda lead no CRM sem prospectar (assinante only). Não duplica se phone já existe."""
        import threading

        def _do() -> None:
            try:
                from app.crm_client import create_lead
                result = create_lead(
                    self._session,
                    name=lead_data.get("name", "Lead"),
                    phone=lead_data.get("phone", ""),
                    website=lead_data.get("website", ""),
                    address=lead_data.get("address", ""),
                )
                lead_id = result.get("id") or result.get("lead_id")
                already = result.get("status") == "exists"
                label = "já existia no CRM" if already else "guardado no CRM"
                self.after(0, lambda: self._crm_save_popup(f"✓ Lead {label} (#{lead_id})", ok=True))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._crm_save_popup(f"✗ Erro: {e}", ok=False))

        threading.Thread(target=_do, daemon=True).start()

    def _crm_save_popup(self, msg: str, ok: bool) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("Guardar no CRM")
        popup.geometry("340x130")
        popup.resizable(False, False)
        popup.grab_set()
        color = "#10B981" if ok else "#EF4444"
        ctk.CTkLabel(
            popup, text=msg,
            text_color=color, font=ctk.CTkFont(size=13), wraplength=300,
        ).pack(pady=(28, 12))
        ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack()

    def _show_error(self, msg: str):
        self._error_label.configure(text=f"⚠  {msg}")
        self._error_label.pack(padx=20, pady=(0, 8))

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_excel(self):
        if not self._results:
            return

        niche = self._niche.get().strip()
        city = self._city.get().strip()
        query = f"{niche} em {city}" if niche and city else "pesquisa"

        from tkinter import filedialog
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"leads_{ts}.xlsx"

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
            initialfile=default_name,
            title="Guardar leads como...",
        )
        if not path:
            return

        try:
            from app.export import export_to_excel
            export_to_excel(self._results, query, Path(path))
            self._show_export_success(path)
        except Exception as exc:
            self._show_error(f"Erro ao exportar: {exc}")

    def _show_export_success(self, path: str):
        popup = ctk.CTkToplevel(self)
        popup.title("Exportado!")
        popup.geometry("360x160")
        popup.resizable(False, False)
        popup.grab_set()

        ctk.CTkLabel(popup, text="✅  Ficheiro guardado!", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(24, 8))
        ctk.CTkLabel(
            popup, text=Path(path).name,
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack()
        ctk.CTkButton(popup, text="OK", width=100, command=popup.destroy).pack(pady=16)

    # ── Configurações ─────────────────────────────────────────────────────────

    def _open_settings(self):
        from app.ui.settings_screen import SettingsScreen
        SettingsScreen(self, session_data=self._session, on_save=self._on_settings_saved)

    def _on_settings_saved(self, updated_session: dict):
        self._session.update(updated_session)
        from app.session import save_session
        save_session(self._session)
        self._mode_label.configure(text=self._mode_description())

    # ── Logout ────────────────────────────────────────────────────────────────

    def _logout(self):
        from app.session import clear_session
        clear_session()
        if self._on_logout:
            self._on_logout()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mode_description(self) -> str:
        if is_subscriber(self._session):
            return "Modo: Assinante — chave API incluída"
        key = self._session.get("google_maps_api_key")
        if key:
            return "Modo: Chave API própria configurada"
        return "Modo: Gratuito (Selenium) — configure a sua chave API em ⚙"
