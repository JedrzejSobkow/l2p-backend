"""
Unit tests for FriendshipService

Tests cover:
- Sending friend requests
- Accepting friend requests
- Removing friendships
- Getting user friendships
- Searching users
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from models.registered_user import RegisteredUser
from models.friendship import Friendship
from services.friendship_service import FriendshipService
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException
)


@pytest.mark.unit
class TestSendFriendRequest:
    """Test cases for send_friend_request method"""
    
    async def test_send_friend_request_success(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test successfully sending a friend request"""
        # Act
        friendship = await FriendshipService.send_friend_request(
            session=db_session,
            requester_id=test_user_1.id,
            recipient_id=test_user_2.id
        )
        
        # Assert
        assert friendship is not None
        assert friendship.user_id_1 == test_user_1.id
        assert friendship.user_id_2 == test_user_2.id
        assert friendship.status == "pending"
        assert friendship.id_friendship is not None
    
    async def test_send_friend_request_to_nonexistent_user(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test sending a friend request to a non-existent user"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_1.id,
                recipient_id=99999  # Non-existent user
            )
        
        assert exc_info.value.message == "User not found"
        assert exc_info.value.details["user_id"] == 99999
    
    async def test_send_friend_request_to_inactive_user(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        inactive_user: RegisteredUser
    ):
        """Test sending a friend request to an inactive user"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_1.id,
                recipient_id=inactive_user.id
            )
        
        assert exc_info.value.message == "User not found"
    
    async def test_send_friend_request_to_self(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test sending a friend request to yourself"""
        # Act & Assert
        with pytest.raises(BadRequestException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_1.id,
                recipient_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Cannot send friend request to yourself"
    
    async def test_send_friend_request_already_pending(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test sending a friend request when one is already pending"""
        # Act & Assert
        with pytest.raises(ConflictException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_1.id,
                recipient_id=test_user_2.id
            )
        
        assert exc_info.value.message == "Friend request already pending"
        assert exc_info.value.details["friendship_id"] == pending_friendship.id_friendship
    
    async def test_send_friend_request_already_pending_reverse(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test sending a friend request when one is already pending (reverse direction)"""
        # Act & Assert
        with pytest.raises(ConflictException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_2.id,
                recipient_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Friend request already pending"
    
    async def test_send_friend_request_already_friends(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser,
        accepted_friendship: Friendship
    ):
        """Test sending a friend request when users are already friends"""
        # Act & Assert
        with pytest.raises(ConflictException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_1.id,
                recipient_id=test_user_3.id
            )
        
        assert exc_info.value.message == "Users are already friends"
    
    async def test_send_friend_request_already_friends_reverse(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser,
        accepted_friendship: Friendship
    ):
        """Test sending a friend request when users are already friends (reverse direction)"""
        # Act & Assert
        with pytest.raises(ConflictException) as exc_info:
            await FriendshipService.send_friend_request(
                session=db_session,
                requester_id=test_user_3.id,
                recipient_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Users are already friends"


@pytest.mark.unit
class TestAcceptFriendRequest:
    """Test cases for accept_friend_request method"""
    
    async def test_accept_friend_request_success(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test successfully accepting a friend request"""
        # Act
        friendship = await FriendshipService.accept_friend_request(
            session=db_session,
            recipient_id=test_user_2.id,
            requester_id=test_user_1.id
        )
        
        # Assert
        assert friendship is not None
        assert friendship.id_friendship == pending_friendship.id_friendship
        assert friendship.status == "accepted"
        assert friendship.user_id_1 == test_user_1.id
        assert friendship.user_id_2 == test_user_2.id
    
    async def test_accept_friend_request_nonexistent_requester(
        self,
        db_session: AsyncSession,
        test_user_2: RegisteredUser
    ):
        """Test accepting a friend request from a non-existent user"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.accept_friend_request(
                session=db_session,
                recipient_id=test_user_2.id,
                requester_id=99999
            )
        
        assert exc_info.value.message == "User not found"
        assert exc_info.value.details["user_id"] == 99999
    
    async def test_accept_friend_request_inactive_requester(
        self,
        db_session: AsyncSession,
        test_user_2: RegisteredUser,
        inactive_user: RegisteredUser
    ):
        """Test accepting a friend request from an inactive user"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.accept_friend_request(
                session=db_session,
                recipient_id=test_user_2.id,
                requester_id=inactive_user.id
            )
        
        assert exc_info.value.message == "User not found"
    
    async def test_accept_friend_request_not_found(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test accepting a non-existent friend request"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.accept_friend_request(
                session=db_session,
                recipient_id=test_user_3.id,
                requester_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Friend request not found"
    
    async def test_accept_friend_request_already_accepted(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser,
        accepted_friendship: Friendship
    ):
        """Test accepting a friend request that is already accepted"""
        # Act & Assert
        with pytest.raises(BadRequestException) as exc_info:
            await FriendshipService.accept_friend_request(
                session=db_session,
                recipient_id=test_user_3.id,
                requester_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Friend request is not pending"
        assert exc_info.value.details["current_status"] == "accepted"
    
    async def test_accept_friend_request_wrong_direction(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test accepting a friend request in the wrong direction (requester trying to accept)"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.accept_friend_request(
                session=db_session,
                recipient_id=test_user_1.id,  # Requester is user_1
                requester_id=test_user_2.id   # Recipient is user_2
            )
        
        assert exc_info.value.message == "Friend request not found"


@pytest.mark.unit
class TestRemoveFriendship:
    """Test cases for remove_friendship method"""
    
    async def test_remove_friendship_success_pending(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test successfully removing a pending friendship"""
        # Act
        await FriendshipService.remove_friendship(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_2.id
        )
        
        # Assert - verify friendship is deleted
        from sqlalchemy import select
        result = await db_session.execute(
            select(Friendship).where(Friendship.id_friendship == pending_friendship.id_friendship)
        )
        deleted_friendship = result.scalar_one_or_none()
        assert deleted_friendship is None
    
    async def test_remove_friendship_success_accepted(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser,
        accepted_friendship: Friendship
    ):
        """Test successfully removing an accepted friendship"""
        # Act
        await FriendshipService.remove_friendship(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id
        )
        
        # Assert - verify friendship is deleted
        from sqlalchemy import select
        result = await db_session.execute(
            select(Friendship).where(Friendship.id_friendship == accepted_friendship.id_friendship)
        )
        deleted_friendship = result.scalar_one_or_none()
        assert deleted_friendship is None
    
    async def test_remove_friendship_reverse_direction(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test removing a friendship from the reverse direction"""
        # Act
        await FriendshipService.remove_friendship(
            session=db_session,
            user_id=test_user_2.id,
            friend_id=test_user_1.id
        )
        
        # Assert - verify friendship is deleted
        from sqlalchemy import select
        result = await db_session.execute(
            select(Friendship).where(Friendship.id_friendship == pending_friendship.id_friendship)
        )
        deleted_friendship = result.scalar_one_or_none()
        assert deleted_friendship is None
    
    async def test_remove_friendship_nonexistent_friend(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test removing a friendship with a non-existent friend"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.remove_friendship(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=99999
            )
        
        assert exc_info.value.message == "User not found"
    
    async def test_remove_friendship_inactive_friend(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        inactive_user: RegisteredUser
    ):
        """Test removing a friendship with an inactive friend"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.remove_friendship(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=inactive_user.id
            )
        
        assert exc_info.value.message == "User not found"
    
    async def test_remove_friendship_not_found(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test removing a friendship that doesn't exist"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await FriendshipService.remove_friendship(
                session=db_session,
                user_id=test_user_2.id,
                friend_id=test_user_3.id
            )
        
        assert exc_info.value.message == "Friendship not found"


@pytest.mark.unit
class TestGetUserFriendships:
    """Test cases for get_user_friendships method"""
    
    async def test_get_user_friendships_empty(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting friendships when user has none"""
        # Create user without friendships
        user = RegisteredUser(
            email="newuser@test.com",
            hashed_password="hashed_password",
            nickname="NewUser",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Act
        friendships = await FriendshipService.get_user_friendships(
            session=db_session,
            user_id=user.id
        )
        
        # Assert
        assert friendships == []
    
    async def test_get_user_friendships_as_requester(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test getting friendships where user is the requester"""
        # Act
        friendships = await FriendshipService.get_user_friendships(
            session=db_session,
            user_id=test_user_1.id
        )
        
        # Assert
        assert len(friendships) == 1
        friendship = friendships[0]
        assert friendship.friend_user_id == test_user_2.id
        assert friendship.friend_nickname == test_user_2.nickname
        assert friendship.status == "pending"
        assert friendship.is_requester is True
    
    async def test_get_user_friendships_as_recipient(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        pending_friendship: Friendship
    ):
        """Test getting friendships where user is the recipient"""
        # Act
        friendships = await FriendshipService.get_user_friendships(
            session=db_session,
            user_id=test_user_2.id
        )
        
        # Assert
        assert len(friendships) == 1
        friendship = friendships[0]
        assert friendship.friend_user_id == test_user_1.id
        assert friendship.friend_nickname == test_user_1.nickname
        assert friendship.status == "pending"
        assert friendship.is_requester is False
    
    async def test_get_user_friendships_multiple(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser,
        pending_friendship: Friendship,
        accepted_friendship: Friendship
    ):
        """Test getting multiple friendships for a user"""
        # Act
        friendships = await FriendshipService.get_user_friendships(
            session=db_session,
            user_id=test_user_1.id
        )
        
        # Assert
        assert len(friendships) == 2
        friend_ids = {f.friend_user_id for f in friendships}
        assert friend_ids == {test_user_2.id, test_user_3.id}
    
    async def test_get_user_friendships_filter_pending(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser,
        pending_friendship: Friendship,
        accepted_friendship: Friendship
    ):
        """Test getting friendships with pending status filter"""
        # Act
        friendships = await FriendshipService.get_user_friendships(
            session=db_session,
            user_id=test_user_1.id,
            status_filter="pending"
        )
        
        # Assert
        assert len(friendships) == 1
        assert friendships[0].friend_user_id == test_user_2.id
        assert friendships[0].status == "pending"
    
    async def test_get_user_friendships_filter_accepted(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser,
        pending_friendship: Friendship,
        accepted_friendship: Friendship
    ):
        """Test getting friendships with accepted status filter"""
        # Act
        friendships = await FriendshipService.get_user_friendships(
            session=db_session,
            user_id=test_user_1.id,
            status_filter="accepted"
        )
        
        # Assert
        assert len(friendships) == 1
        assert friendships[0].friend_user_id == test_user_3.id
        assert friendships[0].status == "accepted"


@pytest.mark.unit
class TestSearchUsers:
    """Test cases for search_users method"""
    
    async def test_search_users_success(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test successfully searching for users"""
        # Act
        users, total = await FriendshipService.search_users(
            session=db_session,
            search_query="TestUser",
            current_user_id=test_user_1.id
        )
        
        # Assert
        assert len(users) == 2  # Excludes current user
        assert total == 2
        user_ids = {u.user_id for u in users}
        assert test_user_2.id in user_ids
        assert test_user_3.id in user_ids
        assert test_user_1.id not in user_ids
    
    async def test_search_users_case_insensitive(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test case-insensitive search"""
        # Act
        users, total = await FriendshipService.search_users(
            session=db_session,
            search_query="testuser",  # lowercase
            current_user_id=test_user_1.id
        )
        
        # Assert
        assert len(users) >= 1
        assert total >= 1
    
    async def test_search_users_partial_match(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test partial nickname matching"""
        # Act
        users, total = await FriendshipService.search_users(
            session=db_session,
            search_query="User2",
            current_user_id=test_user_1.id
        )
        
        # Assert
        assert len(users) == 1
        assert users[0].user_id == test_user_2.id
        assert users[0].nickname == test_user_2.nickname
    
    async def test_search_users_no_results(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test search with no matching results"""
        # Act
        users, total = await FriendshipService.search_users(
            session=db_session,
            search_query="NonExistentUser",
            current_user_id=test_user_1.id
        )
        
        # Assert
        assert len(users) == 0
        assert total == 0
    
    async def test_search_users_excludes_inactive(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        inactive_user: RegisteredUser
    ):
        """Test that inactive users are excluded from search"""
        # Act
        users, total = await FriendshipService.search_users(
            session=db_session,
            search_query="User",
            current_user_id=test_user_1.id
        )
        
        # Assert
        user_ids = {u.user_id for u in users}
        assert inactive_user.id not in user_ids
    
    async def test_search_users_query_too_short(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test search with query shorter than 3 characters"""
        # Act & Assert
        with pytest.raises(BadRequestException) as exc_info:
            await FriendshipService.search_users(
                session=db_session,
                search_query="ab",
                current_user_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Search query must be at least 3 characters"
        assert exc_info.value.details["query_length"] == 2
        assert exc_info.value.details["minimum_length"] == 3
    
    async def test_search_users_pagination(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test pagination in user search"""
        # Create additional users
        for i in range(5):
            user = RegisteredUser(
                email=f"searchuser{i}@test.com",
                hashed_password="hashed_password",
                nickname=f"SearchUser{i}",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
            db_session.add(user)
        await db_session.commit()
        
        # Act - Page 1
        users_page1, total = await FriendshipService.search_users(
            session=db_session,
            search_query="SearchUser",
            current_user_id=test_user_1.id,
            page=1,
            page_size=3
        )
        
        # Act - Page 2
        users_page2, _ = await FriendshipService.search_users(
            session=db_session,
            search_query="SearchUser",
            current_user_id=test_user_1.id,
            page=2,
            page_size=3
        )
        
        # Assert
        assert total == 5
        assert len(users_page1) == 3
        assert len(users_page2) == 2
        
        # Verify no overlap
        page1_ids = {u.user_id for u in users_page1}
        page2_ids = {u.user_id for u in users_page2}
        assert page1_ids.isdisjoint(page2_ids)
    
    async def test_search_users_with_whitespace(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test search query with leading/trailing whitespace"""
        # Act
        users, total = await FriendshipService.search_users(
            session=db_session,
            search_query="  TestUser2  ",
            current_user_id=test_user_1.id
        )
        
        # Assert
        assert len(users) == 1
        assert users[0].user_id == test_user_2.id
