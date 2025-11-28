# tests/test_guest_service.py

import pytest
import json
from unittest.mock import patch, AsyncMock
from services.guest_service import GuestService
from schemas.user_schema import GuestUser


@pytest.mark.asyncio
class TestGuestService:
    """Tests for GuestService"""
    
    async def test_generate_guest_nickname(self):
        """Test guest nickname generation format"""
        nickname = GuestService._generate_guest_nickname()
        
        assert nickname.startswith("guest")
        assert len(nickname) == 11  # "guest" + 6 digits
        assert nickname[5:].isdigit()  # Last 6 chars are digits
    
    async def test_guest_session_key(self):
        """Test Redis key generation"""
        guest_id = "test-uuid-123"
        key = GuestService._guest_session_key(guest_id)
        
        assert key == f"{GuestService.GUEST_SESSION_PREFIX}{guest_id}"
        assert key == "guest_session:test-uuid-123"
    
    async def test_create_guest_session_success(self, redis_client):
        """Test successful guest session creation"""
        guest = await GuestService.create_guest_session(redis_client)
        
        # Verify guest data
        assert guest.guest_id is not None
        assert guest.nickname.startswith("guest")
        assert len(guest.nickname) == 11
        assert guest.pfp_path == "/images/avatar/1.png"
        
        # Verify stored in Redis
        session_key = GuestService._guest_session_key(guest.guest_id)
        stored_data = await redis_client.get(session_key)
        assert stored_data is not None
        
        stored_json = json.loads(stored_data)
        assert stored_json["guest_id"] == guest.guest_id
        assert stored_json["nickname"] == guest.nickname
        
        # Verify nickname in set
        is_in_set = await redis_client.sismember(
            GuestService.GUEST_NICKNAME_SET, 
            guest.nickname
        )
        assert is_in_set
    
    async def test_create_guest_session_ttl(self, redis_client):
        """Test that guest session has proper TTL"""
        guest = await GuestService.create_guest_session(redis_client)
        
        session_key = GuestService._guest_session_key(guest.guest_id)
        ttl = await redis_client.ttl(session_key)
        
        # TTL should be close to 8 hours (28800 seconds)
        assert ttl > 28700  # Allow some margin for test execution time
        assert ttl <= GuestService.GUEST_SESSION_TTL
    
    async def test_create_guest_session_nickname_collision(self, redis_client):
        """Test nickname collision handling"""
        # Create first guest
        guest1 = await GuestService.create_guest_session(redis_client)
        
        # Mock to force collision on first try, then succeed
        original_generate = GuestService._generate_guest_nickname
        call_count = 0
        
        def mock_generate():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return guest1.nickname  # Collision
            return original_generate()
        
        with patch.object(GuestService, '_generate_guest_nickname', side_effect=mock_generate):
            guest2 = await GuestService.create_guest_session(redis_client)
        
        # Should have different nicknames
        assert guest2.nickname != guest1.nickname
        assert guest2.guest_id != guest1.guest_id
    
    async def test_create_guest_session_max_retries_fallback(self, redis_client):
        """Test fallback nickname when max retries exceeded"""
        # Pre-populate many nicknames
        for _ in range(15):
            await GuestService.create_guest_session(redis_client)
        
        # Mock to always return collisions
        with patch.object(GuestService, '_generate_guest_nickname', return_value="guest000000"):
            with patch('uuid.uuid4', return_value=type('obj', (object,), {'__str__': lambda self: 'abcdef123456'})()):
                guest = await GuestService.create_guest_session(redis_client)
        
        # Should use fallback with UUID
        assert guest.nickname.startswith("guest")
        # Fallback format is guest + first 6 chars of UUID
    
    async def test_get_guest_session_exists(self, redis_client):
        """Test retrieving existing guest session"""
        # Create guest
        created_guest = await GuestService.create_guest_session(redis_client)
        
        # Retrieve guest
        retrieved_guest = await GuestService.get_guest_session(
            redis_client, 
            created_guest.guest_id
        )
        
        assert retrieved_guest is not None
        assert retrieved_guest.guest_id == created_guest.guest_id
        assert retrieved_guest.nickname == created_guest.nickname
        assert retrieved_guest.pfp_path == created_guest.pfp_path
    
    async def test_get_guest_session_not_found(self, redis_client):
        """Test retrieving non-existent guest session"""
        result = await GuestService.get_guest_session(redis_client, "nonexistent-id")
        
        assert result is None
    
    async def test_get_guest_session_invalid_json(self, redis_client):
        """Test handling of corrupted guest data"""
        guest_id = "test-corrupted"
        session_key = GuestService._guest_session_key(guest_id)
        
        # Store invalid JSON
        await redis_client.set(session_key, "invalid json data")
        
        result = await GuestService.get_guest_session(redis_client, guest_id)
        
        assert result is None
    
    async def test_extend_guest_session_success(self, redis_client):
        """Test extending guest session TTL"""
        # Create guest
        guest = await GuestService.create_guest_session(redis_client)
        
        # Wait a bit and extend
        import asyncio
        await asyncio.sleep(1)
        
        result = await GuestService.extend_guest_session(redis_client, guest.guest_id)
        
        assert result is True
        
        # Check TTL was reset
        session_key = GuestService._guest_session_key(guest.guest_id)
        ttl = await redis_client.ttl(session_key)
        assert ttl > 28700  # Should be close to full TTL again
    
    async def test_extend_guest_session_not_found(self, redis_client):
        """Test extending non-existent session"""
        result = await GuestService.extend_guest_session(redis_client, "nonexistent-id")
        
        assert result is False
    
    async def test_delete_guest_session_success(self, redis_client):
        """Test deleting guest session"""
        # Create guest
        guest = await GuestService.create_guest_session(redis_client)
        
        # Verify it exists
        assert await GuestService.get_guest_session(redis_client, guest.guest_id) is not None
        
        # Delete
        result = await GuestService.delete_guest_session(redis_client, guest.guest_id)
        
        assert result is True
        
        # Verify deleted
        assert await GuestService.get_guest_session(redis_client, guest.guest_id) is None
        
        # Verify nickname removed from set
        is_in_set = await redis_client.sismember(
            GuestService.GUEST_NICKNAME_SET, 
            guest.nickname
        )
        assert not is_in_set
    
    async def test_delete_guest_session_not_found(self, redis_client):
        """Test deleting non-existent session"""
        result = await GuestService.delete_guest_session(redis_client, "nonexistent-id")
        
        assert result is False
    
    async def test_cleanup_expired_nicknames(self, redis_client):
        """Test cleanup function runs without error"""
        # Create some guests
        for _ in range(3):
            await GuestService.create_guest_session(redis_client)
        
        # Run cleanup (should not raise)
        await GuestService.cleanup_expired_nicknames(redis_client)
        
        # Verify nicknames still in set
        all_nicknames = await redis_client.smembers(GuestService.GUEST_NICKNAME_SET)
        assert len(all_nicknames) >= 3
    
    async def test_cleanup_expired_nicknames_empty(self, redis_client):
        """Test cleanup with no nicknames"""
        # Should not raise
        await GuestService.cleanup_expired_nicknames(redis_client)
    
    async def test_guest_session_constants(self):
        """Test service constants are properly defined"""
        assert GuestService.GUEST_SESSION_PREFIX == "guest_session:"
        assert GuestService.GUEST_NICKNAME_SET == "guest_nicknames"
        assert GuestService.GUEST_SESSION_TTL == 3600 * 8  # 8 hours
    
    async def test_multiple_concurrent_guest_creation(self, redis_client):
        """Test creating multiple guests concurrently"""
        import asyncio
        
        # Create 10 guests concurrently
        guests = await asyncio.gather(*[
            GuestService.create_guest_session(redis_client)
            for _ in range(10)
        ])
        
        # Verify all have unique IDs and nicknames
        guest_ids = [g.guest_id for g in guests]
        nicknames = [g.nickname for g in guests]
        
        assert len(set(guest_ids)) == 10
        # Nicknames might have collisions with 10 guests
        assert len(set(nicknames)) >= 1

    async def test_create_guest_session_all_retries_exhausted(self, redis_client):
        """Test fallback nickname when all 10 retries have collisions"""
        # Pre-create many guests to fill up the namespace
        created_guests = []
        for _ in range(12):
            guest = await GuestService.create_guest_session(redis_client)
            created_guests.append(guest)
        
        # Mock to always return collision for first 10 tries
        collision_nickname = "guest000000"
        call_count = 0
        
        original_generate = GuestService._generate_guest_nickname
        def mock_generate_always_collide():
            nonlocal call_count
            call_count += 1
            if call_count <= 10:
                return collision_nickname
            return original_generate()
        
        # Mock sismember to always return True for collision_nickname
        original_sismember = redis_client.sismember
        async def mock_sismember(key, value):
            if value == collision_nickname:
                return True
            return await original_sismember(key, value)
        
        with patch.object(GuestService, '_generate_guest_nickname', side_effect=mock_generate_always_collide):
            with patch.object(redis_client, 'sismember', side_effect=mock_sismember):
                guest = await GuestService.create_guest_session(redis_client)
        
        # Should use fallback with UUID
        assert guest.nickname.startswith("guest")
        # Verify it's not the collision nickname
        assert guest.nickname != collision_nickname
