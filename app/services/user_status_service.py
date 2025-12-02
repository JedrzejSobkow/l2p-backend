import logging
from typing import Dict, List, Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.socketio_manager import manager, sio
from infrastructure.postgres_connection import postgres_connection
from infrastructure.redis_connection import redis_connection
from models.friendship import Friendship
from schemas.user_status_schema import UserStatus, UserStatusUpdateEvent, FriendStatusListResponse, FriendRequestEvent, FriendRequestAcceptedEvent, FriendRemovedEvent
from services.lobby_service import LobbyService

logger = logging.getLogger(__name__)

class UserStatusService:
    # In-memory tracking of users currently in a game.
    # Maps user_id -> game_name
    _in_game_users: Dict[int, str] = {}

    @classmethod
    async def notify_friendship_ended(cls, user_id_1: int, user_id_2: int):
        """
        Notify both users that their friendship has ended.
        """
        try:
            # Notify user 1
            sessions_1 = manager.get_user_sessions(namespace='/chat', user_id=user_id_1)
            if sessions_1:
                event = FriendRemovedEvent(friend_id=user_id_2)
                event_data = event.model_dump(mode='json')
                for sid in sessions_1:
                    await sio.emit('friend_removed', event_data, room=sid, namespace='/chat')
            
            # Notify user 2
            sessions_2 = manager.get_user_sessions(namespace='/chat', user_id=user_id_2)
            if sessions_2:
                event = FriendRemovedEvent(friend_id=user_id_1)
                event_data = event.model_dump(mode='json')
                for sid in sessions_2:
                    await sio.emit('friend_removed', event_data, room=sid, namespace='/chat')
                    
            logger.info(f"Notified users {user_id_1} and {user_id_2} of friendship end")
        except Exception as e:
            logger.error(f"Error notifying friendship end: {e}")

    @classmethod
    async def notify_friend_request(cls, sender_id: int, recipient_id: int, sender_nickname: str, sender_pfp_path: Optional[str] = None):
        """
        Notify a user that they received a friend request.
        """
        try:
            # Check if recipient is online in chat namespace
            recipient_sessions = manager.get_user_sessions(namespace='/chat', user_id=recipient_id)
            if recipient_sessions:
                event = FriendRequestEvent(
                    sender_id=sender_id,
                    sender_nickname=sender_nickname,
                    sender_pfp_path=sender_pfp_path
                )
                event_data = event.model_dump(mode='json')
                
                for sid in recipient_sessions:
                    await sio.emit('friend_request_received', event_data, room=sid, namespace='/chat')
                logger.info(f"Notified user {recipient_id} of friend request from {sender_id}")
        except Exception as e:
            logger.error(f"Error notifying friend request to user {recipient_id}: {e}")

    @classmethod
    async def notify_friend_request_accepted(cls, requester_id: int, accepter_id: int, accepter_nickname: str, accepter_pfp_path: Optional[str] = None):
        """
        Notify the original requester that their friend request was accepted.
        """
        try:
            # Check if requester is online in chat namespace
            requester_sessions = manager.get_user_sessions(namespace='/chat', user_id=requester_id)
            if requester_sessions:
                event = FriendRequestAcceptedEvent(
                    accepter_id=accepter_id,
                    accepter_nickname=accepter_nickname,
                    accepter_pfp_path=accepter_pfp_path
                )
                event_data = event.model_dump(mode='json')
                
                for sid in requester_sessions:
                    await sio.emit('friend_request_accepted', event_data, room=sid, namespace='/chat')
                logger.info(f"Notified user {requester_id} that {accepter_id} accepted their friend request")
        except Exception as e:
            logger.error(f"Error notifying friend request acceptance to user {requester_id}: {e}")


    @classmethod
    async def get_friends_ids(cls, user_id: int, session: AsyncSession) -> List[int]:
        """
        Get list of user IDs that are friends with the given user.
        """
        stmt = select(Friendship).where(
            (
                (Friendship.user_id_1 == user_id) | 
                (Friendship.user_id_2 == user_id)
            ) & 
            (Friendship.status == 'accepted')
        )
        result = await session.execute(stmt)
        friendships = result.scalars().all()
        
        friend_ids = []
        for f in friendships:
            if f.user_id_1 == user_id:
                friend_ids.append(f.user_id_2)
            else:
                friend_ids.append(f.user_id_1)
        
        return friend_ids

    @classmethod
    async def notify_friends(cls, user_id: int, status: UserStatus, game_name: Optional[str] = None, lobby_code: Optional[str] = None, lobby_filled_slots: Optional[int] = None, lobby_max_slots: Optional[int] = None):
        """
        Notify all online friends of a user's status change.
        """
        # Update in-memory state
        if status == UserStatus.IN_GAME and game_name:
            cls._in_game_users[user_id] = game_name
        else:
            # If going ONLINE or OFFLINE, remove from in-game tracking
            if user_id in cls._in_game_users:
                del cls._in_game_users[user_id]

        # Create event payload
        event = UserStatusUpdateEvent(
            user_id=user_id,
            status=status,
            game_name=game_name,
            lobby_code=lobby_code,
            lobby_filled_slots=lobby_filled_slots,
            lobby_max_slots=lobby_max_slots
        )
        event_data = event.model_dump(mode='json')

        try:
            async with postgres_connection.session_factory() as session:
                friend_ids = await cls.get_friends_ids(user_id, session)
                
            for friend_id in friend_ids:
                # Check if friend is online in chat namespace
                friend_sessions = manager.get_user_sessions(namespace='/chat', user_id=friend_id)
                if friend_sessions:
                    for sid in friend_sessions:
                        await sio.emit('friend_status_update', event_data, room=sid, namespace='/chat')
                    # logger.debug(f"Notified friend {friend_id} of user {user_id} status {status}")
                    
        except Exception as e:
            logger.error(f"Error notifying friends for user {user_id}: {e}")

    @classmethod
    async def get_initial_friend_statuses(cls, user_id: int) -> List[UserStatusUpdateEvent]:
        """
        Get the current status of all friends for a user.
        """
        statuses = []
        try:
            async with postgres_connection.session_factory() as session:
                friend_ids = await cls.get_friends_ids(user_id, session)
            
            # Get redis client
            try:
                redis = redis_connection.get_client()
            except RuntimeError:
                redis = None
                logger.warning("Redis client not connected in get_initial_friend_statuses")

            for friend_id in friend_ids:
                status = UserStatus.OFFLINE
                game_name = None
                lobby_code = None
                lobby_filled_slots = None
                lobby_max_slots = None
                
                # Check if online first (highest priority for OFFLINE status)
                if not manager.is_user_online(friend_id):
                    status = UserStatus.OFFLINE
                else:
                    # User is online, check if in game or lobby
                    status = UserStatus.ONLINE
                    
                    # Check if in game
                    if friend_id in cls._in_game_users:
                        status = UserStatus.IN_GAME
                        game_name = cls._in_game_users[friend_id]
                    else:
                        # Check if in lobby
                        if redis:
                            user_lobby_key = LobbyService._user_lobby_key(friend_id)
                            lobby_code_bytes = await redis.get(user_lobby_key)
                            if lobby_code_bytes:
                                lobby_code = lobby_code_bytes.decode() if isinstance(lobby_code_bytes, bytes) else lobby_code_bytes
                                lobby = await LobbyService.get_lobby(redis, lobby_code)
                                if lobby:
                                    status = UserStatus.IN_LOBBY
                                    lobby_filled_slots = lobby["current_players"]
                                    lobby_max_slots = lobby["max_players"]
                
                statuses.append(UserStatusUpdateEvent(
                    user_id=friend_id,
                    status=status,
                    game_name=game_name,
                    lobby_code=lobby_code,
                    lobby_filled_slots=lobby_filled_slots,
                    lobby_max_slots=lobby_max_slots
                ))
                
        except Exception as e:
            logger.error(f"Error getting initial statuses for user {user_id}: {e}")
            
        return statuses
