# app/config/settings.py

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DECODE_RESPONSES: bool = True
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "l2p_db"
    
    # Application Configuration
    APP_NAME: str = "L2P Backend"
    DEBUG: bool = True
    
    # JWT Authentication Configuration
    SECRET_KEY: str = "CHANGE-THIS-SECRET-KEY-IN-PRODUCTION-USE-ENV-FILE"  # Must be changed in .env file!
    JWT_LIFETIME_SECONDS: int = 3600  # 1 hour
    
    # Email Configuration (Resend API)
    RESEND_API_KEY: str = "CHANGE-THIS-SECRET-KEY-IN-PRODUCTION-USE-ENV-FILE"  # Must be changed in .env file!
    EMAIL_FROM: str = "onboarding@resend.dev"
    FRONTEND_URL: str = "http://localhost:5173"  # Frontend URL for verification links #TODO ADD REDIRECT
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection URL for SQLAlchemy"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
