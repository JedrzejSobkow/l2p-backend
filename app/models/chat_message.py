# app/models/chat_message.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from infrastructure.postgres_connection import Base


class ChatMessage(Base):
    """Chat message model for storing messages between friends"""
    __tablename__ = "chat_messages"
    
    id_message = Column(Integer, primary_key=True, index=True, autoincrement=True)
    friendship_id = Column(Integer, ForeignKey("friendships.id_friendship"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("registered_users.id"), nullable=False, index=True)
    content = Column(Text, nullable=True)  # Nullable for image-only messages
    image_path = Column(String(500), nullable=True)  # Path to image in MinIO
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    friendship = relationship("Friendship", back_populates="messages")
    sender = relationship("RegisteredUser")
    
    def __repr__(self):
        return f"<ChatMessage(id_message={self.id_message}, friendship_id={self.friendship_id}, sender_id={self.sender_id})>"
