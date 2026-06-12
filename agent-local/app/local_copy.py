"""Geração local de copy com IA — modo gratuito (chave OpenAI própria do utilizador).

Chama a OpenAI directamente, sem passar pelo backend-crm — necessário porque
`/api/prospeccao/generate-copy` exige assinatura activa (`require_crm_access`).
O prompt replica o padrão `business_ctx` da Fase 7
(`backend-crm/routes/prospeccao.py::generate_copy`), mas usa o
`local_business_profile` preenchido localmente em vez do AI Profile pago.
"""
from __future__ import annotations

import os

_CHANNEL_LABELS = {
    "whatsapp": "WhatsApp",
    "email": "email",
    "instagram": "Instagram",
    "call": "chamada",
}


class LocalCopyError(Exception):
    """Erro accionável — a UI deve mostrar `str(exc)` directamente ao utilizador."""


def generate_copy_local(
    session: dict,
    *,
    company_name: str,
    sector: str = "",
    contact_name: str = "",
    channel: str = "whatsapp",
    tone: str = "profissional e próximo",
) -> str:
    api_key = (session or {}).get("openai_api_key") or ""
    if not api_key.strip():
        raise LocalCopyError(
            "Configura a tua chave OpenAI API em ⚙ Conta antes de gerar copys."
        )

    profile = (session or {}).get("local_business_profile") or {}
    niche = (profile.get("niche") or "").strip()
    offer = (profile.get("offer_description") or "").strip()
    audience = (profile.get("target_audience") or "").strip()
    brand = (profile.get("brand_name") or "").strip()
    if not (niche or offer or audience or brand):
        raise LocalCopyError(
            "Preenche as tuas informações de negócio antes de gerar copys "
            "(nicho, oferta, público-alvo ou marca)."
        )

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    contact_part = f" para {contact_name}" if contact_name.strip() else ""
    sector_part = f" no setor de {sector}" if sector.strip() else ""
    channel_label = _CHANNEL_LABELS.get(channel, channel)

    business_ctx = ""
    parts = []
    if brand:
        parts.append(f"Empresa remetente: {brand}")
    if niche:
        parts.append(f"Nicho: {niche}")
    if offer:
        parts.append(f"Oferta: {offer}")
    if audience:
        parts.append(f"Público-alvo: {audience}")
    if parts:
        business_ctx = "\n".join(parts) + "\n"

    custom_template = (session or {}).get("local_copy_prompt") or ""
    if custom_template.strip():
        _var_map = {
            "[empresa]": company_name,
            "[nome da empresa do lead]": company_name,
            "[setor]": sector,
            "[contacto]": contact_name,
            "[canal]": channel_label,
            "[tom]": tone,
            "[nicho]": niche,
            "[oferta]": offer,
            "[marca]": brand,
        }
        script = custom_template
        for placeholder, value in _var_map.items():
            script = script.replace(placeholder, value or "")
        prompt = (
            f"Usa este script como referência e gera uma mensagem de prospecção "
            f"personalizada para a empresa {company_name}. "
            f"Adapta o tom e os detalhes para soar natural e directo — não copies "
            f"literalmente, gera uma variação. "
            f"NUNCA uses placeholders como [Seu Nome] ou [Sua Empresa]. "
            f"Máximo 3 frases curtas. Responde APENAS com o texto da mensagem.\n\n"
            f"Script de referência:\n{script}"
        )
    else:
        prompt = (
            f"{business_ctx}"
            f"Escreve uma mensagem de prospecção via {channel_label} para a empresa {company_name}"
            f"{sector_part}{contact_part}. "
            f"Tom: {tone}. "
            f"A oferta deve reflectir o nicho e o produto/serviço do remetente acima — "
            f"não inventes temas genéricos (ex.: marketing digital, limpeza de equipamentos) "
            f"que não tenham relação com a oferta indicada. "
            f"NUNCA uses placeholders como [Seu Nome] ou [Sua Empresa]; usa os dados reais do remetente fornecidos "
            f"ou, na ausência deles, fala apenas em nome da empresa do destinatário sem te apresentares por nome. "
            f"Máximo 3 frases curtas e directas. Não uses saudações genéricas. "
            f"Apresenta uma proposta de valor clara e termina com uma pergunta ou CTA simples. "
            f"Responde APENAS com o texto da mensagem, sem explicações adicionais."
        )

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.7,
        )
    except Exception as exc:
        raise LocalCopyError(f"Erro ao chamar a OpenAI: {exc}") from exc

    return response.choices[0].message.content.strip()
