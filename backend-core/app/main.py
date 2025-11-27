from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.db import Base, engine, SessionLocal
import app.models  # noqa: F401
from app.seed import seed_initial_data

app = FastAPI(title="CRM AutoDigital Core")

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
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
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()


app.include_router(api_router)


@app.get("/")
async def read_root():
    return {"status": "ok"}
