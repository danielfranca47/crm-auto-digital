from __future__ import annotations

from typing import Any, Dict, List


_SUPPORTED_FEATURES = [
    {
        "feature": "Mensagens de texto",
        "mapped_field": "custom_instructions / offer_description",
        "notes": "Totalmente suportado.",
    },
    {
        "feature": "Áudio",
        "mapped_field": "custom_instructions",
        "notes": "Transcrição automática disponível — o conteúdo do áudio é convertido em texto antes da análise.",
    },
    {
        "feature": "Imagem",
        "mapped_field": "offer_pack / warming_session_preview",
        "notes": "Interpretação visual disponível — imagens são analisadas para extrair contexto.",
    },
]

_UNSUPPORTED_FEATURES = [
    {
        "feature": "Vídeo",
        "reason": "Análise de vídeo tem custo elevado e não é suportada atualmente.",
        "workaround": (
            "Se você costuma enviar vídeos nas conversas, escreva uma mensagem de texto logo após "
            "descrevendo o conteúdo do vídeo. Isso garante que a informação seja capturada pelo agente."
        ),
    },
]


def build_compatibility_report(
    conversations: List[Dict[str, Any]],
    media_counts: Dict[str, int],
    recommended_agent_mode: str | None = None,
) -> Dict[str, Any]:
    """
    Gera o relatório de compatibilidade com base nos tipos de mídia detectados
    e nas funcionalidades suportadas pelo sistema.
    """
    pipeline_stages = _detect_pipeline_stages(conversations)

    supported: List[Dict[str, str]] = []
    unsupported: List[Dict[str, str]] = []

    # Texto sempre suportado
    supported.append(_SUPPORTED_FEATURES[0])

    # Áudio
    if media_counts.get("audio", 0) > 0:
        supported.append(_SUPPORTED_FEATURES[1])

    # Imagem
    if media_counts.get("image", 0) > 0:
        supported.append(_SUPPORTED_FEATURES[2])

    # Vídeo — não suportado quando detectado
    if media_counts.get("video", 0) > 0:
        unsupported.append(_UNSUPPORTED_FEATURES[0])

    return {
        "pipeline_stages_detected": pipeline_stages,
        "features_supported": supported,
        "features_unsupported": unsupported,
        "recommended_agent_mode": recommended_agent_mode or "sdr_scheduler",
        "media_counts": media_counts,
    }


def _detect_pipeline_stages(conversations: List[Dict[str, Any]]) -> List[str]:
    """
    Infere os estágios da pipeline presentes nas conversas com base em
    palavras-chave heurísticas.
    """
    combined = " ".join(
        (msg.get("body") or "").lower()
        for conv in conversations
        for msg in conv.get("messages", [])
    )

    stages: List[str] = []

    opening_kw = ["olá", "oi ", "bom dia", "boa tarde", "prazer", "como posso", "entrei em contato"]
    if any(kw in combined for kw in opening_kw):
        stages.append("abertura")

    qual_kw = ["qual o seu", "me conta", "preciso entender", "qual seria", "tem interesse", "você busca"]
    if any(kw in combined for kw in qual_kw):
        stages.append("qualificação")

    price_kw = ["preço", "valor", "investimento", "custo", "quanto", "orçamento", "r$", "reais"]
    if any(kw in combined for kw in price_kw):
        stages.append("apresentação de preço")

    objection_kw = ["caro", "não tenho", "já tenho", "não preciso", "deixa eu pensar", "vou ver", "tô em dúvida"]
    if any(kw in combined for kw in objection_kw):
        stages.append("objeção")

    closing_kw = ["fechar", "assinar", "contratar", "comprar", "adquirir", "quero", "topo", "vamos"]
    if any(kw in combined for kw in closing_kw):
        stages.append("fechamento")

    followup_kw = ["lembrar", "retornar", "segunda", "semana", "amanhã", "posso te contatar", "te mando"]
    if any(kw in combined for kw in followup_kw):
        stages.append("follow-up")

    return stages if stages else ["abertura"]
