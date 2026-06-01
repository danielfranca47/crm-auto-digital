"""
Calls Claude via `claude --print` subprocess (Claude Code CLI) so it uses
the user's existing Claude subscription — no separate API key needed.
"""
import json
import logging
import subprocess
import sys
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List

from readers.transcript_reader import get_recent_sessions
from readers.session_parser import summarize_session
from readers.project_reader import get_project_context

DAYS_LOOKBACK = 7
TIMEOUT_SECONDS = 180

log = logging.getLogger("advisor.analyzer")


def run_analysis() -> Dict[str, Any]:
    sessions_raw = get_recent_sessions(days=DAYS_LOOKBACK)
    summaries = [summarize_session(s) for s in sessions_raw]
    project_ctx = get_project_context()

    if not summaries:
        return _empty_report("Nenhuma sessão encontrada nos últimos 7 dias.")

    prompt = _build_prompt(summaries, project_ctx)
    raw = _call_claude(prompt)
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


def _call_claude(prompt: str) -> str:
    """Run `claude --print` with the prompt via stdin. Uses Claude Code credentials."""
    # Write prompt to a temp file to avoid Windows arg-length limits
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        tmp_path = f.name

    try:
        # claude --print reads from stdin and outputs only the LLM response
        cmd = ["claude", "--print"]
        with open(tmp_path, "r", encoding="utf-8") as stdin_f:
            result = subprocess.run(
                cmd,
                stdin=stdin_f,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=TIMEOUT_SECONDS,
            )

        if result.returncode != 0:
            err = result.stderr.strip()[:500]
            log.error(f"claude --print exited with code {result.returncode}: {err}")
            raise RuntimeError(f"claude CLI error: {err}")

        return result.stdout.strip()

    except FileNotFoundError:
        raise RuntimeError(
            "Comando 'claude' não encontrado. Garante que o Claude Code está instalado "
            "e no PATH. Tenta abrir um novo terminal após a instalação."
        )
    finally:
        os.unlink(tmp_path)


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
