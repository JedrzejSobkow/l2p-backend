# app/models/chat_message.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from infrastructure.postgres_connection import Base


class ChatMessage(Base):
    """Chat message model for storing messages in friend chats"""
    __tablename__ = "chat_messages"
    
    id_message = Column(Integer, primary_key=True, index=True, autoincrement=True)
    friend_chat_id = Column(Integer, ForeignKey("friend_chats.id_friend_chat"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("registered_users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    friend_chat = relationship("FriendChat", back_populates="messages")
    sender = relationship("RegisteredUser")
    
    def __repr__(self):
        return f"<ChatMessage(id_message={self.id_message}, friend_chat_id={self.friend_chat_id}, sender_id={self.sender_id})>"
