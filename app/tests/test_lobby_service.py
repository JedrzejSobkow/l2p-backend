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
            host_pfp_path="/avatars/test.jpg",
            max_players=4
        )
        
        assert lobby is not None
        assert len(lobby["lobby_code"]) == 6
        assert lobby["host_id"] == 1
        assert lobby["max_players"] == 4
        assert lobby["current_players"] == 1
        assert len(lobby["members"]) == 1
        assert lobby["members"][0]["user_id"] == 1
        assert lobby["members"][0]["pfp_path"] == "/avatars/test.jpg"
        assert lobby["members"][0]["is_host"] is True
    
    async def test_create_lobby_invalid_max_players(self, redis_client):
        """Test creating lobby with invalid max_players"""
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.create_lobby(
                redis=redis_client,
                host_id=1,
                host_nickname="TestUser",
                host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4
        )
        
        # Try to create second lobby
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.create_lobby(
                redis=redis_client,
                host_id=1,
                host_nickname="TestUser",
                host_pfp_path=None,
                max_players=4
            )
        assert "already in a lobby" in str(exc.value.message)
    
    async def test_get_lobby_success(self, redis_client):
        """Test getting lobby details"""
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="TestUser",
            host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4
        )
        
        # Join lobby
        lobby = await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
                user_nickname="Player2",
            user_pfp_path=None
            )
        assert "not found" in str(exc.value.message)
    
    async def test_join_lobby_user_in_another_lobby(self, redis_client):
        """Test joining a lobby when user is already in another lobby"""
        # Create first lobby
        lobby1 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host1",
            host_pfp_path=None,
            max_players=4
        )
        
        # User 2 joins first lobby
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby1["lobby_code"],
            user_id=2,
            user_nickname="Player2",
            user_pfp_path=None
        )
        
        # Create second lobby
        lobby2 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=3,
            host_nickname="Host2",
            host_pfp_path=None,
            max_players=4
        )
        
        # User 2 tries to join second lobby (should fail)
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.join_lobby(
                redis=redis_client,
                lobby_code=lobby2["lobby_code"],
                user_id=2,
                user_nickname="Player2",
                user_pfp_path=None
            )
        assert "already in another lobby" in str(exc.value.message)
    
    async def test_join_lobby_full(self, redis_client):
        """Test joining a full lobby"""
        # Create lobby with max 2 players
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=2
        )
        
        # Join lobby (fills it)
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        # Try to join full lobby
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.join_lobby(
                redis=redis_client,
                lobby_code=created_lobby["lobby_code"],
                user_id=3,
                user_nickname="Player3",
            user_pfp_path=None
            )
        assert "full" in str(exc.value.message)
    
    async def test_leave_lobby_success(self, redis_client):
        """Test leaving a lobby"""
        # Create and join lobby
        created_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
            host_pfp_path=None,
            max_players=6
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3",
        user_pfp_path=None
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=created_lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4,
            is_public=True
        )
        
        private_lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=2,
            host_nickname="Host2",
            host_pfp_path=None,
            max_players=4,
            is_public=False
        )
        
        public_lobby2 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=3,
            host_nickname="Host3",
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3",
        user_pfp_path=None
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3",
        user_pfp_path=None
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
            host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
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
            host_pfp_path=None,
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
            host_pfp_path=None,
            max_players=4,
            is_public=True
        )
        
        await asyncio.sleep(0.1)
        
        lobby2 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=2,
            host_nickname="Host2",
            host_pfp_path=None,
            max_players=4,
            is_public=True
        )
        
        await asyncio.sleep(0.1)
        
        lobby3 = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=3,
            host_nickname="Host3",
            host_pfp_path=None,
            max_players=4,
            is_public=True
        )
        
        # Get public lobbies
        public_lobbies = await LobbyService.get_all_public_lobbies(redis_client)
        
        # Should be sorted newest first
        assert public_lobbies[0]["lobby_code"] == lobby3["lobby_code"]
        assert public_lobbies[1]["lobby_code"] == lobby2["lobby_code"]
        assert public_lobbies[2]["lobby_code"] == lobby1["lobby_code"]
    
    async def test_toggle_ready_success(self, redis_client):
        """Test toggling ready status successfully"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Toggle ready to True
        result = await LobbyService.toggle_ready(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=1
        )
        
        assert result["user_id"] == 1
        assert result["is_ready"] is True
        
        # Verify in lobby data
        lobby_data = await LobbyService.get_lobby(redis_client, lobby_code)
        assert lobby_data["members"][0]["is_ready"] is True
        
        # Toggle ready back to False
        result = await LobbyService.toggle_ready(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=1
        )
        
        assert result["user_id"] == 1
        assert result["is_ready"] is False
        
        # Verify in lobby data
        lobby_data = await LobbyService.get_lobby(redis_client, lobby_code)
        assert lobby_data["members"][0]["is_ready"] is False
    
    async def test_toggle_ready_multiple_members(self, redis_client):
        """Test toggling ready for multiple members"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Join second member
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        # Join third member
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=3,
            user_nickname="Player3",
        user_pfp_path=None
        )
        
        # Toggle ready for all members
        await LobbyService.toggle_ready(redis_client, lobby_code, 1)
        await LobbyService.toggle_ready(redis_client, lobby_code, 2)
        await LobbyService.toggle_ready(redis_client, lobby_code, 3)
        
        # Verify all are ready
        lobby_data = await LobbyService.get_lobby(redis_client, lobby_code)
        for member in lobby_data["members"]:
            assert member["is_ready"] is True
        
        # Toggle one member to not ready
        await LobbyService.toggle_ready(redis_client, lobby_code, 2)
        
        # Verify mixed ready state
        lobby_data = await LobbyService.get_lobby(redis_client, lobby_code)
        ready_states = {m["user_id"]: m["is_ready"] for m in lobby_data["members"]}
        assert ready_states[1] is True
        assert ready_states[2] is False
        assert ready_states[3] is True
    
    async def test_toggle_ready_lobby_not_found(self, redis_client):
        """Test toggling ready in non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.toggle_ready(
                redis=redis_client,
                lobby_code="NOTEXIST",
                user_id=1
            )
        assert "Lobby not found" in str(exc.value.message)
    
    async def test_toggle_ready_user_not_in_lobby(self, redis_client):
        """Test toggling ready when user is not a member"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Try to toggle ready for non-member
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.toggle_ready(
                redis=redis_client,
                lobby_code=lobby_code,
                user_id=999
            )
        assert "not a member" in str(exc.value.message)
    
    async def test_new_member_starts_not_ready(self, redis_client):
        """Test that new members start with is_ready=False"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Join as second member
        result = await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        # Verify new member is not ready
        member = next(m for m in result["members"] if m["user_id"] == 2)
        assert member["is_ready"] is False
    
    async def test_ready_state_preserved_across_operations(self, redis_client):
        """Test that ready state is preserved during other operations"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Join members
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=2,
            user_nickname="Player2",
        user_pfp_path=None
        )
        
        # Set host to ready
        await LobbyService.toggle_ready(redis_client, lobby_code, 1)
        
        # Update lobby settings
        await LobbyService.update_lobby_settings(
            redis=redis_client,
            lobby_code=lobby_code,
            user_id=1,
            max_players=5
        )
        
        # Verify host is still ready after settings update
        lobby_data = await LobbyService.get_lobby(redis_client, lobby_code)
        host_member = next(m for m in lobby_data["members"] if m["user_id"] == 1)
        assert host_member["is_ready"] is True
    
    async def test_create_lobby_code_collision_retry(self, redis_client, monkeypatch):
        """Test lobby code generation with collision (retry logic)"""
        call_count = 0
        original_generate = LobbyService._generate_lobby_code
        
        def mock_generate():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return "EXIST1"  # This will collide
            return original_generate()
        
        # Pre-create a lobby with code "EXIST1"
        monkeypatch.setattr(LobbyService, '_generate_lobby_code', lambda: "EXIST1")
        await LobbyService.create_lobby(
            redis=redis_client,
            host_id=99,
            host_nickname="Existing",
            host_pfp_path=None,
            max_players=4
        )
        
        # Now try to create with collision
        monkeypatch.setattr(LobbyService, '_generate_lobby_code', mock_generate)
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="TestUser",
            host_pfp_path=None,
            max_players=4
        )
        
        assert lobby["lobby_code"] != "EXIST1"
        assert call_count >= 3  # Should have retried
    
    async def test_create_lobby_max_collision_attempts(self, redis_client, monkeypatch):
        """Test lobby code generation fails after max attempts"""
        # Mock to always return existing code
        monkeypatch.setattr(LobbyService, '_generate_lobby_code', lambda: "EXIST1")
        
        # Pre-create lobby
        await LobbyService.create_lobby(
            redis=redis_client,
            host_id=99,
            host_nickname="Existing",
            host_pfp_path=None,
            max_players=4
        )
        
        # Try to create another - should fail after 10 attempts
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.create_lobby(
                redis=redis_client,
                host_id=1,
                host_nickname="TestUser",
                host_pfp_path=None,
                max_players=4
            )
        assert "Failed to generate unique lobby code" in str(exc.value.message)
    
    async def test_join_lobby_already_in_same_lobby(self, redis_client):
        """Test joining the same lobby twice"""
        # Create and join lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
            user_pfp_path=None
        )
        
        # Try to join same lobby again
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.join_lobby(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=2,
                user_nickname="Player2",
                user_pfp_path=None
            )
        assert "already in this lobby" in str(exc.value.message)
    
    async def test_leave_lobby_not_found(self, redis_client):
        """Test leaving non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.leave_lobby(
                redis=redis_client,
                lobby_code="NOTEXIST",
                user_id=1
            )
        assert "Lobby not found" in str(exc.value.message)
    
    async def test_update_settings_invalid_max_players_range(self, redis_client):
        """Test updating max_players outside valid range"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        # Try to set max_players too high
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.update_lobby_settings(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=1,
                max_players=10
            )
        assert "Invalid max_players" in str(exc.value.message)
        
        # Try to set max_players too low
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.update_lobby_settings(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=1,
                max_players=1
            )
        assert "Invalid max_players" in str(exc.value.message)
    
    async def test_transfer_host_to_self(self, redis_client):
        """Test transferring host to yourself (should fail)"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.transfer_host(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                current_host_id=1,
                new_host_id=1
            )
        assert "already the host" in str(exc.value.message)
    
    async def test_leave_lobby_user_not_in_lobby(self, redis_client):
        """Test leaving lobby when user is not a member"""
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        # Try to leave when not a member
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.leave_lobby(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=999  # User not in lobby
            )
        assert "You are not in this lobby" in str(exc.value.message)
    
    async def test_update_settings_lobby_not_found(self, redis_client):
        """Test updating settings for non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.update_lobby_settings(
                redis=redis_client,
                lobby_code="NOTEXIST",
                user_id=1,
                max_players=4
            )
        assert "Lobby not found" in str(exc.value.message)
    
    async def test_transfer_host_lobby_not_found(self, redis_client):
        """Test transferring host for non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.transfer_host(
                redis=redis_client,
                lobby_code="NOTEXIST",
                current_host_id=1,
                new_host_id=2
            )
        assert "Lobby not found" in str(exc.value.message)
    
    async def test_close_lobby_with_multiple_members(self, redis_client):
        """Test _close_lobby internal method with multiple members"""
        # Create lobby with multiple members
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
            user_pfp_path=None
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=3,
            user_nickname="Player3",
            user_pfp_path=None
        )
        
        # Close lobby
        await LobbyService._close_lobby(redis_client, lobby["lobby_code"])
        
        # Verify lobby is deleted
        lobby_data = await LobbyService.get_lobby(redis_client, lobby["lobby_code"])
        assert lobby_data is None
        
        # Verify user lobby mappings are deleted
        user1_lobby = await redis_client.get(LobbyService._user_lobby_key(1))
        user2_lobby = await redis_client.get(LobbyService._user_lobby_key(2))
        user3_lobby = await redis_client.get(LobbyService._user_lobby_key(3))
        assert user1_lobby is None
        assert user2_lobby is None
        assert user3_lobby is None
    
    # ================ Lobby Chat Tests ================
    
    async def test_save_lobby_message_success(self, redis_client):
        """Test saving a message to lobby chat"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path="/avatars/host.jpg",
            max_players=4
        )
        
        # Save message
        message = await LobbyService.save_lobby_message(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=1,
            user_nickname="Host",
            user_pfp_path="/avatars/host.jpg",
            content="Hello everyone!"
        )
        
        assert message is not None
        assert message["user_id"] == 1
        assert message["nickname"] == "Host"
        assert message["pfp_path"] == "/avatars/host.jpg"
        assert message["content"] == "Hello everyone!"
        assert "timestamp" in message
    
    async def test_save_lobby_message_not_found(self, redis_client):
        """Test saving message to non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.save_lobby_message(
                redis=redis_client,
                lobby_code="INVALID",
                user_id=1,
                user_nickname="User",
                user_pfp_path=None,
                content="Test message"
            )
        assert "Lobby not found" in str(exc.value.message)
    
    async def test_save_lobby_message_not_member(self, redis_client):
        """Test saving message when user is not a lobby member"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        # Try to send message as non-member
        with pytest.raises(BadRequestException) as exc:
            await LobbyService.save_lobby_message(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=999,
                user_nickname="NonMember",
                user_pfp_path=None,
                content="I'm not a member!"
            )
        assert "not a member" in str(exc.value.message)
    
    async def test_get_lobby_messages_success(self, redis_client):
        """Test getting messages from lobby chat"""
        # Create lobby with two users
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        await LobbyService.join_lobby(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
            user_pfp_path=None
        )
        
        # Send multiple messages
        await LobbyService.save_lobby_message(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=1,
            user_nickname="Host",
            user_pfp_path=None,
            content="Hello!"
        )
        
        await LobbyService.save_lobby_message(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=2,
            user_nickname="Player2",
            user_pfp_path=None,
            content="Hi there!"
        )
        
        await LobbyService.save_lobby_message(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            user_id=1,
            user_nickname="Host",
            user_pfp_path=None,
            content="How are you?"
        )
        
        # Get messages
        messages = await LobbyService.get_lobby_messages(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            limit=50
        )
        
        assert len(messages) == 3
        assert messages[0]["content"] == "Hello!"
        assert messages[0]["user_id"] == 1
        assert messages[1]["content"] == "Hi there!"
        assert messages[1]["user_id"] == 2
        assert messages[2]["content"] == "How are you?"
        assert messages[2]["user_id"] == 1
    
    async def test_get_lobby_messages_with_limit(self, redis_client):
        """Test getting limited number of messages"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        # Send 10 messages
        for i in range(10):
            await LobbyService.save_lobby_message(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=1,
                user_nickname="Host",
                user_pfp_path=None,
                content=f"Message {i+1}"
            )
        
        # Get only last 5 messages
        messages = await LobbyService.get_lobby_messages(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            limit=5
        )
        
        assert len(messages) == 5
        assert messages[0]["content"] == "Message 6"
        assert messages[4]["content"] == "Message 10"
    
    async def test_get_lobby_messages_not_found(self, redis_client):
        """Test getting messages from non-existent lobby"""
        with pytest.raises(NotFoundException) as exc:
            await LobbyService.get_lobby_messages(
                redis=redis_client,
                lobby_code="INVALID",
                limit=50
            )
        assert "Lobby not found" in str(exc.value.message)
    
    async def test_lobby_messages_cache_max_size(self, redis_client):
        """Test that lobby messages cache respects max size"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        # Send more messages than MAX_CACHED_MESSAGES
        num_messages = LobbyService.MAX_CACHED_MESSAGES + 10
        for i in range(num_messages):
            await LobbyService.save_lobby_message(
                redis=redis_client,
                lobby_code=lobby["lobby_code"],
                user_id=1,
                user_nickname="Host",
                user_pfp_path=None,
                content=f"Message {i+1}"
            )
        
        # Get all cached messages
        messages = await LobbyService.get_lobby_messages(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            limit=1000  # Request more than cache size
        )
        
        # Should only get MAX_CACHED_MESSAGES
        assert len(messages) == LobbyService.MAX_CACHED_MESSAGES
        # Should get the most recent messages
        assert messages[0]["content"] == f"Message {num_messages - LobbyService.MAX_CACHED_MESSAGES + 1}"
        assert messages[-1]["content"] == f"Message {num_messages}"
    
    async def test_lobby_messages_empty(self, redis_client):
        """Test getting messages from lobby with no messages"""
        # Create lobby
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_id=1,
            host_nickname="Host",
            host_pfp_path=None,
            max_players=4
        )
        
        # Get messages (should be empty)
        messages = await LobbyService.get_lobby_messages(
            redis=redis_client,
            lobby_code=lobby["lobby_code"],
            limit=50
        )
        
        assert len(messages) == 0
