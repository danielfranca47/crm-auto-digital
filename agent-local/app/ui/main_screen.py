"""Ecrã principal — sidebar de navegação + painéis de conteúdo."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import customtkinter as ctk
from app.session import is_subscriber

# ── Constantes de layout ───────────────────────────────────────────────────

_SIDEBAR_W = 150
_BG = "#12121F"
_SIDEBAR_BG = "#0E0E1A"
_CARD = "#1E1E2E"


class MainScreen(ctk.CTkFrame):
    def __init__(self, master, session_data: dict, on_logout=None):
        super().__init__(master, fg_color=_BG)
        self._session = session_data
        self._on_logout = on_logout
        self._results: List[Dict[str, Any]] = []
        self._searching = False
        self._selected_leads: Dict[str, Dict] = {}
        self._row_check_vars: Dict[str, ctk.BooleanVar] = {}
        self._select_all_var = ctk.BooleanVar(value=False)
        self._active_panel = "pesquisa"
        self._panel_frame: Optional[ctk.CTkFrame] = None
        self._nav_btns: Dict[str, ctk.CTkButton] = {}
        self._build()

    # ── Build principal ────────────────────────────────────────────────────

    def _build(self):
        subscriber = is_subscriber(self._session)
        name = self._session.get("name", "Utilizador")
        email = self._session.get("email", "")
        display_name = name if name and name != email else email.split("@")[0]

        # Sidebar esquerda
        sidebar = ctk.CTkFrame(self, fg_color=_SIDEBAR_BG, width=_SIDEBAR_W, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo / título
        ctk.CTkLabel(
            sidebar, text="🔍\nGerador\nde Leads",
            font=ctk.CTkFont(size=12, weight="bold"),
            justify="center",
        ).pack(pady=(20, 4))

        badge_color = "#10B981" if subscriber else "#6B7280"
        badge_text = "Assinante" if subscriber else "Gratuito"
        ctk.CTkLabel(
            sidebar, text=badge_text,
            fg_color=badge_color, corner_radius=8,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="white", padx=6, pady=2,
        ).pack(pady=(0, 16))

        ctk.CTkFrame(sidebar, fg_color="#2A2A3E", height=1).pack(fill="x", padx=12, pady=(0, 12))

        # Botões de navegação
        nav_items = [
            ("pesquisa",   "🔍",  "Pesquisar"),
            ("prospectar", "📱",  "Prospectar"),
            ("historico",  "📋",  "Histórico"),
            ("conta",      "⚙",   "Conta"),
        ]
        for panel_id, icon, label in nav_items:
            btn = ctk.CTkButton(
                sidebar,
                text=f"{icon}  {label}",
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                hover_color="#1E1E2E",
                text_color="#9CA3AF",
                font=ctk.CTkFont(size=12),
                command=lambda pid=panel_id: self._switch_panel(pid),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[panel_id] = btn

        # Utilizador + logout no fundo do sidebar
        ctk.CTkFrame(sidebar, fg_color="#2A2A3E", height=1).pack(fill="x", padx=12, pady=(8, 8), side="bottom")
        ctk.CTkButton(
            sidebar, text="↩ Sair",
            anchor="w", height=36, corner_radius=8,
            fg_color="transparent", hover_color="#1E1E2E",
            text_color="#4B5563", font=ctk.CTkFont(size=11),
            command=self._logout,
        ).pack(fill="x", padx=8, pady=(0, 4), side="bottom")
        ctk.CTkLabel(
            sidebar, text=display_name[:16],
            font=ctk.CTkFont(size=10), text_color="#6B7280",
        ).pack(pady=(0, 4), side="bottom")

        # Área de conteúdo
        self._content_area = ctk.CTkFrame(self, fg_color=_BG, corner_radius=0)
        self._content_area.pack(side="left", fill="both", expand=True)

        # Painel inicial
        self._switch_panel("pesquisa")

    def _switch_panel(self, panel_id: str) -> None:
        self._active_panel = panel_id

        # Actualizar estilos dos botões nav
        for pid, btn in self._nav_btns.items():
            if pid == panel_id:
                btn.configure(fg_color="#1D4ED8", text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#9CA3AF")

        # Destruir painel actual
        if self._panel_frame is not None:
            self._panel_frame.destroy()

        # Criar novo painel
        self._panel_frame = ctk.CTkFrame(self._content_area, fg_color=_BG, corner_radius=0)
        self._panel_frame.pack(fill="both", expand=True)

        builders = {
            "pesquisa":   self._build_pesquisa,
            "prospectar": self._build_prospectar,
            "historico":  self._build_historico,
            "conta":      self._build_conta,
        }
        builders[panel_id](self._panel_frame)

    # ══════════════════════════════════════════════════════════════════════════
    # PAINEL 1 — PESQUISAR
    # ══════════════════════════════════════════════════════════════════════════

    def _build_pesquisa(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkScrollableFrame(parent, fg_color=_BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        # Formulário
        form = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        form.pack(padx=16, pady=12, fill="x")

        ctk.CTkLabel(form, text="Nova Pesquisa",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 8))

        fields_row = ctk.CTkFrame(form, fg_color="transparent")
        fields_row.pack(padx=16, pady=(0, 8), fill="x")
        fields_row.columnconfigure(0, weight=2)
        fields_row.columnconfigure(1, weight=2)
        fields_row.columnconfigure(2, weight=1)

        for col_idx, label in enumerate(["Nicho / Tipo de negócio", "Cidade / Região", "Limite"]):
            ctk.CTkLabel(fields_row, text=label, font=ctk.CTkFont(size=11)).grid(
                row=0, column=col_idx, sticky="w", padx=(0, 8) if col_idx < 2 else 0, pady=(0, 4)
            )

        self._niche = ctk.CTkEntry(fields_row, placeholder_text="ex: dentistas", height=36, corner_radius=8)
        self._niche.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self._city = ctk.CTkEntry(fields_row, placeholder_text="ex: São Paulo, SP", height=36, corner_radius=8)
        self._city.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        self._limit_var = ctk.StringVar(value="20")
        ctk.CTkOptionMenu(fields_row, values=["10", "20", "40", "60"],
                          variable=self._limit_var, height=36, corner_radius=8
                          ).grid(row=1, column=2, sticky="ew")

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(padx=16, pady=(8, 14), fill="x")

        self._search_btn = ctk.CTkButton(
            btn_row, text="🔍  Pesquisar", height=38, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_search,
        )
        self._search_btn.pack(side="left")

        self._mode_label = ctk.CTkLabel(
            btn_row, text=self._mode_description(),
            font=ctk.CTkFont(size=10), text_color="#6B7280",
        )
        self._mode_label.pack(side="left", padx=10)

        # Barra de progresso
        self._progress_frame = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        self._progress_bar = ctk.CTkProgressBar(self._progress_frame, height=8, corner_radius=4)
        self._progress_bar.set(0)
        self._progress_bar.pack(padx=16, pady=(12, 4), fill="x")
        self._progress_label = ctk.CTkLabel(self._progress_frame, text="",
                                             font=ctk.CTkFont(size=12), text_color="#9CA3AF")
        self._progress_label.pack(padx=16, pady=(0, 12))

        # Erro
        self._error_label = ctk.CTkLabel(body, text="", text_color="#EF4444",
                                          font=ctk.CTkFont(size=12), wraplength=420)

        # Resultados
        self._results_frame = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)

        # Mostrar resultados anteriores se existirem
        if self._results:
            self._show_results(self._results)

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
                results = search_leads(query=query, limit=limit,
                                       session=self._session, progress_callback=self._on_progress)
                self.after(0, lambda r=results: self._show_results(r))
            except SearchError as e:
                self.after(0, lambda msg=str(e): self._show_error(msg))
            finally:
                self.after(0, self._reset_search_btn)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_progress(self, current: int, total: int, message: str):
        def _update():
            try:
                pct = (current / total) if total > 0 else 0
                self._progress_bar.set(min(pct, 1.0))
                self._progress_label.configure(text=message)
            except Exception:
                pass
        self.after(0, _update)

    def _show_progress(self, visible: bool):
        if visible:
            self._progress_frame.pack(padx=16, pady=(0, 8), fill="x")
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
        self._selected_leads.clear()
        self._row_check_vars.clear()
        self._select_all_var.set(False)

        for w in self._results_frame.winfo_children():
            w.destroy()

        subscriber = is_subscriber(self._session)
        n_action_cols = 2 if subscriber else 1
        total_inner_cols = 5 + n_action_cols

        count_text = f"{len(results)} lead{'s' if len(results) != 1 else ''} encontrado{'s' if len(results) != 1 else ''}"
        hdr = ctk.CTkFrame(self._results_frame, fg_color="transparent")
        hdr.pack(padx=16, pady=(12, 4), fill="x")
        ctk.CTkLabel(hdr, text=count_text, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        if results:
            ctk.CTkButton(hdr, text="📥 Excel", height=28, corner_radius=8,
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=self._export_excel).pack(side="right", padx=(4, 0))

            if subscriber:
                ctk.CTkButton(
                    hdr, text="💾 Guardar todos no CRM", height=28, corner_radius=8,
                    fg_color="#065F46", hover_color="#047857",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=self._save_all_to_crm,
                ).pack(side="right", padx=(4, 0))

            # Barra de selecção em lote
            self._sel_bar = ctk.CTkFrame(self._results_frame, fg_color="#1E3A5F", corner_radius=8)
            self._sel_label = ctk.CTkLabel(self._sel_bar, text="0 seleccionados",
                                            font=ctk.CTkFont(size=11), text_color="#93C5FD")
            self._sel_label.pack(side="left", padx=10, pady=6)
            ctk.CTkButton(self._sel_bar, text="📱 Prospectar seleccionados",
                          height=28, corner_radius=6, font=ctk.CTkFont(size=11, weight="bold"),
                          command=self._prospect_selected).pack(side="left", padx=(0, 6), pady=6)
            ctk.CTkButton(self._sel_bar, text="✕ Limpar", height=28, corner_radius=6,
                          fg_color="#374151", hover_color="#4B5563", font=ctk.CTkFont(size=10),
                          command=self._clear_selection).pack(side="left", pady=6)

        if not results:
            ctk.CTkLabel(self._results_frame,
                         text="Nenhum resultado encontrado.",
                         text_color="#6B7280", font=ctk.CTkFont(size=12)).pack(pady=16)
        else:
            table_frame = ctk.CTkScrollableFrame(self._results_frame, fg_color="transparent", height=280)
            table_frame.pack(padx=16, pady=(4, 12), fill="x")
            table_frame.columnconfigure(0, weight=1)

            # Cabeçalho
            hdr_row = ctk.CTkFrame(table_frame, fg_color="transparent")
            hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
            hdr_row.columnconfigure(0, weight=0)
            for i in range(1, 5):
                hdr_row.columnconfigure(i, weight=1)

            ctk.CTkCheckBox(hdr_row, text="", variable=self._select_all_var,
                             width=20, height=20, checkbox_width=16, checkbox_height=16,
                             command=self._toggle_all).grid(row=0, column=0, padx=(4, 8))

            for c_idx, col in enumerate(["Nome", "Telefone", "Website", "Avaliação"]):
                ctk.CTkLabel(hdr_row, text=col, font=ctk.CTkFont(size=10, weight="bold"),
                              text_color="#9CA3AF").grid(row=0, column=c_idx + 1, sticky="w", padx=(0, 6))

            for r_idx, item in enumerate(results[:60]):
                phone_key = item.get("phone") or f"__idx_{r_idx}"
                var = ctk.BooleanVar(value=False)
                self._row_check_vars[phone_key] = var

                row_color = "#1A1A2E" if r_idx % 2 == 0 else "#16162A"
                row_frame = ctk.CTkFrame(table_frame, fg_color=row_color, corner_radius=6, height=34)
                row_frame.grid(row=r_idx + 1, column=0, sticky="ew", pady=1)
                row_frame.columnconfigure(0, weight=0)
                for i in range(1, 5):
                    row_frame.columnconfigure(i, weight=1)
                for i in range(5, total_inner_cols):
                    row_frame.columnconfigure(i, weight=0)
                row_frame.grid_propagate(False)

                ctk.CTkCheckBox(row_frame, text="", variable=var, width=20, height=20,
                                 checkbox_width=16, checkbox_height=16,
                                 command=lambda pk=phone_key, it=item, v=var: self._on_lead_check(pk, it, v)
                                 ).grid(row=0, column=0, padx=(6, 4), pady=7)

                values = [
                    item.get("name", "") or "",
                    item.get("phone", "") or "",
                    item.get("website", "") or "",
                    f"⭐ {item.get('rating', '')}" if item.get("rating") else "",
                ]
                for c_idx, val in enumerate(values):
                    ctk.CTkLabel(row_frame,
                                  text=str(val)[:38] + ("…" if len(str(val)) > 38 else ""),
                                  font=ctk.CTkFont(size=10), anchor="w"
                                  ).grid(row=0, column=c_idx + 1, sticky="w", padx=(2, 4), pady=4)

                ctk.CTkButton(row_frame, text="📱 WA", width=52, height=24,
                               fg_color="#1D4ED8", hover_color="#1E40AF",
                               font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
                               command=lambda it=item: self._open_prospect_dialog(it)
                               ).grid(row=0, column=5, padx=(2, 2), pady=5)

                if subscriber:
                    ctk.CTkButton(row_frame, text="💾 CRM", width=58, height=24,
                                   fg_color="#065F46", hover_color="#047857",
                                   font=ctk.CTkFont(size=10, weight="bold"), corner_radius=6,
                                   command=lambda it=item: self._save_lead_to_crm(it)
                                   ).grid(row=0, column=6, padx=(0, 6), pady=5)

        self._results_frame.pack(padx=16, pady=(0, 8), fill="x")

    # ── Selecção ──────────────────────────────────────────────────────────────

    def _on_lead_check(self, phone_key: str, item: dict, var: ctk.BooleanVar) -> None:
        if var.get():
            self._selected_leads[phone_key] = item
        else:
            self._selected_leads.pop(phone_key, None)
        self._refresh_selection_ui()

    def _toggle_all(self) -> None:
        checked = self._select_all_var.get()
        for phone_key, var in self._row_check_vars.items():
            var.set(checked)
        if checked:
            for i, item in enumerate(self._results[:60]):
                pk = item.get("phone") or f"__idx_{i}"
                self._selected_leads[pk] = item
        else:
            self._selected_leads.clear()
        self._refresh_selection_ui()

    def _clear_selection(self) -> None:
        self._selected_leads.clear()
        self._select_all_var.set(False)
        for var in self._row_check_vars.values():
            var.set(False)
        self._refresh_selection_ui()

    def _refresh_selection_ui(self) -> None:
        n = len(self._selected_leads)
        if not hasattr(self, "_sel_bar"):
            return
        if n > 0:
            self._sel_label.configure(text=f"{n} lead{'s' if n != 1 else ''} seleccionado{'s' if n != 1 else ''}")
            self._sel_bar.pack(padx=16, pady=(0, 6), fill="x")
        else:
            self._sel_bar.pack_forget()

    def _prospect_selected(self) -> None:
        if not self._selected_leads:
            return
        from app.ui.bulk_prospect_dialog import BulkProspectDialog
        BulkProspectDialog(self, leads=list(self._selected_leads.values()), session=self._session)

    # ── Diálogos ──────────────────────────────────────────────────────────────

    def _open_prospect_dialog(self, lead_data: dict) -> None:
        from app.ui.prospect_dialog import ProspectDialog
        ProspectDialog(self, lead_data=lead_data, session=self._session)

    def _save_lead_to_crm(self, lead_data: dict) -> None:
        def _do():
            try:
                from app.crm_client import create_lead
                result = create_lead(self._session, name=lead_data.get("name", "Lead"),
                                     phone=lead_data.get("phone", ""),
                                     website=lead_data.get("website", ""),
                                     address=lead_data.get("address", ""))
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
        popup.geometry("340x120")
        popup.resizable(False, False)
        popup.grab_set()
        ctk.CTkLabel(popup, text=msg, text_color="#10B981" if ok else "#EF4444",
                      font=ctk.CTkFont(size=13), wraplength=300).pack(pady=(24, 10))
        ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack()

    def _save_all_to_crm(self) -> None:
        """Guarda todos os resultados actuais no CRM (assíncrono, com popup de progresso)."""
        if not self._results:
            return
        total = len(self._results)

        popup = ctk.CTkToplevel(self)
        popup.title("Guardar no CRM")
        popup.geometry("380x160")
        popup.resizable(False, False)
        popup.grab_set()

        lbl = ctk.CTkLabel(
            popup, text=f"A guardar 0 / {total} leads…",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF", wraplength=340,
        )
        lbl.pack(pady=(28, 8))

        close_btn = ctk.CTkButton(popup, text="Fechar", width=90, command=popup.destroy)
        close_btn.pack(pady=6)

        def _do():
            from app.crm_client import create_lead
            saved = skipped = errors = 0
            for i, item in enumerate(self._results):
                try:
                    result = create_lead(
                        self._session,
                        name=item.get("name", "Lead"),
                        phone=item.get("phone", ""),
                        website=item.get("website", ""),
                        address=item.get("address", ""),
                    )
                    if result.get("status") == "exists":
                        skipped += 1
                    else:
                        saved += 1
                except Exception:
                    errors += 1
                self.after(0, lambda c=i + 1: lbl.configure(
                    text=f"A guardar {c} / {total} leads…", text_color="#9CA3AF"))

            parts = []
            if saved:
                parts.append(f"✓ {saved} guardado{'s' if saved != 1 else ''}")
            if skipped:
                parts.append(f"⟳ {skipped} já existia{'m' if skipped != 1 else ''}")
            if errors:
                parts.append(f"✗ {errors} erro{'s' if errors != 1 else ''}")
            summary = "   ".join(parts) or "Nenhum lead processado"
            color = "#10B981" if errors == 0 else "#F59E0B"
            self.after(0, lambda: lbl.configure(text=summary, text_color=color))

        threading.Thread(target=_do, daemon=True).start()

    def _show_error(self, msg: str):
        self._error_label.configure(text=f"⚠  {msg}")
        self._error_label.pack(padx=16, pady=(0, 8))

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_excel(self):
        if not self._results:
            return
        niche = self._niche.get().strip() if hasattr(self, "_niche") else ""
        city = self._city.get().strip() if hasattr(self, "_city") else ""
        query = f"{niche} em {city}" if niche and city else "pesquisa"

        from tkinter import filedialog
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
            initialfile=f"leads_{ts}.xlsx",
            title="Guardar leads como...",
        )
        if not path:
            return
        try:
            from app.export import export_to_excel
            export_to_excel(self._results, query, Path(path))
            popup = ctk.CTkToplevel(self)
            popup.title("Exportado!")
            popup.geometry("340x130")
            popup.grab_set()
            ctk.CTkLabel(popup, text="✅  Ficheiro guardado!",
                          font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(24, 6))
            ctk.CTkLabel(popup, text=Path(path).name,
                          font=ctk.CTkFont(size=11), text_color="#9CA3AF").pack()
            ctk.CTkButton(popup, text="OK", width=90, command=popup.destroy).pack(pady=12)
        except Exception as exc:
            self._show_error(f"Erro ao exportar: {exc}")

    # ══════════════════════════════════════════════════════════════════════════
    # PAINEL 2 — PROSPECTAR (Kanban de prospecção)
    # ══════════════════════════════════════════════════════════════════════════

    _KANBAN_COLS = [
        ("to-prospect",  "À Prospectar",  "#6366f1"),
        ("in-progress",  "Em Andamento",  "#f59e0b"),
        ("qualification", "Qualificação", "#22c55e"),
    ]

    def _build_prospectar(self, parent: ctk.CTkFrame) -> None:
        import threading as _threading
        subscriber = is_subscriber(self._session)

        # Para o polling anterior se existir
        if hasattr(self, "_kanban_stop_event") and self._kanban_stop_event is not None:
            self._kanban_stop_event.set()
        self._kanban_stop_event = _threading.Event()
        self._kanban_selected: dict = {}

        # ── Header ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=0, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text="Pipeline de Prospecção",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=16)

        ctk.CTkButton(
            hdr, text="📱 WhatsApp Web", height=30, corner_radius=6,
            fg_color="#065F46", hover_color="#047857", font=ctk.CTkFont(size=11),
            command=self._open_whatsapp_web_inline,
        ).pack(side="right", padx=4, pady=10)

        # Badges de estado (agente + pendentes)
        self._agent_badge_lbl = ctk.CTkLabel(
            hdr, text="● Agente: —",
            font=ctk.CTkFont(size=10), text_color="#6B7280",
            fg_color="#2A2A3E", corner_radius=6, padx=8, pady=2,
        )
        self._agent_badge_lbl.pack(side="right", padx=4, pady=14)

        self._pending_badge_lbl = ctk.CTkLabel(
            hdr, text="Pendentes: —",
            font=ctk.CTkFont(size=10), text_color="#6B7280",
            fg_color="#2A2A3E", corner_radius=6, padx=8, pady=2,
        )
        self._pending_badge_lbl.pack(side="right", padx=4, pady=14)

        # ── Área do Kanban ────────────────────────────────────────────────
        kanban_outer = ctk.CTkFrame(parent, fg_color=_BG, corner_radius=0)
        kanban_outer.pack(fill="both", expand=True)

        # Acção rápida se há leads seleccionados na pesquisa
        if self._selected_leads:
            n = len(self._selected_leads)
            quick = ctk.CTkFrame(kanban_outer, fg_color="#1E3A5F", corner_radius=10)
            quick.pack(padx=12, pady=(8, 0), fill="x")
            ctk.CTkLabel(
                quick,
                text=f"✓  {n} lead{'s' if n != 1 else ''} seleccionado{'s' if n != 1 else ''} em Pesquisar",
                font=ctk.CTkFont(size=11), text_color="#93C5FD",
            ).pack(side="left", padx=12, pady=8)
            ctk.CTkButton(
                quick, text="📱 Prospectar agora →", height=28, corner_radius=6,
                font=ctk.CTkFont(size=11), command=self._prospect_selected,
            ).pack(side="right", padx=10, pady=8)

        # BulkActions (visível quando há leads seleccionados no Kanban)
        self._bulk_bar = ctk.CTkFrame(kanban_outer, fg_color="#1E3A5F", corner_radius=10)
        self._bulk_count_lbl = ctk.CTkLabel(
            self._bulk_bar, text="0 seleccionados",
            font=ctk.CTkFont(size=11), text_color="#93C5FD",
        )
        self._bulk_count_lbl.pack(side="left", padx=10, pady=8)

        self._bulk_msg_entry = ctk.CTkEntry(
            self._bulk_bar, placeholder_text="Mensagem (opcional — usa mensagem guardada se vazio)",
            height=28, corner_radius=6, width=340, font=ctk.CTkFont(size=11),
        )
        self._bulk_msg_entry.pack(side="left", padx=(0, 6), pady=8)

        ctk.CTkButton(
            self._bulk_bar, text="📤 Enfileirar", height=28, corner_radius=6,
            fg_color="#1D4ED8", hover_color="#1E40AF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._enqueue_selected_leads,
        ).pack(side="left", padx=(0, 4), pady=8)

        ctk.CTkButton(
            self._bulk_bar, text="✕", width=28, height=28, corner_radius=6,
            fg_color="#374151", hover_color="#4B5563",
            font=ctk.CTkFont(size=11),
            command=self._clear_kanban_selection,
        ).pack(side="left", pady=8)

        # Frame de conteúdo recarregável
        kanban_content = ctk.CTkFrame(kanban_outer, fg_color=_BG, corner_radius=0)
        kanban_content.pack(fill="both", expand=True)
        self._kanban_content = kanban_content  # referência para enqueue e polling

        # Refresh button — aponta para kanban_content
        ctk.CTkButton(
            hdr, text="⟳ Actualizar", height=30, corner_radius=6,
            fg_color="#2A2A3E", hover_color="#3A3A5E", font=ctk.CTkFont(size=11),
            command=lambda: self._reload_kanban(kanban_content, subscriber),
        ).pack(side="right", padx=4, pady=10)

        self._reload_kanban(kanban_content, subscriber)

        if subscriber:
            self._start_polling(kanban_content, subscriber, self._kanban_stop_event)

    @staticmethod
    def _widget_alive(w) -> bool:
        """Retorna True se o widget ainda existe e não foi destruído."""
        try:
            return bool(w.winfo_exists())
        except Exception:
            return False

    def _reload_kanban(self, container: ctk.CTkFrame, subscriber: bool) -> None:
        """Limpa o container de conteúdo e recarrega o Kanban."""
        if not self._widget_alive(container):
            return
        for w in list(container.winfo_children()):
            w.destroy()

        if not subscriber:
            self._build_kanban_non_subscriber(container)
            return

        lbl = ctk.CTkLabel(container, text="A carregar leads…",
                            font=ctk.CTkFont(size=12), text_color="#9CA3AF")
        lbl.pack(pady=30)

        def _fetch():
            try:
                from app.crm_client import get_leads_kanban
                leads = get_leads_kanban(self._session)
                self.after(0, lambda l=leads: self._render_kanban(container, l))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._show_kanban_error(container, e))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_kanban(self, container: ctk.CTkFrame, leads: list) -> None:
        """Renderiza as 3 colunas do Kanban."""
        if not self._widget_alive(container):
            return
        for w in list(container.winfo_children()):
            w.destroy()

        if not leads:
            empty = ctk.CTkFrame(container, fg_color=_CARD, corner_radius=10)
            empty.pack(padx=12, pady=12, fill="x")
            ctk.CTkLabel(
                empty,
                text="Sem leads nas colunas de prospecção.",
                font=ctk.CTkFont(size=12), text_color="#6B7280",
            ).pack(padx=16, pady=(14, 4))
            ctk.CTkLabel(
                empty,
                text="Pesquise empresas em 🔍 Pesquisar e guarde-as no CRM com 💾 — aparecem aqui em 'À Prospectar'.",
                font=ctk.CTkFont(size=11), text_color="#4B5563", wraplength=460, justify="left",
            ).pack(padx=16, pady=(0, 14))
            return

        grid = ctk.CTkFrame(container, fg_color=_BG)
        grid.pack(fill="both", expand=True, padx=8, pady=8)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)
        grid.rowconfigure(0, weight=1)

        for col_idx, (cat_id, cat_label, col_color) in enumerate(self._KANBAN_COLS):
            col_leads = [l for l in leads if l.get("category") == cat_id]

            col_frame = ctk.CTkFrame(grid, fg_color="#1A1A2E", corner_radius=10)
            col_frame.grid(row=0, column=col_idx, sticky="nsew", padx=4, pady=4)
            col_frame.rowconfigure(1, weight=1)
            col_frame.columnconfigure(0, weight=1)

            # Cabeçalho colorido
            hdr_f = ctk.CTkFrame(col_frame, fg_color=col_color, corner_radius=8, height=36)
            hdr_f.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
            hdr_f.pack_propagate(False)
            ctk.CTkLabel(
                hdr_f,
                text=f"{cat_label}  ({len(col_leads)})",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="white",
            ).pack(expand=True)

            # Área de cards
            cards_scroll = ctk.CTkScrollableFrame(col_frame, fg_color="transparent")
            cards_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))

            if not col_leads:
                ctk.CTkLabel(
                    cards_scroll, text="Sem leads",
                    font=ctk.CTkFont(size=11), text_color="#374151",
                ).pack(pady=16)
            else:
                for lead in col_leads:
                    self._render_kanban_card(cards_scroll, lead, cat_id, container)

    def _render_kanban_card(
        self,
        parent: ctk.CTkFrame,
        lead: dict,
        current_cat: str,
        kanban_container: ctk.CTkFrame,
    ) -> None:
        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=8)
        card.pack(fill="x", padx=4, pady=3)

        name = (lead.get("companyName") or lead.get("contactName") or "Lead")[:26]
        phone = lead.get("phone") or "—"
        lead_id = lead.get("id")
        origin = lead.get("origin") or ""

        # Linha de topo: nome + checkbox (só em to-prospect)
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=8, pady=(6, 1))

        ctk.CTkLabel(
            top_row, text=name,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
        ).pack(side="left", fill="x", expand=True)

        if current_cat == "to-prospect" and lead_id is not None:
            var = ctk.BooleanVar(value=lead_id in self._kanban_selected)
            ctk.CTkCheckBox(
                top_row, text="", variable=var,
                width=20, height=20, checkbox_width=16, checkbox_height=16,
                command=lambda lid=lead_id, v=var: self._on_kanban_check(lid, v),
            ).pack(side="right")

        phone_pady = (0, 1) if origin else (0, 6)
        ctk.CTkLabel(
            card, text=phone,
            font=ctk.CTkFont(size=10), text_color="#6B7280", anchor="w",
        ).pack(fill="x", padx=8, pady=phone_pady)

        if origin:
            ctk.CTkLabel(
                card, text=f"#{lead_id} · {origin}",
                font=ctk.CTkFont(size=9), text_color="#374151", anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 6))

    # ── Selecção Kanban ────────────────────────────────────────────────────────

    def _on_kanban_check(self, lead_id: int, var: ctk.BooleanVar) -> None:
        if var.get():
            self._kanban_selected[lead_id] = lead_id
        else:
            self._kanban_selected.pop(lead_id, None)
        self._refresh_bulk_bar()

    def _refresh_bulk_bar(self) -> None:
        if not hasattr(self, "_bulk_bar") or not self._widget_alive(self._bulk_bar):
            return
        n = len(self._kanban_selected)
        if n > 0:
            self._bulk_count_lbl.configure(text=f"{n} lead{'s' if n != 1 else ''} seleccionado{'s' if n != 1 else ''}")
            self._bulk_bar.pack(padx=12, pady=(4, 0), fill="x")
        else:
            self._bulk_bar.pack_forget()

    def _clear_kanban_selection(self) -> None:
        self._kanban_selected.clear()
        self._refresh_bulk_bar()

    def _enqueue_selected_leads(self) -> None:
        lead_ids = list(self._kanban_selected.keys())
        if not lead_ids:
            return
        msg = self._bulk_msg_entry.get().strip() if hasattr(self, "_bulk_msg_entry") else ""

        # Feedback visual imediato
        if hasattr(self, "_bulk_msg_entry"):
            self._bulk_msg_entry.configure(state="disabled")

        def _do():
            try:
                from app.crm_client import enqueue_whatsapp, move_lead_category
                result = enqueue_whatsapp(self._session, lead_ids, message=msg or None)
                queued_ids = [q["lead_id"] for q in (result.get("queued") or [])]
                for lid in queued_ids:
                    try:
                        move_lead_category(self._session, lid, "in-progress")
                    except Exception:
                        pass
                skipped = result.get("skipped") or []
                n_queued = len(queued_ids)
                n_skip = len(skipped)
                parts = []
                if n_queued:
                    parts.append(f"✓ {n_queued} enfileirado{'s' if n_queued != 1 else ''}")
                if n_skip:
                    parts.append(f"⚠ {n_skip} ignorado{'s' if n_skip != 1 else ''}")
                summary = "  ".join(parts) or "Nenhum lead enfileirado"

                def _after():
                    try:
                        if hasattr(self, "_bulk_msg_entry") and self._widget_alive(self._bulk_msg_entry):
                            self._bulk_msg_entry.configure(state="normal")
                            self._bulk_msg_entry.delete(0, "end")
                    except Exception:
                        pass
                    self._kanban_selected.clear()
                    self._refresh_bulk_bar()
                    self._show_enqueue_toast(summary)
                    kc = getattr(self, "_kanban_content", None)
                    if kc and self._widget_alive(kc):
                        self._reload_kanban(kc, is_subscriber(self._session))

                self.after(0, _after)
            except Exception as exc:
                def _err(e=str(exc)):
                    try:
                        if hasattr(self, "_bulk_msg_entry") and self._widget_alive(self._bulk_msg_entry):
                            self._bulk_msg_entry.configure(state="normal")
                    except Exception:
                        pass
                    self._show_enqueue_toast(f"✗ Erro: {e[:80]}", ok=False)
                self.after(0, _err)

        threading.Thread(target=_do, daemon=True).start()

    def _show_enqueue_toast(self, msg: str, ok: bool = True) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("Enfileirar")
        popup.geometry("340x110")
        popup.resizable(False, False)
        popup.grab_set()
        ctk.CTkLabel(popup, text=msg,
                     text_color="#10B981" if ok else "#EF4444",
                     font=ctk.CTkFont(size=12), wraplength=300).pack(pady=(24, 10))
        ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack()

    # ── Polling de automação ───────────────────────────────────────────────────

    def _start_polling(self, container: ctk.CTkFrame, subscriber: bool,
                       stop_event) -> None:
        def _loop():
            seen_ids: set = set()
            while not stop_event.is_set():
                stop_event.wait(7)
                if stop_event.is_set():
                    break
                self._poll_tick(container, subscriber, seen_ids, stop_event)
        threading.Thread(target=_loop, daemon=True).start()

    def _poll_tick(self, container: ctk.CTkFrame, subscriber: bool,
                   seen_ids: set, stop_event) -> None:
        if stop_event.is_set():
            return
        try:
            from app.crm_client import get_agent_overview, get_whatsapp_queue_count

            # Actualiza badge de agente
            try:
                overview = get_agent_overview(self._session)
                agents = overview.get("agents") or []
                online = any(a.get("online") for a in agents)
                badge_text = "● Agente: Online"
                badge_color = "#10B981"
                if not online:
                    badge_text = "● Agente: Offline"
                    badge_color = "#6B7280"
                self.after(0, lambda t=badge_text, c=badge_color: self._update_agent_badge(t, c))
            except Exception:
                pass

            # Actualiza badge de pendentes
            try:
                count = get_whatsapp_queue_count(self._session)
                self.after(0, lambda n=count: self._update_pending_badge(n))
            except Exception:
                pass

            # Verifica resultados recentes e move leads
            if stop_event.is_set():
                return
            try:
                from app.crm_client import get_whatsapp_recent, move_lead_category
                rows = get_whatsapp_recent(self._session, since_secs=120)
                moved = False
                for row in rows:
                    rid = row.get("id")
                    if rid is None or rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    lead_id = row.get("lead_id")
                    status = row.get("status")
                    if not lead_id:
                        continue
                    try:
                        if status == "sent":
                            move_lead_category(self._session, lead_id, "qualification")
                            moved = True
                        elif status == "failed":
                            move_lead_category(self._session, lead_id, "to-prospect")
                            moved = True
                    except Exception:
                        pass
                if moved and not stop_event.is_set():
                    self.after(0, lambda: self._reload_kanban(container, subscriber)
                               if self._widget_alive(container) else None)
            except Exception:
                pass
        except Exception:
            pass

    def _update_agent_badge(self, text: str, color: str) -> None:
        try:
            if hasattr(self, "_agent_badge_lbl") and self._widget_alive(self._agent_badge_lbl):
                self._agent_badge_lbl.configure(text=text, text_color=color)
        except Exception:
            pass

    def _update_pending_badge(self, count: int) -> None:
        try:
            if hasattr(self, "_pending_badge_lbl") and self._widget_alive(self._pending_badge_lbl):
                self._pending_badge_lbl.configure(text=f"Pendentes: {count}")
        except Exception:
            pass

    def _show_kanban_error(self, container: ctk.CTkFrame, msg: str) -> None:
        if not self._widget_alive(container):
            return
        for w in list(container.winfo_children()):
            w.destroy()
        ctk.CTkLabel(
            container,
            text=f"⚠  Erro ao carregar leads: {msg[:120]}",
            text_color="#EF4444", font=ctk.CTkFont(size=11), wraplength=440,
        ).pack(padx=16, pady=20)

    def _build_kanban_non_subscriber(self, container: ctk.CTkFrame) -> None:
        from app.session import get_prospect_log

        pitch = ctk.CTkFrame(container, fg_color="#1E1B4B", corner_radius=12)
        pitch.pack(padx=12, pady=(12, 8), fill="x")
        ctk.CTkLabel(
            pitch, text="📊  Kanban completo disponível para Assinantes",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#A5B4FC",
        ).pack(padx=16, pady=(12, 3))
        ctk.CTkLabel(
            pitch,
            text="Assine para ver os seus leads nas fases de prospecção com integração CRM.",
            font=ctk.CTkFont(size=10), text_color="#818CF8", wraplength=420,
        ).pack(padx=16, pady=(0, 12))

        entries = get_prospect_log(60)
        if not entries:
            ctk.CTkLabel(
                container, text="Sem registos locais de prospecção ainda.",
                font=ctk.CTkFont(size=11), text_color="#6B7280",
            ).pack(pady=16)
            return

        sent = [e for e in entries if e.get("status") not in ("failed", "error")]
        failed = [e for e in entries if e.get("status") in ("failed", "error")]

        grid = ctk.CTkFrame(container, fg_color=_BG)
        grid.pack(fill="both", expand=True, padx=8, pady=8)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)

        for col_idx, (label, color, col_leads) in enumerate([
            ("Enviados", "#22c55e", sent),
            ("Falhados", "#ef4444", failed),
        ]):
            col_frame = ctk.CTkFrame(grid, fg_color="#1A1A2E", corner_radius=10)
            col_frame.grid(row=0, column=col_idx, sticky="nsew", padx=4, pady=4)
            col_frame.rowconfigure(1, weight=1)
            col_frame.columnconfigure(0, weight=1)

            hdr_f = ctk.CTkFrame(col_frame, fg_color=color, corner_radius=8, height=36)
            hdr_f.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
            hdr_f.pack_propagate(False)
            ctk.CTkLabel(
                hdr_f, text=f"{label}  ({len(col_leads)})",
                font=ctk.CTkFont(size=12, weight="bold"), text_color="white",
            ).pack(expand=True)

            cards_scroll = ctk.CTkScrollableFrame(col_frame, fg_color="transparent")
            cards_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))

            if not col_leads:
                ctk.CTkLabel(cards_scroll, text="Sem leads",
                              font=ctk.CTkFont(size=11), text_color="#374151").pack(pady=16)
            else:
                for entry in col_leads:
                    card = ctk.CTkFrame(cards_scroll, fg_color=_CARD, corner_radius=8)
                    card.pack(fill="x", padx=4, pady=3)
                    name = (entry.get("name") or "—")[:26]
                    phone = entry.get("phone") or "—"
                    ts = (entry.get("ts") or "")[:16].replace("T", " ")
                    ctk.CTkLabel(card, text=name,
                                  font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(fill="x", padx=8, pady=(6, 1))
                    ctk.CTkLabel(card, text=phone,
                                  font=ctk.CTkFont(size=10), text_color="#6B7280", anchor="w").pack(fill="x", padx=8, pady=(0, 1))
                    ctk.CTkLabel(card, text=ts,
                                  font=ctk.CTkFont(size=9), text_color="#374151", anchor="w").pack(fill="x", padx=8, pady=(0, 6))

    def _open_whatsapp_web_inline(self) -> None:
        """Abre Chrome com WhatsApp Web (botão no header do Kanban)."""
        popup = ctk.CTkToplevel(self)
        popup.title("WhatsApp Web")
        popup.geometry("360x140")
        popup.resizable(False, False)
        popup.grab_set()

        lbl = ctk.CTkLabel(popup, text="A abrir Chrome… (10–20s)",
                            font=ctk.CTkFont(size=12), text_color="#60A5FA")
        lbl.pack(pady=(24, 8))

        def _do():
            try:
                from app.whatsapp_client import open_for_login
                open_for_login()
                self.after(0, lambda: lbl.configure(
                    text="✓ Chrome aberto. Se aparecer QR code, faz o scan.",
                    text_color="#10B981"))
            except Exception as exc:
                self.after(0, lambda e=str(exc): lbl.configure(
                    text=f"✗ Erro: {e[:80]}", text_color="#EF4444"))

        ctk.CTkButton(popup, text="Fechar", width=90,
                       command=popup.destroy).pack(pady=4)
        threading.Thread(target=_do, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # PAINEL 3 — HISTÓRICO
    # ══════════════════════════════════════════════════════════════════════════

    def _build_historico(self, parent: ctk.CTkFrame) -> None:
        """Histórico de prospecções inline (sem popup separado)."""
        from app.session import get_prospect_log

        hdr = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=0, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="📋  Histórico de Prospecções",
                      font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=16)

        ctk.CTkButton(hdr, text="↺ Actualizar", height=30, corner_radius=6,
                       fg_color="#2A2A3E", hover_color="#3A3A5E", font=ctk.CTkFont(size=11),
                       command=lambda: self._switch_panel("historico")).pack(side="right", padx=12, pady=9)

        src = "Fonte: CRM (assinante)" if is_subscriber(self._session) else "Fonte: log local"
        ctk.CTkLabel(parent, text=src, font=ctk.CTkFont(size=10), text_color="#6B7280"
                      ).pack(anchor="w", padx=16, pady=(6, 0))

        loading_lbl = ctk.CTkLabel(parent, text="A carregar…",
                                    font=ctk.CTkFont(size=12), text_color="#9CA3AF")
        loading_lbl.pack(pady=12)

        table = ctk.CTkScrollableFrame(parent, fg_color="#12121F", corner_radius=8)
        table.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        def _fetch():
            if is_subscriber(self._session):
                try:
                    from app.crm_client import get_prospect_history
                    entries = get_prospect_history(self._session, limit=200)
                except Exception:
                    entries = get_prospect_log(200)
            else:
                entries = get_prospect_log(200)

            def _render():
                try:
                    if not self._widget_alive(table):
                        return
                    loading_lbl.pack_forget()
                    if not entries:
                        ctk.CTkLabel(table, text="Sem registos de prospecção.",
                                      font=ctk.CTkFont(size=12), text_color="#6B7280").pack(pady=20)
                        return

                    _ACTION_LABELS = {"manual_outbound": "Enviado (manual)", "sent": "Enviado",
                                       "failed": "Falhou", "queued": "Enfileirado"}

                    hdr_row = ctk.CTkFrame(table, fg_color="transparent")
                    hdr_row.pack(fill="x", padx=8, pady=(4, 4))
                    for col in ["Data/Hora", "Nome", "Telefone", "Estado", "Notas"]:
                        ctk.CTkLabel(hdr_row, text=col, font=ctk.CTkFont(size=10, weight="bold"),
                                      text_color="#9CA3AF", anchor="w", width=100 if col != "Notas" else 150
                                      ).pack(side="left", padx=4)

                    for idx, e in enumerate(entries):
                        ts = (e.get("created_at") or e.get("ts") or "")[:16].replace("T", " ")
                        name = (e.get("lead_name") or e.get("name") or "—")[:20]
                        phone = e.get("phone") or "—"
                        action = e.get("action") or e.get("status") or "—"
                        notes = (e.get("notes") or e.get("reason") or "—")[:28]
                        action_label = _ACTION_LABELS.get(action, action)
                        color = "#EF4444" if "fail" in action.lower() else "#10B981"

                        row = ctk.CTkFrame(table, fg_color="#1A1A2E" if idx % 2 == 0 else "#16162A",
                                            corner_radius=4)
                        row.pack(fill="x", padx=8, pady=1)
                        for val, tc, w in [(ts, "#9CA3AF", 100), (name, "#D1D5DB", 100),
                                            (phone, "#9CA3AF", 100), (action_label, color, 100),
                                            (notes, "#9CA3AF", 150)]:
                            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=10),
                                          text_color=tc, anchor="w", width=w
                                          ).pack(side="left", padx=(8 if val == ts else 4, 4), pady=5)

                    ctk.CTkLabel(table, text=f"{len(entries)} registos",
                                  font=ctk.CTkFont(size=10), text_color="#6B7280").pack(pady=6)
                except Exception:
                    pass

            self.after(0, _render)

        threading.Thread(target=_fetch, daemon=True).start()

        # Export CSV
        def _export_csv():
            import csv
            from tkinter import filedialog
            entries_snap = []  # será preenchido — simplificação: re-fetch
            path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                 filetypes=[("CSV", "*.csv")],
                                                 initialfile="historico.csv")
            if path:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Data", "Nome", "Telefone", "Estado", "Notas"])

        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=8)
        ctk.CTkButton(footer, text="📥 Exportar CSV", height=30, corner_radius=6,
                       fg_color="#2A2A3E", command=_export_csv).pack(side="left")

    # ══════════════════════════════════════════════════════════════════════════
    # PAINEL 4 — CONTA / CONFIGURAÇÕES
    # ══════════════════════════════════════════════════════════════════════════

    def _build_conta(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkScrollableFrame(parent, fg_color=_BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        subscriber = is_subscriber(self._session)
        name = self._session.get("name", "—")
        email = self._session.get("email", "—")

        # Secção: conta
        acc = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        acc.pack(padx=20, pady=(16, 12), fill="x")

        ctk.CTkLabel(acc, text="👤  A minha conta",
                      font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(14, 8))

        for label, val in [("Nome", name), ("Email", email)]:
            row = ctk.CTkFrame(acc, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(row, text=f"{label}:", font=ctk.CTkFont(size=11),
                          text_color="#9CA3AF", width=50).pack(side="left")
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=12)).pack(side="left", padx=6)

        badge_text = "✓ Assinante" if subscriber else "Gratuito"
        badge_color = "#10B981" if subscriber else "#6B7280"
        ctk.CTkLabel(acc, text=badge_text, fg_color=badge_color, corner_radius=8,
                      font=ctk.CTkFont(size=11), text_color="white", padx=8, pady=3
                      ).pack(anchor="w", padx=16, pady=(6, 8))

        ctk.CTkLabel(acc,
                      text="ℹ️  Para alterar conta ou recuperar acesso, faz novo login — o sistema envia código por email.",
                      font=ctk.CTkFont(size=10), text_color="#6B7280", wraplength=380, justify="left"
                      ).pack(anchor="w", padx=16, pady=(0, 14))

        # Secção: chave API (não-assinante)
        if not subscriber:
            api_card = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
            api_card.pack(padx=20, fill="x", pady=(0, 12))

            ctk.CTkLabel(api_card, text="🗝  Chave Google Maps API",
                          font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
            ctk.CTkLabel(api_card,
                          text="Configure para pesquisas fiáveis. Sem chave: usa Selenium (mais lento).",
                          font=ctk.CTkFont(size=11), text_color="#6B7280").pack(anchor="w", padx=16, pady=(0, 8))

            entry_row = ctk.CTkFrame(api_card, fg_color="transparent")
            entry_row.pack(padx=16, pady=(0, 6), fill="x")
            entry_row.columnconfigure(0, weight=1)

            key_entry = ctk.CTkEntry(entry_row, placeholder_text="AIza...", height=36,
                                      corner_radius=8, show="•")
            existing = self._session.get("google_maps_api_key", "")
            if existing:
                key_entry.insert(0, existing)
            key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

            visible = [False]

            def _toggle():
                visible[0] = not visible[0]
                key_entry.configure(show="" if visible[0] else "•")
                toggle_btn.configure(text="🙈" if visible[0] else "👁")

            toggle_btn = ctk.CTkButton(entry_row, text="👁", width=36, height=36,
                                        fg_color="#2A2A3E", command=_toggle)
            toggle_btn.grid(row=0, column=1)

            def _save_key():
                key = key_entry.get().strip()
                self._session["google_maps_api_key"] = key or None
                from app.session import save_session
                save_session(self._session)
                if hasattr(self, "_mode_label"):
                    self._mode_label.configure(text=self._mode_description())
                popup = ctk.CTkToplevel(self)
                popup.title("Guardado")
                popup.geometry("280x100")
                popup.grab_set()
                ctk.CTkLabel(popup, text="✓ Chave guardada", font=ctk.CTkFont(size=13)).pack(pady=24)
                self.after(1200, popup.destroy)

            ctk.CTkButton(api_card, text="Guardar chave", height=34,
                           command=_save_key).pack(padx=16, pady=(0, 14))
        else:
            info = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
            info.pack(padx=20, fill="x", pady=(0, 12))
            ctk.CTkLabel(info, text="✓  Chave Google Maps incluída na assinatura",
                          font=ctk.CTkFont(size=12), text_color="#10B981"
                          ).pack(padx=16, pady=14)

        # Templates
        tpl_card = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        tpl_card.pack(padx=20, fill="x", pady=(0, 12))
        ctk.CTkLabel(tpl_card, text="💬  Templates de mensagem",
                      font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))

        from app.session import get_templates
        templates = get_templates(self._session)
        if templates:
            for t in templates:
                row = ctk.CTkFrame(tpl_card, fg_color="#12121F", corner_radius=6)
                row.pack(fill="x", padx=16, pady=2)
                ctk.CTkLabel(row, text=t["name"], font=ctk.CTkFont(size=11),
                              anchor="w").pack(side="left", padx=10, pady=6)
                ctk.CTkLabel(row, text=t["text"][:50] + "…" if len(t.get("text","")) > 50 else t.get("text",""),
                              font=ctk.CTkFont(size=10), text_color="#6B7280",
                              anchor="w").pack(side="left", padx=4)

                def _del(name=t["name"]):
                    from app.session import delete_template, save_session
                    delete_template(self._session, name)
                    save_session(self._session)
                    self._switch_panel("conta")

                ctk.CTkButton(row, text="✕", width=28, height=24,
                               fg_color="#7F1D1D", hover_color="#991B1B",
                               font=ctk.CTkFont(size=10), command=_del
                               ).pack(side="right", padx=6, pady=4)
        else:
            ctk.CTkLabel(tpl_card, text="Sem templates guardados. Cria um no diálogo de prospecção.",
                          font=ctk.CTkFont(size=11), text_color="#6B7280"
                          ).pack(padx=16, pady=(0, 12))

        ctk.CTkLabel(tpl_card, text="", height=4).pack()  # spacer

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mode_description(self) -> str:
        if is_subscriber(self._session):
            return "Modo: Assinante — chave API incluída"
        key = self._session.get("google_maps_api_key")
        if key:
            return "Modo: Chave API própria configurada"
        return "Modo: Gratuito (Selenium) — configure a sua chave em ⚙ Conta"

    def _logout(self):
        from app.session import clear_session
        clear_session()
        if self._on_logout:
            self._on_logout()
