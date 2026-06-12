"""Onboarding wizard multi-step diferenciado por perfil (assinante vs gratuito)."""
from __future__ import annotations

import webbrowser
from typing import Callable, List

import customtkinter as ctk
from app.session import is_subscriber, save_session

LANDING_PAGE_URL = "https://danielfranca.pt/lara-ia"


class OnboardingScreen(ctk.CTkFrame):
    def __init__(self, master, session_data: dict, on_done: Callable):
        super().__init__(master, fg_color="#12121F")
        self._session = session_data
        self._on_done = on_done
        self._step = 0
        self._subscriber = is_subscriber(session_data)
        self._name = (session_data.get("name") or "").split()[0] or "utilizador"

        self._steps: List[Callable] = (
            [self._step_welcome, self._step_how_search, self._step_how_export]
            if self._subscriber
            else [self._step_welcome, self._step_selenium, self._step_upgrade, self._step_how_start]
        )

        self._build_shell()
        self._render_step()

    # ── Shell (estrutura fixa) ────────────────────────────────────────────────

    def _build_shell(self):
        # Header: indicador de progresso
        indicator = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=0, height=52)
        indicator.pack(fill="x")
        indicator.pack_propagate(False)

        self._step_label = ctk.CTkLabel(
            indicator, text="",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        )
        self._step_label.pack(side="left", padx=20)

        self._dots_label = ctk.CTkLabel(
            indicator, text="",
            font=ctk.CTkFont(size=14), text_color="#6B7280",
        )
        self._dots_label.pack(side="right", padx=20)

        # Footer: botões de navegação (side="bottom" para garantir visibilidade)
        nav_outer = ctk.CTkFrame(self, fg_color="#1E1E2E", corner_radius=0, height=72)
        nav_outer.pack(fill="x", side="bottom")
        nav_outer.pack_propagate(False)

        nav_inner = ctk.CTkFrame(nav_outer, fg_color="transparent")
        nav_inner.pack(fill="both", expand=True, padx=24)

        self._prev_btn = ctk.CTkButton(
            nav_inner, text="← Anterior", width=120, height=40,
            fg_color="#2A2A3E", hover_color="#3A3A5E",
            font=ctk.CTkFont(size=13),
            command=self._go_prev,
        )
        self._prev_btn.pack(side="left", pady=16)

        self._next_btn = ctk.CTkButton(
            nav_inner, text="Próximo →", width=160, height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._go_next,
        )
        self._next_btn.pack(side="right", pady=16)

        # Área de conteúdo (entre header e footer)
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True)

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _render_step(self):
        for w in self._content_frame.winfo_children():
            w.destroy()

        total = len(self._steps)
        current = self._step + 1

        self._step_label.configure(text=f"Passo {current} de {total}")
        dots = "  ".join("●" if i == self._step else "○" for i in range(total))
        self._dots_label.configure(text=dots)

        self._prev_btn.configure(state="normal" if self._step > 0 else "disabled")

        is_last = self._step == total - 1
        self._next_btn.configure(
            text="Começar a pesquisar →" if is_last else "Próximo →",
            width=210 if is_last else 160,
        )

        self._steps[self._step](self._content_frame)

    def _go_next(self):
        if self._step >= len(self._steps) - 1:
            self._finish()
        else:
            self._step += 1
            self._render_step()

    def _go_prev(self):
        if self._step > 0:
            self._step -= 1
            self._render_step()

    def _finish(self):
        self._session["onboarding_done"] = True
        save_session(self._session)
        self._on_done()

    # ── Passos comuns ─────────────────────────────────────────────────────────

    def _step_welcome(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color="#1E1E2E", corner_radius=16)
        card.pack(expand=True, padx=40, pady=28, fill="both")

        ctk.CTkLabel(card, text="👋", font=ctk.CTkFont(size=52)).pack(pady=(36, 6))
        ctk.CTkLabel(
            card, text=f"Olá, {self._name}!",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack()

        if self._subscriber:
            badge_text, badge_color = "✓ Assinante", "#10B981"
            msg = "Bem-vindo ao Gerador de Leads Digital Pro.\nA tua assinatura está ativa — todas as\nfuncionalidades estão disponíveis."
        else:
            badge_text, badge_color = "Plano Gratuito", "#6B7280"
            msg = "A tua conta está pronta!\nPodes começar a gerar leads gratuitamente\ne exportar para Excel."

        ctk.CTkLabel(
            card, text=badge_text,
            fg_color=badge_color, corner_radius=12,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white", padx=12, pady=5,
        ).pack(pady=(12, 16))

        ctk.CTkLabel(
            card, text=msg,
            font=ctk.CTkFont(size=13), text_color="#9CA3AF",
            justify="center",
        ).pack(pady=(0, 36))

    # ── Passos assinante ──────────────────────────────────────────────────────

    def _step_how_search(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color="#1E1E2E", corner_radius=16)
        card.pack(expand=True, padx=40, pady=28, fill="both")

        ctk.CTkLabel(card, text="🔍", font=ctk.CTkFont(size=38)).pack(pady=(28, 4))
        ctk.CTkLabel(
            card, text="Como pesquisar",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="Preenche 3 campos e clica em Pesquisar:",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack(pady=(8, 14))

        fields_frame = ctk.CTkFrame(card, fg_color="#12121F", corner_radius=10)
        fields_frame.pack(padx=32, fill="x")

        for label, example in [
            ("Nicho / Tipo de negócio", "ex: dentistas"),
            ("Cidade / Região", "ex: São Paulo, SP"),
            ("Limite", "10 / 20 / 40 / 60 resultados"),
        ]:
            row = ctk.CTkFrame(fields_frame, fg_color="transparent")
            row.pack(padx=16, pady=(8, 2), fill="x")
            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(size=11, weight="bold"), text_color="#9CA3AF", anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                row, text=f"  {example}",
                font=ctk.CTkFont(size=12), fg_color="#2A2A3E", corner_radius=6,
                text_color="#E5E7EB", anchor="w", height=30,
            ).pack(fill="x", pady=(2, 0))

        ctk.CTkFrame(fields_frame, fg_color="transparent", height=8).pack()

        ctk.CTkLabel(
            card,
            text="💡 Modo Assinante — chave API incluída, resultados instantâneos.",
            font=ctk.CTkFont(size=11), text_color="#10B981",
        ).pack(pady=(14, 16))

    def _step_how_export(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color="#1E1E2E", corner_radius=16)
        card.pack(expand=True, padx=40, pady=28, fill="both")

        ctk.CTkLabel(card, text="📥", font=ctk.CTkFont(size=38)).pack(pady=(28, 4))
        ctk.CTkLabel(
            card, text="Como exportar os leads",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="Após a pesquisa, um clique guarda tudo no Excel:",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack(pady=(8, 16))

        steps_frame = ctk.CTkFrame(card, fg_color="transparent")
        steps_frame.pack(padx=32, fill="x")

        for num, text in [
            ("1", "Faz a pesquisa com o nicho e cidade pretendidos"),
            ("2", 'Clica em  "📥 Exportar Excel"  nos resultados'),
            ("3", "Escolhe a pasta no teu PC e confirma o nome"),
            ("4", "Abre o ficheiro .xlsx — dados prontos para usar!"),
        ]:
            row = ctk.CTkFrame(steps_frame, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(
                row, text=num,
                fg_color="#3B82F6", corner_radius=10,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white", width=24, height=24,
            ).pack(side="left", padx=(0, 12))
            ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(size=12), text_color="#E5E7EB", anchor="w",
            ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            card,
            text="Colunas: Nome · Telefone · Website · Endereço · Avaliação · Nº Avaliações · Link Maps",
            font=ctk.CTkFont(size=10), text_color="#4B5563",
            wraplength=480, justify="center",
        ).pack(pady=(14, 16))

    # ── Passos gratuito ───────────────────────────────────────────────────────

    def _step_selenium(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color="#1E1E2E", corner_radius=16)
        card.pack(expand=True, padx=40, pady=28, fill="both")

        ctk.CTkLabel(card, text="🌐", font=ctk.CTkFont(size=38)).pack(pady=(28, 4))
        ctk.CTkLabel(
            card, text="Modo Gratuito — Chrome Automático",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="Como funciona a pesquisa no plano gratuito:",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack(pady=(8, 14))

        info_frame = ctk.CTkFrame(card, fg_color="#12121F", corner_radius=10)
        info_frame.pack(padx=32, fill="x")

        for icon, text in [
            ("🖥️", "O app abre o Chrome automaticamente"),
            ("🗺️", "Navega para o Google Maps e faz a pesquisa"),
            ("📋", "Recolhe os leads e fecha o Chrome sozinho"),
            ("⏱️", "Demora 30–90 segundos (mais lento que com API)"),
        ]:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=15), width=28).pack(side="left")
            ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(size=12), text_color="#E5E7EB", anchor="w",
            ).pack(side="left", padx=4)

        ctk.CTkFrame(info_frame, fg_color="transparent", height=6).pack()

        ctk.CTkLabel(
            card,
            text="💡 Dica: configura a tua chave Google Maps API em ⚙ Configurações para pesquisas mais rápidas.",
            font=ctk.CTkFont(size=11), text_color="#6B7280",
            wraplength=480, justify="center",
        ).pack(pady=(14, 14))

    def _step_upgrade(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color="#1E1E2E", corner_radius=16)
        card.pack(expand=True, padx=40, pady=28, fill="both")

        ctk.CTkLabel(card, text="⭐", font=ctk.CTkFont(size=38)).pack(pady=(24, 4))
        ctk.CTkLabel(
            card, text="Plano Digital Pro",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="Pesquisas muito mais rápidas e sem preocupações",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack(pady=(4, 14))

        benefits_frame = ctk.CTkFrame(card, fg_color="#12121F", corner_radius=10)
        benefits_frame.pack(padx=32, fill="x")

        for text in [
            "Pesquisas via API oficial (10× mais rápido que Selenium)",
            "Chave Google Maps incluída — sem custo extra",
            "Maior volume de leads por pesquisa",
            "Resultados mais fiáveis e completos",
        ]:
            row = ctk.CTkFrame(benefits_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(
                row, text="✓",
                font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981", width=20,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(size=12), text_color="#E5E7EB", anchor="w",
            ).pack(side="left", padx=6, fill="x", expand=True)

        ctk.CTkFrame(benefits_frame, fg_color="transparent", height=6).pack()

        ctk.CTkButton(
            card,
            text="Ver planos →",
            height=38, corner_radius=8,
            fg_color="#10B981", hover_color="#059669",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: webbrowser.open(LANDING_PAGE_URL),
        ).pack(padx=60, pady=(16, 8), fill="x")

    def _step_how_start(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color="#1E1E2E", corner_radius=16)
        card.pack(expand=True, padx=40, pady=28, fill="both")

        ctk.CTkLabel(card, text="🚀", font=ctk.CTkFont(size=38)).pack(pady=(28, 4))
        ctk.CTkLabel(
            card, text="Está tudo pronto!",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack()
        ctk.CTkLabel(
            card, text="Para gerar os teus primeiros leads:",
            font=ctk.CTkFont(size=12), text_color="#9CA3AF",
        ).pack(pady=(8, 14))

        steps_frame = ctk.CTkFrame(card, fg_color="transparent")
        steps_frame.pack(padx=32, fill="x")

        for num, text in [
            ("1", "Escreve o tipo de negócio que procuras (ex: pizzarias)"),
            ("2", "Indica a cidade ou região (ex: Lisboa)"),
            ("3", "Escolhe quantos leads queres (10 a 60)"),
            ("4", "Clica em  🔍 Pesquisar  e aguarda o Chrome trabalhar"),
        ]:
            row = ctk.CTkFrame(steps_frame, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(
                row, text=num,
                fg_color="#6B7280", corner_radius=10,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white", width=24, height=24,
            ).pack(side="left", padx=(0, 12))
            ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(size=12), text_color="#E5E7EB", anchor="w",
            ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            card,
            text="Depois exporta os resultados para Excel com um clique! 📥",
            font=ctk.CTkFont(size=12), text_color="#6B7280",
        ).pack(pady=(14, 16))
