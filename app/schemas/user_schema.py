# app/schemas/user_schema.py

from fastapi_users import schemas
from typing import Optional
from pydantic import EmailStr, Field, ConfigDict


class UserRead(schemas.BaseUser[int]):
    """Schema for reading user data"""
    id: int
    nickname: str
    email: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    pfp_path: Optional[str] = None
    description: Optional[str] = None


class UserCreate(schemas.BaseUserCreate):
    """Schema for creating a new user - only requires email, password, and nickname"""
    email: EmailStr
    password: str = Field(..., min_length=3)
    nickname: str = Field(..., min_length=3, max_length=255)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "strongpassword123",
                "nickname": "cool_user"
            }
        }
    )


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating user data"""
    nickname: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    pfp_path: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
