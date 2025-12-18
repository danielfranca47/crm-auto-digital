"""Ponto de entrada do agente local."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Dict

from agent.config import AgentConfig
from agent.jobs_client import JobsClient
from agent.maps_research_runner import MapsResearchRunner
from agent.whatsapp_runner import WhatsAppRunner

AGENT_VERSION = "0.1.0"

TYPE_ALIASES = {
    "whatsapp.send.local": ["whatsapp_send"],
    "maps.search.local": ["maps_search_fallback"],
    "maps.enrich.local": ["maps_enrich_fallback"],
}


def normalize_job_type(job_type: str) -> str:
    jt = (job_type or "").strip()
    for canonical, aliases in TYPE_ALIASES.items():
        if jt == canonical or jt in aliases:
            return canonical
    return jt


def setup_logging(config: AgentConfig) -> None:
    log_path = config.log_path
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handlers.append(file_handler)
    except OSError:
        print(f"Não foi possível abrir o arquivo de log em {log_path}, seguindo apenas com stdout.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def process_job(
    job: Dict[str, Any], whatsapp_runner: WhatsAppRunner, maps_runner: MapsResearchRunner
) -> Dict[str, Any]:
    job_type = normalize_job_type(job.get("type"))
    payload = job.get("payload") or {}

    if job_type == "whatsapp.send.local":
        phone = payload.get("phone")
        message = payload.get("body")
        if not phone or not message:
            raise ValueError("payload de whatsapp_send inválido: phone/body ausentes")
        return whatsapp_runner.send_whatsapp(phone=phone, message=message)

    if job_type == "maps.search.local":
        return maps_runner.run_search_fallback(payload)

    if job_type == "maps.enrich.local":
        return maps_runner.run_enrich_fallback(payload)

    raise ValueError(f"Tipo de job não suportado: {job_type}")


def main() -> None:
    config = AgentConfig.load()
    job_types = [normalize_job_type(t) for t in (config.job_types or [])]
    setup_logging(config)

    logger = logging.getLogger("agent")
    logger.info("Iniciando agente local — backend=%s", config.backend_url)

    client = JobsClient(config)
    whatsapp_runner = WhatsAppRunner(config)
    maps_runner = MapsResearchRunner(config)

    try:
        client.register_agent(capabilities=job_types, version=AGENT_VERSION)
        logger.info("Agente registrado com ID '%s'", config.agent_id)
    except Exception as exc:
        logger.error("Falha ao registrar agente: %s", exc, exc_info=True)
        time.sleep(config.idle_interval)

    consecutive_errors = 0

    while True:
        try:
            job = client.fetch_next_job(job_types)
            if not job:
                time.sleep(config.idle_interval)
                consecutive_errors = 0
                continue

            job_id = job.get("id")
            logger.info("Job recebido: id=%s tipo=%s", job_id, job.get("type"))
            try:
                result = process_job(job, whatsapp_runner, maps_runner)
                client.report_job(job_id=job_id, status="completed", result=result)
                logger.info("Job %s concluído com sucesso", job_id)
                consecutive_errors = 0
            except Exception as job_exc:  # pragma: no cover - fluxo operacional
                logger.exception("Erro ao processar job %s: %s", job_id, job_exc)
                client.report_job(
                    job_id=job_id,
                    status="failed",
                    error=str(job_exc),
                )
                consecutive_errors += 1
                time.sleep(min(30, config.poll_interval * (1 + consecutive_errors)))
        except KeyboardInterrupt:
            logger.info("Encerrando agente...")
            break
        except Exception as loop_exc:  # pragma: no cover - fluxo operacional
            consecutive_errors += 1
            logger.exception("Erro na comunicação com o backend: %s", loop_exc)
            sleep_time = min(60, config.idle_interval * (1 + consecutive_errors))
            time.sleep(sleep_time)

    whatsapp_runner.close()
    maps_runner.close()


if __name__ == "__main__":
    main()
