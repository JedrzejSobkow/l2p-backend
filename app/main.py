# app/main.py

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from api.routes import default, auth
from infrastructure.redis_connection import connect_redis, disconnect_redis
from infrastructure.postgres_connection import connect_postgres, disconnect_postgres


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
