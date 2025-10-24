# app/main.py

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from api.routes import default, auth, avatars
from infrastructure.redis_connection import connect_redis, disconnect_redis
from infrastructure.postgres_connection import connect_postgres, disconnect_postgres
from services.user_manager import NicknameAlreadyExists, EmailAlreadyExists


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup: Initialize connections
    await connect_redis()
    await connect_postgres()
    
    yield
    
    # Shutdown: Close connections
    await disconnect_postgres()
    await disconnect_redis()


app = FastAPI(lifespan=lifespan)


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

app.include_router(default.router, prefix="/v1")
app.include_router(auth.auth_router, prefix="/v1")
app.include_router(auth.users_router, prefix="/v1")
app.include_router(avatars.avatar_router, prefix="/v1")

