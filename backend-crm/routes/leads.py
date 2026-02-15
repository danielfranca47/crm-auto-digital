# backend/routes/leads.py
from typing import Optional
import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

from database import get_connection, normalize_datetime_value
from models import Lead, LeadUpdate, AppointmentCreate, AppointmentUpdate, BotDisabledUpdate
from security_core import CurrentUser, require_crm_access
from services import rate_limit_service

router = APIRouter()
logger = logging.getLogger(__name__)

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

    return lead_dict


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

        cursor.execute(
            """
            INSERT INTO leads (
                user_id, companyName, contactName, phone, email, origin, category,
                customMessage, observations, priority, createdAt, lastMovement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                current_user.id,
                lead.companyName,
                lead.contactName,
                lead.phone,
                lead.email,
                lead.origin,
                lead.category,
                lead.customMessage,
                lead.observations,
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
            "phone": lead.phone,
            "email": lead.email,
            "origin": lead.origin,
            "category": lead.category,
            "customMessage": lead.customMessage,
            "observations": lead.observations,
            "priority": priority,
            "createdAt": now_iso,
            "lastMovement": now_iso,
            "nextScheduledAction": None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.patch("/{id}")
def atualizar_lead_parcial(id: int, lead: LeadUpdate, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _require_lead_for_user(conn, id, current_user.id)
        campos = []
        valores = []

        dados = lead.dict(exclude_unset=True)
        # UI manda nextScheduledAction junto; não é campo da tabela leads:
        dados.pop("nextScheduledAction", None)

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
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

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
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ? AND user_id = ?
            """,
            (1 if payload.disabled else 0, lead_id, current_user.id),
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
