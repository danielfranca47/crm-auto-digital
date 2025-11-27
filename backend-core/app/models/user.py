from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, func

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)
