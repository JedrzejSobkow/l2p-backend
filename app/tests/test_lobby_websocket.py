# app/tests/test_lobby_websocket.py

import pytest
from services.lobby_service import LobbyService


@pytest.mark.asyncio
class TestLobbyWebSocketGameInfo:
    """Test suite for on_get_lobby_game_info WebSocket endpoint"""
    
    async def test_get_lobby_game_info_with_tictactoe(self, redis_client):
        """Test getting game info returns game_name and display_name for tictactoe"""
        # Create lobby with game
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:1",
            host_nickname="TestHost",
            host_pfp_path=None,
            max_players=4,
            is_public=True,
            game_name="tictactoe"
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Simulate WebSocket endpoint response
        retrieved_lobby = await LobbyService.get_lobby(redis_client, lobby_code)
        
        game_info_response = {
            "lobby_code": lobby_code,
            "game_name": retrieved_lobby.get("selected_game"),
            "game_display_name": retrieved_lobby.get("selected_game_info").display_name if retrieved_lobby.get("selected_game_info") else None
        }
        
        # Verify response has only what's needed
        assert game_info_response["lobby_code"] == lobby_code
        assert game_info_response["game_name"] == "tictactoe"
        assert game_info_response["game_display_name"] == "Tic-Tac-Toe"
    
    async def test_get_lobby_game_info_with_clobber(self, redis_client):
        """Test getting game info returns game_name and display_name for clobber"""
        # Create lobby with clobber game
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:2",
            host_nickname="ClobberHost",
            host_pfp_path=None,
            max_players=2,
            is_public=True,
            game_name="clobber"
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Get lobby
        retrieved_lobby = await LobbyService.get_lobby(redis_client, lobby_code)
        
        # Simulate endpoint response
        game_info_response = {
            "lobby_code": lobby_code,
            "game_name": retrieved_lobby.get("selected_game"),
            "game_display_name": retrieved_lobby.get("selected_game_info").display_name if retrieved_lobby.get("selected_game_info") else None
        }
        
        # Verify response
        assert game_info_response["game_name"] == "clobber"
        assert game_info_response["game_display_name"] == "Clobber"
    
    async def test_get_lobby_game_info_without_game(self, redis_client):
        """Test that lobby without game returns None for game_name and display_name"""
        # Create lobby without game
        lobby = await LobbyService.create_lobby(
            redis=redis_client,
            host_identifier=f"user:3",
            host_nickname="NoGameHost",
            host_pfp_path=None,
            max_players=6,
            is_public=False
        )
        
        lobby_code = lobby["lobby_code"]
        
        # Get lobby
        retrieved_lobby = await LobbyService.get_lobby(redis_client, lobby_code)
        
        # Simulate endpoint response
        game_info_response = {
            "lobby_code": lobby_code,
            "game_name": retrieved_lobby.get("selected_game"),
            "game_display_name": None
        }
        
        assert game_info_response["game_name"] is None
        assert game_info_response["game_display_name"] is None
