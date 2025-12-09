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
    
    def test_timeout_seconds_must_be_positive_per_turn(self):
        """Test that timeout_seconds must be positive when timeout is enabled (per_turn)"""
        with pytest.raises(ValueError, match="timeout_seconds must be positive when timeout is enabled"):
            MockMultiplayerEngine("TEST123", [1, 2], rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 0  # Invalid: should be positive
            })
    
    def test_timeout_seconds_must_be_positive_total_time(self):
        """Test that timeout_seconds must be positive when timeout is enabled (total_time)"""
        with pytest.raises(ValueError, match="timeout_seconds must be positive when timeout is enabled"):
            MockMultiplayerEngine("TEST123", [1, 2], rules={
                "timeout_type": "total_time",
                "timeout_seconds": -10  # Invalid: negative
            })
    
    def test_rule_validation_float_type(self):
        """Test rule validation for float type"""
        class MockFloatEngine(MockMultiplayerEngine):
            @classmethod
            def get_game_info(cls) -> GameInfo:
                return GameInfo(
                    game_name="mock_float",
                    display_name="Mock Float Game",
                    min_players=2,
                    max_players=4,
                    description="Mock game for testing float rules",
                    supported_rules={
                        "speed_multiplier": GameRuleOption(
                            type="float",
                            default=1.0,
                            description="Game speed multiplier"
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Valid float
        engine = MockFloatEngine("TEST123", [1, 2], rules={"speed_multiplier": 1.5})
        assert engine.rules["speed_multiplier"] == 1.5
        
        # Invalid: boolean
        with pytest.raises(ValueError, match="speed_multiplier must be a number"):
            MockFloatEngine("TEST123", [1, 2], rules={"speed_multiplier": True})
        
        # Valid: int should also work for float type
        engine2 = MockFloatEngine("TEST123", [1, 2], rules={"speed_multiplier": 2})
        assert engine2.rules["speed_multiplier"] == 2
    
    def test_rule_validation_boolean_type(self):
        """Test rule validation for boolean type"""
        class MockBoolEngine(MockMultiplayerEngine):
            @classmethod
            def get_game_info(cls) -> GameInfo:
                return GameInfo(
                    game_name="mock_bool",
                    display_name="Mock Bool Game",
                    min_players=2,
                    max_players=4,
                    description="Mock game for testing boolean rules",
                    supported_rules={
                        "friendly_fire": GameRuleOption(
                            type="boolean",
                            default=False,
                            description="Enable friendly fire"
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Valid boolean
        engine = MockBoolEngine("TEST123", [1, 2], rules={"friendly_fire": True})
        assert engine.rules["friendly_fire"] is True
        
        # Invalid: string
        with pytest.raises(ValueError, match="friendly_fire must be a boolean"):
            MockBoolEngine("TEST123", [1, 2], rules={"friendly_fire": "yes"})
    
    def test_rule_validation_string_type(self):
        """Test rule validation for string type"""
        class MockStringEngine(MockMultiplayerEngine):
            @classmethod
            def get_game_info(cls) -> GameInfo:
                return GameInfo(
                    game_name="mock_string",
                    display_name="Mock String Game",
                    min_players=2,
                    max_players=4,
                    description="Mock game for testing string rules",
                    supported_rules={
                        "difficulty": GameRuleOption(
                            type="string",
                            default="normal",
                            allowed_values=["easy", "normal", "hard"],
                            description="Game difficulty"
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Valid string
        engine = MockStringEngine("TEST123", [1, 2], rules={"difficulty": "hard"})
        assert engine.rules["difficulty"] == "hard"
        
        # Invalid: integer
        with pytest.raises(ValueError, match="difficulty must be a string"):
            MockStringEngine("TEST123", [1, 2], rules={"difficulty": 123})
    
    def test_rule_validation_allowed_values(self):
        """Test rule validation for allowed_values constraint"""
        class MockConstraintEngine(MockMultiplayerEngine):
            @classmethod
            def get_game_info(cls) -> GameInfo:
                return GameInfo(
                    game_name="mock_constraint",
                    display_name="Mock Constraint Game",
                    min_players=2,
                    max_players=4,
                    description="Mock game for testing allowed values",
                    supported_rules={
                        "mode": GameRuleOption(
                            type="string",
                            default="standard",
                            allowed_values=["standard", "turbo", "classic"],
                            description="Game mode"
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Valid value from allowed list
        engine = MockConstraintEngine("TEST123", [1, 2], rules={"mode": "turbo"})
        assert engine.rules["mode"] == "turbo"
        
        # Invalid: not in allowed values
        with pytest.raises(ValueError, match="mode value 'invalid' is not in allowed values"):
            MockConstraintEngine("TEST123", [1, 2], rules={"mode": "invalid"})
    
    def test_rule_validation_number_type(self):
        """Test rule validation for 'number' type (accepts int or float)"""
        class MockNumberEngine(MockMultiplayerEngine):
            @classmethod
            def get_game_info(cls) -> GameInfo:
                return GameInfo(
                    game_name="mock_number",
                    display_name="Mock Number Game",
                    min_players=2,
                    max_players=4,
                    description="Mock game for testing number rules",
                    supported_rules={
                        "score_multiplier": GameRuleOption(
                            type="number",
                            default=1.0,
                            description="Score multiplier"
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Valid: integer
        engine1 = MockNumberEngine("TEST123", [1, 2], rules={"score_multiplier": 2})
        assert engine1.rules["score_multiplier"] == 2
        
        # Valid: float
        engine2 = MockNumberEngine("TEST123", [1, 2], rules={"score_multiplier": 1.5})
        assert engine2.rules["score_multiplier"] == 1.5
        
        # Invalid: boolean
        with pytest.raises(ValueError, match="score_multiplier must be a number"):
            MockNumberEngine("TEST123", [1, 2], rules={"score_multiplier": False})
    
    def test_check_timeout_total_time_exceeded(self):
        """Test timeout check for total time mode when time is exceeded"""
        engine = MockMultiplayerEngine("TEST123", [1, 2], rules={
            "timeout_type": "total_time",
            "timeout_seconds": 300,
            "timeout_action": "end_game"
        })
        state = engine.initialize_game_state()
        
        # Set player's remaining time very low
        state["timing"]["player_time_remaining"]["1"] = 5
        # Set turn start time to past (more than 5 seconds ago)
        past_time = datetime.now(UTC) - timedelta(seconds=10)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is True
        assert winner_id == 2  # Other player wins
        assert engine.game_result == GameResult.TIMEOUT
    
    def test_validate_move_with_timeout(self):
        """Test that validate_move rejects moves when timeout has occurred"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 10  # Use valid value for TicTacToe
        })
        state = engine.initialize_game_state()
        
        # Set turn start time way in past to trigger timeout
        past_time = datetime.now(UTC) - timedelta(seconds=20)
        state["timing"]["turn_start_time"] = past_time.isoformat()
        
        # Try to make a move - should fail due to timeout
        result = engine.validate_move(state, 1, {"row": 0, "col": 0})
        
        assert result.valid is False
        assert "Time limit exceeded" in result.error_message
    
    def test_check_timeout_no_timeout_when_within_limit(self):
        """Test that check_timeout returns False when within time limit"""
        engine = MockMultiplayerEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 30
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        # Check immediately - should not have timed out
        timeout_occurred, winner_id = engine.check_timeout(state)
        
        assert timeout_occurred is False
        assert winner_id is None
    
    def test_consume_turn_time_per_turn_mode_clears_start_time(self):
        """Test that consume_turn_time clears turn_start_time in per_turn mode"""
        engine = MockMultiplayerEngine("TEST123", [1, 2], rules={
            "timeout_type": "per_turn",
            "timeout_seconds": 30
        })
        state = engine.initialize_game_state()
        state = engine.start_turn(state)
        
        # Turn start time should be set
        assert state["timing"]["turn_start_time"] is not None
        
        # Consume turn time
        state = engine.consume_turn_time(state)
        
        # Turn start time should be cleared
        assert state["timing"]["turn_start_time"] is None
    
    def test_get_remaining_time_returns_none_for_unknown_timeout_type(self):
        """Test that get_remaining_time returns None for edge cases"""
        engine = MockMultiplayerEngine("TEST123", [1, 2], rules={
            "timeout_type": "none"
        })
        state = engine.initialize_game_state()
        
        # Should return None for no timeout
        remaining = engine.get_remaining_time(state, 1)
        assert remaining is None

    def test_validate_rules_float_type(self):
        """Test validating float/number type rules"""
        from schemas.game_schema import GameRuleOption, GameInfo
        
        # Create mock engine with float rule
        class FloatRuleEngine(GameEngineInterface):
            def _initialize_game_specific_state(self):
                return {}
            
            def _validate_game_specific_move(self, game_state, player_id, move_data):
                return MoveValidationResult(valid=True)
            
            def apply_move(self, game_state, player_id, move_data):
                return game_state
            
            def check_game_result(self, game_state):
                return (GameResult.IN_PROGRESS, None)
            
            @classmethod
            def get_game_name(cls):
                return "float_test"
            
            @classmethod
            def get_game_info(cls):
                return GameInfo(
                    game_name="float_test",
                    display_name="Float Test",
                    min_players=2,
                    max_players=2,
                    description="Test",
                    supported_rules={
                        "float_rule": GameRuleOption(
                            type="float",
                            default=1.5,
                            description="A float rule",
                            allowed_values=None
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Valid float
        engine = FloatRuleEngine(lobby_code="TEST1", player_ids=[1, 2], rules={"float_rule": 2.5})
        assert engine.rules["float_rule"] == 2.5
        
        # Valid int (should be accepted as float)
        engine = FloatRuleEngine(lobby_code="TEST2", player_ids=[1, 2], rules={"float_rule": 3})
        assert engine.rules["float_rule"] == 3
        
        # Invalid - boolean should raise error
        with pytest.raises(ValueError) as exc:
            FloatRuleEngine(lobby_code="TEST3", player_ids=[1, 2], rules={"float_rule": True})
        assert "must be" in str(exc.value).lower()
    
    def test_abstract_methods(self):
        """Test that abstract methods exist and are documented"""
        # This test documents that apply_move is abstract
        # The pass statement in the base class (line 152) is unreachable
        # because Python enforces @abstractmethod decoration
        from abc import ABC
        
        assert issubclass(GameEngineInterface, ABC)
        assert hasattr(GameEngineInterface, 'apply_move')
        assert hasattr(GameEngineInterface.apply_move, '__isabstractmethod__')
        assert GameEngineInterface.apply_move.__isabstractmethod__ is True


@pytest.mark.asyncio
class TestGameEngineEdgeCases:
    """Test edge cases and unpokryte code paths"""
    
    async def test_rule_validation_invalid_integer_type(self):
        """Test validation error for non-integer value (line 109)"""
        class IntRuleEngine(GameEngineInterface):
            def _initialize_game_specific_state(self):
                return {}
            
            def _validate_game_specific_move(self, game_state, player_id, move_data):
                return MoveValidationResult(True)
            
            def apply_move(self, game_state, player_id, move_data):
                return game_state
            
            def check_game_result(self, game_state):
                return (GameResult.IN_PROGRESS, None)
            
            @classmethod
            def get_game_name(cls):
                return "int_test"
            
            @classmethod
            def get_game_info(cls):
                return GameInfo(
                    game_name="int_test",
                    display_name="Integer Test",
                    min_players=2,
                    max_players=2,
                    description="Test integer rules",
                    supported_rules={
                        "count": GameRuleOption(
                            type="integer",
                            default=5,
                            description="Count value"
                        )
                    },
                    turn_based=True,
                    category="test"
                )
        
        # Invalid - string instead of integer (line 109)
        with pytest.raises(ValueError, match="must be an integer"):
            IntRuleEngine("TEST", [1, 2], rules={"count": "five"})
    
    async def test_check_timeout_no_action_configured(self):
        """Test check_timeout returns False when no timeout occurred (line 343)"""
        # Engine with timeout configured
        engine = MockMultiplayerEngine(
            "TEST",
            [1, 2, 3],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 30,
            }
        )
        
        game_state = engine.initialize_game_state()
        # Set recent turn start time - no timeout
        game_state["timing"]["turn_start_time"] = datetime.now(UTC).isoformat()
        
        # Should return False, None when no timeout occurred (line 343)
        timeout_occurred, _ = engine.check_timeout(game_state)
        assert timeout_occurred is False  # Line 343
    
    async def test_consume_turn_time_with_no_timeout(self):
        """Test consume_turn_time returns early when timeout_type is NONE (line 356)"""
        engine = MockMultiplayerEngine("TEST", [1, 2, 3])  # No timeout configured
        
        game_state = engine.initialize_game_state()
        result = engine.consume_turn_time(game_state)
        
        # Should return unchanged when no timeout (line 356)
        assert result == game_state
    
    async def test_get_remaining_time_unknown_type(self):
        """Test get_remaining_time returns None for unknown timeout type (line 425)"""
        engine = MockMultiplayerEngine("TEST", [1, 2, 3])
        game_state = engine.initialize_game_state()
        
        # Manually set an invalid timeout_type to trigger line 425
        engine.timeout_type = "INVALID_TYPE"  # Not a valid TimeoutType
        
        remaining = engine.get_remaining_time(game_state)
        assert remaining is None  # Line 425
    
    async def test_forfeit_two_player_winner_assignment(self):
        """Test forfeit_game sets winner_id for 2-player games (line 464)"""
        engine = MockMultiplayerEngine("TEST", [100, 200])  # 2 players
        
        # Player 100 forfeits
        result, winner_id = engine.forfeit_game(100)
        
        # Winner should be player 200 (line 464)
        assert result == GameResult.FORFEIT
        assert winner_id == 200
        assert engine.winner_id == 200
    
    async def test_calculate_elo_adjustments_with_winner(self):
        """Test calculate_elo_adjustments when there's a winner (lines 478-489)"""
        engine = MockMultiplayerEngine("TEST", [1, 2, 3])
        game_state = {"winner_identifier": 2}
        
        adjustments = engine.calculate_elo_adjustments(game_state)
        
        # Winner gets +1, losers get -1 (lines 478-489)
        assert adjustments[1] == -1
        assert adjustments[2] == 1
        assert adjustments[3] == -1
    
    async def test_calculate_elo_adjustments_no_winner(self):
        """Test calculate_elo_adjustments when there's no winner"""
        engine = MockMultiplayerEngine("TEST", [1, 2, 3])
        game_state = {}  # No winner_id
        
        adjustments = engine.calculate_elo_adjustments(game_state)
        
        # No adjustments when no winner
        assert adjustments == {}