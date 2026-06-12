from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from database import get_connection

logger = logging.getLogger(__name__)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def find_expired_sessions() -> List[Dict[str, Any]]:
    """Retorna runs com status='observing' cujo observation_end_at já passou."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, user_id, modules_requested, use_optimized_strategy
              FROM spy_agent_runs
             WHERE status = 'observing'
               AND observation_end_at <= ?
            """,
            (_now_utc_iso(),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_analyzing(run_id: int) -> None:
    """Muda o status para 'analyzing' e registra o início da análise."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE spy_agent_runs
               SET status = 'analyzing',
                   analyzing_started_at = ?
             WHERE id = ?
            """,
            (_now_utc_iso(), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_completed(run_id: int, leads_sampled: int, messages_sampled: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE spy_agent_runs
               SET status = 'completed',
                   completed_at = ?,
                   leads_sampled = ?,
                   messages_sampled = ?
             WHERE id = ?
            """,
            (_now_utc_iso(), leads_sampled, messages_sampled, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_failed(run_id: int, error: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE spy_agent_runs SET status = 'failed', error = ? WHERE id = ?",
            (error[:500], run_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_module_report(run_id: int, user_id: int, module: str, result: Dict[str, Any]) -> None:
    """Persiste o resultado de um módulo em spy_agent_reports."""
    suggestions = result.get("suggestions", [])
    compatibility = result if module == "compatibility" else None

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO spy_agent_reports
                (run_id, user_id, module, suggestions_json, compatibility_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                user_id,
                module,
                json.dumps(suggestions, ensure_ascii=False),
                json.dumps(compatibility, ensure_ascii=False) if compatibility else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _has_spy_instance(user_id: int) -> bool:
    """Verifica se o usuário tem uma instância espiã configurada."""
    from database import get_connection
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM spy_agent_config WHERE user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def run_analysis_for_session(run: Dict[str, Any]) -> None:
    """
    Executa a análise LLM para uma sessão de espião que expirou o período de observação.
    Chamado em thread separada pelo reconciler loop.

    Se o usuário tem instância espiã configurada, usa spy_conversation_loader (dados isolados).
    Caso contrário, usa load_real_conversations (dados históricos do CRM).
    """
    run_id = run["id"]
    user_id = run["user_id"]
    modules: List[str] = json.loads(run.get("modules_requested") or '["facts","identity","strategy"]')
    use_optimized = bool(run.get("use_optimized_strategy", 1))
    use_spy_source = _has_spy_instance(user_id)

    logger.info(
        "[spy_agent:reconciler] iniciando análise run_id=%s user_id=%s modules=%s spy_source=%s",
        run_id, user_id, modules, use_spy_source,
    )

    try:
        mark_analyzing(run_id)

        from services.spy_agent.compatibility_report import build_compatibility_report

        if use_spy_source:
            from services.spy_agent.spy_conversation_loader import (
                load_spy_conversations,
                count_spy_message_types,
            )
            conversations = load_spy_conversations(user_id)
            # Conta tipos diretamente do banco — garante que áudio/imagem/vídeo
            # apareçam mesmo que os jobs spy.media.process ainda não tenham rodado.
            media_counts = count_spy_message_types(user_id)
        else:
            from services.spy_agent.conversation_loader import (
                load_real_conversations,
                detect_media_types,
            )
            conversations = load_real_conversations(user_id)
            media_counts = detect_media_types(conversations)

        leads_sampled = len(conversations)
        messages_sampled = sum(len(c["messages"]) for c in conversations)

        if leads_sampled == 0:
            mark_failed(run_id, "Nenhuma conversa real encontrada para análise")
            return

        # Busca AI Profile atual para contexto
        current_profile: Dict[str, Any] = {}
        try:
            from core_client import fetch_core_ai_profile_resolve
            current_profile = fetch_core_ai_profile_resolve(user_id) or {}
        except Exception as exc:
            logger.warning("[spy_agent:reconciler] não foi possível buscar AI Profile: %s", exc)

        recommended_mode: str | None = None

        # Módulo 1 — Fatos
        if "facts" in modules:
            from services.spy_agent.module_facts import analyze_facts
            result = analyze_facts(conversations, current_profile)
            save_module_report(run_id, user_id, "facts", result)

        # Módulo 2 — Identidade
        if "identity" in modules:
            from services.spy_agent.module_identity import analyze_identity
            result = analyze_identity(conversations, current_profile)
            save_module_report(run_id, user_id, "identity", result)

        # Módulo 3 — Estratégia
        if "strategy" in modules:
            from services.spy_agent.module_strategy import analyze_strategy
            result = analyze_strategy(conversations, current_profile, use_optimized_strategy=use_optimized)
            recommended_mode = result.get("recommended_agent_mode")
            save_module_report(run_id, user_id, "strategy", result)

        # Módulo 4 — Pipeline de vendas (sempre executa quando há dados espiões)
        if use_spy_source:
            from services.spy_agent.module_sales_pipeline import analyze_pipeline
            pipeline_result = analyze_pipeline(conversations, current_profile)
            if not recommended_mode:
                recommended_mode = pipeline_result.get("recommended_agent_mode")
            save_module_report(run_id, user_id, "sales_pipeline", pipeline_result)

        # Relatório de compatibilidade (sempre)
        compat = build_compatibility_report(conversations, media_counts, recommended_mode)
        save_module_report(run_id, user_id, "compatibility", compat)

        mark_completed(run_id, leads_sampled, messages_sampled)
        logger.info(
            "[spy_agent:reconciler] análise concluída run_id=%s leads=%s msgs=%s",
            run_id, leads_sampled, messages_sampled,
        )

    except Exception as exc:
        logger.error("[spy_agent:reconciler] erro inesperado run_id=%s: %s", run_id, exc, exc_info=True)
        mark_failed(run_id, str(exc))


def reconcile_expired_observations() -> Dict[str, int]:
    """
    Verifica sessões de observação vencidas e dispara análise para cada uma.
    Retorna contadores para logging.
    """
    expired = find_expired_sessions()
    triggered = 0

    for run in expired:
        try:
            run_analysis_for_session(run)
            triggered += 1
        except Exception as exc:
            logger.error("[spy_agent:reconciler] falha ao processar run_id=%s: %s", run["id"], exc)

    return {"scanned": len(expired), "triggered": triggered}
