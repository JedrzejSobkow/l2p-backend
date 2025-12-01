# app/services/games/__init__.py

import inspect
from typing import Dict, Type
from services.game_engine_interface import GameEngineInterface

# Import all game engines here (they will be auto-discovered)
from services.games.tictactoe_engine import TicTacToeEngine
from services.games.clobber_engine import ClobberEngine
from services.games.soccer_engine import SoccerEngine

# Automatically discover all GameEngineInterface subclasses in this module
def _discover_game_engines() -> Dict[str, Type[GameEngineInterface]]:
    """Auto-discover all game engine classes in this module"""
    engines = {}
    
    # Get all classes in the current module
    current_module = inspect.getmodule(inspect.currentframe())
    
    for name, obj in inspect.getmembers(current_module, inspect.isclass):
        # Check if it's a subclass of GameEngineInterface (but not the interface itself)
        if (issubclass(obj, GameEngineInterface) and 
            obj is not GameEngineInterface and
            hasattr(obj, 'get_game_name')):
            try:
                game_name = obj.get_game_name()
                engines[game_name] = obj
            except Exception:
                # Skip classes that can't provide a game name
                pass
    
    return engines

# Build the registry automatically
GAME_ENGINES: Dict[str, Type[GameEngineInterface]] = _discover_game_engines()

__all__ = ["TicTacToeEngine", "ClobberEngine","SoccerEngine", "GAME_ENGINES"]
