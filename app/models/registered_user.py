# app/models/registered_user.py

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from infrastructure.postgres_connection import Base


class RegisteredUser(Base, SQLAlchemyBaseUserTable[int]):
    """Registered User model with authentication details integrated with fastapi-users"""
    __tablename__ = "registered_users"
    
    # Explicitly define the id as primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Custom fields specific to your application
    nickname: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    pfp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    
    # OAuth accounts relationship
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship("OAuthAccount", lazy="joined", cascade="all, delete-orphan")
    
    # fastapi-users provides these fields automatically:
    # - id: int (primary key)
    # - email: str (unique, indexed)
    # - hashed_password: str
    # - is_active: bool (default True)
    # - is_superuser: bool (default False)
    # - is_verified: bool (default False)
    
    def __repr__(self):
        return f"<RegisteredUser(id={self.id}, nickname='{self.nickname}', email='{self.email}', is_active={self.is_active})>"
