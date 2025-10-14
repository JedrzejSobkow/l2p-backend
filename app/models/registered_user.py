# app/models/registered_user.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from infrastructure.postgres_connection import Base


class RegisteredUser(Base):
    """Registered User model with authentication details"""
    __tablename__ = "registered_users"
    
    user_id = Column(Integer, ForeignKey("users.id_user"), primary_key=True, index=True)
    login = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    pfp_path = Column(String(500), nullable=True)
    description = Column(String(1000), nullable=True)
    
    # Relationship to User model
    user = relationship("User", back_populates="registered_user")
    
    def __repr__(self):
        return f"<RegisteredUser(user_id={self.user_id}, login='{self.login}', email='{self.email}', is_active={self.is_active})>"
