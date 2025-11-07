# app/services/lobby_service.py

import json
import random
import string
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC, timedelta
from redis.asyncio import Redis
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
import logging

logger = logging.getLogger(__name__)


class LobbyService:
    """Service for managing game lobbies using Redis"""
    
    # Redis key patterns
    LOBBY_KEY_PREFIX = "lobby:"
    LOBBY_MEMBERS_KEY_PREFIX = "lobby_members:"
    USER_LOBBY_KEY_PREFIX = "user_lobby:"
    LOBBY_MESSAGES_KEY_PREFIX = "lobby_messages:"
    LOBBY_TTL = 3600 * 4  # 4 hours TTL for lobbies
    MAX_CACHED_MESSAGES = 50  # Maximum messages to keep in Redis cache
    
    @staticmethod
    def _generate_lobby_code() -> str:
        """Generate a unique 6-character alphanumeric lobby code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    @staticmethod
    def _lobby_key(lobby_code: str) -> str:
        """Get Redis key for lobby data"""
        return f"{LobbyService.LOBBY_KEY_PREFIX}{lobby_code}"
    
    @staticmethod
    def _lobby_members_key(lobby_code: str) -> str:
        """Get Redis key for lobby members list"""
        return f"{LobbyService.LOBBY_MEMBERS_KEY_PREFIX}{lobby_code}"
    
    @staticmethod
    def _user_lobby_key(user_id: int) -> str:
        """Get Redis key for user's current lobby"""
        return f"{LobbyService.USER_LOBBY_KEY_PREFIX}{user_id}"
    
    @staticmethod
    def _lobby_messages_key(lobby_code: str) -> str:
        """Get Redis key for lobby messages list"""
        return f"{LobbyService.LOBBY_MESSAGES_KEY_PREFIX}{lobby_code}"
    
    @staticmethod
    async def create_lobby(
        redis: Redis,
        host_id: int,
        host_nickname: str,
        host_pfp_path: Optional[str] = None,
        name: Optional[str] = None,
        max_players: int = 6,
        is_public: bool = False,
        game_name: Optional[str] = None,
        game_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new lobby
        
        Args:
            redis: Redis client
            host_id: User ID of the host
            host_nickname: Nickname of the host
            host_pfp_path: Path to host's profile picture
            name: Optional custom lobby name (defaults to "Game: {lobby_code}")
            max_players: Maximum number of players (2-6)
            host_id: User ID of the host
            host_nickname: Nickname of the host
            host_pfp_path: Path to host's profile picture
            max_players: Maximum number of players (2-6)
            is_public: Whether lobby is public
            game_name: Optional pre-selected game
            game_rules: Optional initial game rules
            
        Returns:
            Dictionary with lobby_code and lobby details
            
        Raises:
            BadRequestException: If user is already in a lobby or invalid max_players
        """
        # Validate max_players
        if not 2 <= max_players <= 6:
            raise BadRequestException(
                message="Invalid max_players",
                details={"max_players": "Must be between 2 and 6"}
            )
        
        # Validate game_name if provided
        if game_name:
            from services.game_service import GameService
            if game_name not in GameService.GAME_ENGINES:
                raise BadRequestException(
                    message=f"Unknown game type: {game_name}",
                    details={
                        "available_games": GameService.get_available_games(),
                        "requested_game": game_name
                    }
                )
            
            # If game_name provided without rules, use defaults
            if game_rules is None:
                engine_class = GameService.GAME_ENGINES[game_name]
                game_info = engine_class.get_game_info()
                game_rules = {
                    rule_name: rule_config.default
                    for rule_name, rule_config in game_info.supported_rules.items()
                }
        
        # Check if user is already in a lobby
        existing_lobby = await redis.get(LobbyService._user_lobby_key(host_id))
        if existing_lobby:
            raise BadRequestException(
                message="You are already in a lobby",
                details={"current_lobby": existing_lobby.decode() if isinstance(existing_lobby, bytes) else existing_lobby}
            )
        
        # Generate unique lobby code
        lobby_code = LobbyService._generate_lobby_code()
        max_attempts = 10
        attempts = 0
        
        while await redis.exists(LobbyService._lobby_key(lobby_code)) and attempts < max_attempts:
            lobby_code = LobbyService._generate_lobby_code()
            attempts += 1
        
        if attempts >= max_attempts:
            raise BadRequestException(message="Failed to generate unique lobby code")
        
        now = datetime.now(UTC)
        
        # Set lobby name - use provided name or default to "Game: {lobby_code}"
        lobby_name = name if name else f"Game: {lobby_code}"
        
        # Create lobby data
        lobby_data = {
            "lobby_code": lobby_code,
            "name": lobby_name,
            "host_id": host_id,
            "max_players": max_players,
            "is_public": is_public,
            "created_at": now.isoformat(),
            "selected_game": game_name,
            "game_rules": game_rules or {},
        }
        
        # Create host member data
        host_member = {
            "user_id": host_id,
            "nickname": host_nickname,
            "pfp_path": host_pfp_path,
            "is_host": True,
            "is_ready": False,
            "joined_at": now.isoformat(),
        }
        
        # Store in Redis with pipeline for atomicity
        async with redis.pipeline(transaction=True) as pipe:
            # Store lobby data
            pipe.set(
                LobbyService._lobby_key(lobby_code),
                json.dumps(lobby_data),
                ex=LobbyService.LOBBY_TTL
            )
            
            # Store host as first member (using sorted set with timestamp as score)
            pipe.zadd(
                LobbyService._lobby_members_key(lobby_code),
                {json.dumps(host_member): now.timestamp()}
            )
            pipe.expire(LobbyService._lobby_members_key(lobby_code), LobbyService.LOBBY_TTL)
            
            # Map user to lobby
            pipe.set(
                LobbyService._user_lobby_key(host_id),
                lobby_code,
                ex=LobbyService.LOBBY_TTL
            )
            
            await pipe.execute()
        
        logger.info(f"Lobby '{lobby_name}' ({lobby_code}) created by user {host_id}" + 
                   (f" with game {game_name}" if game_name else ""))
        
        return {
            "lobby_code": lobby_code,
            "name": lobby_name,
            "host_id": host_id,
            "max_players": max_players,
            "is_public": is_public,
            "current_players": 1,
            "members": [host_member],
            "created_at": now,
            "selected_game": game_name,
            "game_rules": game_rules or {},
        }
    
    @staticmethod
    async def get_lobby(redis: Redis, lobby_code: str) -> Optional[Dict[str, Any]]:
        """
        Get lobby details
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            
        Returns:
            Dictionary with lobby details or None if not found
        """
        # Get lobby data
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        if not lobby_data_raw:
            return None
        
        lobby_data = json.loads(lobby_data_raw)
        
        # Get members (sorted by join time)
        members_raw = await redis.zrange(
            LobbyService._lobby_members_key(lobby_code),
            0, -1
        )
        
        members = [json.loads(m) for m in members_raw]
        
        return {
            **lobby_data,
            "current_players": len(members),
            "members": members,
            "created_at": datetime.fromisoformat(lobby_data["created_at"]),
        }
    
    @staticmethod
    async def join_lobby(
        redis: Redis,
        lobby_code: str,
        user_id: int,
        user_nickname: str,
        user_pfp_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Join an existing lobby
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: User ID joining
            user_nickname: Nickname of the user
            user_pfp_path: Path to user's profile picture
            
        Returns:
            Dictionary with updated lobby details
            
        Raises:
            NotFoundException: If lobby not found
            BadRequestException: If user already in lobby or lobby full
        """
        # Check if user is already in a lobby
        existing_lobby = await redis.get(LobbyService._user_lobby_key(user_id))
        if existing_lobby:
            existing_code = existing_lobby.decode() if isinstance(existing_lobby, bytes) else existing_lobby
            if existing_code == lobby_code:
                raise BadRequestException(message="You are already in this lobby")
            else:
                raise BadRequestException(
                    message="You are already in another lobby",
                    details={"current_lobby": existing_code}
                )
        
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(message="Lobby not found", details={"lobby_code": lobby_code})
        
        # Check if lobby is full
        if lobby["current_players"] >= lobby["max_players"]:
            raise BadRequestException(message="Lobby is full")
        
        now = datetime.now(UTC)
        
        # Create member data
        member = {
            "user_id": user_id,
            "nickname": user_nickname,
            "pfp_path": user_pfp_path,
            "is_host": False,
            "is_ready": False,
            "joined_at": now.isoformat(),
        }
        
        # Add member to lobby
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zadd(
                LobbyService._lobby_members_key(lobby_code),
                {json.dumps(member): now.timestamp()}
            )
            pipe.set(
                LobbyService._user_lobby_key(user_id),
                lobby_code,
                ex=LobbyService.LOBBY_TTL
            )
            await pipe.execute()
        
        logger.info(f"User {user_id} joined lobby {lobby_code}")
        
        # Return updated lobby
        return await LobbyService.get_lobby(redis, lobby_code)
    
    @staticmethod
    async def leave_lobby(
        redis: Redis,
        lobby_code: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Leave a lobby
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: User ID leaving
            
        Returns:
            Dictionary with info about host transfer if occurred, or None if lobby closed
            
        Raises:
            NotFoundException: If lobby not found
            BadRequestException: If user not in lobby
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(message="Lobby not found")
        
        # Find member
        member_to_remove = None
        for member in lobby["members"]:
            if member["user_id"] == user_id:
                member_to_remove = member
                break
        
        if not member_to_remove:
            raise BadRequestException(message="You are not in this lobby")
        
        was_host = member_to_remove["is_host"]
        
        # Remove member
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zrem(
                LobbyService._lobby_members_key(lobby_code),
                json.dumps(member_to_remove)
            )
            pipe.delete(LobbyService._user_lobby_key(user_id))
            await pipe.execute()
        
        logger.info(f"User {user_id} left lobby {lobby_code}")
        
        # Get updated member list
        members_raw = await redis.zrange(
            LobbyService._lobby_members_key(lobby_code),
            0, -1
        )
        
        # If no members left, close lobby
        if not members_raw:
            await LobbyService._close_lobby(redis, lobby_code)
            logger.info(f"Lobby {lobby_code} closed (no members left)")
            return None
        
        # If host left, transfer to next oldest member
        if was_host:
            members = [json.loads(m) for m in members_raw]
            new_host = members[0]  # First member (oldest by join time)
            
            # Update host status
            new_host["is_host"] = True
            
            # Update in Redis
            await redis.zrem(
                LobbyService._lobby_members_key(lobby_code),
                json.dumps({**new_host, "is_host": False})
            )
            await redis.zadd(
                LobbyService._lobby_members_key(lobby_code),
                {json.dumps(new_host): datetime.fromisoformat(new_host["joined_at"]).timestamp()}
            )
            
            # Update lobby host_id
            lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
            lobby_data = json.loads(lobby_data_raw)
            lobby_data["host_id"] = new_host["user_id"]
            await redis.set(
                LobbyService._lobby_key(lobby_code),
                json.dumps(lobby_data),
                ex=LobbyService.LOBBY_TTL
            )
            
            logger.info(f"Host transferred from {user_id} to {new_host['user_id']} in lobby {lobby_code}")
            
            return {
                "host_transferred": True,
                "old_host_id": user_id,
                "new_host_id": new_host["user_id"],
                "new_host_nickname": new_host["nickname"],
            }
        
        return {"host_transferred": False}
    
    @staticmethod
    async def update_lobby_settings(
        redis: Redis,
        lobby_code: str,
        user_id: int,
        max_players: Optional[int] = None,
        is_public: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update lobby settings (only host can do this)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: User ID requesting update
            max_players: New max players value (optional)
            is_public: New public/private setting (optional)
            
        Returns:
            Updated lobby details
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If user is not host
            BadRequestException: If invalid max_players or below current player count
        """
        # At least one setting must be provided
        if max_players is None and is_public is None:
            raise BadRequestException(
                message="At least one setting must be provided",
                details={"max_players": max_players, "is_public": is_public}
            )
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(message="Lobby not found")
        
        # Check if user is host
        if lobby["host_id"] != user_id:
            raise ForbiddenException(message="Only the host can update lobby settings")
        
        # Validate max_players if provided
        if max_players is not None:
            if not 2 <= max_players <= 6:
                raise BadRequestException(
                    message="Invalid max_players",
                    details={"max_players": "Must be between 2 and 6"}
                )
            
            # Check if new max is not below current player count
            if max_players < lobby["current_players"]:
                raise BadRequestException(
                    message="Cannot set max_players below current player count",
                    details={
                        "current_players": lobby["current_players"],
                        "requested_max": max_players
                    }
                )
        
        # Update lobby data
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        lobby_data = json.loads(lobby_data_raw)
        
        if max_players is not None:
            lobby_data["max_players"] = max_players
        if is_public is not None:
            lobby_data["is_public"] = is_public
        
        await redis.set(
            LobbyService._lobby_key(lobby_code),
            json.dumps(lobby_data),
            ex=LobbyService.LOBBY_TTL
        )
        
        logger.info(f"Lobby {lobby_code} settings updated by host {user_id}: max_players={max_players}, is_public={is_public}")
        
        return await LobbyService.get_lobby(redis, lobby_code)
    
    @staticmethod
    async def transfer_host(
        redis: Redis,
        lobby_code: str,
        current_host_id: int,
        new_host_id: int
    ) -> Dict[str, Any]:
        """
        Transfer host privileges to another member
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            current_host_id: Current host user ID
            new_host_id: New host user ID
            
        Returns:
            Dictionary with transfer details
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If current user is not host
            BadRequestException: If new host is not in lobby
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(message="Lobby not found")
        
        # Check if user is host
        if lobby["host_id"] != current_host_id:
            raise ForbiddenException(message="Only the host can transfer host privileges")
        
        # Find both members
        current_host_member = None
        new_host_member = None
        
        for member in lobby["members"]:
            if member["user_id"] == current_host_id:
                current_host_member = member
            if member["user_id"] == new_host_id:
                new_host_member = member
        
        if not new_host_member:
            raise BadRequestException(message="New host is not in this lobby")
        
        if new_host_id == current_host_id:
            raise BadRequestException(message="You are already the host")
        
        # Update both members
        current_host_member["is_host"] = False
        new_host_member["is_host"] = True
        
        # Update in Redis
        async with redis.pipeline(transaction=True) as pipe:
            # Remove old entries
            pipe.zrem(
                LobbyService._lobby_members_key(lobby_code),
                json.dumps({**current_host_member, "is_host": True})
            )
            pipe.zrem(
                LobbyService._lobby_members_key(lobby_code),
                json.dumps({**new_host_member, "is_host": False})
            )
            
            # Add updated entries
            pipe.zadd(
                LobbyService._lobby_members_key(lobby_code),
                {
                    json.dumps(current_host_member): datetime.fromisoformat(current_host_member["joined_at"]).timestamp(),
                    json.dumps(new_host_member): datetime.fromisoformat(new_host_member["joined_at"]).timestamp(),
                }
            )
            
            await pipe.execute()
        
        # Update lobby host_id
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        lobby_data = json.loads(lobby_data_raw)
        lobby_data["host_id"] = new_host_id
        await redis.set(
            LobbyService._lobby_key(lobby_code),
            json.dumps(lobby_data),
            ex=LobbyService.LOBBY_TTL
        )
        
        logger.info(f"Host transferred from {current_host_id} to {new_host_id} in lobby {lobby_code}")
        
        return {
            "old_host_id": current_host_id,
            "new_host_id": new_host_id,
            "new_host_nickname": new_host_member["nickname"],
        }
    
    @staticmethod
    async def get_user_lobby(redis: Redis, user_id: int) -> Optional[str]:
        """
        Get the lobby code a user is currently in
        
        Args:
            redis: Redis client
            user_id: User ID
            
        Returns:
            Lobby code or None
        """
        lobby_code = await redis.get(LobbyService._user_lobby_key(user_id))
        if lobby_code:
            return lobby_code.decode() if isinstance(lobby_code, bytes) else lobby_code
        return None
    
    @staticmethod
    async def get_all_public_lobbies(redis: Redis) -> List[Dict[str, Any]]:
        """
        Get all public lobbies
        
        Args:
            redis: Redis client
            
        Returns:
            List of public lobby details
        """
        # Scan for all lobby keys
        lobbies = []
        cursor = 0
        
        while True:
            cursor, keys = await redis.scan(
                cursor=cursor,
                match=f"{LobbyService.LOBBY_KEY_PREFIX}*",
                count=100
            )
            
            for key in keys:
                lobby_code = key.replace(LobbyService.LOBBY_KEY_PREFIX, "")
                lobby = await LobbyService.get_lobby(redis, lobby_code)
                
                if lobby and lobby.get("is_public", False):
                    lobbies.append(lobby)
            
            if cursor == 0:
                break
        
        # Sort by created_at (newest first)
        lobbies.sort(key=lambda x: x["created_at"], reverse=True)
        
        return lobbies
    
    @staticmethod
    async def kick_member(
        redis: Redis,
        lobby_code: str,
        host_id: int,
        user_id_to_kick: int
    ) -> Dict[str, Any]:
        """
        Kick a member from the lobby (host only)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            host_id: Host user ID
            user_id_to_kick: User ID to kick
            
        Returns:
            Dictionary with kicked member info
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If user is not host
            BadRequestException: If trying to kick self or user not in lobby
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(message="Lobby not found")
        
        # Check if user is host
        if lobby["host_id"] != host_id:
            raise ForbiddenException(message="Only the host can kick members")
        
        # Cannot kick yourself
        if user_id_to_kick == host_id:
            raise BadRequestException(message="You cannot kick yourself")
        
        # Find member to kick
        member_to_kick = None
        for member in lobby["members"]:
            if member["user_id"] == user_id_to_kick:
                member_to_kick = member
                break
        
        if not member_to_kick:
            raise BadRequestException(message="User is not in this lobby")
        
        # Remove member
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zrem(
                LobbyService._lobby_members_key(lobby_code),
                json.dumps(member_to_kick)
            )
            pipe.delete(LobbyService._user_lobby_key(user_id_to_kick))
            await pipe.execute()
        
        logger.info(f"User {user_id_to_kick} kicked from lobby {lobby_code} by host {host_id}")
        
        return {
            "user_id": user_id_to_kick,
            "nickname": member_to_kick["nickname"]
        }
    
    @staticmethod
    async def _close_lobby(redis: Redis, lobby_code: str):
        """
        Close/delete a lobby and clean up all related data
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
        """
        # Get all members to clean up their user_lobby mappings
        members_raw = await redis.zrange(
            LobbyService._lobby_members_key(lobby_code),
            0, -1
        )
        
        members = [json.loads(m) for m in members_raw]
        
        # Delete all related keys
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(LobbyService._lobby_key(lobby_code))
            pipe.delete(LobbyService._lobby_members_key(lobby_code))
            
            for member in members:
                pipe.delete(LobbyService._user_lobby_key(member["user_id"]))
            
            await pipe.execute()
        
        logger.info(f"Lobby {lobby_code} closed and cleaned up")
    
    @staticmethod
    async def toggle_ready(
        redis: Redis,
        lobby_code: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Toggle ready status for a member in the lobby
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: User ID of the member
            
        Returns:
            Dictionary with updated member info and new ready status
            
        Raises:
            NotFoundException: If lobby or member not found
        """
        # Check if lobby exists
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        if not lobby_data_raw:
            raise NotFoundException(
                message="Lobby not found",
                details={"lobby_code": lobby_code}
            )
        
        # Get all members
        members_raw = await redis.zrange(
            LobbyService._lobby_members_key(lobby_code),
            0, -1,
            withscores=True
        )
        
        # Find the member
        member_to_update = None
        member_score = None
        
        for member_json, score in members_raw:
            member = json.loads(member_json)
            if member["user_id"] == user_id:
                member_to_update = member
                member_score = score
                break
        
        if not member_to_update:
            raise NotFoundException(
                message="You are not a member of this lobby",
                details={"user_id": user_id, "lobby_code": lobby_code}
            )
        
        # Toggle ready status
        new_ready_status = not member_to_update.get("is_ready", False)
        member_to_update["is_ready"] = new_ready_status
        
        # Update member in Redis
        async with redis.pipeline(transaction=True) as pipe:
            # Remove old member entry
            pipe.zrem(
                LobbyService._lobby_members_key(lobby_code),
                json.dumps({**member_to_update, "is_ready": not new_ready_status})
            )
            
            # Add updated member entry with same score (preserve join time)
            pipe.zadd(
                LobbyService._lobby_members_key(lobby_code),
                {json.dumps(member_to_update): member_score}
            )
            
            # Refresh TTL
            pipe.expire(LobbyService._lobby_members_key(lobby_code), LobbyService.LOBBY_TTL)
            
            await pipe.execute()
        
        logger.info(f"User {user_id} toggled ready to {new_ready_status} in lobby {lobby_code}")
        
        return {
            "user_id": user_id,
            "nickname": member_to_update["nickname"],
            "is_ready": new_ready_status,
            "lobby_code": lobby_code
        }
    
    @staticmethod
    async def save_lobby_message(
        redis: Redis,
        lobby_code: str,
        user_id: int,
        user_nickname: str,
        user_pfp_path: Optional[str],
        content: str
    ) -> Dict[str, Any]:
        """
        Save a message to lobby chat (ephemeral - stored in Redis)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: ID of the message sender
            user_nickname: Nickname of the sender
            user_pfp_path: Profile picture path of the sender
            content: Message content
            
        Returns:
            Dictionary with message details
            
        Raises:
            NotFoundException: If lobby not found
            BadRequestException: If user not in lobby
        """
        # Verify lobby exists
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        if not lobby_data_raw:
            raise NotFoundException(
                message="Lobby not found",
                details={"lobby_code": lobby_code}
            )
        
        # Verify user is a member of this lobby
        members_raw = await redis.zrange(
            LobbyService._lobby_members_key(lobby_code),
            0, -1
        )
        
        is_member = False
        for member_json in members_raw:
            member = json.loads(member_json)
            if member["user_id"] == user_id:
                is_member = True
                break
        
        if not is_member:
            raise BadRequestException(
                message="You are not a member of this lobby",
                details={"user_id": user_id, "lobby_code": lobby_code}
            )
        
        now = datetime.now(UTC)
        
        # Create message data
        message_data = {
            "user_id": user_id,
            "nickname": user_nickname,
            "pfp_path": user_pfp_path,
            "content": content,
            "timestamp": now.isoformat()
        }
        
        # Store message in Redis list (FIFO with max size)
        async with redis.pipeline(transaction=True) as pipe:
            # Add message to the end of the list
            pipe.rpush(
                LobbyService._lobby_messages_key(lobby_code),
                json.dumps(message_data)
            )
            
            # Trim list to keep only last N messages
            pipe.ltrim(
                LobbyService._lobby_messages_key(lobby_code),
                -LobbyService.MAX_CACHED_MESSAGES,
                -1
            )
            
            # Set TTL on messages list
            pipe.expire(
                LobbyService._lobby_messages_key(lobby_code),
                LobbyService.LOBBY_TTL
            )
            
            await pipe.execute()
        
        logger.info(f"User {user_id} sent message to lobby {lobby_code}")
        
        return {
            **message_data,
            "timestamp": now
        }
    
    @staticmethod
    async def get_lobby_messages(
        redis: Redis,
        lobby_code: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from lobby chat
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            limit: Maximum number of messages to retrieve (default 50)
            
        Returns:
            List of message dictionaries
            
        Raises:
            NotFoundException: If lobby not found
        """
        # Verify lobby exists
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        if not lobby_data_raw:
            raise NotFoundException(
                message="Lobby not found",
                details={"lobby_code": lobby_code}
            )
        
        # Get messages (most recent first)
        messages_raw = await redis.lrange(
            LobbyService._lobby_messages_key(lobby_code),
            -limit,
            -1
        )
        
        messages = []
        for msg_json in messages_raw:
            msg = json.loads(msg_json)
            msg["timestamp"] = datetime.fromisoformat(msg["timestamp"])
            messages.append(msg)
        
        return messages

    @staticmethod
    async def select_game(
        redis: Redis,
        lobby_code: str,
        host_id: int,
        game_name: str
    ) -> Dict[str, Any]:
        """
        Select a game for the lobby (host only)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            host_id: User ID of the host (for authorization)
            game_name: Name of the game to select
            
        Returns:
            Dictionary with updated lobby info and game info
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If user is not the host
            BadRequestException: If game name is invalid
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(
                message="Lobby not found",
                details={"lobby_code": lobby_code}
            )
        
        # Check if user is host
        if lobby["host_id"] != host_id:
            raise ForbiddenException(
                message="Only the host can select a game",
                details={"host_id": lobby["host_id"]}
            )
        
        # Validate game name
        from services.game_service import GameService
        if game_name not in GameService.GAME_ENGINES:
            raise BadRequestException(
                message=f"Unknown game type: {game_name}",
                details={
                    "available_games": GameService.get_available_games(),
                    "requested_game": game_name
                }
            )
        
        # Get game info and default rules
        engine_class = GameService.GAME_ENGINES[game_name]
        game_info = engine_class.get_game_info()
        default_rules = {
            rule_name: rule_config.default
            for rule_name, rule_config in game_info.supported_rules.items()
        }
        
        # Update lobby data
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        lobby_data = json.loads(lobby_data_raw)
        lobby_data["selected_game"] = game_name
        lobby_data["game_rules"] = default_rules
        
        # Save to Redis
        await redis.set(
            LobbyService._lobby_key(lobby_code),
            json.dumps(lobby_data),
            ex=LobbyService.LOBBY_TTL
        )
        
        logger.info(f"Game '{game_name}' selected for lobby {lobby_code}")
        
        return {
            "lobby": lobby_data,
            "game_info": game_info.model_dump(),
            "current_rules": default_rules
        }

    @staticmethod
    async def update_game_rules(
        redis: Redis,
        lobby_code: str,
        host_id: int,
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update game rules in the lobby (host only)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            host_id: User ID of the host (for authorization)
            rules: Dictionary of rules to update
            
        Returns:
            Dictionary with updated rules
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If user is not the host
            BadRequestException: If no game selected or invalid rules
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(
                message="Lobby not found",
                details={"lobby_code": lobby_code}
            )
        
        # Check if user is host
        if lobby["host_id"] != host_id:
            raise ForbiddenException(
                message="Only the host can update game rules",
                details={"host_id": lobby["host_id"]}
            )
        
        # Check if game is selected
        if not lobby.get("selected_game"):
            raise BadRequestException(
                message="No game selected. Select a game first.",
                details={"lobby_code": lobby_code}
            )
        
        # Validate rules against game info
        from services.game_service import GameService
        engine_class = GameService.GAME_ENGINES[lobby["selected_game"]]
        game_info = engine_class.get_game_info()
        
        for rule_name, rule_value in rules.items():
            if rule_name not in game_info.supported_rules:
                raise BadRequestException(
                    message=f"Unknown rule: {rule_name}",
                    details={
                        "supported_rules": list(game_info.supported_rules.keys()),
                        "invalid_rule": rule_name
                    }
                )
            
            rule_config = game_info.supported_rules[rule_name]
            
            # Validate based on rule type
            if rule_config.type == "integer":
                if not isinstance(rule_value, int):
                    raise BadRequestException(
                        message=f"Rule '{rule_name}' must be an integer",
                        details={"rule_name": rule_name, "provided_value": rule_value}
                    )
                if rule_config.min is not None and rule_value < rule_config.min:
                    raise BadRequestException(
                        message=f"Rule '{rule_name}' is below minimum",
                        details={"rule_name": rule_name, "min": rule_config.min, "value": rule_value}
                    )
                if rule_config.max is not None and rule_value > rule_config.max:
                    raise BadRequestException(
                        message=f"Rule '{rule_name}' exceeds maximum",
                        details={"rule_name": rule_name, "max": rule_config.max, "value": rule_value}
                    )
            
            elif rule_config.type == "boolean":
                if not isinstance(rule_value, bool):
                    raise BadRequestException(
                        message=f"Rule '{rule_name}' must be a boolean",
                        details={"rule_name": rule_name, "provided_value": rule_value}
                    )
            
            elif rule_config.type == "string":
                if not isinstance(rule_value, str):
                    raise BadRequestException(
                        message=f"Rule '{rule_name}' must be a string",
                        details={"rule_name": rule_name, "provided_value": rule_value}
                    )
        
        # Update lobby data
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        lobby_data = json.loads(lobby_data_raw)
        
        # Merge new rules with existing rules
        current_rules = lobby_data.get("game_rules", {})
        current_rules.update(rules)
        lobby_data["game_rules"] = current_rules
        
        # Save to Redis
        await redis.set(
            LobbyService._lobby_key(lobby_code),
            json.dumps(lobby_data),
            ex=LobbyService.LOBBY_TTL
        )
        
        logger.info(f"Game rules updated for lobby {lobby_code}: {rules}")
        
        return {
            "lobby_code": lobby_code,
            "rules": current_rules
        }

    @staticmethod
    async def clear_game_selection(
        redis: Redis,
        lobby_code: str,
        host_id: int
    ) -> Dict[str, Any]:
        """
        Clear game selection (allows selecting a different game)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            host_id: User ID of the host (for authorization)
            
        Returns:
            Dictionary with updated lobby info
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If user is not the host
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(
                message="Lobby not found",
                details={"lobby_code": lobby_code}
            )
        
        # Check if user is host
        if lobby["host_id"] != host_id:
            raise ForbiddenException(
                message="Only the host can clear game selection",
                details={"host_id": lobby["host_id"]}
            )
        
        # Update lobby data
        lobby_data_raw = await redis.get(LobbyService._lobby_key(lobby_code))
        lobby_data = json.loads(lobby_data_raw)
        lobby_data["selected_game"] = None
        lobby_data["game_rules"] = {}
        
        # Save to Redis
        await redis.set(
            LobbyService._lobby_key(lobby_code),
            json.dumps(lobby_data),
            ex=LobbyService.LOBBY_TTL
        )
        
        logger.info(f"Game selection cleared for lobby {lobby_code}")
        
        return {
            "lobby_code": lobby_code,
            "message": "Game selection cleared"
        }
