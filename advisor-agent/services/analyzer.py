"""
Chama Claude via `claude --print` subprocess (Claude Code CLI) para gerar
o relatório de advisor. Inclui contexto histórico e métricas objectivas.
"""
import json
import logging
import subprocess
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, List

from readers.transcript_reader import get_recent_sessions
from readers.session_parser import summarize_session
from readers.project_reader import get_project_context
from services import history, metrics as metrics_svc

DAYS_LOOKBACK = 7
TIMEOUT_SECONDS = 180

log = logging.getLogger("advisor.analyzer")


def run_analysis() -> Dict[str, Any]:
    sessions_raw = get_recent_sessions(days=DAYS_LOOKBACK)
    summaries = [summarize_session(s) for s in sessions_raw]
    project_ctx = get_project_context()
    past_analyses = history.load_recent(n=4)
    metrics = metrics_svc.compute(sessions_raw)

    if not summaries:
        return _empty_report("Nenhuma sessão encontrada nos últimos 7 dias.")

    prompt = _build_prompt(summaries, project_ctx, past_analyses, metrics)
    raw = _call_claude(prompt)
    return _parse_response(raw, summaries)


def run_briefing() -> Dict[str, Any]:
    """Gera um briefing focado de arranque de dia (prompt diferente, mais curto)."""
    latest = history.load_latest()
    sessions_raw = get_recent_sessions(days=2)
    summaries = [summarize_session(s) for s in sessions_raw]
    metrics = metrics_svc.compute(sessions_raw)

    prompt = _build_briefing_prompt(latest, summaries, metrics)
    raw = _call_claude(prompt)
    return _parse_briefing_response(raw)


# --- Builders de prompt ---

def _build_prompt(
    summaries: List[Dict],
    project_ctx: str,
    past_analyses: List[Dict],
    metrics: Dict,
) -> str:
    sessions_text = json.dumps(summaries, ensure_ascii=False, indent=2)
    metrics_text = json.dumps(metrics, ensure_ascii=False, indent=2)

    period_start = summaries[0]["date"][:10] if summaries else "?"
    period_end = summaries[-1]["date"][:10] if summaries else "?"

    history_block = ""
    if past_analyses:
        history_block = (
            "## Histórico de análises anteriores (para detectar padrões recorrentes)\n"
            + json.dumps(past_analyses, ensure_ascii=False, indent=2)
        )

    return f"""Você é um arquitecto de software sénior e consultor técnico para um fundador solo.
O fundador está a construir um SaaS de CRM com automação de vendas via WhatsApp com 3 tipos de agentes:
- Agente 1: SDR alto ticket (qualificação consultiva profunda)
- Agente 2: Fluxo curto directo para baixo ticket
- Agente 3: Híbrido agendador para profissionais de serviços

{project_ctx}

---

## Métricas objectivas da semana
```json
{metrics_text}
```

{history_block}

---

## Sessões de desenvolvimento (período: {period_start} → {period_end})
```json
{sessions_text}
```

---

Gere um relatório de consultor em JSON **válido** com exactamente esta estrutura (sem markdown extra, sem texto fora do JSON):

{{
  "period": "{period_start} → {period_end}",
  "session_count": {len(summaries)},
  "timeline": [
    {{"date": "YYYY-MM-DD", "summary": "descrição curta", "areas": ["Backend CRM"], "branch": "nome-da-branch"}}
  ],
  "assessment": "avaliação geral do trabalho (2-4 parágrafos). Se houver histórico anterior, referir evolução vs. análises passadas.",
  "strengths": [
    {{"strength": "ponto forte", "evidence": "exemplo concreto das sessões"}}
  ],
  "improvements": [
    {{"area": "área técnica", "issue": "problema identificado", "suggestion": "sugestão concreta e accionável", "priority": "high|medium|low"}}
  ],
  "next_priorities": [
    {{"rank": 1, "description": "o que fazer a seguir", "why": "porquê é prioritário agora"}}
  ]
}}

Responda APENAS com o JSON. Sem texto antes ou depois.
"""


def _build_briefing_prompt(
    latest_report: Dict | None,
    recent_summaries: List[Dict],
    metrics: Dict,
) -> str:
    report_ctx = ""
    if latest_report:
        high_issues = [
            i.get("issue", "") for i in latest_report.get("improvements", [])
            if i.get("priority") == "high"
        ]
        priorities = [p.get("description", "") for p in latest_report.get("next_priorities", [])]
        report_ctx = f"""
## Última análise completa
- Período: {latest_report.get('period', '?')}
- Problemas HIGH: {json.dumps(high_issues, ensure_ascii=False)}
- Próximas prioridades: {json.dumps(priorities, ensure_ascii=False)}
- Avaliação resumida: {latest_report.get('assessment', '')[:500]}
"""

    recent_ctx = ""
    if recent_summaries:
        recent_ctx = "## Sessões das últimas 48h\n" + json.dumps(recent_summaries, ensure_ascii=False, indent=2)

    today = datetime.now().strftime("%A, %d de %B de %Y")

    return f"""Você é um assistente de arranque de dia para um fundador solo de software.
É {today}. Gere um briefing conciso e accionável para começar o dia de trabalho.

{report_ctx}

{recent_ctx}

## Métricas recentes
- Sessões (últimas 48h): {len(recent_summaries)}
- Commits esta semana: {metrics.get('commits_this_week', 0)}

---

Responda APENAS com JSON válido, sem texto extra:

{{
  "date": "{today}",
  "pending_from_yesterday": ["item pendente 1", "item pendente 2"],
  "focus_today": [
    {{"rank": 1, "task": "o que fazer primeiro", "why": "porquê agora"}},
    {{"rank": 2, "task": "o que fazer a seguir", "why": "porquê"}}
  ],
  "watch_out": ["aviso ou risco específico"],
  "motivation": "frase curta de contexto positivo sobre o estado do projecto"
}}

focus_today deve ter 2-3 itens concretos e específicos para o projecto, não genéricos.
"""


# --- Chamada ao Claude CLI ---

def _call_claude(prompt: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        tmp_path = f.name

    try:
        with open(tmp_path, "r", encoding="utf-8") as stdin_f:
            result = subprocess.run(
                ["claude", "--print"],
                stdin=stdin_f,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=TIMEOUT_SECONDS,
            )

        if result.returncode != 0:
            err = result.stderr.strip()[:500]
            log.error(f"claude --print exited {result.returncode}: {err}")
            raise RuntimeError(f"claude CLI error: {err}")

        return result.stdout.strip()

    except FileNotFoundError:
        raise RuntimeError(
            "Comando 'claude' não encontrado. Garante que o Claude Code está instalado "
            "e no PATH. Tenta abrir um novo terminal."
        )
    finally:
        os.unlink(tmp_path)


# --- Parsers de resposta ---

def _parse_response(raw: str, summaries: List[Dict]) -> Dict[str, Any]:
    raw = _strip_fences(raw)
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
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


def _parse_briefing_response(raw: str) -> Dict[str, Any]:
    raw = _strip_fences(raw)
    try:
        briefing = json.loads(raw)
    except json.JSONDecodeError:
        briefing = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "pending_from_yesterday": [],
            "focus_today": [],
            "watch_out": [],
            "motivation": raw[:500],
        }
    briefing["generated_at"] = datetime.now().isoformat()
    return briefing


def _strip_fences(raw: str) -> str:
    if raw.startswith("```"):
        lines = raw.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[1:end])
    return raw.strip()


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
