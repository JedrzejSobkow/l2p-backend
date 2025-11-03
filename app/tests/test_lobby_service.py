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
    
    # ============= Testy dla nowych funkcjonalności =============
    
    async def test_create_public_lobby(self, redis_client):
        """Test creating a public lobby"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4,
            is_public=True
        )
        
        assert lobby["is_public"] is True
        
        # Verify in Redis
        fetched_lobby = await LobbyService.get_lobby(redis_client, lobby["lobby_code"])
        assert fetched_lobby["is_public"] is True
    
    async def test_create_private_lobby_default(self, redis_client):
        """Test that lobbies are private by default"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        assert lobby["is_public"] is False
    
    async def test_get_all_public_lobbies(self, redis_client):
        """Test getting all public lobbies"""
        # Create mix of public and private lobbies
        public_lobby1 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host1",
            max_players=4,
            is_public=True
        )
        
        private_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=2,
            host_nickname="Host2",
            max_players=4,
            is_public=False
        )
        
        public_lobby2 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=3,
            host_nickname="Host3",
            max_players=6,
            is_public=True
        )
        
        # Get public lobbies
        public_lobbies = await LobbyService.get_all_public_lobbies(redis_client)
        
        # Should return only 2 public lobbies
        assert len(public_lobbies) == 2
        
        # Verify they are the right ones
        lobby_codes = [l["lobby_code"] for l in public_lobbies]
        assert public_lobby1["lobby_code"] in lobby_codes
        assert public_lobby2["lobby_code"] in lobby_codes
        assert private_lobby["lobby_code"] not in lobby_codes
        
        # Verify all returned lobbies are public
        for lobby in public_lobbies:
            assert lobby["is_public"] is True
    
    async def test_get_all_public_lobbies_empty(self, redis_client):
        """Test getting public lobbies when none exist"""
        # Create only private lobby
        await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4,
            is_public=False
        )
        
        public_lobbies = await LobbyService.get_all_public_lobbies(redis_client)
        assert len(public_lobbies) == 0
    
    async def test_update_lobby_visibility(self, redis_client):
        """Test changing lobby from private to public"""
        # Create private lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4,
            is_public=False
        )
        
        assert lobby["is_public"] is False
        
        # Change to public
        updated_lobby = await LobbyService.update_lobby_settings(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=1,
            is_public=True
        )
        
        assert updated_lobby["is_public"] is True
        
        # Verify it appears in public lobbies
        public_lobbies = await LobbyService.get_all_public_lobbies(redis_client)
        assert len(public_lobbies) == 1
        assert public_lobbies[0]["lobby_code"] == lobby["lobby_code"]
    
    async def test_update_only_visibility(self, redis_client):
        """Test updating only visibility without changing max_players"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4,
            is_public=False
        )
        
        # Update only visibility
        updated_lobby = await LobbyService.update_lobby_settings(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=1,
            is_public=True
        )
        
        assert updated_lobby["is_public"] is True
        assert updated_lobby["max_players"] == 4  # Unchanged
    
    async def test_update_settings_requires_at_least_one_param(self, redis_client):
        """Test that update_settings requires at least one parameter"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Try to update with no parameters
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.update_lobby_settings(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=1,
                max_players=None,
                is_public=None
            )
        assert "At least one setting must be provided" in str(exc.value.message)
    
    async def test_kick_member_success(self, redis_client):
        """Test kicking a member from lobby"""
        # Create and join lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3"
        )
        
        # Host kicks Player2
        result = await LobbyService.kick_member(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            host_id=1,
            user_id_to_kick=2
        )
        
        assert result["user_id"] == 2
        assert result["nickname"] == "Player2"
        
        # Verify Player2 was removed
        updated_lobby = await LobbyService.get_lobby(redis_client, lobby["lobby_code"])
        assert updated_lobby["current_players"] == 2
        assert not any(m["user_id"] == 2 for m in updated_lobby["members"])
        
        # Verify Player2 no longer has lobby mapping
        player2_lobby = await LobbyService.get_user_lobby(redis_client, 2)
        assert player2_lobby is None
    
    async def test_kick_member_not_host(self, redis_client):
        """Test that non-host cannot kick members"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3"
        )
        
        # Player2 tries to kick Player3
        with pytest.raises(ForbiddenException) as exc:
            await LobbyService.kick_member(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                host_id=2,
                user_id_to_kick=3
            )
        assert "Only the host" in str(exc.value.message)
    
    async def test_kick_member_cannot_kick_self(self, redis_client):
        """Test that host cannot kick themselves"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        # Host tries to kick themselves
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.kick_member(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                host_id=1,
                user_id_to_kick=1
            )
        assert "cannot kick yourself" in str(exc.value.message)
    
    async def test_kick_member_not_in_lobby(self, redis_client):
        """Test kicking user who is not in lobby"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2"
        )
        
        # Try to kick user who isn't in lobby
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.kick_member(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                host_id=1,
                user_id_to_kick=999
            )
        assert "not in this lobby" in str(exc.value.message)
    
    async def test_kick_member_lobby_not_found(self, redis_client):
        """Test kicking from non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.kick_member(
                redis=redis_client,
                lobby_code="INVALID",
                host_id=1,
                user_id_to_kick=2
            )
        assert "not found" in str(exc.value.message)
    
    async def test_update_both_settings_at_once(self, redis_client):
        """Test updating both max_players and is_public simultaneously"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            max_players=4,
            is_public=False
        )
        
        # Update both settings
        updated_lobby = await LobbyService.update_lobby_settings(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=1,
            max_players=6,
            is_public=True
        )
        
        assert updated_lobby["max_players"] == 6
        assert updated_lobby["is_public"] is True
    
    async def test_public_lobbies_sorted_by_creation_time(self, redis_client):
        """Test that public lobbies are sorted by creation time (newest first)"""
        import asyncio
        
        # Create lobbies with slight delays
        lobby1 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host1",
            max_players=4,
            is_public=True
        )
        
        await asyncio.sleep(0.1)
        
        lobby2 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=2,
            host_nickname="Host2",
            max_players=4,
            is_public=True
        )
        
        await asyncio.sleep(0.1)
        
        lobby3 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=3,
            host_nickname="Host3",
            max_players=4,
            is_public=True
        )
        
        # Get public lobbies
        public_lobbies = await LobbyService.get_all_public_lobbies(redis_client)
        
        # Should be sorted newest first
        assert public_lobbies[0]["lobby_code"] == lobby3["lobby_code"]
        assert public_lobbies[1]["lobby_code"] == lobby2["lobby_code"]
        assert public_lobbies[2]["lobby_code"] == lobby1["lobby_code"]
