from fastapi import APIRouter, HTTPException
from database import get_connection
import datetime
from models import Lead, LeadUpdate, AppointmentCreate, AppointmentUpdate


def _map_lead_row(row):
    """
    Converte a linha de lead em dict e injeta a próxima ação (nextScheduledAction)
    com base nos campos next_start_at / next_description vindos do JOIN.
    Mantemos ISO string (UI converte para Date no front).
    """
    lead_dict = dict(row)
    next_date = lead_dict.pop("next_start_at", None)
    next_description = lead_dict.pop("next_description", None)

    next_iso = normalize_datetime_value(next_date)
    next_action = None
    if next_iso:
        next_action = {
            "date": next_iso,
            "description": next_description or "",
        }

    lead_dict["nextScheduledAction"] = next_action
    return lead_dict


def _map_appointment_row(row):
    """
    Normaliza todos os timestamps para ISO com 'T'.
    """
    appointment = dict(row)
    return appointment

router = APIRouter()

# ---------------------------
# Endpoints
# ---------------------------
@router.get("/")
def listar_leads():
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
            ORDER BY l.createdAt DESC
            """
        )
        leads = cursor.fetchall()
        return [_map_lead_row(lead) for lead in leads]
    finally:
        conn.close()


@router.post("/")
def criar_lead(lead: Lead):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO leads (
                companyName, contactName, phone, email, origin, category,
                customMessage, observations, priority, createdAt, lastMovement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                lead.companyName,
                lead.contactName,
                lead.phone,
                lead.email,
                lead.origin,
                lead.category,
                lead.customMessage,
                lead.observations,
                lead.priority or 1,
            ),
        )
        conn.commit()
        lead_id = cursor.lastrowid
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
            "priority": lead.priority or 1,
            "createdAt": now_iso,
            "lastMovement": now_iso,
            "nextScheduledAction": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.patch("/{id}")
def atualizar_lead_parcial(id: int, lead: LeadUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
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

        sql = f"UPDATE leads SET {', '.join(campos)} WHERE id = ?"
        valores.append(id)

        cursor.execute(sql, valores)
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        return {"message": "Lead atualizado com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{lead_id}/appointments")
def listar_compromissos(lead_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM leads WHERE id = ?", (lead_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

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
def criar_compromisso(lead_id: int, payload: AppointmentCreate):
    """
    Cria compromisso mínimo a partir de um Lead.
    Garante campos obrigatórios do schema (title, end_at, status).
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM leads WHERE id = ?", (lead_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        cursor.execute(
            """
            INSERT INTO appointments (
                lead_id, title, description, type, start_at, end_at, status, location, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                lead_id,
                title,
                payload.description,
                payload.start_at.isoformat(),
                payload.end_at.isoformat() if payload.end_at else None,
            ),
        )
        conn.commit()
        appointment_id = cursor.lastrowid

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
def atualizar_compromisso(lead_id: int, appointment_id: int, payload: AppointmentUpdate):
    """
    Atualiza compromisso garantindo normalização de datas e checagem de conflito.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        dados = payload.dict(exclude_unset=True)
        if not dados:
            raise HTTPException(status_code=400, detail="Nenhum dado enviado para atualização")

        campos = []
        valores = []

        for campo, valor in dados.items():
            if campo in ("start_at", "end_at") and valor is not None:
                valor = valor.isoformat()
            campos.append(f"{campo} = ?")
            valores.append(valor)

        if not valores:
            # nada para atualizar
            cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
            row = cursor.fetchone()
            return _map_appointment_row(row)

        campos.append("updated_at = CURRENT_TIMESTAMP")

        sql = f"UPDATE appointments SET {', '.join(campos)} WHERE id = ? AND lead_id = ?"
        valores.extend([appointment_id, lead_id])

        cursor.execute(sql, valores)
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Compromisso não encontrado")

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
def remover_compromisso(lead_id: int, appointment_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
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
