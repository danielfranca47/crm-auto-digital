"""Diálogo de prospecção em lote — envia WhatsApp para múltiplos leads em série com delay."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from app.session import is_subscriber, get_templates


_DELAY_OPTIONS = {"5s": 5, "10s": 10, "15s": 15, "30s": 30}

_DEFAULT_MSG = (
    "Olá! Vi o vosso negócio e gostaria de apresentar uma solução "
    "que pode ajudar. Podemos conversar?"
)

# Chips de estado por lead
_STATUS_ICONS = {
    "waiting":  ("⏳", "#6B7280"),
    "sending":  ("📱", "#60A5FA"),
    "sent":     ("✓",  "#10B981"),
    "failed":   ("✗",  "#EF4444"),
}


class BulkProspectDialog(ctk.CTkToplevel):
    """
    Prospecção em lote — 3 passos:
      1. Formulário (mensagem, delay, opção CRM)
      2. Progresso em tempo real por lead
      3. Resumo final
    """

    def __init__(self, master, leads: List[Dict[str, Any]], session: dict):
        super().__init__(master)
        self.title(f"📱 Prospectar {len(leads)} leads")
        self.geometry("540x520")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        self._leads = leads
        self._session = session
        self._subscriber = is_subscriber(session)
        self._cancel_flag = threading.Event()

        # estado de progresso por lead
        self._statuses: Dict[int, str] = {i: "waiting" for i in range(len(leads))}
        self._status_labels: Dict[int, ctk.CTkLabel] = {}

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=20, pady=16)
        self._show_form()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _clear(self) -> None:
        for w in self._body.winfo_children():
            w.destroy()

    def _phone_clean(self, raw: str) -> str:
        for ch in (" ", "-", "(", ")", "."):
            raw = raw.replace(ch, "")
        return raw

    # ── Passo 1: Formulário ───────────────────────────────────────────────────

    def _show_form(self) -> None:
        self._clear()
        c = self._body

        ctk.CTkLabel(
            c,
            text=f"Prospectar {len(self._leads)} leads via WhatsApp",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 12))

        # Preview dos leads seleccionados
        preview = ctk.CTkScrollableFrame(c, fg_color="#12121F", corner_radius=8, height=80)
        preview.pack(fill="x", pady=(0, 10))
        for lead in self._leads[:10]:
            name = (lead.get("name") or "Lead")[:30]
            phone = lead.get("phone") or "—"
            ctk.CTkLabel(
                preview,
                text=f"• {name}  ({phone})",
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF",
                anchor="w",
            ).pack(anchor="w", padx=8, pady=1)
        if len(self._leads) > 10:
            ctk.CTkLabel(
                preview,
                text=f"  … e mais {len(self._leads) - 10} leads",
                font=ctk.CTkFont(size=11), text_color="#6B7280",
            ).pack(anchor="w", padx=8)

        # Selector de templates
        templates = get_templates(self._session)
        if templates:
            tmpl_row = ctk.CTkFrame(c, fg_color="transparent")
            tmpl_row.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(tmpl_row, text="Template:", font=ctk.CTkFont(size=11),
                         text_color="#9CA3AF").pack(side="left", padx=(0, 6))
            tmpl_names = [t["name"] for t in templates]
            tmpl_var = ctk.StringVar(value="— escolher —")
            ctk.CTkOptionMenu(
                tmpl_row,
                values=["— escolher —"] + tmpl_names,
                variable=tmpl_var,
                height=28, corner_radius=6,
                command=lambda n: self._apply_template(n, templates),
            ).pack(side="left")

        # Mensagem
        ctk.CTkLabel(c, text="Mensagem (partilhada por todos os leads)",
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        self._msg_box = ctk.CTkTextbox(c, height=90, corner_radius=8)
        self._msg_box.insert("1.0", _DEFAULT_MSG)
        self._msg_box.pack(fill="x", pady=(4, 10))

        # Opções
        opts_row = ctk.CTkFrame(c, fg_color="transparent")
        opts_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(opts_row, text="Delay entre envios:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self._delay_var = ctk.StringVar(value="10s")
        ctk.CTkOptionMenu(
            opts_row,
            values=list(_DELAY_OPTIONS.keys()),
            variable=self._delay_var,
            width=80, height=30, corner_radius=6,
        ).pack(side="left")

        if self._subscriber:
            self._crm_var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(
                opts_row, text="Registar no CRM",
                variable=self._crm_var,
                font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=(20, 0))

        # Badge modo
        badge_text = "✓ Assinante — envio + registo no CRM" if self._subscriber else "Gratuito — envio local"
        badge_color = "#10B981" if self._subscriber else "#6B7280"
        ctk.CTkLabel(
            c, text=badge_text,
            fg_color=badge_color, corner_radius=8,
            text_color="white", font=ctk.CTkFont(size=10, weight="bold"),
            padx=8, pady=3,
        ).pack(anchor="w", pady=(0, 12))

        # Botões
        btn_row = ctk.CTkFrame(c, fg_color="transparent")
        btn_row.pack(fill="x")
        ctk.CTkButton(btn_row, text="Cancelar", fg_color="#2A2A3E",
                      hover_color="#3A3A5E", command=self.destroy).pack(side="left")
        ctk.CTkButton(btn_row, text=f"Iniciar {len(self._leads)} envios →",
                      command=self._start_bulk).pack(side="right")

    def _apply_template(self, name: str, templates: list) -> None:
        if name.startswith("—"):
            return
        for t in templates:
            if t.get("name") == name:
                self._msg_box.delete("1.0", "end")
                self._msg_box.insert("1.0", t["text"])
                return

    # ── Passo 2: Progresso ───────────────────────────────────────────────────

    def _show_progress(self) -> None:
        self._clear()
        c = self._body

        ctk.CTkLabel(
            c, text="A enviar mensagens…",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        # Barra de progresso geral
        self._progress_bar = ctk.CTkProgressBar(c, height=8, corner_radius=4)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", pady=(0, 8))

        self._progress_label = ctk.CTkLabel(
            c, text="0 / 0 enviados",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        )
        self._progress_label.pack(anchor="w", pady=(0, 8))

        # Lista de chips por lead
        list_frame = ctk.CTkScrollableFrame(c, fg_color="#12121F", corner_radius=8, height=220)
        list_frame.pack(fill="x", pady=(0, 10))

        for i, lead in enumerate(self._leads):
            name = (lead.get("name") or "Lead")[:35]
            row = ctk.CTkFrame(list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)

            icon, color = _STATUS_ICONS["waiting"]
            lbl = ctk.CTkLabel(
                row, text=f"{icon} {name}",
                font=ctk.CTkFont(size=11), text_color=color, anchor="w",
            )
            lbl.pack(side="left")
            self._status_labels[i] = lbl

        ctk.CTkLabel(
            c, text="⚠  Não feches o Chrome enquanto os envios decorrem.",
            text_color="#F59E0B", font=ctk.CTkFont(size=11), wraplength=480,
        ).pack(pady=(0, 8))

        self._cancel_btn = ctk.CTkButton(
            c, text="Cancelar envios",
            fg_color="#7F1D1D", hover_color="#991B1B",
            command=self._request_cancel,
        )
        self._cancel_btn.pack()

    def _update_chip(self, idx: int, status: str) -> None:
        def _do():
            if idx not in self._status_labels:
                return
            lbl = self._status_labels[idx]
            name = (self._leads[idx].get("name") or "Lead")[:35]
            icon, color = _STATUS_ICONS.get(status, ("?", "#6B7280"))
            try:
                lbl.configure(text=f"{icon} {name}", text_color=color)
            except Exception:
                pass
        self.after(0, _do)

    def _update_progress(self, done: int, total: int) -> None:
        def _do():
            try:
                pct = done / total if total > 0 else 0
                self._progress_bar.set(pct)
                self._progress_label.configure(text=f"{done} / {total} enviados")
            except Exception:
                pass
        self.after(0, _do)

    def _request_cancel(self) -> None:
        self._cancel_flag.set()
        try:
            self._cancel_btn.configure(state="disabled", text="A cancelar…")
        except Exception:
            pass

    # ── Passo 3: Resumo ───────────────────────────────────────────────────────

    def _show_summary(self, sent: int, failed: int, crm_saved: int) -> None:
        self._clear()
        c = self._body
        total = sent + failed

        ctk.CTkLabel(
            c, text="Envios concluídos",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(12, 16))

        stats_frame = ctk.CTkFrame(c, fg_color="#1E1E2E", corner_radius=10)
        stats_frame.pack(fill="x", pady=(0, 12))

        for label, value, color in [
            ("✓ Enviados", str(sent), "#10B981"),
            ("✗ Falhados", str(failed), "#EF4444"),
        ]:
            r = ctk.CTkFrame(stats_frame, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(r, text=label, font=ctk.CTkFont(size=13), text_color="#9CA3AF").pack(side="left")
            ctk.CTkLabel(r, text=value, font=ctk.CTkFont(size=13, weight="bold"), text_color=color).pack(side="right")

        if self._subscriber and crm_saved > 0:
            r = ctk.CTkFrame(stats_frame, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(r, text="💾 Registados no CRM", font=ctk.CTkFont(size=13), text_color="#9CA3AF").pack(side="left")
            ctk.CTkLabel(r, text=str(crm_saved), font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981").pack(side="right")

        if self._cancel_flag.is_set():
            ctk.CTkLabel(
                c, text="Envio cancelado pelo utilizador.",
                text_color="#F59E0B", font=ctk.CTkFont(size=12),
            ).pack(pady=(0, 8))

        ctk.CTkButton(c, text="Fechar", command=self.destroy).pack(pady=(12, 0))

    # ── Lógica de envio ───────────────────────────────────────────────────────

    def _start_bulk(self) -> None:
        message = self._msg_box.get("1.0", "end").strip()
        if not message:
            return
        delay_secs = _DELAY_OPTIONS.get(self._delay_var.get(), 10)
        save_crm = self._subscriber and getattr(self, "_crm_var", None) and self._crm_var.get()

        self._show_progress()
        threading.Thread(
            target=self._run_bulk,
            args=(message, delay_secs, save_crm),
            daemon=True,
        ).start()

    def _run_bulk(self, message: str, delay: int, save_crm: bool) -> None:
        from app.whatsapp_client import send_message
        from app.session import append_prospect_log, upsert_local_lead

        sent = failed = crm_saved = 0
        total = len(self._leads)

        for i, lead in enumerate(self._leads):
            if self._cancel_flag.is_set():
                break

            phone = self._phone_clean(lead.get("phone") or "")
            if not phone:
                self._update_chip(i, "failed")
                failed += 1
                self._update_progress(sent + failed, total)
                continue

            self._update_chip(i, "sending")
            result = send_message(phone, message)

            status = result["status"]
            self._update_chip(i, status)

            entry = {
                "ts": __import__("datetime").datetime.now().isoformat(),
                "name": lead.get("name", "Lead"),
                "phone": phone,
                "status": status,
                "reason": result.get("reason", ""),
            }
            append_prospect_log(entry)

            if not self._subscriber:
                upsert_local_lead(
                    self._session,
                    phone=phone,
                    name=lead.get("name", "Lead"),
                    category="qualification" if status == "sent" else "to-prospect",
                    website=lead.get("website", ""),
                    address=lead.get("address", ""),
                    customMessage=message,
                )

            if status == "sent":
                sent += 1
                if save_crm:
                    try:
                        from app.crm_client import create_lead, log_outbound
                        resp = create_lead(
                            self._session,
                            name=lead.get("name", "Lead"),
                            phone=phone,
                            website=lead.get("website", ""),
                            address=lead.get("address", ""),
                        )
                        lead_id = resp.get("id") or resp.get("lead_id")
                        if lead_id:
                            log_outbound(self._session, lead_id, message)
                            crm_saved += 1
                    except Exception:
                        pass
            else:
                failed += 1

            self._update_progress(sent + failed, total)

            # delay entre envios (excepto no último)
            if i < total - 1 and not self._cancel_flag.is_set():
                time.sleep(delay)

        self.after(0, lambda: self._show_summary(sent, failed, crm_saved))
