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
    """Manages Socket.IO connections for real-time features (supports both registered users and guests)"""
    
    def __init__(self):
        # Maps identifier (user:123 or guest:uuid) to list of their session_ids (sids)
        self.active_connections: Dict[str, list[str]] = {}
        # Maps session_id to identifier
        self.sid_to_identifier: Dict[str, str] = {}
        # Maps session_id to email/reference (email for users, guest-{id} for guests)
        self.sid_to_email: Dict[str, str] = {}
        # Maps session_id to namespace (IMPORTANT: to avoid sending chat messages via lobby namespace!)
        self.sid_to_namespace: Dict[str, str] = {}
        # Maps identifier to nickname (cached for display purposes)
        self.identifier_to_nickname: Dict[str, str] = {}
        
        # BACKWARD COMPATIBILITY: Keep old methods working
        # Maps session_id to user_id (int) - only for registered users
        self.sid_to_user: Dict[str, int] = {}
        # Maps user_id to nickname - only for registered users
        self.user_to_nickname: Dict[int, str] = {}
    
    def connect(self, sid: str, identifier: str, email: str, nickname: str = None, namespace: str = None):
        """
        Register a connection (works for both registered users and guests)
        
        Args:
            sid: Socket.IO session ID
            identifier: Unique identifier - "user:{id}" or "guest:{uuid}"
            email: Email for users or "guest-{uuid}" for guests
            nickname: Display name
            namespace: Socket.IO namespace
        """
        # Add sid to identifier's list of connections
        if identifier not in self.active_connections:
            self.active_connections[identifier] = []
        
        if sid not in self.active_connections[identifier]:
            self.active_connections[identifier].append(sid)
        
        self.sid_to_identifier[sid] = identifier
        self.sid_to_email[sid] = email
        
        # Track which namespace this sid belongs to
        if namespace:
            self.sid_to_namespace[sid] = namespace
        
        # Cache nickname if provided
        if nickname:
            self.identifier_to_nickname[identifier] = nickname
        
        # BACKWARD COMPATIBILITY: If it's a registered user, populate old mappings
        if identifier.startswith("user:"):
            try:
                user_id = int(identifier.split(":", 1)[1])
                self.sid_to_user[sid] = user_id
                if nickname:
                    self.user_to_nickname[user_id] = nickname
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse user_id from identifier {identifier}: {e}")
        
        logger.info(f"Connection {identifier} ({email}) with session {sid} to namespace {namespace}")
    
    def disconnect(self, sid: str):
        """Unregister a connection"""
        if sid in self.sid_to_identifier:
            identifier = self.sid_to_identifier[sid]
            email = self.sid_to_email.get(sid, "unknown")
            namespace = self.sid_to_namespace.get(sid, "unknown")
            
            # Remove this specific sid from identifier's connections
            if identifier in self.active_connections:
                if sid in self.active_connections[identifier]:
                    self.active_connections[identifier].remove(sid)
                
                # If no more connections, clean up nickname cache
                if not self.active_connections[identifier]:
                    del self.active_connections[identifier]
                    if identifier in self.identifier_to_nickname:
                        del self.identifier_to_nickname[identifier]
            
            # BACKWARD COMPATIBILITY: Clean up old mappings
            if sid in self.sid_to_user:
                user_id = self.sid_to_user[sid]
                del self.sid_to_user[sid]
                # Clean up user_to_nickname if no more sessions for this user
                if identifier.startswith("user:") and identifier not in self.active_connections:
                    if user_id in self.user_to_nickname:
                        del self.user_to_nickname[user_id]
            
            del self.sid_to_identifier[sid]
            if sid in self.sid_to_email:
                del self.sid_to_email[sid]
            if sid in self.sid_to_namespace:
                del self.sid_to_namespace[sid]
            logger.info(f"Connection {identifier} ({email}) disconnected from {namespace} (session {sid})")
    
    def get_identifier(self, sid: str) -> Optional[str]:
        """Get identifier from session_id"""
        return self.sid_to_identifier.get(sid)
    
    def get_user_id(self, sid: str) -> Optional[int]:
        """
        Get user_id from session_id (BACKWARD COMPATIBILITY - only works for registered users)
        Returns None for guests
        """
        return self.sid_to_user.get(sid)
    
    def get_sid(self, identifier: str, namespace: str = None) -> Optional[str]:
        """
        Get first session_id from identifier, optionally filtered by namespace.
        
        WARNING: Returns only the first session. If you need to support multiple
        devices (e.g., phone + laptop), use get_identifier_sessions() instead.
        
        Args:
            identifier: The identifier ("user:123" or "guest:uuid")
            namespace: Optional namespace filter (e.g., '/chat', '/lobby')
            
        Returns:
            First session_id or None
        """
        sessions = self.active_connections.get(identifier, [])
        
        # Filter by namespace if provided
        if namespace:
            sessions = [sid for sid in sessions if self.sid_to_namespace.get(sid) == namespace]
        
        return sessions[0] if sessions else None
    
    def get_identifier_sessions(self, namespace: str, identifier: str) -> list[str]:
        """
        Get all session_ids for an identifier in a specific namespace.
        
        Use this method to properly support users with multiple active sessions.
        
        Args:
            namespace: The socket.io namespace (e.g., '/chat', '/lobby')
            identifier: The identifier ("user:123" or "guest:uuid")
            
        Returns:
            List of all session_ids for the identifier in this namespace
        """
        all_sessions = self.active_connections.get(identifier, [])
        # Filter to only return sids that belong to the requested namespace
        return [sid for sid in all_sessions if self.sid_to_namespace.get(sid) == namespace]
    
    def get_user_sessions(self, namespace: str, user_id: int) -> list[str]:
        """
        BACKWARD COMPATIBILITY: Get all sessions for a registered user
        
        Args:
            namespace: The socket.io namespace
            user_id: The user's ID (registered user only)
            
        Returns:
            List of all session_ids for the user in this namespace
        """
        identifier = f"user:{user_id}"
        return self.get_identifier_sessions(namespace, identifier)
    
    def is_user_online(self, identifier: str) -> bool:
        """Check if identifier is currently connected"""
        return identifier in self.active_connections and len(self.active_connections[identifier]) > 0
    
    def get_nickname(self, identifier: str) -> Optional[str]:
        """
        Get cached nickname from identifier
        Can accept either "user:123" / "guest:uuid" or just int for backward compatibility
        """
        if isinstance(identifier, int):
            # BACKWARD COMPATIBILITY: convert int user_id to identifier
            identifier = f"user:{identifier}"
        return self.identifier_to_nickname.get(identifier)

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


# Helper function to authenticate guest from cookie
async def authenticate_guest(guest_id: str):
    """
    Authenticate guest from guest_id and extend session TTL
    
    Args:
        guest_id: Guest UUID from cookie
        
    Returns:
        GuestUser if valid session exists, None otherwise
    """
    try:
        from infrastructure.redis_connection import get_redis
        from services.guest_service import GuestService
        
        redis = get_redis()
        guest = await GuestService.get_guest_session(redis, guest_id)
        
        if not guest:
            logger.warning(f"Guest session not found: {guest_id}")
            return None
        
        # Extend session TTL on successful authentication (keeps guest active)
        await GuestService.extend_guest_session(redis, guest_id)
        
        return guest
        
    except Exception as e:
        logger.error(f"Guest authentication error: {str(e)}")
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


def extract_guest_id_from_environ(environ: dict) -> Optional[str]:
    """
    Extract guest_id from cookies
    
    Args:
        environ: ASGI environ dict
        
    Returns:
        Guest ID string if found, None otherwise
    """
    cookie_header = environ.get('HTTP_COOKIE', '')
    if cookie_header:
        # Parse cookies manually
        cookies = {}
        for cookie in cookie_header.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name] = value
        
        return cookies.get('l2p_guest')
    
    return None


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
        user_identifier = f"user:{user.id}"
        manager.connect(sid, user_identifier, user.email, user.nickname, namespace=self.namespace)

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


class GuestAuthNamespace(BaseNamespace):
    """
    Authenticated namespace that accepts BOTH registered users (JWT) AND guests (guest cookie).
    
    Subclass this for namespaces that should support guest access (e.g., lobby, game).
    Implement `handle_connect(self, sid, environ, session_user)` in subclasses where
    session_user is a SessionUser object (which can be either registered or guest).
    """

    async def on_connect(self, sid, environ):
        from schemas.user_schema import SessionUser
        
        # Try JWT authentication first (registered users)
        token = extract_token_from_environ(environ)
        if token:
            user = await authenticate_user(token)
            if user:
                # Registered user authenticated
                identifier = f"user:{user.id}"
                session_user = SessionUser(
                    user_id=user.id,
                    guest_id=None,
                    nickname=user.nickname,
                    is_guest=False,
                    pfp_path=user.pfp_path,
                    email=user.email
                )
                
                # Register connection
                manager.connect(sid, identifier, user.email, user.nickname, namespace=self.namespace)
                
                # Call subclass hook
                if hasattr(self, 'handle_connect'):
                    try:
                        await self.handle_connect(sid, environ, session_user)
                    except Exception:
                        logger.exception('Error in handle_connect hook')
                
                return True
        
        # Try guest authentication (guest cookie)
        guest_id = extract_guest_id_from_environ(environ)
        if guest_id:
            guest = await authenticate_guest(guest_id)
            if guest:
                # Guest authenticated
                identifier = f"guest:{guest.guest_id}"
                session_user = SessionUser(
                    user_id=None,
                    guest_id=guest.guest_id,
                    nickname=guest.nickname,
                    is_guest=True,
                    pfp_path=guest.pfp_path,
                    email=None
                )
                
                # Register connection
                manager.connect(sid, identifier, f"guest-{guest.guest_id}", guest.nickname, namespace=self.namespace)
                
                # Call subclass hook
                if hasattr(self, 'handle_connect'):
                    try:
                        await self.handle_connect(sid, environ, session_user)
                    except Exception:
                        logger.exception('Error in handle_connect hook')
                
                return True
        
        # No valid authentication found
        logger.warning(f"Connection attempt without valid auth from {sid} to {self.namespace}")
        await self.emit('error', {
            'message': 'Authentication required. Please provide JWT token or guest session.'
        }, room=sid)
        await self.disconnect(sid)
        return False

    async def on_disconnect(self, sid):
        # Default disconnect behaviour
        logger.info(f"Client disconnected from {self.namespace}: {sid}")
        
        # Call subclass hook before unregistering
        if hasattr(self, 'handle_disconnect'):
            try:
                await self.handle_disconnect(sid)
            except Exception:
                logger.exception('Error in handle_disconnect hook')
        
        manager.disconnect(sid)

    async def get_session_user(self, sid):
        """
        Return SessionUser for given sid (works for both registered users and guests).
        
        Returns:
            SessionUser object or None if not found
        """
        from schemas.user_schema import SessionUser
        
        identifier = manager.get_identifier(sid)
        if not identifier:
            return None
        
        nickname = manager.get_nickname(identifier)
        
        if identifier.startswith("user:"):
            # Registered user
            user_id = int(identifier.split(":")[1])
            try:
                async with postgres_connection.session_factory() as session:
                    user_query = select(RegisteredUser).where(RegisteredUser.id == user_id)
                    result = await session.execute(user_query)
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        return None
                    
                    return SessionUser(
                        user_id=user.id,
                        guest_id=None,
                        nickname=user.nickname,
                        is_guest=False,
                        pfp_path=user.pfp_path,
                        email=user.email
                    )
            except Exception:
                logger.exception('Error fetching user from DB')
                return None
        
        elif identifier.startswith("guest:"):
            # Guest user
            guest_id = identifier.split(":", 1)[1]
            try:
                from infrastructure.redis_connection import get_redis
                from services.guest_service import GuestService
                
                redis = get_redis()
                guest = await GuestService.get_guest_session(redis, guest_id)
                
                if not guest:
                    return None
                
                return SessionUser(
                    user_id=None,
                    guest_id=guest.guest_id,
                    nickname=guest.nickname,
                    is_guest=True,
                    pfp_path=guest.pfp_path,
                    email=None
                )
            except Exception:
                logger.exception('Error fetching guest from Redis')
                return None
        
        return None
    
    async def get_authenticated_user(self, sid) -> Optional[RegisteredUser]:
        """
        BACKWARD COMPATIBILITY: Return RegisteredUser for given sid or None.
        Only works for registered users, returns None for guests.
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

