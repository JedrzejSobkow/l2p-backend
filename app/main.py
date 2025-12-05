# app/main.py

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, status
from api.routes import auth, avatars, friendship, chat, lobby, user_status
from api.exception_handlers import register_exception_handlers
from infrastructure.redis_connection import redis_connection
from infrastructure.postgres_connection import postgres_connection
from infrastructure.minio_connection import minio_connection
import socketio
import asyncio
import logging

logger = logging.getLogger(__name__)

from fastapi.responses import JSONResponse
from services.user_manager import NicknameAlreadyExists, EmailAlreadyExists


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup: Initialize connections
    await redis_connection.connect()
    await postgres_connection.connect()
    
    minio_connection.connect()
    
    # Start timeout checker background task (Redis keyspace notification listener)
    from services.timeout_checker import TimeoutChecker
    from api.socketio import sio
    
    timeout_checker = TimeoutChecker(redis_connection.get_client(), sio)
    timeout_checker_task = asyncio.create_task(timeout_checker.start())
    logger.info("Timeout checker started (listening for Redis key expirations)")

    yield
    
    # Shutdown: Stop background tasks and close connections
    timeout_checker.stop()
    try:
        await asyncio.wait_for(timeout_checker_task, timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Timeout checker task did not stop gracefully")
    
    await postgres_connection.disconnect()
    await redis_connection.disconnect()
    minio_connection.disconnect()


app = FastAPI(lifespan=lifespan)

# Register domain exception handlers
register_exception_handlers(app)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy"}


# Exception handlers for custom validation errors
@app.exception_handler(NicknameAlreadyExists)
async def nickname_already_exists_handler(request: Request, exc: NicknameAlreadyExists):
    """Handle nickname already exists exception"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": {"field": "nickname", "message": str(exc)}}
    )


@app.exception_handler(EmailAlreadyExists)
async def email_already_exists_handler(request: Request, exc: EmailAlreadyExists):
    """Handle email already exists exception"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": {"field": "email", "message": str(exc)}}
    )


# CORS configuration - important: can't use "*" with allow_credentials=True
# Add your frontend URLs here
app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React/Next.js default
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,  # Required for cookies/authentication
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.auth_router, prefix="/v1")
app.include_router(auth.users_router, prefix="/v1")
app.include_router(avatars.avatar_router, prefix="/v1")
app.include_router(friendship.friendship_router, prefix="/v1")
app.include_router(chat.router, prefix="/v1")
app.include_router(lobby.router, prefix="/v1")
app.include_router(user_status.router, prefix="/v1")

# Import game router
from api.routes import game
app.include_router(game.router, prefix="/v1")

# Import Socket.IO instance and register all namespaces
from api.socketio import sio

# Wrap FastAPI app with Socket.IO
# This allows Socket.IO to handle /socket.io/* paths and pass everything else to FastAPI
# Namespaces are registered in api/socketio/__init__.py
app = socketio.ASGIApp(sio, app)
