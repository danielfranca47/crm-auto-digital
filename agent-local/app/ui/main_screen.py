"""Ecrã principal — sidebar de navegação + painéis de conteúdo."""
from __future__ import annotations

import threading
import webbrowser
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
        self._kanban_card_vars: Dict[int, ctk.BooleanVar] = {}
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
            ("pesquisa",      "🔍",  "Pesquisar"),
            ("assistente-ia", "✨",  "Assistente IA"),
            ("prospectar",    "📱",  "Prospectar"),
            ("historico",     "📋",  "Histórico"),
            ("conta",         "⚙",   "Conta"),
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
            "pesquisa":      self._build_pesquisa,
            "assistente-ia": self._build_assistente_ia,
            "prospectar":    self._build_prospectar,
            "historico":     self._build_historico,
            "conta":         self._build_conta,
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
        self._results_hdr = hdr
        ctk.CTkLabel(hdr, text=count_text, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        if results:
            ctk.CTkButton(hdr, text="📥 Excel", height=28, corner_radius=8,
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=self._export_excel).pack(side="right", padx=(4, 0))

            if subscriber:
                ctk.CTkButton(
                    hdr, text="✨ Gerar copy com IA", height=28, corner_radius=8,
                    fg_color="#4F46E5", hover_color="#4338CA",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=self._ir_para_assistente_ia,
                ).pack(side="right", padx=(4, 0))

                ctk.CTkButton(
                    hdr, text="💾 Guardar todos no CRM", height=28, corner_radius=8,
                    fg_color="#065F46", hover_color="#047857",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=self._save_all_to_crm,
                ).pack(side="right", padx=(4, 0))
            else:
                self._gen_local_copies_btn = ctk.CTkButton(
                    hdr, text="✨ Gerar copies (local)", height=28, corner_radius=8,
                    fg_color="#4F46E5", hover_color="#4338CA",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=self._generate_local_copies_for_selected,
                )
                self._gen_local_copies_btn.pack(side="right", padx=(4, 0))

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

    # ── Geração de copies em lote (local, modo gratuito) ─────────────────────

    _LOCAL_COPY_BATCH_LIMIT = 15

    def _generate_local_copies_for_selected(self) -> None:
        """Equivalente local de "✨ Gerar copy com IA" — gera copies com a
        chave OpenAI e o perfil de negócio do utilizador (Fase 8) e já cria/
        actualiza os cards correspondentes no Kanban local (Fase 9), sem
        tocar no backend-crm."""
        if not self._selected_leads:
            return

        from app.local_copy import generate_copy_local
        from app.session import upsert_local_lead

        api_key = (self._session.get("openai_api_key") or "").strip()
        profile = self._session.get("local_business_profile") or {}
        has_profile = any((profile.get(k) or "").strip() for k in
                          ("niche", "offer_description", "target_audience", "brand_name"))
        if not api_key:
            self._show_enqueue_toast(
                "Configura a tua chave OpenAI API em ⚙ Conta antes de gerar copies.", ok=False)
            return
        if not has_profile:
            self._show_enqueue_toast(
                "Preenche as tuas informações de negócio antes de gerar copies "
                "(nicho, oferta, público-alvo ou marca).", ok=False)
            return

        all_selected = list(self._selected_leads.values())
        selected = all_selected[:self._LOCAL_COPY_BATCH_LIMIT]
        skipped = len(all_selected) - len(selected)

        self._gen_local_copies_btn.configure(state="disabled", text="A gerar…")

        progress_lbl = ctk.CTkLabel(
            self._results_hdr, text=f"A gerar copies… 0/{len(selected)}",
            font=ctk.CTkFont(size=11), text_color="#9CA3AF",
        )
        progress_lbl.pack(side="left", padx=(12, 0))

        def _update_progress(idx: int, total: int) -> None:
            if self._widget_alive(progress_lbl):
                progress_lbl.configure(text=f"A gerar copies… {idx}/{total}")

        def _worker():
            generated = failed = 0

            for idx, item in enumerate(selected, start=1):
                self.after(0, lambda i=idx, n=len(selected): _update_progress(i, n))

                phone = item.get("phone") or ""
                name = item.get("name") or "Empresa"
                if not phone:
                    failed += 1
                    continue

                try:
                    text = generate_copy_local(
                        self._session, company_name=name, channel="whatsapp",
                        tone="profissional e próximo",
                    )
                    upsert_local_lead(
                        self._session,
                        phone=phone, name=name, category="to-prospect",
                        website=item.get("website", ""), address=item.get("address", ""),
                        customMessage=text,
                    )
                    generated += 1
                except Exception:
                    failed += 1

            def _done():
                try:
                    self._gen_local_copies_btn.configure(state="normal", text="✨ Gerar copies (local)")
                except Exception:
                    pass
                if self._widget_alive(progress_lbl):
                    progress_lbl.destroy()

                parts = []
                if generated:
                    parts.append(f"✓ {generated} copy(s) gerada(s)")
                if failed:
                    parts.append(f"⚠ {failed} falhou" if failed == 1 else f"⚠ {failed} falharam")
                if skipped:
                    parts.append(f"— {skipped} não processado{'s' if skipped != 1 else ''} (limite de {self._LOCAL_COPY_BATCH_LIMIT})")
                summary = "  ".join(parts) or "Nenhuma copy gerada"
                self._show_enqueue_toast(summary, ok=bool(generated))

                kc = getattr(self, "_kanban_content", None)
                if kc and self._widget_alive(kc):
                    self._reload_kanban(kc, is_subscriber(self._session))

            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

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

    # ── Atalho Pesquisar → Assistente IA ─────────────────────────────────────

    def _ir_para_assistente_ia(self) -> None:
        """Navega para Assistente IA e auto-inicia o upload dos resultados actuais."""
        self._switch_panel("assistente-ia")
        # Painel já construído — disparar upload após tk processar eventos pendentes
        self.after(80, self._ai_use_search_results)

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
    # PAINEL 2 — ASSISTENTE IA (upload em lote + geração de copy)
    # ══════════════════════════════════════════════════════════════════════════

    # Estados internos do painel (redefinidos a cada abertura)
    _ai_upload_id: str | None = None
    _ai_columns: list = []
    _ai_column_map: dict = {}
    _ai_mapping_confirmed: bool = False
    _ai_preview_stats: dict = {}
    _ai_preview_rows: list = []

    # Aliases para auto-detecção de colunas
    _COL_ALIASES = {
        "empresa":  ["empresa", "company", "companyname", "company_name", "nome", "name",
                     "razao_social", "razão_social", "negocio", "negócio"],
        "contato":  ["contato", "contact", "contactname", "contact_name", "responsavel",
                     "responsável", "pessoa", "person"],
        "telefone": ["telefone", "phone", "tel", "celular", "whatsapp", "mobile",
                     "fone", "numero", "número"],
        "notas":    ["notas", "notes", "observacao", "observação", "obs", "descricao",
                     "descrição", "description", "sector", "setor", "segmento"],
    }

    def _ai_autodetect(self, columns: list) -> dict:
        """Tenta detectar automaticamente o mapeamento de colunas."""
        mapping: dict = {}
        cols_lower = {c.lower().strip(): c for c in columns}
        for field, aliases in self._COL_ALIASES.items():
            for alias in aliases:
                if alias in cols_lower:
                    mapping[field] = cols_lower[alias]
                    break
        return mapping

    def _build_assistente_ia(self, parent: ctk.CTkFrame) -> None:
        """Painel Assistente IA — fluxo de upload em lote e geração de copy."""
        from app.session import is_subscriber

        # Reinicializa estado do painel
        self._ai_upload_id = None
        self._ai_columns = []
        self._ai_column_map = {}
        self._ai_mapping_confirmed = False
        self._ai_preview_stats = {}
        self._ai_preview_rows = []

        subscriber = is_subscriber(self._session)

        body = ctk.CTkScrollableFrame(parent, fg_color=_BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        hdr.pack(padx=16, pady=(12, 0), fill="x")
        ctk.CTkLabel(hdr, text="✨  Assistente IA",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            hdr,
            text="Importa uma planilha ou usa os resultados da pesquisa actual para gerar copys e criar leads no CRM.",
            font=ctk.CTkFont(size=11), text_color="#9CA3AF", wraplength=520, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        # ── Upsell para não-assinantes ────────────────────────────────────────
        if not subscriber:
            pitch = ctk.CTkFrame(body, fg_color="#1E1B4B", corner_radius=12)
            pitch.pack(padx=16, pady=12, fill="x")
            ctk.CTkLabel(pitch, text="🔒  Disponível para Assinantes",
                         font=ctk.CTkFont(size=13, weight="bold"), text_color="#A5B4FC",
                         ).pack(padx=16, pady=(14, 3))
            ctk.CTkLabel(
                pitch,
                text="Assine para importar planilhas, gerar copys com IA e criar leads automaticamente no CRM.",
                font=ctk.CTkFont(size=10), text_color="#818CF8", wraplength=440,
            ).pack(padx=16, pady=(0, 14))

            self._build_free_copy_generator(body)
            return

        # ── PASSO 1: Escolher fonte ───────────────────────────────────────────
        step1 = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        step1.pack(padx=16, pady=(10, 0), fill="x")

        ctk.CTkLabel(step1, text="Passo 1 — Escolher fonte",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))

        btn_row = ctk.CTkFrame(step1, fg_color="transparent")
        btn_row.pack(padx=16, pady=(0, 10), fill="x")

        self._ai_upload_lbl = ctk.CTkLabel(
            step1, text="", font=ctk.CTkFont(size=11), text_color="#10B981",
        )

        # Referência ao body para que os passos seguintes possam ser construídos
        self._ai_body = body

        ctk.CTkButton(
            btn_row, text="📂  Escolher ficheiro (XLSX / CSV)",
            height=38, corner_radius=8, font=ctk.CTkFont(size=12),
            command=self._ai_pick_file,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="🔄  Gerar copys para leads sem copy",
            height=38, corner_radius=8, fg_color="#374151", hover_color="#4B5563",
            font=ctk.CTkFont(size=12),
            command=self._ai_start_existing_leads_flow,
        ).pack(side="left", padx=(0, 8))

        # Resultados da pesquisa disponíveis — botão discreto como fallback
        # (o caminho principal é o botão "✨ Gerar copy com IA" no painel Pesquisar)
        n_results = len(self._results)
        if n_results:
            ctk.CTkLabel(
                btn_row,
                text=f"  ou  🔍 {n_results} lead{'s' if n_results != 1 else ''} da pesquisa:",
                font=ctk.CTkFont(size=11), text_color="#6B7280",
            ).pack(side="left", padx=(8, 0))
            ctk.CTkButton(
                btn_row,
                text="Usar",
                height=30, corner_radius=6, width=54,
                fg_color="#374151", hover_color="#4B5563",
                font=ctk.CTkFont(size=11),
                command=self._ai_use_search_results,
            ).pack(side="left", padx=(4, 0))

        self._ai_upload_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        # Barra de progresso de upload (oculta inicialmente)
        self._ai_prog_frame = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        self._ai_prog_bar = ctk.CTkProgressBar(self._ai_prog_frame, height=8, corner_radius=4,
                                                mode="indeterminate")
        self._ai_prog_bar.pack(padx=16, pady=(12, 4), fill="x")
        self._ai_prog_lbl = ctk.CTkLabel(self._ai_prog_frame, text="A enviar ficheiro…",
                                          font=ctk.CTkFont(size=11), text_color="#9CA3AF")
        self._ai_prog_lbl.pack(padx=16, pady=(0, 12))

        # Contentor para os passos 2-5 (construídos dinamicamente)
        self._ai_steps_frame = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        self._ai_steps_frame.pack(fill="x", padx=0, pady=0)

    # ── Acções do Passo 1 ─────────────────────────────────────────────────────

    def _ai_pick_file(self) -> None:
        """Abre filedialog para seleccionar CSV/XLSX e envia para o backend."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Escolher planilha",
            filetypes=[
                ("Planilha", "*.xlsx *.csv"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
                ("Todos", "*.*"),
            ],
        )
        if not path:
            return
        import os
        filename = os.path.basename(path)
        self._ai_upload_lbl.configure(text=f"📄  {filename} — a enviar…", text_color="#9CA3AF")
        self._ai_prog_frame.pack(padx=16, pady=(0, 10), fill="x")
        self._ai_prog_bar.start()

        def _worker():
            try:
                from app.crm_client import upload_file
                result = upload_file(self._session, path)
                self.after(0, lambda r=result: self._ai_on_upload_ok(r))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._ai_on_upload_err(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_use_search_results(self) -> None:
        """
        Converte os resultados actuais da Pesquisa num ficheiro CSV temporário
        e envia para o backend — evita ao utilizador ter de exportar/reimportar.
        """
        if not self._results:
            return
        import csv, os, tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False,
            encoding="utf-8-sig", newline="",
        )
        writer = csv.DictWriter(tmp, fieldnames=["empresa", "telefone", "website", "endereco"])
        writer.writeheader()
        for item in self._results:
            writer.writerow({
                "empresa":  item.get("name", ""),
                "telefone": item.get("phone", ""),
                "website":  item.get("website", ""),
                "endereco": item.get("address", ""),
            })
        tmp.close()
        tmp_path = tmp.name

        n = len(self._results)
        self._ai_upload_lbl.configure(
            text=f"🔍  {n} resultados da pesquisa — a converter…", text_color="#9CA3AF",
        )
        self._ai_prog_frame.pack(padx=16, pady=(0, 10), fill="x")
        self._ai_prog_bar.start()

        def _worker():
            try:
                from app.crm_client import upload_file
                result = upload_file(self._session, tmp_path)
                os.unlink(tmp_path)
                self.after(0, lambda r=result: self._ai_on_upload_ok(r))
            except Exception as exc:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                self.after(0, lambda e=str(exc): self._ai_on_upload_err(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_on_upload_ok(self, result: dict) -> None:
        """Upload bem-sucedido: guarda estado e constrói o Passo 2."""
        try:
            self._ai_prog_bar.stop()
            self._ai_prog_frame.pack_forget()
        except Exception:
            pass

        self._ai_upload_id = result.get("upload_id") or result.get("id", "")
        self._ai_columns = result.get("columns") or [
            k for k in (result.get("sample") or [{}])[0].keys()
        ] if result.get("sample") else []

        filename = result.get("filename", "ficheiro")
        self._ai_upload_lbl.configure(
            text=f"✅  {filename} enviado — {len(self._ai_columns)} colunas detectadas",
            text_color="#10B981",
        )

        self._ai_column_map = self._ai_autodetect(self._ai_columns)
        self._ai_mapping_confirmed = False

        # Limpa passos anteriores e constrói Passo 2
        for w in self._ai_steps_frame.winfo_children():
            w.destroy()
        self._ai_build_step2(self._ai_steps_frame)

    def _ai_on_upload_err(self, msg: str) -> None:
        try:
            self._ai_prog_bar.stop()
            self._ai_prog_frame.pack_forget()
        except Exception:
            pass
        self._ai_upload_lbl.configure(
            text=f"⚠  Erro no upload: {msg[:80]}", text_color="#EF4444",
        )

    # ── Fluxo: gerar copys para leads existentes sem copy ─────────────────────

    def _ai_start_existing_leads_flow(self) -> None:
        """Busca leads do Kanban sem copy gerada e mostra selector para os processar."""
        if getattr(self, "_ai_existing_flow_running", False):
            return
        self._ai_existing_flow_running = True

        for w in list(self._ai_steps_frame.winfo_children()):
            w.destroy()

        card = ctk.CTkFrame(self._ai_steps_frame, fg_color=_CARD, corner_radius=12)
        card._ai_step = "existing"
        card.pack(padx=16, pady=(10, 0), fill="x")

        title_lbl = ctk.CTkLabel(
            card, text="🔄  A procurar leads sem copy gerada…",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        title_lbl.pack(anchor="w", padx=16, pady=(14, 4))
        loading_lbl = ctk.CTkLabel(
            card, text="A verificar leads do Kanban — pode demorar alguns segundos…",
            font=ctk.CTkFont(size=10), text_color="#6B7280",
        )
        loading_lbl.pack(anchor="w", padx=16, pady=(0, 14))

        def _worker():
            from app.crm_client import get_leads_kanban
            try:
                leads = get_leads_kanban(self._session)
            except Exception as exc:
                self._ai_existing_flow_running = False
                self.after(0, lambda e=str(exc): self._ai_existing_leads_err(card, loading_lbl, e))
                return

            without_copy = [lead for lead in leads if lead.get("id") is not None and not lead.get("hasMessages")]

            self._ai_existing_flow_running = False
            self.after(0, lambda lst=without_copy: self._ai_build_existing_leads_picker(card, title_lbl, loading_lbl, lst))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_existing_leads_err(self, card: ctk.CTkFrame, loading_lbl, msg: str) -> None:
        if not self._widget_alive(card):
            return
        loading_lbl.configure(
            text=f"⚠  Erro ao carregar leads: {msg[:100]}", text_color="#EF4444",
        )

    def _ai_build_existing_leads_picker(self, card: ctk.CTkFrame, title_lbl, loading_lbl, leads: list) -> None:
        if not self._widget_alive(card):
            return
        loading_lbl.destroy()
        title_lbl.configure(text=f"🔄  Leads sem copy gerada — {len(leads)} encontrado(s)")

        if not leads:
            ctk.CTkLabel(
                card, text="Todos os leads no Kanban já têm copy gerada. 🎉",
                font=ctk.CTkFont(size=11), text_color="#6B7280",
            ).pack(anchor="w", padx=16, pady=(0, 14))
            return

        self._ai_existing_leads = leads
        self._ai_existing_vars: dict = {}

        self._ai_existing_select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            card, text="Seleccionar todos", variable=self._ai_existing_select_all_var,
            font=ctk.CTkFont(size=11), command=self._ai_toggle_all_existing,
        ).pack(anchor="w", padx=16, pady=(0, 4))

        list_frame = ctk.CTkScrollableFrame(card, fg_color="#12121F", corner_radius=8, height=180)
        list_frame.pack(fill="x", padx=16, pady=(0, 10))

        for lead in leads:
            lid = lead.get("id")
            name = (lead.get("companyName") or lead.get("contactName") or "Lead")[:40]
            phone = lead.get("phone") or "—"
            var = ctk.BooleanVar(value=True)
            self._ai_existing_vars[lid] = var
            ctk.CTkCheckBox(
                list_frame, text=f"{name}  ·  {phone}", variable=var,
                font=ctk.CTkFont(size=10),
            ).pack(anchor="w", padx=4, pady=2)

        ctk.CTkLabel(card, text="Canal:", font=ctk.CTkFont(size=11),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(4, 2))
        self._ai_existing_ch_whatsapp = ctk.BooleanVar(value=True)
        self._ai_existing_ch_email = ctk.BooleanVar(value=False)
        self._ai_existing_ch_instagram = ctk.BooleanVar(value=False)
        ch_row = ctk.CTkFrame(card, fg_color="transparent")
        ch_row.pack(anchor="w", padx=16, pady=(0, 8))
        for lbl, var in [("WhatsApp", self._ai_existing_ch_whatsapp),
                          ("Email", self._ai_existing_ch_email),
                          ("Instagram", self._ai_existing_ch_instagram)]:
            ctk.CTkCheckBox(ch_row, text=lbl, variable=var,
                             font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(card, text="Tom de voz:", font=ctk.CTkFont(size=11),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(4, 2))
        self._ai_existing_tone_entry = ctk.CTkEntry(
            card, placeholder_text="ex: profissional e próximo",
            height=34, corner_radius=8, font=ctk.CTkFont(size=11),
        )
        self._ai_existing_tone_entry.insert(0, "profissional e próximo")
        self._ai_existing_tone_entry.pack(padx=16, pady=(0, 10), fill="x")

        self._ai_existing_gen_btn = ctk.CTkButton(
            card, text="✨  Gerar copys para seleccionados",
            height=38, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda c=card: self._ai_generate_copys_for_existing(c),
        )
        self._ai_existing_gen_btn.pack(padx=16, pady=(0, 14))

    def _ai_toggle_all_existing(self) -> None:
        checked = self._ai_existing_select_all_var.get()
        for var in self._ai_existing_vars.values():
            try:
                var.set(checked)
            except Exception:
                pass

    def _ai_generate_copys_for_existing(self, card: ctk.CTkFrame) -> None:
        selected = [lid for lid, var in self._ai_existing_vars.items() if var.get()]
        if not selected:
            return

        channels = []
        if self._ai_existing_ch_whatsapp.get():
            channels.append("whatsapp")
        if self._ai_existing_ch_email.get():
            channels.append("email")
        if self._ai_existing_ch_instagram.get():
            channels.append("instagram")
        channels = channels or ["whatsapp"]

        tone = self._ai_existing_tone_entry.get().strip() or "profissional e próximo"
        leads_by_id = {l.get("id"): l for l in self._ai_existing_leads}

        self._ai_existing_gen_btn.configure(state="disabled", text="A gerar copys…")

        progress_lbl = ctk.CTkLabel(
            card, text=f"A gerar copys… 0/{len(selected)}",
            font=ctk.CTkFont(size=11), text_color="#9CA3AF",
        )
        progress_lbl.pack(padx=16, pady=(0, 14))

        def _worker():
            from app.crm_client import generate_copy, upsert_lead_message
            n_msgs = 0
            n_errors = 0
            generated_ids: list = []

            for idx, lid in enumerate(selected, start=1):
                lead = leads_by_id.get(lid) or {}
                company = lead.get("companyName") or lead.get("contactName") or "Empresa"
                contact = lead.get("contactName") or ""

                self.after(0, lambda i=idx, n=len(selected): self._ai_update_existing_progress(progress_lbl, i, n))

                got_any = False
                for ch in channels:
                    try:
                        body = generate_copy(
                            self._session, company_name=company, sector="",
                            contact_name=contact, channel=ch, tone=tone,
                            custom_prompt_template=self._session.get("local_copy_prompt") or "",
                        )
                        if body:
                            upsert_lead_message(self._session, lid, ch, body)
                            n_msgs += 1
                            got_any = True
                    except Exception:
                        n_errors += 1
                if got_any:
                    generated_ids.append(lid)

            result = {
                "stats": {"leads": len(generated_ids), "messages": n_msgs, "errors": n_errors},
                "lead_ids": generated_ids,
            }
            self.after(0, lambda r=result: self._ai_on_existing_generation_done(card, progress_lbl, r))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_update_existing_progress(self, progress_lbl, idx: int, total: int) -> None:
        if self._widget_alive(progress_lbl):
            progress_lbl.configure(text=f"A gerar copys… {idx}/{total}")

    def _ai_on_existing_generation_done(self, card: ctk.CTkFrame, progress_lbl, result: dict) -> None:
        try:
            self._ai_existing_gen_btn.configure(state="normal", text="✨  Gerar copys para seleccionados")
        except Exception:
            pass
        if self._widget_alive(progress_lbl):
            progress_lbl.destroy()

        stats = result.get("stats") or {}
        done_card = ctk.CTkFrame(card, fg_color="#12121F", corner_radius=10)
        done_card.pack(padx=16, pady=(0, 14), fill="x")

        summary = f"✅  {stats.get('messages', 0)} copy(s) gerada(s) para {stats.get('leads', 0)} lead(s)"
        if stats.get("errors"):
            summary += f"   ·   ⚠ {stats['errors']} erro(s)"
        ctk.CTkLabel(
            done_card, text=summary,
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981",
        ).pack(anchor="w", padx=14, pady=(12, 8))

        lead_ids = result.get("lead_ids") or []
        if lead_ids:
            self._ai_load_messages_preview(done_card, lead_ids)

    # ── Passo 2 — Mapeamento de colunas ──────────────────────────────────────

    def _ai_build_step2(self, parent: ctk.CTkFrame) -> None:
        """Passo 2 — Dropdowns de mapeamento de colunas com auto-detecção."""
        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=12)
        card.pack(padx=16, pady=(10, 0), fill="x")

        ctk.CTkLabel(card, text="Passo 2 — Mapeamento de colunas",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            card,
            text="Indica qual coluna da planilha corresponde a cada campo. Usa '(nenhum)' se o campo não existir.",
            font=ctk.CTkFont(size=10), text_color="#9CA3AF", wraplength=500,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        options = ["(nenhum)"] + self._ai_columns
        fields = [
            ("empresa",  "Empresa / Nome"),
            ("contato",  "Contacto / Pessoa"),
            ("telefone", "Telefone"),
            ("notas",    "Notas / Sector"),
        ]

        self._ai_map_vars: dict[str, ctk.StringVar] = {}

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(padx=16, pady=(0, 8), fill="x")

        for row_idx, (field, label) in enumerate(fields):
            ctk.CTkLabel(grid, text=label, font=ctk.CTkFont(size=11),
                         width=130, anchor="w").grid(row=row_idx, column=0, sticky="w", pady=3)
            current = self._ai_column_map.get(field, "(nenhum)")
            if current not in options:
                current = "(nenhum)"
            var = ctk.StringVar(value=current)
            self._ai_map_vars[field] = var
            ctk.CTkOptionMenu(
                grid, values=options, variable=var,
                width=220, height=32, corner_radius=6,
                command=lambda val, f=field: self._ai_map_vars[f].set(val),
            ).grid(row=row_idx, column=1, sticky="w", padx=(8, 0), pady=3)

        # Opção de duplicados
        ctk.CTkLabel(card, text="Duplicados:", font=ctk.CTkFont(size=11),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(4, 2))

        ow_row = ctk.CTkFrame(card, fg_color="transparent")
        ow_row.pack(anchor="w", padx=16, pady=(0, 10))
        self._ai_overwrite_var = ctk.StringVar(value="skip")
        for val, lbl in [("skip", "Pular"), ("update", "Actualizar"), ("duplicate", "Criar mesmo assim")]:
            ctk.CTkRadioButton(
                ow_row, text=lbl, variable=self._ai_overwrite_var, value=val,
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            card, text="✓  Confirmar mapeamento →",
            height=36, corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda p=parent: self._ai_confirm_mapping(p),
        ).pack(padx=16, pady=(0, 14))

    def _ai_confirm_mapping(self, parent: ctk.CTkFrame) -> None:
        """Guarda o mapeamento confirmado e constrói o Passo 3 (preview)."""
        self._ai_column_map = {
            field: var.get()
            for field, var in self._ai_map_vars.items()
            if var.get() != "(nenhum)"
        }
        self._ai_mapping_confirmed = True
        self._ai_build_step3(parent)

    # ── Passo 3 — Preview / Dedupe ────────────────────────────────────────────

    def _ai_build_step3(self, parent: ctk.CTkFrame) -> None:
        """Passo 3 — Gera prévia de dedupe e mostra stats + amostra de linhas."""
        # Remove preview anterior se existir
        for w in list(parent.winfo_children()):
            if getattr(w, "_ai_step", None) in (3, 4, 5):
                w.destroy()

        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=12)
        card._ai_step = 3
        card.pack(padx=16, pady=(10, 0), fill="x")

        ctk.CTkLabel(card, text="Passo 3 — Prévia",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))

        prog = ctk.CTkProgressBar(card, height=6, corner_radius=3, mode="indeterminate")
        prog.pack(padx=16, pady=(0, 4), fill="x")
        prog.start()
        prog_lbl = ctk.CTkLabel(card, text="A analisar duplicados…",
                                 font=ctk.CTkFont(size=11), text_color="#9CA3AF")
        prog_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        def _worker():
            try:
                from app.crm_client import preview_assistente_ia
                result = preview_assistente_ia(
                    self._session,
                    self._ai_upload_id,
                    self._ai_overwrite_var.get(),
                    self._ai_column_map,
                )
                self.after(0, lambda r=result: self._ai_on_preview_ok(card, prog, prog_lbl, parent, r))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._ai_on_preview_err(prog, prog_lbl, e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_on_preview_ok(
        self,
        card: ctk.CTkFrame,
        prog: ctk.CTkProgressBar,
        prog_lbl: ctk.CTkLabel,
        parent: ctk.CTkFrame,
        result: dict,
    ) -> None:
        try:
            prog.stop()
            prog.pack_forget()
            prog_lbl.pack_forget()
        except Exception:
            pass

        self._ai_preview_stats = result.get("stats") or {}
        self._ai_preview_rows = result.get("rows") or []

        stats = self._ai_preview_stats
        stat_items = [
            ("Total",         stats.get("total", 0),       "#9CA3AF"),
            ("Criar",         stats.get("pred_create", 0), "#10B981"),
            ("Actualizar",    stats.get("pred_update", 0), "#F59E0B"),
            ("Pular",         stats.get("pred_skip", 0),   "#6B7280"),
        ]

        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(padx=16, pady=(4, 8), fill="x")
        for label, val, color in stat_items:
            box = ctk.CTkFrame(stats_row, fg_color="#12121F", corner_radius=8)
            box.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(box, text=str(val), font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=color).pack(padx=12, pady=(6, 1))
            ctk.CTkLabel(box, text=label, font=ctk.CTkFont(size=9),
                         text_color="#6B7280").pack(padx=12, pady=(0, 6))

        # Tabela de amostra (10 linhas)
        if self._ai_preview_rows:
            ctk.CTkLabel(card, text="Amostra (primeiras 10 linhas):",
                         font=ctk.CTkFont(size=10), text_color="#6B7280").pack(anchor="w", padx=16, pady=(0, 4))

            tbl = ctk.CTkScrollableFrame(card, fg_color="transparent", height=180)
            tbl.pack(padx=16, pady=(0, 8), fill="x")

            hdr_row = ctk.CTkFrame(tbl, fg_color="transparent")
            hdr_row.pack(fill="x", pady=(0, 2))
            for col_lbl, w in [("Empresa", 180), ("Telefone", 110), ("Acção", 80), ("Dup?", 60)]:
                ctk.CTkLabel(hdr_row, text=col_lbl, font=ctk.CTkFont(size=9, weight="bold"),
                             text_color="#9CA3AF", width=w, anchor="w").pack(side="left", padx=2)

            for idx, row in enumerate(self._ai_preview_rows[:10]):
                action = row.get("pred_action", "?")
                dup_flags = []
                if row.get("dup_phone"):
                    dup_flags.append("☎")
                if row.get("dup_email"):
                    dup_flags.append("✉")
                if row.get("dup_name"):
                    dup_flags.append("Aa")
                action_color = {"create": "#10B981", "update": "#F59E0B", "skip": "#6B7280"}.get(action, "#9CA3AF")

                r = ctk.CTkFrame(tbl, fg_color="#1A1A2E" if idx % 2 == 0 else "#16162A", corner_radius=4)
                r.pack(fill="x", pady=1)
                empresa = str(row.get("company") or row.get("empresa") or "—")[:28]
                phone   = str(row.get("phone") or row.get("telefone") or "—")[:14]
                for val, w, tc in [
                    (empresa, 180, "#D1D5DB"),
                    (phone, 110, "#9CA3AF"),
                    (action, 80, action_color),
                    (" ".join(dup_flags) or "—", 60, "#EF4444" if dup_flags else "#4B5563"),
                ]:
                    ctk.CTkLabel(r, text=val, font=ctk.CTkFont(size=10),
                                 text_color=tc, width=w, anchor="w").pack(side="left", padx=(4, 2), pady=4)

        # Botão para avançar para Passo 4
        ctk.CTkButton(
            card, text="⚙  Configurar e processar →",
            height=36, corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda p=parent: self._ai_build_step4(p),
        ).pack(padx=16, pady=(4, 14))

    def _ai_on_preview_err(
        self, prog: ctk.CTkProgressBar, prog_lbl: ctk.CTkLabel, msg: str,
    ) -> None:
        try:
            prog.stop()
            prog.pack_forget()
        except Exception:
            pass
        prog_lbl.configure(text=f"⚠  Erro na prévia: {msg[:80]}", text_color="#EF4444")

    # ── Passo 4 — Opções + Processamento ─────────────────────────────────────

    def _ai_build_step4(self, parent: ctk.CTkFrame) -> None:
        """Passo 4 — Opções de processamento (criar cards, gerar copys, canais, tom)."""
        # Remove passos 4-5 anteriores se existirem
        for w in list(parent.winfo_children()):
            if getattr(w, "_ai_step", None) in (4, 5):
                w.destroy()

        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=12)
        card._ai_step = 4
        card.pack(padx=16, pady=(10, 0), fill="x")

        ctk.CTkLabel(card, text="Passo 4 — Opções de processamento",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(12, 8))

        # Checkboxes principais
        self._ai_create_cards_var = ctk.BooleanVar(value=True)
        self._ai_generate_copys_var = ctk.BooleanVar(value=False)

        chk_row = ctk.CTkFrame(card, fg_color="transparent")
        chk_row.pack(anchor="w", padx=16, pady=(0, 8))
        ctk.CTkCheckBox(chk_row, text="Criar cards no CRM",
                        variable=self._ai_create_cards_var,
                        font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 16))
        ctk.CTkCheckBox(chk_row, text="Gerar copys com IA",
                        variable=self._ai_generate_copys_var,
                        font=ctk.CTkFont(size=11)).pack(side="left")

        # Canais (WhatsApp, Email, Instagram)
        ctk.CTkLabel(card, text="Canais:", font=ctk.CTkFont(size=11),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(4, 2))
        self._ai_ch_whatsapp = ctk.BooleanVar(value=True)
        self._ai_ch_email = ctk.BooleanVar(value=False)
        self._ai_ch_instagram = ctk.BooleanVar(value=False)
        ch_row = ctk.CTkFrame(card, fg_color="transparent")
        ch_row.pack(anchor="w", padx=16, pady=(0, 8))
        for lbl, var in [("WhatsApp", self._ai_ch_whatsapp),
                          ("Email", self._ai_ch_email),
                          ("Instagram", self._ai_ch_instagram)]:
            ctk.CTkCheckBox(ch_row, text=lbl, variable=var,
                             font=ctk.CTkFont(size=11),
                             command=self._ai_sync_generate_copys_with_channels).pack(side="left", padx=(0, 12))

        # Tom de voz
        ctk.CTkLabel(card, text="Tom de voz:", font=ctk.CTkFont(size=11),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(4, 2))
        self._ai_tone_entry = ctk.CTkEntry(card, placeholder_text="ex: profissional e próximo",
                                            height=34, corner_radius=8, font=ctk.CTkFont(size=11))
        self._ai_tone_entry.insert(0, "profissional e próximo")
        self._ai_tone_entry.pack(padx=16, pady=(0, 6), fill="x")

        # Idioma
        ctk.CTkLabel(card, text="Idioma:", font=ctk.CTkFont(size=11),
                     text_color="#9CA3AF").pack(anchor="w", padx=16, pady=(4, 2))
        self._ai_lang_entry = ctk.CTkEntry(card, placeholder_text="pt-PT",
                                            height=34, corner_radius=8, font=ctk.CTkFont(size=11),
                                            width=120)
        self._ai_lang_entry.insert(0, "pt-PT")
        self._ai_lang_entry.pack(anchor="w", padx=16, pady=(0, 10))

        # Botão processar
        self._ai_process_btn = ctk.CTkButton(
            card, text="🚀  Confirmar e Processar",
            height=38, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda p=parent: self._ai_start_processing(p),
        )
        self._ai_process_btn.pack(padx=16, pady=(0, 14))

    def _ai_sync_generate_copys_with_channels(self) -> None:
        """Marcar qualquer canal liga automaticamente 'Gerar copys com IA' — evita
        que o utilizador seleccione um canal sem activar a geração propriamente dita."""
        any_channel = (
            self._ai_ch_whatsapp.get()
            or self._ai_ch_email.get()
            or self._ai_ch_instagram.get()
        )
        if any_channel:
            self._ai_generate_copys_var.set(True)

    def _ai_start_processing(self, parent: ctk.CTkFrame) -> None:
        """Recolhe opções e executa POST /assistente-ia/processar."""
        channels = []
        if self._ai_ch_whatsapp.get():
            channels.append("whatsapp")
        if self._ai_ch_email.get():
            channels.append("email")
        if self._ai_ch_instagram.get():
            channels.append("instagram")

        self._ai_process_btn.configure(state="disabled", text="A processar…")

        def _worker():
            try:
                from app.crm_client import processar_assistente_ia
                result = processar_assistente_ia(
                    self._session,
                    self._ai_upload_id,
                    create_cards=self._ai_create_cards_var.get(),
                    generate_copys=self._ai_generate_copys_var.get(),
                    channels=channels or ["whatsapp"],
                    overwrite=self._ai_overwrite_var.get(),
                    tone=self._ai_tone_entry.get().strip() or "profissional e próximo",
                    language=self._ai_lang_entry.get().strip() or "pt-PT",
                    column_map=self._ai_column_map,
                    custom_prompt_template=self._session.get("local_copy_prompt") or "",
                )
                self.after(0, lambda r=result: self._ai_on_process_ok(parent, r))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._ai_on_process_err(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_on_process_err(self, msg: str) -> None:
        try:
            self._ai_process_btn.configure(state="normal", text="🚀  Confirmar e Processar")
        except Exception:
            pass
        popup = ctk.CTkToplevel(self)
        popup.title("Erro")
        popup.geometry("380x130")
        popup.grab_set()
        ctk.CTkLabel(popup, text=f"⚠  Erro: {msg[:100]}", text_color="#EF4444",
                     font=ctk.CTkFont(size=12), wraplength=340).pack(pady=(24, 10))
        ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack()

    def _ai_on_process_ok(self, parent: ctk.CTkFrame, result: dict) -> None:
        """Processamento concluído — mostra Passo 5 com resultados."""
        try:
            self._ai_process_btn.configure(state="normal", text="🚀  Confirmar e Processar")
        except Exception:
            pass
        self._ai_build_step5(parent, result)

    # ── Passo 5 — Resultados ──────────────────────────────────────────────────

    def _ai_build_step5(self, parent: ctk.CTkFrame, result: dict) -> None:
        """Passo 5 — Exibe estatísticas finais e botão 'Ver no Prospectar'."""
        for w in list(parent.winfo_children()):
            if getattr(w, "_ai_step", None) == 5:
                w.destroy()

        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=12)
        card._ai_step = 5
        card.pack(padx=16, pady=(10, 0), fill="x")

        ctk.CTkLabel(card, text="✅  Processamento concluído",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981",
                     ).pack(anchor="w", padx=16, pady=(14, 8))

        stats = result.get("stats") or {}
        stat_items = [
            ("Criados",     stats.get("created", 0),  "#10B981"),
            ("Actualizados", stats.get("updated", 0), "#F59E0B"),
            ("Pulados",     stats.get("skipped", 0),  "#6B7280"),
            ("Mensagens",   stats.get("messages", 0), "#818CF8"),
        ]
        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(padx=16, pady=(0, 10), fill="x")
        for label, val, color in stat_items:
            box = ctk.CTkFrame(stats_row, fg_color="#12121F", corner_radius=8)
            box.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(box, text=str(val), font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=color).pack(padx=14, pady=(6, 1))
            ctk.CTkLabel(box, text=label, font=ctk.CTkFont(size=9),
                         text_color="#6B7280").pack(padx=14, pady=(0, 6))

        errors = result.get("errors") or []
        if errors:
            ctk.CTkLabel(card, text=f"⚠  {len(errors)} erro(s):",
                         font=ctk.CTkFont(size=10), text_color="#F59E0B").pack(anchor="w", padx=16)
            for err in errors[:5]:
                ctk.CTkLabel(card, text=f"  • {str(err)[:80]}",
                             font=ctk.CTkFont(size=9), text_color="#6B7280").pack(anchor="w", padx=16, pady=1)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(padx=16, pady=(8, 14), fill="x")
        ctk.CTkButton(
            btn_row, text="📱  Ver no Prospectar",
            height=36, corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_panel("prospectar"),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="↺  Nova importação",
            height=36, corner_radius=8, fg_color="#374151", hover_color="#4B5563",
            font=ctk.CTkFont(size=11),
            command=lambda: self._switch_panel("assistente-ia"),
        ).pack(side="left")

        lead_ids = result.get("lead_ids") or []
        if lead_ids:
            self._ai_load_messages_preview(card, lead_ids)

    def _ai_load_messages_preview(self, card: ctk.CTkFrame, lead_ids: list) -> None:
        """Busca e mostra as copys geradas para os leads processados (assíncrono)."""
        preview_card = ctk.CTkFrame(card, fg_color="#12121F", corner_radius=10)
        preview_card._ai_step = 5
        preview_card.pack(padx=16, pady=(0, 14), fill="x")

        ctk.CTkLabel(
            preview_card, text="✨  Mensagens geradas — prévia",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 2))

        loading_lbl = ctk.CTkLabel(
            preview_card, text="A carregar mensagens…",
            font=ctk.CTkFont(size=11), text_color="#6B7280",
        )
        loading_lbl.pack(anchor="w", padx=14, pady=(0, 12))

        def _worker():
            from app.crm_client import get_lead_messages
            entries = []
            for lid in lead_ids[:30]:
                try:
                    msgs = get_lead_messages(self._session, lid)
                except Exception:
                    msgs = []
                for m in msgs:
                    entries.append((lid, m))
            self.after(0, lambda e=entries: self._ai_render_messages_preview(preview_card, loading_lbl, e))

        threading.Thread(target=_worker, daemon=True).start()

    def _ai_render_messages_preview(self, preview_card: ctk.CTkFrame, loading_lbl, entries: list) -> None:
        if not self._widget_alive(preview_card):
            return
        loading_lbl.destroy()

        if not entries:
            ctk.CTkLabel(
                preview_card, text="Nenhuma mensagem encontrada para os leads processados.",
                font=ctk.CTkFont(size=11), text_color="#6B7280",
            ).pack(anchor="w", padx=14, pady=(0, 12))
            return

        scroll = ctk.CTkScrollableFrame(preview_card, fg_color="transparent", height=260)
        scroll.pack(fill="x", padx=10, pady=(0, 12))

        _channel_labels = {"whatsapp": "WhatsApp", "email": "Email", "instagram": "Instagram"}

        for lead_id, msg in entries[:30]:
            row = ctk.CTkFrame(scroll, fg_color=_CARD, corner_radius=8)
            row.pack(fill="x", padx=4, pady=3)

            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(8, 2))
            channel_label = _channel_labels.get(msg.get("channel"), msg.get("channel") or "—")
            ctk.CTkLabel(
                hdr, text=f"Lead #{lead_id} · {channel_label}",
                font=ctk.CTkFont(size=10, weight="bold"), text_color="#818CF8",
            ).pack(side="left")
            ctk.CTkButton(
                hdr, text="📋 Copiar", width=70, height=22, corner_radius=6,
                fg_color="#374151", hover_color="#4B5563", font=ctk.CTkFont(size=9),
                command=lambda b=msg.get("body") or "": self._copy_text_to_clipboard(b),
            ).pack(side="right")

            body = (msg.get("body") or "").strip()
            ctk.CTkLabel(
                row, text=body[:280] + ("…" if len(body) > 280 else ""),
                font=ctk.CTkFont(size=10), text_color="#D1D5DB",
                anchor="w", justify="left", wraplength=620,
            ).pack(fill="x", padx=10, pady=(0, 8))

    # ── Gerador de copy local (modo gratuito, chave OpenAI própria) ──────────
    def _build_free_copy_generator(self, body: ctk.CTkFrame) -> None:
        from app.session import save_session
        from app.ui.business_profile_screen import BusinessProfileScreen

        card = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        card.pack(padx=16, pady=(0, 16), fill="x")

        ctk.CTkLabel(card, text="✨  Gerador de copy (modo gratuito)",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            card,
            text="Gera mensagens de prospecção com a tua própria chave OpenAI — sem precisar de assinatura.",
            font=ctk.CTkFont(size=11), text_color="#9CA3AF", wraplength=520, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # ── Indicadores de estado ────────────────────────────────────────────
        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(anchor="w", padx=16, pady=(0, 10), fill="x")

        key_lbl = ctk.CTkLabel(status_row, text="", font=ctk.CTkFont(size=11))
        key_lbl.pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            status_row, text="Configurar em ⚙ Conta", height=26, width=140,
            corner_radius=6, fg_color="#374151", hover_color="#4B5563",
            font=ctk.CTkFont(size=10), command=lambda: self._switch_panel("conta"),
        ).pack(side="left", padx=(0, 16))

        profile_lbl = ctk.CTkLabel(status_row, text="", font=ctk.CTkFont(size=11))
        profile_lbl.pack(side="left", padx=(0, 6))

        def _refresh_status():
            has_key = bool((self._session.get("openai_api_key") or "").strip())
            key_lbl.configure(
                text="🔑 Chave OpenAI: configurada" if has_key else "🔑 Chave OpenAI: não configurada",
                text_color="#10B981" if has_key else "#F59E0B",
            )
            profile = self._session.get("local_business_profile") or {}
            has_profile = any((profile.get(k) or "").strip() for k in
                              ("niche", "offer_description", "target_audience", "brand_name"))
            profile_lbl.configure(
                text="📋 Perfil de negócio: preenchido" if has_profile else "📋 Perfil de negócio: por preencher",
                text_color="#10B981" if has_profile else "#F59E0B",
            )

        def _open_business_profile():
            def _on_save(_profile):
                save_session(self._session)
                _refresh_status()
            BusinessProfileScreen(self, self._session, on_save=_on_save)

        ctk.CTkButton(
            status_row, text="Preencher informações de negócio", height=26, width=190,
            corner_radius=6, fg_color="#374151", hover_color="#4B5563",
            font=ctk.CTkFont(size=10), command=_open_business_profile,
        ).pack(side="left")

        _refresh_status()

        # ── Formulário do lead avulso ────────────────────────────────────────
        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(padx=16, pady=(0, 6), fill="x")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        company_entry = ctk.CTkEntry(form, placeholder_text="Nome da empresa do lead", height=36, corner_radius=8)
        company_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)

        sector_entry = ctk.CTkEntry(form, placeholder_text="Sector (opcional)", height=36, corner_radius=8)
        sector_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=4)

        contact_entry = ctk.CTkEntry(form, placeholder_text="Nome do contacto (opcional)", height=36, corner_radius=8)
        contact_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=4)

        channel_combo = ctk.CTkComboBox(
            form, values=["whatsapp", "email", "instagram", "call"],
            height=36, corner_radius=8,
        )
        channel_combo.set("whatsapp")
        channel_combo.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=4)

        tone_entry = ctk.CTkEntry(form, placeholder_text="Tom (ex.: profissional e próximo)", height=36, corner_radius=8)
        tone_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

        gen_btn = ctk.CTkButton(card, text="✨  Gerar copy", height=38, corner_radius=8,
                                font=ctk.CTkFont(size=12))
        gen_btn.pack(anchor="w", padx=16, pady=(6, 6))

        msg_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=11),
                               text_color="#F59E0B", wraplength=520, justify="left")
        msg_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        result_frame = ctk.CTkFrame(card, fg_color="#111827", corner_radius=10)
        result_lbl = ctk.CTkLabel(result_frame, text="", font=ctk.CTkFont(size=11),
                                  text_color="#D1D5DB", wraplength=520, justify="left", anchor="w")
        result_lbl.pack(fill="x", padx=12, pady=(10, 4))
        copy_btn = ctk.CTkButton(
            result_frame, text="📋 Copiar", width=80, height=26, corner_radius=6,
            fg_color="#374151", hover_color="#4B5563", font=ctk.CTkFont(size=10),
            command=lambda: self._copy_text_to_clipboard(result_lbl.cget("text")),
        )
        copy_btn.pack(anchor="e", padx=12, pady=(0, 10))

        def _on_done(text: Optional[str], error: Optional[str]) -> None:
            gen_btn.configure(state="normal", text="✨  Gerar copy")
            if error:
                msg_lbl.configure(text=error)
                result_frame.pack_forget()
                return
            msg_lbl.configure(text="")
            result_lbl.configure(text=text or "")
            result_frame.pack(padx=16, pady=(0, 14), fill="x")

        def _generate():
            from app.local_copy import generate_copy_local, LocalCopyError

            company = company_entry.get().strip()
            if not company:
                msg_lbl.configure(text="Indica o nome da empresa do lead.")
                return

            msg_lbl.configure(text="")
            result_frame.pack_forget()
            gen_btn.configure(state="disabled", text="A gerar…")

            sector = sector_entry.get().strip()
            contact = contact_entry.get().strip()
            channel = channel_combo.get().strip() or "whatsapp"
            tone = tone_entry.get().strip() or "profissional e próximo"

            def _worker():
                try:
                    text = generate_copy_local(
                        self._session, company_name=company, sector=sector,
                        contact_name=contact, channel=channel, tone=tone,
                    )
                    self.after(0, lambda: _on_done(text, None))
                except LocalCopyError as exc:
                    msg = str(exc)
                    self.after(0, lambda m=msg: _on_done(None, m))
                except Exception as exc:
                    msg = f"Erro ao gerar mensagem: {exc}"
                    self.after(0, lambda m=msg: _on_done(None, m))

            threading.Thread(target=_worker, daemon=True).start()

        gen_btn.configure(command=_generate)

    def _copy_text_to_clipboard(self, text: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # PAINEL 3 — PROSPECTAR (Kanban de prospecção)
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

        # Badges de estado (agente + pendentes) — só fazem sentido com fila/agente remoto (CRM)
        self._agent_badge_lbl = ctk.CTkLabel(
            hdr, text="● Agente: —",
            font=ctk.CTkFont(size=10), text_color="#6B7280",
            fg_color="#2A2A3E", corner_radius=6, padx=8, pady=2,
        )
        self._pending_badge_lbl = ctk.CTkLabel(
            hdr, text="Pendentes: —",
            font=ctk.CTkFont(size=10), text_color="#6B7280",
            fg_color="#2A2A3E", corner_radius=6, padx=8, pady=2,
        )
        if subscriber:
            self._agent_badge_lbl.pack(side="right", padx=4, pady=14)
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

        self._bulk_channel_var = ctk.StringVar(value="whatsapp")
        for val, lbl in [("whatsapp", "WhatsApp"), ("email", "Email")]:
            ctk.CTkRadioButton(self._bulk_bar, text=lbl, variable=self._bulk_channel_var, value=val,
                               font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8), pady=8)

        ctk.CTkButton(
            self._bulk_bar, text="📤 Enfileirar", height=28, corner_radius=6,
            fg_color="#1D4ED8", hover_color="#1E40AF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._enqueue_selected_leads if subscriber else self._send_selected_local_leads,
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
        self._kanban_card_vars = {}

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

            if cat_id == "to-prospect" and col_leads:
                self._kanban_col_select_all_var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(
                    hdr_f, text="", variable=self._kanban_col_select_all_var,
                    width=20, height=20, checkbox_width=16, checkbox_height=16,
                    fg_color="white", checkmark_color=col_color, border_color="white",
                    hover_color="#E5E7EB",
                    command=lambda ls=col_leads: self._toggle_all_kanban(ls),
                ).pack(side="left", padx=(8, 0))
                ctk.CTkLabel(
                    hdr_f,
                    text=f"{cat_label}  ({len(col_leads)})",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="white",
                ).pack(side="left", padx=4, expand=True)
            else:
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
        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=8, cursor="hand2")
        card.pack(fill="x", padx=4, pady=3)

        name = (lead.get("companyName") or lead.get("contactName") or "Lead")[:26]
        phone = lead.get("phone") or "—"
        lead_id = lead.get("id")
        origin = lead.get("origin") or ""

        if lead_id is not None:
            card.bind("<Button-1>", lambda _e, l=lead: self._show_lead_detail(l))

        # Linha de topo: nome + checkbox (só em to-prospect)
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=8, pady=(6, 1))

        name_lbl = ctk.CTkLabel(
            top_row, text=name,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
        )
        name_lbl.pack(side="left", fill="x", expand=True)
        if lead_id is not None:
            name_lbl.bind("<Button-1>", lambda _e, l=lead: self._show_lead_detail(l))

        if current_cat == "to-prospect" and lead_id is not None:
            var = ctk.BooleanVar(value=lead_id in self._kanban_selected)
            self._kanban_card_vars[lead_id] = var
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
            origin_lbl = ctk.CTkLabel(
                card, text=f"#{lead_id} · {origin}",
                font=ctk.CTkFont(size=9), text_color="#374151", anchor="w",
            )
            origin_lbl.pack(fill="x", padx=8, pady=(0, 6))
            if lead_id is not None:
                origin_lbl.bind("<Button-1>", lambda _e, l=lead: self._show_lead_detail(l))

    # ── Detalhe do lead (modal com mensagens geradas) ──────────────────────────

    def _show_lead_detail(self, lead: dict) -> None:
        """Abre modal com dados do lead e prévia das copys geradas (editável)."""
        lead_id = lead.get("id")
        if lead_id is None:
            return

        popup = ctk.CTkToplevel(self)
        popup.title(f"Lead #{lead_id}")
        popup.geometry("520x520")
        popup.resizable(True, True)
        popup.grab_set()
        popup.focus()

        name = lead.get("companyName") or lead.get("contactName") or "Lead"
        phone = lead.get("phone") or "—"
        origin = lead.get("origin") or "—"

        hdr = ctk.CTkFrame(popup, fg_color="#1E1E2E", corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text=name, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(10, 0))
        ctk.CTkLabel(
            hdr, text=f"📞 {phone}   ·   origem: {origin}   ·   #{lead_id}",
            font=ctk.CTkFont(size=10), text_color="#9CA3AF",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            popup, text="Mensagens geradas",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 4))

        body_frame = ctk.CTkScrollableFrame(popup, fg_color="#12121F", corner_radius=8)
        body_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        loading_lbl = ctk.CTkLabel(
            body_frame, text="A carregar…",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        )
        loading_lbl.pack(pady=20)

        footer = ctk.CTkFrame(popup, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=8)
        ctk.CTkButton(footer, text="Fechar", width=100, command=popup.destroy).pack()

        def _worker():
            try:
                from app.crm_client import get_lead_messages
                msgs = get_lead_messages(self._session, lead_id)
            except Exception:
                msgs = []
            self.after(0, lambda m=msgs: self._render_lead_detail_messages(body_frame, loading_lbl, lead_id, m))

        threading.Thread(target=_worker, daemon=True).start()

    def _render_lead_detail_messages(self, body_frame, loading_lbl, lead_id: int, msgs: list) -> None:
        if not self._widget_alive(body_frame):
            return
        loading_lbl.destroy()

        if not msgs:
            ctk.CTkLabel(
                body_frame,
                text="Sem mensagens geradas para este lead.\nGera copys via Assistente IA ou no painel Pesquisar.",
                font=ctk.CTkFont(size=11), text_color="#6B7280", justify="left",
            ).pack(pady=20, padx=12)
            return

        _channel_labels = {"whatsapp": "WhatsApp", "email": "Email", "instagram": "Instagram"}

        for msg in msgs:
            row = ctk.CTkFrame(body_frame, fg_color=_CARD, corner_radius=8)
            row.pack(fill="x", padx=6, pady=4)

            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(8, 2))
            channel_label = _channel_labels.get(msg.get("channel"), msg.get("channel") or "—")
            ctk.CTkLabel(
                hdr, text=f"📨 {channel_label}",
                font=ctk.CTkFont(size=11, weight="bold"), text_color="#818CF8",
            ).pack(side="left")
            ctk.CTkButton(
                hdr, text="📋 Copiar", width=78, height=24, corner_radius=6,
                fg_color="#374151", hover_color="#4B5563", font=ctk.CTkFont(size=10),
                command=lambda b=msg.get("body") or "": self._copy_text_to_clipboard(b),
            ).pack(side="right")

            body_box = ctk.CTkTextbox(row, height=110, corner_radius=6, font=ctk.CTkFont(size=11))
            body_box.pack(fill="x", padx=10, pady=(0, 6))
            body_box.insert("1.0", (msg.get("body") or "").strip())

            ctk.CTkButton(
                row, text="💾 Guardar alteração", width=140, height=26, corner_radius=6,
                fg_color="#1D4ED8", hover_color="#1E40AF", font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda mid=msg.get("id"), ch=msg.get("channel"), box=body_box:
                    self._save_lead_message(lead_id, mid, ch, box),
            ).pack(anchor="e", padx=10, pady=(0, 8))

    def _save_lead_message(self, lead_id: int, message_id, channel: str, box) -> None:
        new_body = box.get("1.0", "end").strip()
        if not new_body:
            return

        def _worker():
            try:
                from app.crm_client import upsert_lead_message
                upsert_lead_message(self._session, lead_id, channel, new_body, message_id=message_id)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # ── Selecção Kanban ────────────────────────────────────────────────────────

    def _on_kanban_check(self, lead_id: int, var: ctk.BooleanVar) -> None:
        if var.get():
            self._kanban_selected[lead_id] = lead_id
        else:
            self._kanban_selected.pop(lead_id, None)
        self._refresh_bulk_bar()
        self._sync_select_all_var()

    def _toggle_all_kanban(self, col_leads: list) -> None:
        """Selecciona/deselecciona todos os leads de 'À Prospectar' de uma vez."""
        select = getattr(self, "_kanban_col_select_all_var", None)
        if select is None:
            return
        checked = select.get()
        for lead in col_leads:
            lid = lead.get("id")
            if lid is None:
                continue
            if checked:
                self._kanban_selected[lid] = lid
            else:
                self._kanban_selected.pop(lid, None)
            card_var = self._kanban_card_vars.get(lid)
            if card_var is not None:
                try:
                    card_var.set(checked)
                except Exception:
                    pass
        self._refresh_bulk_bar()

    def _sync_select_all_var(self) -> None:
        """Mantém o checkbox de 'seleccionar todos' em sincronia com os cards individuais."""
        select = getattr(self, "_kanban_col_select_all_var", None)
        if select is None or not self._kanban_card_vars:
            return
        try:
            all_selected = all(lid in self._kanban_selected for lid in self._kanban_card_vars)
            select.set(all_selected)
        except Exception:
            pass

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
        select = getattr(self, "_kanban_col_select_all_var", None)
        if select is not None:
            try:
                select.set(False)
            except Exception:
                pass
        for var in self._kanban_card_vars.values():
            try:
                var.set(False)
            except Exception:
                pass
        self._refresh_bulk_bar()

    def _enqueue_selected_leads(self) -> None:
        lead_ids = list(self._kanban_selected.keys())
        if not lead_ids:
            return
        msg = self._bulk_msg_entry.get().strip() if hasattr(self, "_bulk_msg_entry") else ""
        channel = self._bulk_channel_var.get() if hasattr(self, "_bulk_channel_var") else "whatsapp"

        # Feedback visual imediato
        if hasattr(self, "_bulk_msg_entry"):
            self._bulk_msg_entry.configure(state="disabled")

        def _do():
            try:
                from app.crm_client import enqueue_whatsapp, enqueue_email, move_lead_category
                if channel == "email":
                    result = enqueue_email(self._session, lead_ids, message=msg or None)
                else:
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
                        if status == "completed":
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
        """Kanban local para não-assinantes — espelha o pipeline de assinante,
        mas alimentado por `session["local_leads"]` e movido mecanicamente
        consoante o resultado real do envio (sem CRM/polling remoto)."""
        from app.session import get_local_leads
        self._render_local_kanban(container, get_local_leads(self._session))

    def _render_local_kanban(self, container: ctk.CTkFrame, leads: list) -> None:
        """Renderiza as 3 colunas do Kanban local (mesma estrutura visual do remoto)."""
        if not self._widget_alive(container):
            return
        for w in list(container.winfo_children()):
            w.destroy()
        self._kanban_card_vars = {}

        if not leads:
            empty = ctk.CTkFrame(container, fg_color=_CARD, corner_radius=10)
            empty.pack(padx=12, pady=12, fill="x")
            ctk.CTkLabel(
                empty,
                text="Sem leads no pipeline local de prospecção.",
                font=ctk.CTkFont(size=12), text_color="#6B7280",
            ).pack(padx=16, pady=(14, 4))
            ctk.CTkLabel(
                empty,
                text="Prospecte a partir de 🔍 Pesquisar — cada envio entra aqui automaticamente, "
                     "consoante o resultado: sucesso vai para 'Qualificação', falha volta para 'À Prospectar'.",
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

            hdr_f = ctk.CTkFrame(col_frame, fg_color=col_color, corner_radius=8, height=36)
            hdr_f.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
            hdr_f.pack_propagate(False)

            if cat_id == "to-prospect" and col_leads:
                self._kanban_col_select_all_var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(
                    hdr_f, text="", variable=self._kanban_col_select_all_var,
                    width=20, height=20, checkbox_width=16, checkbox_height=16,
                    fg_color="white", checkmark_color=col_color, border_color="white",
                    hover_color="#E5E7EB",
                    command=lambda ls=col_leads: self._toggle_all_kanban(ls),
                ).pack(side="left", padx=(8, 0))
                ctk.CTkLabel(
                    hdr_f,
                    text=f"{cat_label}  ({len(col_leads)})",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="white",
                ).pack(side="left", padx=4, expand=True)
            else:
                ctk.CTkLabel(
                    hdr_f,
                    text=f"{cat_label}  ({len(col_leads)})",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="white",
                ).pack(expand=True)

            cards_scroll = ctk.CTkScrollableFrame(col_frame, fg_color="transparent")
            cards_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))

            if not col_leads:
                ctk.CTkLabel(
                    cards_scroll, text="Sem leads",
                    font=ctk.CTkFont(size=11), text_color="#374151",
                ).pack(pady=16)
            else:
                for lead in col_leads:
                    self._render_local_kanban_card(cards_scroll, lead, cat_id, container)

    def _render_local_kanban_card(
        self,
        parent: ctk.CTkFrame,
        lead: dict,
        current_cat: str,
        kanban_container: ctk.CTkFrame,
    ) -> None:
        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=8, cursor="hand2")
        card.pack(fill="x", padx=4, pady=3)

        name = (lead.get("companyName") or "Lead")[:26]
        phone = lead.get("phone") or "—"
        lead_id = lead.get("id")
        origin = lead.get("origin") or "Local"

        card.bind("<Button-1>", lambda _e, l=lead: self._show_local_lead_detail(l))

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=8, pady=(6, 1))

        name_lbl = ctk.CTkLabel(
            top_row, text=name,
            font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
        )
        name_lbl.pack(side="left", fill="x", expand=True)
        name_lbl.bind("<Button-1>", lambda _e, l=lead: self._show_local_lead_detail(l))

        if current_cat == "to-prospect" and lead_id is not None:
            var = ctk.BooleanVar(value=lead_id in self._kanban_selected)
            self._kanban_card_vars[lead_id] = var
            ctk.CTkCheckBox(
                top_row, text="", variable=var,
                width=20, height=20, checkbox_width=16, checkbox_height=16,
                command=lambda lid=lead_id, v=var: self._on_kanban_check(lid, v),
            ).pack(side="right")

        ctk.CTkLabel(
            card, text=phone,
            font=ctk.CTkFont(size=10), text_color="#6B7280", anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 1))

        origin_lbl = ctk.CTkLabel(
            card, text=f"#{lead_id} · {origin}",
            font=ctk.CTkFont(size=9), text_color="#374151", anchor="w",
        )
        origin_lbl.pack(fill="x", padx=8, pady=(0, 6))
        origin_lbl.bind("<Button-1>", lambda _e, l=lead: self._show_local_lead_detail(l))

    # ── Detalhe do lead local (modal com mensagem editável + copy/reenvio) ────

    def _show_local_lead_detail(self, lead: dict) -> None:
        lead_id = lead.get("id")
        if lead_id is None:
            return

        popup = ctk.CTkToplevel(self)
        popup.title(f"Lead {lead_id}")
        popup.geometry("520x640")
        popup.resizable(True, True)
        popup.grab_set()
        popup.focus()

        name = lead.get("companyName") or "Lead"
        phone = lead.get("phone") or "—"
        cat_label = next((c[1] for c in self._KANBAN_COLS if c[0] == lead.get("category")), "—")

        hdr = ctk.CTkFrame(popup, fg_color="#1E1E2E", corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        company_label = ctk.CTkLabel(
            hdr, text=name, font=ctk.CTkFont(size=14, weight="bold"),
        )
        company_label.pack(anchor="w", padx=16, pady=(10, 0))
        meta_label = ctk.CTkLabel(
            hdr, text=f"📞 {phone}   ·   estágio: {cat_label}   ·   {lead_id}",
            font=ctk.CTkFont(size=10), text_color="#9CA3AF",
        )
        meta_label.pack(anchor="w", padx=16, pady=(0, 10))

        # ── Dados do lead (editáveis) ─────────────────────────────────────────
        dados_frame = ctk.CTkFrame(popup, fg_color="transparent")
        dados_frame.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(dados_frame, text="Empresa:", width=70, anchor="w",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        entry_company = ctk.CTkEntry(dados_frame, height=28, font=ctk.CTkFont(size=11))
        entry_company.insert(0, lead.get("companyName") or "")
        entry_company.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(dados_frame, text="Contacto:", width=70, anchor="w",
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", pady=(4, 0), padx=(0, 6))
        entry_contact = ctk.CTkEntry(dados_frame, height=28, font=ctk.CTkFont(size=11))
        entry_contact.insert(0, lead.get("contactName") or "")
        entry_contact.grid(row=1, column=1, sticky="ew", pady=(4, 0))

        ctk.CTkLabel(dados_frame, text="Telefone:", width=70, anchor="w",
                     font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", pady=(4, 0), padx=(0, 6))
        entry_phone = ctk.CTkEntry(dados_frame, height=28, font=ctk.CTkFont(size=11))
        entry_phone.insert(0, lead.get("phone") or "")
        entry_phone.grid(row=2, column=1, sticky="ew", pady=(4, 0))

        dados_frame.columnconfigure(1, weight=1)

        dados_btn_row = ctk.CTkFrame(dados_frame, fg_color="transparent")
        dados_btn_row.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        status_dados_lbl = ctk.CTkLabel(
            dados_btn_row, text="", font=ctk.CTkFont(size=11), wraplength=300,
        )

        def _save_lead_data() -> None:
            from app.session import update_local_lead
            new_company = entry_company.get().strip()
            new_contact = entry_contact.get().strip()
            new_phone_val = entry_phone.get().strip()
            if not new_company:
                status_dados_lbl.configure(text="Empresa não pode estar vazio.", text_color="#EF4444")
                return
            update_local_lead(
                self._session, lead_id,
                companyName=new_company,
                contactName=new_contact,
                phone=new_phone_val,
            )
            lead["companyName"] = new_company
            lead["contactName"] = new_contact
            lead["phone"] = new_phone_val
            company_label.configure(text=new_company)
            meta_label.configure(
                text=f"📞 {new_phone_val or '—'}   ·   estágio: {cat_label}   ·   {lead_id}"
            )
            status_dados_lbl.configure(text="✓ Dados guardados.", text_color="#16A34A")
            kc = getattr(self, "_kanban_content", None)
            if kc and self._widget_alive(kc):
                self._reload_kanban(kc, is_subscriber(self._session))

        ctk.CTkButton(
            dados_btn_row, text="💾 Guardar dados", width=140, height=28, corner_radius=6,
            fg_color="#1D4ED8", hover_color="#1E40AF", font=ctk.CTkFont(size=11, weight="bold"),
            command=_save_lead_data,
        ).pack(side="left")
        status_dados_lbl.pack(side="left", padx=(10, 0))

        ctk.CTkFrame(popup, height=1, fg_color="#374151").pack(fill="x", padx=16, pady=(10, 0))

        ctk.CTkLabel(
            popup, text="Mensagem",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 4))

        msg_box = ctk.CTkTextbox(popup, height=140, corner_radius=8, font=ctk.CTkFont(size=11))
        msg_box.pack(fill="x", padx=16, pady=(0, 6))
        msg_box.insert("1.0", lead.get("customMessage") or "")

        status_lbl = ctk.CTkLabel(
            popup, text="", font=ctk.CTkFont(size=11), text_color="#9CA3AF", wraplength=480, justify="left",
        )
        status_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        actions = ctk.CTkFrame(popup, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 6))

        def _save_message() -> None:
            from app.session import update_local_lead
            text = msg_box.get("1.0", "end").strip()
            update_local_lead(self._session, lead_id, customMessage=text)
            lead["customMessage"] = text
            status_lbl.configure(text="✓ Mensagem guardada.", text_color="#10B981")

        ctk.CTkButton(
            actions, text="💾 Guardar mensagem", width=150, height=28, corner_radius=6,
            fg_color="#1D4ED8", hover_color="#1E40AF", font=ctk.CTkFont(size=11, weight="bold"),
            command=_save_message,
        ).pack(side="left")

        ctk.CTkButton(
            actions, text="📋 Copiar", width=90, height=28, corner_radius=6,
            fg_color="#374151", hover_color="#4B5563", font=ctk.CTkFont(size=11),
            command=lambda: self._copy_text_to_clipboard(msg_box.get("1.0", "end").strip()),
        ).pack(side="left", padx=(6, 0))

        copy_btn = ctk.CTkButton(
            actions, text="✨ Gerar copy", width=120, height=28, corner_radius=6,
            fg_color="#7C3AED", hover_color="#6D28D9", font=ctk.CTkFont(size=11, weight="bold"),
        )
        copy_btn.pack(side="left", padx=(6, 0))

        resend_btn = ctk.CTkButton(
            actions, text="📱 Reenviar agora", width=130, height=28, corner_radius=6,
            fg_color="#065F46", hover_color="#047857", font=ctk.CTkFont(size=11, weight="bold"),
        )
        resend_btn.pack(side="right")

        def _generate_copy() -> None:
            from app.local_copy import generate_copy_local, LocalCopyError

            copy_btn.configure(state="disabled", text="A gerar…")
            status_lbl.configure(text="")

            def _worker():
                try:
                    text = generate_copy_local(
                        self._session,
                        company_name=lead.get("companyName") or name,
                        contact_name=lead.get("contactName") or "",
                    )
                    self.after(0, lambda: _on_copy_done(text, None))
                except LocalCopyError as exc:
                    self.after(0, lambda: _on_copy_done(None, str(exc)))
                except Exception as exc:
                    self.after(0, lambda: _on_copy_done(None, f"Erro ao gerar mensagem: {exc}"))

            def _on_copy_done(text, error):
                copy_btn.configure(state="normal", text="✨ Gerar copy")
                if error:
                    status_lbl.configure(text=error, text_color="#EF4444")
                    return
                msg_box.delete("1.0", "end")
                msg_box.insert("1.0", text or "")
                status_lbl.configure(text="✓ Copy gerada — revê e guarda se quiseres usá-la no reenvio.", text_color="#10B981")

            threading.Thread(target=_worker, daemon=True).start()

        copy_btn.configure(command=_generate_copy)

        def _resend() -> None:
            from app.session import update_local_lead
            from app.whatsapp_client import send_message

            text = msg_box.get("1.0", "end").strip()
            if not text:
                status_lbl.configure(text="Escreve uma mensagem antes de reenviar.", text_color="#EF4444")
                return

            resend_btn.configure(state="disabled", text="A enviar…")
            status_lbl.configure(text="A enviar via WhatsApp Web…", text_color="#9CA3AF")

            def _worker():
                current_phone = lead.get("phone") or phone
                result = send_message(current_phone, text)
                status = result["status"]
                # Actualiza este lead específico por id — upsert_local_lead faz
                # match por telefone, o que corrompe outro lead se dois leads
                # partilharem o mesmo número (ex.: mesmo número de teste).
                update_local_lead(
                    self._session,
                    lead_id,
                    category="qualification" if status == "sent" else "to-prospect",
                    customMessage=text,
                )

                def _done():
                    resend_btn.configure(state="normal", text="📱 Reenviar agora")
                    if status == "sent":
                        status_lbl.configure(text="✓ Enviado — lead movido para 'Qualificação'.", text_color="#10B981")
                    else:
                        status_lbl.configure(
                            text=f"✗ Falhou ({result.get('reason', '—')}) — lead em 'À Prospectar' para nova tentativa.",
                            text_color="#EF4444",
                        )
                    kc = getattr(self, "_kanban_content", None)
                    if kc and self._widget_alive(kc):
                        self._reload_kanban(kc, is_subscriber(self._session))

                self.after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        resend_btn.configure(command=_resend)

        def _confirm_delete() -> None:
            confirm = ctk.CTkToplevel(popup)
            confirm.title("Eliminar lead")
            confirm.geometry("340x150")
            confirm.resizable(False, False)
            confirm.grab_set()

            ctk.CTkLabel(
                confirm,
                text="Eliminar este lead do Kanban local?\nEsta acção não pode ser desfeita.",
                font=ctk.CTkFont(size=12), wraplength=300, justify="center",
            ).pack(pady=(24, 16))

            def _do_delete() -> None:
                from app.session import delete_local_lead
                delete_local_lead(self._session, lead_id)
                confirm.destroy()
                popup.destroy()
                kc = getattr(self, "_kanban_content", None)
                if kc and self._widget_alive(kc):
                    self._reload_kanban(kc, is_subscriber(self._session))

            row = ctk.CTkFrame(confirm, fg_color="transparent")
            row.pack(pady=(0, 8))
            ctk.CTkButton(
                row, text="Cancelar", width=100,
                fg_color="#374151", hover_color="#4B5563",
                command=confirm.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                row, text="🗑 Eliminar", width=100,
                fg_color="#7F1D1D", hover_color="#991B1B",
                command=_do_delete,
            ).pack(side="left")

        footer = ctk.CTkFrame(popup, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=8)
        ctk.CTkButton(
            footer, text="🗑 Eliminar lead", width=130, height=28, corner_radius=6,
            fg_color="#7F1D1D", hover_color="#991B1B", font=ctk.CTkFont(size=11),
            command=_confirm_delete,
        ).pack(side="left")
        ctk.CTkButton(footer, text="Fechar", width=100, command=popup.destroy).pack(side="right")

    def _send_selected_local_leads(self) -> None:
        """Equivalente local de `_enqueue_selected_leads` — envia sequencialmente
        via WhatsApp Web (Selenium) e move cada lead mecanicamente consoante o
        resultado real do envio (sem CRM)."""
        lead_ids = list(self._kanban_selected.keys())
        if not lead_ids:
            return
        msg = self._bulk_msg_entry.get().strip() if hasattr(self, "_bulk_msg_entry") else ""

        if hasattr(self, "_bulk_msg_entry"):
            self._bulk_msg_entry.configure(state="disabled")

        def _do():
            import random as _random
            import time as _time
            from app.session import get_local_leads, move_local_lead, upsert_local_lead
            from app.whatsapp_client import send_message

            leads_by_id = {l.get("id"): l for l in get_local_leads(self._session)}
            sent = failed = 0
            total = len(lead_ids)

            for i, lid in enumerate(lead_ids):
                lead = leads_by_id.get(lid)
                if not lead:
                    continue
                phone = lead.get("phone") or ""
                text = msg or lead.get("customMessage") or ""
                if not phone or not text:
                    failed += 1
                    continue

                move_local_lead(self._session, lid, "in-progress")
                result = send_message(phone, text)
                status = result["status"]
                upsert_local_lead(
                    self._session,
                    phone=phone,
                    name=lead.get("companyName", "Lead"),
                    category="qualification" if status == "sent" else "to-prospect",
                    website=lead.get("website", ""),
                    address=lead.get("address", ""),
                    customMessage=text,
                )
                if status == "sent":
                    sent += 1
                else:
                    failed += 1

                if i < total - 1:
                    _time.sleep(_random.uniform(25, 60))

            parts = []
            if sent:
                parts.append(f"✓ {sent} enviado{'s' if sent != 1 else ''}")
            if failed:
                parts.append(f"⚠ {failed} falhado{'s' if failed != 1 else ''}")
            summary = "  ".join(parts) or "Nenhum lead enviado"

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

        threading.Thread(target=_do, daemon=True).start()

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
    # PAINEL 4 — HISTÓRICO
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
            summary = None
            if is_subscriber(self._session):
                try:
                    from app.crm_client import get_prospect_history, get_prospect_history_summary
                    entries = get_prospect_history(self._session, limit=200)
                    try:
                        summary = get_prospect_history_summary(self._session)
                    except Exception:
                        summary = None
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
                    _CHANNEL_LABELS = {"email": "Email", "whatsapp": "WhatsApp"}

                    hdr_row = ctk.CTkFrame(table, fg_color="transparent")
                    hdr_row.pack(fill="x", padx=8, pady=(4, 4))
                    _COLS = [("Data/Hora", 100), ("Nome", 100), ("Canal", 70),
                             ("Contacto", 110), ("Estado", 100), ("Notas", 140)]
                    for col, w in _COLS:
                        ctk.CTkLabel(hdr_row, text=col, font=ctk.CTkFont(size=10, weight="bold"),
                                      text_color="#9CA3AF", anchor="w", width=w
                                      ).pack(side="left", padx=4)

                    for idx, e in enumerate(entries):
                        ts = (e.get("created_at") or e.get("ts") or "")[:16].replace("T", " ")
                        name = (e.get("lead_name") or e.get("name") or "—")[:20]
                        channel = e.get("channel") or ""
                        channel_label = _CHANNEL_LABELS.get(channel, channel or "—")
                        contact = (e.get("email") if channel == "email" else e.get("phone")) or "—"
                        action = e.get("action") or e.get("status") or "—"
                        notes = (e.get("notes") or e.get("reason") or "—")[:28]
                        action_label = _ACTION_LABELS.get(action, action)
                        color = "#EF4444" if "fail" in action.lower() else "#10B981"

                        row = ctk.CTkFrame(table, fg_color="#1A1A2E" if idx % 2 == 0 else "#16162A",
                                            corner_radius=4)
                        row.pack(fill="x", padx=8, pady=1)
                        for val, tc, w in [(ts, "#9CA3AF", 100), (name, "#D1D5DB", 100),
                                            (channel_label, "#9CA3AF", 70), (contact, "#9CA3AF", 110),
                                            (action_label, color, 100), (notes, "#9CA3AF", 140)]:
                            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=10),
                                          text_color=tc, anchor="w", width=w
                                          ).pack(side="left", padx=(8 if val == ts else 4, 4), pady=5)

                    ctk.CTkLabel(table, text=f"{len(entries)} registos",
                                  font=ctk.CTkFont(size=10), text_color="#6B7280").pack(pady=6)

                    if summary:
                        parts = []
                        if summary.get("sent"):
                            s = summary["sent"]
                            parts.append(f"✓ {s} enviado{'s' if s != 1 else ''}")
                        if summary.get("failed"):
                            fl = summary["failed"]
                            parts.append(f"⚠ {fl} falhado{'s' if fl != 1 else ''}")
                        if summary.get("queued"):
                            q = summary["queued"]
                            parts.append(f"📥 {q} enfileirado{'s' if q != 1 else ''}")
                        if parts:
                            ctk.CTkLabel(table, text="  ".join(parts),
                                          font=ctk.CTkFont(size=11, weight="bold"),
                                          text_color="#D1D5DB").pack(pady=(0, 8))
                except Exception:
                    pass

            self._historico_entries = entries
            self.after(0, _render)

        threading.Thread(target=_fetch, daemon=True).start()

        # Export CSV
        def _export_csv():
            import csv
            from tkinter import filedialog
            entries_snap = getattr(self, "_historico_entries", [])
            if not entries_snap:
                return
            path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                 filetypes=[("CSV", "*.csv")],
                                                 initialfile="historico.csv")
            if path:
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as f:
                        w = csv.writer(f)
                        w.writerow(["Data/Hora", "Nome", "Canal", "Contacto", "Estado", "Notas"])
                        for e in entries_snap:
                            ts = (e.get("created_at") or e.get("ts") or "")[:16].replace("T", " ")
                            channel = e.get("channel") or ""
                            contact = (e.get("email") if channel == "email" else e.get("phone")) or ""
                            w.writerow([
                                ts,
                                e.get("lead_name") or e.get("name") or "",
                                channel,
                                contact,
                                e.get("action") or e.get("status") or "",
                                e.get("notes") or e.get("reason") or "",
                            ])
                    popup = ctk.CTkToplevel(self)
                    popup.title("Exportado!")
                    popup.geometry("320x120")
                    popup.grab_set()
                    from pathlib import Path
                    ctk.CTkLabel(popup, text=f"✅  {Path(path).name}",
                                 font=ctk.CTkFont(size=13)).pack(pady=(24, 8))
                    ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack()
                except Exception as exc:
                    error_popup = ctk.CTkToplevel(self)
                    error_popup.title("Erro ao exportar")
                    error_popup.geometry("360x120")
                    error_popup.grab_set()
                    ctk.CTkLabel(error_popup, text=f"⚠ {exc}", font=ctk.CTkFont(size=12),
                                 wraplength=320).pack(pady=(20, 8))
                    ctk.CTkButton(error_popup, text="OK", width=80, command=error_popup.destroy).pack()

        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=8)
        ctk.CTkButton(footer, text="📥 Exportar CSV", height=30, corner_radius=6,
                       fg_color="#2A2A3E", command=_export_csv).pack(side="left")

    # ══════════════════════════════════════════════════════════════════════════
    # PAINEL 5 — CONTA / CONFIGURAÇÕES
    # ══════════════════════════════════════════════════════════════════════════

    def _show_smtp_help_popup(self) -> None:
        """Popup com o passo-a-passo para gerar uma senha de app do Gmail (ícone '?' do card SMTP)."""
        popup = ctk.CTkToplevel(self)
        popup.title("Como obter a senha de app")
        popup.geometry("420x480")
        popup.grab_set()

        ctk.CTkLabel(
            popup, text="Como gerar a senha de app do Gmail",
            font=ctk.CTkFont(size=14, weight="bold"), wraplength=380, justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            popup,
            text="Isto é diferente da senha normal da conta — o Gmail só aceita login de "
                 "programas externos através desta senha especial de 16 caracteres.\n\n"
                 "Pré-requisito: a verificação em 2 etapas precisa estar activada na conta. "
                 "Sem isso, a opção de senhas de app nem aparece.",
            font=ctk.CTkFont(size=11), text_color="#9CA3AF", wraplength=380, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        steps = (
            "1. Entra em myaccount.google.com com a conta que vais usar para enviar\n"
            "2. No menu lateral, ir a Segurança\n"
            "3. Confirmar que \"Verificação em duas etapas\" está activada (activar se não estiver)\n"
            "4. Ainda em Segurança, procurar \"Senhas de app\"\n"
            "5. Em \"Nome do app\", escrever algo como \"CRM AutoDigital\" e clicar em Criar\n"
            "6. Copiar a senha de 16 caracteres mostrada, sem espaços\n"
            "7. Colar essa senha aqui no campo \"Senha (ou senha de app)\" — não a senha normal"
        )
        ctk.CTkLabel(
            popup, text=steps, font=ctk.CTkFont(size=11),
            wraplength=380, justify="left", anchor="w",
        ).pack(anchor="w", padx=16, pady=(0, 12), fill="x")

        ctk.CTkButton(
            popup, text="🔗 Abrir myaccount.google.com/apppasswords", height=34,
            command=lambda: webbrowser.open("https://myaccount.google.com/apppasswords"),
        ).pack(padx=16, pady=(0, 8), fill="x")

        ctk.CTkButton(
            popup, text="Fechar", height=34, fg_color="#374151", hover_color="#4B5563",
            command=popup.destroy,
        ).pack(padx=16, pady=(0, 16), fill="x")

    def _build_smtp_card(self, body: ctk.CTkFrame) -> None:
        """Card 'Conta de email (SMTP)' — usada como canal de prospecção (Fase 5/6)."""
        card = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        card.pack(padx=20, fill="x", pady=(0, 12))

        ctk.CTkLabel(card, text="📧  Conta de email (prospecção)",
                      font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            card,
            text="Conecta uma conta de email para enviar o primeiro contacto por email "
                 "quando escolheres esse canal ao Enfileirar. Gmail exige verificação em 2 "
                 "etapas activada e uma senha de app (não a senha normal da conta).",
            font=ctk.CTkFont(size=11), text_color="#6B7280", wraplength=380, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        status_lbl = ctk.CTkLabel(card, text="Verificando…", fg_color="#2A2A3E", corner_radius=8,
                                   font=ctk.CTkFont(size=11), text_color="#6B7280", padx=8, pady=3)
        status_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        fields_row = ctk.CTkFrame(card, fg_color="transparent")
        fields_row.pack(padx=16, fill="x")
        fields_row.columnconfigure(0, weight=1)
        fields_row.columnconfigure(1, weight=1)

        host_entry = ctk.CTkEntry(fields_row, placeholder_text="Host (ex: smtp.gmail.com)", height=36, corner_radius=8)
        host_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)
        port_entry = ctk.CTkEntry(fields_row, placeholder_text="Porta", height=36, corner_radius=8)
        port_entry.insert(0, "587")
        port_entry.grid(row=0, column=1, sticky="ew", pady=4)

        user_entry = ctk.CTkEntry(card, placeholder_text="Username (ex: seu@gmail.com)", height=36, corner_radius=8)
        user_entry.pack(padx=16, fill="x", pady=4)

        pwd_row = ctk.CTkFrame(card, fg_color="transparent")
        pwd_row.pack(padx=16, fill="x", pady=4)
        pwd_row.columnconfigure(0, weight=1)
        pwd_entry = ctk.CTkEntry(pwd_row, placeholder_text="Senha (ou senha de app)", height=36,
                                  corner_radius=8, show="•")
        pwd_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        pwd_visible = [False]

        def _pwd_toggle():
            pwd_visible[0] = not pwd_visible[0]
            pwd_entry.configure(show="" if pwd_visible[0] else "•")
            pwd_toggle_btn.configure(text="🙈" if pwd_visible[0] else "👁")

        pwd_toggle_btn = ctk.CTkButton(pwd_row, text="👁", width=36, height=36,
                                        fg_color="#2A2A3E", command=_pwd_toggle)
        pwd_toggle_btn.grid(row=0, column=1, padx=(0, 6))

        help_btn = ctk.CTkButton(pwd_row, text="?", width=36, height=36,
                                  fg_color="#2A2A3E", command=lambda: self._show_smtp_help_popup())
        help_btn.grid(row=0, column=2)

        from_name_entry = ctk.CTkEntry(card, placeholder_text="Nome do remetente (opcional)", height=36, corner_radius=8)
        from_name_entry.pack(padx=16, fill="x", pady=4)

        error_lbl = ctk.CTkLabel(card, text="", text_color="#EF4444", font=ctk.CTkFont(size=11),
                                  wraplength=380, justify="left")
        error_lbl.pack(anchor="w", padx=16, pady=(4, 0))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(padx=16, pady=(6, 14), fill="x")

        def _refresh_status():
            def _do():
                from app.auth import get_smtp_status, AuthError
                try:
                    data = get_smtp_status(self._session["access_token"])
                except AuthError as exc:
                    data = None
                    err = str(exc)
                else:
                    err = None

                def _after():
                    if not self._widget_alive(status_lbl):
                        return
                    if err:
                        status_lbl.configure(text="Erro ao verificar", fg_color="#2A2A3E", text_color="#EF4444")
                        return
                    if data and data.get("connected"):
                        status_lbl.configure(text=f"✓ Conectado — {data.get('username', '')}",
                                              fg_color="#065F46", text_color="#10B981")
                        if self._widget_alive(host_entry):
                            host_entry.delete(0, "end"); host_entry.insert(0, data.get("host") or "")
                            port_entry.delete(0, "end"); port_entry.insert(0, str(data.get("port") or 587))
                            user_entry.delete(0, "end"); user_entry.insert(0, data.get("username") or "")
                            from_name_entry.delete(0, "end"); from_name_entry.insert(0, data.get("from_name") or "")
                        disconnect_btn.pack(side="left", padx=(8, 0))
                    else:
                        status_lbl.configure(text="Não conectado", fg_color="#2A2A3E", text_color="#6B7280")
                        disconnect_btn.pack_forget()
                self.after(0, _after)
            threading.Thread(target=_do, daemon=True).start()

        def _save():
            host = host_entry.get().strip()
            username = user_entry.get().strip()
            password = pwd_entry.get().strip()
            from_name = from_name_entry.get().strip()
            try:
                port = int(port_entry.get().strip() or "587")
            except ValueError:
                error_lbl.configure(text="Porta inválida.")
                return
            if not host or not username or not password:
                error_lbl.configure(text="Preenche host, username e senha.")
                return

            error_lbl.configure(text="")
            save_btn.configure(state="disabled", text="A testar…")

            def _do():
                from app.auth import save_smtp_account, AuthError
                try:
                    save_smtp_account(self._session["access_token"], host, port, username, password,
                                       from_name=from_name or None)
                except AuthError as exc:
                    err = str(exc)
                else:
                    err = None

                def _after():
                    if not self._widget_alive(save_btn):
                        return
                    save_btn.configure(state="normal", text="Conectar")
                    if err:
                        error_lbl.configure(text=err)
                        return
                    pwd_entry.delete(0, "end")
                    popup = ctk.CTkToplevel(self)
                    popup.title("Conectado")
                    popup.geometry("280x100")
                    popup.grab_set()
                    ctk.CTkLabel(popup, text="✓ Conta de email conectada", font=ctk.CTkFont(size=13)).pack(pady=24)
                    self.after(1200, popup.destroy)
                    _refresh_status()
                self.after(0, _after)
            threading.Thread(target=_do, daemon=True).start()

        def _disconnect():
            disconnect_btn.configure(state="disabled", text="A desconectar…")

            def _do():
                from app.auth import disconnect_smtp_account, AuthError
                try:
                    disconnect_smtp_account(self._session["access_token"])
                except AuthError as exc:
                    err = str(exc)
                else:
                    err = None

                def _after():
                    if not self._widget_alive(disconnect_btn):
                        return
                    disconnect_btn.configure(state="normal", text="Desconectar")
                    if err:
                        error_lbl.configure(text=err)
                        return
                    host_entry.delete(0, "end")
                    user_entry.delete(0, "end")
                    from_name_entry.delete(0, "end")
                    _refresh_status()
                self.after(0, _after)
            threading.Thread(target=_do, daemon=True).start()

        save_btn = ctk.CTkButton(btn_row, text="Conectar", height=34, command=_save)
        save_btn.pack(side="left")
        disconnect_btn = ctk.CTkButton(btn_row, text="Desconectar", height=34,
                                        fg_color="#374151", hover_color="#4B5563", command=_disconnect)
        # visibilidade controlada por _refresh_status (só aparece se já conectado)

        _refresh_status()

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

        # Secção: conta de email (SMTP) — usada pela prospecção via canal Email
        self._build_smtp_card(body)

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

            # Secção: chave OpenAI API (gerador de copy no modo gratuito)
            openai_card = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
            openai_card.pack(padx=20, fill="x", pady=(0, 12))

            ctk.CTkLabel(openai_card, text="🔑  Chave OpenAI API",
                          font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
            ctk.CTkLabel(openai_card,
                          text="Necessária para gerar copys com IA no modo gratuito (Assistente IA). "
                               "A tua chave fica guardada apenas neste computador.",
                          font=ctk.CTkFont(size=11), text_color="#6B7280", wraplength=380, justify="left"
                          ).pack(anchor="w", padx=16, pady=(0, 8))

            oai_entry_row = ctk.CTkFrame(openai_card, fg_color="transparent")
            oai_entry_row.pack(padx=16, pady=(0, 6), fill="x")
            oai_entry_row.columnconfigure(0, weight=1)

            oai_key_entry = ctk.CTkEntry(oai_entry_row, placeholder_text="sk-...", height=36,
                                          corner_radius=8, show="•")
            oai_existing = self._session.get("openai_api_key", "")
            if oai_existing:
                oai_key_entry.insert(0, oai_existing)
            oai_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

            oai_visible = [False]

            def _oai_toggle():
                oai_visible[0] = not oai_visible[0]
                oai_key_entry.configure(show="" if oai_visible[0] else "•")
                oai_toggle_btn.configure(text="🙈" if oai_visible[0] else "👁")

            oai_toggle_btn = ctk.CTkButton(oai_entry_row, text="👁", width=36, height=36,
                                            fg_color="#2A2A3E", command=_oai_toggle)
            oai_toggle_btn.grid(row=0, column=1)

            def _save_oai_key():
                key = oai_key_entry.get().strip()
                self._session["openai_api_key"] = key or None
                from app.session import save_session
                save_session(self._session)
                popup = ctk.CTkToplevel(self)
                popup.title("Guardado")
                popup.geometry("280x100")
                popup.grab_set()
                ctk.CTkLabel(popup, text="✓ Chave guardada", font=ctk.CTkFont(size=13)).pack(pady=24)
                self.after(1200, popup.destroy)

            ctk.CTkButton(openai_card, text="Guardar chave", height=34,
                           command=_save_oai_key).pack(padx=16, pady=(0, 14))

        else:
            info = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
            info.pack(padx=20, fill="x", pady=(0, 12))
            ctk.CTkLabel(info, text="✓  Chave Google Maps incluída na assinatura",
                          font=ctk.CTkFont(size=12), text_color="#10B981"
                          ).pack(padx=16, pady=14)

        # Secção: prompt de copy personalizado (disponível para todos os planos)
        _DEFAULT_COPY_PROMPT = (
            "Escreve uma mensagem de prospecção via [canal] para a empresa [empresa]. "
            "Tom: [tom]. "
            "A oferta deve reflectir o [nicho] e a proposta de valor de [oferta] — "
            "não inventes temas genéricos que não tenham relação com a oferta da [marca]. "
            "NUNCA uses placeholders como [Seu Nome] ou [Sua Empresa]; usa os dados reais "
            "do remetente ou fala apenas em nome da empresa do destinatário. "
            "Máximo 3 frases curtas e directas. Não uses saudações genéricas. "
            "Apresenta uma proposta de valor clara e termina com uma pergunta ou CTA simples."
        )

        prompt_card = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=12)
        prompt_card.pack(padx=20, fill="x", pady=(0, 12))

        ctk.CTkLabel(prompt_card, text="🤖  Prompt de Copy",
                      font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            prompt_card,
            text="Edita o script abaixo — a IA gera uma variação personalizada para cada lead.\n"
                 "Usa as variáveis disponíveis. \"Restaurar padrão\" repõe o texto original.",
            font=ctk.CTkFont(size=11), text_color="#6B7280", wraplength=380, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        prompt_box = ctk.CTkTextbox(prompt_card, height=140, corner_radius=8, font=ctk.CTkFont(size=12))
        prompt_box.pack(padx=16, fill="x")
        existing_prompt = self._session.get("local_copy_prompt") or ""
        prompt_box.insert("0.0", existing_prompt if existing_prompt else _DEFAULT_COPY_PROMPT)

        chips_frame = ctk.CTkFrame(prompt_card, fg_color="transparent")
        chips_frame.pack(anchor="w", padx=16, pady=(6, 4))

        _CHIP_VARS = [
            "[empresa]", "[setor]", "[contacto]", "[canal]",
            "[tom]", "[nicho]", "[oferta]", "[marca]",
        ]
        for _cv in _CHIP_VARS:
            def _insert_var(_v=_cv):
                prompt_box.insert("end", _v)
            ctk.CTkButton(
                chips_frame, text=_cv, height=24, corner_radius=6,
                fg_color="#1E3A5F", hover_color="#2563EB",
                font=ctk.CTkFont(size=10),
                command=_insert_var,
            ).pack(side="left", padx=(0, 4), pady=2)

        def _save_prompt():
            text = prompt_box.get("0.0", "end").strip()
            self._session["local_copy_prompt"] = text
            from app.session import save_session
            save_session(self._session)
            _toast = ctk.CTkToplevel(self)
            _toast.title("Guardado")
            _toast.geometry("280x100")
            _toast.grab_set()
            ctk.CTkLabel(_toast, text="✓ Prompt guardado", font=ctk.CTkFont(size=13)).pack(pady=24)
            self.after(1200, _toast.destroy)

        def _restore_prompt():
            self._session["local_copy_prompt"] = ""
            from app.session import save_session
            save_session(self._session)
            prompt_box.delete("0.0", "end")
            prompt_box.insert("0.0", _DEFAULT_COPY_PROMPT)
            _toast = ctk.CTkToplevel(self)
            _toast.title("Reposto")
            _toast.geometry("280x100")
            _toast.grab_set()
            ctk.CTkLabel(_toast, text="✓ Prompt padrão restaurado", font=ctk.CTkFont(size=13)).pack(pady=24)
            self.after(1200, _toast.destroy)

        prompt_btn_row = ctk.CTkFrame(prompt_card, fg_color="transparent")
        prompt_btn_row.pack(padx=16, pady=(6, 14), fill="x")
        ctk.CTkButton(prompt_btn_row, text="Guardar prompt", height=34,
                       command=_save_prompt).pack(side="left")
        ctk.CTkButton(prompt_btn_row, text="Restaurar padrão", height=34,
                       fg_color="#374151", hover_color="#4B5563",
                       command=_restore_prompt).pack(side="left", padx=(8, 0))

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
