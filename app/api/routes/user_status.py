# app/api/routes/user_status.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from models.registered_user import RegisteredUser
from schemas.user_status_schema import (
    UserStatusUpdateEvent,
    FriendStatusListResponse,
    UserStatus
)
from services.user_status_service import UserStatusService
from services.lobby_service import LobbyService
from infrastructure.postgres_connection import get_db_session
from infrastructure.redis_connection import redis_connection
from infrastructure.socketio_manager import manager
from api.routes.auth import current_active_user
import logging

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/status", tags=["User Status"])


@router.get("/friends", response_model=FriendStatusListResponse)
async def get_friends_statuses(
    current_user: RegisteredUser = Depends(current_active_user),
):
    """
    Get the current status of all friends.
    
    Returns a list of status information for all friends, including:
    - Online/Offline status
    - In-game status with game name
    - In-lobby status with lobby details
    
    This endpoint replaces the initial friend statuses that were previously
    sent via SocketIO on connection. Clients should call this endpoint to
    get initial statuses, then listen to 'friend_status_update' SocketIO
    events for real-time updates.
    """
    statuses = await UserStatusService.get_initial_friend_statuses(current_user.id)
    return FriendStatusListResponse(statuses=statuses)


@router.get("/friends/online", response_model=FriendStatusListResponse)
async def get_online_friends(
    current_user: RegisteredUser = Depends(current_active_user),
):
    """
    Get only the currently online friends (excludes offline friends).
    
    Returns a filtered list containing only friends who are:
    - ONLINE
    - IN_GAME
    - IN_LOBBY
    
    Useful for displaying active/available friends without cluttering
    the UI with offline users.
    """
    all_statuses = await UserStatusService.get_initial_friend_statuses(current_user.id)
    online_statuses = [s for s in all_statuses if s.status != UserStatus.OFFLINE]
    return FriendStatusListResponse(statuses=online_statuses)


@router.get("/me", response_model=UserStatusUpdateEvent)
async def get_my_status(
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get your own current status as seen by your friends.
    
    Returns your current status including:
    - Online status (always ONLINE when calling this, or IN_GAME/IN_LOBBY)
    - Game information if in a game
    - Lobby information if in a lobby
    """
    status = UserStatus.ONLINE
    game_name = None
    lobby_code = None
    lobby_filled_slots = None
    lobby_max_slots = None
    
    # Check if in game
    if current_user.id in UserStatusService._in_game_users:
        status = UserStatus.IN_GAME
        game_name = UserStatusService._in_game_users[current_user.id]
    else:
        # Check if in lobby
        try:
            redis = redis_connection.get_client()
            user_lobby_key = LobbyService._user_lobby_key(current_user.id)
            lobby_code_bytes = await redis.get(user_lobby_key)
            if lobby_code_bytes:
                lobby_code = lobby_code_bytes.decode() if isinstance(lobby_code_bytes, bytes) else lobby_code_bytes
                lobby = await LobbyService.get_lobby(redis, lobby_code)
                if lobby:
                    status = UserStatus.IN_LOBBY
                    lobby_filled_slots = lobby["current_players"]
                    lobby_max_slots = lobby["max_players"]
        except RuntimeError:
            logger.warning("Redis client not connected in get_my_status")
        except Exception as e:
            logger.error(f"Error checking lobby status: {e}")
    
    return UserStatusUpdateEvent(
        user_id=current_user.id,
        status=status,
        game_name=game_name,
        lobby_code=lobby_code,
        lobby_filled_slots=lobby_filled_slots,
        lobby_max_slots=lobby_max_slots
    )


@router.get("/users/{user_id}", response_model=UserStatusUpdateEvent)
async def get_user_status(
    user_id: int,
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get the current status of a specific user.
    
    **Authorization**: You can only query the status of users who are your friends.
    
    Args:
        user_id: The ID of the user whose status you want to query
    
    Returns:
        UserStatusUpdateEvent containing the user's current status
    
    Raises:
        403: If the requested user is not your friend
        404: If the user does not exist
    """
    # Get list of friend IDs to verify authorization
    friend_ids = await UserStatusService.get_friends_ids(current_user.id, session)
    
    if user_id not in friend_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only query the status of your friends"
        )
    
    # Build status for this specific user (similar to get_initial_friend_statuses logic)
    user_status = UserStatus.OFFLINE
    game_name = None
    lobby_code = None
    lobby_filled_slots = None
    lobby_max_slots = None
    
    # Check if online first
    if not manager.is_user_online(user_id):
        user_status = UserStatus.OFFLINE
    else:
        # User is online, check if in game or lobby
        user_status = UserStatus.ONLINE
        
        # Check if in game
        if user_id in UserStatusService._in_game_users:
            user_status = UserStatus.IN_GAME
            game_name = UserStatusService._in_game_users[user_id]
        else:
            # Check if in lobby
            try:
                redis = redis_connection.get_client()
                user_lobby_key = LobbyService._user_lobby_key(user_id)
                lobby_code_bytes = await redis.get(user_lobby_key)
                if lobby_code_bytes:
                    lobby_code = lobby_code_bytes.decode() if isinstance(lobby_code_bytes, bytes) else lobby_code_bytes
                    lobby = await LobbyService.get_lobby(redis, lobby_code)
                    if lobby:
                        user_status = UserStatus.IN_LOBBY
                        lobby_filled_slots = lobby["current_players"]
                        lobby_max_slots = lobby["max_players"]
            except RuntimeError:
                logger.warning("Redis client not connected in get_user_status")
            except Exception as e:
                logger.error(f"Error checking lobby status for user {user_id}: {e}")
    
    return UserStatusUpdateEvent(
        user_id=user_id,
        status=user_status,
        game_name=game_name,
        lobby_code=lobby_code,
        lobby_filled_slots=lobby_filled_slots,
        lobby_max_slots=lobby_max_slots
    )
