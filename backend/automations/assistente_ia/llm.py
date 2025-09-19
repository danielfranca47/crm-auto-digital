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
        sender: Optional[Dict] = None  # 👈 novo: dados do remetente (profile)
    ) -> Dict[str, Dict]:
        ctx = context or {}
        scenario = self._choose_scenario(ctx)
        ctx_summary = self._ctx_summary(ctx)
        out: Dict[str, Dict] = {}

        sender = sender or {}
        s_name = sender.get("name") or ""
        s_company = sender.get("company") or ""
        s_email = sender.get("email") or ""
        s_phone = sender.get("phone") or ""
        s_signature = sender.get("signature") or ""

        if not self.enabled:
            # MOCK para desenvolvimento local (sem API)
            for ch in channels:
                if ch == "email":
                    out[ch] = {
                        "subject": f"Ideias rápidas para {lead['companyName']}",
                        "body": (
                            f"Olá, {{prospect.company}}, tudo bem?\n\n"
                            f"Cenário: {scenario}. {ctx_summary}\n"
                            f"Posso enviar 2 ideias com valores?\n\n"
                            f"{{sender.signature}}"
                        ),
                        "model": "mock"
                    }
                elif ch == "whatsapp":
                    out[ch] = {"body": (
                        f"Olá, {{prospect.company}}!\n"
                        f"Notei uma oportunidade ({scenario}). {ctx_summary}\n"
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
        common = (
            f"Empresa do prospect: {lead['companyName']}\n"
            f"Cenário: {scenario}\n"
            f"Contexto: {ctx_summary}\n"
            f"Remetente: Nome={s_name}; Empresa={s_company}; Email={s_email}; Telefone={s_phone}\n"
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
                      "Se cenário='no_site': proponha site próprio com CTA/WhatsApp.\n"
                      "Se cenário='weak_site': 2–3 melhorias rápidas (mobile/HTTPS/SEO) + convite para call de 15 min.\n"
                      "Se cenário='decent_site': foque em automações de captação (form->WhatsApp, agendador, chat) e teste-piloto.\n"
                      "Retorne como JSON: {\"subject\":\"...\",\"body\":\"...\"}\n"
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
