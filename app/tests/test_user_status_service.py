"""
Comprehensive unit tests for UserStatusService

Tests cover:
- Friend status notifications
- Friendship ended notifications
- Friend request notifications
- Friend request acceptance notifications
- Getting friend IDs
- Getting initial friend statuses
- Online/offline status tracking
- In-game status tracking
- In-lobby status tracking
- Status updates to multiple friends
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.user_status_service import UserStatusService
from models.friendship import Friendship
from models.registered_user import RegisteredUser
from schemas.user_status_schema import UserStatus, UserStatusUpdateEvent, FriendStatusListResponse


@pytest.mark.unit
class TestGetFriendsIds:
    """Test cases for get_friends_ids method"""
    
    async def test_get_friends_ids_empty(self, db_session: AsyncSession, test_user_1: RegisteredUser):
        """Test getting friend IDs when user has no friends"""
        friend_ids = await UserStatusService.get_friends_ids(test_user_1.id, db_session)
        
        assert friend_ids == []
    
    async def test_get_friends_ids_single_friend(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test getting friend IDs with one friend"""
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        friend_ids = await UserStatusService.get_friends_ids(test_user_1.id, db_session)
        
        assert len(friend_ids) == 1
        assert test_user_2.id in friend_ids
    
    async def test_get_friends_ids_multiple_friends(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting friend IDs with multiple friends"""
        # Create friendships
        friendship1 = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        friendship2 = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_3.id,
            status="accepted"
        )
        db_session.add_all([friendship1, friendship2])
        await db_session.commit()
        
        friend_ids = await UserStatusService.get_friends_ids(test_user_1.id, db_session)
        
        assert len(friend_ids) == 2
        assert test_user_2.id in friend_ids
        assert test_user_3.id in friend_ids
    
    async def test_get_friends_ids_excludes_pending(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test that pending friendships are excluded"""
        # Create pending friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="pending"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        friend_ids = await UserStatusService.get_friends_ids(test_user_1.id, db_session)
        
        assert len(friend_ids) == 0
    
    async def test_get_friends_ids_bidirectional(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test friendship works in both directions"""
        # Create friendship with user_2 as first user
        friendship = Friendship(
            user_id_1=test_user_2.id,
            user_id_2=test_user_1.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Should work when querying from either side
        friend_ids_1 = await UserStatusService.get_friends_ids(test_user_1.id, db_session)
        friend_ids_2 = await UserStatusService.get_friends_ids(test_user_2.id, db_session)
        
        assert test_user_2.id in friend_ids_1
        assert test_user_1.id in friend_ids_2


@pytest.mark.unit
class TestNotifyFriends:
    """Test cases for notify_friends method"""
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_notify_friends_online_status(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test notifying friends of online status"""
        # Setup mocks
        async def async_context_manager():
            return db_session
        
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Mock friend is online
        mock_manager.get_user_sessions.return_value = ["sid123"]
        mock_sio.emit = AsyncMock()
        
        # Notify friends
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.ONLINE
        )
        
        # Verify emit was called
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        assert call_args[0][0] == 'friend_status_update'
        assert call_args[1]['namespace'] == '/chat'
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_notify_friends_in_game_status(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test notifying friends of in-game status"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Mock friend is online
        mock_manager.get_user_sessions.return_value = ["sid123"]
        mock_sio.emit = AsyncMock()
        
        # Notify friends
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.IN_GAME,
            game_name="checkers"
        )
        
        # Verify in-game tracking
        assert test_user_1.id in UserStatusService._in_game_users
        assert UserStatusService._in_game_users[test_user_1.id] == "checkers"
        
        # Verify emit was called
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        event_data = call_args[0][1]
        assert event_data['status'] == UserStatus.IN_GAME
        assert event_data['game_name'] == "checkers"
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_notify_friends_offline_clears_in_game(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that going offline clears in-game tracking"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        mock_manager.get_user_sessions.return_value = []
        mock_sio.emit = AsyncMock()
        
        # Add to in-game tracking
        UserStatusService._in_game_users[test_user_1.id] = "checkers"
        
        # Go offline
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.OFFLINE
        )
        
        # Verify removed from in-game tracking
        assert test_user_1.id not in UserStatusService._in_game_users
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_notify_friends_in_lobby_with_details(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test notifying friends of in-lobby status with lobby details"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        mock_manager.get_user_sessions.return_value = ["sid456"]
        mock_sio.emit = AsyncMock()
        
        # Notify friends
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.IN_LOBBY,
            lobby_code="ABC123",
            lobby_filled_slots=2,
            lobby_max_slots=4
        )
        
        # Verify emit was called with lobby details
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        event_data = call_args[0][1]
        assert event_data['status'] == UserStatus.IN_LOBBY
        assert event_data['lobby_code'] == "ABC123"
        assert event_data['lobby_filled_slots'] == 2
        assert event_data['lobby_max_slots'] == 4
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_notify_friends_skips_offline_friends(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test that offline friends don't receive notifications"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Friend is offline (no sessions)
        mock_manager.get_user_sessions.return_value = []
        mock_sio.emit = AsyncMock()
        
        # Notify friends
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.ONLINE
        )
        
        # Emit should not be called
        mock_sio.emit.assert_not_called()


@pytest.mark.unit
class TestNotifyFriendshipEnded:
    """Test cases for notify_friendship_ended method"""
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friendship_ended_both_online(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notifying both users of friendship end when both online"""
        mock_manager.get_user_sessions.return_value = ["sid1"]
        mock_sio.emit = AsyncMock()
        
        await UserStatusService.notify_friendship_ended(
            user_id_1=100,
            user_id_2=200
        )
        
        # Should emit twice (once to each user)
        assert mock_sio.emit.call_count == 2
        
        # Check first call (to user 1)
        first_call = mock_sio.emit.call_args_list[0]
        assert first_call[0][0] == 'friend_removed'
        assert first_call[0][1]['friend_id'] == 200
        
        # Check second call (to user 2)
        second_call = mock_sio.emit.call_args_list[1]
        assert second_call[0][0] == 'friend_removed'
        assert second_call[0][1]['friend_id'] == 100
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friendship_ended_one_offline(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notifying friendship end when one user offline"""
        # User 1 online, user 2 offline
        def get_sessions_side_effect(namespace, user_id):
            if user_id == 100:
                return ["sid1"]
            return []
        
        mock_manager.get_user_sessions.side_effect = get_sessions_side_effect
        mock_sio.emit = AsyncMock()
        
        await UserStatusService.notify_friendship_ended(
            user_id_1=100,
            user_id_2=200
        )
        
        # Should only emit once (to online user)
        assert mock_sio.emit.call_count == 1


@pytest.mark.unit
class TestNotifyFriendRequest:
    """Test cases for notify_friend_request method"""
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friend_request_recipient_online(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notifying recipient of friend request when online"""
        mock_manager.get_user_sessions.return_value = ["sid123"]
        mock_sio.emit = AsyncMock()
        
        await UserStatusService.notify_friend_request(
            sender_id=100,
            recipient_id=200,
            sender_nickname="TestSender",
            sender_pfp_path="/path/to/avatar.png"
        )
        
        # Verify emit was called
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        assert call_args[0][0] == 'friend_request_received'
        event_data = call_args[0][1]
        assert event_data['sender_id'] == 100
        assert event_data['sender_nickname'] == "TestSender"
        assert event_data['sender_pfp_path'] == "/path/to/avatar.png"
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friend_request_recipient_offline(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notifying recipient when offline (should not emit)"""
        mock_manager.get_user_sessions.return_value = []
        mock_sio.emit = AsyncMock()
        
        await UserStatusService.notify_friend_request(
            sender_id=100,
            recipient_id=200,
            sender_nickname="TestSender"
        )
        
        # Should not emit when offline
        mock_sio.emit.assert_not_called()


@pytest.mark.unit
class TestNotifyFriendRequestAccepted:
    """Test cases for notify_friend_request_accepted method"""
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friend_request_accepted_requester_online(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notifying requester of acceptance when online"""
        mock_manager.get_user_sessions.return_value = ["sid456"]
        mock_sio.emit = AsyncMock()
        
        await UserStatusService.notify_friend_request_accepted(
            requester_id=100,
            accepter_id=200,
            accepter_nickname="TestAccepter",
            accepter_pfp_path="/path/to/accepter.png"
        )
        
        # Verify emit was called
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        assert call_args[0][0] == 'friend_request_accepted'
        event_data = call_args[0][1]
        assert event_data['accepter_id'] == 200
        assert event_data['accepter_nickname'] == "TestAccepter"
        assert event_data['accepter_pfp_path'] == "/path/to/accepter.png"
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friend_request_accepted_requester_offline(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notifying requester when offline (should not emit)"""
        mock_manager.get_user_sessions.return_value = []
        mock_sio.emit = AsyncMock()
        
        await UserStatusService.notify_friend_request_accepted(
            requester_id=100,
            accepter_id=200,
            accepter_nickname="TestAccepter"
        )
        
        # Should not emit when offline
        mock_sio.emit.assert_not_called()


@pytest.mark.unit
class TestGetInitialFriendStatuses:
    """Test cases for get_initial_friend_statuses method"""
    
    @patch('services.user_status_service.redis_connection')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_get_initial_statuses_all_offline(
        self,
        mock_postgres,
        mock_manager,
        mock_redis,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting initial statuses when all friends are offline"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendships
        friendship1 = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        friendship2 = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_3.id,
            status="accepted"
        )
        db_session.add_all([friendship1, friendship2])
        await db_session.commit()
        
        # All friends offline
        mock_manager.is_user_online.return_value = False
        mock_redis.get_client.return_value = None
        
        statuses = await UserStatusService.get_initial_friend_statuses(test_user_1.id)
        
        assert len(statuses) == 2
        for status in statuses:
            assert status.status == UserStatus.OFFLINE
    
    @patch('services.user_status_service.redis_connection')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_get_initial_statuses_friend_online(
        self,
        mock_postgres,
        mock_manager,
        mock_redis,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test getting initial statuses when friend is online"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Friend is online
        mock_manager.is_user_online.return_value = True
        mock_redis.get_client.return_value = None
        
        statuses = await UserStatusService.get_initial_friend_statuses(test_user_1.id)
        
        assert len(statuses) == 1
        assert statuses[0].status == UserStatus.ONLINE
    
    @patch('services.user_status_service.redis_connection')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    @patch('services.user_status_service.LobbyService')
    async def test_get_initial_statuses_friend_in_lobby(
        self,
        mock_lobby_service,
        mock_postgres,
        mock_manager,
        mock_redis,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test getting initial statuses when friend is in lobby"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Friend is online and in lobby
        mock_manager.is_user_online.return_value = True
        
        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=b"LOBBY123")
        mock_redis.get_client.return_value = mock_redis_client
        
        mock_lobby_service.get_lobby = AsyncMock(return_value={
            "current_players": 3,
            "max_players": 6
        })
        
        statuses = await UserStatusService.get_initial_friend_statuses(test_user_1.id)
        
        assert len(statuses) == 1
        assert statuses[0].status == UserStatus.IN_LOBBY
        assert statuses[0].lobby_code == "LOBBY123"
        assert statuses[0].lobby_filled_slots == 3
        assert statuses[0].lobby_max_slots == 6
    
    @patch('services.user_status_service.redis_connection')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_get_initial_statuses_friend_in_game(
        self,
        mock_postgres,
        mock_manager,
        mock_redis,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test getting initial statuses when friend is in game"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Friend is online and in game
        mock_manager.is_user_online.return_value = True
        mock_redis.get_client.return_value = None
        
        # Add friend to in-game tracking
        UserStatusService._in_game_users[test_user_2.id] = "tictactoe"
        
        statuses = await UserStatusService.get_initial_friend_statuses(test_user_1.id)
        
        assert len(statuses) == 1
        assert statuses[0].status == UserStatus.IN_GAME
        assert statuses[0].game_name == "tictactoe"
        
        # Cleanup
        del UserStatusService._in_game_users[test_user_2.id]
    
    @patch('services.user_status_service.redis_connection')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_get_initial_statuses_handles_errors(
        self,
        mock_postgres,
        mock_manager,
        mock_redis,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that get_initial_statuses handles errors gracefully"""
        # Setup mocks to raise exception
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Should not raise, should return empty list
        statuses = await UserStatusService.get_initial_friend_statuses(test_user_1.id)
        
        assert statuses == []


@pytest.mark.unit
class TestInGameTracking:
    """Test cases for in-game user tracking"""
    
    def test_in_game_users_dictionary_exists(self):
        """Test that _in_game_users dictionary exists"""
        assert hasattr(UserStatusService, '_in_game_users')
        assert isinstance(UserStatusService._in_game_users, dict)
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_in_game_tracking_adds_user(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that notifying IN_GAME adds user to tracking"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        mock_manager.get_user_sessions.return_value = []
        mock_sio.emit = AsyncMock()
        
        # Clear tracking
        UserStatusService._in_game_users.clear()
        
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.IN_GAME,
            game_name="checkers"
        )
        
        assert test_user_1.id in UserStatusService._in_game_users
        assert UserStatusService._in_game_users[test_user_1.id] == "checkers"
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_in_game_tracking_removes_user_on_online(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test that notifying ONLINE removes user from tracking"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        mock_manager.get_user_sessions.return_value = []
        mock_sio.emit = AsyncMock()
        
        # Add user to tracking
        UserStatusService._in_game_users[test_user_1.id] = "checkers"
        
        await UserStatusService.notify_friends(
            user_id=test_user_1.id,
            status=UserStatus.ONLINE
        )
        
        assert test_user_1.id not in UserStatusService._in_game_users


@pytest.mark.unit
class TestExceptionHandling:
    """Test exception handling in UserStatusService"""
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friendship_ended_handles_exception(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notify_friendship_ended handles exceptions gracefully"""
        # Make sio.emit raise an exception
        mock_sio.emit = AsyncMock(side_effect=Exception("Socket error"))
        mock_manager.get_user_sessions.return_value = ["session_1"]
        
        # Should not raise exception
        await UserStatusService.notify_friendship_ended(1, 2)
        
        # Verify it tried to get sessions
        assert mock_manager.get_user_sessions.called
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friend_request_handles_exception(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notify_friend_request handles exceptions gracefully"""
        # Make sio.emit raise an exception
        mock_sio.emit = AsyncMock(side_effect=Exception("Socket error"))
        mock_manager.get_user_sessions.return_value = ["session_1"]
        
        # Should not raise exception
        await UserStatusService.notify_friend_request(
            sender_id=1,
            recipient_id=2,
            sender_nickname="TestUser",
            sender_pfp_path="/path/to/pfp"
        )
        
        # Verify it tried to get sessions
        assert mock_manager.get_user_sessions.called
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    async def test_notify_friend_request_accepted_handles_exception(
        self,
        mock_manager,
        mock_sio
    ):
        """Test notify_friend_request_accepted handles exceptions gracefully"""
        # Make sio.emit raise an exception
        mock_sio.emit = AsyncMock(side_effect=Exception("Socket error"))
        mock_manager.get_user_sessions.return_value = ["session_1"]
        
        # Should not raise exception
        await UserStatusService.notify_friend_request_accepted(
            requester_id=1,
            accepter_id=2,
            accepter_nickname="Accepter",
            accepter_pfp_path="/path/to/pfp"
        )
        
        # Verify it tried to get sessions
        assert mock_manager.get_user_sessions.called
    
    @patch('services.user_status_service.sio')
    @patch('services.user_status_service.manager')
    @patch('services.user_status_service.postgres_connection')
    async def test_notify_friends_handles_exception(
        self,
        mock_postgres,
        mock_manager,
        mock_sio,
        db_session: AsyncSession
    ):
        """Test notify_friends handles exceptions gracefully"""
        # Setup mocks
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("Database error"))
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Should not raise exception
        await UserStatusService.notify_friends(
            user_id=1,
            status=UserStatus.ONLINE
        )
        
        # Verify it tried to get session
        assert mock_postgres.session_factory.called
    
    @patch('services.user_status_service.redis_connection')
    @patch('services.user_status_service.postgres_connection')
    async def test_get_initial_statuses_handles_redis_error(
        self,
        mock_postgres,
        mock_redis,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test get_initial_friend_statuses handles Redis connection errors"""
        # Setup postgres mock to return friend IDs
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_postgres.session_factory = MagicMock(return_value=mock_session_cm)
        
        # Create friendship in test database
        friendship = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        
        # Make redis_connection.get_client() raise RuntimeError
        mock_redis.get_client.side_effect = RuntimeError("Redis not connected")
        
        # Should not raise exception, should return offline statuses
        statuses = await UserStatusService.get_initial_friend_statuses(test_user_1.id)
        
        # Should have one status for test_user_2
        assert len(statuses) == 1
        assert statuses[0].user_id == test_user_2.id
        assert statuses[0].status == UserStatus.OFFLINE
