"""
Verificação periódica de saúde das conexões WhatsApp.

Executado pelo APScheduler a cada 6 horas: para cada WhatsappConnection que o
nosso banco acha que está ativa, pergunta pra UazAPI se ela ainda está viva
de verdade e corrige o status (disparando os emails de desconexão/reconexão,
via `apply_connection_status_change`) quando detecta que a sessão morreu sem
o webhook `connection` ter avisado — ver docs/architecture/whatsapp-connection.md,
seção "Deteção de queda de sessão".

Só um 401 explícito da UazAPI (token inválido) ou uma resposta de status que
diga claramente que a sessão caiu contam como morte confirmada. Qualquer
outro erro (timeout, 5xx, 429 esgotado) é tratado como transitório: loga e
pula, tenta de novo no próximo ciclo — evita marcar uma conexão saudável como
morta por causa de uma falha pontual de rede.
"""
import asyncio
import logging
from datetime import datetime

from app.config import settings
from app.db import SessionLocal
from app import models
from app.services import uazapi_admin
from app.services import whatsapp_connections as connections_service
from app.utils.crypto import SecretEncryptionError, decrypt_secret

logger = logging.getLogger(__name__)

_INTER_REQUEST_DELAY_SECONDS = 0.3


async def _check_connection(db, connection: models.WhatsappConnection) -> str:
    """Verifica uma conexão e retorna um rótulo curto do resultado, usado só
    para o sumário do job."""
    try:
        plain_token = decrypt_secret(connection.instance_token_encrypted)
    except SecretEncryptionError as exc:
        logger.warning(
            "whatsapp_connection_check: token ilegível instance_id=%s error=%s",
            connection.instance_id,
            exc,
        )
        return "token_error"

    try:
        raw = await uazapi_admin.get_status(
            base_url=settings.UAZAPI_BASE_URL or "",
            instance_token=plain_token,
            instance_id=connection.instance_id,
        )
    except uazapi_admin.UazapiAdminError as exc:
        if exc.status_code == 401:
            connections_service.apply_connection_status_change(db, connection, "disconnected")
            logger.info(
                "whatsapp_connection_check: sessão morta detectada (401) instance_id=%s",
                connection.instance_id,
            )
            return "marked_dead"
        logger.warning(
            "whatsapp_connection_check: erro transitório instance_id=%s status=%s",
            connection.instance_id,
            exc.status_code,
        )
        return "transient_error"

    status_value, _, _ = uazapi_admin.extract_connection_meta(raw)
    if not status_value:
        logger.info(
            "whatsapp_connection_check: status não encontrado no payload instance_id=%s",
            connection.instance_id,
        )
        return "status_unknown"

    connections_service.apply_connection_status_change(db, connection, status_value)
    is_active = connections_service.normalize_connection_status_for_crm(status_value) == "active"
    return "confirmed_alive" if is_active else "confirmed_dead"


async def run_whatsapp_connection_check_async() -> dict:
    """Versão async do job — use esta diretamente quando já houver um event
    loop rodando (ex.: dentro de uma rota FastAPI `async def`, como o trigger
    manual em `app/api/cron.py`). `run_whatsapp_connection_check()` (a versão
    síncrona usada pelo APScheduler) não serve nesse caso: `asyncio.run()`
    não pode ser chamado a partir de um loop já em execução."""
    db = SessionLocal()
    summary = {"checked": 0, "marked_dead": 0, "errors": 0, "ran_at": None}
    try:
        connections = db.query(models.WhatsappConnection).all()
        active_connections = [
            c for c in connections
            if connections_service.normalize_connection_status_for_crm(c.status) == "active"
        ]
        for connection in active_connections:
            summary["checked"] += 1
            try:
                result = await _check_connection(db, connection)
                if result in ("marked_dead", "confirmed_dead"):
                    summary["marked_dead"] += 1
                elif result in ("token_error", "transient_error"):
                    summary["errors"] += 1
            except Exception as exc:
                summary["errors"] += 1
                logger.warning(
                    "whatsapp_connection_check: falha inesperada instance_id=%s error=%s",
                    connection.instance_id,
                    exc,
                )
            await asyncio.sleep(_INTER_REQUEST_DELAY_SECONDS)
    finally:
        db.close()

    summary["ran_at"] = datetime.utcnow().isoformat()
    logger.info("whatsapp_connection_check concluído: %s", summary)
    return summary


def run_whatsapp_connection_check() -> dict:
    """Entrypoint síncrono para o APScheduler (mesmo padrão de
    `run_daily_subscription_jobs`) — roda as chamadas assíncronas à UazAPI
    por dentro via `asyncio.run`. O APScheduler executa jobs em thread própria,
    sem event loop ativo, então isso é seguro aqui (ao contrário do trigger
    manual — ver `run_whatsapp_connection_check_async`)."""
    return asyncio.run(run_whatsapp_connection_check_async())
