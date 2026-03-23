# backend/routes/leads.py
from typing import Any, Optional
import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta, timezone

from database import get_connection, normalize_datetime_value
from models import Lead, LeadUpdate, AppointmentCreate, AppointmentUpdate, BotDisabledUpdate, StartFollowupPayload
from security_core import CurrentUser, require_crm_access
from services import rate_limit_service
from services.agent_type import resolve_agent_type_for_user
from core_client import fetch_core_ai_profile
from services.phone_normalizer import PhoneNormalizationError, normalize_to_e164
from services.lead_category_policy import apply_closing_bot_disable_side_effect
from services.followup_state import (
    stop_followup_for_lead_category,
    stop_followup_on_handoff,
    pause_followup_manually,
    resume_followup_manually,
    cancel_followup_manually,
)
from services.qualification_guardrails import can_advance_from_qualification

router = APIRouter()
logger = logging.getLogger(__name__)


FOLLOWUP_CONTRACT_VERSION = 1
_FOLLOWUP_VARIANT_BY_AGENT_TYPE = {
    "agent_1": "sdr_scheduler",
    "agent_3": "hybrid_scheduler",
}
_MAX_ATTEMPTS_BY_VARIANT = {
    "sdr_scheduler": 4,
    "hybrid_scheduler": 3,
}
_FIRST_FOLLOWUP_OFFSET_MINUTES = {
    "sdr_scheduler": {
        "default": 30,
    },
    "hybrid_scheduler": {
        "yes": 120,
        "no_show": 30,
        "canceled": 30,
        "needs_reschedule": 30,
        "default": 30,
    },
}

# ---------------------------
# Helpers
# ---------------------------

def _map_lead_row(row):
    """
    Converte a linha de lead em dict e injeta a próxima ação (nextScheduledAction)
    com base nos campos next_start_at / next_description vindos do JOIN.
    Mantemos ISO string (UI converte para Date no front).
    """
    lead_dict = dict(row)
    next_date = lead_dict.pop("next_start_at", None)
    next_iso = normalize_datetime_value(next_date)
    next_description = lead_dict.pop("next_description", None)

    next_action = None
    if next_iso:
        next_action = {
            "date": next_iso,
            "description": next_description or "",
        }

    lead_dict["nextScheduledAction"] = next_action

    # normaliza createdAt/lastMovement se vierem com espaço
    for k in ("createdAt", "lastMovement"):
        if lead_dict.get(k):
            lead_dict[k] = str(lead_dict[k]).replace(" ", "T")

    normalized_contract = _normalize_followup_contract(
        lead_dict.get("followup_contract"),
        agent_type=lead_dict.get("agent_type"),
    )
    lead_dict["followup_contract"] = normalized_contract

    if normalized_contract:
        if lead_dict.get("followup_status") is None:
            lead_dict["followup_status"] = normalized_contract.get("status")
        if lead_dict.get("next_followup_at") is None:
            lead_dict["next_followup_at"] = normalized_contract.get("next_followup_at")

    return lead_dict


def _resolve_followup_variant(agent_type: str) -> Optional[str]:
    return _FOLLOWUP_VARIANT_BY_AGENT_TYPE.get(str(agent_type or "").strip().lower())


def _resolve_max_attempts(followup_variant: Optional[str]) -> int:
    return int(_MAX_ATTEMPTS_BY_VARIANT.get(str(followup_variant or "").strip().lower(), 3))


def _resolve_first_followup_offset_minutes(
    *,
    followup_variant: Optional[str],
    meeting_or_session_happened: Optional[str],
) -> int:
    variant_key = str(followup_variant or "").strip().lower()
    scenario_key = str(meeting_or_session_happened or "").strip().lower()
    rules = _FIRST_FOLLOWUP_OFFSET_MINUTES.get(variant_key) or {"default": 30}
    return int(rules.get(scenario_key, rules.get("default", 30)))


def _normalize_followup_contract(raw_contract: Any, *, agent_type: Optional[str] = None) -> Optional[dict[str, Any]]:
    if not raw_contract:
        return None

    contract_data: Any = raw_contract
    if isinstance(raw_contract, str):
        try:
            contract_data = json.loads(raw_contract)
        except json.JSONDecodeError:
            return None

    if not isinstance(contract_data, dict):
        return None

    normalized = dict(contract_data)

    followup_variant = str(normalized.get("followup_variant") or "").strip().lower() or _resolve_followup_variant(agent_type or "")
    if followup_variant:
        normalized["followup_variant"] = followup_variant

    normalized.setdefault("version", FOLLOWUP_CONTRACT_VERSION)
    normalized.setdefault("status", "active")
    normalized.setdefault("attempts", 0)
    normalized.setdefault("max_attempts", _resolve_max_attempts(followup_variant))
    normalized.setdefault("next_followup_at", None)
    normalized.setdefault("last_followup_at", None)
    normalized.setdefault("stop_reason", None)

    return normalized


def _table_columns(conn, table_name: str) -> set[str]:
    cur = conn.cursor()
    rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _map_appointment_row(row):
    """
    Normaliza todos os timestamps para ISO com 'T' e devolve dict.
    """
    d = dict(row)
    for k in ("start_at", "end_at", "created_at", "updated_at"):
        if k in d:
            d[k] = normalize_datetime_value(d[k])
    return d


def _require_lead_for_user(conn, lead_id: int, user_id: int) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    )
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")


def _normalize_or_400(value, field_name: str) -> Optional[str]:
    """
    Usa normalize_datetime_value e, se inválido, lança 400 para o campo indicado.
    """
    try:
        return normalize_datetime_value(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Formato de data/hora inválido para {field_name}") from exc


def _list_tables_with_lead_id(conn) -> list[str]:
    """Retorna todas as tabelas do schema atual que possuem coluna `lead_id`."""
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT name
          FROM sqlite_master
         WHERE type = 'table'
           AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()

    tables_with_lead_id: list[str] = []
    for row in rows:
        table_name = row[0]
        columns = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
        if any(str(col[1]).lower() == "lead_id" for col in columns):
            tables_with_lead_id.append(table_name)

    return tables_with_lead_id


def _delete_lead_related_rows(conn, lead_id: int) -> dict[str, int]:
    """Apaga registros por lead_id em todas as tabelas que possuem essa coluna."""
    cur = conn.cursor()
    deleted_by_table: dict[str, int] = {}

    table_names = _list_tables_with_lead_id(conn)
    ordered_tables = [table for table in table_names if table != "leads"]

    for table in ordered_tables:
        cur.execute(f"DELETE FROM {table} WHERE lead_id = ?", (lead_id,))
        deleted_by_table[table] = cur.rowcount if cur.rowcount is not None else 0

    cur.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    deleted_by_table["leads"] = cur.rowcount if cur.rowcount is not None else 0

    return deleted_by_table


def _check_conflict(
    conn,
    lead_id: int,
    start_at,
    end_at,
    *,
    ignore_appointment_id: Optional[int] = None,
):
    """
    Normaliza start/end e checa sobreposição com outros compromissos do mesmo lead.
    Regra: há conflito quando um outro registro tem start < end_do_novo
    E (end ou start se end for nulo) > start_do_novo.
    """
    start_iso = _normalize_or_400(start_at, "start_at")
    if start_iso is None:
        raise HTTPException(status_code=400, detail="start_at é obrigatório")

    end_iso = None
    if end_at is not None:
        end_iso = _normalize_or_400(end_at, "end_at")

    # se não veio fim, considere 0 duração (usa start em ambos)
    end_for_overlap = end_iso or start_iso

    cur = conn.cursor()
    query = (
        "SELECT id FROM appointments "
        "WHERE lead_id = ? "
        "AND datetime(start_at) < datetime(?) "
        "AND datetime(COALESCE(end_at, start_at)) > datetime(?)"
    )
    params = [lead_id, end_for_overlap, start_iso]

    if ignore_appointment_id is not None:
        query += " AND id != ?"
        params.append(ignore_appointment_id)

    cur.execute(query, params)
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Já existe um compromisso conflitante para este período.")

    return start_iso, end_iso


# ---------------------------
# Endpoints
# ---------------------------

@router.get("/")
def listar_leads(current_user: CurrentUser = Depends(require_crm_access)):
    """
    Lista leads e injeta a próxima ação agendada por lead (compromisso futuro mais próximo).
    Evita comparação naive/aware no Python — usamos datetime() do SQLite.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT l.*,
                   next_app.start_at AS next_start_at,
                   next_app.description AS next_description
            FROM leads l
            LEFT JOIN (
                SELECT lead_id, start_at, description
                FROM (
                    SELECT a.lead_id,
                           a.start_at,
                           a.description,
                           ROW_NUMBER() OVER (
                               PARTITION BY a.lead_id
                               ORDER BY datetime(a.start_at) ASC
                           ) AS rn
                    FROM appointments a
                    WHERE datetime(a.start_at) >= datetime('now')
                )
                WHERE rn = 1
            ) AS next_app
            ON next_app.lead_id = l.id
            WHERE l.user_id = ?
            ORDER BY l.createdAt DESC
            """
            ,
            (current_user.id,),
        )
        leads = cursor.fetchall()
        return [_map_lead_row(lead) for lead in leads]
    finally:
        conn.close()


@router.post("/")
def criar_lead(lead: Lead, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        rate_limit_service.ensure_max_leads(
            user_id=current_user.id,
            entitlements=current_user.entitlements,
            amount_to_add=1,
            conn=conn,
        )
        # usa 1 como default se priority vier None
        priority = lead.priority or 1

        phone_e164 = ""
        if lead.phone:
            try:
                phone_e164 = normalize_to_e164(lead.phone, lead.country_code)
            except PhoneNormalizationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            existing = cursor.execute(
                "SELECT * FROM leads WHERE user_id = ? AND phone = ? LIMIT 1",
                (current_user.id, phone_e164),
            ).fetchone()
            if existing:
                out = {k: existing[k] for k in existing.keys()}
                for k in ("createdAt", "lastMovement"):
                    if out.get(k):
                        out[k] = str(out[k]).replace(" ", "T")
                out["nextScheduledAction"] = None
                out["status"] = "exists"
                out["lead_id"] = out.get("id")
                return out

        resolved_agent_type = lead.agent_type or resolve_agent_type_for_user(
            user_id=current_user.id,
            token=current_user.token,
        )

        cursor.execute(
            """
            INSERT INTO leads (
                user_id, companyName, contactName, phone, email, origin, category,
                customMessage, observations, agent_type, priority, createdAt, lastMovement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                current_user.id,
                lead.companyName,
                lead.contactName,
                phone_e164 or None,
                lead.email,
                lead.origin,
                lead.category,
                lead.customMessage,
                lead.observations,
                resolved_agent_type,
                priority,
            ),
        )
        conn.commit()
        lead_id = cursor.lastrowid

        # opcional: ler de volta para devolver os timestamps realmente gravados no SQLite
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()

        if row:
            out = {k: row[k] for k in row.keys()}
            for k in ("createdAt", "lastMovement"):
                if out.get(k):
                    out[k] = str(out[k]).replace(" ", "T")
            out["nextScheduledAction"] = None
            return out

        # fallback: se por algum motivo não leu a linha, monta manual com now em UTC
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "id": lead_id,
            "companyName": lead.companyName,
            "contactName": lead.contactName,
            "phone": phone_e164 or None,
            "email": lead.email,
            "origin": lead.origin,
            "category": lead.category,
            "customMessage": lead.customMessage,
            "observations": lead.observations,
            "agent_type": resolved_agent_type,
            "priority": priority,
            "createdAt": now_iso,
            "lastMovement": now_iso,
            "nextScheduledAction": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/start-followup")
def start_followup_transition(
    payload: StartFollowupPayload,
    current_user: CurrentUser = Depends(require_crm_access),
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT id, user_id, category, agent_type FROM leads WHERE id = ? AND user_id = ?",
            (payload.lead_id, current_user.id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        current_category = str(row["category"] or "").strip().lower()
        if current_category != "apresentation":
            raise HTTPException(status_code=400, detail="Transição assistida só é permitida de apresentation para follow-up")

        db_agent_type = str(row["agent_type"] or "").strip().lower()
        if db_agent_type and db_agent_type != payload.agent_type:
            raise HTTPException(status_code=400, detail="agent_type enviado difere do lead")

        if payload.agent_type not in {"agent_1", "agent_3"}:
            raise HTTPException(status_code=400, detail="Transição assistida disponível apenas para agent_1 e agent_3")

        can_advance, missing_fields = can_advance_from_qualification(conn, payload.lead_id, current_user.id)
        if not can_advance:
            logger.info(
                "lead_category_blocked_incomplete_qualification lead_id=%s missing=%s origin=followup",
                payload.lead_id,
                missing_fields,
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "qualification_incomplete",
                    "missing_fields": missing_fields,
                    "message": "Não é possível iniciar follow-up: qualification incompleta",
                },
            )

        followup_variant = _resolve_followup_variant(payload.agent_type)
        if not followup_variant:
            raise HTTPException(status_code=400, detail="Não foi possível resolver a variante de follow-up")

        ai_profile: dict = {}
        try:
            ai_profile = fetch_core_ai_profile(current_user.token) or {}
        except Exception:
            pass

        now_utc = datetime.now(timezone.utc)
        profile_max = ai_profile.get("followup_max_attempts")
        max_attempts = int(profile_max) if profile_max is not None else _resolve_max_attempts(followup_variant)
        profile_offset = ai_profile.get("followup_first_offset")
        if profile_offset is not None:
            first_offset_minutes = int(profile_offset)
        else:
            first_offset_minutes = _resolve_first_followup_offset_minutes(
                followup_variant=followup_variant,
                meeting_or_session_happened=payload.meeting_or_session_happened,
            )
        next_followup_at = (now_utc + timedelta(minutes=first_offset_minutes)).isoformat()
        meeting_happened = payload.meeting_or_session_happened == "yes"
        contract = {
            "phase": "follow-up",
            "version": FOLLOWUP_CONTRACT_VERSION,
            "followup_variant": followup_variant,
            "trigger": "manual_crm_transition",
            "status": "active",
            "attempts": 0,
            "max_attempts": max_attempts,
            "next_followup_at": next_followup_at,
            "last_followup_at": None,
            "stop_reason": None,
            "meeting_happened": meeting_happened,
            "meeting_or_session_happened": payload.meeting_or_session_happened,
            "outcome": payload.outcome,
            "temperature": payload.outcome,
            "proposal_sent": payload.proposal_sent,
            "followup_goal": payload.followup_goal,
            "operator_note": (payload.operator_note or "").strip() or None,
            "created_at": now_utc.isoformat(),
        }

        mirror_status = str(contract.get("status") or "active")
        mirror_next_followup_at = contract.get("next_followup_at")
        lead_columns = _table_columns(conn, "leads")
        has_followup_status = "followup_status" in lead_columns
        has_next_followup_at = "next_followup_at" in lead_columns

        update_set_parts = [
            "category = 'follow-up'",
            "bot_disabled = 0",
            "bot_disabled_reason = NULL",
            "followup_contract = ?",
            "agent_type = COALESCE(NULLIF(agent_type, ''), ?)",
            "lastMovement = CURRENT_TIMESTAMP",
        ]
        update_params = [
            json.dumps(contract, ensure_ascii=False),
            payload.agent_type,
        ]
        if has_followup_status:
            update_set_parts.append("followup_status = ?")
            update_params.append(mirror_status)
        if has_next_followup_at:
            update_set_parts.append("next_followup_at = ?")
            update_params.append(mirror_next_followup_at)

        update_params.extend([payload.lead_id, current_user.id])
        cursor.execute(
            f"""
            UPDATE leads
               SET {', '.join(update_set_parts)}
             WHERE id = ? AND user_id = ?
            """,
            update_params,
        )
        cursor.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'followup_started_manual', ?, ?)
            """,
            (
                payload.lead_id,
                json.dumps(contract, ensure_ascii=False),
                current_user.id,
            ),
        )
        conn.commit()
        return {
            "status": "ok",
            "lead_id": payload.lead_id,
            "category": "follow-up",
            "bot_disabled": False,
            "followup_contract": contract,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.patch("/{id}")
def atualizar_lead_parcial(id: int, lead: LeadUpdate, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _require_lead_for_user(conn, id, current_user.id)
        row = cursor.execute(
            "SELECT category FROM leads WHERE id = ? AND user_id = ?",
            (id, current_user.id),
        ).fetchone()
        old_category = (row["category"] if row else None)

        campos = []
        valores = []

        dados = lead.dict(exclude_unset=True)
        # UI manda nextScheduledAction junto; não é campo da tabela leads:
        dados.pop("nextScheduledAction", None)

        if "category" in dados:
            normalized_old = str(old_category or "").strip().lower()
            normalized_new = str(dados.get("category") or "").strip().lower()
            if normalized_old == "qualification" and normalized_new in {"apresentation", "follow-up", "closing"}:
                can_advance, missing_fields = can_advance_from_qualification(conn, id, current_user.id)
                if not can_advance:
                    logger.info(
                        "lead_category_blocked_incomplete_qualification lead_id=%s missing=%s origin=patch",
                        id,
                        missing_fields,
                    )
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "qualification_incomplete",
                            "missing_fields": missing_fields,
                            "message": "Não é possível avançar o lead: qualification incompleta",
                        },
                    )

        if "phone" in dados:
            raw_phone = dados.get("phone")
            if raw_phone:
                try:
                    normalized_phone = normalize_to_e164(raw_phone, dados.get("country_code"))
                except PhoneNormalizationError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc

                conflict = cursor.execute(
                    "SELECT id FROM leads WHERE user_id = ? AND phone = ? AND id != ? LIMIT 1",
                    (current_user.id, normalized_phone, id),
                ).fetchone()
                if conflict:
                    raise HTTPException(status_code=409, detail="Telefone já cadastrado para outro lead")
                dados["phone"] = normalized_phone
            else:
                dados["phone"] = None
        dados.pop("country_code", None)

        for campo, valor in dados.items():
            if isinstance(valor, datetime):
                valor = valor.isoformat()
            campos.append(f"{campo} = ?")
            valores.append(valor)

        if not campos:
            raise HTTPException(status_code=400, detail="Nenhum dado enviado para atualização")

        campos.append("lastMovement = CURRENT_TIMESTAMP")

        sql = f"UPDATE leads SET {', '.join(campos)} WHERE id = ? AND user_id = ?"
        valores.extend([id, current_user.id])

        cursor.execute(sql, valores)

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        new_category = dados.get("category", old_category)
        apply_closing_bot_disable_side_effect(
            conn,
            lead_id=id,
            user_id=current_user.id,
            old_category=old_category,
            new_category=new_category,
        )
        stop_followup_for_lead_category(
            conn,
            lead_id=id,
            user_id=current_user.id,
            new_category=new_category,
        )
        conn.commit()

        return {"message": "Lead atualizado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{id}")
def excluir_lead(id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM leads WHERE id = ? AND user_id = ?", (id, current_user.id))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        deleted_by_table = _delete_lead_related_rows(conn, id)
        if deleted_by_table.get("leads", 0) == 0:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        conn.commit()
        logger.info("lead_deleted lead_id=%s deleted_by_table=%s", id, deleted_by_table)
        return {"status": "ok", "deleted_lead_id": id}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{lead_id}/bot-disabled")
def update_lead_bot_disabled(
    lead_id: int,
    payload: BotDisabledUpdate,
    current_user: CurrentUser = Depends(require_crm_access),
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _require_lead_for_user(conn, lead_id, current_user.id)
        cursor.execute(
            """
            UPDATE leads
               SET bot_disabled = ?,
                   bot_disabled_reason = ?,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ? AND user_id = ?
            """,
            (
                1 if payload.disabled else 0,
                (payload.reason or None) if payload.disabled else None,
                lead_id,
                current_user.id,
            ),
        )
        notes = {"disabled": payload.disabled}
        if payload.reason:
            notes["reason"] = payload.reason
        cursor.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'bot_disabled_changed', ?, ?)
            """,
            (lead_id, json.dumps(notes, ensure_ascii=False), current_user.id),
        )
        if payload.disabled:
            stop_followup_on_handoff(
                conn,
                lead_id=lead_id,
                user_id=current_user.id,
                reason=payload.reason,
            )
        conn.commit()
        return {"status": "ok", "lead_id": lead_id, "bot_disabled": payload.disabled}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{lead_id}/appointments")
def listar_compromissos(lead_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _require_lead_for_user(conn, lead_id, current_user.id)

        cursor.execute(
            """
            SELECT *
            FROM appointments
            WHERE lead_id = ?
            ORDER BY start_at ASC
            """,
            (lead_id,),
        )
        rows = cursor.fetchall()
        return [_map_appointment_row(row) for row in rows]
    finally:
        conn.close()


@router.post("/{lead_id}/appointments")
def criar_compromisso(lead_id: int, payload: AppointmentCreate, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        _require_lead_for_user(conn, lead_id, current_user.id)

        # Título/Status padrão se não vierem no payload
        title = payload.title or "Compromisso"
        status = payload.status or "pending"

        # --- NOVO: normalizar datas e default de end_at ---
        start_iso = normalize_datetime_value(payload.start_at)
        end_iso = normalize_datetime_value(payload.end_at) if payload.end_at else start_iso
        if not start_iso:
            raise HTTPException(status_code=400, detail="start_at inválido")

        # Checagem de conflito usando os valores já normalizados
        normalized_start, normalized_end = _check_conflict(
            conn,
            lead_id,
            start_iso,
            end_iso,
        )

        # Inserção
        cursor.execute(
            """
            INSERT INTO appointments (
                lead_id, title, description, type, start_at, end_at, status, location,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                lead_id,
                title,
                payload.description,
                payload.type,
                normalized_start,
                normalized_end,
                status,
                payload.location,
            ),
        )
        conn.commit()
        appointment_id = cursor.lastrowid

        # Retorna o registro recém-criado
        cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        row = cursor.fetchone()
        return _map_appointment_row(row)

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.patch("/{lead_id}/appointments/{appointment_id}")
def atualizar_compromisso(lead_id: int, appointment_id: int, payload: AppointmentUpdate, current_user: CurrentUser = Depends(require_crm_access)):
    """
    Atualiza compromisso garantindo normalização de datas e checagem de conflito.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _require_lead_for_user(conn, lead_id, current_user.id)
        # Verifica se existe
        cursor.execute(
            "SELECT * FROM appointments WHERE id = ? AND lead_id = ?",
            (appointment_id, lead_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Compromisso não encontrado")

        dados = payload.dict(exclude_unset=True)
        if not dados:
            # nada para atualizar; devolve estado atual mapeado
            return _map_appointment_row(row)

        # Se start/end forem alterados, normalizamos valores finais para manter coerência.
        # Regra mínima de hardening: end_at ausente ou menor que start_at -> end_at = start_at.
        new_start = dados.get("start_at", None)
        new_end = dados.get("end_at", None)
        if new_start is not None or new_end is not None:
            start_final_iso = normalize_datetime_value(new_start if new_start is not None else row["start_at"])
            end_candidate = new_end if new_end is not None else row["end_at"]
            end_final_iso = normalize_datetime_value(end_candidate) if end_candidate is not None else None

            if not end_final_iso:
                end_final_iso = start_final_iso
            elif datetime.fromisoformat(end_final_iso) < datetime.fromisoformat(start_final_iso):
                end_final_iso = start_final_iso

            dados["start_at"] = start_final_iso
            dados["end_at"] = end_final_iso

            _check_conflict(
                conn,
                lead_id,
                start_final_iso,
                end_final_iso,
                ignore_appointment_id=appointment_id,
            )

        campos = []
        valores = []

        for campo, valor in dados.items():
            if campo in ("start_at", "end_at") and valor is not None:
                # aceita datetime do Pydantic ou string; grava como ISO
                if isinstance(valor, datetime):
                    valor = valor.isoformat()
            campos.append(f"{campo} = ?")
            valores.append(valor)

        campos.append("updated_at = CURRENT_TIMESTAMP")

        sql = f"UPDATE appointments SET {', '.join(campos)} WHERE id = ? AND lead_id = ?"
        valores.extend([appointment_id, lead_id])

        cursor.execute(sql, valores)
        conn.commit()

        cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        row = cursor.fetchone()
        return _map_appointment_row(row)

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{lead_id}/appointments/{appointment_id}")
def remover_compromisso(lead_id: int, appointment_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _require_lead_for_user(conn, lead_id, current_user.id)
        cursor.execute(
            "DELETE FROM appointments WHERE id = ? AND lead_id = ?",
            (appointment_id, lead_id),
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Compromisso não encontrado")

        return {"message": "Compromisso removido com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ---------------------------
# Follow-up pause / resume / cancel
# ---------------------------

@router.post("/{id}/followup/pause")
def pause_followup(id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        _require_lead_for_user(conn, id, current_user.id)
        result = pause_followup_manually(conn, lead_id=id, user_id=current_user.id)
        if not result.get("updated"):
            reason = result.get("reason", "unknown")
            if reason == "lead_not_found":
                raise HTTPException(status_code=404, detail="Lead não encontrado")
            if reason == "contract_missing":
                raise HTTPException(status_code=400, detail="Lead não tem contrato de follow-up")
            if reason == "invalid_status":
                raise HTTPException(
                    status_code=409,
                    detail=f"Não é possível pausar: status atual é '{result.get('current_status')}'",
                )
            raise HTTPException(status_code=400, detail=reason)
        conn.commit()
        return result
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{id}/followup/resume")
def resume_followup(id: int, current_user: CurrentUser = Depends(require_crm_access)):
    ai_profile: dict = {}
    try:
        ai_profile = fetch_core_ai_profile(current_user.token) or {}
    except Exception:
        pass

    conn = get_connection()
    try:
        _require_lead_for_user(conn, id, current_user.id)
        result = resume_followup_manually(conn, lead_id=id, user_id=current_user.id, ai_profile=ai_profile)
        if not result.get("updated"):
            reason = result.get("reason", "unknown")
            if reason == "lead_not_found":
                raise HTTPException(status_code=404, detail="Lead não encontrado")
            if reason == "contract_missing":
                raise HTTPException(status_code=400, detail="Lead não tem contrato de follow-up")
            if reason == "not_manually_paused":
                raise HTTPException(
                    status_code=409,
                    detail=f"Não é possível retomar: status atual é '{result.get('current_status')}'",
                )
            if reason == "max_attempts_reached":
                raise HTTPException(status_code=409, detail="Número máximo de tentativas já atingido")
            raise HTTPException(status_code=400, detail=reason)
        conn.commit()
        return result
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{id}/followup/cancel")
def cancel_followup(id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        _require_lead_for_user(conn, id, current_user.id)
        result = cancel_followup_manually(conn, lead_id=id, user_id=current_user.id)
        if not result.get("updated"):
            reason = result.get("reason", "unknown")
            if reason == "lead_not_found":
                raise HTTPException(status_code=404, detail="Lead não encontrado")
            if reason == "contract_missing":
                raise HTTPException(status_code=400, detail="Lead não tem contrato de follow-up")
            if reason == "already_closed":
                raise HTTPException(status_code=409, detail="Follow-up já está encerrado")
            raise HTTPException(status_code=400, detail=reason)
        conn.commit()
        return result
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
