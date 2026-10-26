"""
Pull Google Calendar → CRM: importa os eventos do Google de um período para `appointments`
(source='google', lead_id NULL) e remove os que já não existem no Google.

Usado pela rota POST /api/appointments/google-sync (clique na Agenda) e pelo orchestrator
antes de montar calendar_busy_slots (agente agendador).

Só apaga com uma leitura bem-sucedida da Google: se list_events falhar, GoogleCalendarError
propaga e nada é alterado — uma falha de permissão ou de rede nunca esvazia a agenda importada.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from database import get_connection
from services.google_calendar_service import list_events

logger = logging.getLogger(__name__)


def sync_user_google_events(user_id: int, start: str, end: str, timeout: float = 10.0) -> Optional[int]:
    """Sincroniza o período [start, end] do Google do utilizador.

    Retorna None se o utilizador não tem o Google ligado, ou o número de eventos lidos.
    Lança GoogleCalendarError quando a Google falha.
    """
    google_events = list_events(user_id=user_id, time_min=start, time_max=end, timeout=timeout)
    if google_events is None:
        return None

    conn = get_connection()
    try:
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        synced_ids: List[str] = []

        for event in google_events:
            gid = event.get("id")
            if not gid:
                continue
            synced_ids.append(gid)

            start_dt = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date") or ""
            end_dt = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date") or start_dt
            title = event.get("summary") or "Evento Google"
            description = event.get("description")
            # "transparent" = marcado como Disponível no Google (padrão dos eventos de dia inteiro)
            transparency = event.get("transparency")

            existing = cur.execute(
                "SELECT id FROM appointments WHERE google_event_id = ? AND user_id = ?",
                (gid, user_id),
            ).fetchone()

            if existing:
                cur.execute(
                    "UPDATE appointments SET title = ?, description = ?, start_at = ?, end_at = ?,"
                    " google_transparency = ?, updated_at = ?"
                    " WHERE google_event_id = ? AND user_id = ?",
                    (title, description, start_dt, end_dt, transparency, now, gid, user_id),
                )
            else:
                cur.execute(
                    "INSERT INTO appointments"
                    " (user_id, lead_id, title, description, type, status, start_at, end_at, source,"
                    " google_event_id, google_transparency, created_at, updated_at)"
                    " VALUES (?, NULL, ?, ?, 'meeting', 'pending', ?, ?, 'google', ?, ?, ?, ?)",
                    (user_id, title, description, start_dt, end_dt, gid, transparency, now, now),
                )

        # Remove Google appointments deste período que já não existem no Google
        if synced_ids:
            placeholders = ",".join("?" * len(synced_ids))
            cur.execute(
                f"DELETE FROM appointments"
                f" WHERE source = 'google' AND user_id = ? AND start_at >= ? AND start_at <= ?"
                f" AND google_event_id NOT IN ({placeholders})",
                [user_id, start, end, *synced_ids],
            )
        else:
            cur.execute(
                "DELETE FROM appointments"
                " WHERE source = 'google' AND user_id = ? AND start_at >= ? AND start_at <= ?",
                (user_id, start, end),
            )

        conn.commit()
        return len(synced_ids)
    finally:
        conn.close()
