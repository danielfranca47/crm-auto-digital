"""
collab_monitor.py — Cadastro de instâncias WhatsApp de monitoramento de colaborador.

Diferente do Agente Espião (routes/spy_agent.py): aqui são N instâncias por
conta, permanentes, cada uma nomeada por colaborador. A ingestão real das
mensagens (Fase 3) acontece em services/collab_monitor/monitor_inbound_handler.py,
roteada a partir do webhook da UazAPI (routes/webhooks.py) — este arquivo cuida
apenas do cadastro/conexão da instância e da leitura agregada das conversas.

Fluxo:
  POST   /api/collab-monitor/instances                 → cadastra colaborador + conecta (QR)
  GET    /api/collab-monitor/instances                 → lista instâncias da conta
  DELETE /api/collab-monitor/instances/{id}             → remove o cadastro + desconecta a instância na UazAPI
  POST   /api/collab-monitor/instances/{id}/reconnect   → reconecta via QR
  GET    /api/collab-monitor/conversations              → lista leads monitorados (tela estilo WhatsApp Web)
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core_client import (
    connect_core_whatsapp_instance,
    delete_core_whatsapp_instance,
    fetch_core_whatsapp_connection_resolve,
    init_core_whatsapp_instance,
    set_core_whatsapp_webhook,
)
from database import get_connection
from security_core import CurrentUser, require_crm_access
from services.lead_category_policy import BOT_STRUCTURALLY_INACTIVE_CATEGORIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collab-monitor", tags=["CollabMonitor"])

_QR_KEYS = {"qrcode", "qrCode", "qr_code"}
_PAIR_KEYS = {"paircode", "pairCode", "pair_code"}


def _sanitize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    sanitized = re.sub(r"[\s\-\+\(\)]", "", value)
    return sanitized or None


def _extract_pair_code(raw: Dict[str, Any]) -> Optional[str]:
    return _find_in_payload(raw, _PAIR_KEYS)


def _find_in_payload(payload: Any, keys: set) -> Optional[str]:
    if isinstance(payload, dict):
        for k in keys:
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for value in payload.values():
            found = _find_in_payload(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_in_payload(item, keys)
            if found:
                return found
    return None


def _infer_qr_kind(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://") or value.startswith("data:image"):
        return "url"
    if re.fullmatch(r"[A-Za-z0-9+/=\n\r]+", value) and len(value) > 80:
        return "base64"
    return "text"


def _normalize_status_raw(raw: Dict[str, Any]) -> Optional[str]:
    status_payload = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    logged_in = (
        raw.get("loggedIn")
        if isinstance(raw.get("loggedIn"), bool)
        else status_payload.get("loggedIn")
        if isinstance(status_payload.get("loggedIn"), bool)
        else None
    )
    connected = (
        raw.get("connected")
        if isinstance(raw.get("connected"), bool)
        else status_payload.get("connected")
        if isinstance(status_payload.get("connected"), bool)
        else None
    )
    instance_status_raw = raw.get("instance")
    instance_status = instance_status_raw.get("status") if isinstance(instance_status_raw, dict) else None
    if logged_in is True:
        return "connected"
    if connected is False and logged_in is False:
        return "disconnected"
    if isinstance(instance_status, str):
        return instance_status.strip().lower()
    return None


def _build_webhook_url() -> Optional[str]:
    base = os.getenv("CRM_PUBLIC_BASE_URL")
    secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not base or not secret:
        return None
    return f"{base.rstrip('/')}/webhooks/whatsapp/uazapi?secret={secret}"


def _set_monitor_webhook(instance_id: str) -> None:
    webhook_url = _build_webhook_url()
    if not webhook_url:
        logger.warning("[collab_monitor] CRM_PUBLIC_BASE_URL/CRM_WEBHOOK_SECRET ausente — webhook não configurado")
        return
    try:
        set_core_whatsapp_webhook(
            instance_id,
            webhook_url,
            ["messages", "connection"],
            False,
            True,
            ["wasSentByApi", "isGroupYes"],
        )
    except Exception as exc:
        logger.warning("[collab_monitor] falha ao configurar webhook instance=%s error=%s", instance_id, exc)


def _generate_instance_id(user_id: int) -> str:
    return f"collab-{user_id}-{uuid4().hex[:8]}"


class CollabMonitorCreateRequest(BaseModel):
    collaborator_name: str
    phone: Optional[str] = None


class CollabMonitorReconnectRequest(BaseModel):
    phone: Optional[str] = None


class CollabMonitorInstanceOut(BaseModel):
    id: int
    instance_id: str
    collaborator_name: str
    status: str
    phone_e164: Optional[str] = None
    connection_status: Optional[str] = None
    created_at: str
    updated_at: str


class QRPayload(BaseModel):
    kind: Optional[str] = None
    value: Optional[str] = None


class CollabMonitorConnectResponse(BaseModel):
    id: int
    instance_id: str
    collaborator_name: str
    status: Optional[str] = None
    qr: QRPayload
    pair_code: Optional[str] = None


class CollabMonitorConversationOut(BaseModel):
    lead_id: int
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    instance_id: str
    collaborator_name: Optional[str] = None
    msg_count: int = 0
    last_message_at: Optional[str] = None
    last_message_preview: Optional[str] = None
    category: Optional[str] = None
    last_message_from: Optional[str] = None


class CollabMonitorConversationsPage(BaseModel):
    items: List[CollabMonitorConversationOut]
    has_more: bool


class CollabMonitorSettingsOut(BaseModel):
    stale_threshold_hours: int


class CollabMonitorSettingsUpdate(BaseModel):
    stale_threshold_hours: int


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _get_row(conn, row_id: int, user_id: int) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM collab_monitor_instances WHERE id = ? AND user_id = ?",
        (row_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Instância de colaborador não encontrada")
    return dict(row)


@router.post("/instances", response_model=CollabMonitorConnectResponse)
async def create_collab_monitor_instance(
    body: CollabMonitorCreateRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> CollabMonitorConnectResponse:
    """Cadastra um novo colaborador para monitoramento e inicia a conexão (QR ou código de pareamento, se `phone` informado)."""
    collaborator_name = body.collaborator_name.strip()
    if not collaborator_name:
        raise HTTPException(status_code=400, detail="Nome do colaborador é obrigatório")

    phone = _sanitize_phone(body.phone)
    instance_id = _generate_instance_id(current_user.id)

    init_core_whatsapp_instance(current_user.id, instance_id, role="monitor")
    raw = connect_core_whatsapp_instance(current_user.id, instance_id, phone=phone)
    _set_monitor_webhook(instance_id)

    status_value = _normalize_status_raw(raw)
    qr_value = _find_in_payload(raw, _QR_KEYS)
    qr_kind = _infer_qr_kind(qr_value) if qr_value else None
    pair_code = _extract_pair_code(raw)

    now = _now_utc_iso()
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO collab_monitor_instances
                (user_id, instance_id, collaborator_name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (current_user.id, instance_id, collaborator_name, status_value or "pending", now, now),
        )
        conn.commit()
        row_id = cur.lastrowid
    finally:
        conn.close()

    logger.info(
        "[collab_monitor] instância criada user=%s instance=%s collaborator=%s",
        current_user.id,
        instance_id,
        collaborator_name,
    )

    return CollabMonitorConnectResponse(
        id=row_id,
        instance_id=instance_id,
        collaborator_name=collaborator_name,
        status=status_value,
        qr=QRPayload(kind=qr_kind, value=qr_value),
        pair_code=pair_code,
    )


@router.get("/instances", response_model=List[CollabMonitorInstanceOut])
async def list_collab_monitor_instances(
    current_user: CurrentUser = Depends(require_crm_access),
) -> List[CollabMonitorInstanceOut]:
    """Lista as instâncias de colaborador cadastradas nesta conta."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM collab_monitor_instances WHERE user_id = ? ORDER BY created_at DESC",
            (current_user.id,),
        ).fetchall()
    finally:
        conn.close()

    result: List[CollabMonitorInstanceOut] = []
    for row in rows:
        row = dict(row)
        phone_e164 = None
        connection_status = None
        try:
            conn_info = fetch_core_whatsapp_connection_resolve(row["instance_id"])
            phone_e164 = conn_info.get("phone_e164")
            connection_status = conn_info.get("connection_status")
        except Exception:
            pass

        result.append(
            CollabMonitorInstanceOut(
                id=row["id"],
                instance_id=row["instance_id"],
                collaborator_name=row["collaborator_name"],
                status=row["status"],
                phone_e164=phone_e164,
                connection_status=connection_status,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    return result


@router.delete("/instances/{row_id}")
async def delete_collab_monitor_instance(
    row_id: int,
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Remove o cadastro de monitoramento de um colaborador e apaga a instância na UazAPI."""
    conn = get_connection()
    try:
        row = _get_row(conn, row_id, current_user.id)
        conn.execute(
            "DELETE FROM collab_monitor_instances WHERE id = ? AND user_id = ?",
            (row_id, current_user.id),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        delete_core_whatsapp_instance(row["instance_id"])
    except Exception as exc:
        logger.warning(
            "[collab_monitor] falha ao apagar instancia na UazAPI (nao-bloqueante) instance=%s error=%s",
            row["instance_id"],
            exc,
        )

    return {"ok": True}


@router.post("/instances/{row_id}/reconnect", response_model=CollabMonitorConnectResponse)
async def reconnect_collab_monitor_instance(
    row_id: int,
    body: CollabMonitorReconnectRequest = CollabMonitorReconnectRequest(),
    current_user: CurrentUser = Depends(require_crm_access),
) -> CollabMonitorConnectResponse:
    """Reconecta a instância de um colaborador via QR code ou código de pareamento (se `phone` informado), sem perder o cadastro."""
    conn = get_connection()
    try:
        row = _get_row(conn, row_id, current_user.id)
    finally:
        conn.close()

    instance_id = row["instance_id"]
    phone = _sanitize_phone(body.phone)

    try:
        raw = connect_core_whatsapp_instance(current_user.id, instance_id, phone=phone)
    except HTTPException:
        logger.info("[collab_monitor:reconnect] token expirado para %s — reiniciando instância", instance_id)
        init_core_whatsapp_instance(current_user.id, instance_id, role="monitor")
        raw = connect_core_whatsapp_instance(current_user.id, instance_id, phone=phone)

    _set_monitor_webhook(instance_id)

    status_value = _normalize_status_raw(raw)
    qr_value = _find_in_payload(raw, _QR_KEYS)
    qr_kind = _infer_qr_kind(qr_value) if qr_value else None
    pair_code = _extract_pair_code(raw)

    now = _now_utc_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE collab_monitor_instances SET status = ?, updated_at = ? WHERE id = ?",
            (status_value or row["status"], now, row_id),
        )
        conn.commit()
    finally:
        conn.close()

    return CollabMonitorConnectResponse(
        id=row_id,
        instance_id=instance_id,
        collaborator_name=row["collaborator_name"],
        status=status_value,
        qr=QRPayload(kind=qr_kind, value=qr_value),
        pair_code=pair_code,
    )


@router.get("/settings", response_model=CollabMonitorSettingsOut)
async def get_collab_monitor_settings(
    current_user: CurrentUser = Depends(require_crm_access),
) -> CollabMonitorSettingsOut:
    """Configuração de conta do Monitoramento — hoje só o limiar (em horas) de
    silêncio do colaborador que dispara o alerta de conversa parada na tela.
    Sem linha cadastrada, devolve o default (3h) sem criar nada."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT stale_threshold_hours FROM collab_monitor_settings WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()
    finally:
        conn.close()
    return CollabMonitorSettingsOut(stale_threshold_hours=row["stale_threshold_hours"] if row else 3)


@router.put("/settings", response_model=CollabMonitorSettingsOut)
async def update_collab_monitor_settings(
    body: CollabMonitorSettingsUpdate,
    current_user: CurrentUser = Depends(require_crm_access),
) -> CollabMonitorSettingsOut:
    if body.stale_threshold_hours < 1 or body.stale_threshold_hours > 168:
        raise HTTPException(status_code=400, detail="stale_threshold_hours deve estar entre 1 e 168")

    now = _now_utc_iso()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO collab_monitor_settings (user_id, stale_threshold_hours, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                stale_threshold_hours = excluded.stale_threshold_hours,
                updated_at = excluded.updated_at
            """,
            (current_user.id, body.stale_threshold_hours, now),
        )
        conn.commit()
    finally:
        conn.close()
    return CollabMonitorSettingsOut(stale_threshold_hours=body.stale_threshold_hours)


@router.get("/conversations", response_model=CollabMonitorConversationsPage)
async def list_collab_monitor_conversations(
    instance_id: Optional[str] = None,
    status: str = Query("active", pattern="^(active|all)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(require_crm_access),
) -> CollabMonitorConversationsPage:
    """Lista os leads originados de monitoramento de colaborador
    (`collab_monitor_instance_id IS NOT NULL`), em qualquer estágio do funil —
    não desaparece daqui quando a classificação de estágio avança a
    categoria além de `monitoring`. Agrupados por colaborador, com contagem,
    preview e direção (`last_message_from`) da última mensagem, e a
    categoria atual do lead — base da tela estilo WhatsApp Web. Filtro
    opcional por `instance_id`. `status=active` (default) esconde conversas em
    categoria estruturalmente encerrada (`BOT_STRUCTURALLY_INACTIVE_CATEGORIES`);
    `status=all` devolve o histórico completo. Paginação tradicional via
    `limit`/`offset` — busca `limit+1` linhas para decidir `has_more` sem
    precisar de um `COUNT(*)` separado."""
    conn = get_connection()
    try:
        query = """
            SELECT l.id AS lead_id,
                   l.contactName AS contact_name,
                   l.phone AS phone,
                   l.collab_monitor_instance_id AS instance_id,
                   l.category AS category,
                   cmi.collaborator_name AS collaborator_name,
                   msg_agg.msg_count AS msg_count,
                   last_msg.createdAt AS last_message_at,
                   last_msg.body AS last_message_preview,
                   last_msg.model AS last_message_from
            FROM leads l
            LEFT JOIN collab_monitor_instances cmi
              ON cmi.instance_id = l.collab_monitor_instance_id
             AND cmi.user_id = l.user_id
            LEFT JOIN (
                SELECT lead_id, COUNT(*) AS msg_count
                FROM messages
                GROUP BY lead_id
            ) AS msg_agg
              ON msg_agg.lead_id = l.id
            LEFT JOIN (
                SELECT lead_id, body, createdAt, model
                FROM (
                    SELECT lead_id, body, createdAt, model,
                           ROW_NUMBER() OVER (
                               PARTITION BY lead_id
                               ORDER BY datetime(createdAt) DESC
                           ) AS rn
                    FROM messages
                )
                WHERE rn = 1
            ) AS last_msg
              ON last_msg.lead_id = l.id
            WHERE l.user_id = ?
              AND l.collab_monitor_instance_id IS NOT NULL
        """
        params: List[Any] = [current_user.id]
        if instance_id:
            query += " AND l.collab_monitor_instance_id = ?"
            params.append(instance_id)
        if status == "active":
            placeholders = ",".join("?" for _ in BOT_STRUCTURALLY_INACTIVE_CATEGORIES)
            query += f" AND l.category NOT IN ({placeholders})"
            params.extend(BOT_STRUCTURALLY_INACTIVE_CATEGORIES)
        query += " ORDER BY datetime(last_msg.createdAt) DESC LIMIT ? OFFSET ?"
        params.extend([limit + 1, offset])

        rows = conn.execute(query, tuple(params)).fetchall()
    finally:
        conn.close()

    has_more = len(rows) > limit
    rows = rows[:limit]

    return CollabMonitorConversationsPage(
        items=[
            CollabMonitorConversationOut(
                lead_id=row["lead_id"],
                contact_name=row["contact_name"],
                phone=row["phone"],
                instance_id=row["instance_id"],
                collaborator_name=row["collaborator_name"],
                msg_count=row["msg_count"] or 0,
                last_message_at=row["last_message_at"],
                last_message_preview=row["last_message_preview"],
                category=row["category"],
                last_message_from=row["last_message_from"],
            )
            for row in rows
        ],
        has_more=has_more,
    )
