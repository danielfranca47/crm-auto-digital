from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db import Base


class PlanLimits(Base):
    __tablename__ = "plan_limits"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False, unique=True, index=True)
    max_leads = Column(Integer, nullable=True)
    max_agents_local = Column(Integer, nullable=True)
    max_pesquisa_selenium_daily = Column(Integer, nullable=True)
    max_pesquisa_turbo_monthly = Column(Integer, nullable=True)
    max_prospec_monthly = Column(Integer, nullable=True)
    max_copy_generation_monthly = Column(Integer, nullable=True)
    max_ia_conversas_monthly = Column(Integer, nullable=True)
    require_agent_local_activation_fee = Column(Boolean, default=False, nullable=False)
    ia_memory_advanced = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)

    plan = relationship("Plan", back_populates="limits")

    def as_dict(self) -> dict:
        return {
            "max_leads": self.max_leads,
            "max_agents_local": self.max_agents_local,
            "max_pesquisa_selenium_daily": self.max_pesquisa_selenium_daily,
            "max_pesquisa_turbo_monthly": self.max_pesquisa_turbo_monthly,
            "max_prospec_monthly": self.max_prospec_monthly,
            "max_copy_generation_monthly": self.max_copy_generation_monthly,
            "max_ia_conversas_monthly": self.max_ia_conversas_monthly,
            "require_agent_local_activation_fee": self.require_agent_local_activation_fee,
            "ia_memory_advanced": self.ia_memory_advanced,
        }
