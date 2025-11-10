# app/infrastructure/user_database.py

from typing import AsyncGenerator
from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from models.registered_user import RegisteredUser
from models.oauth_account import OAuthAccount
from infrastructure.postgres_connection import get_db_session


async def get_user_db(session: AsyncSession = Depends(get_db_session)) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """Dependency to get the user database adapter with OAuth support"""
    yield SQLAlchemyUserDatabase(session, RegisteredUser, OAuthAccount)
