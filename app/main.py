# app/main.py

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from api.routes import default, auth, friendship, chat
from api.exception_handlers import register_exception_handlers
from infrastructure.redis_connection import redis_connection
from infrastructure.postgres_connection import postgres_connection
from infrastructure.minio_connection import minio_connection
import socketio
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup: Initialize connections
    await redis_connection.connect()
    await postgres_connection.connect()
    
    minio_connection.connect()

    yield
    
    # Shutdown: Close connections
    await postgres_connection.disconnect()
    await redis_connection.disconnect()
    minio_connection.disconnect()


app = FastAPI(lifespan=lifespan)

# Register domain exception handlers
register_exception_handlers(app)

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],  #TODO adres frontendu zamiast '*'
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(default.router, prefix="/v1")
app.include_router(auth.auth_router, prefix="/v1")
app.include_router(auth.users_router, prefix="/v1")
app.include_router(friendship.friendship_router, prefix="/v1")
app.include_router(chat.router, prefix="/v1")

# Import Socket.IO instance and register all namespaces
from api.socketio import sio

# Wrap FastAPI app with Socket.IO
# This allows Socket.IO to handle /socket.io/* paths and pass everything else to FastAPI
# Namespaces are registered in api/socketio/__init__.py
app = socketio.ASGIApp(sio, app)

