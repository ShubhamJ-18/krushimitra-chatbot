import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), default="New Conversation")
    language = Column(String(32), default="English")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)  # JSON-encoded citations
    intent = Column(String(64), nullable=True)  # e.g., 'crop_doctor', 'fertilizer', 'weather'
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")

class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), default="Farmer")
    district = Column(String(100), default="Pune")
    state = Column(String(100), default="Maharashtra")
    farm_size_acres = Column(String(50), default="3-5")
    primary_crops = Column(String(255), default="Soybean, Cotton, Onion")
    irrigation_type = Column(String(100), default="Drip / Well")
    preferred_language = Column(String(32), default="Marathi")
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), nullable=True)
    message_id = Column(String(36), nullable=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
