# app/services/games/tictactoe_engine.py

from typing import Dict, Any, Optional, List
from services.game_engine_interface import (
    GameEngineInterface,
    MoveValidationResult,
    GameResult,
)
from schemas.game_schema import GameInfo, GameRuleOption


class TicTacToeEngine(GameEngineInterface):
    """
    Tic-tac-toe game engine implementation.
    
    Rules:
    - 2 players only
    - 3x3 grid
    - Players alternate placing X and O
    - Win by getting 3 in a row (horizontal, vertical, or diagonal)
    - Draw if board is full with no winner
    
    Custom rules supported:
    - board_size: Size of the board (default: 3, supports 3-5)
    - win_length: Number in a row to win (default: 3)
    """
    
    def __init__(self, lobby_code: str, player_ids: List[int], rules: Optional[Dict[str, Any]] = None):
        super().__init__(lobby_code, player_ids, rules)
        
        # Validate player count
        if len(player_ids) != 2:
            raise ValueError("Tic-tac-toe requires exactly 2 players")
        
        # Parse custom rules
        self.board_size = self.rules.get("board_size", 3)
        self.win_length = self.rules.get("win_length", 3)
        
        # Validate board size
        if not 3 <= self.board_size <= 5:
            raise ValueError("Board size must be between 3 and 5")
        
        # Validate win length
        if self.win_length > self.board_size:
            raise ValueError("Win length cannot exceed board size")
        
        # Assign symbols to players
        self.player_symbols = {
            player_ids[0]: "X",
            player_ids[1]: "O"
        }
    
    def initialize_game_state(self) -> Dict[str, Any]:
        """Initialize an empty tic-tac-toe board"""
        board = [[None for _ in range(self.board_size)] for _ in range(self.board_size)]
        
        return {
            "board": board,
            "move_count": 0,
            "last_move": None,
            "player_symbols": self.player_symbols,
        }
    
    def validate_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate a tic-tac-toe move.
        
        Move data should contain:
        - row: int (0 to board_size-1)
        - col: int (0 to board_size-1)
        """
        # Check if it's the player's turn
        if player_id != self.current_player_id:
            return MoveValidationResult(False, "It's not your turn")
        
        # Check if game is still in progress
        if self.game_result != GameResult.IN_PROGRESS:
            return MoveValidationResult(False, "Game has already ended")
        
        # Validate move data structure
        if "row" not in move_data or "col" not in move_data:
            return MoveValidationResult(False, "Move must contain 'row' and 'col' fields")
        
        try:
            row = int(move_data["row"])
            col = int(move_data["col"])
        except (ValueError, TypeError):
            return MoveValidationResult(False, "Row and col must be integers")
        
        # Check if position is within bounds
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return MoveValidationResult(False, f"Position out of bounds (board size: {self.board_size}x{self.board_size})")
        
        # Check if position is empty
        board = game_state["board"]
        if board[row][col] is not None:
            return MoveValidationResult(False, "Position already occupied")
        
        return MoveValidationResult(True)
    
    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a tic-tac-toe move to the board"""
        row = int(move_data["row"])
        col = int(move_data["col"])
        symbol = self.player_symbols[player_id]
        
        # Update the board
        game_state["board"][row][col] = symbol
        game_state["move_count"] += 1
        game_state["last_move"] = {
            "player_id": player_id,
            "row": row,
            "col": col,
            "symbol": symbol
        }
        
        return game_state
    
    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        """Check for win or draw conditions"""
        board = game_state["board"]
        
        # Check for a winner
        winner_symbol = self._check_winner(board)
        if winner_symbol:
            # Find the player ID with this symbol
            winner_id = next(pid for pid, sym in self.player_symbols.items() if sym == winner_symbol)
            self.game_result = GameResult.PLAYER_WIN
            self.winner_id = winner_id
            return GameResult.PLAYER_WIN, winner_id
        
        # Check for draw (board full)
        if game_state["move_count"] >= self.board_size * self.board_size:
            self.game_result = GameResult.DRAW
            return GameResult.DRAW, None
        
        # Game still in progress
        return GameResult.IN_PROGRESS, None
    
    def _check_winner(self, board: List[List[Optional[str]]]) -> Optional[str]:
        """
        Check if there's a winner on the board.
        
        Returns:
            Winning symbol ('X' or 'O') or None
        """
        # Check rows
        for row in board:
            winner = self._check_line(row)
            if winner:
                return winner
        
        # Check columns
        for col_idx in range(self.board_size):
            column = [board[row_idx][col_idx] for row_idx in range(self.board_size)]
            winner = self._check_line(column)
            if winner:
                return winner
        
        # Check diagonals
        diag1 = [board[i][i] for i in range(self.board_size)]
        winner = self._check_line(diag1)
        if winner:
            return winner
        
        diag2 = [board[i][self.board_size - 1 - i] for i in range(self.board_size)]
        winner = self._check_line(diag2)
        if winner:
            return winner
        
        return None
    
    def _check_line(self, line: List[Optional[str]]) -> Optional[str]:
        """
        Check if a line contains a win.
        
        Args:
            line: List of symbols in a row/column/diagonal
            
        Returns:
            Winning symbol or None
        """
        if len(line) < self.win_length:
            return None
        
        # Check for consecutive symbols
        for i in range(len(line) - self.win_length + 1):
            segment = line[i:i + self.win_length]
            if all(s is not None and s == segment[0] for s in segment):
                return segment[0]
        
        return None
    
    @classmethod
    def get_game_name(cls) -> str:
        """Get the game name"""
        return "tictactoe"
    
    @classmethod
    def get_game_info(cls) -> GameInfo:
        """Get static tic-tac-toe game information"""
        return GameInfo(
            game_name=cls.get_game_name(),
            display_name="Tic-Tac-Toe",
            description="Classic tic-tac-toe game. Get 3 in a row to win!",
            min_players=2,
            max_players=2,
            supported_rules={
                "board_size": GameRuleOption(
                    type="integer",
                    min=3,
                    max=5,
                    default=3,
                    description="Size of the game board (NxN)"
                ),
                "win_length": GameRuleOption(
                    type="integer",
                    min=3,
                    max=5,
                    default=3,
                    description="Number of symbols in a row needed to win"
                )
            },
            turn_based=True,
            category="strategy",
            game_image_path="/static/images/games/tictactoe.png",
        )
