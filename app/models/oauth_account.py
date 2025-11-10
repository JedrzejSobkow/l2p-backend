# app/models/oauth_account.py

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseOAuthAccountTable
from infrastructure.postgres_connection import Base


class OAuthAccount(Base, SQLAlchemyBaseOAuthAccountTable[int]):
    """OAuth account model for storing third-party authentication data"""
    __tablename__ = "oauth_accounts"
    
    # Explicitly define the id as primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to the user
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("registered_users.id", ondelete="CASCADE"), nullable=False)
    
    # fastapi-users provides these fields automatically:
    # - oauth_name: str (e.g., "google")
    # - access_token: str
    # - expires_at: int | None
    # - refresh_token: str | None
    # - account_id: str (unique OAuth account ID)
    # - account_email: str
    
    def __repr__(self):
        return f"<OAuthAccount(id={self.id}, oauth_name='{self.oauth_name}', user_id={self.user_id})>"
