"""
Pedidos de correção da skill de configuração de agentes.

- /api/suporte/pedidos-correcao — o utilizador cria e consulta os seus pedidos
- /admin/pedidos-correcao       — o admin lista todos e muda o estado (frontend-admin)
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core_client import require_crm_admin
from database import get_connection
from security_core import CurrentUser, require_crm_access
from services import agent_fix_requests as pedidos

router = APIRouter(prefix="/api/suporte/pedidos-correcao", tags=["pedidos-correcao"])
admin_router = APIRouter(prefix="/admin/pedidos-correcao", tags=["admin-pedidos-correcao"])

Estado = Literal["novo", "em_curso", "feito", "descartado"]


class PedidoCreate(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=200)
    sintoma: str = Field(..., min_length=3, max_length=4000)
    evidencia: Optional[str] = Field(None, max_length=20000)
    cenarios_json: Optional[str] = Field(None, max_length=50000)
    bancada: Optional[str] = Field(None, max_length=80)


class PedidoUpdate(BaseModel):
    estado: Optional[Estado] = None
    nota_admin: Optional[str] = Field(None, max_length=4000)


def _conn() -> sqlite3.Connection:
    return get_connection()  # já com row_factory = sqlite3.Row


@router.post("")
def criar_pedido(body: PedidoCreate, current_user: CurrentUser = Depends(require_crm_access)) -> Dict[str, Any]:
    with closing(_conn()) as conn:
        try:
            return pedidos.criar(conn, int(current_user.id), current_user.email, body.titulo, body.sintoma,
                                 body.evidencia, body.cenarios_json, body.bancada)
        except pedidos.LimiteDePedidos as exc:
            raise HTTPException(status_code=429, detail=f"Limite de pedidos abertos: {exc}")


@router.get("")
def listar_meus(current_user: CurrentUser = Depends(require_crm_access)) -> List[Dict[str, Any]]:
    with closing(_conn()) as conn:
        return pedidos.listar_do_utilizador(conn, int(current_user.id))


@admin_router.get("")
def admin_listar(estado: Optional[Estado] = None, _: dict = Depends(require_crm_admin)) -> List[Dict[str, Any]]:
    with closing(_conn()) as conn:
        return pedidos.listar_todos(conn, estado)


@admin_router.patch("/{pedido_id}")
def admin_atualizar(pedido_id: int, body: PedidoUpdate, _: dict = Depends(require_crm_admin)) -> Dict[str, Any]:
    with closing(_conn()) as conn:
        r = pedidos.atualizar(conn, pedido_id, body.estado, body.nota_admin)
    if r is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return r
