"""
Detecta padrões negativos ou dignos de atenção nos dados de sessão e histórico.
Retorna uma lista de alertas para exibir no dashboard.
Não chama o Claude — execução instantânea.
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, Any, List


def detect(
    sessions_raw: List[Dict],
    metrics: Dict[str, Any],
    history: List[Dict],
) -> List[Dict[str, str]]:
    alerts = []

    alerts += _check_file_instability(metrics)
    alerts += _check_area_concentration(metrics)
    alerts += _check_recurring_high_priority(history)
    alerts += _check_no_commits(metrics)
    alerts += _check_session_gap(sessions_raw)
    alerts += _check_low_commit_vs_sessions(metrics)

    return alerts


# --- Regras individuais ---

def _check_file_instability(metrics: Dict) -> List[Dict]:
    alerts = []
    for file_path, count in metrics.get("most_modified_files", []):
        if count >= 5:
            alerts.append({
                "level": "warning",
                "title": f"Ficheiro instável: {file_path}",
                "detail": f"Modificado {count}× esta semana. Pode indicar lógica complexa, bugs recorrentes ou refactoring incompleto.",
                "action": "Considera estabilizar este ficheiro antes de avançar.",
            })
    return alerts


def _check_area_concentration(metrics: Dict) -> List[Dict]:
    areas = metrics.get("files_by_area", {})
    if not areas:
        return []
    total = sum(areas.values())
    for area, count in areas.items():
        pct = round(count / total * 100)
        if pct >= 70 and total >= 8:
            return [{
                "level": "info",
                "title": f"Foco concentrado: {pct}% do trabalho em {area}",
                "detail": "Atenção ao risco de outras áreas do sistema ficarem para trás.",
                "action": "Verifica se há débito acumulado nas outras áreas.",
            }]
    return []


def _check_recurring_high_priority(history: List[Dict]) -> List[Dict]:
    if len(history) < 2:
        return []

    # Conta quantas análises passadas tinham cada issue como HIGH
    issue_count: Counter = Counter()
    for past in history:
        for issue in past.get("high_priority_issues", []):
            if issue:
                issue_count[issue[:80]] += 1

    alerts = []
    for issue, count in issue_count.items():
        if count >= 2:
            alerts.append({
                "level": "warning",
                "title": f"Problema recorrente ({count}× nas últimas análises)",
                "detail": f'"{issue}"',
                "action": "Este ponto de melhoria está a acumular. Considera dedicar uma sessão focada só para isto.",
            })
    return alerts


def _check_no_commits(metrics: Dict) -> List[Dict]:
    commits = metrics.get("commits_this_week", 0)
    sessions = metrics.get("total_sessions", 0)
    if sessions >= 3 and commits == 0:
        return [{
            "level": "warning",
            "title": "Nenhum commit esta semana",
            "detail": f"Tiveste {sessions} sessões de trabalho mas sem commits registados.",
            "action": "Verifica se há trabalho por commitar ou se as sessões foram exploratórias.",
        }]
    return []


def _check_session_gap(sessions_raw: List[Dict]) -> List[Dict]:
    if not sessions_raw:
        return []
    last_ts = sessions_raw[-1].get("started_at", "")
    if not last_ts:
        return []
    try:
        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        # Remove timezone for comparison
        last_dt = last_dt.replace(tzinfo=None)
        gap = datetime.now() - last_dt
        if gap > timedelta(days=4):
            days = gap.days
            return [{
                "level": "info",
                "title": f"Pausa de {days} dias sem sessão",
                "detail": "Não foi detectada nenhuma sessão de desenvolvimento nos últimos dias.",
                "action": "Nada urgente — só para ter consciência do ritmo.",
            }]
    except Exception:
        pass
    return []


def _check_low_commit_vs_sessions(metrics: Dict) -> List[Dict]:
    commits = metrics.get("commits_this_week", 0)
    sessions = metrics.get("total_sessions", 0)
    if sessions >= 5 and commits >= 1 and commits / sessions < 0.3:
        return [{
            "level": "info",
            "title": f"Ratio sessões/commits baixo ({sessions} sessões, {commits} commits)",
            "detail": "Muitas sessões para poucos commits. Pode indicar muita exploração ou sessões longas sem checkpoint.",
            "action": "Considera commitar com mais frequência para preservar o contexto de cada mudança.",
        }]
    return []
