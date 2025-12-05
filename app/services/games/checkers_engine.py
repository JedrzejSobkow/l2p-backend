# app/services/games/checkers_engine.py

from typing import Dict, Any, Optional, List
from services.game_engine_interface import (
    GameEngineInterface,
    MoveValidationResult,
    GameResult,
)
from schemas.game_schema import GameInfo, GameRuleOption


class CheckersEngine(GameEngineInterface):
    """
    Checkers (Warcaby) game engine implementation.
    
    Rules:
    - 2 players only
    - 8x8 board (standard) or 10x10 (international)
    - Pieces move diagonally forward
    - Must capture if possible (forced capture)
    - Multiple captures in sequence (multi-jump)
    - Pieces become kings when reaching opposite end
    - Kings can move and capture in all diagonal directions
    - First player unable to make a legal move loses
    
    Custom rules supported:
    - board_size: Size of the board (8 for standard, 10 for international)
    - forced_capture: Whether captures are mandatory (default: true)
    - flying_kings: Whether kings can move multiple squares (default: false for standard, true for international)
    - backward_capture: Whether regular pieces can capture backward (default: true)
    """
    
    def __init__(self, lobby_code: str, player_ids: List[int], rules: Optional[Dict[str, Any]] = None):
        super().__init__(lobby_code, player_ids, rules)
        
        # Validate player count
        if len(player_ids) != 2:
            raise ValueError("Checkers requires exactly 2 players")
        
        # Parse and convert custom rules (validation already done by parent class)
        self.board_size = int(self.rules.get("board_size", 8))
        self.forced_capture = self._convert_to_boolean(self.rules.get("forced_capture", True))
        self.flying_kings = self._convert_to_boolean(self.rules.get("flying_kings", False))
        self.backward_capture = self._convert_to_boolean(self.rules.get("backward_capture", True))
        
        # Assign colors to players
        # Player 1 = White (starts at bottom, moves up)
        # Player 2 = Black (starts at top, moves down)
        self.player_colors = {
            player_ids[0]: "white",
            player_ids[1]: "black"
        }
    
    def _convert_to_boolean(self, value: Any) -> bool:
        """Convert a value to boolean, handling string representations."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["true", "1", "yes"]
        return bool(value)
    
    def _initialize_game_specific_state(self) -> Dict[str, Any]:
        """Initialize checkers board with starting positions"""
        board = self._create_starting_board()
        
        return {
            "board": board,
            "move_count": 0,
            "last_move": None,
            "player_colors": self.player_colors,
            "consecutive_non_capture_moves": 0,  # For draw by repetition
            "position_history": [],  # Track positions for draw detection
        }
    
    def _create_starting_board(self) -> List[List[Optional[str]]]:
        """
        Create the initial board configuration.
        
        Returns:
            2D list representing the board with pieces:
            - 'w': white regular piece
            - 'W': white king
            - 'b': black regular piece
            - 'B': black king
            - None: empty square
        """
        board = [[None for _ in range(self.board_size)] for _ in range(self.board_size)]
        
        # Number of rows with pieces for each player
        piece_rows = 3 if self.board_size == 8 else 4
        
        # Place black pieces (top of board)
        for row in range(piece_rows):
            for col in range(self.board_size):
                # Only place on dark squares (assuming row+col is odd for dark squares)
                if (row + col) % 2 == 1:
                    board[row][col] = "b"
        
        # Place white pieces (bottom of board)
        for row in range(self.board_size - piece_rows, self.board_size):
            for col in range(self.board_size):
                # Only place on dark squares
                if (row + col) % 2 == 1:
                    board[row][col] = "w"
        
        return board
    
    def _validate_game_specific_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate a checkers move.
        
        Move data should contain:
        - from_row: int (starting row)
        - from_col: int (starting column)
        - to_row: int (destination row)
        - to_col: int (destination column)
        """
        # Validate move data structure
        required_fields = ["from_row", "from_col", "to_row", "to_col"]
        for field in required_fields:
            if field not in move_data:
                return MoveValidationResult(False, f"Move must contain '{field}' field")
        
        try:
            from_row = int(move_data["from_row"])
            from_col = int(move_data["from_col"])
            to_row = int(move_data["to_row"])
            to_col = int(move_data["to_col"])
        except (ValueError, TypeError):
            return MoveValidationResult(False, "All coordinates must be integers")
        
        # Check if positions are within bounds
        if not self._is_valid_position(from_row, from_col):
            return MoveValidationResult(False, "Starting position out of bounds")
        
        if not self._is_valid_position(to_row, to_col):
            return MoveValidationResult(False, "Destination position out of bounds")
        
        board = game_state["board"]
        player_color = self.player_colors[player_id]
        
        # Check if starting position contains player's piece
        from_piece = board[from_row][from_col]
        if not self._is_player_piece(from_piece, player_color):
            return MoveValidationResult(False, "No piece of yours at starting position")
        
        # Check if destination is empty
        if board[to_row][to_col] is not None:
            return MoveValidationResult(False, "Destination square is occupied")
        
        # Check if move is diagonal
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        
        if abs(row_diff) != abs(col_diff):
            return MoveValidationResult(False, "Must move diagonally")
        
        # Check if destination is on a dark square (valid square)
        if (to_row + to_col) % 2 == 0:
            return MoveValidationResult(False, "Can only move to dark squares")
        
        # Determine if this is a capture move or regular move
        distance = abs(row_diff)
        is_king = from_piece.isupper()
        
        # Check if forced capture rule applies
        if self.forced_capture:
            capture_moves = self._get_capture_moves(game_state, player_id)
            if capture_moves:
                # Must make a capture move
                is_capture = self._is_capture_move(board, from_row, from_col, to_row, to_col, player_color, is_king)
                if not is_capture:
                    return MoveValidationResult(False, "Must capture when possible")
        
        # Validate based on move type
        if distance == 1:
            # Regular move (no capture)
            return self._validate_regular_move(from_row, from_col, to_row, to_col, from_piece, player_color, is_king)
        elif distance >= 2:
            # Could be capture or flying king move
            # Check if this is actually a capture attempt
            is_capture_attempt = self._is_capture_move(board, from_row, from_col, to_row, to_col, player_color, is_king)
            
            if is_capture_attempt:
                # Validate as capture
                return self._validate_capture_move(board, from_row, from_col, to_row, to_col, player_color, is_king)
            elif is_king and self.flying_kings:
                # Flying king regular move
                return self._validate_regular_move(from_row, from_col, to_row, to_col, from_piece, player_color, is_king)
            elif is_king and not self.flying_kings:
                # Standard king trying to move multiple squares without capture
                return MoveValidationResult(False, "Kings can only move one square in standard rules")
            else:
                # Non-king trying to move multiple squares - must be capture attempt
                return self._validate_capture_move(board, from_row, from_col, to_row, to_col, player_color, is_king)
        else:
            return MoveValidationResult(False, "Invalid move distance")
    
    def _is_player_piece(self, piece: Optional[str], player_color: str) -> bool:
        """Check if a piece belongs to a player"""
        if piece is None:
            return False
        return piece.lower() == player_color[0]  # 'w' or 'b'
    
    def _validate_regular_move(self, from_row: int, from_col: int, to_row: int, to_col: int, 
                               piece: str, player_color: str, is_king: bool) -> MoveValidationResult:
        """Validate a regular (non-capture) move"""
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        distance = abs(row_diff)
        
        if is_king:
            # Kings can move in any diagonal direction
            if self.flying_kings:
                # International rules: kings can move multiple squares
                # Check path is clear
                row_dir = 1 if row_diff > 0 else -1
                col_dir = 1 if col_diff > 0 else -1
                current_row = from_row + row_dir
                current_col = from_col + col_dir
                
                while current_row != to_row:
                    # Path must be clear for flying kings
                    # Note: we're in regular move, so no pieces should be in path
                    current_row += row_dir
                    current_col += col_dir
                
                return MoveValidationResult(True)
            else:
                # Standard rules: kings move one square
                if distance == 1:
                    return MoveValidationResult(True)
                else:
                    return MoveValidationResult(False, "Kings can only move one square in standard rules")
        else:
            # Regular pieces can only move forward
            if distance != 1:
                return MoveValidationResult(False, "Regular pieces can only move one square")
            
            if player_color == "white":
                # White moves up (negative row direction)
                if row_diff == -1:
                    return MoveValidationResult(True)
                else:
                    return MoveValidationResult(False, "Regular pieces can only move forward")
            else:  # black
                # Black moves down (positive row direction)
                if row_diff == 1:
                    return MoveValidationResult(True)
                else:
                    return MoveValidationResult(False, "Regular pieces can only move forward")
    
    def _validate_capture_move(self, board: List[List[Optional[str]]], from_row: int, from_col: int, 
                               to_row: int, to_col: int, player_color: str, is_king: bool) -> MoveValidationResult:
        """Validate a capture move"""
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        distance = abs(row_diff)
        
        # For flying kings, check path
        if is_king and self.flying_kings:
            # Check if there's exactly one opponent piece in the path
            captured_pieces = []
            row_dir = 1 if row_diff > 0 else -1
            col_dir = 1 if col_diff > 0 else -1
            
            current_row = from_row + row_dir
            current_col = from_col + col_dir
            
            while current_row != to_row:
                piece = board[current_row][current_col]
                if piece is not None:
                    if self._is_opponent_piece(piece, player_color):
                        captured_pieces.append((current_row, current_col))
                    else:
                        return MoveValidationResult(False, "Cannot jump over own pieces")
                
                current_row += row_dir
                current_col += col_dir
            
            if len(captured_pieces) != 1:
                return MoveValidationResult(False, "Must capture exactly one piece")
            
            return MoveValidationResult(True)
        else:
            # Standard capture: must be exactly 2 squares away
            if distance != 2:
                return MoveValidationResult(False, "Capture moves must jump exactly 2 squares")
            
            # Check direction for regular pieces
            if not is_king:
                if player_color == "white":
                    # White normally moves up
                    if row_diff > 0 and not self.backward_capture:
                        return MoveValidationResult(False, "Regular pieces cannot capture backward")
                else:  # black
                    # Black normally moves down
                    if row_diff < 0 and not self.backward_capture:
                        return MoveValidationResult(False, "Regular pieces cannot capture backward")
            
            # Check if there's an opponent piece to capture
            mid_row = (from_row + to_row) // 2
            mid_col = (from_col + to_col) // 2
            mid_piece = board[mid_row][mid_col]
            
            if mid_piece is None:
                return MoveValidationResult(False, "No piece to capture")
            
            if not self._is_opponent_piece(mid_piece, player_color):
                return MoveValidationResult(False, "Cannot capture own pieces")
            
            return MoveValidationResult(True)
    
    def _is_opponent_piece(self, piece: str, player_color: str) -> bool:
        """Check if a piece belongs to the opponent"""
        opponent_color = "b" if player_color == "white" else "w"
        return piece.lower() == opponent_color
    
    def _is_capture_move(self, board: List[List[Optional[str]]], from_row: int, from_col: int, 
                        to_row: int, to_col: int, player_color: str, is_king: bool) -> bool:
        """Check if a move is a capture move"""
        distance = abs(to_row - from_row)
        
        if distance < 2:
            return False
        
        if is_king and self.flying_kings:
            # Check path for opponent piece
            row_diff = to_row - from_row
            col_diff = to_col - from_col
            row_dir = 1 if row_diff > 0 else -1
            col_dir = 1 if col_diff > 0 else -1
            
            current_row = from_row + row_dir
            current_col = from_col + col_dir
            
            while current_row != to_row:
                piece = board[current_row][current_col]
                if piece is not None and self._is_opponent_piece(piece, player_color):
                    return True
                current_row += row_dir
                current_col += col_dir
            return False
        else:
            # Standard capture check
            if distance == 2:
                mid_row = (from_row + to_row) // 2
                mid_col = (from_col + to_col) // 2
                mid_piece = board[mid_row][mid_col]
                return mid_piece is not None and self._is_opponent_piece(mid_piece, player_color)
            return False
    
    def _is_valid_position(self, row: int, col: int) -> bool:
        """Check if a position is within board bounds"""
        return 0 <= row < self.board_size and 0 <= col < self.board_size
    
    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a checkers move"""
        from_row = int(move_data["from_row"])
        from_col = int(move_data["from_col"])
        to_row = int(move_data["to_row"])
        to_col = int(move_data["to_col"])
        
        board = game_state["board"]
        player_color = self.player_colors[player_id]
        piece = board[from_row][from_col]
        is_king = piece.isupper()
        
        # Determine if this is a capture move
        distance = abs(to_row - from_row)
        captured_piece = None
        
        if distance >= 2:
            # Capture move - remove captured piece(s)
            if is_king and self.flying_kings:
                # Find and remove the captured piece in the path
                row_diff = to_row - from_row
                col_diff = to_col - from_col
                row_dir = 1 if row_diff > 0 else -1
                col_dir = 1 if col_diff > 0 else -1
                
                current_row = from_row + row_dir
                current_col = from_col + col_dir
                
                while current_row != to_row:
                    if board[current_row][current_col] is not None and \
                       self._is_opponent_piece(board[current_row][current_col], player_color):
                        captured_piece = board[current_row][current_col]
                        board[current_row][current_col] = None
                        break
                    current_row += row_dir
                    current_col += col_dir
            else:
                # Standard capture
                mid_row = (from_row + to_row) // 2
                mid_col = (from_col + to_col) // 2
                captured_piece = board[mid_row][mid_col]
                board[mid_row][mid_col] = None
            
            game_state["consecutive_non_capture_moves"] = 0
        else:
            game_state["consecutive_non_capture_moves"] += 1
        
        # Move piece
        board[from_row][from_col] = None
        board[to_row][to_col] = piece
        
        # Check for promotion to king
        if not is_king:
            if player_color == "white" and to_row == 0:
                # White reaches top
                board[to_row][to_col] = "W"
            elif player_color == "black" and to_row == self.board_size - 1:
                # Black reaches bottom
                board[to_row][to_col] = "B"
        
        game_state["move_count"] += 1
        game_state["last_move"] = {
            "player_id": player_id,
            "from_row": from_row,
            "from_col": from_col,
            "to_row": to_row,
            "to_col": to_col,
            "captured": captured_piece is not None,
            "promoted": board[to_row][to_col] != piece
        }
        
        # Add position to history for draw detection
        board_hash = self._hash_board(board)
        game_state["position_history"].append(board_hash)
        
        # Check if the next player has any legal moves
        next_player_id = next(pid for pid in self.player_ids if pid != player_id)
        legal_moves = self._get_all_legal_moves(game_state, next_player_id)
        game_state["legal_moves"] = legal_moves  # Store legal moves in the game state
        game_state["has_legal_moves"] = "Yes" if legal_moves else "No"
        
        return game_state
    
    def _hash_board(self, board: List[List[Optional[str]]]) -> str:
        """Create a hash of the board state for position tracking"""
        return "".join("".join(cell or "." for cell in row) for row in board)
    
    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        """
        Check if the game has ended.
        
        Win conditions:
        - Opponent has no pieces left
        - Opponent has no legal moves
        
        Draw conditions:
        - 40 moves without capture
        - Position repeated 3 times
        """
        board = game_state["board"]
        
        # Check for draw by repetition (3-fold repetition)
        position_history = game_state.get("position_history", [])
        if position_history:
            current_position = position_history[-1]
            repetitions = position_history.count(current_position)
            if repetitions >= 3:
                self.game_result = GameResult.DRAW
                self.winner_id = None
                return GameResult.DRAW, None
        
        # Check for draw by 40 non-capture moves
        if game_state.get("consecutive_non_capture_moves", 0) >= 40:
            self.game_result = GameResult.DRAW
            self.winner_id = None
            return GameResult.DRAW, None
        
        # Count pieces for each player
        white_pieces = 0
        black_pieces = 0
        
        for row in board:
            for cell in row:
                if cell and cell.lower() == "w":
                    white_pieces += 1
                elif cell and cell.lower() == "b":
                    black_pieces += 1
        
        # Check if opponent has no pieces
        current_player_color = self.player_colors[self.current_player_id]
        if current_player_color == "white" and black_pieces == 0:
            self.game_result = GameResult.PLAYER_WIN
            self.winner_id = self.current_player_id
            return GameResult.PLAYER_WIN, self.winner_id
        elif current_player_color == "black" and white_pieces == 0:
            self.game_result = GameResult.PLAYER_WIN
            self.winner_id = self.current_player_id
            return GameResult.PLAYER_WIN, self.winner_id
        
        # Check if current player has any legal moves
        legal_moves = self._get_all_legal_moves(game_state, self.current_player_id)
        
        if not legal_moves:
            # Current player has no moves - they lose
            self.game_result = GameResult.PLAYER_WIN
            self.winner_id = next(pid for pid in self.player_ids if pid != self.current_player_id)
            return GameResult.PLAYER_WIN, self.winner_id
        
        # Game continues
        return GameResult.IN_PROGRESS, None
    
    def _get_capture_moves(self, game_state: Dict[str, Any], player_id: int) -> List[Dict[str, int]]:
        """Get all possible capture moves for a player"""
        board = game_state["board"]
        player_color = self.player_colors[player_id]
        capture_moves = []
        
        for row in range(self.board_size):
            for col in range(self.board_size):
                piece = board[row][col]
                if self._is_player_piece(piece, player_color):
                    is_king = piece.isupper()
                    
                    # Check all diagonal directions
                    directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
                    
                    for dr, dc in directions:
                        # For flying kings, check multiple distances
                        if is_king and self.flying_kings:
                            # First, scan for an opponent piece in this direction
                            opponent_distance = None
                            for d in range(1, self.board_size):
                                check_row = row + dr * d
                                check_col = col + dc * d
                                
                                if not self._is_valid_position(check_row, check_col):
                                    break
                                
                                piece_at_pos = board[check_row][check_col]
                                if piece_at_pos is not None:
                                    if self._is_opponent_piece(piece_at_pos, player_color):
                                        opponent_distance = d
                                    break
                            
                            # If we found an opponent, check all valid landing squares beyond it
                            if opponent_distance is not None:
                                distance = opponent_distance + 1
                                while distance < self.board_size:
                                    new_row = row + dr * distance
                                    new_col = col + dc * distance
                                    
                                    if not self._is_valid_position(new_row, new_col):
                                        break
                                    
                                    if board[new_row][new_col] is not None:
                                        break
                                    
                                    capture_moves.append({
                                        "from_row": row,
                                        "from_col": col,
                                        "to_row": new_row,
                                        "to_col": new_col
                                    })
                                    
                                    distance += 1
                        else:
                            # Standard capture (2 squares)
                            new_row = row + dr * 2
                            new_col = col + dc * 2
                            
                            if not self._is_valid_position(new_row, new_col):
                                continue
                            
                            if board[new_row][new_col] is not None:
                                continue
                            
                            # Check direction for regular pieces
                            if not is_king:
                                if player_color == "white" and dr > 0 and not self.backward_capture:
                                    continue
                                if player_color == "black" and dr < 0 and not self.backward_capture:
                                    continue
                            
                            if self._is_capture_move(board, row, col, new_row, new_col, player_color, is_king):
                                capture_moves.append({
                                    "from_row": row,
                                    "from_col": col,
                                    "to_row": new_row,
                                    "to_col": new_col
                                })
        
        return capture_moves
    
    def _get_all_legal_moves(self, game_state: Dict[str, Any], player_id: int) -> List[Dict[str, int]]:
        """Get all legal moves for a player"""
        # If forced capture is enabled, check for capture moves first
        if self.forced_capture:
            capture_moves = self._get_capture_moves(game_state, player_id)
            if capture_moves:
                return capture_moves
        
        # Get regular moves
        board = game_state["board"]
        player_color = self.player_colors[player_id]
        legal_moves = []
        
        for row in range(self.board_size):
            for col in range(self.board_size):
                piece = board[row][col]
                if self._is_player_piece(piece, player_color):
                    is_king = piece.isupper()
                    
                    # Get possible moves for this piece
                    piece_moves = self._get_piece_moves(board, row, col, piece, player_color, is_king)
                    legal_moves.extend(piece_moves)
        
        return legal_moves
    
    def _get_piece_moves(self, board: List[List[Optional[str]]], row: int, col: int, 
                         piece: str, player_color: str, is_king: bool) -> List[Dict[str, int]]:
        """Get all possible moves for a specific piece"""
        moves = []
        
        # Determine which directions this piece can move
        if is_king:
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        else:
            if player_color == "white":
                # White moves up
                directions = [(-1, -1), (-1, 1)]
            else:
                # Black moves down
                directions = [(1, -1), (1, 1)]
        
        for dr, dc in directions:
            # Regular moves (1 square)
            new_row = row + dr
            new_col = col + dc
            
            if self._is_valid_position(new_row, new_col) and board[new_row][new_col] is None:
                moves.append({
                    "from_row": row,
                    "from_col": col,
                    "to_row": new_row,
                    "to_col": new_col
                })
            
            # For flying kings, check multiple distances
            if is_king and self.flying_kings:
                distance = 2
                while distance < self.board_size:
                    new_row = row + dr * distance
                    new_col = col + dc * distance
                    
                    if not self._is_valid_position(new_row, new_col):
                        break
                    
                    if board[new_row][new_col] is not None:
                        break
                    
                    moves.append({
                        "from_row": row,
                        "from_col": col,
                        "to_row": new_row,
                        "to_col": new_col
                    })
                    
                    distance += 1
        
        return moves
    
    @classmethod
    def get_game_name(cls) -> str:
        """Get the game name"""
        return "checkers"
    
    @classmethod
    def get_game_info(cls) -> GameInfo:
        """Get static checkers game information"""
        return GameInfo(
            game_name=cls.get_game_name(),
            display_name="Checkers",
            description="Classic checkers game. Capture opponent's pieces by jumping diagonally. Reaching the opposite end promotes a piece to a king. First player unable to move loses!",
            min_players=2,
            max_players=2,
            supported_rules={
                "board_size": GameRuleOption(
                    type="integer",
                    allowed_values=[8, 10],
                    default=8,
                    description="Board size: 8 for standard checkers, 10 for international"
                ),
                "forced_capture": GameRuleOption(
                    type="string",
                    allowed_values=["Yes", "No"],
                    default="Yes",
                    description="Whether captures are mandatory (must capture when possible)"
                ),
                "flying_kings": GameRuleOption(
                    type="string",
                    allowed_values=["Yes", "No"],
                    default="No",
                    description="Whether kings can move multiple squares (international checkers)"
                ),
                "backward_capture": GameRuleOption(
                    type="string",
                    allowed_values=["Yes", "No"],
                    default="Yes",
                    description="Whether regular pieces can capture backward"
                ),
                "timeout_type": GameRuleOption(
                    type="string",
                    allowed_values=["none", "total_time", "per_turn"],
                    default="none",
                    description="Type of timeout: 'none' (no timeout), 'total_time' (total time per player), or 'per_turn' (time limit per turn)"
                ),
                "timeout_seconds": GameRuleOption(
                    type="integer",
                    allowed_values=[10, 15, 30, 60, 120, 300, 600],
                    default=300,
                    description="Timeout duration in seconds (e.g., 300 for 5 minutes). Only applies when timeout_type is not 'none'"
                )
            },
            turn_based=True,
            category="strategy",
            game_image_path="/static/images/games/checkers.png",
        )

    def initialize_game_state(self) -> Dict[str, Any]:
        """Initialize the game state with starting positions and metadata."""
        game_state = self._initialize_game_specific_state()
        game_state["move_count"] = 0
        game_state["result"] = GameResult.IN_PROGRESS.value
        game_state["winner_identifier"] = None
        game_state["current_turn_identifier"] = self.current_player_id

        # Calculate legal moves for the first player
        legal_moves = self._get_all_legal_moves(game_state, self.current_player_id)
        game_state["legal_moves"] = legal_moves
        game_state["has_legal_moves"] = "Yes" if legal_moves else "No"

        return game_state
