# backend/app.py
import os
from pathlib import Path
from dotenv import load_dotenv

# ✅ Carrega .env do backend (e .env.local, se existir)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from auth_mvp import router as auth_router
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
)
from routes import public


def _parse_origins(csv: str | None) -> list[str]:
    """Converte 'a,b,c/' -> ['a','b','c'] (sem barras finais, sem vazios)."""
    if not csv:
        return []
    return [o.strip().rstrip("/") for o in csv.split(",") if o.strip()]


# -----------------------------------------------------------------------------
# APP PRIVADO (CRM)  -> /api, /auth, etc.
# -----------------------------------------------------------------------------
app = FastAPI(title="CRM API", version="1.0.0")

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
app.include_router(auth_router)                                   # /auth/*
app.include_router(leads.router,         prefix="/api/leads",        tags=["Leads"])
app.include_router(search.router,        prefix="/api/pesquisa",     tags=["Pesquisa"])
app.include_router(assistente_ia.router, prefix="/api/assistente-ia",tags=["Assistente IA"])
app.include_router(uploads.router,       prefix="/api",              tags=["Uploads"])
app.include_router(prospeccao.router)                               # já define prefix="/api/prospeccao"
app.include_router(profile.router)                                  # prefixo definido no arquivo
app.include_router(appointments.router)                             # já define prefix="/api/appointments"
app.include_router(agents.router)                                   # /api/agents
# app.include_router(dashboard.router)

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
