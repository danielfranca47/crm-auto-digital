# backend/app.py
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# ✅ Carrega .env do backend (e .env.local, se existir)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routes import (
    leads,
    search,
    assistente_ia,
    uploads,
    prospeccao,
    profile,
    dashboard,
    appointments,
    agents,
    usage,
    knowledge,
    qualification,
    webhooks,
    executor,
    whatsapp_connect,
    notifications,
    playground,
    spy_agent,
    checkout,
)
from routes import public
from routes import admin_agents
from routes import admin_billing
from routes import knowledge_ingest
from services.followup_reconciler import (
    reconcile_due_followups,
    scan_inactive_clients_for_checkin,
    scan_inactive_leads_for_auto_followup,
)
from services.spy_agent.observation_reconciler import reconcile_expired_observations
from services.spy_agent.spy_media_worker import process_pending_spy_media_jobs
from services.knowledge_ingest.ingest_worker import process_pending_knowledge_ingest_jobs

logger = logging.getLogger(__name__)

_RECONCILER_INTERVAL = int(os.getenv("FOLLOWUP_RECONCILER_INTERVAL_SECONDS", "60"))
_RECONCILER_STARTUP_DELAY = 5  # segundos de grace period antes da 1ª execução
_SPY_RECONCILER_INTERVAL = int(os.getenv("SPY_AGENT_RECONCILER_INTERVAL_SECONDS", "60"))
_SPY_MEDIA_WORKER_INTERVAL = int(os.getenv("SPY_MEDIA_WORKER_INTERVAL_SECONDS", "30"))
_KNOWLEDGE_INGEST_WORKER_INTERVAL = int(os.getenv("KNOWLEDGE_INGEST_WORKER_INTERVAL_SECONDS", "10"))


async def _reconciler_loop() -> None:
    logger.info(
        "[reconciler] scheduler iniciado — intervalo=%ds startup_delay=%ds",
        _RECONCILER_INTERVAL,
        _RECONCILER_STARTUP_DELAY,
    )
    await asyncio.sleep(_RECONCILER_STARTUP_DELAY)
    while True:
        try:
            result = await asyncio.to_thread(reconcile_due_followups)
            if result["eligible"] > 0 or result["enqueued"] > 0:
                logger.info(
                    "[reconciler] scanned=%d eligible=%d enqueued=%d skipped_duplicate=%d skipped_circuit_breaker=%d",
                    result["scanned"],
                    result["eligible"],
                    result["enqueued"],
                    result["skipped_duplicate"],
                    result.get("skipped_circuit_breaker", 0),
                )
            else:
                logger.debug("[reconciler] nenhum follow-up vencido — scanned=%d", result["scanned"])

            auto_result = await asyncio.to_thread(scan_inactive_leads_for_auto_followup)
            if auto_result["started"] > 0:
                logger.info(
                    "[reconciler] auto_inactivity scanned=%d started=%d",
                    auto_result["scanned"],
                    auto_result["started"],
                )

            checkin_result = await asyncio.to_thread(scan_inactive_clients_for_checkin)
            if checkin_result["started"] > 0:
                logger.info(
                    "[reconciler] client_checkin scanned=%d started=%d",
                    checkin_result["scanned"],
                    checkin_result["started"],
                )
        except Exception as exc:
            logger.error("[reconciler] erro inesperado: %s", exc, exc_info=True)
        await asyncio.sleep(_RECONCILER_INTERVAL)


async def _spy_reconciler_loop() -> None:
    logger.info("[spy_reconciler] scheduler iniciado — intervalo=%ds", _SPY_RECONCILER_INTERVAL)
    await asyncio.sleep(_RECONCILER_STARTUP_DELAY + 2)  # stagger levemente
    while True:
        try:
            result = await asyncio.to_thread(reconcile_expired_observations)
            if result["triggered"] > 0:
                logger.info(
                    "[spy_reconciler] scanned=%d triggered=%d",
                    result["scanned"],
                    result["triggered"],
                )
        except Exception as exc:
            logger.error("[spy_reconciler] erro inesperado: %s", exc, exc_info=True)
        await asyncio.sleep(_SPY_RECONCILER_INTERVAL)


async def _spy_media_worker_loop() -> None:
    """Processa jobs spy.media.process (áudio → Whisper, imagem → Vision) internamente."""
    logger.info("[spy_media_worker] scheduler iniciado — intervalo=%ds", _SPY_MEDIA_WORKER_INTERVAL)
    await asyncio.sleep(_RECONCILER_STARTUP_DELAY + 4)  # stagger após os outros
    while True:
        try:
            result = await asyncio.to_thread(process_pending_spy_media_jobs)
            if result["processed"] > 0 or result["failed"] > 0:
                logger.info(
                    "[spy_media_worker] processed=%d failed=%d",
                    result["processed"],
                    result["failed"],
                )
        except Exception as exc:
            logger.error("[spy_media_worker] erro inesperado: %s", exc, exc_info=True)
        await asyncio.sleep(_SPY_MEDIA_WORKER_INTERVAL)


async def _knowledge_ingest_worker_loop() -> None:
    """Processa jobs knowledge.ingest.internal (extração de fontes da base de conhecimento)."""
    logger.info(
        "[knowledge_ingest_worker] scheduler iniciado — intervalo=%ds",
        _KNOWLEDGE_INGEST_WORKER_INTERVAL,
    )
    await asyncio.sleep(_RECONCILER_STARTUP_DELAY + 6)  # stagger após os outros
    while True:
        try:
            result = await asyncio.to_thread(process_pending_knowledge_ingest_jobs)
            if result["processed"] > 0 or result["failed"] > 0:
                logger.info(
                    "[knowledge_ingest_worker] processed=%d failed=%d",
                    result["processed"],
                    result["failed"],
                )
        except Exception as exc:
            logger.error("[knowledge_ingest_worker] erro inesperado: %s", exc, exc_info=True)
        await asyncio.sleep(_KNOWLEDGE_INGEST_WORKER_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_reconciler_loop())
    spy_task = asyncio.create_task(_spy_reconciler_loop())
    spy_media_task = asyncio.create_task(_spy_media_worker_loop())
    knowledge_ingest_task = asyncio.create_task(_knowledge_ingest_worker_loop())
    try:
        yield
    finally:
        for t in (task, spy_task, spy_media_task, knowledge_ingest_task):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        logger.info("[reconciler] schedulers encerrados")


def _parse_origins(csv: str | None) -> list[str]:
    """Converte 'a,b,c/' -> ['a','b','c'] (sem barras finais, sem vazios)."""
    if not csv:
        return []
    return [o.strip().rstrip("/") for o in csv.split(",") if o.strip()]


# -----------------------------------------------------------------------------
# APP PRIVADO (CRM)  -> /api, /auth, etc.
# -----------------------------------------------------------------------------
app = FastAPI(title="CRM API", version="1.0.0", lifespan=lifespan)

# Inicializa DB
init_db()

# ---------- CORS (Privado) 100% via .env ----------
# Lê listas do .env
private_origins = _parse_origins(os.getenv("PRIVATE_ORIGINS"))
public_origins_for_parent = _parse_origins(os.getenv("PUBLIC_ORIGINS"))

# União (privado ∪ público) sem duplicatas — evita bloquear preflight de /public no app-pai
parent_allow_origins = list(dict.fromkeys(private_origins + public_origins_for_parent))

allow_credentials_private = os.getenv("CORS_ALLOW_CREDENTIALS_PRIVATE", "true").lower() == "true"

print("[PRIVATE CORS]", parent_allow_origins, "allow_credentials=", allow_credentials_private)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parent_allow_origins,
    allow_credentials=allow_credentials_private,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------- Routers Privados ----------
app.include_router(leads.router,         prefix="/api/leads",        tags=["Leads"])
app.include_router(search.router,        prefix="/api/pesquisa",     tags=["Pesquisa"])
app.include_router(assistente_ia.router, prefix="/api/assistente-ia",tags=["Assistente IA"])
app.include_router(uploads.router,       prefix="/api",              tags=["Uploads"])
app.include_router(prospeccao.router)                               # já define prefix="/api/prospeccao"
app.include_router(profile.router)                                  # prefixo definido no arquivo
app.include_router(appointments.router)                             # já define prefix="/api/appointments"
app.include_router(agents.router)                                   # /api/agents
app.include_router(usage.router)                                    # /api/usage
app.include_router(knowledge_ingest.router)                         # /api/knowledge/ingest (antes de knowledge p/ evitar sombra de rota)
app.include_router(knowledge.router)                                # /api/knowledge
app.include_router(qualification.router)                            # /api/qualification
app.include_router(webhooks.router)                                 # /webhooks/whatsapp/inbound
app.include_router(executor.router)                                 # /api/jobs, /api/whatsapp/* internal
app.include_router(whatsapp_connect.router)                         # /api/whatsapp/connect, /api/whatsapp/status
app.include_router(notifications.router)                            # /api/notifications
app.include_router(playground.router)                               # /api/playground
app.include_router(spy_agent.router)                                # /api/spy-agent
app.include_router(checkout.router)                                 # /checkout/efi/{offer_key}
app.include_router(admin_agents.router)                             # /admin/agents/*
app.include_router(admin_billing.router)                            # /admin/billing/*
# app.include_router(dashboard.router)

# Static: mídia de follow-up
_followup_media_dir = Path("data/uploads/followup-media")
_followup_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/followup-media", StaticFiles(directory=str(_followup_media_dir)), name="followup-media")

# Static: mídia de knowledge (imagens/PDFs enviados ao lead)
_knowledge_media_dir = Path("data/uploads/knowledge/media")
_knowledge_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/knowledge-media", StaticFiles(directory=str(_knowledge_media_dir)), name="knowledge-media")

# -----------------------------------------------------------------------------
# SUB-APP PÚBLICO (Website / Form) -> montado em /public
# -----------------------------------------------------------------------------
public_app = FastAPI(title="Public API", version="1.0.0")

public_origins = _parse_origins(os.getenv("PUBLIC_ORIGINS"))
allow_credentials_public = os.getenv("CORS_ALLOW_CREDENTIALS_PUBLIC", "false").lower() == "true"

# Suporte a wildcard: PUBLIC_ORIGINS=*  (apenas com credentials False)
allow_all_public = (len(public_origins) == 1 and public_origins[0] == "*")
if allow_all_public and allow_credentials_public:
    allow_credentials_public = False  # segurança

print("[PUBLIC CORS]", public_origins if not allow_all_public else ["*"], "allow_credentials=", allow_credentials_public)

public_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_public else public_origins,
    allow_credentials=allow_credentials_public,  # manter False para formulário público
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],  # inclui x-form-token
)

# Router público sem prefixo; montado em /public vira /public/leads etc.
public_app.include_router(public.router, tags=["Public"])

# Monta o sub-app público
app.mount("/public", public_app)

# -----------------------------------------------------------------------------
# Lifecycle / Raiz
# -----------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "API CRM rodando 🎯"}
