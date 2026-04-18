# automations/assistente_ia/llm.py
import os
from typing import Dict, List, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

DEFAULT_MODEL = "gpt-3.5-turbo"

class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = bool(self.api_key and OpenAI is not None)
        if self.enabled:
            self.client = OpenAI(api_key=self.api_key)

    # -------- helpers de cenário --------
    def _choose_scenario(self, ctx: Dict) -> str:
        if ctx.get("no_own_site") or (ctx.get("website_kind") in {"social","messaging","directory","link_aggregator","builder_hosted"}):
            return "no_site"
        issues = int(ctx.get("issues_count") or 0)
        if (not ctx.get("mobile_ready")) or (not ctx.get("ssl_ok")) or issues >= 5:
            return "weak_site"
        return "decent_site"

    def _format_outreach_scenarios(self, scenarios: list) -> str:
        """Formata os cenários dinâmicos do meta-prompter para injeção no prompt."""
        if not scenarios:
            return ""
        lines = ["Cenários de prospecção para este nicho:"]
        for sc in scenarios:
            lines.append(
                f"- [{sc.get('scenario_key', '')}] {sc.get('description', '')}"
                f" | WhatsApp: {sc.get('whatsapp_angle', '')}"
                f" | CTA: {sc.get('cta', '')}"
            )
        return "\n".join(lines)

    def _format_legacy_scenario(self, scenario: str, ctx_summary: str) -> str:
        """Formata o cenário legado (no_site / weak_site / decent_site)."""
        return f"Cenário: {scenario}\nContexto: {ctx_summary}"

    def _ctx_summary(self, ctx: Dict) -> str:
        parts = []
        if ctx.get("website_kind"): parts.append(f"tipo_site={ctx['website_kind']}")
        if ctx.get("own_domain"): parts.append("dominio_proprio=sim")
        if ctx.get("no_own_site"): parts.append("sem_site_proprio=sim")
        if ctx.get("mobile_ready") is not None: parts.append(f"mobile={'ok' if ctx['mobile_ready'] else 'x'}")
        if ctx.get("ssl_ok") is not None: parts.append(f"https={'ok' if ctx['ssl_ok'] else 'x'}")
        if ctx.get("issues_count") is not None: parts.append(f"issues={ctx['issues_count']}")
        if ctx.get("services_keywords"): parts.append(f"servicos={ctx['services_keywords']}")
        if ctx.get("instagram_handle"): parts.append(f"ig=@{ctx['instagram_handle']}")
        if ctx.get("trust_score_adj") is not None: parts.append(f"trust_adj={ctx['trust_score_adj']}")
        if ctx.get("next_action"): parts.append(f"proxima_acao={ctx['next_action']}")
        return " | ".join(parts)

    # -------- geração principal --------
    def generate_for_lead(
        self,
        lead: Dict,                   # {id, companyName, contactName, email, phone, ...}
        channels: List[str],
        tone: Optional[str],
        language: Optional[str],
        context: Optional[Dict] = None,
        sender: Optional[Dict] = None,  # dados do remetente (profile)
        ai_profile: Optional[Dict] = None,  # ai_profile com generated_prompt_parts (Tarefa 4.3)
    ) -> Dict[str, Dict]:
        ctx = context or {}
        ctx_summary = self._ctx_summary(ctx)
        out: Dict[str, Dict] = {}

        # Tarefa 4.3 — usar cenários dinâmicos do nicho quando disponíveis
        prompt_parts = (ai_profile or {}).get("generated_prompt_parts") or {}
        outreach_scenarios = prompt_parts.get("outreach_scenarios")
        if outreach_scenarios:
            scenario_context = self._format_outreach_scenarios(outreach_scenarios)
            scenario = None  # não usado quando cenários dinâmicos estão ativos
        else:
            # Fallback para cenários fixos existentes (legado)
            scenario = self._choose_scenario(ctx)
            scenario_context = self._format_legacy_scenario(scenario, ctx_summary)

        sender = sender or {}
        s_name = sender.get("name") or ""
        s_company = sender.get("company") or ""
        s_email = sender.get("email") or ""
        s_phone = sender.get("phone") or ""
        s_signature = sender.get("signature") or ""

        # Contexto do AI Profile (negócio do remetente)
        _ap = ai_profile or {}
        ap_niche = _ap.get("niche") or ""
        ap_offer = _ap.get("offer_description") or ""
        ap_audience = _ap.get("target_audience") or ""
        ap_brand = _ap.get("brand_name") or s_company

        if not self.enabled:
            # MOCK para desenvolvimento local (sem API)
            for ch in channels:
                if ch == "email":
                    out[ch] = {
                        "subject": f"Ideias rápidas para {lead['companyName']}",
                        "body": (
                            f"Olá, {{prospect.company}}, tudo bem?\n\n"
                            f"{scenario_context}\n"
                            f"Posso enviar 2 ideias com valores?\n\n"
                            f"{{sender.signature}}"
                        ),
                        "model": "mock"
                    }
                elif ch == "whatsapp":
                    out[ch] = {"body": (
                        f"Olá, {{prospect.company}}!\n"
                        f"{scenario_context}\n"
                        f"Posso enviar 2 ideias e valores?\n\n"
                        f"— {{sender.name}}, {{sender.company}}"
                    ), "model": "mock"}
                elif ch == "instagram":
                    out[ch] = {"body": (
                        f"Oi, {ctx.get('instagram_handle','equipe')}!\n"
                        f"Pensei em 2 ideias para {{prospect.company}}. Envio por aqui?"
                    ), "model": "mock"}
                elif ch == "call":
                    out[ch] = {"body": (
                        "Abertura (10–15s) → 2–3 perguntas → pitch 20s (site/automação) → CTA: enviar ideias/valores hoje."
                    ), "model": "mock"}
            return out

        # ---------- prompts reais ----------
        # Contexto comum a todos os canais
        business_ctx = ""
        if ap_niche or ap_offer or ap_audience:
            parts = []
            if ap_brand: parts.append(f"Empresa remetente: {ap_brand}")
            if ap_niche: parts.append(f"Nicho: {ap_niche}")
            if ap_offer: parts.append(f"Oferta: {ap_offer}")
            if ap_audience: parts.append(f"Público-alvo: {ap_audience}")
            business_ctx = "\n".join(parts) + "\n"

        common = (
            f"Empresa do prospect: {lead['companyName']}\n"
            f"{scenario_context}\n"
            f"{business_ctx}"
            f"Remetente: Nome={s_name}; Empresa={ap_brand or s_company}; Email={s_email}; Telefone={s_phone}\n"
            "NUNCA use placeholders como [Seu Nome] ou [Sua Empresa]; use os dados do Remetente fornecidos.\n"
            "Se contactName estiver vazio, cumprimente pela empresa (ex.: 'Olá, A Casa do Porco Bar').\n"
        )

        for ch in channels:
            if ch == "email":
                prompt = (
                    common
                    + f"Escreva um e-mail em {language or 'pt-PT'} com tom {tone or 'profissional'}.\n"
                      "Regras: assunto <= 60 caracteres; corpo com 120–180 palavras; sem links; "
                      "parágrafos separados por uma linha em branco; CTA final: 'Posso enviar 2 ideias e valores?'.\n"
                    + (
                        "Use os cenários de prospecção do nicho fornecidos acima para escolher o ângulo mais relevante.\n"
                        if outreach_scenarios else
                        "Se cenário='no_site': proponha site próprio com CTA/WhatsApp.\n"
                        "Se cenário='weak_site': 2–3 melhorias rápidas (mobile/HTTPS/SEO) + convite para call de 15 min.\n"
                        "Se cenário='decent_site': foque em automações de captação (form->WhatsApp, agendador, chat) e teste-piloto.\n"
                    )
                    + "Retorne como JSON: {\"subject\":\"...\",\"body\":\"...\"}\n"
                      "Use as variáveis literais {{prospect.company}} e {{sender.signature}} nos locais apropriados (serão interpoladas depois)."
                )
                data = self._chat_json(prompt, temperature=0.5)
                out[ch] = {"subject": data.get("subject","Assunto"), "body": data.get("body",""), "model": self.model}

            elif ch == "whatsapp":
                prompt = (
                    common
                    + f"Escreva uma mensagem de WhatsApp em {language or 'pt-PT'} com tom {tone or 'profissional'}.\n"
                      "Comprimento: 4–6 linhas; sem links; CTA final pedindo permissão para enviar 2 ideias e valores.\n"
                      "Use {{prospect.company}} onde a empresa deva aparecer e assine como '{{sender.name}}, {{sender.company}}'."
                )
                out[ch] = {"body": self._chat_text(prompt, temperature=0.5), "model": self.model}

            elif ch == "instagram":
                prompt = (
                    common
                    + f"Escreva uma DM curta em {language or 'pt-PT'} com tom {tone or 'profissional'}.\n"
                      "Comprimento: 2–4 linhas; amigável; sem parecer spam; CTA: posso enviar 2 ideias curtas?\n"
                      "Use {{prospect.company}} e '@handle' se existir."
                )
                out[ch] = {"body": self._chat_text(prompt, temperature=0.5), "model": self.model}

            elif ch == "call":
                prompt = (
                    common
                    + f"Monte um roteiro de ligação em {language or 'pt-PT'} com bullets: abertura (10–15s), 2–3 perguntas, "
                      "pitch 20s (site/automação) e CTA de próximo passo."
                )
                out[ch] = {"body": self._chat_text(prompt, temperature=0.4), "model": self.model}

        return out

    # -------- chamadas OpenAI --------
    def _chat_text(self, prompt: str, temperature: float = 0.5) -> str:
        r = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Você é um assistente de prospecção objetivo e cordial."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        return r.choices[0].message.content.strip()

    def _chat_json(self, prompt: str, temperature: float = 0.5) -> Dict:
        r = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Você escreve e-mails comerciais objetivos e cordiais."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        import json
        return json.loads(r.choices[0].message.content or "{}")
