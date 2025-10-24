# app/api/routes/auth.py

from fastapi import APIRouter, Depends, Response, Request
from fastapi_users import FastAPIUsers
from models.registered_user import RegisteredUser
from schemas.user_schema import UserRead, UserCreate, UserUpdate
from services.user_manager import get_user_manager, UserManager
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

# Custom registration endpoint that automatically requests verification
@auth_router.post("/register", response_model=UserRead)
async def register_and_verify(
    request: Request,
    user_create: UserCreate,
    user_manager: UserManager = Depends(get_user_manager),
):
    """Register a new user and automatically request email verification"""
    # Register the user
    user = await user_manager.create(user_create, safe=True, request=request)
    
    # If registration was successful, request verification
    if user:
        # Generate and send verification token
        token = await user_manager.request_verify(user, request)
    
    return user

# Include password reset routes
auth_router.include_router(
    fastapi_users.get_reset_password_router(),
)

# Include email verification routes
auth_router.include_router(
    fastapi_users.get_verify_router(UserRead),
)

# Dependency to get current active user
current_active_user = fastapi_users.current_user(active=True) #TODO verification required?

# Dependency to get current active superuser
current_superuser = fastapi_users.current_user(active=True, superuser=True)


@users_router.delete("/me", status_code=204, tags=["Users"])
async def delete_current_user(
    response: Response,
    user: RegisteredUser = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Deactivate the current user account and log them out.
    
    This endpoint:
    - Sets the user's is_active field to False
    - Clears the authentication cookie to log them out
    """
    # Deactivate the user account
    await user_manager.user_db.update(user, {"is_active": False})
    
    # Clear the authentication cookie to log out the user
    response.delete_cookie(
        key="l2p_auth",
        httponly=True,
        samesite="lax",
    )
    
    return None

# Include user management routes (get, update, delete user)
# Note: This is included AFTER our custom delete endpoint to avoid conflicts
users_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
)