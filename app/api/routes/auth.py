# app/api/routes/auth.py

from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from models.registered_user import RegisteredUser
from schemas.user_schema import UserRead, UserCreate, UserUpdate
from services.user_manager import get_user_manager
from infrastructure.auth_config import auth_backend


# Initialize FastAPIUsers with our user manager and auth backend
fastapi_users = FastAPIUsers[RegisteredUser, int](
    get_user_manager=get_user_manager,
    auth_backends=[auth_backend],
)

# Create routers
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["Users"])

# Include authentication routes (login, logout)
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
)

# Include registration route
auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
)

# Include password reset routes
auth_router.include_router(
    fastapi_users.get_reset_password_router(),
)

# Include email verification routes
auth_router.include_router(
    fastapi_users.get_verify_router(UserRead),
)

# Include user management routes (get, update, delete user)
users_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
)

# Dependency to get current active user
current_active_user = fastapi_users.current_user(active=True)

# Dependency to get current active superuser
current_superuser = fastapi_users.current_user(active=True, superuser=True)
