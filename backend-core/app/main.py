from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.db import Base, SessionLocal, engine, ensure_ai_profile_columns, ensure_auth_otps_table, ensure_google_calendar_columns, ensure_plan_limits_columns, ensure_subscription_columns, ensure_user_columns, ensure_user_extra_columns, ensure_whatsapp_connections_table
import app.models  # noqa: F401
from app.seed import seed_initial_data

app = FastAPI(title="CRM AutoDigital Core")

_scheduler = None

origins = [
    # dev
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    # produção
    "https://danielfranca.pt",
    "https://www.danielfranca.pt",
    "https://crmapp.danielfranca.pt",
    "https://admin.danielfranca.pt",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    global _scheduler
    ensure_user_columns()
    ensure_user_extra_columns()
    ensure_google_calendar_columns()
    ensure_plan_limits_columns()
    ensure_subscription_columns()
    ensure_whatsapp_connections_table()
    ensure_ai_profile_columns()
    ensure_auth_otps_table()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.jobs.subscription_jobs import run_daily_subscription_jobs

        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(run_daily_subscription_jobs, CronTrigger(hour=12, minute=0, timezone="UTC"))  # 09:00 Brasília (UTC-3)
        _scheduler.start()
        import logging
        logging.getLogger(__name__).info("APScheduler iniciado — job diário às 12:00 UTC (09:00 Brasília)")
        # Processar pendentes de quando o servidor estava offline
        run_daily_subscription_jobs()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Falha ao iniciar APScheduler: %s", exc)


@app.on_event("shutdown")
def on_shutdown() -> None:
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


app.include_router(api_router)


@app.get("/")
async def read_root():
    return {"status": "ok"}
