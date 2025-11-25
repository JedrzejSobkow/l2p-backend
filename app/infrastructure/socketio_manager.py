# app/infrastructure/socketio_manager.py

import socketio
from typing import Dict, Optional
from jose import jwt, JWTError
from sqlalchemy import select
from models.registered_user import RegisteredUser
from config.settings import settings
from infrastructure.postgres_connection import postgres_connection
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages Socket.IO connections for real-time features"""
    
    def __init__(self):
        # Maps user_id to list of their session_ids (sids) - supports multiple namespaces
        self.active_connections: Dict[int, list[str]] = {}
        # Maps session_id to user_id
        self.sid_to_user: Dict[str, int] = {}
        # Maps session_id to user email (for reference)
        self.sid_to_email: Dict[str, str] = {}
        # Maps session_id to namespace (IMPORTANT: to avoid sending chat messages via lobby namespace!)
        self.sid_to_namespace: Dict[str, str] = {}
        # Maps user_id to nickname (cached for display purposes)
        self.user_to_nickname: Dict[int, str] = {}
    
    def connect(self, sid: str, user_id: int, email: str, nickname: str = None, namespace: str = None):
        """Register a user's connection"""
        # Add sid to user's list of connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        if sid not in self.active_connections[user_id]:
            self.active_connections[user_id].append(sid)
        
        self.sid_to_user[sid] = user_id
        self.sid_to_email[sid] = email
        
        # Track which namespace this sid belongs to
        if namespace:
            self.sid_to_namespace[sid] = namespace
        
        # Cache nickname if provided
        if nickname:
            self.user_to_nickname[user_id] = nickname
        
        logger.info(f"User {user_id} ({email}) connected with session {sid} to namespace {namespace}")
    
    def disconnect(self, sid: str):
        """Unregister a user's connection"""
        if sid in self.sid_to_user:
            user_id = self.sid_to_user[sid]
            email = self.sid_to_email.get(sid, "unknown")
            namespace = self.sid_to_namespace.get(sid, "unknown")
            
            # Remove this specific sid from user's connections
            if user_id in self.active_connections:
                if sid in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(sid)
                
                # If user has no more connections, clean up nickname cache
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    if user_id in self.user_to_nickname:
                        del self.user_to_nickname[user_id]
            
            del self.sid_to_user[sid]
            if sid in self.sid_to_email:
                del self.sid_to_email[sid]
            if sid in self.sid_to_namespace:
                del self.sid_to_namespace[sid]
            logger.info(f"User {user_id} ({email}) disconnected from {namespace} (session {sid})")
    
    def get_user_id(self, sid: str) -> Optional[int]:
        """Get user_id from session_id"""
        return self.sid_to_user.get(sid)
    
    def get_sid(self, user_id: int, namespace: str = None) -> Optional[str]:
        """
        Get first session_id from user_id, optionally filtered by namespace.
        
        WARNING: Returns only the first session. If you need to support multiple
        devices (e.g., phone + laptop), use get_user_sessions() instead.
        
        Args:
            user_id: The user's ID
            namespace: Optional namespace filter (e.g., '/chat', '/lobby')
            
        Returns:
            First session_id or None
        """
        sessions = self.active_connections.get(user_id, [])
        
        # Filter by namespace if provided
        if namespace:
            sessions = [sid for sid in sessions if self.sid_to_namespace.get(sid) == namespace]
        
        return sessions[0] if sessions else None
    
    def get_user_sessions(self, namespace: str, user_id: int) -> list[str]:
        """
        Get all session_ids for a user in a specific namespace.
        
        Use this method instead of get_sid() to properly support users with
        multiple active sessions (e.g., mobile + desktop).
        
        CRITICAL: This filters by namespace to ensure chat messages don't get
        sent via lobby namespace and vice versa!
        
        Args:
            namespace: The socket.io namespace (e.g., '/chat', '/lobby')
            user_id: The user's ID
            
        Returns:
            List of all session_ids for the user in this namespace (may be empty if offline)
        """
        all_sessions = self.active_connections.get(user_id, [])
        # Filter to only return sids that belong to the requested namespace
        return [sid for sid in all_sessions if self.sid_to_namespace.get(sid) == namespace]
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if user is currently connected"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    def get_nickname(self, user_id: int) -> Optional[str]:
        """Get cached nickname from user_id"""
        return self.user_to_nickname.get(user_id)

    def get_online_users_count(self) -> int:
        """Get total number of online users"""
        return len(self.active_connections)


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


def extract_token_from_environ(environ: dict) -> Optional[str]:
    """
    Extract JWT token from query parameters OR cookies
    
    Args:
        environ: ASGI environ dict
        
    Returns:
        Token string if found, None otherwise
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
    
    return token


# Create global Socket.IO server with proper configuration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # TODO: Configure proper CORS for production
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Global connection manager instance
manager = ConnectionManager()


class BaseNamespace(socketio.AsyncNamespace):
    """Base namespace that does nothing for now - might come in handy when handling guests."""
    pass


class AuthNamespace(BaseNamespace):
    """Authenticated namespace that centralizes authentication and connection lifecycle.

    Subclass this to avoid duplicating authentication/connect/disconnect logic
    across namespaces. Implement `handle_connect(self, sid, environ, user)`
    and/or `handle_disconnect(self, sid)` in subclasses to run namespace-
    specific logic after a successful authenticate/connect or on disconnect.
    """

    async def on_connect(self, sid, environ):
        # Extract and validate token
        token = extract_token_from_environ(environ)
        if not token:
            logger.warning(f"Connection attempt without token from {sid} to {self.namespace}")
            await self.emit('error', {
                'message': 'Authentication required. Please provide token in query parameter or login cookie.'
            }, room=sid)
            await self.disconnect(sid)
            return False

        user = await authenticate_user(token)
        if not user:
            logger.warning(f"Authentication failed for session {sid} on {self.namespace}")
            await self.emit('error', {'message': 'Invalid or expired token'}, room=sid)
            await self.disconnect(sid)
            return False

        # Register connection globally with nickname and namespace
        manager.connect(sid, user.id, user.email, user.nickname, namespace=self.namespace)

        # Call subclass hook if available
        if hasattr(self, 'handle_connect'):
            try:
                await self.handle_connect(sid, environ, user)
            except Exception:
                logger.exception('Error in handle_connect hook')

    async def on_disconnect(self, sid):
        # Default disconnect behaviour
        logger.info(f"Client disconnected from {self.namespace}: {sid}")
        # Call subclass hook before unregistering (in case subclass needs user id)
        if hasattr(self, 'handle_disconnect'):
            try:
                await self.handle_disconnect(sid)
            except Exception:
                logger.exception('Error in handle_disconnect hook')

        manager.disconnect(sid)

    async def get_authenticated_user(self, sid) -> Optional[RegisteredUser]:
        """Return RegisteredUser for given sid or None.

        This helper is useful inside event handlers to get the full user
        object when only `sid` is available.
        """
        user_id = manager.get_user_id(sid)
        if not user_id:
            return None

        try:
            async with postgres_connection.session_factory() as session:
                user_query = select(RegisteredUser).where(RegisteredUser.id == int(user_id))
                result = await session.execute(user_query)
                return result.scalar_one_or_none()
        except Exception:
            logger.exception('Error fetching user from DB')
            return None

