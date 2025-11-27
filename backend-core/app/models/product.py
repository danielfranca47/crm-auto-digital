from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)

    plans = relationship("Plan", back_populates="product", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="product", cascade="all, delete-orphan")
    user_addons = relationship("UserAddon", back_populates="product", cascade="all, delete-orphan")
    usage_counters = relationship("UsageCounter", back_populates="product", cascade="all, delete-orphan")
