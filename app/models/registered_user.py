# app/models/registered_user.py

from sqlalchemy import Column, Integer, String, Boolean
from infrastructure.postgres_connection import Base


class RegisteredUser(Base):
    """Registered User model with authentication details"""
    __tablename__ = "registered_users"
    
    id_user = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nickname = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    pfp_path = Column(String(500), nullable=True)
    description = Column(String(1000), nullable=True)
    
    def __repr__(self):
        return f"<RegisteredUser(id_user={self.id_user}, nickname='{self.nickname}', email='{self.email}', is_active={self.is_active})>"
