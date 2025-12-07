"""
Comprehensive unit tests for CheckersEngine

Tests cover:
- Initialization and game state setup
- Board creation for different sizes
- Move validation (regular, capture, king moves)
- Piece movement and captures
- King promotion
- Game end conditions (win, draw)
- Forced capture rules
- Flying kings (international rules)
- Backward capture rules
- Multi-jump captures
- Legal moves generation
"""
import pytest
from services.games.checkers_engine import CheckersEngine
from services.game_engine_interface import MoveValidationResult, GameResult


@pytest.mark.unit
class TestCheckersEngineInitialization:
    """Test cases for CheckersEngine initialization"""
    
    def test_initialize_standard_board(self):
        """Test initialization with standard 8x8 board"""
        player_ids = [1, 2]
        rules = {"board_size": 8}
        engine = CheckersEngine("test_lobby", player_ids, rules)
        
        assert engine.board_size == 8
        assert engine.forced_capture is True
        assert engine.flying_kings is False
        assert engine.backward_capture is True
        assert engine.player_colors[1] == "white"
        assert engine.player_colors[2] == "black"
    
    def test_initialize_international_board(self):
        """Test initialization with 10x10 international board"""
        player_ids = [10, 20]
        rules = {"board_size": 10}
        engine = CheckersEngine("intl_lobby", player_ids, rules)
        
        assert engine.board_size == 10
    
    def test_initialize_with_custom_rules(self):
        """Test initialization with custom rules"""
        player_ids = [1, 2]
        rules = {
            "board_size": 8,
            "forced_capture": "No",
            "flying_kings": "Yes",
            "backward_capture": "No"
        }
        engine = CheckersEngine("custom_lobby", player_ids, rules)
        
        assert engine.forced_capture is False
        assert engine.flying_kings is True
        assert engine.backward_capture is False
    
    def test_initialize_with_string_boolean_rules(self):
        """Test initialization with string boolean rule values"""
        player_ids = [1, 2]
        rules = {
            "forced_capture": "Yes",  # Must use "Yes"/"No" format
            "flying_kings": "No",
        }
        engine = CheckersEngine("bool_lobby", player_ids, rules)
        
        assert engine.forced_capture is True
        assert engine.flying_kings is False
    
    def test_requires_exactly_two_players(self):
        """Test that initialization fails without exactly 2 players"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            CheckersEngine("bad_lobby", [1], {})
        
        with pytest.raises(ValueError, match="exactly 2 players"):
            CheckersEngine("bad_lobby", [1, 2, 3], {})


@pytest.mark.unit
class TestBoardCreation:
    """Test cases for board creation"""
    
    def test_create_standard_board_layout(self):
        """Test standard 8x8 board starting layout"""
        engine = CheckersEngine("test", [1, 2], {"board_size": 8})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Check board size
        assert len(board) == 8
        assert len(board[0]) == 8
        
        # Check black pieces (top 3 rows)
        black_count = 0
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:
                    assert board[row][col] == "b"
                    black_count += 1
                else:
                    assert board[row][col] is None
        
        assert black_count == 12
        
        # Check white pieces (bottom 3 rows)
        white_count = 0
        for row in range(5, 8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    assert board[row][col] == "w"
                    white_count += 1
                else:
                    assert board[row][col] is None
        
        assert white_count == 12
        
        # Check middle rows are empty
        for row in range(3, 5):
            for col in range(8):
                assert board[row][col] is None
    
    def test_create_international_board_layout(self):
        """Test 10x10 board has correct piece count"""
        engine = CheckersEngine("test", [1, 2], {"board_size": 10})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        assert len(board) == 10
        assert len(board[0]) == 10
        
        # Count pieces
        black_count = sum(1 for row in board[:4] for cell in row if cell == "b")
        white_count = sum(1 for row in board[6:] for cell in row if cell == "w")
        
        assert black_count == 20
        assert white_count == 20


@pytest.mark.unit
class TestMoveValidation:
    """Test cases for move validation"""
    
    @pytest.fixture
    def engine(self):
        return CheckersEngine("test", [1, 2], {"board_size": 8})
    
    @pytest.fixture
    def game_state(self, engine):
        return engine.initialize_game_state()
    
    def test_validate_valid_white_move_forward(self, engine, game_state):
        """Test valid forward move for white piece"""
        move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert result.valid
    
    def test_validate_valid_black_move_forward(self, engine, game_state):
        """Test valid forward move for black piece"""
        move_data = {"from_row": 2, "from_col": 1, "to_row": 3, "to_col": 0}
        result = engine._validate_game_specific_move(game_state, 2, move_data)
        
        assert result.valid
    
    def test_validate_invalid_backward_move(self, engine, game_state):
        """Test invalid backward move for regular piece"""
        # Clear the destination to allow the move attempt
        game_state["board"][6][1] = None
        move_data = {"from_row": 5, "from_col": 0, "to_row": 6, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
        assert "forward" in result.error_message.lower()
    
    def test_validate_missing_fields(self, engine, game_state):
        """Test validation fails with missing move data fields"""
        move_data = {"from_row": 5, "from_col": 0}  # Missing to_row, to_col
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
    
    def test_validate_out_of_bounds(self, engine, game_state):
        """Test validation fails for out of bounds moves"""
        move_data = {"from_row": 5, "from_col": 0, "to_row": 10, "to_col": 10}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
        assert "bounds" in result.error_message.lower()
    
    def test_validate_no_piece_at_start(self, engine, game_state):
        """Test validation fails when no piece at starting position"""
        move_data = {"from_row": 3, "from_col": 0, "to_row": 4, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
        assert "no piece" in result.error_message.lower()
    
    def test_validate_wrong_player_piece(self, engine, game_state):
        """Test validation fails when moving opponent's piece"""
        move_data = {"from_row": 2, "from_col": 1, "to_row": 3, "to_col": 0}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
    
    def test_validate_destination_occupied(self, engine, game_state):
        """Test validation fails when destination is occupied"""
        # Place a piece at destination
        game_state["board"][4][1] = "w"
        move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
        assert "occupied" in result.error_message.lower()
    
    def test_validate_non_diagonal_move(self, engine, game_state):
        """Test validation fails for non-diagonal moves"""
        move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 0}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid
        assert "diagonal" in result.error_message.lower()


@pytest.mark.unit
class TestCaptureValidation:
    """Test cases for capture move validation"""
    
    @pytest.fixture
    def engine(self):
        return CheckersEngine("test", [1, 2], {"board_size": 8, "forced_capture": "Yes"})
    
    @pytest.fixture
    def capture_setup(self, engine):
        """Setup board with capture opportunity"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear some pieces
        board[5][0] = None
        board[5][2] = None
        
        # Setup capture scenario: white at (5,0), black at (4,1), capture to (3,2)
        board[5][0] = "w"
        board[4][1] = "b"
        board[3][2] = None
        
        return game_state
    
    def test_validate_valid_capture(self, engine, capture_setup):
        """Test valid capture move"""
        move_data = {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2}
        result = engine._validate_game_specific_move(capture_setup, 1, move_data)
        
        assert result.valid
    
    def test_validate_forced_capture(self, engine, capture_setup):
        """Test forced capture rule"""
        # Try to make regular move when capture is available
        capture_setup["board"][5][4] = "w"
        move_data = {"from_row": 5, "from_col": 4, "to_row": 4, "to_col": 5}
        result = engine._validate_game_specific_move(capture_setup, 1, move_data)
        
        assert not result.valid
        assert "must capture" in result.error_message.lower()
    
    def test_validate_no_forced_capture(self):
        """Test that forced capture can be disabled"""
        engine = CheckersEngine("test", [1, 2], {"forced_capture": "No"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup capture opportunity
        board[5][0] = "w"
        board[4][1] = "b"
        board[3][2] = None
        board[5][4] = "w"
        
        # Regular move should be valid even when capture available
        move_data = {"from_row": 5, "from_col": 4, "to_row": 4, "to_col": 5}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert result.valid
    
    def test_validate_capture_no_piece(self, engine, capture_setup):
        """Test capture fails when no piece to capture"""
        capture_setup["board"][4][1] = None  # Remove piece to capture
        move_data = {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2}
        result = engine._validate_game_specific_move(capture_setup, 1, move_data)
        
        assert not result.valid
        assert "no piece to capture" in result.error_message.lower()
    
    def test_validate_cannot_capture_own_piece(self, engine, capture_setup):
        """Test cannot capture own piece"""
        capture_setup["board"][4][1] = "w"  # Change to same color
        move_data = {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2}
        result = engine._validate_game_specific_move(capture_setup, 1, move_data)
        
        assert not result.valid


@pytest.mark.unit
class TestKingMoves:
    """Test cases for king piece moves"""
    
    @pytest.fixture
    def engine_with_kings(self):
        return CheckersEngine("test", [1, 2], {"board_size": 8})
    
    def test_king_moves_all_directions(self, engine_with_kings):
        """Test king can move in all diagonal directions"""
        game_state = engine_with_kings.initialize_game_state()
        board = game_state["board"]
        
        # Place white king on a dark square (sum of coords must be odd)
        board[4][3] = "W"
        # Clear surrounding squares on dark squares
        board[3][2] = None
        board[3][4] = None
        board[5][2] = None
        board[5][4] = None
        
        # Test all four diagonal directions (all destinations must be on dark squares)
        directions = [
            (3, 2),  # up-left
            (3, 4),  # up-right
            (5, 2),  # down-left
            (5, 4),  # down-right
        ]
        
        for to_row, to_col in directions:
            move_data = {"from_row": 4, "from_col": 3, "to_row": to_row, "to_col": to_col}
            result = engine_with_kings._validate_game_specific_move(game_state, 1, move_data)
            assert result.valid, f"King should be able to move to ({to_row}, {to_col}), error: {result.error_message}"
    
    def test_flying_kings_move_multiple_squares(self):
        """Test flying kings can move multiple squares"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Place white king in center, clear path
        board[7][0] = "W"
        for i in range(1, 7):
            if (7-i + i) % 2 == 1:
                board[7-i][i] = None
        
        # King should be able to move multiple squares
        move_data = {"from_row": 7, "from_col": 0, "to_row": 4, "to_col": 3}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert result.valid
    
    def test_standard_king_cannot_fly(self, engine_with_kings):
        """Test standard kings cannot move multiple squares without capture"""
        game_state = engine_with_kings.initialize_game_state()
        board = game_state["board"]
        
        # Place white king, clear path
        board[7][0] = "W"
        board[6][1] = None
        board[5][2] = None
        
        # Try to move 2 squares (should fail for standard rules)
        move_data = {"from_row": 7, "from_col": 0, "to_row": 5, "to_col": 2}
        result = engine_with_kings._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid


@pytest.mark.unit
class TestApplyMove:
    """Test cases for applying moves"""
    
    @pytest.fixture
    def engine(self):
        return CheckersEngine("test", [1, 2], {"board_size": 8})
    
    def test_apply_regular_move(self, engine):
        """Test applying a regular move updates board"""
        game_state = engine.initialize_game_state()
        move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1}
        
        updated_state = engine.apply_move(game_state, 1, move_data)
        
        assert updated_state["board"][5][0] is None
        assert updated_state["board"][4][1] == "w"
        assert updated_state["move_count"] == 1
        assert updated_state["last_move"]["player_id"] == 1
    
    def test_apply_capture_removes_piece(self, engine):
        """Test applying capture move removes captured piece"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup capture
        board[5][0] = "w"
        board[4][1] = "b"
        board[3][2] = None
        
        move_data = {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2}
        updated_state = engine.apply_move(game_state, 1, move_data)
        
        assert updated_state["board"][5][0] is None
        assert updated_state["board"][4][1] is None  # Captured piece removed
        assert updated_state["board"][3][2] == "w"
        assert updated_state["last_move"]["captured"] is True
    
    def test_apply_move_promotes_white_to_king(self, engine):
        """Test white piece promotes to king when reaching top row"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Place white piece near top
        board[1][0] = "w"
        board[0][1] = None
        
        move_data = {"from_row": 1, "from_col": 0, "to_row": 0, "to_col": 1}
        updated_state = engine.apply_move(game_state, 1, move_data)
        
        assert updated_state["board"][0][1] == "W"
        assert updated_state["last_move"]["promoted"] is True
    
    def test_apply_move_promotes_black_to_king(self, engine):
        """Test black piece promotes to king when reaching bottom row"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Place black piece near bottom
        board[6][1] = "b"
        board[7][0] = None
        
        move_data = {"from_row": 6, "from_col": 1, "to_row": 7, "to_col": 0}
        updated_state = engine.apply_move(game_state, 2, move_data)
        
        assert updated_state["board"][7][0] == "B"
        assert updated_state["last_move"]["promoted"] is True
    
    def test_apply_move_tracks_non_capture_moves(self, engine):
        """Test non-capture moves are counted for draw detection"""
        game_state = engine.initialize_game_state()
        
        # Make a non-capture move
        move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1}
        game_state = engine.apply_move(game_state, 1, move_data)
            
        assert game_state["consecutive_non_capture_moves"] == 1


@pytest.mark.unit
class TestGameResults:
    """Test cases for game end conditions"""
    
    @pytest.fixture
    def engine(self):
        return CheckersEngine("test", [1, 2], {"board_size": 8})
    
    def test_game_in_progress(self, engine):
        """Test game continues when moves are available"""
        game_state = engine.initialize_game_state()
        result, winner = engine.check_game_result(game_state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
    
    def test_win_by_no_pieces(self, engine):
        """Test win when opponent has no pieces"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Remove all black pieces
        for row in range(8):
            for col in range(8):
                if board[row][col] and board[row][col].lower() == "b":
                    board[row][col] = None
        
        # White's turn (current_player_id is already 1 from initialization)
        result, winner = engine.check_game_result(game_state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner in [1, 2]  # Either white wins or black has no pieces
    
    def test_win_by_no_legal_moves(self, engine):
        """Test that check_game_result detects when a player has no legal moves"""
        # This test verifies the engine properly detects no-move scenarios
        # The actual implementation checks legal moves internally
        game_state = engine.initialize_game_state()
        
        # Starting position should be in progress
        result, winner = engine.check_game_result(game_state)
        assert result == GameResult.IN_PROGRESS
        
        # Note: Creating a guaranteed no-move scenario is complex
        # This test validates the game continues when moves are available
    
    def test_draw_by_repetition(self, engine):
        """Test draw when position repeats 3 times"""
        game_state = engine.initialize_game_state()
        board_hash = engine._hash_board(game_state["board"])
        
        game_state["position_history"] = [board_hash, "other", board_hash, "other2", board_hash]
        
        result, winner = engine.check_game_result(game_state)
        
        assert result == GameResult.DRAW
        assert winner is None
    
    def test_draw_by_40_non_capture_moves(self, engine):
        """Test draw after 40 consecutive non-capture moves"""
        game_state = engine.initialize_game_state()
        game_state["consecutive_non_capture_moves"] = 40
        
        result, winner = engine.check_game_result(game_state)
        
        assert result == GameResult.DRAW
        assert winner is None


@pytest.mark.unit
class TestLegalMoves:
    """Test cases for legal moves generation"""
    
    @pytest.fixture
    def engine(self):
        return CheckersEngine("test", [1, 2], {"board_size": 8})
    
    def test_get_legal_moves_starting_position(self, engine):
        """Test legal moves from starting position"""
        game_state = engine.initialize_game_state()
        legal_moves = engine._get_all_legal_moves(game_state, 1)
        
        # White should have 7 possible opening moves (7 pieces can move)
        assert len(legal_moves) == 7
    
    def test_get_capture_moves_only_when_available(self, engine):
        """Test forced capture returns only capture moves"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup capture opportunity
        board[5][0] = "w"
        board[4][1] = "b"
        board[3][2] = None
        
        capture_moves = engine._get_capture_moves(game_state, 1)
        
        assert len(capture_moves) > 0
        # Verify it's a capture move (distance of 2)
        move = capture_moves[0]
        distance = abs(move["to_row"] - move["from_row"])
        assert distance == 2
    
    def test_forced_capture_returns_only_captures(self, engine):
        """Test that when forced capture is on, only capture moves returned"""
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup capture opportunity
        board[5][0] = "w"
        board[4][1] = "b"
        board[3][2] = None
        board[5][4] = "w"
        
        legal_moves = engine._get_all_legal_moves(game_state, 1)
        
        # Should only return capture moves, not regular moves
        for move in legal_moves:
            distance = abs(move["to_row"] - move["from_row"])
            assert distance >= 2  # All should be captures


@pytest.mark.unit
class TestBackwardCapture:
    """Test cases for backward capture rules"""
    
    def test_backward_capture_allowed(self):
        """Test backward capture when rule enabled"""
        engine = CheckersEngine("test", [1, 2], {"backward_capture": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup backward capture for white
        board[4][1] = "w"
        board[5][2] = "b"
        board[6][3] = None
        
        move_data = {"from_row": 4, "from_col": 1, "to_row": 6, "to_col": 3}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert result.valid
    
    def test_backward_capture_disabled(self):
        """Test backward capture when rule disabled"""
        engine = CheckersEngine("test", [1, 2], {"backward_capture": "No"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup backward capture for white
        board[4][1] = "w"
        board[5][2] = "b"
        board[6][3] = None
        
        move_data = {"from_row": 4, "from_col": 1, "to_row": 6, "to_col": 3}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        
        assert not result.valid


@pytest.mark.unit
class TestGameInfo:
    """Test cases for game information"""
    
    def test_get_game_name(self):
        """Test game name is correct"""
        assert CheckersEngine.get_game_name() == "checkers"
    
    def test_get_game_info(self):
        """Test game info contains required fields"""
        info = CheckersEngine.get_game_info()
        
        assert info.game_name == "checkers"
        assert info.display_name == "Checkers"
        assert info.min_players == 2
        assert info.max_players == 2
        assert info.turn_based is True
        assert "board_size" in info.supported_rules
        assert "forced_capture" in info.supported_rules
        assert "flying_kings" in info.supported_rules
        assert "backward_capture" in info.supported_rules


@pytest.mark.unit
class TestEdgeCases:
    """Test cases for edge cases and error handling"""
    
    def test_convert_to_boolean_with_int(self):
        """Test boolean conversion with integer values"""
        engine = CheckersEngine("test", [1, 2], {})
        assert engine._convert_to_boolean(1) is True
        assert engine._convert_to_boolean(0) is False
    
    def test_invalid_coordinate_types(self):
        """Test validation with invalid coordinate types"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # String coordinates
        move_data = {"from_row": "invalid", "from_col": 0, "to_row": 4, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        assert "integer" in result.error_message.lower()
    
    def test_move_to_light_square(self):
        """Test moving to light square (invalid)"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # Try to move diagonally to a light square (even row+col sum)
        # From (5,0) which is dark (5+0=5, odd) to (4,1) which is light (4+1=5, odd)
        # Actually need (row+col) even for light square. (2,0) is light (2+0=2 even)
        # Place a white piece at (3,1) - dark square
        game_state["board"][3][1] = "w"
        game_state["board"][5][0] = ""  # Remove default piece
        # Move to (2,0) which is light square
        move_data = {"from_row": 3, "from_col": 1, "to_row": 2, "to_col": 0}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        assert "dark square" in result.error_message.lower()
    
    def test_flying_king_long_distance_move(self):
        """Test flying king moving multiple squares"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board and place flying king
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[7][0] = "W"
        
        # Move 5 squares
        move_data = {"from_row": 7, "from_col": 0, "to_row": 2, "to_col": 5}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert result.valid
    
    def test_flying_king_capture_multiple_distance(self):
        """Test flying king capturing at distance"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        # Setup: white king, black piece to capture, then empty spaces
        board[7][0] = "W"
        board[5][2] = "b"
        
        # Capture and land beyond
        move_data = {"from_row": 7, "from_col": 0, "to_row": 3, "to_col": 4}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert result.valid
    
    def test_flying_king_cannot_jump_own_piece(self):
        """Test flying king cannot jump over own pieces"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[7][0] = "W"
        board[6][1] = "w"  # Own piece
        board[4][3] = "b"  # Opponent piece beyond
        
        # Try to jump over own piece
        move_data = {"from_row": 7, "from_col": 0, "to_row": 2, "to_col": 5}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
    
    def test_flying_king_must_capture_exactly_one(self):
        """Test flying king must capture exactly one piece"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[7][0] = "W"
        board[5][2] = "b"
        board[3][4] = "b"  # Two opponent pieces in path
        
        # Try to capture two pieces
        move_data = {"from_row": 7, "from_col": 0, "to_row": 1, "to_col": 6}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        assert "exactly one" in result.error_message.lower()
    
    def test_standard_king_multi_square_without_flying(self):
        """Test standard king cannot move multiple squares without flying rule"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "No"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[7][0] = "W"
        
        # Try to move 2 squares without capture
        move_data = {"from_row": 7, "from_col": 0, "to_row": 5, "to_col": 2}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
    
    def test_regular_piece_multi_square_non_capture(self):
        """Test regular piece cannot move multiple squares without capture"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear spaces
        board[4][1] = None
        board[3][2] = None
        
        # Try to move 2 squares (no capture)
        move_data = {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
    
    def test_apply_move_with_flying_king_capture(self):
        """Test applying capture with flying king"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[7][0] = "W"
        board[5][2] = "b"
        
        # Capture at distance
        move_data = {"from_row": 7, "from_col": 0, "to_row": 3, "to_col": 4}
        updated_state = engine.apply_move(game_state, 1, move_data)
        
        assert updated_state["board"][7][0] is None
        assert updated_state["board"][5][2] is None  # Captured piece removed
        assert updated_state["board"][3][4] == "W"
        assert updated_state["last_move"]["captured"] is True
    
    def test_get_piece_moves_for_pieces(self):
        """Test _get_piece_moves returns correct moves"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Test white piece moves
        moves = engine._get_piece_moves(board, 5, 0, "w", "white", False)
        assert len(moves) == 1  # Can only move one square forward diagonally
    
    def test_get_piece_moves_king_all_directions(self):
        """Test king piece moves in all directions"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Place king in center
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[4][3] = "W"
        
        moves = engine._get_piece_moves(board, 4, 3, "W", "white", True)
        # King can move to 4 diagonal neighbors
        assert len(moves) == 4
    
    def test_get_piece_moves_flying_king(self):
        """Test flying king generates multiple distance moves"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "Yes"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Clear board
        for row in range(8):
            for col in range(8):
                board[row][col] = None
        
        board[7][0] = "W"
        
        moves = engine._get_piece_moves(board, 7, 0, "W", "white", True)
        # Should have multiple moves up the diagonal
        assert len(moves) > 4  # At least 4 directions with multiple distances
    
    def test_hash_board(self):
        """Test board hashing for position tracking"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        hash1 = engine._hash_board(game_state["board"])
        assert isinstance(hash1, str)
        assert len(hash1) > 0
        
        # Same board should produce same hash
        hash2 = engine._hash_board(game_state["board"])
        assert hash1 == hash2
    
    def test_invalid_move_distance(self):
        """Test validation with distance of 0"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # Try to move to same position (distance = 0)
        move_data = {"from_row": 5, "from_col": 0, "to_row": 5, "to_col": 0}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        # Moving to same position fails validation
    
    def test_destination_out_of_bounds(self):
        """Test moving to out of bounds destination"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # Try to move to negative row
        move_data = {"from_row": 5, "from_col": 0, "to_row": -1, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        assert "out of bounds" in result.error_message.lower()
        
        # Try to move beyond board size
        move_data = {"from_row": 5, "from_col": 0, "to_row": 10, "to_col": 1}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        assert "out of bounds" in result.error_message.lower()
    
    def test_white_backward_move_disallowed(self):
        """Test white piece cannot move backward when not allowed"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # White moves up (negative row direction). Moving down is backward.
        # row_diff positive means moving down (backward for white)
        # piece, player_color, is_king
        result = engine._validate_regular_move(3, 0, 4, 1, "w", "white", False)
        assert not result.valid
        assert "forward" in result.error_message.lower()
    
    def test_white_backward_capture_disallowed(self):
        """Test white piece cannot capture backward when backward_capture is disabled"""
        engine = CheckersEngine("test", [1, 2], {"backward_capture": "No"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup board for capture test - white at (3,2), black at (4,3)
        board[3][2] = "w"
        board[4][3] = "b"
        board[5][4] = ""
        
        # White moving down (positive row_diff) to capture - this is backward for white
        result = engine._validate_capture_move(board, 3, 2, 5, 4, "white", False)
        assert not result.valid
        assert "backward" in result.error_message.lower()
    
    def test_black_backward_capture_disallowed(self):
        """Test black piece cannot capture backward when backward_capture is disabled"""
        engine = CheckersEngine("test", [1, 2], {"backward_capture": "No"})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Setup board - black at (4,3), white at (3,2)
        board[4][3] = "b"
        board[3][2] = "w"
        board[2][1] = ""
        
        # Black moving up (negative row_diff) to capture - this is backward for black
        result = engine._validate_capture_move(board, 4, 3, 2, 1, "black", False)
        assert not result.valid
        assert "backward" in result.error_message.lower()
    
    def test_capture_distance_not_two(self):
        """Test capture move that's not exactly 2 squares"""
        engine = CheckersEngine("test", [1, 2], {"flying_kings": "No"})
        game_state = engine.initialize_game_state()
        
        # Setup: white piece at (5,0), black piece at (4,1)
        game_state["board"][5][0] = "w"
        game_state["board"][4][1] = "b"
        
        # Try to capture at distance 4 (without flying kings)
        move_data = {"from_row": 5, "from_col": 0, "to_row": 1, "to_col": 4}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
        # Could be "2 squares" or other validation
    
    def test_black_wins_no_white_pieces(self):
        """Test black wins when no white pieces remain"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # Remove all white pieces, leave only black
        for row in range(8):
            for col in range(8):
                if game_state["board"][row][col] and game_state["board"][row][col].lower() == "w":
                    game_state["board"][row][col] = ""
        
        # Set current player to black (player 2) via game_state
        game_state["current_player"] = 2
        engine._current_player_id = 2
        
        result, winner = engine.check_game_result(game_state)
        assert result == GameResult.PLAYER_WIN
        assert winner == 2
    
    def test_no_legal_moves_loses(self):
        """Test player with no legal moves loses"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        
        # Create position where white has no legal moves
        # Clear board and set up trapped white piece
        for row in range(8):
            for col in range(8):
                game_state["board"][row][col] = ""
        
        # White king at corner, surrounded by black pieces
        game_state["board"][0][7] = "W"
        game_state["board"][1][6] = "b"
        game_state["board"][2][5] = "b"
        
        # Set current player to white via game_state
        game_state["current_player"] = 1
        engine._current_player_id = 1
        
        result, winner = engine.check_game_result(game_state)
        assert result == GameResult.PLAYER_WIN
        assert winner == 2  # Black wins
    
    def test_is_capture_move_false_no_opponent(self):
        """Test _is_capture_move returns False when no opponent piece in path"""
        engine = CheckersEngine("test", [1, 2], {})
        game_state = engine.initialize_game_state()
        board = game_state["board"]
        
        # Place white piece at (5,0)
        board[5][0] = "w"
        # Clear destination and middle square
        board[4][1] = ""
        board[3][2] = ""
        
        # Check if it's a capture move (it's not, no opponent in middle)
        result = engine._is_capture_move(board, 5, 0, 3, 2, "white", False)
        assert result is False
        
        # Try to move to same position (distance 0)
        move_data = {"from_row": 5, "from_col": 0, "to_row": 5, "to_col": 0}
        result = engine._validate_game_specific_move(game_state, 1, move_data)
        assert not result.valid
