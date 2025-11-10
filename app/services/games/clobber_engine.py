# app/services/games/clobber_engine.py

from typing import Dict, Any, Optional, List
from services.game_engine_interface import (
    GameEngineInterface,
    MoveValidationResult,
    GameResult,
)
from schemas.game_schema import GameInfo, GameRuleOption


class ClobberEngine(GameEngineInterface):
    """
    Clobber game engine implementation.
    
    Rules:
    - 2 players only
    - Board with alternating pattern of pieces (default 5x6)
    - Players control pieces of their color (white/black)
    - Move by capturing: piece moves to adjacent cell (orthogonal) occupied by opponent
    - Cannot move to empty cells
    - First player unable to make a legal move loses
    
    Custom rules supported:
    - board_width: Width of the board (default: 6, supports 4-10)
    - board_height: Height of the board (default: 5, supports 4-10)
    - starting_pattern: Initial piece arrangement ('checkerboard' or 'rows')
    """
    
    def __init__(self, lobby_code: str, player_ids: List[int], rules: Optional[Dict[str, Any]] = None):
        super().__init__(lobby_code, player_ids, rules)
        
        # Validate player count
        if len(player_ids) != 2:
            raise ValueError("Clobber requires exactly 2 players")
        
        # Parse custom rules (validation already done by parent class)
        self.board_width = self.rules.get("board_width", 6)
        self.board_height = self.rules.get("board_height", 5)
        self.starting_pattern = self.rules.get("starting_pattern", "checkerboard")
        
        # Assign colors to players
        self.player_colors = {
            player_ids[0]: "W",  # White
            player_ids[1]: "B"   # Black
        }
    
    def _initialize_game_specific_state(self) -> Dict[str, Any]:
        """Initialize clobber board with starting pattern"""
        board = self._create_starting_board()
        
        return {
            "board": board,
            "move_count": 0,
            "last_move": None,
            "player_colors": self.player_colors,
            "legal_moves_cache": None,  # Cache for performance
        }
    
    def _create_starting_board(self) -> List[List[Optional[str]]]:
        """
        Create the initial board configuration.
        
        Returns:
            2D list representing the board with 'W' (white), 'B' (black), or None
        """
        board = [[None for _ in range(self.board_width)] for _ in range(self.board_height)]
        
        if self.starting_pattern == "checkerboard":
            # Alternating checkerboard pattern
            for row in range(self.board_height):
                for col in range(self.board_width):
                    if (row + col) % 2 == 0:
                        board[row][col] = "W"
                    else:
                        board[row][col] = "B"
        
        elif self.starting_pattern == "rows":
            # Alternating rows
            for row in range(self.board_height):
                color = "W" if row % 2 == 0 else "B"
                for col in range(self.board_width):
                    board[row][col] = color
        
        return board
    
    def _validate_game_specific_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate a clobber move.
        
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
            return MoveValidationResult(False, f"Starting position out of bounds")
        
        if not self._is_valid_position(to_row, to_col):
            return MoveValidationResult(False, f"Destination position out of bounds")
        
        board = game_state["board"]
        player_color = self.player_colors[player_id]
        
        # Check if starting position contains player's piece
        if board[from_row][from_col] != player_color:
            return MoveValidationResult(False, "No piece of yours at starting position")
        
        # Check if move is orthogonally adjacent (not diagonal)
        row_diff = abs(to_row - from_row)
        col_diff = abs(to_col - from_col)
        
        if not ((row_diff == 1 and col_diff == 0) or (row_diff == 0 and col_diff == 1)):
            return MoveValidationResult(False, "Can only move to orthogonally adjacent cells")
        
        # Check if destination contains opponent's piece (must capture)
        opponent_color = "B" if player_color == "W" else "W"
        if board[to_row][to_col] != opponent_color:
            return MoveValidationResult(False, "Can only move onto opponent's pieces (must capture)")
        
        return MoveValidationResult(True)
    
    def _is_valid_position(self, row: int, col: int) -> bool:
        """Check if a position is within board bounds"""
        return 0 <= row < self.board_height and 0 <= col < self.board_width
    
    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a clobber move (capture opponent's piece)"""
        from_row = int(move_data["from_row"])
        from_col = int(move_data["from_col"])
        to_row = int(move_data["to_row"])
        to_col = int(move_data["to_col"])
        
        player_color = self.player_colors[player_id]
        
        # Move piece and capture
        game_state["board"][from_row][from_col] = None
        game_state["board"][to_row][to_col] = player_color
        
        game_state["move_count"] += 1
        game_state["last_move"] = {
            "player_id": player_id,
            "from_row": from_row,
            "from_col": from_col,
            "to_row": to_row,
            "to_col": to_col,
            "color": player_color
        }
        
        # Invalidate legal moves cache
        game_state["legal_moves_cache"] = None
        
        return game_state
    
    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        """
        Check if current player has any legal moves.
        If not, they lose and opponent wins.
        """
        # Check if current player has any legal moves
        legal_moves = self._get_legal_moves(game_state, self.current_player_id)
        
        if not legal_moves:
            # Current player has no moves - they lose
            self.game_result = GameResult.PLAYER_WIN
            # Winner is the other player
            self.winner_id = next(pid for pid in self.player_ids if pid != self.current_player_id)
            return GameResult.PLAYER_WIN, self.winner_id
        
        # Game continues
        return GameResult.IN_PROGRESS, None
    
    def _get_legal_moves(self, game_state: Dict[str, Any], player_id: int) -> List[Dict[str, int]]:
        """
        Get all legal moves for a player.
        
        Returns:
            List of move dictionaries with from_row, from_col, to_row, to_col
        """
        board = game_state["board"]
        player_color = self.player_colors[player_id]
        opponent_color = "B" if player_color == "W" else "W"
        legal_moves = []
        
        # Check all cells for player's pieces
        for row in range(self.board_height):
            for col in range(self.board_width):
                if board[row][col] == player_color:
                    # Check all 4 orthogonal directions
                    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
                    for dr, dc in directions:
                        new_row, new_col = row + dr, col + dc
                        
                        # Check if destination is valid and contains opponent
                        if (self._is_valid_position(new_row, new_col) and
                            board[new_row][new_col] == opponent_color):
                            legal_moves.append({
                                "from_row": row,
                                "from_col": col,
                                "to_row": new_row,
                                "to_col": new_col
                            })
        
        return legal_moves
    
    @classmethod
    def get_game_name(cls) -> str:
        """Get the game name"""
        return "clobber"
    
    @classmethod
    def get_game_info(cls) -> GameInfo:
        """Get static clobber game information"""
        return GameInfo(
            game_name=cls.get_game_name(),
            display_name="Clobber",
            description="Strategic capture game. Move your pieces to capture adjacent opponent pieces. First player unable to move loses!",
            min_players=2,
            max_players=2,
            supported_rules={
                "board_width": GameRuleOption(
                    type="integer",
                    allowed_values=[4, 5, 6, 7, 8, 9, 10],
                    default=6,
                    description="Width of the game board"
                ),
                "board_height": GameRuleOption(
                    type="integer",
                    allowed_values=[4, 5, 6, 7, 8, 9, 10],
                    default=5,
                    description="Height of the game board"
                ),
                "starting_pattern": GameRuleOption(
                    type="string",
                    allowed_values=["checkerboard", "rows"],
                    default="checkerboard",
                    description="Initial piece arrangement: 'checkerboard' for alternating pattern, 'rows' for alternating rows"
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
            game_image_path="/static/images/games/clobber.png",
        )
