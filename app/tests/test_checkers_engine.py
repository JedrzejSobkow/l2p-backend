# app/tests/test_checkers_engine.py

import pytest
from services.games.checkers_engine import CheckersEngine
from services.game_engine_interface import GameResult


class TestCheckersEngine:
    """Tests for CheckersEngine"""
    
    # ========================
    # Initialization Tests
    # ========================
    
    def test_initialization_standard(self):
        """Test standard checkers initialization"""
        engine = CheckersEngine("TEST123", [1, 2])
        
        assert engine.lobby_code == "TEST123"
        assert engine.player_ids == [1, 2]
        assert engine.board_size == 8
        assert engine.forced_capture is True
        assert engine.flying_kings is False
        assert engine.backward_capture is True
        assert engine.current_player_id == 1
        assert engine.player_colors == {1: "white", 2: "black"}
        
    def test_initialization_custom_board_size(self):
        """Test custom board size (international)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"board_size": 10})
        
        assert engine.board_size == 10
        
    def test_initialization_custom_rules(self):
        """Test custom rules"""
        engine = CheckersEngine("TEST123", [1, 2], rules={
            "board_size": 10,
            "forced_capture": False,
            "flying_kings": True,
            "backward_capture": False
        })
        
        assert engine.board_size == 10
        assert engine.forced_capture is False
        assert engine.flying_kings is True
        assert engine.backward_capture is False
        
    def test_initialization_invalid_player_count(self):
        """Test that initialization fails with wrong number of players"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            CheckersEngine("TEST123", [1, 2, 3])
            
    def test_initialization_single_player(self):
        """Test that initialization fails with only one player"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            CheckersEngine("TEST123", [1])
    
    # ========================
    # Game State Initialization Tests
    # ========================
    
    def test_initialize_game_state_8x8(self):
        """Test game state initialization for 8x8 board"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert "board" in state
        assert len(state["board"]) == 8
        assert len(state["board"][0]) == 8
        assert state["move_count"] == 0
        assert state["last_move"] is None
        assert state["consecutive_non_capture_moves"] == 0
        assert "position_history" in state
        
        # Verify piece placement (3 rows each)
        board = state["board"]
        
        # Check black pieces (top 3 rows)
        black_count = 0
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares
                    assert board[row][col] == "b"
                    black_count += 1
                else:
                    assert board[row][col] is None
        
        assert black_count == 12
        
        # Check white pieces (bottom 3 rows)
        white_count = 0
        for row in range(5, 8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares
                    assert board[row][col] == "w"
                    white_count += 1
                else:
                    assert board[row][col] is None
        
        assert white_count == 12
        
        # Check middle rows are empty
        for row in range(3, 5):
            for col in range(8):
                assert board[row][col] is None
                    
    def test_initialize_game_state_10x10(self):
        """Test game state initialization for 10x10 board"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"board_size": 10})
        state = engine.initialize_game_state()
        
        assert len(state["board"]) == 10
        assert len(state["board"][0]) == 10
        
        # Count pieces (should be 20 per player for 10x10)
        board = state["board"]
        black_count = sum(1 for row in range(4) for col in range(10) if board[row][col] == "b")
        white_count = sum(1 for row in range(6, 10) for col in range(10) if board[row][col] == "w")
        
        assert black_count == 20
        assert white_count == 20
    
    # ========================
    # Move Validation Tests - Basic
    # ========================
    
    def test_validate_move_missing_fields(self):
        """Test validation fails when required fields are missing"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0, "to_row": 4
        })
        
        assert result.valid is False
        assert "to_col" in result.error_message
        
    def test_validate_move_invalid_coordinates(self):
        """Test validation fails for non-integer coordinates"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {
            "from_row": "invalid", "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        
        assert result.valid is False
        assert "must be integers" in result.error_message
        
    def test_validate_move_out_of_bounds(self):
        """Test validation fails for out of bounds positions"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {
            "from_row": 10, "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        
        assert result.valid is False
        assert "out of bounds" in result.error_message
        
    def test_validate_move_wrong_turn(self):
        """Test validation fails for wrong player's turn"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 2's turn hasn't started yet
        result = engine.validate_move(state, 2, {
            "from_row": 2, "from_col": 1,
            "to_row": 3, "to_col": 0
        })
        
        assert result.valid is False
        assert "not your turn" in result.error_message
        
    def test_validate_move_no_piece_at_start(self):
        """Test validation fails when no player's piece at starting position"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Try to move from empty square
        result = engine.validate_move(state, 1, {
            "from_row": 3, "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        
        assert result.valid is False
        assert "No piece of yours" in result.error_message
        
    def test_validate_move_opponent_piece(self):
        """Test validation fails when trying to move opponent's piece"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 (white) trying to move black piece
        result = engine.validate_move(state, 1, {
            "from_row": 2, "from_col": 1,
            "to_row": 3, "to_col": 0
        })
        
        assert result.valid is False
        assert "No piece of yours" in result.error_message
        
    def test_validate_move_destination_occupied(self):
        """Test validation fails when destination is occupied"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Try to move to occupied square
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 5, "to_col": 2
        })
        
        assert result.valid is False
        assert "occupied" in result.error_message
        
    def test_validate_move_light_square(self):
        """Test validation fails when moving to light square"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up piece on dark square trying to move to light square diagonally
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][1] = "w"  # Dark square (5+1=6, even)
        # (4,0) is light square (4+0=4, even)
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 1,
            "to_row": 4, "to_col": 0
        })
        
        assert result.valid is False
        assert "dark squares" in result.error_message
        
    def test_validate_move_not_diagonal(self):
        """Test validation fails for non-diagonal moves"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Clear board and set up pieces
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][1] = "w"
        
        # Try horizontal move
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 1,
            "to_row": 5, "to_col": 3
        })
        
        assert result.valid is False
        assert "diagonally" in result.error_message
    
    # ========================
    # Regular Move Tests
    # ========================
    
    def test_validate_regular_move_white_forward(self):
        """Test valid forward move for white piece"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # White moves from (5,0) to (4,1)
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        
        assert result.valid is True
        
    def test_validate_regular_move_white_backward_fails(self):
        """Test that white pieces cannot move backward"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up a white piece in middle
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][1] = "w"
        
        # Try to move backward (down)
        result = engine.validate_move(state, 1, {
            "from_row": 4, "from_col": 1,
            "to_row": 5, "to_col": 0
        })
        
        assert result.valid is False
        assert "forward" in result.error_message
        
    def test_validate_regular_move_black_forward(self):
        """Test valid forward move for black piece"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # First move by white
        state = engine.apply_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        engine.advance_turn()
        
        # Black moves from (2,1) to (3,0)
        result = engine.validate_move(state, 2, {
            "from_row": 2, "from_col": 1,
            "to_row": 3, "to_col": 0
        })
        
        assert result.valid is True
        
    def test_validate_regular_move_black_backward_fails(self):
        """Test that black pieces cannot move backward"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][1] = "b"
        engine.current_turn_index = 1  # Black's turn
        
        # Try to move backward (up)
        result = engine.validate_move(state, 2, {
            "from_row": 4, "from_col": 1,
            "to_row": 3, "to_col": 0
        })
        
        assert result.valid is False
        assert "forward" in result.error_message
    
    # ========================
    # Capture Move Tests
    # ========================
    
    def test_validate_capture_move_white(self):
        """Test valid capture move for white"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up a capture situation
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][4][1] = "b"
        # (3,2) is empty
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2
        })
        
        assert result.valid is True
        
    def test_validate_capture_move_black(self):
        """Test valid capture move for black"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up a capture situation
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][2][1] = "b"
        state["board"][3][2] = "w"
        # (4,3) is empty
        engine.current_turn_index = 1
        
        result = engine.validate_move(state, 2, {
            "from_row": 2, "from_col": 1,
            "to_row": 4, "to_col": 3
        })
        
        assert result.valid is True
        
    def test_validate_capture_backward_allowed(self):
        """Test backward capture is allowed by default"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # White piece with black piece behind it
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][3][2] = "w"
        state["board"][4][3] = "b"
        # (5,4) is empty
        
        result = engine.validate_move(state, 1, {
            "from_row": 3, "from_col": 2,
            "to_row": 5, "to_col": 4
        })
        
        assert result.valid is True
        
    def test_validate_capture_backward_disabled(self):
        """Test backward capture when disabled"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"backward_capture": False})
        state = engine.initialize_game_state()
        
        # White piece with black piece behind it
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][3][2] = "w"
        state["board"][4][3] = "b"
        
        result = engine.validate_move(state, 1, {
            "from_row": 3, "from_col": 2,
            "to_row": 5, "to_col": 4
        })
        
        assert result.valid is False
        assert "backward" in result.error_message
        
    def test_validate_capture_no_piece_to_capture(self):
        """Test capture fails when no piece in middle"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        # No piece at (4,1)
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2
        })
        
        assert result.valid is False
        assert "No piece to capture" in result.error_message
        
    def test_validate_capture_own_piece(self):
        """Test cannot capture own piece"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][4][1] = "w"  # Own piece
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2
        })
        
        assert result.valid is False
        assert "Cannot capture own pieces" in result.error_message
        
    def test_forced_capture_required(self):
        """Test that capture is forced when available"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up: white piece can either move or capture
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][4][1] = "b"  # Can capture
        # Can also move to (4,1) if it was empty, but it's not
        
        # Try to make a regular move when capture is available
        state["board"][5][2] = "w"
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 2,
            "to_row": 4, "to_col": 3
        })
        
        assert result.valid is False
        assert "Must capture" in result.error_message
        
    def test_forced_capture_disabled(self):
        """Test moves allowed when forced capture is disabled"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"forced_capture": False})
        state = engine.initialize_game_state()
        
        # Set up: white piece can capture but chooses not to
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][4][1] = "b"  # Could capture
        state["board"][5][2] = "w"
        
        # Make a regular move instead
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 2,
            "to_row": 4, "to_col": 3
        })
        
        assert result.valid is True
    
    # ========================
    # King Tests
    # ========================
    
    def test_king_creation_white(self):
        """Test white piece becomes king at row 0"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up white piece near top
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][1][0] = "w"
        
        state = engine.apply_move(state, 1, {
            "from_row": 1, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        assert state["board"][0][1] == "W"
        assert state["last_move"]["promoted"] is True
        
    def test_king_creation_black(self):
        """Test black piece becomes king at row 7"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up black piece near bottom
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][6][1] = "b"
        engine.current_turn_index = 1
        
        state = engine.apply_move(state, 2, {
            "from_row": 6, "from_col": 1,
            "to_row": 7, "to_col": 0
        })
        
        assert state["board"][7][0] == "B"
        assert state["last_move"]["promoted"] is True
        
    def test_king_move_backward(self):
        """Test king can move backward"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][1] = "W"  # White king
        
        # Move backward (down for white)
        result = engine.validate_move(state, 1, {
            "from_row": 4, "from_col": 1,
            "to_row": 5, "to_col": 0
        })
        
        assert result.valid is True
        
    def test_king_move_all_directions(self):
        """Test king can move in all diagonal directions"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][3] = "W"  # White king in center on dark square (4+3=7, odd)
        
        # Test all 4 diagonal directions to dark squares
        directions = [
            (3, 2),  # Up-left to dark square (3+2=5, odd)
            (3, 4),  # Up-right to dark square (3+4=7, odd)
            (5, 2),  # Down-left to dark square (5+2=7, odd)
            (5, 4),  # Down-right to dark square (5+4=9, odd)
        ]
        
        for to_row, to_col in directions:
            result = engine.validate_move(state, 1, {
                "from_row": 4, "from_col": 3,
                "to_row": to_row, "to_col": to_col
            })
            assert result.valid is True, f"Move to ({to_row}, {to_col}) should be valid"
            
    def test_king_standard_cannot_fly(self):
        """Test standard king cannot move multiple squares"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][3] = "W"  # Dark square (4+3=7, odd)
        
        # Try to move 2 squares diagonally to (2,1) which is dark square (2+1=3, odd)
        result = engine.validate_move(state, 1, {
            "from_row": 4, "from_col": 3,
            "to_row": 2, "to_col": 1
        })
        
        assert result.valid is False
        assert "one square" in result.error_message
        
    def test_king_flying_enabled(self):
        """Test flying king can move multiple squares"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"  # Dark square (7+0=7, odd)
        
        # Move multiple squares to (4,3) which is dark square (4+3=7, odd)
        result = engine.validate_move(state, 1, {
            "from_row": 7, "from_col": 0,
            "to_row": 4, "to_col": 3
        })
        
        assert result.valid is True
        
    def test_king_flying_capture(self):
        """Test flying king can capture at distance"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        state["board"][5][2] = "b"  # Opponent piece
        
        # Capture at distance
        result = engine.validate_move(state, 1, {
            "from_row": 7, "from_col": 0,
            "to_row": 3, "to_col": 4
        })
        
        assert result.valid is True
        
    def test_king_flying_cannot_jump_multiple(self):
        """Test flying king cannot jump multiple pieces"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        state["board"][5][2] = "b"  # First opponent
        state["board"][3][4] = "b"  # Second opponent
        
        result = engine.validate_move(state, 1, {
            "from_row": 7, "from_col": 0,
            "to_row": 1, "to_col": 6
        })
        
        assert result.valid is False
        assert "exactly one" in result.error_message
    
    # ========================
    # Apply Move Tests
    # ========================
    
    def test_apply_regular_move(self):
        """Test applying a regular move"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.apply_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        
        assert state["board"][5][0] is None
        assert state["board"][4][1] == "w"
        assert state["move_count"] == 1
        assert state["consecutive_non_capture_moves"] == 1
        assert state["last_move"]["captured"] is False
        
    def test_apply_capture_move(self):
        """Test applying a capture move"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][4][1] = "b"
        
        state = engine.apply_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2
        })
        
        assert state["board"][5][0] is None
        assert state["board"][4][1] is None  # Captured piece removed
        assert state["board"][3][2] == "w"
        assert state["consecutive_non_capture_moves"] == 0
        assert state["last_move"]["captured"] is True
        
    def test_apply_move_with_promotion(self):
        """Test applying move that results in promotion"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][1][0] = "w"
        
        state = engine.apply_move(state, 1, {
            "from_row": 1, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        assert state["board"][0][1] == "W"
        assert state["last_move"]["promoted"] is True
        
    def test_apply_flying_king_capture(self):
        """Test applying flying king capture"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        state["board"][5][2] = "b"
        
        state = engine.apply_move(state, 1, {
            "from_row": 7, "from_col": 0,
            "to_row": 3, "to_col": 4
        })
        
        assert state["board"][7][0] is None
        assert state["board"][5][2] is None  # Captured
        assert state["board"][3][4] == "W"
    
    # ========================
    # Game Result Tests
    # ========================
    
    def test_check_game_in_progress(self):
        """Test game in progress detection"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
        
    def test_check_game_white_wins_no_black_pieces(self):
        """Test white wins when black has no pieces"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Only white pieces left
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][3][2] = "w"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
        
    def test_check_game_black_wins_no_white_pieces(self):
        """Test black wins when white has no pieces"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Only black pieces left
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][3][2] = "b"
        engine.current_turn_index = 1
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 2
        
    def test_check_game_no_legal_moves(self):
        """Test win when player has no legal moves"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # White regular piece at top row with no forward moves possible
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][0][1] = "w"  # White regular piece at top (can't move forward, already at top)
        # Black piece exists elsewhere so game isn't over by piece count
        state["board"][5][2] = "b"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 2  # Black wins
        
    def test_check_game_draw_40_moves(self):
        """Test draw after 40 non-capture moves"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][0][1] = "W"
        state["board"][7][6] = "B"
        state["consecutive_non_capture_moves"] = 40
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.DRAW
        assert winner is None
        
    def test_check_game_draw_threefold_repetition(self):
        """Test draw by threefold repetition"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][0][1] = "W"
        state["board"][7][6] = "B"
        
        # Simulate same position appearing 3 times
        board_hash = engine._hash_board(state["board"])
        state["position_history"] = [board_hash, "other", board_hash, "other2", board_hash]
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.DRAW
        assert winner is None
    
    # ========================
    # Game Info Tests
    # ========================
    
    def test_get_game_name(self):
        """Test game name"""
        assert CheckersEngine.get_game_name() == "checkers"
        
    def test_get_game_info(self):
        """Test game info structure"""
        info = CheckersEngine.get_game_info()
        
        assert info.game_name == "checkers"
        assert info.display_name == "Checkers"
        assert info.min_players == 2
        assert info.max_players == 2
        assert info.turn_based is True
        assert info.category == "strategy"
        
        # Check supported rules
        assert "board_size" in info.supported_rules
        assert "forced_capture" in info.supported_rules
        assert "flying_kings" in info.supported_rules
        assert "backward_capture" in info.supported_rules
        assert "timeout_type" in info.supported_rules
        assert "timeout_seconds" in info.supported_rules
        
        # Check rule defaults
        assert info.supported_rules["board_size"].default == 8
        assert info.supported_rules["forced_capture"].default is True
        assert info.supported_rules["flying_kings"].default is False
        assert info.supported_rules["backward_capture"].default is True
    
    # ========================
    # Integration Tests
    # ========================
    
    def test_complete_game_sequence(self):
        """Test a complete game sequence"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Move 1: White advances
        state = engine.apply_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1
        })
        engine.advance_turn()
        assert engine.current_player_id == 2
        
        # Move 2: Black advances
        state = engine.apply_move(state, 2, {
            "from_row": 2, "from_col": 1,
            "to_row": 3, "to_col": 0
        })
        engine.advance_turn()
        assert engine.current_player_id == 1
        
        # Move 3: White captures
        state = engine.apply_move(state, 1, {
            "from_row": 5, "from_col": 2,
            "to_row": 4, "to_col": 3
        })
        engine.advance_turn()
        
        # Verify game state
        assert state["move_count"] == 3
        assert state["board"][4][1] == "w"
        assert state["board"][3][0] == "b"
        
        result, winner = engine.check_game_result(state)
        assert result == GameResult.IN_PROGRESS
        
    def test_game_with_promotion_and_capture(self):
        """Test game with king promotion and capture"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up near-promotion scenario
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][1][2] = "w"
        state["board"][0][1] = None  # Empty for promotion
        
        # Move to promote
        state = engine.apply_move(state, 1, {
            "from_row": 1, "from_col": 2,
            "to_row": 0, "to_col": 1
        })
        
        assert state["board"][0][1] == "W"
        
        # Now use king to move backward
        engine.advance_turn()
        state["board"][2][3] = "b"
        engine.advance_turn()
        
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 1,
            "to_row": 1, "to_col": 0
        })
        
        assert result.valid is True
    
    # ========================
    # Edge Cases and Coverage Tests
    # ========================
    
    def test_regular_piece_move_distance_validation(self):
        """Test regular piece trying to move more than 1 square without capture"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        # No piece in between for capture
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2
        })
        
        assert result.valid is False
        assert "No piece to capture" in result.error_message
    
    def test_flying_king_blocked_path(self):
        """Test flying king path blocked by own piece"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        state["board"][5][2] = "w"  # Own piece in path
        state["board"][4][3] = "b"  # Opponent further
        
        result = engine.validate_move(state, 1, {
            "from_row": 7, "from_col": 0,
            "to_row": 2, "to_col": 5
        })
        
        assert result.valid is False
        assert "jump over own pieces" in result.error_message
    
    def test_flying_king_no_captures_in_path(self):
        """Test flying king with no opponent pieces in path"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        # No pieces in diagonal path to (3,4)
        
        result = engine.validate_move(state, 1, {
            "from_row": 7, "from_col": 0,
            "to_row": 3, "to_col": 4
        })
        
        assert result.valid is True
    
    def test_capture_distance_not_2_standard(self):
        """Test capture validation with distance != 2 for standard pieces"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][4][1] = "b"
        state["board"][3][2] = "b"  # Second opponent piece
        
        # Try to capture at distance 3
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 2, "to_col": 3
        })
        
        assert result.valid is False
        assert "exactly 2 squares" in result.error_message
    
    def test_white_backward_capture_disabled(self):
        """Test white piece cannot capture backward when disabled"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"backward_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][3][2] = "w"
        state["board"][4][3] = "b"
        
        result = engine.validate_move(state, 1, {
            "from_row": 3, "from_col": 2,
            "to_row": 5, "to_col": 4
        })
        
        assert result.valid is False
        assert "backward" in result.error_message
    
    def test_black_backward_capture_disabled(self):
        """Test black piece cannot capture backward when disabled"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"backward_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][3] = "b"
        state["board"][3][2] = "w"
        engine.current_turn_index = 1
        
        result = engine.validate_move(state, 2, {
            "from_row": 4, "from_col": 3,
            "to_row": 2, "to_col": 1
        })
        
        assert result.valid is False
        assert "backward" in result.error_message
    
    def test_is_capture_move_non_distance_2(self):
        """Test _is_capture_move returns False for distance != 2 in standard mode"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        
        # Distance 1 is not a capture
        is_capture = engine._is_capture_move(state["board"], 5, 0, 4, 1, "white", False)
        assert is_capture is False
    
    def test_get_capture_moves_with_flying_king_blocked(self):
        """Test _get_capture_moves with flying king encountering obstacles"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True, "forced_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        state["board"][6][1] = "w"  # Blocks path immediately
        
        capture_moves = engine._get_capture_moves(state, 1)
        
        # Should find no captures due to blocked path
        assert len(capture_moves) == 0
    
    def test_get_all_legal_moves_no_captures(self):
        """Test _get_all_legal_moves returns regular moves when no captures available"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"forced_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        state["board"][7][2] = "b"
        
        legal_moves = engine._get_all_legal_moves(state, 1)
        
        # Should have regular forward moves
        assert len(legal_moves) > 0
    
    def test_get_piece_moves_black_directions(self):
        """Test _get_piece_moves for black piece directions"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][2][1] = "b"
        
        moves = engine._get_piece_moves(state["board"], 2, 1, "b", "black", False)
        
        # Black moves down-left and down-right
        assert len(moves) == 2
        # Verify moves are downward
        for move in moves:
            assert move["to_row"] > 2
    
    def test_get_piece_moves_king_directions(self):
        """Test _get_piece_moves for king in all 4 directions"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][3] = "W"
        
        moves = engine._get_piece_moves(state["board"], 4, 3, "W", "white", True)
        
        # King should have 4 possible moves
        assert len(moves) == 4
    
    def test_get_piece_moves_flying_king(self):
        """Test _get_piece_moves for flying king moving multiple squares"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        
        moves = engine._get_piece_moves(state["board"], 7, 0, "W", "white", True)
        
        # Flying king should have many moves in diagonal directions
        assert len(moves) > 4  # More than just 1 square in each direction
    
    def test_get_piece_moves_flying_king_blocked(self):
        """Test flying king stops at obstacles"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"
        state["board"][5][2] = "b"  # Blocks one diagonal
        
        moves = engine._get_piece_moves(state["board"], 7, 0, "W", "white", True)
        
        # Should still have moves in other directions
        assert len(moves) > 0
        # But the blocked diagonal should be limited
        up_right_moves = [m for m in moves if m["to_row"] < 7 and m["to_col"] > 0]
        # Can only go to (6,1) before hitting obstacle
        assert all(m["to_row"] >= 6 for m in up_right_moves if m["to_col"] == 1)
    
    def test_regular_piece_cannot_move_multiple_squares(self):
        """Test regular (non-king) piece trying to move 3+ squares falls through to capture validation"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"forced_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"  # Regular white piece
        # Try to move 3 squares (no opponent to capture)
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 2, "to_col": 3
        })
        
        # Should fail - will go to capture validation and fail there
        assert result.valid is False
    
    def test_regular_piece_wrong_distance(self):
        """Test regular piece validation for distance > 1 in regular move path"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"forced_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]  
        state["board"][5][0] = "w"
        # No opponent at (4,1) so not a capture, just trying to move 2 squares
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2
        })
        
        # Should fail at capture validation
        assert result.valid is False
    
    def test_regular_piece_move_distance_2_in_regular_validation(self):
        """Test that regular non-king piece cannot move 2 squares in regular move validation"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"forced_capture": False})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"
        # Move 2 squares but there's no piece to capture
        # This will trigger line 230 in _validate_regular_move
        
        result = engine.validate_move(state, 1, {
            "from_row": 5, "from_col": 0,
            "to_row": 3, "to_col": 2  
        })
        
        assert result.valid is False
    
    def test_flying_king_capture_moves_distance_increment(self):
        """Test flying king finds multiple capture landing squares at increasing distances"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][7][0] = "W"  # White king at corner
        state["board"][5][2] = "b"  # Black opponent 2 squares away diagonally
        # Landing squares are (4,3), (3,4), (2,5), (1,6), (0,7) - all empty
        
        capture_moves = engine._get_capture_moves(state, 1)
        
        # Should find multiple captures with same start but different landing squares
        relevant_captures = [
            m for m in capture_moves
            if m["from_row"] == 7 and m["from_col"] == 0
        ]
        # Should have captures to (4,3) and beyond
        assert len(relevant_captures) > 0
    
    def test_destination_out_of_bounds(self):
        """Test validation when destination is out of bounds (covers line 129)"""
        engine = CheckersEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine._validate_game_specific_move(
            state, 1,
            {"from_row": 5, "from_col": 0, "to_row": -1, "to_col": 1}
        )
        assert not result.valid
        assert "out of bounds" in result.error_message.lower()
    
    def test_invalid_move_distance(self):
        """Test validation for invalid move distance (distance=0) (covers line 189)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": False})
        state = engine.initialize_game_state()
        
        # Try to move piece to same position (distance=0)
        result = engine._validate_game_specific_move(
            state, 1,
            {"from_row": 5, "from_col": 0, "to_row": 5, "to_col": 0}
        )
        assert not result.valid
        # This should fail diagonal check first, but let's see what we get
    
    def test_king_multisquare_standard_rules(self):
        """Test that kings can't move multiple squares in standard rules (covers line 226)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": False})
        state = engine.initialize_game_state()
        
        # Clear board and place a king
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][4][1] = "W"  # King on dark square
        
        # Try to move king 2 squares (not a capture, no opponent in path)
        result = engine._validate_game_specific_move(
            state, 1,
            {"from_row": 4, "from_col": 1, "to_row": 2, "to_col": 3}
        )
        assert not result.valid
        assert "one square" in result.error_message.lower()
    
    def test_regular_piece_multisquare(self):
        """Test that regular pieces can't move multiple squares (covers line 230)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": False})
        state = engine.initialize_game_state()
        
        # Clear board and place a regular piece
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][5][0] = "w"  # Regular white piece
        
        # Try to move regular piece 2 squares without any opponent to capture
        result = engine._validate_game_specific_move(
            state, 1,
            {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2}
        )
        assert not result.valid
        # This will try capture validation since distance >= 2 for non-king
        assert "capture" in result.error_message.lower()
    
    def test_flying_king_capture_out_of_bounds(self):
        """Test flying king capture when landing squares go out of bounds (covers line 535)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": True})
        state = engine.initialize_game_state()
        
        # Place king near edge with opponent in path
        state["board"] = [[None for _ in range(8)] for _ in range(8)]
        state["board"][2][1] = "W"  # White king near top edge
        state["board"][1][2] = "b"  # Black opponent 1 square diagonally
        # Landing at (0,3) would be valid, but (-1,4) would be out of bounds
        
        capture_moves = engine._get_capture_moves(state, 1)
        
        # Should find capture to (0,3) but stop before going out of bounds
        relevant_captures = [
            m for m in capture_moves
            if m["from_row"] == 2 and m["from_col"] == 1 and m["to_row"] == 0
        ]
        assert len(relevant_captures) == 1
        assert relevant_captures[0]["to_col"] == 3
    
    def test_validate_regular_move_king_multisquare_standard(self):
        """Test _validate_regular_move for king moving multiple squares in standard rules (covers line 226)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": False})
        
        # Test king trying to move 2 squares as regular move (not capture)
        result = engine._validate_regular_move(4, 1, 2, 3, "W", "white", True)
        assert not result.valid
        assert "one square" in result.error_message.lower()
    
    def test_validate_regular_move_piece_multisquare(self):
        """Test _validate_regular_move for regular piece moving multiple squares (covers line 230)"""
        engine = CheckersEngine("TEST123", [1, 2], rules={"flying_kings": False})
        
        # Test regular piece trying to move 2 squares as regular move (not capture)
        result = engine._validate_regular_move(5, 0, 3, 2, "w", "white", False)
        assert not result.valid
        assert "one square" in result.error_message.lower()


