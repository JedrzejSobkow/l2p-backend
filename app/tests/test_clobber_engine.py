# app/tests/test_clobber_engine.py

import pytest
from services.games.clobber_engine import ClobberEngine
from services.game_engine_interface import GameResult


class TestClobberEngine:
    """Tests for ClobberEngine"""
    
    def test_initialization_standard(self):
        """Test standard clobber initialization"""
        engine = ClobberEngine("TEST123", [1, 2])
        
        assert engine.lobby_code == "TEST123"
        assert engine.player_ids == [1, 2]
        assert engine.board_width == 6
        assert engine.board_height == 5
        assert engine.starting_pattern == "checkerboard"
        assert engine.current_player_id == 1
        
    def test_initialization_custom_board_size(self):
        """Test custom board size"""
        engine = ClobberEngine("TEST123", [1, 2], rules={"board_width": 8, "board_height": 7})
        
        assert engine.board_width == 8
        assert engine.board_height == 7
        
    def test_initialization_custom_starting_pattern(self):
        """Test custom starting pattern"""
        engine = ClobberEngine("TEST123", [1, 2], rules={"starting_pattern": "rows"})
        
        assert engine.starting_pattern == "rows"
        
    def test_initialization_invalid_player_count(self):
        """Test that initialization fails with wrong number of players"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            ClobberEngine("TEST123", [1, 2, 3])
            
    def test_initialization_single_player(self):
        """Test that initialization fails with only one player"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            ClobberEngine("TEST123", [1])
    
    def test_initialize_game_state_checkerboard(self):
        """Test game state initialization with checkerboard pattern"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert "board" in state
        assert len(state["board"]) == 5
        assert len(state["board"][0]) == 6
        assert state["move_count"] == 0
        assert state["last_move"] is None
        
        # Verify checkerboard pattern
        board = state["board"]
        for row in range(5):
            for col in range(6):
                if (row + col) % 2 == 0:
                    assert board[row][col] == "W"
                else:
                    assert board[row][col] == "B"
                    
    def test_initialize_game_state_rows_pattern(self):
        """Test game state initialization with rows pattern"""
        engine = ClobberEngine("TEST123", [1, 2], rules={"starting_pattern": "rows"})
        state = engine.initialize_game_state()
        
        board = state["board"]
        # Verify rows pattern
        for row in range(5):
            expected_color = "W" if row % 2 == 0 else "B"
            for col in range(6):
                assert board[row][col] == expected_color
                
    def test_validate_move_valid(self):
        """Test valid move validation"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # In checkerboard pattern, (0,0) is W and (0,1) is B
        # Player 1 controls W, so they can capture (0,1)
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        assert result.valid is True
        assert result.error_message is None
        
    def test_validate_move_wrong_turn(self):
        """Test validation fails for wrong player's turn"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 2's turn hasn't started yet
        result = engine.validate_move(state, 2, {
            "from_row": 0, "from_col": 1,
            "to_row": 0, "to_col": 0
        })
        
        assert result.valid is False
        assert "not your turn" in result.error_message
        
    def test_validate_move_missing_fields(self):
        """Test validation fails when required fields are missing"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Missing 'to_col'
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0, "to_row": 0
        })
        
        assert result.valid is False
        assert "to_col" in result.error_message
        
    def test_validate_move_invalid_coordinates(self):
        """Test validation fails for non-integer coordinates"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {
            "from_row": "invalid", "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        assert result.valid is False
        assert "must be integers" in result.error_message
        
    def test_validate_move_out_of_bounds_start(self):
        """Test validation fails for out of bounds starting position"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {
            "from_row": 10, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        assert result.valid is False
        assert "out of bounds" in result.error_message
        
    def test_validate_move_out_of_bounds_destination(self):
        """Test validation fails for out of bounds destination"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 10
        })
        
        assert result.valid is False
        assert "out of bounds" in result.error_message
        
    def test_validate_move_no_piece_at_start(self):
        """Test validation fails when no player's piece at starting position"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 (W) trying to move from a B position
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 1,  # This is B
            "to_row": 0, "to_col": 0
        })
        
        assert result.valid is False
        assert "No piece of yours" in result.error_message
        
    def test_validate_move_diagonal_not_allowed(self):
        """Test validation fails for diagonal moves"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Try diagonal move from (0,0) to (1,1)
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 1, "to_col": 1
        })
        
        assert result.valid is False
        assert "orthogonally adjacent" in result.error_message
        
    def test_validate_move_too_far(self):
        """Test validation fails for moves more than 1 cell away"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Try to move 2 cells away
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 2
        })
        
        assert result.valid is False
        assert "orthogonally adjacent" in result.error_message
        
    def test_validate_move_empty_destination(self):
        """Test validation fails when trying to move to empty cell"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Clear a cell
        state["board"][0][2] = None
        
        # Try to move to empty cell
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 2
        })
        
        assert result.valid is False
        # Should fail because it's too far, but if it was adjacent, it should fail for being empty
        
        # Let's make an adjacent cell empty
        state["board"][1][0] = None
        
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 1, "to_col": 0
        })
        
        assert result.valid is False
        assert "must capture" in result.error_message
        
    def test_validate_move_capturing_own_piece(self):
        """Test validation fails when trying to capture own piece"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # In checkerboard: (0,0)=W, (0,2)=W, (1,1)=W
        # Manually set up adjacent same-color pieces
        state["board"][0][0] = "W"
        state["board"][1][0] = "W"  # Make this W instead of B
        
        # Player 1 (W) cannot capture their own piece
        result = engine.validate_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 1, "to_col": 0  # Trying to capture own piece
        })
        
        assert result.valid is False
        assert "must capture" in result.error_message
        
    def test_apply_move(self):
        """Test applying a valid move"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 (W) captures (0,1) which is B
        state = engine.apply_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        assert state["board"][0][0] is None  # Original position empty
        assert state["board"][0][1] == "W"   # New position has W
        assert state["move_count"] == 1
        assert state["last_move"]["player_id"] == 1
        assert state["last_move"]["from_row"] == 0
        assert state["last_move"]["to_row"] == 0
        
    def test_check_game_in_progress(self):
        """Test game in progress detection"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Make one move
        state = engine.apply_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
        
    def test_check_game_result_no_moves(self):
        """Test win detection when player has no legal moves"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Create a board state where current player has no moves
        # Clear the board and place pieces strategically
        board = [[None for _ in range(6)] for _ in range(5)]
        board[0][0] = "W"  # Player 1's piece
        board[2][2] = "W"  # Another W piece isolated
        # No B pieces adjacent to any W piece
        state["board"] = board
        
        engine.current_turn_index = 0  # Player 1's turn (W)
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 2  # Player 2 wins because Player 1 can't move
        
    def test_get_legal_moves(self):
        """Test getting legal moves for a player"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # In standard checkerboard, player 1 (W) should have moves
        legal_moves = engine._get_legal_moves(state, 1)
        
        assert len(legal_moves) > 0
        # Each move should have required fields
        for move in legal_moves:
            assert "from_row" in move
            assert "from_col" in move
            assert "to_row" in move
            assert "to_col" in move
            
    def test_get_legal_moves_no_moves_available(self):
        """Test getting legal moves when none are available"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Create a board where player has no moves
        board = [[None for _ in range(6)] for _ in range(5)]
        board[0][0] = "W"
        state["board"] = board
        
        legal_moves = engine._get_legal_moves(state, 1)
        
        assert len(legal_moves) == 0
        
    def test_advance_turn(self):
        """Test turn advancement"""
        engine = ClobberEngine("TEST123", [1, 2])
        
        assert engine.current_player_id == 1
        
        engine.advance_turn()
        assert engine.current_player_id == 2
        
        engine.advance_turn()
        assert engine.current_player_id == 1
        
    def test_forfeit_game(self):
        """Test game forfeit"""
        engine = ClobberEngine("TEST123", [1, 2])
        
        result, winner = engine.forfeit_game(1)
        
        assert result == GameResult.FORFEIT
        assert winner == 2
        
    def test_full_game_flow(self):
        """Test a complete game flow with multiple moves"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Sequence of moves (this is illustrative)
        moves = [
            (1, {"from_row": 0, "from_col": 0, "to_row": 0, "to_col": 1}),  # W captures B
            (2, {"from_row": 0, "from_col": 2, "to_row": 0, "to_col": 1}),  # B captures W
            (1, {"from_row": 1, "from_col": 0, "to_row": 0, "to_col": 0}),  # W moves
        ]
        
        for i, (player_id, move_data) in enumerate(moves):
            # Validate move
            validation = engine.validate_move(state, player_id, move_data)
            
            if not validation.valid:
                # Skip invalid moves in this test
                continue
                
            # Apply move
            state = engine.apply_move(state, player_id, move_data)
            
            # Check result
            result, winner = engine.check_game_result(state)
            
            # Game should still be in progress for early moves
            if result != GameResult.IN_PROGRESS:
                assert result == GameResult.PLAYER_WIN
                assert winner is not None
                break
                
            engine.advance_turn()
            
    def test_custom_small_board(self):
        """Test game with custom small board"""
        engine = ClobberEngine("TEST123", [1, 2], rules={"board_width": 4, "board_height": 4})
        state = engine.initialize_game_state()
        
        assert len(state["board"]) == 4
        assert len(state["board"][0]) == 4
        
    def test_custom_large_board(self):
        """Test game with custom large board"""
        engine = ClobberEngine("TEST123", [1, 2], rules={"board_width": 10, "board_height": 10})
        state = engine.initialize_game_state()
        
        assert len(state["board"]) == 10
        assert len(state["board"][0]) == 10
        
    def test_is_valid_position(self):
        """Test position validation helper"""
        engine = ClobberEngine("TEST123", [1, 2])
        
        assert engine._is_valid_position(0, 0) is True
        assert engine._is_valid_position(4, 5) is True
        assert engine._is_valid_position(-1, 0) is False
        assert engine._is_valid_position(0, -1) is False
        assert engine._is_valid_position(5, 0) is False  # height is 5, so max row is 4
        assert engine._is_valid_position(0, 6) is False  # width is 6, so max col is 5
        
    def test_player_colors_assignment(self):
        """Test that player colors are correctly assigned"""
        engine = ClobberEngine("TEST123", [10, 20])
        
        assert engine.player_colors[10] == "W"
        assert engine.player_colors[20] == "B"
        
    def test_legal_moves_all_directions(self):
        """Test that legal moves are found in all orthogonal directions"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Create a specific board state
        # Place W in center with B pieces around it
        board = [[None for _ in range(6)] for _ in range(5)]
        board[2][2] = "W"  # Center
        board[2][1] = "B"  # Left
        board[2][3] = "B"  # Right
        board[1][2] = "B"  # Up
        board[3][2] = "B"  # Down
        state["board"] = board
        
        legal_moves = engine._get_legal_moves(state, 1)
        
        # Should have exactly 4 legal moves (one in each direction)
        assert len(legal_moves) == 4
        
        # Verify all directions are covered
        directions = set()
        for move in legal_moves:
            if move["to_row"] < move["from_row"]:
                directions.add("up")
            elif move["to_row"] > move["from_row"]:
                directions.add("down")
            elif move["to_col"] < move["from_col"]:
                directions.add("left")
            elif move["to_col"] > move["from_col"]:
                directions.add("right")
                
        assert directions == {"up", "down", "left", "right"}
        
    def test_game_state_after_capture(self):
        """Test game state is correctly updated after capture"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Count pieces before
        white_before = sum(1 for row in state["board"] for cell in row if cell == "W")
        black_before = sum(1 for row in state["board"] for cell in row if cell == "B")
        
        # Player 1 (W) captures a B piece
        state = engine.apply_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        
        # Count pieces after
        white_after = sum(1 for row in state["board"] for cell in row if cell == "W")
        black_after = sum(1 for row in state["board"] for cell in row if cell == "B")
        
        # White count should stay same (moved one piece)
        assert white_after == white_before
        # Black count should decrease by 1 (one captured)
        assert black_after == black_before - 1
        
    def test_last_move_tracking(self):
        """Test that last move is properly tracked"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert state["last_move"] is None
        
        # Make a move
        move_data = {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 1
        }
        state = engine.apply_move(state, 1, move_data)
        
        assert state["last_move"] is not None
        assert state["last_move"]["player_id"] == 1
        assert state["last_move"]["from_row"] == 0
        assert state["last_move"]["from_col"] == 0
        assert state["last_move"]["to_row"] == 0
        assert state["last_move"]["to_col"] == 1
        assert state["last_move"]["color"] == "W"
        
    def test_move_count_increments(self):
        """Test that move count increments correctly"""
        engine = ClobberEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert state["move_count"] == 0
        
        # Make moves
        state = engine.apply_move(state, 1, {
            "from_row": 0, "from_col": 0,
            "to_row": 0, "to_col": 1
        })
        assert state["move_count"] == 1
        
        engine.advance_turn()
        state = engine.apply_move(state, 2, {
            "from_row": 0, "from_col": 2,
            "to_row": 0, "to_col": 1
        })
        assert state["move_count"] == 2
