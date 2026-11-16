"""
Cliente simulado para testes do agente no Playground.

Gera a próxima fala de um CLIENTE de teste a partir de uma persona e da conversa até agora. Serve as
skills de configuração de agentes (`.claude/skills/diagnosticar-agente/scripts/simular.py`) quando
correm sem chave de LLM local, como no PC de um colaborador. Não toca no motor do agente nem em dados
de nenhuma conta: só devolve texto.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.4
FIM = "FIM"


def build_prompt(persona: str, agente_nome: str, agente_negocio: str, idioma: Optional[str],
                 conversa: List[tuple[str, str]]) -> str:
    """Mesmo prompt de `simular.py::cliente_ia` — os dois lados têm de dar resultados comparáveis."""
    hist = "\n".join(f"{'CLIENTE' if de == 'cliente' else agente_nome.upper()}: {texto}" for de, texto in conversa)
    return (
        f"Você faz o papel de um CLIENTE a conversar no WhatsApp com {agente_nome}, atendente de: {agente_negocio}.\n"
        f"PERSONA E OBJETIVO: {persona}\n\n"
        f"Escreva só a próxima mensagem do cliente: curta e informal, como no WhatsApp, em {idioma or 'português'}, "
        f"e responda ao que {agente_nome} perguntou. Siga o que a persona diz para cada situação. "
        "Não invente que recebeu algo que não foi enviado. Quando o objetivo estiver concluído (ou a persona desistir) "
        f"e não tiver mais nada a dizer, responda exatamente {FIM}.\n\n"
        f"CONVERSA ATÉ AGORA:\n{hist}\n\nCLIENTE:"
    )


class SimulatedClientUnavailable(RuntimeError):
    """Sem chave ou sem biblioteca da OpenAI no servidor."""


def next_message(prompt: str) -> tuple[str, bool]:
    """Devolve (mensagem, fim). `fim` = o cliente simulado não tem mais nada a dizer."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SimulatedClientUnavailable("OPENAI_API_KEY não configurado")
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise SimulatedClientUnavailable("biblioteca openai não instalada") from exc

    raw = OpenAI(api_key=api_key).chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = (raw.choices[0].message.content or "").strip().strip('"')
    return texto, FIM in texto  # mesma regra de simular.py
