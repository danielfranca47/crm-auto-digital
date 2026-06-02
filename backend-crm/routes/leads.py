# backend/routes/leads.py
from typing import Any, Optional
import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta, timezone

from database import get_connection, normalize_datetime_value
import os
import uuid
from fastapi import UploadFile, File
from pathlib import Path
from models import Lead, LeadUpdate, AppointmentCreate, AppointmentUpdate, BotDisabledUpdate, StartFollowupPayload, QualificationPatchPayload, ScheduledMessagePayload, SendNowPayload
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
    progress_followup_after_auto_send,
)
from services.jobs_service import TYPE_WHATSAPP_SEND, TYPE_WHATSAPP_FOLLOWUP_PREGENERATE, create_job
from services.qualification_guardrails import can_advance_from_qualification
from services.qualification_state import upsert_qualification_state

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


def _generate_followup_message_llm(
    *,
    first_name: str,
    brand_name: str,
    niche: str,
    tone_of_voice: str,
    situation: str,
    goal: str,
    operator_note: str,
) -> str:
    import os
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("no key")
        client = OpenAI(api_key=api_key)
        identity = f"da {brand_name}" if brand_name else "do time de vendas"
        niche_line = f"do segmento de {niche}" if niche else ""
        context_parts = []
        if situation:
            context_parts.append(f"- Situação atual: {situation}")
        if goal:
            context_parts.append(f"- Objetivo desta mensagem: {goal}")
        if operator_note:
            context_parts.append(f"- Contexto adicional (use como orientação, não copie literalmente): {operator_note}")
        context_block = "\n".join(context_parts) if context_parts else "- Dar continuidade ao relacionamento comercial"
        system_prompt = (
            f"Você é um vendedor {identity} {niche_line}.\n"
            "Escreva UMA mensagem curta de follow-up para WhatsApp.\n"
            "REGRAS:\n"
            f"- Tom: {tone_of_voice}\n"
            "- Máximo 280 caracteres\n"
            "- Natural e humano, como uma pessoa real enviaria no WhatsApp\n"
            "- NÃO mencione número de tentativa, sequência ou contagem\n"
            "- NÃO use rótulos como 'Objetivo:', 'Contexto:', 'Situação:'\n"
            "- NÃO invente informações além do fornecido\n"
            "- Finalize com uma pergunta ou chamada para ação clara\n"
            "- Retorne APENAS o texto da mensagem, sem aspas, sem prefixo"
        )
        user_prompt = (
            f"Lead: {first_name}\n\n"
            f"Contexto interno (oriente a mensagem com base nisso):\n{context_block}"
        )
        r = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=200,
        )
        return r.choices[0].message.content.strip()
    except Exception:
        goal_sentence = f"Queria saber se você conseguiu avançar com {goal}." if goal else "Queria saber como posso te ajudar a dar o próximo passo."
        return (
            f"Oi {first_name}! Tudo bem?\n\n"
            f"{goal_sentence}\n\n"
            "Qualquer dúvida, pode falar comigo!"
        )


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
              AND (l.is_playground IS NULL OR l.is_playground = 0)
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
    from services.plan_gates import check_follow_up_enabled
    check_follow_up_enabled(current_user.entitlements)

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
            _SCORE_SENTINEL = "_below_threshold_"
            _real_missing = [k for k in missing_fields if _SCORE_SENTINEL not in k]
            _score_failure = any(_SCORE_SENTINEL in k for k in missing_fields)
            missing_fields_detail = []
            try:
                _profile = fetch_core_ai_profile(current_user.token) or {}
                _qfields = _profile.get("qualification_fields") or []
                _field_meta = {f["key"]: f for f in _qfields if isinstance(f, dict) and "key" in f}
                for _key in _real_missing:
                    _meta = _field_meta.get(_key, {})
                    missing_fields_detail.append({
                        "key": _key,
                        "label": _meta.get("label") or _key,
                        "question": _meta.get("question"),
                    })
                if _score_failure:
                    # Sempre exibir os 4 campos 4P — são os únicos que compute_4p_scores() lê.
                    # Campos custom do AI Profile (ex: "Quer agendar") não afetam o score,
                    # por isso não podem resolver uma falha de pontuação.
                    _active_keys = {d["key"] for d in missing_fields_detail}
                    _4p_defaults = [
                        ("decision_role", "Papel na decisão de compra", "O lead decide sozinho? Ex: 'Sim, sou eu' ou 'Preciso consultar meu sócio'"),
                        ("urgency", "Urgência / necessidade", "Qual a urgência? Ex: 'Precisa essa semana' ou 'Sem pressa por enquanto'"),
                        ("budget_or_price_acceptance", "Orçamento / aceitação de preço", "O lead aceitou o preço? Ex: 'Ok, tranquilo' ou 'Está um pouco caro'"),
                        ("availability_window", "Janela de disponibilidade", "Quando o lead tem disponibilidade? Ex: 'Terças de manhã' ou 'Qualquer dia da semana'"),
                    ]
                    for _key, _label, _question in _4p_defaults:
                        if _key not in _active_keys:
                            missing_fields_detail.append({"key": _key, "label": _label, "question": _question})
            except Exception:
                missing_fields_detail = [{"key": k, "label": k, "question": None} for k in _real_missing]
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "qualification_incomplete",
                    "missing_fields": missing_fields,
                    "missing_fields_detail": missing_fields_detail,
                    "score_failure": _score_failure,
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
            "meeting_or_session_happened": payload.meeting_or_session_happened,
            "outcome": payload.outcome,
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
        create_job(
            job_type=TYPE_WHATSAPP_FOLLOWUP_PREGENERATE,
            payload={"lead_id": payload.lead_id, "user_id": current_user.id},
            user_id=current_user.id,
        )
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


@router.patch("/{lead_id}/qualification-fields")
def patch_lead_qualification_fields(
    lead_id: int,
    body: QualificationPatchPayload,
    current_user: CurrentUser = Depends(require_crm_access),
):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, current_user.id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        upsert_qualification_state(lead_id, current_user.id, {"data_json": body.fields})
        return {"status": "ok", "lead_id": lead_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{lead_id}/qualification-fields")
def get_lead_qualification_fields(
    lead_id: int,
    current_user: CurrentUser = Depends(require_crm_access),
):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, current_user.id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        state = conn.execute(
            "SELECT data_json FROM lead_qualification_state WHERE lead_id = ?",
            (lead_id,),
        ).fetchone()
        if not state:
            return {"fields": {}}
        import json as _json
        raw = state["data_json"]
        fields = _json.loads(raw) if isinstance(raw, str) else (raw or {})
        return {"fields": fields}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/followups/active")
def list_active_followups(current_user: CurrentUser = Depends(require_crm_access)):
    """Lista leads em follow-up não encerrado, ordenados por próximo envio."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, companyName, contactName, phone, category,
                   followup_status, next_followup_at, followup_contract,
                   agent_type, lastMovement, createdAt, bot_disabled
              FROM leads
             WHERE user_id = ?
               AND category = 'follow-up'
               AND COALESCE(followup_status, '') != 'closed'
               AND (is_playground IS NULL OR is_playground = 0)
             ORDER BY
               CASE COALESCE(followup_status,'')
                    WHEN 'active' THEN 0
                    WHEN 'scheduled' THEN 1
                    WHEN 'manually_paused' THEN 2
                    WHEN 'paused' THEN 3
                    ELSE 4 END,
               datetime(COALESCE(next_followup_at, '9999-12-31')) ASC
            """,
            (current_user.id,),
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["followup_contract"] = _normalize_followup_contract(
            d.get("followup_contract"),
            agent_type=d.get("agent_type"),
        )
        for k in ("createdAt", "lastMovement"):
            if d.get(k):
                d[k] = str(d[k]).replace(" ", "T")
        result.append(d)
    return result


@router.get("/followups/stats")
def followup_stats(current_user: CurrentUser = Depends(require_crm_access)):
    """Retorna métricas do stats bar da Central de Follow-ups."""
    now_utc = datetime.now(timezone.utc)
    two_hours_later = now_utc + timedelta(hours=2)
    today_date = now_utc.date()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT followup_status, next_followup_at, followup_contract, lastMovement
              FROM leads
             WHERE user_id = ?
               AND category = 'follow-up'
               AND COALESCE(followup_status, '') != 'closed'
               AND (is_playground IS NULL OR is_playground = 0)
            """,
            (current_user.id,),
        ).fetchall()

    total_active = len(rows)
    hot_active = 0
    urgent_count = 0
    replied_today = 0

    for row in rows:
        contract = _normalize_followup_contract(row["followup_contract"])
        temp = str((contract or {}).get("outcome") or "").lower()
        if temp == "hot":
            hot_active += 1

        status = str(row["followup_status"] or "").lower()
        if status in ("active", "scheduled") and row["next_followup_at"]:
            try:
                next_dt = datetime.fromisoformat(str(row["next_followup_at"]).replace("Z", "+00:00"))
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                if now_utc < next_dt <= two_hours_later:
                    urgent_count += 1
            except Exception:
                pass

        if status in ("paused", "manually_paused") and row["lastMovement"]:
            try:
                last_dt = datetime.fromisoformat(str(row["lastMovement"]).replace(" ", "T"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if last_dt.date() == today_date:
                    replied_today += 1
            except Exception:
                pass

    return {
        "total_active": total_active,
        "hot_active": hot_active,
        "urgent_count": urgent_count,
        "replied_today": replied_today,
    }


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


# ──────────────────────────────────────────────────────────────────────────────
# Edição Pré-Disparo (Tarefa 7)
# ──────────────────────────────────────────────────────────────────────────────

_FOLLOWUP_MEDIA_DIR = Path("data/uploads/followup-media")
_FOLLOWUP_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx", ".mp3", ".ogg", ".m4a", ".mp4", ".mov"}
_MEDIA_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


@router.get("/{lead_id}/followup/scheduled-message")
def get_scheduled_message(lead_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    """Retorna a mensagem agendada para a próxima tentativa de follow-up."""
    with get_connection() as conn:
        _require_lead_for_user(conn, lead_id, current_user.id)
        row = conn.execute(
            """
            SELECT followup_contract, followup_status, next_followup_at,
                   companyName, contactName, phone, agent_type
              FROM leads
             WHERE id = ? AND user_id = ?
            """,
            (lead_id, current_user.id),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    contract = _normalize_followup_contract(row["followup_contract"], agent_type=row["agent_type"])
    scheduled_msg = (contract or {}).get("scheduled_message") or {}

    return {
        "lead_id": lead_id,
        "companyName": row["companyName"],
        "contactName": row["contactName"],
        "phone": row["phone"],
        "agent_type": row["agent_type"],
        "followup_status": row["followup_status"],
        "next_followup_at": row["next_followup_at"],
        "scheduled_message": scheduled_msg,
        "contract": contract,
    }


@router.put("/{lead_id}/followup/scheduled-message")
def update_scheduled_message(
    lead_id: int,
    payload: ScheduledMessagePayload,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Salva edição manual da mensagem agendada em followup_contract.scheduled_message."""
    conn = get_connection()
    try:
        _require_lead_for_user(conn, lead_id, current_user.id)
        row = conn.execute(
            "SELECT followup_contract, agent_type FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, current_user.id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        contract = _normalize_followup_contract(row["followup_contract"], agent_type=row["agent_type"]) or {}
        contract["scheduled_message"] = {
            "content": payload.content,
            "media_url": payload.media_url,
            "media_type": payload.media_type,
            "edited_by_user": True,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        conn.execute(
            "UPDATE leads SET followup_contract = ?, lastMovement = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (json.dumps(contract, ensure_ascii=False), lead_id, current_user.id),
        )
        conn.commit()
        return {"status": "ok", "scheduled_message": contract["scheduled_message"]}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{lead_id}/followup/regenerate")
def regenerate_followup_message(lead_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    """Gera nova versão da mensagem sem sobrescrever o rascunho atual."""
    with get_connection() as conn:
        _require_lead_for_user(conn, lead_id, current_user.id)
        row = conn.execute(
            "SELECT followup_contract, agent_type, companyName, contactName FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, current_user.id),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    contract = _normalize_followup_contract(row["followup_contract"], agent_type=row["agent_type"]) or {}
    attempts = int(contract.get("attempts") or 0)
    max_attempts = int(contract.get("max_attempts") or 4)
    outcome = str(contract.get("outcome") or "warm").lower()
    goal = str(contract.get("followup_goal") or "").strip()
    operator_note = str(contract.get("operator_note") or "").strip()
    contact = str(row["contactName"] or row["companyName"] or "")
    first_name = contact.split()[0] if contact else "você"

    ai_profile: dict = {}
    try:
        ai_profile = fetch_core_ai_profile(current_user.token) or {}
    except Exception:
        pass

    brand_name = str(ai_profile.get("brand_name") or "").strip()
    tone_of_voice = str(ai_profile.get("tone_of_voice") or "amigável e profissional").strip()
    niche = str(ai_profile.get("niche") or "").strip()

    situation_map = {
        "hot": "o lead demonstrou alto interesse e está próximo de fechar",
        "warm": "o lead tem interesse moderado e está sendo acompanhado",
        "cold": "o lead está distante e precisa ser reengajado com cuidado",
        "interested_not_closed": "o lead tem interesse mas ainda não fechou",
        "reschedule_needed": "o lead precisa remarcar o horário",
        "converted": "o lead converteu e está entrando no processo de onboarding",
        "no_show": "o lead não compareceu ao último contato",
    }
    situation = situation_map.get(outcome, "o lead está em acompanhamento")

    content = _generate_followup_message_llm(
        first_name=first_name,
        brand_name=brand_name,
        niche=niche,
        tone_of_voice=tone_of_voice,
        situation=situation,
        goal=goal,
        operator_note=operator_note,
    )

    return {"content": content, "generated": True, "attempts": attempts, "max_attempts": max_attempts}


@router.post("/{lead_id}/followup/send-now")
def send_followup_now(
    lead_id: int,
    payload: SendNowPayload,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Envia a mensagem de follow-up imediatamente via job e avança a tentativa."""
    ai_profile: dict = {}
    try:
        ai_profile = fetch_core_ai_profile(current_user.token) or {}
    except Exception:
        pass

    conn = get_connection()
    try:
        _require_lead_for_user(conn, lead_id, current_user.id)
        row = conn.execute(
            "SELECT followup_contract, agent_type, phone, followup_status FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, current_user.id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        phone = row["phone"]
        if not phone:
            raise HTTPException(status_code=400, detail="Lead sem telefone cadastrado")

        if str(row["followup_status"] or "").lower() == "closed":
            raise HTTPException(status_code=409, detail="Follow-up já está encerrado")

        job_payload = json.dumps({
            "lead_id": lead_id,
            "user_id": current_user.id,
            "phone": phone,
            "body": payload.content,
            "media_url": payload.media_url,
            "media_type": payload.media_type,
            "source": "followup_send_now",
        }, ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO jobs (user_id, type, payload, status, priority, attempts,
                              assigned_agent_id, created_at, updated_at, scheduled_at)
            VALUES (?, ?, ?, 'pending', 1, 0, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (current_user.id, TYPE_WHATSAPP_SEND, job_payload),
        )
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        progress = progress_followup_after_auto_send(
            conn,
            lead_id=lead_id,
            user_id=current_user.id,
            source_job_id=job_id,
            ai_profile=ai_profile,
        )

        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, 'whatsapp', NULL, 'followup_sent_now_manual', ?, ?)
            """,
            (lead_id, json.dumps({"job_id": job_id, "progress": progress}, ensure_ascii=False), current_user.id),
        )
        conn.commit()
        return {"status": "ok", "job_id": job_id, "progress": progress}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{lead_id}/followup/upload-media")
async def upload_followup_media(
    lead_id: int,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Upload de mídia para ser enviada junto com o follow-up."""
    with get_connection() as conn:
        _require_lead_for_user(conn, lead_id, current_user.id)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_MEDIA_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensão não permitida. Use: {', '.join(sorted(_ALLOWED_MEDIA_EXTS))}",
        )

    content = await file.read()
    if len(content) > _MEDIA_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máx 100 MB)")

    uid = str(uuid.uuid4())
    filename = f"{uid}{ext}"
    dest = _FOLLOWUP_MEDIA_DIR / filename
    try:
        with open(dest, "wb") as fh:
            fh.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo: {e}")

    public_base = os.getenv("CRM_PUBLIC_BASE_URL", "").rstrip("/")
    media_url = f"{public_base}/api/followup-media/{filename}" if public_base else f"/api/followup-media/{filename}"

    return {"ok": True, "filename": filename, "original_name": file.filename, "ext": ext, "media_url": media_url}
