# app/api/socketio/chat_namespace.py

import socketio
from infrastructure.socketio_manager import sio, manager, AuthNamespace
from infrastructure.postgres_connection import get_db_session
from services.chat_service import ChatService
from sqlalchemy import select
from models.registered_user import RegisteredUser
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
        # Emit a richer connected payload (includes nickname)
        await self.emit('connected', {
            'message': 'Connected to chat server',
            'user_id': user.id,
            'email': user.email,
            'nickname': user.nickname
        }, room=sid)
    
    async def on_send_message(self, sid, data):
        """
        Handle sending a message
        User is already authenticated from connection
        
        For images, use the presigned upload flow:
        1. get_upload_url (HTTP) - Get presigned URL
        2. Upload directly to MinIO
        3. send_message (this event) - Save message with image_path
        
        Expected data:
        {
            "friend_user_id": 123,  // User ID of the friend
            "content": "Hello!",  // Optional if image_path is provided
            "image_path": "bucket/path/to/image.jpg"  // Optional, from get_upload_url
        }
        """
        try:
            user_id = manager.get_user_id(sid)
            if not user_id:
                await self.emit('error', {'message': 'Not authenticated. Please reconnect.'}, room=sid)
                return
            
            friend_user_id = data.get('friend_user_id')
            content = data.get('content')
            image_path = data.get('image_path')
            
            if not friend_user_id:
                await self.emit('error', {'message': 'friend_user_id is required'}, room=sid)
                return
            
            # Either content or image_path must be provided
            if not content and not image_path:
                await self.emit('error', {'message': 'Either content or image_path is required'}, room=sid)
                return
            
            # Get database session
            async for session in get_db_session():
                try:
                    # Get friendship
                    friendship, current_user, friend = await ChatService.get_friendship_by_id(
                        session=session,
                        user_id=user_id,
                        friend_id=friend_user_id
                    )
                    
                    # Validate image_path if provided
                    if image_path:
                        ChatService.validate_image_path(image_path, friendship.id_friendship)
                    
                    # Save message to database
                    message = await ChatService.save_message(
                        session=session,
                        friendship_id=friendship.id_friendship,
                        sender_id=user_id,
                        content=content,
                        image_path=image_path
                    )
                    
                    # Get image URL if image_path is provided
                    image_url = None
                    if image_path:
                        image_url = ChatService._get_image_url(image_path)
                    
                    # Prepare message data
                    message_data = {
                        'id': message.id_message,
                        'sender_id': user_id,
                        'sender_nickname': current_user.nickname,
                        'content': content,
                        'image_url': image_url,
                        'created_at': message.created_at.isoformat(),
                        'friendship_id': friendship.id_friendship
                    }
                    
                    # Send to sender (confirmation)
                    await self.emit('message', {
                        **message_data,
                        'is_mine': True
                    }, room=sid)
                    
                    # Send to recipient if online
                    friend_sid = manager.get_sid(friend.id)
                    if friend_sid:
                        await self.emit('message', {
                            **message_data,
                            'is_mine': False
                        }, room=friend_sid)
                        logger.info(f"Message sent to online user {friend.id}")
                        
                        # Emit lightweight conversation update to friend
                        await self.emit('conversation_updated', {
                            'friendship_id': friendship.id_friendship,
                            'friend_id': user_id,
                            'friend_nickname': current_user.nickname,
                            'last_message_time': message.created_at.isoformat(),
                            'last_message_content': content,
                            'last_message_is_mine': False
                        }, room=friend_sid)
                    else:
                        logger.info(f"User {friend.id} is offline, message saved to database")
                    
                    # Emit lightweight conversation update to sender
                    await self.emit('conversation_updated', {
                        'friendship_id': friendship.id_friendship,
                        'friend_id': friend.id,
                        'friend_nickname': friend.nickname,
                        'last_message_time': message.created_at.isoformat(),
                        'last_message_content': content,
                        'last_message_is_mine': True
                    }, room=sid)
                    
                except Exception as e:
                    logger.error(f"Error sending message: {str(e)}")
                    await self.emit('error', {'message': str(e)}, room=sid)
                
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            await self.emit('error', {'message': f'Failed to send message: {str(e)}'}, room=sid)
    
    async def on_typing(self, sid, data):
        """
        Notify friend that user is typing
        
        Uses cached data from the connection manager for optimal performance.
        No database queries needed - typing indicators are ephemeral and
        don't require strict validation.
        
        Expected data:
        {
            "friend_user_id": 123  // User ID of the friend to notify
        }
        """
        try:
            user_id = manager.get_user_id(sid)
            if not user_id:
                return
            
            user_nickname = manager.get_nickname(user_id)
            if not user_nickname:
                return
            
            friend_user_id = data.get('friend_user_id')
            if not friend_user_id:
                return
            
            # Check if friend is online and get their session
            friend_sid = manager.get_sid(friend_user_id)
            if not friend_sid:
                # Friend is not online, no need to send typing indicator
                return
            
            # Send typing indicator to friend
            await self.emit('user_typing', {
                'user_id': user_id,
                'nickname': user_nickname
            }, room=friend_sid)
                
        except Exception as e:
            logger.error(f"Error in typing: {str(e)}")


# Register the namespace
sio.register_namespace(ChatNamespace('/chat'))
