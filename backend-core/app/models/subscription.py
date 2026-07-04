from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False, index=True)
    status = Column(String, default="active", nullable=False)
    current_period_start = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)
    current_period_end = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    expiry_warning_sent = Column(Boolean, default=False, nullable=False)
    expiry_warning_stage = Column(Integer, nullable=True)
    origin_offer = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")
    product = relationship("Product", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
