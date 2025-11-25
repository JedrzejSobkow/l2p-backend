# app/services/game_engine_interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, UTC
from schemas.game_schema import GameInfo
import logging

logger = logging.getLogger(__name__)


class GameResult(Enum):
    """Possible game results"""
    IN_PROGRESS = "in_progress"
    PLAYER_WIN = "player_win"
    DRAW = "draw"
    FORFEIT = "forfeit"
    TIMEOUT = "timeout"


class TimeoutType(Enum):
    """Types of timeout configurations"""
    NONE = "none"
    TOTAL_TIME = "total_time"
    PER_TURN = "per_turn"


class TimeoutAction(Enum):
    """What happens when a player times out"""
    END_GAME = "end_game"  # Game ends, other player(s) win (e.g., chess, 2-player games)
    SKIP_TURN = "skip_turn"  # Player's turn is skipped, game continues (e.g., UNO, 4-player games)
    ELIMINATE_PLAYER = "eliminate_player"  # Player is eliminated, others continue


class MoveValidationResult:
    """Result of move validation"""
    def __init__(self, valid: bool, error_message: Optional[str] = None):
        self.valid = valid
        self.error_message = error_message


class GameEngineInterface(ABC):
    """
    Abstract interface for turn-based game engines.
    
    Each game implementation should:
    - Validate moves according to game rules
    - Track game state
    - Determine win/draw conditions
    - Support custom rule configurations
    """
    
    def __init__(self, lobby_code: str, player_ids: List[int], rules: Optional[Dict[str, Any]] = None):
        """
        Initialize the game engine.
        
        Args:
            lobby_code: The lobby code this game is bound to
            player_ids: List of player IDs participating in the game
            rules: Optional dictionary of custom rules for this game instance
        """
        self.lobby_code = lobby_code
        self.player_ids = player_ids
        self.rules = rules or {}
        self.current_turn_index = 0
        self.game_result = GameResult.IN_PROGRESS
        self.winner_id: Optional[int] = None
        
        # Validate custom rules against game info
        self._validate_rules()
        
        # Timeout configuration
        timeout_type_str = self.rules.get("timeout_type", "none")
        self.timeout_type = TimeoutType(timeout_type_str) if timeout_type_str else TimeoutType.NONE
        self.timeout_seconds = self.rules.get("timeout_seconds", 0)
        
        # Timeout action - what happens when time expires
        timeout_action_str = self.rules.get("timeout_action", "end_game")
        self.timeout_action = TimeoutAction(timeout_action_str) if timeout_action_str else TimeoutAction.END_GAME
        
        # Validate timeout configuration
        if self.timeout_type != TimeoutType.NONE and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when timeout is enabled")
    
    def _validate_rules(self):
        """
        Validate custom rules against the game's supported rules.
        This uses the GameRuleOption definitions from get_game_info().
        Only validates rules that are explicitly provided by the user.
        """
        game_info = self.get_game_info()
        
        for rule_name, rule_value in self.rules.items():
            # Skip validation for rules not defined in game info
            if rule_name not in game_info.supported_rules:
                continue
            
            # Skip validation for None values - they'll use defaults
            if rule_value is None:
                continue
            
            rule_option = game_info.supported_rules[rule_name]
            
            # Type validation
            if rule_option.type == "integer":
                if not isinstance(rule_value, int) or isinstance(rule_value, bool):
                    raise ValueError(f"{rule_name} must be an integer, got {type(rule_value).__name__}")
            elif rule_option.type == "float" or rule_option.type == "number":
                if not isinstance(rule_value, (int, float)) or isinstance(rule_value, bool):
                    raise ValueError(f"{rule_name} must be a number, got {type(rule_value).__name__}")
            elif rule_option.type == "boolean":
                if not isinstance(rule_value, bool):
                    raise ValueError(f"{rule_name} must be a boolean, got {type(rule_value).__name__}")
            elif rule_option.type == "string":
                if not isinstance(rule_value, str):
                    raise ValueError(f"{rule_name} must be a string, got {type(rule_value).__name__}")
            
            # Allowed values validation
            if rule_option.allowed_values is not None:
                if rule_value not in rule_option.allowed_values:
                    raise ValueError(f"{rule_name} value '{rule_value}' is not in allowed values: {rule_option.allowed_values}")
    
    @property
    def current_player_id(self) -> int:
        """Get the ID of the player whose turn it is"""
        return self.player_ids[self.current_turn_index]
    
    def initialize_game_state(self) -> Dict[str, Any]:
        """
        Initialize and return the starting game state with timing information.
        
        Returns:
            Dictionary representing the initial game state with timing data
        """
        # Get game-specific state from subclass
        game_state = self._initialize_game_specific_state()
        
        # Add timing information
        game_state["timing"] = self._initialize_timing_state()
        
        return game_state
    
    @abstractmethod
    def _initialize_game_specific_state(self) -> Dict[str, Any]:
        """
        Initialize game-specific state (to be implemented by subclasses).
        
        Returns:
            Dictionary representing the game-specific initial state
        """
        pass
    
    def _initialize_timing_state(self) -> Dict[str, Any]:
        """
        Initialize timing state based on timeout configuration.
        
        Returns:
            Dictionary with timing information
        """
        timing_state = {
            "timeout_type": self.timeout_type.value,
            "timeout_seconds": self.timeout_seconds,
            "turn_start_time": None,
        }
        
        # For total time mode, initialize remaining time for each player
        if self.timeout_type == TimeoutType.TOTAL_TIME:
            timing_state["player_time_remaining"] = {
                str(player_id): self.timeout_seconds for player_id in self.player_ids
            }
        
        return timing_state
    
    def validate_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate if a move is legal according to game rules and timing.
        
        Args:
            game_state: Current game state
            player_id: ID of the player making the move
            move_data: Data describing the move
            
        Returns:
            MoveValidationResult indicating if the move is valid
        """
        # Check for timeout first
        timeout_occurred, _ = self.check_timeout(game_state)
        if timeout_occurred:
            return MoveValidationResult(False, "Time limit exceeded")
        
        # Check if it's the player's turn
        if player_id != self.current_player_id:
            return MoveValidationResult(False, "It's not your turn")
        
        # Check if game is still in progress
        if self.game_result != GameResult.IN_PROGRESS:
            return MoveValidationResult(False, "Game has already ended")
        
        # Delegate to game-specific validation
        return self._validate_game_specific_move(game_state, player_id, move_data)
    
    @abstractmethod
    def _validate_game_specific_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate game-specific move rules (to be implemented by subclasses).
        
        Args:
            game_state: Current game state
            player_id: ID of the player making the move
            move_data: Data describing the move
            
        Returns:
            MoveValidationResult indicating if the move is valid
        """
        pass
    
    @abstractmethod
    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a validated move to the game state.
        
        Args:
            game_state: Current game state
            player_id: ID of the player making the move
            move_data: Data describing the move
            
        Returns:
            Updated game state after the move is applied
        """
        pass
    
    @abstractmethod
    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        """
        Check if the game has ended and determine the result.
        
        Args:
            game_state: Current game state
            
        Returns:
            Tuple of (GameResult, winner_id or None)
        """
        pass
    
    def advance_turn(self):
        """Advance to the next player's turn"""
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)
    
    def start_turn(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mark the start of a turn for timing purposes.
        
        Args:
            game_state: Current game state
            
        Returns:
            Updated game state with turn start time recorded
        """
        if self.timeout_type != TimeoutType.NONE:
            game_state["timing"]["turn_start_time"] = datetime.now(UTC).isoformat()
        return game_state
    
    def check_timeout(self, game_state: Dict[str, Any]) -> tuple[bool, Optional[int]]:
        """
        Check if the current player has exceeded their time limit.
        
        Args:
            game_state: Current game state
            
        Returns:
            Tuple of (timeout_occurred, winner_id)
            - timeout_occurred: True if timeout has occurred
            - winner_id: ID of the winner (if game ends), or None (if turn is skipped)
        """
        if self.timeout_type == TimeoutType.NONE:
            return False, None
        
        timing = game_state.get("timing", {})
        turn_start_time_str = timing.get("turn_start_time")
        
        if not turn_start_time_str:
            # Turn hasn't started yet
            return False, None
        
        turn_start_time = datetime.fromisoformat(turn_start_time_str)
        current_time = datetime.now(UTC)
        elapsed_seconds = (current_time - turn_start_time).total_seconds()
        
        current_player_id = self.current_player_id
        
        if self.timeout_type == TimeoutType.PER_TURN:
            # Check if turn time exceeded
            if elapsed_seconds > self.timeout_seconds:
                return self._handle_timeout_action(game_state, current_player_id)
        
        elif self.timeout_type == TimeoutType.TOTAL_TIME:
            # Check if player's total time exceeded
            player_time_remaining = timing.get("player_time_remaining", {})
            remaining_time = player_time_remaining.get(str(current_player_id), 0)
            
            if elapsed_seconds > remaining_time:
                return self._handle_timeout_action(game_state, current_player_id)
        
        return False, None
    
    def _handle_timeout_action(self, game_state: Dict[str, Any], timed_out_player_id: int) -> tuple[bool, Optional[int]]:
        """
        Handle what happens when a player times out based on timeout_action.
        
        Args:
            game_state: Current game state
            timed_out_player_id: ID of the player who timed out
            
        Returns:
            Tuple of (timeout_occurred, winner_id)
        """
        if self.timeout_action == TimeoutAction.SKIP_TURN:
            # Just skip this player's turn, game continues
            logger.info(f"Player {timed_out_player_id} timed out - skipping turn")
            return True, None  # Timeout occurred but no winner (game continues)
            
        elif self.timeout_action == TimeoutAction.END_GAME:
            # Game ends, other player(s) win
            self.game_result = GameResult.TIMEOUT
            # For 2-player games, other player wins
            if len(self.player_ids) == 2:
                self.winner_id = next(pid for pid in self.player_ids if pid != timed_out_player_id)
            else:
                # For multi-player, no single winner determined by timeout
                self.winner_id = None
            logger.info(f"Player {timed_out_player_id} timed out - game ended")
            return True, self.winner_id
            
        elif self.timeout_action == TimeoutAction.ELIMINATE_PLAYER:
            # Remove player from game, others continue
            # This would need more complex logic to track eliminated players
            logger.info(f"Player {timed_out_player_id} timed out - player eliminated")
            # For now, treat like skip turn
            return True, None
        
        return False, None
    
    def consume_turn_time(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update time tracking after a move is made.
        
        Args:
            game_state: Current game state
            
        Returns:
            Updated game state with time consumed
        """
        if self.timeout_type == TimeoutType.NONE:
            return game_state
        
        timing = game_state.get("timing", {})
        turn_start_time_str = timing.get("turn_start_time")
        
        if not turn_start_time_str:
            return game_state
        
        turn_start_time = datetime.fromisoformat(turn_start_time_str)
        current_time = datetime.now(UTC)
        elapsed_seconds = (current_time - turn_start_time).total_seconds()
        
        if self.timeout_type == TimeoutType.TOTAL_TIME:
            # Deduct elapsed time from player's total time
            current_player_id = self.current_player_id
            player_time_remaining = timing.get("player_time_remaining", {})
            remaining_time = player_time_remaining.get(str(current_player_id), 0)
            new_remaining_time = max(0, remaining_time - elapsed_seconds)
            player_time_remaining[str(current_player_id)] = new_remaining_time
            timing["player_time_remaining"] = player_time_remaining
        
        # Clear turn start time
        timing["turn_start_time"] = None
        game_state["timing"] = timing
        
        return game_state
    
    def get_remaining_time(self, game_state: Dict[str, Any], player_id: Optional[int] = None) -> Optional[float]:
        """
        Get remaining time for a player.
        
        Args:
            game_state: Current game state
            player_id: Player ID to check (defaults to current player)
            
        Returns:
            Remaining time in seconds, or None if no timeout is configured
        """
        if self.timeout_type == TimeoutType.NONE:
            return None
        
        if player_id is None:
            player_id = self.current_player_id
        
        timing = game_state.get("timing", {})
        turn_start_time_str = timing.get("turn_start_time")
        
        if self.timeout_type == TimeoutType.PER_TURN:
            if not turn_start_time_str:
                return self.timeout_seconds
            
            turn_start_time = datetime.fromisoformat(turn_start_time_str)
            current_time = datetime.now(UTC)
            elapsed_seconds = (current_time - turn_start_time).total_seconds()
            return max(0, self.timeout_seconds - elapsed_seconds)
        
        elif self.timeout_type == TimeoutType.TOTAL_TIME:
            player_time_remaining = timing.get("player_time_remaining", {})
            remaining_time = player_time_remaining.get(str(player_id), 0)
            
            # If it's currently this player's turn, subtract elapsed time
            if player_id == self.current_player_id and turn_start_time_str:
                turn_start_time = datetime.fromisoformat(turn_start_time_str)
                current_time = datetime.now(UTC)
                elapsed_seconds = (current_time - turn_start_time).total_seconds()
                remaining_time = max(0, remaining_time - elapsed_seconds)
            
            return remaining_time
        
        return None
    
    @classmethod
    @abstractmethod
    def get_game_name(cls) -> str:
        """
        Get the unique name identifier for this game type.
        
        Returns:
            String name of the game
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_game_info(cls) -> GameInfo:
        """
        Get static game information without requiring an instance.
        This should return game metadata like rules, player requirements,
        supported options, etc.
        
        Returns:
            GameInfo DTO with static game information
        """
        pass
    
    def forfeit_game(self, player_id: int) -> tuple[GameResult, Optional[int]]:
        """
        Handle a player forfeiting the game.
        
        Args:
            player_id: ID of the player forfeiting
            
        Returns:
            Tuple of (GameResult.FORFEIT, winner_id)
        """
        self.game_result = GameResult.FORFEIT
        # Winner is the other player(s) - for 2-player games
        if len(self.player_ids) == 2:
            self.winner_id = next(pid for pid in self.player_ids if pid != player_id)
        return GameResult.FORFEIT, self.winner_id
    
    def calculate_elo_adjustments(self, game_state: Dict[str, Any]) -> Dict[int, int]:
        """
        Calculate ELO adjustments for all players based on game state.
        Can be overridden by subclasses for custom ELO logic (e.g. 2nd/3rd place).
        
        Args:
            game_state: The final game state
            
        Returns:
            Dictionary mapping player_id to ELO adjustment (e.g. {1: 1, 2: -1})
        """
        adjustments = {}
        winner_id = game_state.get("winner_id")
        
        if winner_id:
            # Base case: Winner gets +1, everyone else gets -1
            for player_id in self.player_ids:
                if player_id == winner_id:
                    adjustments[player_id] = 1
                else:
                    adjustments[player_id] = -1
        
        return adjustments
