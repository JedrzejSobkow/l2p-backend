"""
Pytest configuration and fixtures for testing
"""
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from infrastructure.postgres_connection import Base
from models.registered_user import RegisteredUser
from models.friendship import Friendship
from models.chat_message import ChatMessage  # Import to register with Base
from datetime import datetime, UTC


# Test database URL - using file-based SQLite to avoid in-memory connection issues
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="function")
async def db_engine():
    """Create a test database engine"""
    # Import all models to ensure they're registered with Base.metadata
    from models.registered_user import RegisteredUser  # noqa: F401
    from models.friendship import Friendship  # noqa: F401
    from models.chat_message import ChatMessage  # noqa: F401
    
    import os
    # Remove test database if it exists
    if os.path.exists("./test.db"):
        os.remove("./test.db")
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables and close
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()
    
    # Remove test database file
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session"""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user_1(db_session: AsyncSession) -> RegisteredUser:
    """Create a test user 1"""
    user = RegisteredUser(
        email="user1@test.com",
        hashed_password="hashed_password_1",
        nickname="TestUser1",
        pfp_path="/path/to/pfp1.jpg",
        description="Test user 1 description",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_2(db_session: AsyncSession) -> RegisteredUser:
    """Create a test user 2"""
    user = RegisteredUser(
        email="user2@test.com",
        hashed_password="hashed_password_2",
        nickname="TestUser2",
        pfp_path="/path/to/pfp2.jpg",
        description="Test user 2 description",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_3(db_session: AsyncSession) -> RegisteredUser:
    """Create a test user 3"""
    user = RegisteredUser(
        email="user3@test.com",
        hashed_password="hashed_password_3",
        nickname="TestUser3",
        pfp_path="/path/to/pfp3.jpg",
        description="Test user 3 description",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> RegisteredUser:
    """Create an inactive test user"""
    user = RegisteredUser(
        email="inactive@test.com",
        hashed_password="hashed_password_inactive",
        nickname="InactiveUser",
        pfp_path=None,
        description=None,
        is_active=False,
        is_superuser=False,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def pending_friendship(
    db_session: AsyncSession,
    test_user_1: RegisteredUser,
    test_user_2: RegisteredUser
) -> Friendship:
    """Create a pending friendship between user 1 and user 2"""
    friendship = Friendship(
        user_id_1=test_user_1.id,
        user_id_2=test_user_2.id,
        status="pending",
        created_at=datetime.now(UTC)
    )
    db_session.add(friendship)
    await db_session.commit()
    await db_session.refresh(friendship)
    return friendship


@pytest.fixture
async def accepted_friendship(
    db_session: AsyncSession,
    test_user_1: RegisteredUser,
    test_user_3: RegisteredUser
) -> Friendship:
    """Create an accepted friendship between user 1 and user 3"""
    friendship = Friendship(
        user_id_1=test_user_1.id,
        user_id_2=test_user_3.id,
        status="accepted",
        created_at=datetime.now(UTC)
    )
    db_session.add(friendship)
    await db_session.commit()
    await db_session.refresh(friendship)
    return friendship


@pytest.fixture
async def redis_client():
    """Create a test Redis client using fakeredis"""
    import fakeredis.aioredis
    
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    yield redis
    
    # Cleanup
    await redis.flushall()
    await redis.aclose()
