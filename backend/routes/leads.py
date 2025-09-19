from fastapi import APIRouter, HTTPException
from models import Lead
from database import get_connection
import datetime
from models import LeadUpdate

router = APIRouter()

@router.get("/")
def listar_leads():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY createdAt DESC")
    leads = cursor.fetchall()
    conn.close()
    return [dict(lead) for lead in leads]

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

        for campo, valor in lead.dict(exclude_unset=True).items():
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
