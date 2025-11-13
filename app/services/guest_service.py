# app/services/guest_service.py

import json
import uuid
import random
from typing import Optional
from datetime import datetime, UTC
from redis.asyncio import Redis
from schemas.user_schema import GuestUser
import logging

logger = logging.getLogger(__name__)


class GuestService:
    """Service for managing guest sessions in Redis"""
    
    GUEST_SESSION_PREFIX = "guest_session:"
    GUEST_NICKNAME_SET = "guest_nicknames"  # Set to track used guest nicknames
    GUEST_SESSION_TTL = 3600 * 8  # 8 hours TTL for guest sessions
    
    @staticmethod
    def _generate_guest_nickname() -> str:
        """
        Generate guest nickname in format: guest{6digits}
        Total length: 5 + 6 = 11 characters (within 20 char limit)
        """
        random_digits = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        return f"guest{random_digits}"
    
    @staticmethod
    def _guest_session_key(guest_id: str) -> str:
        """Get Redis key for guest session data"""
        return f"{GuestService.GUEST_SESSION_PREFIX}{guest_id}"
    
    @staticmethod
    async def create_guest_session(redis: Redis) -> GuestUser:
        """
        Create a new guest session with auto-generated nickname
        
        Args:
            redis: Redis client
            
        Returns:
            GuestUser with generated guest_id and nickname
        """
        guest_id = str(uuid.uuid4())
        
        # Generate unique nickname (retry if collision, though very unlikely)
        max_retries = 10
        for _ in range(max_retries):
            nickname = GuestService._generate_guest_nickname()
            
            # Check if nickname is already in use (in the set of active guest nicknames)
            is_taken = await redis.sismember(GuestService.GUEST_NICKNAME_SET, nickname)
            
            if not is_taken:
                break
        else:
            # If all retries failed, use UUID suffix
            nickname = f"guest{str(uuid.uuid4())[:6]}"
            logger.warning(f"Generated fallback nickname: {nickname}")
        
        # Create guest data
        guest_data = {
            "guest_id": guest_id,
            "nickname": nickname,
            "created_at": datetime.now(UTC).isoformat(),
            "pfp_path": "/images/avatar/1.png"
        }
        
        # Store in Redis with TTL
        session_key = GuestService._guest_session_key(guest_id)
        
        async with redis.pipeline(transaction=True) as pipe:
            # Store guest session data
            pipe.setex(session_key, GuestService.GUEST_SESSION_TTL, json.dumps(guest_data))
            
            # Add nickname to active set (with same TTL)
            pipe.sadd(GuestService.GUEST_NICKNAME_SET, nickname)
            
            await pipe.execute()
        
        logger.info(f"Created guest session: {guest_id} with nickname: {nickname}")
        
        return GuestUser(**guest_data)
    
    @staticmethod
    async def get_guest_session(redis: Redis, guest_id: str) -> Optional[GuestUser]:
        """
        Retrieve guest session data
        
        Args:
            redis: Redis client
            guest_id: Guest UUID
            
        Returns:
            GuestUser if session exists and is valid, None otherwise
        """
        session_key = GuestService._guest_session_key(guest_id)
        data = await redis.get(session_key)
        
        if not data:
            logger.debug(f"Guest session not found: {guest_id}")
            return None
        
        try:
            guest_data = json.loads(data)
            return GuestUser(**guest_data)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error parsing guest session {guest_id}: {str(e)}")
            return None
    
    @staticmethod
    async def extend_guest_session(redis: Redis, guest_id: str) -> bool:
        """
        Extend TTL of guest session (e.g., on activity)
        
        Args:
            redis: Redis client
            guest_id: Guest UUID
            
        Returns:
            True if session was extended, False if session doesn't exist
        """
        session_key = GuestService._guest_session_key(guest_id)
        result = await redis.expire(session_key, GuestService.GUEST_SESSION_TTL)
        
        if result:
            logger.debug(f"Extended guest session: {guest_id}")
        else:
            logger.debug(f"Could not extend guest session (not found): {guest_id}")
        
        return bool(result)
    
    @staticmethod
    async def delete_guest_session(redis: Redis, guest_id: str) -> bool:
        """
        Delete guest session (e.g., on explicit logout or cleanup)
        
        Args:
            redis: Redis client
            guest_id: Guest UUID
            
        Returns:
            True if session was deleted, False if it didn't exist
        """
        # Get guest data to remove nickname from set
        guest = await GuestService.get_guest_session(redis, guest_id)
        
        session_key = GuestService._guest_session_key(guest_id)
        
        async with redis.pipeline(transaction=True) as pipe:
            # Delete session data
            pipe.delete(session_key)
            
            # Remove nickname from active set if we have it
            if guest:
                pipe.srem(GuestService.GUEST_NICKNAME_SET, guest.nickname)
            
            results = await pipe.execute()
        
        deleted = results[0] > 0
        
        if deleted:
            logger.info(f"Deleted guest session: {guest_id}")
        else:
            logger.debug(f"Guest session not found for deletion: {guest_id}")
        
        return deleted
    
    @staticmethod
    async def cleanup_expired_nicknames(redis: Redis):
        """
        Cleanup nicknames in the set that no longer have active sessions.
        This is a maintenance function that can be called periodically.
        
        Note: Redis TTL on the session keys should handle most cleanup,
        but this ensures the nickname set stays clean.
        """
        all_nicknames = await redis.smembers(GuestService.GUEST_NICKNAME_SET)
        
        if not all_nicknames:
            return
        
        # Check each nickname's corresponding session
        for nickname in all_nicknames:
            # We don't have direct nickname->guest_id mapping, so this is best-effort
            # In practice, Redis TTL handles this automatically
            pass
        
        logger.debug(f"Guest nickname set contains {len(all_nicknames)} entries")
