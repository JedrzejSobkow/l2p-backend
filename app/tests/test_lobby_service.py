# app/tests/test_lobby_service.py

import pytest
from datetime import datetime, UTC
from services.lobby_service import LobbyService
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)


@pytest.mark.asyncio
class TestLobbyService:
    """Test suite for LobbyService"""
    
    async def test_create_lobby_success(self, redis_client):
        """Test creating a lobby successfully"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="TestUser",
            max_players=4
        )
        
        assert lobby is not None
        assert len(lobby["lobby_code"]) == 6
        assert lobby["host_id"] == 1
        assert lobby["max_players"] == 4
        assert lobby["current_players"] == 1
        assert len(lobby["members"]) == 1
        assert lobby["members"][0]["user_id"] == 1
        assert lobby["members"][0]["is_host"] is True
    
    async def test_create_lobby_invalid_max_players(self, redis_client):
        """Test creating lobby with invalid max_players"""
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.create_lobby(
                redis=redis_client,
                host_id=1,
                host_nickname="TestUser",
                max_players=10  # Invalid: > 6
            )
        assert "Invalid max_players" in str(exc.value.message)
    
    async def test_create_lobby_user_already_in_lobby(self, redis_client):
        """Test creating lobby when user is already in one"""
        # Create first lobby
        await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="TestUser",
            max_players=4
        )
        
        # Try to create second lobby
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.create_lobby(
                redis=redis_client,
                host_id=1,
                host_nickname="TestUser",
                max_players=4
            )
        assert "already in a lobby" in str(exc.value.message)
    
    async def test_get_lobby_success(self, redis_client):
        """Test getting lobby details"""
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="TestUser",
            max_players=4
        )
        
        lobby = await LobbyService.get_lobby(redis_client, created_lobby["lobby_code"])
        
        assert lobby is not None
        assert lobby["lobby_code"] == created_lobby["lobby_code"]
        assert lobby["host_id"] == 1
        assert lobby["current_players"] == 1
    
    async def test_get_lobby_not_found(self, redis_client):
        """Test getting non-existent lobby"""
        lobby = await LobbyService.get_lobby(redis_client, "INVALID")
        assert lobby is None
    
    async def test_join_lobby_success(self, redis_client):
        """Test joining a lobby"""
        # Create lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Join lobby
        lobby = await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        assert lobby["current_players"] == 2
        assert len(lobby["members"]) == 2
        assert lobby["members"][1]["user_id"] == 2
        assert lobby["members"][1]["is_host"] is False
    
    async def test_join_lobby_not_found(self, redis_client):
        """Test joining non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.join_lobby(
                redis=redis_client,
                lobby_code="INVALID",
                user_id=2,
                user_nickname="Player2"
            )
        assert "not found" in str(exc.value.message)
    
    async def test_join_lobby_full(self, redis_client):
        """Test joining a full lobby"""
        # Create lobby with max 2 players
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=2
        )
        
        # Join lobby (fills it)
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Try to join full lobby
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.join_lobby(
                redis=redis_client,
                lobby_code=created_lobby["lobby_code"],
                user_id=3,
                user_nickname="Player3"
            )
        assert "full" in str(exc.value.message)
    
    async def test_leave_lobby_success(self, redis_client):
        """Test leaving a lobby"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Leave lobby
        result = await LobbyService.leave_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2
        )
        
        assert result is not None
        assert result.get("host_transferred") is False
        
        # Verify member was removed
        lobby = await LobbyService.get_lobby(redis_client, created_lobby["lobby_code"])
        assert lobby["current_players"] == 1
    
    async def test_leave_lobby_host_transfer(self, redis_client):
        """Test that host is transferred when host leaves"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Host leaves
        result = await LobbyService.leave_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=1
        )
        
        assert result is not None
        assert result.get("host_transferred") is True
        assert result["new_host_id"] == 2
        
        # Verify new host
        lobby = await LobbyService.get_lobby(redis_client, created_lobby["lobby_code"])
        assert lobby["host_id"] == 2
        assert lobby["current_players"] == 1
    
    async def test_leave_lobby_last_member_closes_lobby(self, redis_client):
        """Test that lobby closes when last member leaves"""
        # Create lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Host leaves (last member)
        result = await LobbyService.leave_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=1
        )
        
        assert result is None
        
        # Verify lobby is closed
        lobby = await LobbyService.get_lobby(redis_client, created_lobby["lobby_code"])
        assert lobby is None
    
    async def test_update_lobby_settings_success(self, redis_client):
        """Test updating lobby settings"""
        # Create lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Update settings
        lobby = await LobbyService.update_lobby_settings(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=1,
            max_players=6
        )
        
        assert lobby["max_players"] == 6
    
    async def test_update_lobby_settings_not_host(self, redis_client):
        """Test that non-host cannot update settings"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Try to update settings as non-host
        with pytest.raises(ForbiddenException) as exc:
            await LobbyService.update_lobby_settings(
                redis=redis_client,
                lobby_code=created_lobby["lobby_code"],
                user_id=2,
                max_players=6
            )
        assert "Only the host" in str(exc.value.message)
    
    async def test_update_lobby_settings_below_current_players(self, redis_client):
        """Test that max_players cannot be set below current player count"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=6
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3"
        )
        
        # Try to set max_players to 2 (below current 3 players)
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.update_lobby_settings(
                redis=redis_client,
                lobby_code=created_lobby["lobby_code"],
                user_id=1,
                max_players=2
            )
        assert "below current player count" in str(exc.value.message)
    
    async def test_transfer_host_success(self, redis_client):
        """Test transferring host privileges"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Transfer host
        result = await LobbyService.transfer_host(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            current_host_id=1,
            new_host_id=2
        )
        
        assert result["new_host_id"] == 2
        assert result["old_host_id"] == 1
        
        # Verify transfer
        lobby = await LobbyService.get_lobby(redis_client, created_lobby["lobby_code"])
        assert lobby["host_id"] == 2
    
    async def test_transfer_host_not_host(self, redis_client):
        """Test that non-host cannot transfer host"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Try to transfer as non-host
        with pytest.raises(ForbiddenException) as exc:
            await LobbyService.transfer_host(
                redis=redis_client,
                lobby_code=created_lobby["lobby_code"],
                current_host_id=2,
                new_host_id=1
            )
        assert "Only the host" in str(exc.value.message)
    
    async def test_transfer_host_to_non_member(self, redis_client):
        """Test that host cannot be transferred to non-member"""
        # Create lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Try to transfer to non-member
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.transfer_host(
                redis=redis_client,
                lobby_code=created_lobby["lobby_code"],
                current_host_id=1,
                new_host_id=999
            )
        assert "not in this lobby" in str(exc.value.message)
    
    async def test_get_user_lobby(self, redis_client):
        """Test getting user's current lobby"""
        # Create lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Get user's lobby
        lobby_code = await LobbyService.get_user_lobby(redis_client, 1)
        assert lobby_code == created_lobby["lobby_code"]
        
        # User not in lobby
        lobby_code = await LobbyService.get_user_lobby(redis_client, 999)
        assert lobby_code is None
