# app/schemas/user_schema.py

from fastapi_users import schemas
from typing import Optional
from pydantic import EmailStr, Field, ConfigDict, field_validator
import re


class UserValidatorsMixin:
    """Mixin class with shared validators for user schemas"""
    
    @field_validator('nickname')
    @classmethod
    def validate_nickname(cls, v: Optional[str]) -> Optional[str]:
        """Validate nickname - example: no spaces allowed"""
        if v is not None:
            # Strip whitespace
            v = v.strip()
            # Example validation: no leading/trailing spaces after strip
            if not v:
                raise ValueError('Nickname cannot be empty or only whitespace')
            # Example: disallow special characters (customize as needed)
            # if not v.replace('_', '').isalnum():
            #     raise ValueError('Nickname can only contain letters, numbers, and underscores')
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Validate password strength"""
        if v is not None:
            # Example validation: ensure password has some complexity
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters long')
            # Add more rules as needed:
            # if not any(c.isupper() for c in v):
            #     raise ValueError('Password must contain at least one uppercase letter')
            # if not any(c.isdigit() for c in v):
            #     raise ValueError('Password must contain at least one digit')
        return v


class UserRead(schemas.BaseUser[int]):
    """Schema for reading user data"""
    nickname: str
    email: str
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    pfp_path: Optional[str] = None
    description: Optional[str] = None


class UserCreate(UserValidatorsMixin, schemas.BaseUserCreate):
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


class UserUpdate(UserValidatorsMixin, schemas.BaseUserUpdate):
    """Schema for updating user data - only allows patching pfp_path, description, password, and nickname"""
    email: None = None

    nickname: Optional[str] = Field(None, min_length=3, max_length=255)
    password: Optional[str] = Field(None, min_length=3)
    pfp_path: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('pfp_path')
    @classmethod
    def validate_pfp_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate profile picture path
        
        TODO: Restrict paths to predefined allowed paths
        """
        if v is not None:
            # Only allow predefined avatar paths: /images/avatar/x.png where x is 1-16
            pattern = r'^/images/avatar/([1-9]|1[0-6])\.png$'
            if not re.match(pattern, v):
                raise ValueError('Profile picture path must be in format /images/avatar/x.png where x is a number between 1 and 16')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nickname": "new_cool_nickname",
                "pfp_path": "/images/avatar/1.png",
                "description": "Pensjonariusz Bekas"
            }
        }
    )
