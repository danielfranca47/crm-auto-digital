"""
Verificações de plano (feature-gates) para o backend-crm.
Lê entitlements fornecidos pelo backend-core via require_crm_access.
"""
import sqlite3
from datetime import datetime, timezone

from fastapi import HTTPException, status


def check_follow_up_enabled(entitlements: dict) -> None:
    """Levanta 403 se follow-up automático não estiver incluído no plano."""
    limits = entitlements.get("limits") or {}
    enabled = limits.get("follow_up_enabled", True)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "follow_up_not_included",
                "message": "Follow-up automático não está disponível no plano Start. Faça upgrade para o Growth para activar esta funcionalidade.",
            },
        )


def check_playground_limit(user_id: int, entitlements: dict, conn: sqlite3.Connection) -> None:
    """
    Verifica e incrementa o contador de usos mensais do playground.
    Levanta 403 se o utilizador atingiu o limite do mês.
    None = ilimitado (não bloqueia).
    """
    limits = entitlements.get("limits") or {}
    monthly_limit = limits.get("playground_monthly_limit")

    if monthly_limit is None:
        return  # ilimitado

    month_key = datetime.now(timezone.utc).strftime("%Y-%m")

    # Garante que a tabela existe
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS playground_usage_monthly (
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, month)
        )
        """
    )

    row = conn.execute(
        "SELECT count FROM playground_usage_monthly WHERE user_id = ? AND month = ?",
        (user_id, month_key),
    ).fetchone()

    current_count = row["count"] if row else 0

    if current_count >= monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "playground_limit_reached",
                "message": f"Atingiste o limite de {monthly_limit} testes no Playground este mês. O contador reinicia no próximo mês.",
                "used": current_count,
                "limit": monthly_limit,
            },
        )

    # Incrementa
    conn.execute(
        """
        INSERT INTO playground_usage_monthly (user_id, month, count)
        VALUES (?, ?, 1)
        ON CONFLICT (user_id, month) DO UPDATE SET count = count + 1
        """,
        (user_id, month_key),
    )
    conn.commit()
