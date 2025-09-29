from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_connection
from models import AppointmentCreate, AppointmentUpdate

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


def _row_to_dict(row) -> dict:
    data = dict(row)
    for key in ("start_time", "end_time", "created_at", "updated_at"):
        value = data.get(key)
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, str):
            # sqlite pode retornar string; normaliza para isoformat sem alterar se já estiver
            try:
                data[key] = datetime.fromisoformat(value).isoformat()
            except ValueError:
                pass
    return data


@router.get("/")
def list_appointments(
    start: Optional[str] = Query(None, description="ISO datetime mínimo"),
    end: Optional[str] = Query(None, description="ISO datetime máximo"),
    status: Optional[str] = Query(None, description="Filtra por status"),
    lead_id: Optional[int] = Query(None, description="Filtra por lead"),
) -> List[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = [
            "SELECT a.*, l.companyName AS lead_company, l.contactName AS lead_contact",
            "FROM appointments a",
            "LEFT JOIN leads l ON l.id = a.lead_id",
            "WHERE 1 = 1",
        ]
        params: List[object] = []

    if status:
        query.append("AND a.status = ?")
        params.append(status)
    if lead_id is not None:
        query.append("AND a.lead_id = ?")
        params.append(lead_id)
    if start:
        try:
            start_iso = datetime.fromisoformat(start).isoformat()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Parâmetro 'start' inválido") from exc
        query.append("AND a.start_time >= ?")
        params.append(start_iso)
    if end:
        try:
            end_iso = datetime.fromisoformat(end).isoformat()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Parâmetro 'end' inválido") from exc
        query.append("AND a.start_time <= ?")
        params.append(end_iso)

        query.append("ORDER BY a.start_time ASC")

        cursor.execute("\n".join(query), params)
        rows = cursor.fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/{appointment_id}")
def get_appointment(appointment_id: int) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.*, l.companyName AS lead_company, l.contactName AS lead_contact
            FROM appointments a
            LEFT JOIN leads l ON l.id = a.lead_id
            WHERE a.id = ?
            """,
            (appointment_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return _row_to_dict(row)
    finally:
        conn.close()


@router.post("/")
def create_appointment(payload: AppointmentCreate) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO appointments (
                lead_id, title, description, type, status, start_time, end_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.lead_id,
                payload.title,
                payload.description,
                payload.type,
                payload.status,
                payload.start_time.isoformat(),
                payload.end_time.isoformat() if payload.end_time else None,
            ),
        )
        conn.commit()
        appointment_id = cursor.lastrowid
        return get_appointment(appointment_id)
    except Exception as exc:  # pragma: no cover - FastAPI converte para JSON
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@router.patch("/{appointment_id}")
def update_appointment(appointment_id: int, payload: AppointmentUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        fields = []
        params: List[object] = []
        for key, value in updates.items():
            if key in {"start_time", "end_time"} and value is not None:
                value = value.isoformat()
            fields.append(f"{key} = ?")
            params.append(value)

        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(appointment_id)

        sql = f"UPDATE appointments SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(sql, params)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Appointment not found")
        conn.commit()
        return get_appointment(appointment_id)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:  # pragma: no cover
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@router.delete("/{appointment_id}")
def delete_appointment(appointment_id: int) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Appointment not found")
        conn.commit()
        return {"ok": True}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
