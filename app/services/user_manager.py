# app/services/user_manager.py

from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin
from models.registered_user import RegisteredUser
from infrastructure.user_database import get_user_db
from config.settings import settings


class UserManager(IntegerIDMixin, BaseUserManager[RegisteredUser, int]):
    """User manager for registered users with custom hooks"""
    
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY
    
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


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency to get the user manager"""
    yield UserManager(user_db)
