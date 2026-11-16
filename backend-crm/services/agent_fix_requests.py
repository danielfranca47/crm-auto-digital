"""
Pedidos de correção do sistema vindos da skill de configuração de agentes.

Um colaborador sem acesso ao código (modo colaborador da skill `configuracao-personalizada`)
regista aqui o que só uma correção de código resolve, com a evidência medida. O Daniel vê-os no
frontend-admin e trata-os pelo fluxo de implementação; a skill do colaborador consulta o estado.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

ESTADOS = ("novo", "em_curso", "feito", "descartado")
MAX_ABERTOS_POR_UTILIZADOR = 20


class LimiteDePedidos(RuntimeError):
    pass


def _row(r: sqlite3.Row) -> Dict[str, Any]:
    return dict(r)


def criar(conn: sqlite3.Connection, user_id: int, user_email: Optional[str], titulo: str, sintoma: str,
          evidencia: Optional[str], cenarios_json: Optional[str], bancada: Optional[str]) -> Dict[str, Any]:
    abertos = conn.execute(
        "SELECT COUNT(*) FROM agent_fix_requests WHERE user_id = ? AND estado IN ('novo','em_curso')",
        (user_id,),
    ).fetchone()[0]
    if abertos >= MAX_ABERTOS_POR_UTILIZADOR:
        raise LimiteDePedidos(f"já há {abertos} pedidos abertos")
    cur = conn.execute(
        """
        INSERT INTO agent_fix_requests (user_id, user_email, titulo, sintoma, evidencia, cenarios_json, bancada)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, user_email, titulo, sintoma, evidencia, cenarios_json, bancada),
    )
    conn.commit()
    return obter(conn, cur.lastrowid)


def obter(conn: sqlite3.Connection, pedido_id: int) -> Optional[Dict[str, Any]]:
    r = conn.execute("SELECT * FROM agent_fix_requests WHERE id = ?", (pedido_id,)).fetchone()
    return _row(r) if r else None


def listar_do_utilizador(conn: sqlite3.Connection, user_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM agent_fix_requests WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [_row(r) for r in rows]


def listar_todos(conn: sqlite3.Connection, estado: Optional[str] = None) -> List[Dict[str, Any]]:
    if estado:
        rows = conn.execute(
            "SELECT * FROM agent_fix_requests WHERE estado = ? ORDER BY created_at DESC, id DESC", (estado,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM agent_fix_requests ORDER BY created_at DESC, id DESC").fetchall()
    return [_row(r) for r in rows]


def atualizar(conn: sqlite3.Connection, pedido_id: int, estado: Optional[str], nota_admin: Optional[str]) -> Optional[Dict[str, Any]]:
    if obter(conn, pedido_id) is None:
        return None
    campos, valores = [], []
    if estado is not None:
        campos.append("estado = ?")
        valores.append(estado)
    if nota_admin is not None:
        campos.append("nota_admin = ?")
        valores.append(nota_admin)
    if campos:
        conn.execute(
            f"UPDATE agent_fix_requests SET {', '.join(campos)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*valores, pedido_id),
        )
        conn.commit()
    return obter(conn, pedido_id)
