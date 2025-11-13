# app/tests/test_tictactoe_engine.py

import pytest
from services.games.tictactoe_engine import TicTacToeEngine
from services.game_engine_interface import GameResult


class TestTicTacToeEngine:
    """Tests for TicTacToeEngine"""
    
    def test_initialization_standard(self):
        """Test standard 3x3 tic-tac-toe initialization"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        
        assert engine.lobby_code == "TEST123"
        assert engine.player_ids == [1, 2]
        assert engine.board_size == 3
        assert engine.win_length == 3
        assert engine.current_player_id == 1
        
    def test_initialization_custom_board_size(self):
        """Test custom board size"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={"board_size": 4})
        
        assert engine.board_size == 4
        assert engine.win_length == 3
        
    def test_initialization_invalid_player_count(self):
        """Test that initialization fails with wrong number of players"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            TicTacToeEngine("TEST123", [1, 2, 3])
    
    def test_initialize_game_state(self):
        """Test game state initialization"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert "board" in state
        assert len(state["board"]) == 3
        assert len(state["board"][0]) == 3
        assert all(cell is None for row in state["board"] for cell in row)
        assert state["move_count"] == 0
        assert state["last_move"] is None
        
    def test_validate_move_valid(self):
        """Test valid move validation"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"row": 0, "col": 0})
        
        assert result.valid is True
        assert result.error_message is None
        
    def test_validate_move_wrong_turn(self):
        """Test validation fails for wrong player's turn"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 2, {"row": 0, "col": 0})
        
        assert result.valid is False
        assert "not your turn" in result.error_message
        
    def test_validate_move_occupied(self):
        """Test validation fails for occupied position"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Make first move
        engine.apply_move(state, 1, {"row": 0, "col": 0})
        
        # Try to play in same position
        result = engine.validate_move(state, 1, {"row": 0, "col": 0})
        
        assert result.valid is False
        assert "occupied" in result.error_message
        
    def test_validate_move_out_of_bounds(self):
        """Test validation fails for out of bounds position"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"row": 5, "col": 5})
        
        assert result.valid is False
        assert "out of bounds" in result.error_message
        
    def test_apply_move(self):
        """Test applying a move"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.apply_move(state, 1, {"row": 1, "col": 1})
        
        assert state["board"][1][1] == "X"
        assert state["move_count"] == 1
        assert state["last_move"]["player_id"] == 1
        assert state["last_move"]["row"] == 1
        assert state["last_move"]["col"] == 1
        
    def test_check_winner_row(self):
        """Test detecting a row win"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 wins with top row
        state = engine.apply_move(state, 1, {"row": 0, "col": 0})
        state = engine.apply_move(state, 1, {"row": 0, "col": 1})
        state = engine.apply_move(state, 1, {"row": 0, "col": 2})
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
        
    def test_check_winner_column(self):
        """Test detecting a column win"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 2 wins with middle column
        state = engine.apply_move(state, 2, {"row": 0, "col": 1})
        state = engine.apply_move(state, 2, {"row": 1, "col": 1})
        state = engine.apply_move(state, 2, {"row": 2, "col": 1})
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 2
        
    def test_check_winner_diagonal(self):
        """Test detecting a diagonal win"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 wins with main diagonal
        state = engine.apply_move(state, 1, {"row": 0, "col": 0})
        state = engine.apply_move(state, 1, {"row": 1, "col": 1})
        state = engine.apply_move(state, 1, {"row": 2, "col": 2})
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
        
    def test_check_draw(self):
        """Test detecting a draw"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Fill board with no winner
        # X O X
        # X O O
        # O X X
        moves = [
            (1, 0, 0), (2, 0, 1), (1, 0, 2),
            (1, 1, 0), (2, 1, 1), (2, 1, 2),
            (2, 2, 0), (1, 2, 1), (1, 2, 2)
        ]
        
        for player_id, row, col in moves:
            state = engine.apply_move(state, player_id, {"row": row, "col": col})
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.DRAW
        assert winner is None
        
    def test_game_in_progress(self):
        """Test game in progress detection"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Make one move
        state = engine.apply_move(state, 1, {"row": 0, "col": 0})
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
        
    def test_advance_turn(self):
        """Test turn advancement"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        
        assert engine.current_player_id == 1
        
        engine.advance_turn()
        assert engine.current_player_id == 2
        
        engine.advance_turn()
        assert engine.current_player_id == 1
        
    def test_forfeit_game(self):
        """Test game forfeit"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        
        result, winner = engine.forfeit_game(1)
        
        assert result == GameResult.FORFEIT
        assert winner == 2
        
    def test_full_game_flow(self):
        """Test a complete game flow"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1: (0,0), (1,1), (2,2) - diagonal win
        # Player 2: (0,1), (0,2)
        moves = [
            (1, 0, 0),  # X
            (2, 0, 1),  # O
            (1, 1, 1),  # X
            (2, 0, 2),  # O
            (1, 2, 2),  # X wins
        ]
        
        for i, (player_id, row, col) in enumerate(moves):
            # Validate move
            validation = engine.validate_move(state, player_id, {"row": row, "col": col})
            assert validation.valid, f"Move {i} should be valid"
            
            # Apply move
            state = engine.apply_move(state, player_id, {"row": row, "col": col})
            
            # Check result
            result, winner = engine.check_game_result(state)
            
            if i < len(moves) - 1:
                assert result == GameResult.IN_PROGRESS
                engine.advance_turn()
            else:
                assert result == GameResult.PLAYER_WIN
                assert winner == 1
                
    def test_custom_board_size_game(self):
        """Test game with custom board size"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={"board_size": 4, "win_length": 4})
        state = engine.initialize_game_state()
        
        assert len(state["board"]) == 4
        assert len(state["board"][0]) == 4
        
        # Player 1 wins with 4 in a row
        for col in range(4):
            state = engine.apply_move(state, 1, {"row": 0, "col": col})
        
        result, winner = engine.check_game_result(state)
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
    
    def test_initialization_win_length_exceeds_board_size(self):
        """Test that win_length cannot exceed board_size"""
        with pytest.raises(ValueError, match="Win length cannot exceed board size"):
            TicTacToeEngine("TEST123", [1, 2], rules={"board_size": 3, "win_length": 5})
    
    def test_validate_move_missing_row_field(self):
        """Test validation fails when 'row' field is missing"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"col": 0})  # Missing 'row'
        
        assert result.valid is False
        assert "must contain 'row' and 'col' fields" in result.error_message
    
    def test_validate_move_missing_col_field(self):
        """Test validation fails when 'col' field is missing"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"row": 0})  # Missing 'col'
        
        assert result.valid is False
        assert "must contain 'row' and 'col' fields" in result.error_message
    
    def test_validate_move_non_integer_row(self):
        """Test validation fails when row is not an integer"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"row": "invalid", "col": 0})
        
        assert result.valid is False
        assert "must be integers" in result.error_message
    
    def test_validate_move_non_integer_col(self):
        """Test validation fails when col is not an integer"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"row": 0, "col": None})
        
        assert result.valid is False
        assert "must be integers" in result.error_message
    
    def test_check_winner_anti_diagonal(self):
        """Test win detection on anti-diagonal (top-right to bottom-left)"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 wins on anti-diagonal: (0,2), (1,1), (2,0)
        state = engine.apply_move(state, 1, {"row": 0, "col": 2})  # X
        state = engine.apply_move(state, 2, {"row": 0, "col": 0})  # O
        state = engine.apply_move(state, 1, {"row": 1, "col": 1})  # X
        state = engine.apply_move(state, 2, {"row": 0, "col": 1})  # O
        state = engine.apply_move(state, 1, {"row": 2, "col": 0})  # X wins
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
    
    def test_check_line_with_short_line(self):
        """Test _check_line returns None when line is shorter than win_length"""
        engine = TicTacToeEngine("TEST123", [1, 2], rules={"board_size": 5, "win_length": 4})
        state = engine.initialize_game_state()
        
        # Place only 2 symbols in a row (less than win_length=4)
        state = engine.apply_move(state, 1, {"row": 0, "col": 0})
        state = engine.apply_move(state, 2, {"row": 1, "col": 0})
        state = engine.apply_move(state, 1, {"row": 0, "col": 1})
        
        result, winner = engine.check_game_result(state)
        
        # Should be in progress, not won
        assert result == GameResult.IN_PROGRESS
        assert winner is None
    
    def test_check_line_no_consecutive_win(self):
        """Test _check_line returns None when there's no consecutive winning sequence"""
        engine = TicTacToeEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Create a board with symbols but no winning line (alternating X and O)
        # Row 0: X O X
        state = engine.apply_move(state, 1, {"row": 0, "col": 0})  # X
        state = engine.apply_move(state, 2, {"row": 0, "col": 1})  # O
        state = engine.apply_move(state, 1, {"row": 0, "col": 2})  # X
        state = engine.apply_move(state, 2, {"row": 1, "col": 0})  # O
        
        result, winner = engine.check_game_result(state)
        
        # No winner yet - alternating symbols
        assert result == GameResult.IN_PROGRESS
        assert winner is None

    def test_check_line_short_line(self):
        """Test that _check_line handles lines shorter than win_length gracefully (line 172)"""
        # The edge case at line 172 handles when len(line) < win_length
        # This prevents index errors when checking partial lines
        engine = TicTacToeEngine(
            lobby_code="EDGE",
            player_ids=[1, 2],
            rules={"board_size": 3, "win_length": 3}
        )
        
        # Test with a line that's too short to win
        short_line = ["X", "X"]  # Length 2, but win_length is 3
        result = engine._check_line(short_line)
        
        # Should return None (can't win with a line shorter than win_length)
        assert result is None
        
        # Test with empty line
        empty_line = []
        result = engine._check_line(empty_line)
        assert result is None
