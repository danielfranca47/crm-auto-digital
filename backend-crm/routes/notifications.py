# routes/notifications.py
from fastapi import APIRouter, HTTPException, Depends

from database import get_connection
from security_core import CurrentUser, require_crm_access

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("/unread")
def get_unread_notifications(user: CurrentUser = Depends(require_crm_access)):
    """Retorna notificações não lidas do usuário (últimas 50)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT n.id, n.lead_id, n.type, n.created_at,
                   l.companyName, l.contactName
              FROM notifications n
         LEFT JOIN leads l ON l.id = n.lead_id
             WHERE n.user_id = ? AND n.read = 0
          ORDER BY n.created_at DESC
             LIMIT 50
            """,
            (user["user_id"],),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user: CurrentUser = Depends(require_crm_access),
):
    """Marca uma notificação como lida."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user["user_id"]),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notificação não encontrada")
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user: CurrentUser = Depends(require_crm_access)):
    """Marca todas as notificações não lidas do usuário como lidas."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0",
            (user["user_id"],),
        )
        conn.commit()
    return {"ok": True}
