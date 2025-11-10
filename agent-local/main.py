"""Ponto de entrada do agente local."""
from __future__ import annotations
import logging
import signal
import sys
import time
from pathlib import Path

import requests

from agent.config import settings
from agent.jobs_client import JobsClient, client
from agent.whatsapp_runner import runner

LOG_PATH = Path(__file__).with_name("agent.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger("agent.main")


shutdown_flag = False


def handle_signal(signum, frame):  # type: ignore[override]
    global shutdown_flag
    logger.info("Sinal %s recebido. Encerrando loop...", signum)
    shutdown_flag = True


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def process_job(job: dict, jobs_client: JobsClient) -> None:
    job_id = job.get("id")
    job_type = job.get("type")
    payload = job.get("payload") or {}

    logger.info("Processando job %s (%s)", job_id, job_type)

    try:
        if job_type == "whatsapp_send":
            result = runner.send_message(payload)
            jobs_client.report(job_id, "completed", result=result)
        else:
            error_msg = f"Tipo de job não suportado: {job_type}"
            logger.error(error_msg)
            jobs_client.report(job_id, "failed", result={"error": error_msg}, error=error_msg)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Erro executando job %s", job_id)
        jobs_client.report(
            job_id,
            "failed",
            result={"error": str(exc)},
            error=str(exc),
        )


def main() -> None:
    logger.info("Iniciando agente local com backend %s", settings.backend_url)
    jobs_client = client

    # Registro inicial
    retry_delay = 5
    while True:
        try:
            jobs_client.register()
            break
        except requests.RequestException as exc:
            logger.warning("Falha ao registrar agente: %s", exc)
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

    poll_delay = settings.poll_interval
    backoff = poll_delay

    while not shutdown_flag:
        try:
            job = jobs_client.next_job(settings.accepted_job_types)
            if not job:
                logger.debug("Sem jobs no momento. Aguardando %ss", poll_delay)
                time.sleep(poll_delay)
                backoff = poll_delay
                continue

            process_job(job, jobs_client)
            backoff = poll_delay
        except requests.RequestException as exc:
            logger.warning("Erro de comunicação com backend: %s", exc)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erro inesperado no loop principal: %s", exc)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

    logger.info("Agente finalizado. Fechando recursos...")
    runner.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário.")
        runner.close()
