# app/api/routes/friendship.py

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from models.registered_user import RegisteredUser
from schemas.friendship_schema import (
    FriendshipCreate,
    FriendshipResponse,
    FriendshipWithUser,
    UserSearchResponse,
    UserSearchResult
)
from services.friendship_service import FriendshipService
from infrastructure.postgres_connection import get_db_session
from api.routes.auth import current_active_user
import math


# Create router
friendship_router = APIRouter(prefix="/friends", tags=["Friendships"])


@friendship_router.get("/search", response_model=UserSearchResponse)
async def search_users(
    q: str = Query(..., min_length=3, description="Search query (minimum 3 characters)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of results per page"),
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Search for users by nickname.
    
    - **q**: Search query (minimum 3 characters)
    - **page**: Page number (default: 1)
    - **page_size**: Number of results per page (default: 20, max: 100)
    
    Returns paginated list of users matching the search query.
    """
    users, total = await FriendshipService.search_users(
        session=session,
        search_query=q,
        current_user_id=current_user.id,
        page=page,
        page_size=page_size
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return UserSearchResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@friendship_router.post("/request", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    friendship_data: FriendshipCreate,
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Send a friend request to another user.
    
    - **friend_user_id**: User ID of the user to send the friend request to
    
    Returns the created friendship object with status 'pending'.
    """
    friendship = await FriendshipService.send_friend_request(
        session=session,
        requester_id=current_user.id,
        recipient_id=friendship_data.friend_user_id
    )
    
    return friendship


@friendship_router.post("/accept", response_model=FriendshipResponse)
async def accept_friend_request(
    friendship_data: FriendshipCreate,
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Accept a pending friend request.
    
    - **friend_user_id**: User ID of the user who sent the friend request
    
    Only the recipient of the friend request can accept it.
    """
    friendship = await FriendshipService.accept_friend_request(
        session=session,
        recipient_id=current_user.id,
        requester_id=friendship_data.friend_user_id
    )
    
    return friendship


@friendship_router.delete("/{friend_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friendship(
    friend_user_id: int,
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Remove a friendship or reject a friend request.
    
    - **friend_user_id**: User ID of the friend to remove
    
    Either user in the friendship can remove it.
    If the friendship is pending, this acts as rejecting the request.
    """
    await FriendshipService.remove_friendship(
        session=session,
        user_id=current_user.id,
        friend_id=friend_user_id
    )
    
    return None


@friendship_router.get("/", response_model=list[FriendshipWithUser])
async def get_my_friendships(
    status_filter: Optional[str] = Query(None, description="Filter by status: 'pending' or 'accepted'"),
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get all friendships for the current user.
    
    - **status**: Optional filter by status ('pending' or 'accepted')
    
    Returns list of friendships with friend details.
    Pending friendships where you are user_id_2 are incoming requests.
    Pending friendships where you are user_id_1 are outgoing requests.
    """
    friendships = await FriendshipService.get_user_friendships(
        session=session,
        user_id=current_user.id,
        status_filter=status_filter
    )
    
    return friendships
