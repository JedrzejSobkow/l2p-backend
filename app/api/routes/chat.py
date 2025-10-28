# app/api/routes/chat.py

import socketio
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from services.chat_service import ChatService
from infrastructure.postgres_connection import postgres_connection
from config.settings import settings
from jose import jwt, JWTError
from sqlalchemy import select
from models.registered_user import RegisteredUser
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Socket.IO server with proper configuration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # TODO: Configure proper CORS for production
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)


class ConnectionManager:
    """Manages Socket.IO connections for real-time chat"""
    
    def __init__(self):
        # Maps user_id to their session_id (sid)
        self.active_connections: Dict[int, str] = {}
        # Maps session_id to user_id
        self.sid_to_user: Dict[str, int] = {}
        # Maps session_id to user email (for reference)
        self.sid_to_email: Dict[str, str] = {}
    
    def connect(self, sid: str, user_id: int, email: str):
        """Register a user's connection"""
        # If user already connected from another session, disconnect old session
        if user_id in self.active_connections:
            old_sid = self.active_connections[user_id]
            if old_sid in self.sid_to_user:
                del self.sid_to_user[old_sid]
            if old_sid in self.sid_to_email:
                del self.sid_to_email[old_sid]
        
        self.active_connections[user_id] = sid
        self.sid_to_user[sid] = user_id
        self.sid_to_email[sid] = email
        logger.info(f"User {user_id} ({email}) connected with session {sid}")
    
    def disconnect(self, sid: str):
        """Unregister a user's connection"""
        if sid in self.sid_to_user:
            user_id = self.sid_to_user[sid]
            email = self.sid_to_email.get(sid, "unknown")
            del self.active_connections[user_id]
            del self.sid_to_user[sid]
            if sid in self.sid_to_email:
                del self.sid_to_email[sid]
            logger.info(f"User {user_id} ({email}) disconnected (session {sid})")
    
    def get_user_id(self, sid: str) -> int:
        """Get user_id from session_id"""
        return self.sid_to_user.get(sid)
    
    def get_sid(self, user_id: int) -> str:
        """Get session_id from user_id"""
        return self.active_connections.get(user_id)
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if user is currently connected"""
        return user_id in self.active_connections


# Global connection manager instance
manager = ConnectionManager()


# Helper function to authenticate user from JWT token
async def authenticate_user(token: str) -> Optional[RegisteredUser]:
    """
    Authenticate user from JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        RegisteredUser if valid, None otherwise
    """
    try:
        # Decode JWT token with proper audience
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            audience="fastapi-users:auth"  # fastapi-users uses this audience
        )
        user_id = payload.get("sub")
        
        if not user_id:
            logger.warning("Token missing 'sub' claim")
            return None
        
        # Get database session and fetch user
        async with postgres_connection.session_factory() as session:
            user_query = select(RegisteredUser).where(
                RegisteredUser.id == int(user_id),
                RegisteredUser.is_active == True
            )
            result = await session.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User not found for id: {user_id}")
                return None
            
            return user
            
    except JWTError as e:
        logger.warning(f"JWT validation error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None


# Dependency to get database session
async def get_db_session():
    """Get database session"""
    if not postgres_connection.session_factory:
        raise RuntimeError("Database not connected")
    
    async with postgres_connection.session_factory() as session:
        yield session


@sio.event
async def connect(sid, environ):
    """
    Handle client connection
    Requires JWT authentication via query parameter OR cookie
    
    Client can connect with:
    1. Query parameter: io('http://server', { query: { token: 'jwt_token_here' } })
    2. Cookie: Browser will automatically send cookies (recommended for web apps)
    """
    # Extract token from query parameters OR cookies
    query_string = environ.get('QUERY_STRING', '')
    token = None
    
    # Try to get token from query string first
    if query_string:
        from urllib.parse import parse_qs
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
    
    # If no token in query, try to get from cookies
    if not token:
        cookie_header = environ.get('HTTP_COOKIE', '')
        if cookie_header:
            # Parse cookies manually
            cookies = {}
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    cookies[name] = value
            
            token = cookies.get('l2p_auth')
    
    if not token:
        logger.warning(f"Connection attempt without token from {sid}")
        await sio.emit('error', {
            'message': 'Authentication required. Please provide token in query parameter or login cookie.'
        }, room=sid)
        await sio.disconnect(sid)
        return False
    
    # Authenticate user
    user = await authenticate_user(token)
    if not user:
        logger.warning(f"Authentication failed for session {sid}")
        await sio.emit('error', {'message': 'Invalid or expired token'}, room=sid)
        await sio.disconnect(sid)
        return False
    
    # Register user connection
    manager.connect(sid, user.id, user.email)
    
    logger.info(f"Client authenticated and connected: {sid} (User: {user.id}, Email: {user.email})")
    await sio.emit('connected', {
        'message': 'Connected to chat server',
        'user_id': user.id,
        'email': user.email,
        'nickname': user.nickname
    }, room=sid)


@sio.event
async def disconnect(sid):
    """
    Handle client disconnection
    """
    logger.info(f"Client disconnected: {sid}")
    manager.disconnect(sid)


@sio.event
async def send_message(sid, data):
    """
    Handle sending a message
    User is already authenticated from connection
    
    Expected data:
    {
        "friend_nickname": "friend_username",
        "content": "Hello!"
    }
    """
    try:
        user_id = manager.get_user_id(sid)
        if not user_id:
            await sio.emit('error', {'message': 'Not authenticated. Please reconnect.'}, room=sid)
            return
        
        friend_nickname = data.get('friend_nickname')
        content = data.get('content')
        
        if not friend_nickname or not content:
            await sio.emit('error', {'message': 'friend_nickname and content are required'}, room=sid)
            return
        
        # Get database session
        async for session in get_db_session():
            try:
                # Get or create friend chat
                friend_chat, current_user, friend = await ChatService.get_or_create_friend_chat(
                    session=session,
                    user_id=user_id,
                    friend_nickname=friend_nickname
                )
                
                # Save message to database
                message = await ChatService.save_message(
                    session=session,
                    friend_chat_id=friend_chat.id_friend_chat,
                    sender_id=user_id,
                    content=content
                )
                
                # Prepare message data
                message_data = {
                    'id': message.id_message,
                    'sender_id': user_id,
                    'sender_nickname': current_user.nickname,
                    'content': content,
                    'created_at': message.created_at.isoformat(),
                    'friend_chat_id': friend_chat.id_friend_chat
                }
                
                # Send to sender (confirmation)
                await sio.emit('message', {
                    **message_data,
                    'is_mine': True
                }, room=sid)
                
                # Send to recipient if online
                friend_sid = manager.get_sid(friend.id)
                if friend_sid:
                    await sio.emit('message', {
                        **message_data,
                        'is_mine': False
                    }, room=friend_sid)
                    logger.info(f"Message sent to online user {friend.id}")
                else:
                    logger.info(f"User {friend.id} is offline, message saved to database")
                
            except Exception as e:
                logger.error(f"Error sending message: {str(e)}")
                await sio.emit('error', {'message': str(e)}, room=sid)
            
    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        await sio.emit('error', {'message': f'Failed to send message: {str(e)}'}, room=sid)


@sio.event
async def get_chat_history(sid, data):
    """
    Get chat history with a friend
    User is already authenticated from connection
    
    Expected data:
    {
        "friend_nickname": "friend_username",
        "page": 1,
        "page_size": 50
    }
    """
    try:
        user_id = manager.get_user_id(sid)
        if not user_id:
            await sio.emit('error', {'message': 'Not authenticated. Please reconnect.'}, room=sid)
            return
        
        friend_nickname = data.get('friend_nickname')
        page = data.get('page', 1)
        page_size = data.get('page_size', 50)
        
        if not friend_nickname:
            await sio.emit('error', {'message': 'friend_nickname is required'}, room=sid)
            return
        
        # Get database session
        async for session in get_db_session():
            try:
                # Get chat history
                history = await ChatService.get_chat_history(
                    session=session,
                    user_id=user_id,
                    friend_nickname=friend_nickname,
                    page=page,
                    page_size=page_size
                )
                
                # Send chat history
                await sio.emit('chat_history', history, room=sid)
                
            except Exception as e:
                logger.error(f"Error getting chat history: {str(e)}")
                await sio.emit('error', {'message': str(e)}, room=sid)
            
    except Exception as e:
        logger.error(f"Error in get_chat_history: {str(e)}")
        await sio.emit('error', {'message': f'Failed to get chat history: {str(e)}'}, room=sid)


@sio.event
async def typing(sid, data):
    """
    Notify friend that user is typing
    
    Expected data:
    {
        "friend_id": 456
    }
    """
    try:
        user_id = manager.get_user_id(sid)
        if not user_id:
            return
        
        friend_id = data.get('friend_id')
        if not friend_id:
            return
        
        # Send typing indicator to friend if online
        friend_sid = manager.get_sid(friend_id)
        if friend_sid:
            await sio.emit('user_typing', {'user_id': user_id}, room=friend_sid)
            
    except Exception as e:
        logger.error(f"Error in typing: {str(e)}")


# Create ASGI application
socket_app = socketio.ASGIApp(sio)
