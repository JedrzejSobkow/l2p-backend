# app/api/routes/game.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from services.game_service import GameService
from schemas.game_schema import AvailableGamesResponse, GameInfo

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/available")
async def get_available_games(full_info: bool = False):
    """
    Get list of available game types.
    
    Args:
        full_info: If True, returns full GameInfo for each game. If False, returns just names.
    
    Returns a list of all game engines that have been registered
    and are available to play.
    
    Example response (full_info=False):
    ```json
    {
        "games": ["tictactoe"]
    }
    ```
    
    Example response (full_info=True):
    ```json
    {
        "games": [
            {
                "game_name": "tictactoe",
                "display_name": "Tic-Tac-Toe",
                "description": "...",
                "min_players": 2,
                "max_players": 2,
                "supported_rules": {...},
                ...
            }
        ]
    }
    ```
    """
    if not full_info:
        games = GameService.get_available_games()
        return AvailableGamesResponse(games=games)
    
    # Return full game info
    games_info = []
    for game_name in GameService.get_available_games():
        engine_class = GameService.GAME_ENGINES[game_name]
        try:
            game_info = engine_class.get_game_info()
            games_info.append(game_info)
        except Exception as e:
            # Skip games that can't provide info
            continue
    
    return {
        "games": [info.model_dump() for info in games_info],
        "total": len(games_info)
    }


@router.get("/info/{game_name}")
async def get_game_info(game_name: str):
    """
    Get information about a specific game type.
    
    Args:
        game_name: The name of the game (e.g., 'tictactoe')
        
    Returns:
        Dictionary with game information including rules, player count, etc.
        
    Raises:
        404: If game type not found
    """
    if game_name not in GameService.GAME_ENGINES:
        return {
            "error": "Game not found",
            "available_games": GameService.get_available_games()
        }
    
    engine_class = GameService.GAME_ENGINES[game_name]
    
    # Get static game information without creating an instance
    try:
        game_info = engine_class.get_game_info()
        return game_info
    except Exception as e:
        return {
            "game_name": game_name,
            "error": f"Could not retrieve game info: {str(e)}"
        }
