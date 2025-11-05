# app/tests/test_game_service.py

import pytest
import json
from services.game_service import GameService
from services.game_engine_interface import GameResult
from exceptions.domain_exceptions import NotFoundException, BadRequestException


@pytest.mark.asyncio
class TestGameService:
    """Tests for GameService"""
    
    async def test_create_game_success(self, redis_client):
        """Test successful game creation"""
        result = await GameService.create_game(
            redis=redis_client,
            lobby_code="TEST123",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        assert result["lobby_code"] == "TEST123"
        assert result["game_name"] == "tictactoe"
        assert "game_state" in result
        assert result["current_turn_player_id"] == 1
        
        # Verify data is stored in Redis
        game_state = await redis_client.get(GameService._game_state_key("TEST123"))
        assert game_state is not None
        
        engine_config = await redis_client.get(GameService._game_engine_key("TEST123"))
        assert engine_config is not None
        
    async def test_create_game_with_custom_rules(self, redis_client):
        """Test game creation with custom rules"""
        result = await GameService.create_game(
            redis=redis_client,
            lobby_code="TEST456",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={"board_size": 4, "win_length": 4}
        )
        
        assert result["game_info"]["board_size"] == 4
        assert result["game_info"]["win_length"] == 4
        
    async def test_create_game_already_exists(self, redis_client):
        """Test that creating a game twice fails"""
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TEST789",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        with pytest.raises(BadRequestException, match="already exists"):
            await GameService.create_game(
                redis=redis_client,
                lobby_code="TEST789",
                game_name="tictactoe",
                player_ids=[1, 2]
            )
            
    async def test_create_game_invalid_game_name(self, redis_client):
        """Test creating game with invalid game name"""
        with pytest.raises(BadRequestException, match="Unknown game type"):
            await GameService.create_game(
                redis=redis_client,
                lobby_code="TEST999",
                game_name="invalid_game",
                player_ids=[1, 2]
            )
            
    async def test_get_game_success(self, redis_client):
        """Test getting game state"""
        # Create game first
        await GameService.create_game(
            redis=redis_client,
            lobby_code="GETTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Get game
        game = await GameService.get_game(redis_client, "GETTEST")
        
        assert game is not None
        assert game["lobby_code"] == "GETTEST"
        assert "game_state" in game
        assert "engine_config" in game
        
    async def test_get_game_not_found(self, redis_client):
        """Test getting non-existent game"""
        game = await GameService.get_game(redis_client, "NOTFOUND")
        assert game is None
        
    async def test_make_move_success(self, redis_client):
        """Test making a valid move"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="MOVETEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Make move
        result = await GameService.make_move(
            redis=redis_client,
            lobby_code="MOVETEST",
            player_id=1,
            move_data={"row": 0, "col": 0}
        )
        
        assert result["game_state"]["board"][0][0] == "X"
        assert result["game_state"]["move_count"] == 1
        assert result["result"] == GameResult.IN_PROGRESS.value
        assert result["current_turn_player_id"] == 2  # Turn advanced
        
    async def test_make_move_wrong_turn(self, redis_client):
        """Test making a move when it's not player's turn"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TURNTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Try to make move as player 2 (but it's player 1's turn)
        with pytest.raises(BadRequestException, match="not your turn"):
            await GameService.make_move(
                redis=redis_client,
                lobby_code="TURNTEST",
                player_id=2,
                move_data={"row": 0, "col": 0}
            )
            
    async def test_make_move_invalid_position(self, redis_client):
        """Test making a move to invalid position"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="INVALIDTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Try to make move to occupied position
        await GameService.make_move(
            redis=redis_client,
            lobby_code="INVALIDTEST",
            player_id=1,
            move_data={"row": 0, "col": 0}
        )
        
        # Player 2's turn, try same position
        with pytest.raises(BadRequestException, match="occupied"):
            await GameService.make_move(
                redis=redis_client,
                lobby_code="INVALIDTEST",
                player_id=2,
                move_data={"row": 0, "col": 0}
            )
            
    async def test_game_win_detection(self, redis_client):
        """Test that game detects win condition"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="WINTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Play moves to create a win for player 1
        # Player 1: (0,0), (1,1), (2,2) - diagonal
        # Player 2: (0,1), (0,2)
        moves = [
            (1, {"row": 0, "col": 0}),
            (2, {"row": 0, "col": 1}),
            (1, {"row": 1, "col": 1}),
            (2, {"row": 0, "col": 2}),
            (1, {"row": 2, "col": 2}),  # Winning move
        ]
        
        for player_id, move_data in moves[:-1]:
            await GameService.make_move(
                redis=redis_client,
                lobby_code="WINTEST",
                player_id=player_id,
                move_data=move_data
            )
        
        # Final move should trigger win
        result = await GameService.make_move(
            redis=redis_client,
            lobby_code="WINTEST",
            player_id=1,
            move_data={"row": 2, "col": 2}
        )
        
        assert result["result"] == GameResult.PLAYER_WIN.value
        assert result["winner_id"] == 1
        
    async def test_game_draw_detection(self, redis_client):
        """Test that game detects draw condition"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="DRAWTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Play moves to create a draw
        # X O X
        # X O O
        # O X X
        moves = [
            (1, {"row": 0, "col": 0}),  # X
            (2, {"row": 0, "col": 1}),  # O
            (1, {"row": 0, "col": 2}),  # X
            (2, {"row": 1, "col": 1}),  # O
            (1, {"row": 1, "col": 0}),  # X
            (2, {"row": 1, "col": 2}),  # O
            (1, {"row": 2, "col": 1}),  # X
            (2, {"row": 2, "col": 0}),  # O
            (1, {"row": 2, "col": 2}),  # X - Final move, board full
        ]
        
        result = None
        for player_id, move_data in moves:
            result = await GameService.make_move(
                redis=redis_client,
                lobby_code="DRAWTEST",
                player_id=player_id,
                move_data=move_data
            )
        
        assert result["result"] == GameResult.DRAW.value
        assert result["winner_id"] is None
        
    async def test_forfeit_game(self, redis_client):
        """Test forfeiting a game"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="FORFTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Player 1 forfeits
        result = await GameService.forfeit_game(
            redis=redis_client,
            lobby_code="FORFTEST",
            player_id=1
        )
        
        assert result["result"] == GameResult.FORFEIT.value
        assert result["winner_id"] == 2
        assert result["game_state"]["forfeited_by"] == 1
        
    async def test_delete_game(self, redis_client):
        """Test deleting a game"""
        # Create game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="DELTEST",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Verify it exists
        game = await GameService.get_game(redis_client, "DELTEST")
        assert game is not None
        
        # Delete it
        await GameService.delete_game(redis_client, "DELTEST")
        
        # Verify it's gone
        game = await GameService.get_game(redis_client, "DELTEST")
        assert game is None
        
    async def test_get_available_games(self):
        """Test getting list of available games"""
        games = GameService.get_available_games()
        
        assert isinstance(games, list)
        assert "tictactoe" in games
