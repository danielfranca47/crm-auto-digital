"""Capacidade de instâncias na UazAPI.

O plano UazAPI tem dois tetos: instâncias conectadas ao mesmo tempo e
instâncias *registadas* no total (mesmo desconectadas). Instâncias mortas que
ninguém apaga ocupam vaga para sempre; com o teto cheio, `/instance/init`
devolve 429 e nenhum cliente consegue conectar. Este módulo reconcilia o que
existe de facto na UazAPI (`GET /instance/all`) com `whatsapp_connections` e
liberta vagas — ver docs/architecture/whatsapp-connection.md, seção
"Capacidade de instâncias na UazAPI".

- órfã: existe na UazAPI, não existe no nosso banco, status `disconnected`.
- morta: existe nos dois, `disconnected` na UazAPI e inativa no banco.

Nunca apaga instâncias `connected`/`connecting` (ex.: cliente a ler um QR).

Só corre em produção (Railway) por omissão — ver `cleanup_enabled()`.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.services import uazapi_admin
from app.services import whatsapp_connections as connections_service

logger = logging.getLogger(__name__)

# Órfã recém-criada pode ser só uma instância cujo upsert local ainda não
# gravou (entre o /instance/init e o commit) — nunca mexer nelas.
ORPHAN_MIN_AGE = timedelta(minutes=10)

_DELETABLE_UAZAPI_STATUSES = {"disconnected"}


def cleanup_enabled() -> bool:
    """Apagar instâncias só é seguro onde o banco é o de produção. Um
    backend-core local costuma apontar para a mesma UazAPI de produção com um
    banco SQLite local que não conhece os clientes reais — ali, todas as
    instâncias de produção pareceriam órfãs. Por omissão liga só no Railway
    (`RAILWAY_ENVIRONMENT`, injetada pelo Railway); `UAZAPI_INSTANCE_CLEANUP_ENABLED`
    (true/false) força explicitamente."""
    explicit = os.getenv("UAZAPI_INSTANCE_CLEANUP_ENABLED")
    if explicit is not None and explicit.strip():
        return explicit.strip().lower() in {"1", "true", "yes"}
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT_NAME"))


@dataclass
class InstanceCandidate:
    name: str
    token: str
    kind: str  # "orphan" | "dead"
    created_at: Optional[datetime]
    sort_key: datetime


def _parse_uazapi_datetime(value: Any) -> Optional[datetime]:
    """"2026-09-28 22:41:40.582Z" → datetime UTC naive (mesmo padrão do banco)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("T", " ").rstrip("Z").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def classify_instances(
    db: Session,
    listing: list[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> tuple[list[InstanceCandidate], list[InstanceCandidate], list[InstanceCandidate]]:
    """Separa a listagem da UazAPI em (órfãs apagáveis, órfãs recentes demais,
    mortas com registo local). Tudo o resto (vivas, a conectar, sem token) fica
    de fora. Órfãs ordenadas da mais antiga; mortas pela queda mais antiga."""
    now = now or datetime.utcnow()
    orphans: list[InstanceCandidate] = []
    young_orphans: list[InstanceCandidate] = []
    dead: list[InstanceCandidate] = []

    for item in listing:
        name = item.get("name")
        token = item.get("token")
        status = str(item.get("status") or "").strip().lower()
        if not isinstance(name, str) or not name or not isinstance(token, str) or not token:
            continue
        if status not in _DELETABLE_UAZAPI_STATUSES:
            continue

        created_at = _parse_uazapi_datetime(item.get("created"))
        connection = connections_service.get_connection_by_instance(db, name)

        if connection is None:
            candidate = InstanceCandidate(
                name=name,
                token=token,
                kind="orphan",
                created_at=created_at,
                sort_key=created_at or datetime.min,
            )
            if created_at is None or now - created_at < ORPHAN_MIN_AGE:
                young_orphans.append(candidate)
            else:
                orphans.append(candidate)
            continue

        if connections_service.normalize_connection_status_for_crm(connection.status) == "active":
            # Banco acha que está viva e a UazAPI diz o contrário — isso é
            # trabalho do job de 6h / webhook, não desta limpeza.
            continue

        last_disconnect = _parse_uazapi_datetime(item.get("lastDisconnect"))
        dead.append(
            InstanceCandidate(
                name=name,
                token=token,
                kind="dead",
                created_at=created_at,
                sort_key=last_disconnect or connection.updated_at or created_at or datetime.min,
            )
        )

    orphans.sort(key=lambda c: c.sort_key)
    dead.sort(key=lambda c: c.sort_key)
    return orphans, young_orphans, dead


async def _delete_candidate(db: Session, candidate: InstanceCandidate, *, reason: str) -> bool:
    try:
        await uazapi_admin.delete_instance(
            base_url=settings.UAZAPI_BASE_URL or "",
            instance_token=candidate.token,
            instance_id=candidate.name,
        )
    except uazapi_admin.UazapiAdminError as exc:
        if exc.status_code != 404:
            logger.warning(
                "event=uazapi_instance_delete_failed instance_id=%s kind=%s reason=%s status=%s",
                candidate.name,
                candidate.kind,
                reason,
                exc.status_code,
            )
            return False
    if candidate.kind == "dead":
        connections_service.delete_connection_by_instance(db, candidate.name)
    logger.info(
        "event=uazapi_instance_deleted instance_id=%s kind=%s reason=%s",
        candidate.name,
        candidate.kind,
        reason,
    )
    return True


async def _list_instances() -> list[Dict[str, Any]]:
    return await uazapi_admin.list_instances(
        base_url=settings.UAZAPI_BASE_URL or "",
        admin_token=settings.UAZAPI_ADMIN_TOKEN or "",
    )


async def reclaim_instance_slots(db: Session, needed: int = 1) -> list[str]:
    """Liberta até `needed` vagas quando o teto foi atingido: órfãs primeiro
    (mais antigas), depois instâncias mortas de clientes (queda mais antiga).
    Ao apagar uma morta, a linha local também sai — o próximo "Reconectar QR"
    desse cliente cria uma instância nova pelo fluxo normal. Devolve os nomes
    apagados (vazio = nada a libertar)."""
    if not cleanup_enabled():
        logger.warning("event=uazapi_reclaim_skipped reason=cleanup_disabled")
        return []
    listing = await _list_instances()
    orphans, young_orphans, dead = classify_instances(db, listing)
    deleted: list[str] = []
    for candidate in [*orphans, *dead]:
        if len(deleted) >= needed:
            break
        if await _delete_candidate(db, candidate, reason="instance_limit"):
            deleted.append(candidate.name)
    logger.info(
        "event=uazapi_reclaim total=%s orphans=%s young_orphans=%s dead=%s deleted=%s",
        len(listing),
        len(orphans),
        len(young_orphans),
        len(dead),
        deleted,
    )
    return deleted


async def cleanup_orphans(db: Session) -> Dict[str, Any]:
    """Limpeza preventiva: apaga só órfãs (sem registo local, desconectadas,
    com mais de ORPHAN_MIN_AGE). Instâncias de clientes nunca são apagadas
    aqui — só por demanda, em `reclaim_instance_slots`."""
    if not cleanup_enabled():
        logger.info("event=uazapi_capacity skipped=cleanup_disabled")
        return {"skipped": "cleanup_disabled", "ran_at": datetime.utcnow().isoformat()}
    listing = await _list_instances()
    orphans, young_orphans, dead = classify_instances(db, listing)
    deleted = [c.name for c in orphans if await _delete_candidate(db, c, reason="daily_cleanup")]
    summary = {
        "total_before": len(listing),
        "deleted_orphans": deleted,
        "young_orphans_skipped": len(young_orphans),
        "dead_with_record": len(dead),
        "total_after": len(listing) - len(deleted),
        "ran_at": datetime.utcnow().isoformat(),
    }
    logger.info("event=uazapi_capacity %s", summary)
    return summary
