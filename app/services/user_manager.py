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
from services.email_service import email_service
import secrets
import string


class NicknameAlreadyExists(Exception):
    """Exception raised when nickname is already taken"""
    pass


class EmailAlreadyExists(Exception):
    """Exception raised when email is already registered"""
    pass


class UserManager(IntegerIDMixin, BaseUserManager[RegisteredUser, int]):
    """User manager for registered users with custom hooks"""
    
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY
    
    async def validate_email_unique(self, email: str, exclude_user_id: Optional[int] = None):
        """
        Validate that email is unique in the database
        
        Args:
            email: The email to check
            exclude_user_id: Optional user ID to exclude from the check (for updates)
            
        Raises:
            EmailAlreadyExists: If email is already registered.
        """
        query = select(RegisteredUser).where(RegisteredUser.email == email)
        if exclude_user_id is not None:
            query = query.where(RegisteredUser.id != exclude_user_id)
        
        result = await self.user_db.session.execute(query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user is not None:
            raise EmailAlreadyExists(f"Email '{email}' is already registered")
    
    async def validate_nickname_unique(self, nickname: str, exclude_user_id: Optional[int] = None):
        """
        Validate that nickname is unique in the database
        
        Args:
            nickname: The nickname to check
            exclude_user_id: Optional user ID to exclude from the check (for updates)
            
        Raises:
            NicknameAlreadyExists: If nickname is already taken
        """
        query = select(RegisteredUser).where(RegisteredUser.nickname == nickname)
        if exclude_user_id is not None:
            query = query.where(RegisteredUser.id != exclude_user_id)
        
        result = await self.user_db.session.execute(query)
        existing_user = result.scalar_one_or_none()
        
        if existing_user is not None:
            raise NicknameAlreadyExists(f"Nickname '{nickname}' is already taken")
    
    async def on_after_register(self, user: RegisteredUser, request: Optional[Request] = None):
        """Hook called after user registration"""
        print(f"✅ User {user.id} (nickname: {user.nickname}) has registered with email: {user.email}")
    
    async def on_after_forgot_password(
        self, user: RegisteredUser, token: str, request: Optional[Request] = None
    ):
        """Hook called after forgot password request"""
        print(f"🔑 User {user.id} ({user.email}) has forgotten their password. Reset token: {token}")
        # Send password reset email
        await email_service.send_password_reset_email(
            email=user.email,
            token=token,
            nickname=user.nickname
        )
    
    async def on_after_request_verify(
        self, user: RegisteredUser, token: str, request: Optional[Request] = None
    ):
        """Hook called after verification request"""
        print(f"📧 Verification requested for user {user.id} ({user.email}). Verification token: {token}")
        # Send verification email
        await email_service.send_verification_email(
            email=user.email,
            token=token,
            nickname=user.nickname
        )
    
    async def on_after_login(
        self, 
        user: RegisteredUser, 
        request: Optional[Request] = None,
        response = None
    ):
        """Hook called after successful login"""
        print(f"🔐 User {user.id} ({user.nickname}) has logged in")
    
    async def on_after_register(self, user: RegisteredUser, request: Optional[Request] = None):
        """Hook called after user registration"""
        print(f"✅ User {user.id} (nickname: {user.nickname}) has registered with email: {user.email}")
    
    async def _generate_unique_nickname(self, oauth_name: str, email: Optional[str] = None) -> str:
        """Generate a unique nickname for OAuth users"""
        # First, try to use the email username as the nickname
        if email:
            email_username = email.split('@')[0]
            # Clean the username - remove dots, special chars, keep alphanumeric and underscores
            clean_username = ''.join(c if c.isalnum() or c == '_' else '_' for c in email_username)
            
            # Try the cleaned email username first
            try:
                await self.validate_nickname_unique(clean_username)
                return clean_username
            except NicknameAlreadyExists:
                # Try with a counter suffix
                for counter in range(1, 100):
                    try_nickname = f"{clean_username}{counter}"
                    try:
                        await self.validate_nickname_unique(try_nickname)
                        return try_nickname
                    except NicknameAlreadyExists:
                        continue
        
        # Fallback: generate random nickname
        random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(5))
        generated_nickname = f"{oauth_name}_user_{random_suffix}"
        
        # Ensure the nickname is unique
        counter = 0
        while True:
            try:
                await self.validate_nickname_unique(generated_nickname)
                return generated_nickname  # Nickname is unique
            except NicknameAlreadyExists:
                counter += 1
                generated_nickname = f"{oauth_name}_user_{random_suffix}_{counter}"
    
    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: Optional[int] = None,
        refresh_token: Optional[str] = None,
        request: Optional[Request] = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> RegisteredUser:
        """
        Handle OAuth callback and create user with auto-generated nickname.
        
        This override ensures that OAuth users get a valid nickname.
        """
        # Check if OAuth account already exists
        try:
            user = await self.get_by_oauth_account(oauth_name, account_id)
            # Update existing OAuth account
            await self.user_db.update_oauth_account(
                user,
                {"oauth_name": oauth_name, "account_id": account_id},
                {
                    "access_token": access_token,
                    "account_email": account_email,
                    "expires_at": expires_at,
                    "refresh_token": refresh_token,
                }
            )
            return user
        except:
            pass  # OAuth account doesn't exist, continue to create
        
        # Try to associate with existing user by email
        if associate_by_email:
            try:
                user = await self.get_by_email(account_email)
                # Create OAuth account association
                await self.user_db.add_oauth_account(
                    user,
                    {
                        "oauth_name": oauth_name,
                        "account_id": account_id,
                        "access_token": access_token,
                        "account_email": account_email,
                        "expires_at": expires_at,
                        "refresh_token": refresh_token,
                    }
                )
                return user
            except:
                pass  # User doesn't exist, continue to create
        
        # Generate a unique nickname for this OAuth user
        nickname = await self._generate_unique_nickname(oauth_name, account_email)
        
        # Create new user with generated nickname
        user_dict = {
            "email": account_email,
            "hashed_password": self.password_helper.hash(secrets.token_urlsafe(32)),
            "is_verified": is_verified_by_default,
            "nickname": nickname,  # Add the generated nickname
        }
        
        user = await self.user_db.create(user_dict)
        
        # Create OAuth account association
        await self.user_db.add_oauth_account(
            user,
            {
                "oauth_name": oauth_name,
                "account_id": account_id,
                "access_token": access_token,
                "account_email": account_email,
                "expires_at": expires_at,
                "refresh_token": refresh_token,
            }
        )
        
        await self.on_after_register(user, request)
        
        return user
    
    async def create(self, user_create: UserCreate, safe: bool = False, request: Optional[Request] = None) -> RegisteredUser:
        """
        Override create to validate nickname and email uniqueness before creating user.
        Also sets the generated nickname for OAuth users.
        """
        # For OAuth users, we need to set a nickname if not provided
        if not hasattr(user_create, 'nickname') or not user_create.nickname:
            # This shouldn't happen with normal registration, but handle it for OAuth
            raise ValueError("Nickname is required")
        
        # Validate email is unique
        await self.validate_email_unique(user_create.email)
        
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
        Override update to validate nickname and email uniqueness when being changed
        """
        # If email is being updated, validate it's unique
        if user_update.email is not None and user_update.email != user.email:
            await self.validate_email_unique(user_update.email, exclude_user_id=user.id)
        
        # If nickname is being updated, validate it's unique
        if user_update.nickname is not None and user_update.nickname != user.nickname:
            await self.validate_nickname_unique(user_update.nickname, exclude_user_id=user.id)
        
        # Call parent update method
        return await super().update(user_update, user, safe=safe, request=request)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency to get the user manager"""
    yield UserManager(user_db)
