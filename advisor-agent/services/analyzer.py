"""
Calls Claude API with session summaries + project context and returns a
structured advisor report as a dict.
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, List

import anthropic

from readers.transcript_reader import get_recent_sessions
from readers.session_parser import summarize_session
from readers.project_reader import get_project_context

MODEL = "claude-sonnet-4-6"
DAYS_LOOKBACK = 7


def run_analysis() -> Dict[str, Any]:
    sessions_raw = get_recent_sessions(days=DAYS_LOOKBACK)
    summaries = [summarize_session(s) for s in sessions_raw]
    project_ctx = get_project_context()

    if not summaries:
        return _empty_report("Nenhuma sessão encontrada nos últimos 7 dias.")

    prompt = _build_prompt(summaries, project_ctx)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return _parse_response(raw, summaries)


def _build_prompt(summaries: List[Dict], project_ctx: str) -> str:
    sessions_text = json.dumps(summaries, ensure_ascii=False, indent=2)

    period_start = summaries[0]["date"][:10] if summaries else "?"
    period_end = summaries[-1]["date"][:10] if summaries else "?"

    return f"""Você é um arquitecto de software sénior e consultor técnico.
Analise o trabalho de desenvolvimento de um fundador que está a construir um SaaS de CRM com automação de vendas via WhatsApp, com 3 tipos de agentes:
- Agente 1: SDR alto ticket (consultivo, qualificação profunda)
- Agente 2: Fluxo curto directo para baixo ticket
- Agente 3: Híbrido agendador para profissionais de serviços

O seu papel é: avaliar tecnicamente o trabalho, identificar pontos fortes e fracos, e dar prioridades claras.

{project_ctx}

---

## Sessões de desenvolvimento (período: {period_start} → {period_end})

```json
{sessions_text}
```

---

Gere um relatório de consultor em JSON **válido** com exactamente esta estrutura (sem markdown extra):

{{
  "period": "{period_start} → {period_end}",
  "session_count": {len(summaries)},
  "timeline": [
    {{"date": "YYYY-MM-DD", "summary": "descrição curta do que foi feito", "areas": ["Backend CRM"], "branch": "nome-da-branch"}}
  ],
  "assessment": "avaliação geral do trabalho (2-4 parágrafos): qualidade técnica, consistência com a arquitectura, progressão em relação aos objectivos do produto",
  "strengths": [
    {{"strength": "ponto forte", "evidence": "exemplo concreto das sessões"}}
  ],
  "improvements": [
    {{"area": "área técnica", "issue": "problema identificado", "suggestion": "sugestão concreta", "priority": "high|medium|low"}}
  ],
  "next_priorities": [
    {{"rank": 1, "description": "o que fazer a seguir", "why": "porquê é prioritário"}}
  ]
}}

Responda APENAS com o JSON. Sem texto antes ou depois.
"""


def _parse_response(raw: str, summaries: List[Dict]) -> Dict[str, Any]:
    # Strip possible markdown code fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return raw text as assessment
        report = {
            "period": "?",
            "session_count": len(summaries),
            "timeline": [],
            "assessment": raw,
            "strengths": [],
            "improvements": [],
            "next_priorities": [],
        }

    report["generated_at"] = datetime.now().isoformat()
    return report


def _empty_report(reason: str) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(),
        "period": "—",
        "session_count": 0,
        "timeline": [],
        "assessment": reason,
        "strengths": [],
        "improvements": [],
        "next_priorities": [],
    }
