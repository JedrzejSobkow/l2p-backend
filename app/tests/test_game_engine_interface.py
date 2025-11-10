# app/tests/test_game_engine_interface.py

import pytest
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, Optional
from services.games.tictactoe_engine import TicTacToeEngine
from services.game_engine_interface import (
    GameResult,
    TimeoutType,
    TimeoutAction,
    MoveValidationResult,
    GameEngineInterface,
)
from schemas.game_schema import GameInfo, GameRuleOption


class MockMultiplayerEngine(GameEngineInterface):
    """Mock game engine for testing multiplayer scenarios"""
    
    def _initialize_game_specific_state(self) -> Dict[str, Any]:
        return {"mock_state": "initialized"}
    
    def _validate_game_specific_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        return MoveValidationResult(valid=True)
    
    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        return game_state
    
    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        return (GameResult.IN_PROGRESS, None)
    
    @classmethod
    def get_game_name(cls) -> str:
        return "mock_multiplayer"
    
    @classmethod
    def get_game_info(cls) -> GameInfo:
        return GameInfo(
            game_name="mock_multiplayer",
            display_name="Mock Multiplayer Game",
            min_players=2,
            max_players=4,
            description="Mock game for testing",
            supported_rules={},
            turn_based=True,
            category="test"
        )


class TestGameEngineInterfaceExtended:
    """Extended tests for GameEngineInterface to improve coverage"""
    
    def test_timeout_action_skip_turn(self):
        """Test timeout action SKIP_TURN"""
        engine = MockMultiplayerEngine("TEST123", [1, 2, 3], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 1,
            "timeout_action": "skip_turn"
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is True
        assert winner_id is None  # No winner, turn is just skipped
        assert engine.game_result == GameResult.IN_PROGRESS  # Game continues
    
    def test_timeout_action_end_game_multiplayer(self):
        """Test timeout action END_GAME with more than 2 players"""
        engine = MockMultiplayerEngine("TEST123", [1, 2, 3], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 1,
            "timeout_action": "end_game"
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is True
        assert winner_id is None  # No single winner in multiplayer
        assert engine.game_result == GameResult.TIMEOUT
    
    def test_timeout_action_eliminate_player(self):
        """Test timeout action ELIMINATE_PLAYER"""
        engine = MockMultiplayerEngine("TEST123", [1, 2, 3], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 1,
            "timeout_action": "eliminate_player"
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is True
        assert winner_id is None  # Treated like skip turn for now
    
    def test_validate_move_wrong_player(self):
        """Test that validation fails when it's not the player's turn"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 2 tries to move but it's player 1's turn
        result = engine.validate_move(state, 2, {"row": 0, "col": 0})
        
        assert result.valid is False
        assert "It's not your turn" in result.error_message
    
    def test_validate_move_game_already_ended(self):
        """Test that validation fails when game has already ended"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Manually end the game
        engine.game_result = GameResult.PLAYER_WIN
        engine.winner_id = 1
        
        result = engine.validate_move(state, 1, {"row": 0, "col": 0})
        
        assert result.valid is False
        assert "Game has already ended" in result.error_message
    
    def test_check_timeout_no_turn_start_time(self):
        """Test check_timeout when turn hasn't started yet"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        # Don't call start_turn, so turn_start_time is None
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is False
        assert winner_id is None
    
    def test_consume_turn_time_no_start_time(self):
        """Test consume_turn_time when turn hasn't started"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        # Don't set turn_start_time
        
        initial_time = state["timing"]["player_time_remaining"]["1"]
        state = engine.consume_turn_time(state)
        final_time = state["timing"]["player_time_remaining"]["1"]
        
        # Time should not change
        assert initial_time == final_time
    
    def test_consume_turn_time_per_turn_timeout(self):
        """Test consume_turn_time with per-turn timeout (should just clear start time)"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        state = engine.consume_turn_time(state)
        
        # Turn start time should be cleared
        assert state["timing"]["turn_start_time"] is None
    
    def test_get_remaining_time_per_turn_not_started(self):
        """Test get_remaining_time for per-turn when turn hasn't started"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        # Don't call start_turn
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time == 60  # Full time available
    
    def test_get_remaining_time_per_turn_elapsed(self):
        """Test get_remaining_time for per-turn with some time elapsed"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to 5 seconds ago
        past_time = datetime.now(UTC) - timedelta(seconds=5)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time is not None
        assert 54 <= remaining_time <= 56  # Should be around 55 seconds
    
    def test_get_remaining_time_total_time_not_current_player(self):
        """Test get_remaining_time for total time when checking non-current player"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)  # Player 1's turn
        
        # Check player 2's remaining time (not current player)
        remaining_time = engine.get_remaining_time(state, 2)
        
        assert remaining_time == 300  # Full time since they haven't played yet
    
    def test_get_remaining_time_total_time_current_player_elapsed(self):
        """Test get_remaining_time for total time with current player having elapsed time"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to 10 seconds ago for player 1
        past_time = datetime.now(UTC) - timedelta(seconds=10)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time is not None
        assert 289 <= remaining_time <= 291  # Should be around 290 seconds
    
    def test_get_remaining_time_default_to_current_player(self):
        """Test get_remaining_time defaults to current player when player_id not specified"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        # Don't specify player_id, should default to current player (player 1)
        remaining_time = engine.get_remaining_time(state)
        
        assert remaining_time is not None
        assert 59 <= remaining_time <= 60
    
    def test_forfeit_game_multiplayer(self):
        """Test forfeit_game with more than 2 players"""
        engine = MockMultiplayerEngine("TEST123", [1, 2, 3])
        
        result, winner_id = engine.forfeit_game(1)
        
        assert result == GameResult.FORFEIT
        assert winner_id is None  # No single winner in multiplayer
        assert engine.game_result == GameResult.FORFEIT
        assert engine.winner_id is None
    
    def test_advance_turn_cycles_correctly(self):
        """Test that advance_turn cycles through all players"""
        engine = MockMultiplayerEngine("TEST123", [1, 2, 3])
        
        assert engine.current_player_id == 1
        engine.advance_turn()
        assert engine.current_player_id == 2
        engine.advance_turn()
        assert engine.current_player_id == 3
        engine.advance_turn()
        assert engine.current_player_id == 1  # Cycles back
    
    def test_move_validation_result_valid(self):
        """Test MoveValidationResult for valid move"""
        result = MoveValidationResult(valid=True)
        
        assert result.valid is True
        assert result.error_message is None
    
    def test_move_validation_result_invalid_with_message(self):
        """Test MoveValidationResult for invalid move with error message"""
        result = MoveValidationResult(valid=False, error_message="Invalid position")
        
        assert result.valid is False
        assert result.error_message == "Invalid position"
    
    def test_initialization_with_none_timeout_type(self):
        """Test initialization when timeout_type is None or empty"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": None
        })
        
        assert engine.timeout_type == TimeoutType.NONE
    
    def test_initialization_with_none_timeout_action(self):
        """Test initialization when timeout_action is None"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60,
            "timeout_action": None
        })
        
        assert engine.timeout_action == TimeoutAction.END_GAME
    
    def test_consume_turn_time_negative_time_protection(self):
        """Test that consume_turn_time doesn't set negative time"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        
        # Set player's remaining time very low
        state["timing"]["player_time_remaining"]["1"] = 1
        
        # Set turn start time to way in the past (more than remaining time)
        past_time = datetime.now(UTC) - timedelta(seconds=10)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        state = engine.consume_turn_time(state)
        
        # Time should be 0, not negative
        assert state["timing"]["player_time_remaining"]["1"] == 0
    
    def test_get_remaining_time_negative_protection_per_turn(self):
        """Test that get_remaining_time doesn't return negative for per-turn"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 10  # Use valid value from allowed list
        })
        state = engine.initialize_game_state()
        
        # Set turn start time way in the past
        past_time = datetime.now(UTC) - timedelta(seconds=20)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time == 0  # Should be 0, not negative
    
    def test_get_remaining_time_negative_protection_total_time(self):
        """Test that get_remaining_time doesn't return negative for total time"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        
        # Set player's remaining time very low and turn start way in past
        state["timing"]["player_time_remaining"]["1"] = 5
        past_time = datetime.now(UTC) - timedelta(seconds=10)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time == 0  # Should be 0, not negative
