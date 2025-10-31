# app/services/friendship_service.py

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import joinedload
from models.friendship import Friendship
from models.registered_user import RegisteredUser
from schemas.friendship_schema import FriendshipWithUser, UserSearchResult
from exceptions.domain_exceptions import NotFoundException, BadRequestException, ConflictException


class FriendshipService:
    """Service for managing friendships"""
    
    @staticmethod
    async def send_friend_request(
        session: AsyncSession,
        requester_id: int,
        recipient_id: int
    ) -> Friendship:
        """
        Send a friend request from requester to recipient
        
        Args:
            session: Database session
            requester_id: ID of user sending the request
            recipient_id: ID of user receiving the request
            
        Returns:
            Created friendship object
            
        Raises:
            NotFoundException: If recipient doesn't exist
            BadRequestException: If users are the same
            ConflictException: If friendship already exists
        """
        # Check if recipient exists and is active
        recipient_query = select(RegisteredUser).where(
            RegisteredUser.id == recipient_id,
            RegisteredUser.is_active == True
        )
        result = await session.execute(recipient_query)
        recipient = result.scalar_one_or_none()
        
        if not recipient:
            raise NotFoundException(
                message="User not found",
                details={"user_id": recipient_id}
            )
        
        # Check if trying to friend themselves
        if requester_id == recipient.id:
            raise BadRequestException(
                message="Cannot send friend request to yourself"
            )
        
        # Check if friendship already exists (in either direction)
        existing_query = select(Friendship).where(
            or_(
                and_(
                    Friendship.user_id_1 == requester_id,
                    Friendship.user_id_2 == recipient.id
                ),
                and_(
                    Friendship.user_id_1 == recipient.id,
                    Friendship.user_id_2 == requester_id
                )
            )
        )
        result = await session.execute(existing_query)
        existing_friendship = result.scalar_one_or_none()
        
        if existing_friendship:
            if existing_friendship.status == "pending":
                raise ConflictException(
                    message="Friend request already pending",
                    details={"friendship_id": existing_friendship.id_friendship}
                )
            elif existing_friendship.status == "accepted":
                raise ConflictException(
                    message="Users are already friends",
                    details={"friendship_id": existing_friendship.id_friendship}
                )
        
        # Create new friendship with pending status
        new_friendship = Friendship(
            user_id_1=requester_id,
            user_id_2=recipient.id,
            status="pending"
        )
        
        session.add(new_friendship)
        await session.commit()
        await session.refresh(new_friendship)
        
        return new_friendship
    
    @staticmethod
    async def accept_friend_request(
        session: AsyncSession,
        recipient_id: int,
        requester_id: int
    ) -> Friendship:
        """
        Accept a pending friend request
        
        Args:
            session: Database session
            recipient_id: ID of user accepting the request
            requester_id: ID of user who sent the request
            
        Returns:
            Updated friendship object
            
        Raises:
            NotFoundException: If requester or friendship not found
            BadRequestException: If friendship is not pending
        """
        # Get the requester
        requester_query = select(RegisteredUser).where(
            RegisteredUser.id == requester_id,
            RegisteredUser.is_active == True
        )
        result = await session.execute(requester_query)
        requester = result.scalar_one_or_none()
        
        if not requester:
            raise NotFoundException(
                message="User not found",
                details={"user_id": requester_id}
            )
        
        # Get the friendship where requester is user_id_1 and recipient is user_id_2
        query = select(Friendship).where(
            and_(
                Friendship.user_id_1 == requester.id,
                Friendship.user_id_2 == recipient_id
            )
        )
        result = await session.execute(query)
        friendship = result.scalar_one_or_none()
        
        if not friendship:
            raise NotFoundException(
                message="Friend request not found",
                details={"requester_id": requester_id, "recipient_id": recipient_id}
            )
        
        # Check if request is pending
        if friendship.status != "pending":
            raise BadRequestException(
                message="Friend request is not pending",
                details={"current_status": friendship.status, "friendship_id": friendship.id_friendship}
            )
        
        # Update status to accepted
        friendship.status = "accepted"
        await session.commit()
        await session.refresh(friendship)
        
        return friendship
    
    @staticmethod
    async def remove_friendship(
        session: AsyncSession,
        user_id: int,
        friend_id: int
    ) -> None:
        """
        Remove a friendship or reject a friend request
        
        Args:
            session: Database session
            user_id: ID of user removing the friendship
            friend_id: ID of the friend to remove
            
        Raises:
            NotFoundException: If friend or friendship not found
        """
        # Get the friend
        friend_query = select(RegisteredUser).where(
            RegisteredUser.id == friend_id,
            RegisteredUser.is_active == True
        )
        result = await session.execute(friend_query)
        friend = result.scalar_one_or_none()
        
        if not friend:
            raise NotFoundException(
                message="User not found",
                details={"user_id": friend_id}
            )
        
        # Get the friendship (in either direction)
        query = select(Friendship).where(
            or_(
                and_(
                    Friendship.user_id_1 == user_id,
                    Friendship.user_id_2 == friend.id
                ),
                and_(
                    Friendship.user_id_1 == friend.id,
                    Friendship.user_id_2 == user_id
                )
            )
        )
        result = await session.execute(query)
        friendship = result.scalar_one_or_none()
        
        if not friendship:
            raise NotFoundException(
                message="Friendship not found",
                details={"user_id": user_id, "friend_id": friend_id}
            )
        
        # Delete the friendship
        await session.delete(friendship)
        await session.commit()
    
    @staticmethod
    async def get_user_friendships(
        session: AsyncSession,
        user_id: int,
        status_filter: Optional[str] = None
    ) -> List[FriendshipWithUser]:
        """
        Get all friendships for a user
        
        Args:
            session: Database session
            user_id: ID of the user
            status_filter: Optional status filter ('pending', 'accepted')
            
        Returns:
            List of friendships with user details
        """
        # Build query to get friendships where user is either user_1 or user_2
        query = select(Friendship).where(
            or_(
                Friendship.user_id_1 == user_id,
                Friendship.user_id_2 == user_id
            )
        ).options(
            joinedload(Friendship.user_1),
            joinedload(Friendship.user_2)
        )
        
        if status_filter:
            query = query.where(Friendship.status == status_filter)
        
        result = await session.execute(query)
        friendships = result.scalars().all()
        
        # Transform to response format
        friendship_list = []
        for friendship in friendships:
            # Determine which user is the friend (not the current user)
            if friendship.user_id_1 == user_id:
                friend = friendship.user_2
                friend_id = friendship.user_id_2
                is_requester = True
            else:
                friend = friendship.user_1
                friend_id = friendship.user_id_1
                is_requester = False
            
            friendship_list.append(FriendshipWithUser(
                friend_user_id=friend_id,
                friend_nickname=friend.nickname,
                friend_pfp_path=friend.pfp_path,
                friend_description=friend.description,
                status=friendship.status,
                created_at=friendship.created_at,
                is_requester=is_requester
            ))
        
        return friendship_list
    
    @staticmethod
    async def search_users(
        session: AsyncSession,
        search_query: str,
        current_user_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[UserSearchResult], int]:
        """
        Search for users by nickname
        
        Args:
            session: Database session
            search_query: Search string (minimum 3 characters)
            current_user_id: ID of the current user (to exclude from results)
            page: Page number (1-indexed)
            page_size: Number of results per page
            
        Returns:
            Tuple of (list of users, total count)
            
        Raises:
            BadRequestException: If search query is too short
        """
        # Validate search query length
        if len(search_query.strip()) < 3:
            raise BadRequestException(
                message="Search query must be at least 3 characters",
                details={"query_length": len(search_query.strip()), "minimum_length": 3}
            )
        
        # Build query to search by nickname (case-insensitive)
        search_pattern = f"%{search_query.strip()}%"
        base_query = select(RegisteredUser).where(
            and_(
                RegisteredUser.nickname.ilike(search_pattern),
                RegisteredUser.id != current_user_id,  # Exclude current user
                RegisteredUser.is_active == True  # Only active users
            )
        ).order_by(RegisteredUser.nickname)
        
        # Get total count
        count_query = select(func.count()).select_from(RegisteredUser).where(
            and_(
                RegisteredUser.nickname.ilike(search_pattern),
                RegisteredUser.id != current_user_id,
                RegisteredUser.is_active == True
            )
        )
        count_result = await session.execute(count_query)
        total = count_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = base_query.limit(page_size).offset(offset)
        
        result = await session.execute(query)
        users = result.scalars().all()
        
        # Transform to response format
        user_list = [
            UserSearchResult(
                user_id=user.id,
                nickname=user.nickname,
                pfp_path=user.pfp_path,
                description=user.description
            )
            for user in users
        ]
        
        return user_list, total
