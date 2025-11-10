# app/tests/test_games_init.py

import pytest
from services.games import GAME_ENGINES, TicTacToeEngine
from services.game_engine_interface import GameEngineInterface


class TestGamesInit:
    """Test suite for games/__init__.py module"""
    
    def test_game_engines_registry_not_empty(self):
        """Test that game engines registry is populated"""
        assert len(GAME_ENGINES) > 0, "GAME_ENGINES should contain at least one engine"
    
    def test_tictactoe_in_registry(self):
        """Test that TicTacToe engine is registered"""
        assert "tictactoe" in GAME_ENGINES
        assert GAME_ENGINES["tictactoe"] == TicTacToeEngine
    
    def test_all_engines_are_subclasses(self):
        """Test that all registered engines are GameEngineInterface subclasses"""
        for game_name, engine_class in GAME_ENGINES.items():
            assert issubclass(engine_class, GameEngineInterface)
            assert engine_class is not GameEngineInterface
    
    def test_all_engines_have_get_game_name(self):
        """Test that all registered engines have get_game_name method"""
        for game_name, engine_class in GAME_ENGINES.items():
            assert hasattr(engine_class, 'get_game_name')
            assert callable(engine_class.get_game_name)
    
    def test_all_engines_return_correct_name(self):
        """Test that all engines return their registered name"""
        for game_name, engine_class in GAME_ENGINES.items():
            assert engine_class.get_game_name() == game_name
    
    def test_discover_game_engines_exception_handling(self):
        """Test that _discover_game_engines handles exceptions gracefully"""
        # This test ensures the exception handling path is covered
        from services.games import _discover_game_engines
        import inspect
        from unittest.mock import patch, MagicMock
        
        # Create a mock class that raises an exception in get_game_name
        class BrokenEngine(GameEngineInterface):
            @classmethod
            def get_game_name(cls):
                raise RuntimeError("Intentional error for testing")
        
        # Mock inspect.getmembers to return our broken engine
        mock_module = MagicMock()
        original_members = [
            ("TicTacToeEngine", TicTacToeEngine),
            ("BrokenEngine", BrokenEngine),
            ("GameEngineInterface", GameEngineInterface),
        ]
        
        with patch('inspect.getmodule') as mock_getmodule:
            with patch('inspect.getmembers') as mock_getmembers:
                with patch('inspect.currentframe') as mock_frame:
                    mock_getmodule.return_value = mock_module
                    mock_getmembers.return_value = original_members
                    mock_frame.return_value = MagicMock()
                    
                    # This should not raise an exception
                    engines = _discover_game_engines()
                    
                    # The broken engine should be skipped
                    assert "tictactoe" in engines
                    # BrokenEngine should not be in the registry due to exception
                    assert len([e for e in engines.values() if e == BrokenEngine]) == 0
