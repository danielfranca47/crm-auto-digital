from fastapi import APIRouter, Depends, HTTPException

from database import get_connection
from models import BotResumeModePayload
from security_core import CurrentUser, require_crm_access
from services import bot_global_pause

router = APIRouter(prefix="/api/bot-pause", tags=["Bot Pause"])


@router.get("/status")
def get_bot_pause_status(current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        return bot_global_pause.get_status(conn, user_id=current_user.id)
    finally:
        conn.close()


@router.post("/pause")
def pause_all_bots(current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        result = bot_global_pause.pause_all(conn, user_id=current_user.id)
        conn.commit()
        return {"status": "ok", **result}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/resume")
def resume_all_bots(
    payload: BotResumeModePayload,
    current_user: CurrentUser = Depends(require_crm_access),
):
    conn = get_connection()
    try:
        result = bot_global_pause.resume_all(conn, user_id=current_user.id, mode=payload.mode)
        conn.commit()
        return {"status": "ok", **result}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
