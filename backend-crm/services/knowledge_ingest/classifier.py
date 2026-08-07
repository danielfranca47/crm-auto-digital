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
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_TIMEOUT_SECONDS = 120
_MAX_TOTAL_CHARS = 60_000
_MIN_CONTENT_CHARS = 20

# service_pricing_table é a única categoria allowMultiple (ver docs/architecture/knowledge-base.md)
# — pedimos ao LLM linhas estruturadas em vez de texto livre para o item já nascer editável como
# tabela na UI (ServicePricingTables.tsx), sem exigir conversão manual depois.
_PRICING_TABLE_KEY = "service_pricing_table"


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

    if any(cat.get("key") == _PRICING_TABLE_KEY for cat in categories):
        lines.append(
            f"REGRA ESPECIAL PARA '{_PRICING_TABLE_KEY}': em vez de \"content\" (texto), "
            'retorne "rows": uma lista com um objeto por serviço/pacote encontrado nas fontes, '
            'no formato {"nome": "<nome do serviço>", "duracaoMinutos": <número ou null>, '
            '"preco": "<preço como texto, ex.: \'R$150\'>", "descricao": "<opcional>"}. '
            "Preserve nomes, preços e durações exactamente como aparecem nas fontes."
        )
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
        '{"categories": {"<key da categoria>": {"content": "<texto>", "source_refs": [<índices>]} '
        f'ou {{"rows": [...], "source_refs": [...]}} para \'{_PRICING_TABLE_KEY}\' (ver regra '
        'especial acima) ou null}}'
    )
    return "\n".join(lines)


def _serialize_pricing_rows(raw_rows: Any) -> Optional[str]:
    """
    Normaliza "rows" devolvido pelo LLM para o mesmo JSON structured_v1 que
    ServicePricingTables.tsx:serializeServicePricingRows() produz no frontend —
    mesmo schema, para o item nascer editável como tabela sem conversão manual.
    Retorna None se raw_rows não for uma lista utilizável (nenhuma linha com nome).
    """
    if not isinstance(raw_rows, list):
        return None

    rows: List[Dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        nome = str(raw.get("nome") or "").strip()
        if not nome:
            continue
        duracao = raw.get("duracaoMinutos")
        duracao = duracao if isinstance(duracao, (int, float)) and not isinstance(duracao, bool) else None
        descricao = str(raw.get("descricao") or "").strip()
        row: Dict[str, Any] = {
            "nome": nome,
            "duracaoMinutos": duracao,
            "preco": str(raw.get("preco") or "").strip(),
        }
        if descricao:
            row["descricao"] = descricao
        rows.append(row)

    if not rows:
        return None
    return json.dumps({"format": "structured_v1", "rows": rows}, ensure_ascii=False)


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
        refs = entry.get("source_refs")
        refs = [r for r in refs if isinstance(r, int)] if isinstance(refs, list) else []

        content: Optional[str] = None
        if key == _PRICING_TABLE_KEY:
            content = _serialize_pricing_rows(entry.get("rows"))
        if content is None:
            # categoria normal, ou o LLM ignorou a regra especial de rows — trata como texto livre
            content = (entry.get("content") or "").strip()
            if len(content) < _MIN_CONTENT_CHARS:
                continue
        result[key] = {"content": content, "source_refs": refs}

    logger.info(
        "[knowledge_ingest] classificador: %d/%d categorias cobertas",
        len(result),
        len(valid_keys),
    )
    return result
