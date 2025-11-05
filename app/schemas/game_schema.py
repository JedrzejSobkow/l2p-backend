# app/schemas/game_schema.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime


# Game Info DTOs
class GameRuleOption(BaseModel):
    """Schema for a configurable game rule option"""
    type: str = Field(..., description="Data type of the rule (e.g., 'integer', 'boolean', 'string')")
    min: Optional[Union[int, float]] = Field(None, description="Minimum value for numeric rules")
    max: Optional[Union[int, float]] = Field(None, description="Maximum value for numeric rules")
    default: Any = Field(..., description="Default value for the rule")
    description: str = Field(..., description="Human-readable description of the rule")


class GameInfo(BaseModel):
    """Static information about a game type"""
    game_name: str = Field(..., description="Unique identifier for the game type")
    display_name: str = Field(..., description="Human-readable display name")
    description: str = Field(..., description="Description of the game")
    min_players: int = Field(..., description="Minimum number of players required")
    max_players: int = Field(..., description="Maximum number of players allowed")
    supported_rules: Dict[str, GameRuleOption] = Field(default_factory=dict, description="Configurable rules for the game")
    turn_based: bool = Field(..., description="Whether the game is turn-based")
    category: str = Field(..., description="Game category (e.g., 'strategy', 'action', 'puzzle')")
    game_image_path: Optional[str] = Field(None, description="Path to the game's image asset")


# Request schemas
class CreateGameRequest(BaseModel):
    """Request to create a new game"""
    game_name: str = Field(..., description="Name of the game type (e.g., 'tictactoe')")
    rules: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom rules for the game")


class MakeMoveRequest(BaseModel):
    """Request to make a move in the game"""
    move_data: Dict[str, Any] = Field(..., description="Game-specific move data")


class ForfeitGameRequest(BaseModel):
    """Request to forfeit the game"""
    pass


# Response schemas
class GameStateResponse(BaseModel):
    """Response containing current game state"""
    lobby_code: str
    game_state: Dict[str, Any]
    engine_config: Dict[str, Any]


class GameCreatedResponse(BaseModel):
    """Response when a game is successfully created"""
    lobby_code: str
    game_name: str
    game_state: Dict[str, Any]
    game_info: GameInfo
    current_turn_player_id: int
    created_at: datetime


class MoveProcessedResponse(BaseModel):
    """Response after a move is processed"""
    game_state: Dict[str, Any]
    result: str
    winner_id: Optional[int]
    current_turn_player_id: Optional[int]


class GameResultResponse(BaseModel):
    """Response with game result"""
    game_state: Dict[str, Any]
    result: str
    winner_id: Optional[int]


class AvailableGamesResponse(BaseModel):
    """Response with list of available games"""
    games: List[str]


# Event schemas (for Socket.IO broadcasts)
class GameStartedEvent(BaseModel):
    """Event when a game starts"""
    lobby_code: str
    game_name: str
    game_state: Dict[str, Any]
    game_info: GameInfo
    current_turn_player_id: int


class MoveMadeEvent(BaseModel):
    """Event when a player makes a move"""
    lobby_code: str
    player_id: int
    move_data: Dict[str, Any]
    game_state: Dict[str, Any]
    current_turn_player_id: Optional[int]


class GameEndedEvent(BaseModel):
    """Event when a game ends"""
    lobby_code: str
    result: str
    winner_id: Optional[int]
    game_state: Dict[str, Any]


class PlayerForfeitedEvent(BaseModel):
    """Event when a player forfeits"""
    lobby_code: str
    player_id: int
    winner_id: Optional[int]
    game_state: Dict[str, Any]


class GameErrorResponse(BaseModel):
    """Error response for game operations"""
    error: str
    details: Optional[Dict[str, Any]] = None
