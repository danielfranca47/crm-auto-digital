from fastapi import APIRouter, HTTPException
from database import get_connection
import datetime
from models import Lead, LeadUpdate, AppointmentCreate, AppointmentUpdate


def _map_lead_row(row):
    lead_dict = dict(row)
    next_date = lead_dict.pop("next_start_at", None)
    next_description = lead_dict.pop("next_description", None)

    next_action = None
    if next_date:
        next_action = {
            "date": next_date,
            "description": next_description or "",
        }

    lead_dict["nextScheduledAction"] = next_action
    return lead_dict


def _map_appointment_row(row):
    appointment = dict(row)
    return appointment


def _parse_db_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(value.replace(' ', 'T'))


def _check_conflict(cursor, lead_id, start_at, end_at, ignore_appointment_id=None):
    if start_at is None:
        raise HTTPException(status_code=400, detail="start_at é obrigatório")

    compare_end = end_at or start_at
    params = [lead_id]
    query = [
        "SELECT 1",
        "FROM appointments",
        "WHERE lead_id = ?",
    ]

    if ignore_appointment_id is not None:
        query.append("AND id != ?")
        params.append(ignore_appointment_id)

    query.extend(
        [
            "AND datetime(start_at) <= datetime(?)",
            "AND datetime(COALESCE(end_at, start_at)) >= datetime(?)",
            "LIMIT 1",
        ]
    )

    params.extend([compare_end.isoformat(), start_at.isoformat()])

    cursor.execute('\n'.join(query), tuple(params))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Já existe um compromisso nesse intervalo")


router = APIRouter()

@router.get("/")
def listar_leads():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT l.*, next_app.start_at AS next_start_at, next_app.description AS next_description
        FROM leads l
        LEFT JOIN (
            SELECT id, lead_id, start_at, description
            FROM (
                SELECT a.*, ROW_NUMBER() OVER (PARTITION BY lead_id ORDER BY start_at ASC) AS rn
                FROM appointments a
                WHERE a.start_at >= CURRENT_TIMESTAMP
            )
            WHERE rn = 1
        ) AS next_app ON next_app.lead_id = l.id
        ORDER BY l.createdAt DESC
        """
    )
    leads = cursor.fetchall()
    conn.close()
    return [_map_lead_row(lead) for lead in leads]

@router.post("/")
def criar_lead(lead: Lead):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO leads (
                companyName, contactName, phone, email, origin, category,
                customMessage, observations, priority, createdAt, lastMovement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            lead.companyName,
            lead.contactName,
            lead.phone,
            lead.email,
            lead.origin,
            lead.category,
            lead.customMessage,
            lead.observations,
            lead.priority or 1
        ))
        conn.commit()
        lead_id = cursor.lastrowid

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
            "createdAt": datetime.datetime.now().isoformat(),      # Opcional: você pode retornar um timestamp real aqui se quiser
            "lastMovement": datetime.datetime.now().isoformat()
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
        dados.pop("nextScheduledAction", None)

        for campo, valor in dados.items():
            if isinstance(valor, datetime.datetime):
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

        return { "message": "Lead atualizado com sucesso" }

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
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM leads WHERE id = ?", (lead_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        _check_conflict(cursor, lead_id, payload.start_at, payload.end_at)

        cursor.execute(
            """
            INSERT INTO appointments (lead_id, description, start_at, end_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                lead_id,
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

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        conn.close()


@router.patch("/{lead_id}/appointments/{appointment_id}")
def atualizar_compromisso(lead_id: int, appointment_id: int, payload: AppointmentUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        current = cursor.execute("SELECT * FROM appointments WHERE id = ? AND lead_id = ?", (appointment_id, lead_id)).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="Compromisso não encontrado")

        dados = payload.dict(exclude_unset=True)
        if not dados:
            raise HTTPException(status_code=400, detail="Nenhum dado enviado para atualização")

        campos = []
        valores = []

        final_start = _parse_db_datetime(current["start_at"])
        final_end = _parse_db_datetime(current["end_at"])

        if "description" in dados:
            campos.append("description = ?")
            valores.append(dados["description"])

        if "start_at" in dados:
            novo_inicio = dados["start_at"]
            if novo_inicio is None:
                raise HTTPException(status_code=400, detail="start_at não pode ser nulo")
            final_start = novo_inicio
            campos.append("start_at = ?")
            valores.append(novo_inicio.isoformat())

        if "end_at" in dados:
            novo_fim = dados["end_at"]
            final_end = novo_fim
            campos.append("end_at = ?")
            valores.append(novo_fim.isoformat() if novo_fim else None)

        if not campos:
            raise HTTPException(status_code=400, detail="Nenhum dado enviado para atualização")

        _check_conflict(cursor, lead_id, final_start, final_end, ignore_appointment_id=appointment_id)

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
