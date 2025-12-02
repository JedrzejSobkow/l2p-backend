# app/api/socketio/chat_namespace.py

import socketio
from infrastructure.socketio_manager import sio, manager, AuthNamespace
from infrastructure.postgres_connection import get_db_session
from services.chat_service import ChatService
from models.registered_user import RegisteredUser
from schemas.chat_schema import (
    SendChatMessageEvent, 
    TypingIndicatorEvent,
    ChatMessageResponse,
    ConversationUpdatedResponse,
    UserTypingResponse,
    SocketErrorResponse
)
from services.user_status_service import UserStatusService
from schemas.user_status_schema import UserStatus, FriendStatusListResponse
from pydantic import ValidationError
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class ChatNamespace(AuthNamespace):
    """Socket.IO namespace for chat functionality"""

    async def handle_connect(self, sid, environ, user: RegisteredUser):
        """Namespace-specific connect hook called after successful auth.

        `user` is the authenticated RegisteredUser returned by
        `authenticate_user`.
        """
        logger.info(f"Client authenticated and connected to /chat: {sid} (User: {user.id}, Email: {user.email})")
        
        # Notify friends that user is online
        # Check if user is in lobby
        from services.lobby_service import LobbyService
        from infrastructure.redis_connection import redis_connection
        
        status = UserStatus.ONLINE
        lobby_data = None
        
        try:
            redis = redis_connection.get_client()
            user_lobby_key = LobbyService._user_lobby_key(user.id)
            lobby_code_bytes = await redis.get(user_lobby_key)
            if lobby_code_bytes:
                lobby_code = lobby_code_bytes.decode() if isinstance(lobby_code_bytes, bytes) else lobby_code_bytes
                lobby = await LobbyService.get_lobby(redis, lobby_code)
                if lobby:
                    status = UserStatus.IN_LOBBY
                    lobby_data = lobby
        except Exception as e:
            logger.error(f"Error checking lobby status in handle_connect: {e}")

        if status == UserStatus.IN_LOBBY and lobby_data:
             await UserStatusService.notify_friends(
                user.id, 
                status, 
                lobby_code=lobby_data["lobby_code"],
                lobby_filled_slots=lobby_data["current_players"],
                lobby_max_slots=lobby_data["max_players"]
            )
        else:
            await UserStatusService.notify_friends(user.id, UserStatus.ONLINE)
        
        # Send initial friend statuses to the connecting user
        initial_statuses = await UserStatusService.get_initial_friend_statuses(user.id)
        response = FriendStatusListResponse(statuses=initial_statuses)
        await self.emit('initial_friend_statuses', response.model_dump(mode='json'), room=sid)

    async def handle_disconnect(self, sid):
        """Handle disconnection"""
        user_id = manager.get_user_id(sid)
        if user_id:
            # Check if this is the last connection for this user in this namespace
            sessions = manager.get_user_sessions(namespace='/chat', user_id=user_id)
            if len(sessions) <= 1:
                # User is going offline
                await UserStatusService.notify_friends(user_id, UserStatus.OFFLINE)

        
    
    async def on_send_message(self, sid, data):
        """
        Handle sending a message
        User is already authenticated from connection
        
        For images, use the presigned upload flow:
        1. get_upload_url (HTTP) - Get presigned URL
        2. Upload directly to MinIO
        3. send_message (this event) - Save message with image_path
        """
        try:
            # Validate input data using DTO
            try:
                message_dto = SendChatMessageEvent(**data)
            except ValidationError as e:
                error_response = SocketErrorResponse(
                    message='Invalid data format',
                    errors=e.errors()
                )
                await self.emit('error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = SocketErrorResponse(message='Not authenticated. Please reconnect.')
                await self.emit('error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Either content or image_path must be provided
            if not message_dto.content and not message_dto.image_path:
                error_response = SocketErrorResponse(message='Either content or image_path is required')
                await self.emit('error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get database session
            async for session in get_db_session():
                try:
                    # Process message sending 
                    result = await ChatService.process_send_message(
                        session=session,
                        user_id=user_id,
                        friend_user_id=message_dto.friend_user_id,
                        content=message_dto.content,
                        image_path=message_dto.image_path
                    )
                    
                    message_data = result['message']
                    sender = result['sender']
                    recipient = result['recipient']
                    
                    # Build message event response
                    message_response = ChatMessageResponse(
                        id=message_data['id'],
                        sender_id=message_data['sender_id'],
                        sender_nickname=message_data['sender_nickname'],
                        content=message_data['content'],
                        image_url=message_data['image_url'],
                        created_at=message_data['created_at'],
                        is_mine=True,
                        temp_id=message_dto.temp_id  # Echo back temp_id for client matching
                    )
                    
                    # Send to sender (confirmation)
                    await self.emit('message', message_response.model_dump(mode='json'), room=sid)
                    
                    # Send to recipient if online
                    friend_sid = manager.get_sid(recipient['identifier'], namespace='/chat')
                    if friend_sid:
                        # Update is_mine for recipient
                        message_response.is_mine = False
                        await self.emit('message', message_response.model_dump(mode='json'), room=friend_sid)
                        logger.info(f"Message sent to online user {recipient['identifier']}")
                        
                        # Emit conversation update to recipient
                        conversation_update = ConversationUpdatedResponse(
                            friendship_id=message_data['friendship_id'],
                            friend_id=sender['id'],
                            friend_nickname=sender['nickname'],
                            last_message_time=message_data['created_at'],
                            last_message_content=message_dto.content,
                            last_message_is_mine=False
                        )
                        await self.emit('conversation_updated', conversation_update.model_dump(mode='json'), room=friend_sid)
                    else:
                        logger.info(f"User {recipient['identifier']} is offline, message saved to database")
                    
                    # Emit conversation update to sender
                    conversation_update = ConversationUpdatedResponse(
                        friendship_id=message_data['friendship_id'],
                        friend_id=recipient['identifier'],
                        friend_nickname=recipient['nickname'],
                        last_message_time=message_data['created_at'],
                        last_message_content=message_dto.content,
                        last_message_is_mine=True
                    )
                    await self.emit('conversation_updated', conversation_update.model_dump(mode='json'), room=sid)
                    
                except HTTPException as e:
                    # Handle HTTP exceptions from service layer
                    logger.error(f"HTTP error sending message: {e.status_code} - {e.detail}")
                    error_response = SocketErrorResponse(message=e.detail)
                    await self.emit('error', error_response.model_dump(mode='json'), room=sid)
                except Exception as e:
                    logger.error(f"Error sending message: {str(e)}")
                    error_response = SocketErrorResponse(message=str(e))
                    await self.emit('error', error_response.model_dump(mode='json'), room=sid)
                
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            error_response = SocketErrorResponse(message=f'Failed to send message: {str(e)}')
            await self.emit('error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_typing(self, sid, data):
        """
        Notify friend that user is typing
        """
        try:
            # Validate input data using DTO
            try:
                typing_dto = TypingIndicatorEvent(**data)
            except ValidationError as e:
                # Silently ignore invalid typing events (they're ephemeral)
                logger.debug(f"Invalid typing indicator data: {e}")
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                return
            
            user_nickname = manager.get_nickname(user_id)
            if not user_nickname:
                return
            
            # Check if friend is online and get their session
            friend_identifier = "user:{}".format(typing_dto.friend_user_id)
            friend_sid = manager.get_sid(friend_identifier, namespace='/chat')
            if not friend_sid:
                # Friend is not online, no need to send typing indicator
                return
            
            # Build and send typing indicator to friend
            typing_response = UserTypingResponse(
                user_id=user_id,
                nickname=user_nickname
            )
            await self.emit('user_typing', typing_response.model_dump(mode='json'), room=friend_sid)
                
        except Exception as e:
            logger.error(f"Error in typing: {str(e)}")


# Register the namespace
sio.register_namespace(ChatNamespace('/chat'))
