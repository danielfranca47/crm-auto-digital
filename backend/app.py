# backend/app.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import init_db
from routes import (
    leads,
    search,
    assistente_ia,
    uploads,
    prospeccao,
    whatsapp,
    profile,
    dashboard,
    appointments,
)
from routes import public  # noqa: E402
from automations.whatsapp.qr_manager import qr_manager  # para fechar o driver no shutdown

app = FastAPI(title="CRM API", version="1.0.0")

# Carrega env antes de tocar no DB
load_dotenv()
init_db()

# ---------- CORS ----------
# Configure em .env: FRONTEND_ORIGINS="http://localhost:5173,https://seu-front.app"
origins_env = os.getenv(
    "FRONTEND_ORIGINS",
    "https://danielfranca.pt,http://localhost:5175",
)
allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

origins = [o.strip() for o in origins_env.split(",") if o.strip()]
# Se credentials=True, evite '*' por exigência do navegador
if allow_credentials_env and origins == ["*"]:
    # fallback seguro: não usar wildcard quando credenciais são necessárias
    allow_credentials_env = False  # ou defina FRONTEND_ORIGINS explicitamente

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials_env,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Routers ----------
# Atenção: alguns routers já têm prefixo no próprio arquivo.
app.include_router(leads.router, prefix="/api/leads", tags=["Leads"])
app.include_router(search.router, prefix="/api/pesquisa", tags=["Pesquisa"])
app.include_router(assistente_ia.router, prefix="/api/assistente-ia", tags=["Assistente IA"])
app.include_router(uploads.router, prefix="/api", tags=["Uploads"])
app.include_router(prospeccao.router)   # já define prefix="/api/prospeccao"
app.include_router(whatsapp.router)     # já define prefix="/api/whatsapp"
app.include_router(profile.router)      # use o prefixo definido no arquivo
app.include_router(appointments.router) # já define prefix="/api/appointments"
app.include_router(public.router)       # prefix="/public"

# Se o dashboard tiver prefixo próprio no arquivo, você pode habilitar:
# app.include_router(dashboard.router)

# ---------- Lifecycle ----------
@app.on_event("shutdown")
def _on_shutdown():
    # Fecha a sessão do Chrome/Selenium de forma graciosa
    try:
        qr_manager.stop()
    except Exception:
        pass

@app.get("/")
def root():
    return {"status": "API CRM rodando 🎯"}
