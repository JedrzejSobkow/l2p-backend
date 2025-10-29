# app/config/settings.py

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    
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
    
    # MinIO Configuration
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False  # Set to True for HTTPS
    MINIO_BUCKET_NAME: str = "l2p-bucket"
    
    # File Upload Configuration
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB in bytes
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    IMAGE_URL_EXPIRY_HOURS: int = 24  # How long presigned image URLs are valid
      
    # Email Configuration (Resend API)
    RESEND_API_KEY: str = "CHANGE-THIS-SECRET-KEY-IN-PRODUCTION-USE-ENV-FILE" # Must be changed in .env file!
    EMAIL_FROM: str = "L2P <noreply@rychu777.com>"  # Your verified domain
    FRONTEND_URL: str = "http://localhost:5173"  # Frontend URL for verification links #TODO ADD REDIRECT
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection URL for SQLAlchemy"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()
