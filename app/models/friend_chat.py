# app/models/friend_chat.py

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from infrastructure.postgres_connection import Base


class FriendChat(Base):
    """Friend chat model bound to a friendship"""
    __tablename__ = "friend_chats"
    
    id_friend_chat = Column(Integer, primary_key=True, index=True, autoincrement=True)
    friendship_id = Column(Integer, ForeignKey("friendships.id_friendship"), nullable=False, unique=True, index=True)
    
    # Relationship to Friendship model
    friendship = relationship("Friendship", back_populates="friend_chat")
    
    def __repr__(self):
        return f"<FriendChat(id_friend_chat={self.id_friend_chat}, friendship_id={self.friendship_id})>"
