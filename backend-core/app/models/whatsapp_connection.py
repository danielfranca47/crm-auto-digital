from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db import Base


class WhatsappConnection(Base):
    __tablename__ = "whatsapp_connections"
    __table_args__ = (
        UniqueConstraint("instance_id", name="uq_whatsapp_connections_instance_id"),
        Index("ix_whatsapp_connections_user_id", "user_id"),
        Index("ix_whatsapp_connections_instance_id", "instance_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False, default="uazapi")
    instance_id = Column(String, nullable=False)
    phone_e164 = Column(String, nullable=True)
    instance_token_encrypted = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="active")
    disconnect_alert_sent_at = Column(DateTime, nullable=True)
    last_disconnect_email_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        onupdate=func.now(),
        default=datetime.utcnow,
    )

    user = relationship("User", backref="whatsapp_connections")
