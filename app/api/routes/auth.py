# app/api/routes/auth.py

from fastapi import APIRouter, Depends, Response, Request, Query
from fastapi_users import FastAPIUsers
from models.registered_user import RegisteredUser
from schemas.user_schema import UserRead, UserCreate, UserUpdate, GuestSessionResponse, UserLeaderboardRead
from services.user_manager import get_user_manager, UserManager
from services.guest_service import GuestService
from infrastructure.auth_config import auth_backend
from infrastructure.google_oauth import google_oauth_client
from infrastructure.redis_connection import get_redis
from infrastructure.socketio_manager import manager as socketio_manager
from config.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.postgres_connection import get_db_session
from sqlalchemy import select


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

# Include Google OAuth routes
# The scopes parameter tells FastAPI Users which permissions to request from Google
auth_router.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,
        settings.SECRET_KEY,
        redirect_url=f"{settings.BACKEND_URL}/v1/auth/google/callback",
        associate_by_email=True,  # Associate OAuth account with existing email
        is_verified_by_default=True,  # Mark OAuth users as verified by default
    ),
    prefix="/google",
    tags=["Authentication"],
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


@users_router.get("/online-count", tags=["Users"])
async def get_online_users_count():
    """
    Get the total number of online users.
    """
    count = socketio_manager.get_online_users_count()
    return {"count": count}


@auth_router.post("/guest/session", response_model=GuestSessionResponse, tags=["Authentication"])
async def create_guest_session(
    response: Response,
):
    """
    Create a guest session with auto-generated nickname (guest{6digits})
    
    - No input required
    - Returns guest_id and nickname
    - Sets cookie 'l2p_guest' with guest_id
    - Session expires after 8 hours
    """
    redis = get_redis()
    
    # Create guest session with auto-generated nickname
    guest = await GuestService.create_guest_session(redis)
    
    # Set guest cookie
    response.set_cookie(
        key="l2p_guest",
        value=guest.guest_id,
        httponly=True,
        max_age=GuestService.GUEST_SESSION_TTL,
        samesite="lax"
    )
    
    return GuestSessionResponse(
        guest_id=guest.guest_id,
        nickname=guest.nickname,
        expires_in=GuestService.GUEST_SESSION_TTL
    )


@users_router.get("/leaderboard", response_model=list[UserLeaderboardRead])
async def get_leaderboard(
    n: int = Query(default=10, ge=1, le=100, description="Number of top players to retrieve"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve the top N players with the highest ELO ratings.
    
    Args:
        n: Number of top players to retrieve (default: 10, max: 100)
        
    Returns:
        List of users sorted by ELO rating in descending order
    """
    stmt = (
        select(RegisteredUser)
        .where(RegisteredUser.is_active == True)
        .order_by(RegisteredUser.elo.desc())
        .limit(n)
    )
    
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    return users

@users_router.delete("/me", status_code=204, tags=["Users"])
async def delete_current_user(
    response: Response,
    user: RegisteredUser = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Permanently delete the current user account and log them out.
    
    This endpoint:
    - Completely removes the user from the database
    - Clears the authentication cookie to log them out
    """
    # Delete the user from the database
    # await user_manager.user_db.update(user, {"is_active": False}) just deactivating
    await user_manager.user_db.delete(user)
    
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
