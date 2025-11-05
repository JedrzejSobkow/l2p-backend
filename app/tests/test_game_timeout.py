# app/tests/test_game_timeout.py

import pytest
from datetime import datetime, UTC, timedelta
from services.games.tictactoe_engine import TicTacToeEngine
from services.game_engine_interface import GameResult, TimeoutType


class TestGameTimeout:
    """Tests for game timeout functionality"""
    
    def test_initialization_no_timeout(self):
        """Test initialization without timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        
        assert engine.timeout_type == TimeoutType.NONE
        assert engine.timeout_seconds == 0
    
    def test_initialization_per_turn_timeout(self):
        """Test initialization with per-turn timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        
        assert engine.timeout_type == TimeoutType.PER_TURN
        assert engine.timeout_seconds == 60
    
    def test_initialization_total_time_timeout(self):
        """Test initialization with total time timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        
        assert engine.timeout_type == TimeoutType.TOTAL_TIME
        assert engine.timeout_seconds == 300
    
    def test_initialization_invalid_timeout(self):
        """Test that initialization fails with invalid timeout configuration"""
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            TicTacToeEngine("TEST123", [1, 2], rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 0
            })
    
    def test_timing_state_initialization_no_timeout(self):
        """Test timing state is initialized correctly without timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert "timing" in state
        timing = state["timing"]
        assert timing["timeout_type"] == "none"
        assert timing["timeout_seconds"] == 0
        assert timing["turn_start_time"] is None
    
    def test_timing_state_initialization_per_turn(self):
        """Test timing state is initialized correctly with per-turn timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        
        assert "timing" in state
        timing = state["timing"]
        assert timing["timeout_type"] == "per_turn"
        assert timing["timeout_seconds"] == 60
        assert timing["turn_start_time"] is None
    
    def test_timing_state_initialization_total_time(self):
        """Test timing state is initialized correctly with total time timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        
        assert "timing" in state
        timing = state["timing"]
        assert timing["timeout_type"] == "total_time"
        assert timing["timeout_seconds"] == 300
        assert timing["turn_start_time"] is None
        assert "player_time_remaining" in timing
        assert timing["player_time_remaining"]["1"] == 300
        assert timing["player_time_remaining"]["2"] == 300
    
    def test_start_turn_no_timeout(self):
        """Test starting a turn without timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.start_turn(state)
        
        # Turn start time should still be None when no timeout is configured
        assert state["timing"]["turn_start_time"] is None
    
    def test_start_turn_with_timeout(self):
        """Test starting a turn with timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        
        state = engine.start_turn(state)
        
        # Turn start time should be set
        assert state["timing"]["turn_start_time"] is not None
        turn_start = datetime.fromisoformat(state["timing"]["turn_start_time"])
        assert isinstance(turn_start, datetime)
    
    def test_check_timeout_no_timeout_configured(self):
        """Test checking timeout when no timeout is configured"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is False
        assert winner_id is None
    
    def test_check_timeout_per_turn_not_expired(self):
        """Test checking timeout when per-turn timeout has not expired"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is False
        assert winner_id is None
    
    def test_check_timeout_per_turn_expired(self):
        """Test checking timeout when per-turn timeout has expired"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 1  # 1 second timeout
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is True
        assert winner_id == 2  # Player 2 wins because Player 1 timed out
        assert engine.game_result == GameResult.TIMEOUT
    
    def test_check_timeout_total_time_not_expired(self):
        """Test checking timeout when total time has not expired"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is False
        assert winner_id is None
    
    def test_check_timeout_total_time_expired(self):
        """Test checking timeout when total time has expired"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 10
        })
        state = engine.initialize_game_state()
        
        # Set player 1's remaining time to very low
        state["timing"]["player_time_remaining"]["1"] = 1
        
        # Set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is True
        assert winner_id == 2  # Player 2 wins because Player 1 timed out
        assert engine.game_result == GameResult.TIMEOUT
    
    def test_consume_turn_time_no_timeout(self):
        """Test consuming turn time when no timeout is configured"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        state = engine.consume_turn_time(state)
        
        # Should return unchanged state
        assert state["timing"]["turn_start_time"] is None
    
    def test_consume_turn_time_total_time(self):
        """Test consuming turn time with total time timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=5)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        initial_time = state["timing"]["player_time_remaining"]["1"]
        state = engine.consume_turn_time(state)
        
        # Player's time should be reduced
        final_time = state["timing"]["player_time_remaining"]["1"]
        assert final_time < initial_time
        assert final_time >= initial_time - 6  # Allow some tolerance
        
        # Turn start time should be cleared
        assert state["timing"]["turn_start_time"] is None
    
    def test_get_remaining_time_no_timeout(self):
        """Test getting remaining time when no timeout is configured"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        remaining_time = engine.get_remaining_time(state)
        
        assert remaining_time is None
    
    def test_get_remaining_time_per_turn(self):
        """Test getting remaining time with per-turn timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 60
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time is not None
        assert 59 <= remaining_time <= 60  # Should be close to 60 seconds
    
    def test_get_remaining_time_total_time(self):
        """Test getting remaining time with total time timeout"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        remaining_time = engine.get_remaining_time(state, 1)
        
        assert remaining_time is not None
        assert 299 <= remaining_time <= 300  # Should be close to 300 seconds
    
    def test_validate_move_timeout(self):
        """Test that move validation fails when timeout occurs"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 1
        })
        state = engine.initialize_game_state()
        
        # Manually set turn start time to past
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        result = engine.validate_move(state, 1, {"row": 0, "col": 0})
        
        assert result.valid is False
        assert "Time limit exceeded" in result.error_message
    
    def test_game_info_includes_timeout_rules(self):
        """Test that game info includes timeout configuration options"""
        game_info = TicTacToeEngine.get_game_info()
        
        assert "timeout_type" in game_info.supported_rules
        assert "timeout_seconds" in game_info.supported_rules
        
        timeout_type_rule = game_info.supported_rules["timeout_type"]
        assert timeout_type_rule.default == "none"
        
        timeout_seconds_rule = game_info.supported_rules["timeout_seconds"]
        assert timeout_seconds_rule.type == "integer"
        assert timeout_seconds_rule.min == 10
        assert timeout_seconds_rule.max == 3600
