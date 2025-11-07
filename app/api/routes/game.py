# app/api/routes/game.py

from fastapi import APIRouter, Depends
from typing import List
from services.game_service import GameService
from schemas.game_schema import AvailableGamesResponse

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/available", response_model=AvailableGamesResponse)
async def get_available_games():
    """
    Get list of available game types.
    
    Returns a list of all game engines that have been registered
    and are available to play.
    
    Example response:
    ```json
    {
        "games": ["tictactoe"]
    }
    ```
    """
    games = GameService.get_available_games()
    return AvailableGamesResponse(games=games)


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
