# app/models/user.py

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from infrastructure.postgres_connection import Base


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id_user = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nickname = Column(String(255), nullable=False, unique=True, index=True)
    
    # Relationship to RegisteredUser model (one-to-one)
    registered_user = relationship("RegisteredUser", back_populates="user", uselist=False)
    
    def __repr__(self):
        return f"<User(id_user={self.id_user}, nickname='{self.nickname}')>"
