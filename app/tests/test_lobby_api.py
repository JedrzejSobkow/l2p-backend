# app/tests/test_lobby_api.py

import pytest
import asyncio
from services.lobby_service import LobbyService


@pytest.mark.asyncio
class TestLobbyAPIGameInfo:
    """Test suite for Lobby API game info functionality"""
    
    async def test_lobby_service_returns_game_info_for_create(self, redis_client):
        """Test that creating a lobby with game returns selected_game and selected_game_info"""
        # Create lobby with game directly via service (simulates API call)
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:1",
            host_nickname="TestHost",
            host_pfp_path=None,
            name="API Test Lobby",
            max_players=4,
            is_public=True,
            game_name="tictactoe",
            game_rules={
                "board_size": 5,
                "win_length": 4
            }
        )
        
        # Verify the response includes selected_game
        assert lobby["selected_game"] == "tictactoe"
        assert lobby["game_rules"]["board_size"] == 5
        assert lobby["game_rules"]["win_length"] == 4
        
        # Get lobby to verify selected_game_info is populated
        retrieved_lobby = await LobbyService.get_lobby(redis_client, lobby["lobby_code"])
        
        assert retrieved_lobby["selected_game"] == "tictactoe"
        assert retrieved_lobby["selected_game_info"] is not None
        assert retrieved_lobby["selected_game_info"].game_name == "tictactoe"
        assert retrieved_lobby["selected_game_info"].display_name == "Tic-Tac-Toe"
        assert retrieved_lobby["game_rules"]["board_size"] == 5
    
    async def test_lobby_service_returns_no_game_info_without_game(self, redis_client):
        """Test that creating a lobby without game has no selected_game_info"""
        # Create lobby without game
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:2",
            host_nickname="TestHost2",
            host_pfp_path=None,
            name="API Test No Game",
            max_players=6,
            is_public=False
        )
        
        # Verify no game is selected
        assert lobby.get("selected_game") is None
        assert lobby.get("game_rules") == {}
        
        # Get lobby to verify selected_game_info is None
        retrieved_lobby = await LobbyService.get_lobby(redis_client, lobby["lobby_code"])
        
        assert retrieved_lobby.get("selected_game") is None
        assert retrieved_lobby.get("selected_game_info") is None
    
    async def test_public_lobbies_include_game_info(self, redis_client):
        """Test that get_all_public_lobbies returns game info for lobbies with games"""
        # Create public lobby with tictactoe
        lobby1 = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:10",
            host_nickname="Host1",
            host_pfp_path=None,
            max_players=4,
            is_public=True,
            game_name="tictactoe"
        )
        
        # Create public lobby with clobber
        lobby2 = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:11",
            host_nickname="Host2",
            host_pfp_path=None,
            max_players=2,
            is_public=True,
            game_name="clobber"
        )
        
        # Create public lobby without game
        lobby3 = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:12",
            host_nickname="Host3",
            host_pfp_path=None,
            max_players=6,
            is_public=True
        )
        
        # Get all public lobbies
        lobbies = await LobbyService.get_all_public_lobbies(redis_client)
        
        # Should have at least our 3 lobbies
        assert len(lobbies) >= 3
        
        # Find our lobbies and verify game info
        lobby_codes = {lobby1["lobby_code"], lobby2["lobby_code"], lobby3["lobby_code"]}
        
        for lobby in lobbies:
            if lobby["lobby_code"] in lobby_codes:
                if lobby["selected_game"] == "tictactoe":
                    assert lobby["selected_game_info"] is not None
                    assert lobby["selected_game_info"].display_name == "Tic-Tac-Toe"
                elif lobby["selected_game"] == "clobber":
                    assert lobby["selected_game_info"] is not None
                    assert lobby["selected_game_info"].display_name == "Clobber"
                elif lobby["selected_game"] is None:
                    assert lobby["selected_game_info"] is None
    
    async def test_filter_public_lobbies_by_game(self, redis_client):
        """Test filtering public lobbies by game includes correct game info"""
        # Create public lobbies with different games
        lobby_ttt = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:20",
            host_nickname="TTTHost",
            host_pfp_path=None,
            max_players=4,
            is_public=True,
            game_name="tictactoe"
        )
        
        lobby_clobber = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:21",
            host_nickname="ClobberHost",
            host_pfp_path=None,
            max_players=2,
            is_public=True,
            game_name="clobber"
        )
        
        # Filter by tictactoe
        ttt_lobbies = await LobbyService.get_all_public_lobbies(
            redis_client,
            game_name="tictactoe"
        )
        
        # All returned lobbies should have tictactoe
        assert len(ttt_lobbies) >= 1
        for lobby in ttt_lobbies:
            assert lobby["selected_game"] == "tictactoe"
            assert lobby["selected_game_info"] is not None
            assert lobby["selected_game_info"].game_name == "tictactoe"
            assert lobby["selected_game_info"].display_name == "Tic-Tac-Toe"
        
        # Filter by clobber
        clobber_lobbies = await LobbyService.get_all_public_lobbies(
            redis_client,
            game_name="clobber"
        )
        
        # All returned lobbies should have clobber
        assert len(clobber_lobbies) >= 1
        for lobby in clobber_lobbies:
            assert lobby["selected_game"] == "clobber"
            assert lobby["selected_game_info"] is not None
            assert lobby["selected_game_info"].game_name == "clobber"
            assert lobby["selected_game_info"].display_name == "Clobber"

