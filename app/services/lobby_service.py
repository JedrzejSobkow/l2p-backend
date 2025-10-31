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
    LOBBY_TTL = 3600 * 4  # 4 hours TTL for lobbies
    
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
    async def create_lobby(
        redis: Redis,
        host_id: int,
        host_nickname: str,
        max_players: int = 6
    ) -> Dict[str, Any]:
        """
        Create a new lobby
        
        Args:
            redis: Redis client
            host_id: User ID of the host
            host_nickname: Nickname of the host
            max_players: Maximum number of players (2-6)
            
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
        
        # Create lobby data
        lobby_data = {
            "lobby_code": lobby_code,
            "host_id": host_id,
            "max_players": max_players,
            "created_at": now.isoformat(),
        }
        
        # Create host member data
        host_member = {
            "user_id": host_id,
            "nickname": host_nickname,
            "is_host": True,
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
        
        logger.info(f"Lobby {lobby_code} created by user {host_id}")
        
        return {
            "lobby_code": lobby_code,
            "host_id": host_id,
            "max_players": max_players,
            "current_players": 1,
            "members": [host_member],
            "created_at": now,
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
        user_nickname: str
    ) -> Dict[str, Any]:
        """
        Join an existing lobby
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: User ID joining
            user_nickname: Nickname of the user
            
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
            "is_host": False,
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
        max_players: int
    ) -> Dict[str, Any]:
        """
        Update lobby settings (only host can do this)
        
        Args:
            redis: Redis client
            lobby_code: 6-character lobby code
            user_id: User ID requesting update
            max_players: New max players value
            
        Returns:
            Updated lobby details
            
        Raises:
            NotFoundException: If lobby not found
            ForbiddenException: If user is not host
            BadRequestException: If invalid max_players or below current player count
        """
        # Get lobby
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        if not lobby:
            raise NotFoundException(message="Lobby not found")
        
        # Check if user is host
        if lobby["host_id"] != user_id:
            raise ForbiddenException(message="Only the host can update lobby settings")
        
        # Validate max_players
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
        lobby_data["max_players"] = max_players
        
        await redis.set(
            LobbyService._lobby_key(lobby_code),
            json.dumps(lobby_data),
            ex=LobbyService.LOBBY_TTL
        )
        
        logger.info(f"Lobby {lobby_code} max_players updated to {max_players} by host {user_id}")
        
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
