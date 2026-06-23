import os
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
    language = Column(String, nullable=True, server_default="pt-BR")
    niche = Column(String, nullable=False)
    target_audience = Column(String, nullable=False)
    offer_description = Column(String, nullable=False)
    goals = Column(String, nullable=False)
    custom_instructions = Column(String, nullable=True)
    agent_mode = Column(String, nullable=True, server_default="sdr_scheduler")
    presentation_variant = Column(String, nullable=True)
    hybrid_flow_style = Column(String, nullable=True)
    response_style = Column(String, nullable=True, server_default="active")
    offer_pack = Column(JSON, nullable=True)
    identity_mode = Column(String, nullable=True, server_default="human_agent")
    handoff_policy = Column(String, nullable=True, server_default="keep_active_notify")
    handoff_custom_text = Column(String, nullable=True)
    requires_handoff = Column(Boolean, nullable=True, default=False)
    human_in_loop = Column(Boolean, nullable=True, default=False)
    followup_cadence = Column(JSON, nullable=True)
    followup_max_attempts = Column(Integer, nullable=True)
    followup_first_offset = Column(Integer, nullable=True)
    followup_allowed_hours = Column(String, nullable=True)
    followup_auto_trigger_enabled = Column(Boolean, nullable=True, default=False)
    followup_auto_trigger_inactivity_days = Column(Integer, nullable=True, server_default="3")
    followup_checkin_auto_trigger_enabled = Column(Boolean, nullable=True, default=False)
    followup_checkin_inactivity_days = Column(Integer, nullable=True, server_default="30")
    origin_inbound_opener = Column(String, nullable=True)
    origin_outbound_opener = Column(String, nullable=True)
    followup_sdr_instructions = Column(String, nullable=True)
    followup_recovery_instructions = Column(String, nullable=True)
    followup_postsession_instructions = Column(String, nullable=True)
    followup_checkin_instructions = Column(String, nullable=True)
    followup_goal_instructions = Column(JSON, nullable=True)
    cart_recovery_attempt_instructions = Column(JSON, nullable=True)
    followup_outcome_instructions = Column(JSON, nullable=True)
    objection_common = Column(String, nullable=True)
    qualification_score_threshold = Column(Integer, nullable=True, server_default="6")
    nurture_vs_discard_rule = Column(String, nullable=True, server_default="discard")
    appointment_reminder_offsets = Column(JSON, nullable=True)
    briefing_enabled = Column(Boolean, nullable=True, default=True)
    briefing_channel = Column(String, nullable=True, server_default="whatsapp")
    briefing_lead_time = Column(Integer, nullable=True, server_default="120")
    operator_whatsapp = Column(String, nullable=True)
    payment_gateway = Column(String, nullable=True)
    payment_webhook_secret = Column(String, nullable=True)
    buying_signal_keywords = Column(JSON, nullable=True)
    qualification_required_fields = Column(JSON, nullable=True)
    qualification_fields = Column(JSON, nullable=True)
    calendar_integration = Column(String, nullable=True, server_default="none")
    warming_social_proof = Column(String, nullable=True)
    warming_session_preview = Column(String, nullable=True)
    appointment_mode = Column(String, nullable=True, server_default="exploratory")
    scheduling_offer_style = Column(String, nullable=True, server_default="offer_alternatives")
    meeting_management_enabled = Column(Boolean, nullable=True, default=True)
    availability_schedule = Column(String, nullable=True)
    availability_mode = Column(String, nullable=True, server_default="24h")
    first_reply_delay_min_seconds = Column(Integer, nullable=True, server_default="0")
    first_reply_delay_max_seconds = Column(Integer, nullable=True, server_default="0")
    reply_delay_min_seconds = Column(Integer, nullable=True, server_default="0")
    reply_delay_max_seconds = Column(Integer, nullable=True, server_default="0")
    multi_message_buffer_seconds = Column(Integer, nullable=True, server_default="8")
    custom_variables = Column(JSON, nullable=True)
    enabled_extensions = Column(JSON, nullable=True)
    audio_transcription_enabled = Column(Boolean, default=False, nullable=False, server_default="0")
    sales_flow = Column(JSON, nullable=True)
    generated_prompt_parts = Column(JSON, nullable=True)
    prompt_parts_generated_at = Column(DateTime, nullable=True)
    prompt_parts_version = Column(Integer, nullable=True, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, default=datetime.utcnow
    )

    user = relationship("User", back_populates="ai_profile")

    @property
    def payment_webhook_url(self) -> str | None:
        if not self.payment_gateway or not self.payment_webhook_secret:
            return None
        base = os.getenv("CRM_PUBLIC_BASE_URL", "").rstrip("/")
        return f"{base}/webhooks/payment/{self.payment_gateway}?token={self.payment_webhook_secret}"
