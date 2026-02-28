from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db import Base


class AIProfile(Base):
    __tablename__ = "ai_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_ai_profiles_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    template_key = Column(String, nullable=False)
    name = Column(String, nullable=False)
    brand_name = Column(String, nullable=False)
    tone_of_voice = Column(String, nullable=False)
    timezone = Column(String, nullable=True, server_default="UTC")
    niche = Column(String, nullable=False)
    target_audience = Column(String, nullable=False)
    offer_description = Column(String, nullable=False)
    goals = Column(String, nullable=False)
    custom_instructions = Column(String, nullable=True)
    agent_mode = Column(String, nullable=True, server_default="sdr_scheduler")
    presentation_variant = Column(String, nullable=True)
    hybrid_flow_style = Column(String, nullable=True)
    offer_pack = Column(JSON, nullable=True)
    identity_mode = Column(String, nullable=True, server_default="human_agent")
    handoff_policy = Column(String, nullable=True, server_default="keep_active_notify")
    handoff_custom_text = Column(String, nullable=True)
    requires_handoff = Column(Boolean, nullable=True, default=False)
    human_in_loop = Column(Boolean, nullable=True, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, default=datetime.utcnow
    )

    user = relationship("User", back_populates="ai_profile")
