# app/models/friendship.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from infrastructure.postgres_connection import Base


class Friendship(Base):
    """Friendship model linking two registered users"""
    __tablename__ = "friendships"
    
    id_friendship = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id_1 = Column(Integer, ForeignKey("registered_users.id"), nullable=False, index=True)
    user_id_2 = Column(Integer, ForeignKey("registered_users.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships to RegisteredUser model
    user_1 = relationship("RegisteredUser", foreign_keys=[user_id_1])
    user_2 = relationship("RegisteredUser", foreign_keys=[user_id_2])
    
    def __repr__(self):
        return f"<Friendship(id_friendship={self.id_friendship}, user_1={self.user_id_1}, user_2={self.user_id_2}, status='{self.status}')>"
