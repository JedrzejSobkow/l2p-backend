# app/services/user_manager.py

from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from fastapi_users.exceptions import UserAlreadyExists
from sqlalchemy import select
from models.registered_user import RegisteredUser
from infrastructure.user_database import get_user_db
from config.settings import settings
from schemas.user_schema import UserCreate, UserUpdate


class UserManager(IntegerIDMixin, BaseUserManager[RegisteredUser, int]):
    """User manager for registered users with custom hooks"""
    
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY
    
    async def validate_nickname_unique(self, nickname: str, exclude_user_id: Optional[int] = None):
        """
        Validate that nickname is unique in the database
        
        Args:
            nickname: The nickname to check
            exclude_user_id: Optional user ID to exclude from the check (for updates)
            
        Raises:
            UserAlreadyExists: If nickname is already taken
        """
        query = select(RegisteredUser).where(RegisteredUser.nickname == nickname)
        if exclude_user_id is not None:
            query = query.where(RegisteredUser.id != exclude_user_id)
        
        result = await self.user_db.session.execute(query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user is not None:
            raise UserAlreadyExists(f"Nickname '{nickname}' is already taken")
    
    async def on_after_register(self, user: RegisteredUser, request: Optional[Request] = None):
        """Hook called after user registration"""
        print(f"✅ User {user.id} (nickname: {user.nickname}) has registered with email: {user.email}")
    
    async def on_after_forgot_password(
        self, user: RegisteredUser, token: str, request: Optional[Request] = None
    ):
        """Hook called after forgot password request"""
        print(f"🔑 User {user.id} ({user.email}) has forgotten their password. Reset token: {token}")
    
    async def on_after_request_verify(
        self, user: RegisteredUser, token: str, request: Optional[Request] = None
    ):
        """Hook called after verification request"""
        print(f"📧 Verification requested for user {user.id} ({user.email}). Verification token: {token}")
    
    async def on_after_login(
        self, 
        user: RegisteredUser, 
        request: Optional[Request] = None,
        response = None
    ):
        """Hook called after successful login"""
        print(f"🔐 User {user.id} ({user.nickname}) has logged in")
    
    async def create(self, user_create: UserCreate, safe: bool = False, request: Optional[Request] = None) -> RegisteredUser:
        """
        Override create to validate nickname uniqueness before creating user
        """
        # Validate nickname is unique
        await self.validate_nickname_unique(user_create.nickname)
        
        # Call parent create method
        return await super().create(user_create, safe=safe, request=request)
    
    async def update(
        self,
        user_update: UserUpdate,
        user: RegisteredUser,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> RegisteredUser:
        """
        Override update to validate nickname uniqueness when nickname is being changed
        """
        # If nickname is being updated, validate it's unique
        if user_update.nickname is not None and user_update.nickname != user.nickname:
            await self.validate_nickname_unique(user_update.nickname, exclude_user_id=user.id)
        
        # Call parent update method
        return await super().update(user_update, user, safe=safe, request=request)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency to get the user manager"""
    yield UserManager(user_db)
