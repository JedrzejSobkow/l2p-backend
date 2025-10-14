# app/infrastructure/postgres_connection.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from config.settings import settings


# Base class for SQLAlchemy models
Base = declarative_base()


class PostgresConnection:
    """Simple PostgreSQL connection manager using SQLAlchemy"""
    
    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
    
    async def connect(self):
        """Connect to PostgreSQL"""
        if self.engine is not None:
            return  # Already connected
        
        try:
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,  # Log SQL queries in debug mode
                pool_pre_ping=True,  # Verify connections before using them
                pool_size=10,  # Connection pool size
                max_overflow=20,  # Maximum overflow connections
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            # Test connection
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            
            print(f"✅ Connected to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
        except Exception as e:
            print(f"❌ Failed to connect to PostgreSQL: {e}")
            self.engine = None
            self.session_factory = None
            raise
    
    async def disconnect(self):
        """Disconnect from PostgreSQL"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            print("✅ Disconnected from PostgreSQL")
    
    def get_engine(self) -> AsyncEngine:
        """Get the SQLAlchemy async engine instance"""
        if not self.engine:
            raise RuntimeError("PostgreSQL engine is not connected. Call connect() first.")
        return self.engine
    
    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory for creating database sessions"""
        if not self.session_factory:
            raise RuntimeError("PostgreSQL session factory is not initialized. Call connect() first.")
        return self.session_factory


# Shared instance
postgres_connection = PostgresConnection()


async def connect_postgres():
    """Connect to PostgreSQL"""
    await postgres_connection.connect()


async def disconnect_postgres():
    """Disconnect from PostgreSQL"""
    await postgres_connection.disconnect()


def get_postgres_engine() -> AsyncEngine:
    """Get the PostgreSQL async engine instance"""
    return postgres_connection.get_engine()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory for creating database sessions"""
    return postgres_connection.get_session_factory()


async def get_db_session() -> AsyncSession:
    """
    Dependency for FastAPI routes to get a database session.
    
    Usage in routes:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(User))
            users = result.scalars().all()
            return users
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
