# app/tests/test_game_service.py

import pytest
import json
from datetime import datetime, UTC, timedelta
from services.game_service import GameService
from services.game_engine_interface import GameResult
from exceptions.domain_exceptions import NotFoundException, BadRequestException


@pytest.mark.asyncio
class TestGameService:
    """Comprehensive tests for GameService"""
    
    # ============================================================================
    # CREATE GAME TESTS
    # ============================================================================
    
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
        
        # game_info is a GameInfo object, access supported_rules
        assert result["game_info"].supported_rules["board_size"].default == 3
        assert result["game_info"].supported_rules["win_length"].default == 3
        
    async def test_create_game_already_exists(self, redis_client):
        """Test that creating a game twice fails"""
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TEST789",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        with pytest.raises(BadRequestException, match="already in progress"):
            await GameService.create_game(
                redis=redis_client,
                lobby_code="TEST789",
                game_name="tictactoe",
                player_ids=[1, 2]
            )
    
    async def test_create_game_replace_finished_game(self, redis_client):
        """Test creating a new game when a finished game exists"""
        # Create and finish a game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="REPLACE1",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Forfeit to finish it
        await GameService.forfeit_game(
            redis=redis_client,
            lobby_code="REPLACE1",
            player_id=1
        )
        
        # Now create a new game with the same lobby code
        result = await GameService.create_game(
            redis=redis_client,
            lobby_code="REPLACE1",
            game_name="tictactoe",
            player_ids=[3, 4]
        )
        
        assert result["lobby_code"] == "REPLACE1"
        # Should have new players
        game = await GameService.get_game(redis_client, "REPLACE1")
        assert game["engine_config"]["player_ids"] == [3, 4]
        assert game["game_state"]["result"] == GameResult.IN_PROGRESS.value
            
    async def test_create_game_invalid_game_name(self, redis_client):
        """Test creating game with invalid game name"""
        with pytest.raises(BadRequestException, match="Unknown game type"):
            await GameService.create_game(
                redis=redis_client,
                lobby_code="TEST999",
                game_name="invalid_game",
                player_ids=[1, 2]
            )
    
    async def test_create_game_invalid_rules(self, redis_client):
        """Test creating game with invalid rules that cause ValueError"""
        # TicTacToe requires exactly 2 players
        with pytest.raises(BadRequestException, match="Failed to create game"):
            await GameService.create_game(
                redis=redis_client,
                lobby_code="INVALID1",
                game_name="tictactoe",
                player_ids=[1, 2, 3]  # Too many players
            )
    
    # ============================================================================
    # GET GAME TESTS
    # ============================================================================
            
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
    
    # ============================================================================
    # MAKE MOVE TESTS
    # ============================================================================
        
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
    
    async def test_make_move_game_not_found(self, redis_client):
        """Test making move when game doesn't exist"""
        with pytest.raises(NotFoundException, match="Game not found"):
            await GameService.make_move(
                redis=redis_client,
                lobby_code="NOEXIST",
                player_id=1,
                move_data={"row": 0, "col": 0}
            )
    
    async def test_make_move_state_not_found(self, redis_client):
        """Test making move when engine exists but state is missing"""
        # Create only engine config, not state
        engine_config = {
            "game_name": "tictactoe",
            "lobby_code": "NOSTATE",
            "player_ids": [1, 2],
            "rules": {},
            "current_turn_index": 0,
        }
        
        await redis_client.set(
            GameService._game_engine_key("NOSTATE"),
            json.dumps(engine_config)
        )
        
        with pytest.raises(NotFoundException, match="Game state not found"):
            await GameService.make_move(
                redis=redis_client,
                lobby_code="NOSTATE",
                player_id=1,
                move_data={"row": 0, "col": 0}
            )
    
    # ============================================================================
    # GAME RESULT TESTS
    # ============================================================================
            
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
    
    # ============================================================================
    # TIMEOUT TESTS
    # ============================================================================
    
    async def test_make_move_timeout_ends_game(self, redis_client):
        """Test timeout that ends the game"""
        # Create game with short timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TIMEOUT1",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "end_game"
            }
        )
        
        # Get the game state and manually set turn start time to past
        state_raw = await redis_client.get(GameService._game_state_key("TIMEOUT1"))
        game_state = json.loads(state_raw)
        
        # Set turn start time to 12 seconds ago (past the 10 second timeout)
        past_time = datetime.now(UTC) - timedelta(seconds=12)
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        
        await redis_client.set(
            GameService._game_state_key("TIMEOUT1"),
            json.dumps(game_state)
        )
        
        # Try to make a move - should fail with timeout
        with pytest.raises(BadRequestException, match="Time limit exceeded - game ended"):
            await GameService.make_move(
                redis=redis_client,
                lobby_code="TIMEOUT1",
                player_id=1,
                move_data={"row": 0, "col": 0}
            )
        
        # Verify game ended with timeout
        game = await GameService.get_game(redis_client, "TIMEOUT1")
        assert game["game_state"]["result"] == GameResult.TIMEOUT.value
    
    async def test_make_move_timeout_skips_turn(self, redis_client):
        """Test timeout that skips turn instead of ending game"""
        # Create game with skip turn action
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TIMEOUT2",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "skip_turn"
            }
        )
        
        # Get the game state and manually set turn start time to past
        state_raw = await redis_client.get(GameService._game_state_key("TIMEOUT2"))
        game_state = json.loads(state_raw)
        
        # Set turn start time to 12 seconds ago (past the 10 second timeout)
        past_time = datetime.now(UTC) - timedelta(seconds=12)
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        
        await redis_client.set(
            GameService._game_state_key("TIMEOUT2"),
            json.dumps(game_state)
        )
        
        # Try to make a move as player 1 - should fail and skip to player 2
        with pytest.raises(BadRequestException, match="your turn was skipped"):
            await GameService.make_move(
                redis=redis_client,
                lobby_code="TIMEOUT2",
                player_id=1,
                move_data={"row": 0, "col": 0}
            )
        
        # Verify turn advanced to player 2
        game = await GameService.get_game(redis_client, "TIMEOUT2")
        assert game["game_state"]["current_turn_player_id"] == 2
        assert game["game_state"]["result"] == GameResult.IN_PROGRESS.value
    
    # ============================================================================
    # FORFEIT TESTS
    # ============================================================================
        
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
    
    async def test_forfeit_game_not_found(self, redis_client):
        """Test forfeiting when game doesn't exist"""
        with pytest.raises(NotFoundException, match="Game not found"):
            await GameService.forfeit_game(
                redis=redis_client,
                lobby_code="NOEXIST",
                player_id=1
            )
    
    async def test_forfeit_game_state_not_found(self, redis_client):
        """Test forfeiting when engine exists but state is missing"""
        # Create only engine config
        engine_config = {
            "game_name": "tictactoe",
            "lobby_code": "FORFSTATE",
            "player_ids": [1, 2],
            "rules": {},
            "current_turn_index": 0,
        }
        
        await redis_client.set(
            GameService._game_engine_key("FORFSTATE"),
            json.dumps(engine_config)
        )
        
        with pytest.raises(NotFoundException, match="Game state not found"):
            await GameService.forfeit_game(
                redis=redis_client,
                lobby_code="FORFSTATE",
                player_id=1
            )
    
    # ============================================================================
    # TIMING INFO TESTS
    # ============================================================================
    
    async def test_get_timing_info_success(self, redis_client):
        """Test getting timing information for a game"""
        # Create game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TIMING1",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "total_time",
                "timeout_seconds": 300
            }
        )
        
        timing_info = await GameService.get_timing_info(redis_client, "TIMING1")
        
        assert timing_info is not None
        assert timing_info["timeout_type"] == "total_time"
        assert timing_info["timeout_seconds"] == 300
        assert timing_info["current_player_id"] == 1
        assert "player_time_remaining" in timing_info
        assert "1" in timing_info["player_time_remaining"]
        assert "2" in timing_info["player_time_remaining"]
    
    async def test_get_timing_info_no_timeout(self, redis_client):
        """Test getting timing info for game without timeout"""
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TIMING2",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        timing_info = await GameService.get_timing_info(redis_client, "TIMING2")
        
        assert timing_info is not None
        assert timing_info["timeout_type"] == "none"
        assert "player_time_remaining" not in timing_info
    
    async def test_get_timing_info_not_found(self, redis_client):
        """Test getting timing info when game doesn't exist"""
        timing_info = await GameService.get_timing_info(redis_client, "NOEXIST")
        assert timing_info is None
    
    async def test_get_timing_info_state_not_found(self, redis_client):
        """Test getting timing info when engine exists but state missing"""
        # Create only engine config
        engine_config = {
            "game_name": "tictactoe",
            "lobby_code": "TIMINGNOSTATE",
            "player_ids": [1, 2],
            "rules": {},
            "current_turn_index": 0,
        }
        
        await redis_client.set(
            GameService._game_engine_key("TIMINGNOSTATE"),
            json.dumps(engine_config)
        )
        
        timing_info = await GameService.get_timing_info(redis_client, "TIMINGNOSTATE")
        assert timing_info is None
    
    # ============================================================================
    # TIMEOUT KEY MANAGEMENT TESTS
    # ============================================================================
    
    async def test_set_timeout_key_with_timeout(self, redis_client):
        """Test setting timeout key when timeout is configured"""
        # Create game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="SETKEY1",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 60
            }
        )
        
        # Check that timeout key exists
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("SETKEY1")
        value = await redis_client.get(timeout_key)
        assert value is not None
    
    async def test_set_timeout_key_no_timeout(self, redis_client):
        """Test that no timeout key is set when timeout is not configured"""
        await GameService.create_game(
            redis=redis_client,
            lobby_code="SETKEY2",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Check that timeout key doesn't exist
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("SETKEY2")
        value = await redis_client.get(timeout_key)
        assert value is None
    
    async def test_set_timeout_key_no_remaining_time(self, redis_client):
        """Test that timeout key is not set when no time remaining"""
        # Create game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="SETKEY3",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "total_time",
                "timeout_seconds": 10
            }
        )
        
        # Manually set player's remaining time to 0
        state_raw = await redis_client.get(GameService._game_state_key("SETKEY3"))
        game_state = json.loads(state_raw)
        game_state["timing"]["player_time_remaining"]["1"] = 0
        
        await redis_client.set(
            GameService._game_state_key("SETKEY3"),
            json.dumps(game_state)
        )
        
        # Load engine and try to set timeout key
        engine = await GameService._load_engine(redis_client, "SETKEY3")
        
        # Clear existing timeout key first
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("SETKEY3")
        await redis_client.delete(timeout_key)
        
        # Try to set timeout key with 0 remaining time
        await GameService._set_timeout_key(redis_client, engine, game_state, "SETKEY3")
        
        # Timeout key should not be set
        value = await redis_client.get(timeout_key)
        assert value is None
    
    async def test_clear_timeout_key(self, redis_client):
        """Test clearing timeout key"""
        # Create game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="CLEARKEY1",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 60
            }
        )
        
        # Verify timeout key exists
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("CLEARKEY1")
        value = await redis_client.get(timeout_key)
        assert value is not None
        
        # Clear it
        await GameService._clear_timeout_key(redis_client, "CLEARKEY1")
        
        # Verify it's gone
        value = await redis_client.get(timeout_key)
        assert value is None
    
    async def test_game_finished_clears_timeout_key(self, redis_client):
        """Test that timeout key is cleared when game finishes"""
        # Create game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="FINISH1",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 60
            }
        )
        
        # Verify timeout key exists
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("FINISH1")
        value = await redis_client.get(timeout_key)
        assert value is not None
        
        # Forfeit to end game
        await GameService.forfeit_game(
            redis=redis_client,
            lobby_code="FINISH1",
            player_id=1
        )
        
        # Verify timeout key is cleared
        value = await redis_client.get(timeout_key)
        assert value is None
    
    async def test_make_move_clears_timeout_on_win(self, redis_client):
        """Test that timeout key is cleared when game ends by win"""
        # Create game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="WIN_TIMEOUT",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 60
            }
        )
        
        # Play moves to create a win
        moves = [
            (1, {"row": 0, "col": 0}),
            (2, {"row": 0, "col": 1}),
            (1, {"row": 1, "col": 1}),
            (2, {"row": 0, "col": 2}),
            (1, {"row": 2, "col": 2}),  # Winning move
        ]
        
        for player_id, move_data in moves:
            await GameService.make_move(
                redis=redis_client,
                lobby_code="WIN_TIMEOUT",
                player_id=player_id,
                move_data=move_data
            )
        
        # Verify timeout key is cleared
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("WIN_TIMEOUT")
        value = await redis_client.get(timeout_key)
        assert value is None
    
    async def test_make_move_updates_timeout_key(self, redis_client):
        """Test that timeout key is updated after each move"""
        # Create game with total time timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="UPDATE_TIMEOUT",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "total_time",
                "timeout_seconds": 300
            }
        )
        
        # Make a move
        await GameService.make_move(
            redis=redis_client,
            lobby_code="UPDATE_TIMEOUT",
            player_id=1,
            move_data={"row": 0, "col": 0}
        )
        
        # Verify timeout key still exists (for player 2's turn now)
        from services.timeout_checker import TimeoutChecker
        timeout_key = TimeoutChecker.get_timeout_key("UPDATE_TIMEOUT")
        value = await redis_client.get(timeout_key)
        assert value is not None
    
    # ============================================================================
    # ENGINE LOADING TESTS
    # ============================================================================
    
    async def test_load_engine_not_found(self, redis_client):
        """Test loading engine when game doesn't exist"""
        engine = await GameService._load_engine(redis_client, "NOTEXIST")
        assert engine is None
    
    async def test_load_engine_unknown_game_type(self, redis_client):
        """Test loading engine with corrupted/unknown game type in storage"""
        # Manually insert invalid game config
        invalid_config = {
            "game_name": "unknown_game_type",
            "lobby_code": "CORRUPT",
            "player_ids": [1, 2],
            "rules": {},
            "current_turn_index": 0,
        }
        
        await redis_client.set(
            GameService._game_engine_key("CORRUPT"),
            json.dumps(invalid_config)
        )
        
        engine = await GameService._load_engine(redis_client, "CORRUPT")
        assert engine is None
    
    # ============================================================================
    # DELETE GAME TESTS
    # ============================================================================
        
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
    
    # ============================================================================
    # UTILITY TESTS
    # ============================================================================
        
    async def test_get_available_games(self):
        """Test getting list of available games"""
        games = GameService.get_available_games()
        
        assert isinstance(games, list)
        assert "tictactoe" in games
