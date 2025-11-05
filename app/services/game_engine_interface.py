# app/services/game_engine_interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from schemas.game_schema import GameInfo


class GameResult(Enum):
    """Possible game results"""
    IN_PROGRESS = "in_progress"
    PLAYER_WIN = "player_win"
    DRAW = "draw"
    FORFEIT = "forfeit"


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
    
    @property
    def current_player_id(self) -> int:
        """Get the ID of the player whose turn it is"""
        return self.player_ids[self.current_turn_index]
    
    @abstractmethod
    def initialize_game_state(self) -> Dict[str, Any]:
        """
        Initialize and return the starting game state.
        
        Returns:
            Dictionary representing the initial game state
        """
        pass
    
    @abstractmethod
    def validate_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate if a move is legal according to game rules.
        
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
