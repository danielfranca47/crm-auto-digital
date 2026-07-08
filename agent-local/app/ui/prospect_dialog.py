"""Diálogo de prospecção via WhatsApp Web — 3 passos: formulário → enviando → resultado."""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from app.session import is_subscriber


class ProspectDialog(ctk.CTkToplevel):
    """
    Diálogo modal que envia uma mensagem de prospecção via WhatsApp Web.

    Fluxo assinante  → envia + cria lead no CRM + regista outbound
    Fluxo gratuito   → envia localmente, sem qualquer chamada ao CRM
    """

    _DEFAULT_MSG = (
        "Olá! Vi o vosso negócio e gostaria de apresentar uma solução "
        "que pode ajudar. Podemos conversar?"
    )

    def __init__(
        self,
        master,
        lead_data: Dict[str, Any],
        session: dict,
        on_sent: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master)
        self.title("📱 Prospectar via WhatsApp")
        self.geometry("500x440")
        self.resizable(False, False)
        self.grab_set()
        self.focus()

        self._lead = lead_data
        self._session = session
        self._subscriber = is_subscriber(session)
        self._on_sent = on_sent

        self._phone_final = ""
        self._msg_final = ""
        self._result: Dict[str, str] = {}

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=24, pady=20)

        self._show_form()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _clear(self) -> None:
        for w in self._body.winfo_children():
            w.destroy()

    def _phone_clean(self, raw: str) -> str:
        for ch in (" ", "-", "(", ")", "."):
            raw = raw.replace(ch, "")
        if raw and not raw.startswith("+"):
            raw = "+" + raw
        return raw

    # ── Passo 1: Formulário ──────────────────────────────────────────────────

    def _show_form(self) -> None:
        self._clear()
        c = self._body

        name = (self._lead.get("name") or "Lead")[:40]
        ctk.CTkLabel(
            c, text=f"Prospectar: {name}",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 14))

        # Telefone
        ctk.CTkLabel(c, text="Número (com código de país, ex: +351912345678)",
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        raw_phone = self._phone_clean(self._lead.get("phone") or "")
        self._phone_var = ctk.StringVar(value=raw_phone)
        ctk.CTkEntry(c, textvariable=self._phone_var, height=36,
                     corner_radius=8).pack(fill="x", pady=(4, 12))

        # Templates de mensagem
        from app.session import get_templates
        templates = get_templates(self._session)
        if templates:
            tmpl_row = ctk.CTkFrame(c, fg_color="transparent")
            tmpl_row.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(tmpl_row, text="Template:", font=ctk.CTkFont(size=11),
                         text_color="#9CA3AF").pack(side="left", padx=(0, 6))
            tmpl_names = [t["name"] for t in templates]
            self._tmpl_var = ctk.StringVar(value="— escolher template —")
            tmpl_menu = ctk.CTkOptionMenu(
                tmpl_row,
                values=["— escolher template —"] + tmpl_names,
                variable=self._tmpl_var,
                height=28, corner_radius=6,
                command=self._apply_template,
            )
            tmpl_menu.pack(side="left")

        # Mensagem — linha de título + acções
        msg_row = ctk.CTkFrame(c, fg_color="transparent")
        msg_row.pack(fill="x")
        ctk.CTkLabel(msg_row, text="Mensagem de prospecção",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkButton(
            msg_row, text="💾 Guardar template",
            width=130, height=22,
            fg_color="transparent", hover_color="#1E1E2E",
            text_color="#6B7280", font=ctk.CTkFont(size=10),
            command=self._save_as_template,
        ).pack(side="right")

        # Botão "Gerar copy IA" — só para assinantes
        if self._subscriber:
            self._ai_btn = ctk.CTkButton(
                msg_row, text="✨ Gerar com IA",
                width=120, height=22,
                fg_color="#312E81", hover_color="#3730A3",
                text_color="#C7D2FE", font=ctk.CTkFont(size=10),
                command=self._generate_ai_copy,
            )
            self._ai_btn.pack(side="right", padx=(0, 6))

        self._msg_box = ctk.CTkTextbox(c, height=100, corner_radius=8)
        self._msg_box.insert("1.0", self._DEFAULT_MSG)
        self._msg_box.pack(fill="x", pady=(4, 12))

        # Badge modo
        if self._subscriber:
            badge_text = "✓ Assinante — envio + registo no CRM"
            badge_color = "#10B981"
        else:
            badge_text = "Gratuito — envio local, sem registo no CRM"
            badge_color = "#6B7280"

        ctk.CTkLabel(
            c, text=badge_text,
            fg_color=badge_color, corner_radius=8,
            text_color="white",
            font=ctk.CTkFont(size=10, weight="bold"),
            padx=8, pady=3,
        ).pack(anchor="w", pady=(0, 14))

        # Botões
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(
            row, text="Cancelar",
            fg_color="#2A2A3E", hover_color="#3A3A5E",
            command=self.destroy,
        ).pack(side="left")
        ctk.CTkButton(
            row, text="Enviar via WhatsApp →",
            command=self._start_send,
        ).pack(side="right")

    # ── Copy IA ──────────────────────────────────────────────────────────────

    def _generate_ai_copy(self) -> None:
        if not hasattr(self, "_ai_btn"):
            return
        self._ai_btn.configure(state="disabled", text="A gerar…")

        name = self._lead.get("name", "")
        sector = self._lead.get("sector", "")

        def _do():
            try:
                from app.crm_client import generate_copy
                text = generate_copy(
                    self._session,
                    company_name=name or "Empresa",
                    sector=sector,
                    channel="whatsapp",
                    custom_prompt_template=self._session.get("local_copy_prompt") or "",
                )
                def _apply():
                    self._msg_box.delete("1.0", "end")
                    self._msg_box.insert("1.0", text)
                    try:
                        self._ai_btn.configure(state="normal", text="✨ Gerar com IA")
                    except Exception:
                        pass
                self.after(0, _apply)
            except Exception as exc:
                def _err(e=str(exc)):
                    try:
                        self._ai_btn.configure(state="normal", text="✨ Gerar com IA")
                    except Exception:
                        pass
                    # Mostra toast de erro discreto
                    lbl = ctk.CTkLabel(
                        self._body, text=f"⚠ Erro ao gerar: {e[:60]}",
                        text_color="#EF4444", font=ctk.CTkFont(size=10),
                    )
                    lbl.pack(pady=(0, 4))
                    self.after(4000, lbl.destroy)
                self.after(0, _err)

        threading.Thread(target=_do, daemon=True).start()

    # ── Templates ────────────────────────────────────────────────────────────

    def _apply_template(self, name: str) -> None:
        if name.startswith("—"):
            return
        from app.session import get_templates
        for t in get_templates(self._session):
            if t.get("name") == name:
                self._msg_box.delete("1.0", "end")
                self._msg_box.insert("1.0", t["text"])
                return

    def _save_as_template(self) -> None:
        text = self._msg_box.get("1.0", "end").strip()
        if not text:
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Guardar template")
        popup.geometry("320x150")
        popup.resizable(False, False)
        popup.grab_set()

        ctk.CTkLabel(popup, text="Nome do template:",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(16, 4))
        name_entry = ctk.CTkEntry(popup, height=34, corner_radius=8)
        name_entry.pack(fill="x", padx=20, pady=(0, 12))

        def _confirm() -> None:
            name = name_entry.get().strip()
            if not name:
                return
            from app.session import save_template
            save_template(self._session, name, text)
            popup.destroy()

        ctk.CTkButton(popup, text="Guardar", command=_confirm).pack()

    # ── Passo 2: Enviando ────────────────────────────────────────────────────

    def _show_sending(self) -> None:
        self._clear()
        c = self._body

        ctk.CTkLabel(
            c, text="A enviar mensagem…",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(20, 8))

        self._status_lbl = ctk.CTkLabel(
            c,
            text="A iniciar o Chrome com WhatsApp Web…",
            text_color="#9CA3AF",
            font=ctk.CTkFont(size=12),
            wraplength=440,
        )
        self._status_lbl.pack(pady=4)

        bar = ctk.CTkProgressBar(c, mode="indeterminate")
        bar.pack(fill="x", pady=12)
        bar.start()

        ctk.CTkLabel(
            c,
            text="⚠  Não feches o Chrome enquanto a mensagem está a ser enviada.",
            text_color="#F59E0B",
            font=ctk.CTkFont(size=11),
            wraplength=440,
        ).pack(pady=(0, 8))

    def _update_status(self, msg: str) -> None:
        def _do():
            if hasattr(self, "_status_lbl"):
                try:
                    self._status_lbl.configure(text=msg)
                except Exception:
                    pass
        self.after(0, _do)

    # ── Passo 3: Resultado ───────────────────────────────────────────────────

    def _show_result(self) -> None:
        self._clear()
        c = self._body

        ok = self._result.get("status") == "sent"
        icon = "✅" if ok else "❌"
        title = "Mensagem enviada!" if ok else "Falha no envio"
        color = "#10B981" if ok else "#EF4444"

        ctk.CTkLabel(
            c, text=f"{icon}  {title}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=color,
        ).pack(pady=(20, 8))

        if not ok:
            reason = self._result.get("reason", "Erro desconhecido")
            ctk.CTkLabel(
                c, text=reason,
                text_color="#9CA3AF",
                font=ctk.CTkFont(size=12),
                wraplength=440,
            ).pack(pady=(0, 8))

        # Estado CRM (só assinante + envio ok)
        if ok and self._subscriber:
            crm_ok = self._result.get("crm_status") == "ok"
            if crm_ok:
                crm_txt = "✓ Registado no CRM"
                crm_color = "#10B981"
            else:
                err = self._result.get("crm_error", "")
                crm_txt = f"⚠ CRM não actualizado: {err}" if err else "⚠ CRM não actualizado"
                crm_color = "#F59E0B"
            ctk.CTkLabel(
                c, text=crm_txt,
                text_color=crm_color,
                font=ctk.CTkFont(size=12),
                wraplength=440,
            ).pack(pady=(0, 8))

        ctk.CTkButton(c, text="Fechar", command=self.destroy).pack(pady=(16, 0))

        if ok and callable(self._on_sent):
            try:
                self._on_sent()
            except Exception:
                pass

    # ── Lógica de envio ──────────────────────────────────────────────────────

    def _start_send(self) -> None:
        phone = self._phone_clean(self._phone_var.get().strip())
        message = self._msg_box.get("1.0", "end").strip()
        if not phone or not message:
            return
        self._phone_final = phone
        self._msg_final = message
        self._show_sending()
        threading.Thread(target=self._do_send, daemon=True).start()

    def _do_send(self) -> None:
        from app.whatsapp_client import send_message
        result = send_message(
            self._phone_final,
            self._msg_final,
            on_progress=self._update_status,
        )
        self._result = result

        if result["status"] == "sent" and self._subscriber:
            self._update_status("A registar no CRM…")
            self._do_crm_sync()
        elif not self._subscriber:
            from app.session import upsert_local_lead
            upsert_local_lead(
                self._session,
                phone=self._phone_final,
                name=self._lead.get("name", "Lead"),
                category="qualification" if result["status"] == "sent" else "to-prospect",
                website=self._lead.get("website", ""),
                address=self._lead.get("address", ""),
                customMessage=self._msg_final,
            )

        self.after(0, self._show_result)

    def _do_crm_sync(self) -> None:
        """Cria lead no CRM e regista outbound. Idempotente: usa lead existente se phone duplicado."""
        try:
            from app.crm_client import create_lead, log_outbound

            lead_resp = create_lead(
                self._session,
                name=self._lead.get("name", "Lead"),
                phone=self._phone_final,
                website=self._lead.get("website", ""),
                address=self._lead.get("address", ""),
            )
            lead_id = lead_resp.get("id") or lead_resp.get("lead_id")
            if lead_id:
                log_outbound(self._session, lead_id, self._msg_final)
                self._result["crm_status"] = "ok"
                self._result["crm_lead_id"] = str(lead_id)
            else:
                self._result["crm_status"] = "error"
                self._result["crm_error"] = "lead_id não retornado"

        except Exception as exc:
            logger_msg = str(exc)
            self._result["crm_status"] = "error"
            self._result["crm_error"] = logger_msg[:120]
