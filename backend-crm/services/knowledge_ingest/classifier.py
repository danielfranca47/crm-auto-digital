"""
classifier.py — Classificação LLM dos textos extraídos nas categorias da base.

Recebe os textos das fontes (já extraídos) + a lista de categorias guiadas do
template do agente + o contexto do negócio, e retorna um mapa
categoria → conteúdo extraído (ou nada, se as fontes não cobrirem a categoria).

Modelo: gpt-4o-mini com response_format=json_object e temperature=0 — mesmo
modelo já usado no projeto para vision (spy media), barato e suficiente para
extração estruturada. O prompt restringe a resposta ao conteúdo das fontes
para mitigar alucinação.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_TIMEOUT_SECONDS = 120
_MAX_TOTAL_CHARS = 60_000
_MIN_CONTENT_CHARS = 20


def _build_prompt(
    sources: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> str:
    lines: List[str] = []

    lines.append("CONTEXTO DO NEGÓCIO:")
    lines.append(f"- Nicho: {context.get('niche') or 'não informado'}")
    lines.append(f"- Público-alvo: {context.get('audience') or 'não informado'}")
    lines.append(f"- Oferta principal: {context.get('offer') or 'não informado'}")
    lines.append("")

    lines.append("CATEGORIAS DA BASE DE CONHECIMENTO:")
    for cat in categories:
        key = cat.get("key") or ""
        label = cat.get("label") or key
        description = cat.get("description") or ""
        lines.append(f"- {key} — {label}: {description}")
    lines.append("")

    lines.append("FONTES:")
    total = 0
    for idx, src in enumerate(sources):
        origin = src.get("url") or src.get("filename") or f"fonte {idx}"
        description = src.get("description") or ""
        header = f"[{idx}] {origin}"
        if description:
            header += f' (descrição do usuário: "{description}")'
        text = src.get("text") or ""
        remaining = _MAX_TOTAL_CHARS - total
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining]
        total += len(text)
        lines.append(header)
        lines.append(text)
        lines.append("---")
    lines.append("")

    lines.append(
        "INSTRUÇÕES:\n"
        "Para cada categoria listada acima, extraia e reorganize o conteúdo relevante "
        "das fontes, em português, pronto para um agente de WhatsApp usar em conversas "
        "com leads. Preserve valores, preços, horários e nomes exatamente como estão "
        "nas fontes. Se as fontes não cobrirem uma categoria, use null para ela. "
        "Não repita o mesmo conteúdo em várias categorias; priorize a mais específica.\n\n"
        "Responda com JSON exatamente neste formato:\n"
        '{"categories": {"<key da categoria>": {"content": "<texto>", "source_refs": [<índices das fontes usadas>]} ou null}}'
    )
    return "\n".join(lines)


def classify_sources(
    sources: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Retorna {category_key: {"content": str, "source_refs": [int]}} apenas para as
    categorias que o LLM conseguiu cobrir com conteúdo válido (≥ 20 chars).
    Levanta exceção em falha de API — o worker decide retry/failed.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY ausente — classificação impossível")

    valid_keys = {c.get("key") for c in categories if c.get("key")}
    if not valid_keys or not sources:
        return {}

    prompt = _build_prompt(sources, categories, context)

    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _MODEL,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Você organiza a base de conhecimento de um agente de vendas e "
                            "atendimento no WhatsApp. Use SOMENTE informação presente nas "
                            "fontes fornecidas; NUNCA invente dados, preços, horários ou "
                            "nomes. Responda apenas com JSON válido."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    raw = data["choices"][0]["message"]["content"] or "{}"
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"resposta do classificador não é JSON válido: {exc}")

    result: Dict[str, Dict[str, Any]] = {}
    for key, entry in (parsed.get("categories") or {}).items():
        if key not in valid_keys or not isinstance(entry, dict):
            continue
        content = (entry.get("content") or "").strip()
        if len(content) < _MIN_CONTENT_CHARS:
            continue
        refs = entry.get("source_refs")
        refs = [r for r in refs if isinstance(r, int)] if isinstance(refs, list) else []
        result[key] = {"content": content, "source_refs": refs}

    logger.info(
        "[knowledge_ingest] classificador: %d/%d categorias cobertas",
        len(result),
        len(valid_keys),
    )
    return result
