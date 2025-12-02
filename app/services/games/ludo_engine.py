# app/services/games/ludo_engine.py

from typing import Dict, Any, Optional, List
import random
from services.game_engine_interface import (
    GameEngineInterface,
    MoveValidationResult,
    GameResult,
)
from schemas.game_schema import GameInfo, GameRuleOption


class LudoEngine(GameEngineInterface):
    """
    Ludo board game engine implementation.
    
    Full implementation of standard Ludo rules:
    - 2-4 players, each with 4 pieces
    - 52-square circular track + 4 home paths (6 squares each)
    - Roll dice (1-6) to determine movement
    - Roll 6 to get piece out of yard
    - Roll 6 grants extra turn
    - Capture opponent pieces by landing on them (sends back to yard)
    - Safe squares prevent captures
    - Win by getting all 4 pieces home
    - Exact roll needed to enter home
    """
    
    # Board configuration
    BOARD_SQUARES = 52  # Main circular track
    HOME_PATH_LENGTH = 6  # Squares in each player's home stretch
    PIECES_PER_PLAYER = 4
    
    # Special square positions (0-indexed on 52-square track)
    # These are the safe squares where pieces cannot be captured
    SAFE_SQUARES = [0, 8, 13, 21, 26, 34, 39, 47]  # Starting squares + safe zones
    
    # Starting positions for each player color (on main track)
    # Player 0 (Red) starts at 0, Player 1 (Green) at 13, Player 2 (Yellow) at 26, Player 3 (Blue) at 39
    STARTING_POSITIONS = {
        0: 0,   # Red
        1: 13,  # Green
        2: 26,  # Yellow
        3: 39,  # Blue
    }
    
    # Home entry positions (where pieces leave main track to enter home path)
    HOME_ENTRY_POSITIONS = {
        0: 50,  # Red enters home path at square 50
        1: 11,  # Green enters home path at square 11
        2: 24,  # Yellow enters home path at square 24
        3: 37,  # Blue enters home path at square 37
    }
    
    def __init__(self, lobby_code: str, player_ids: List[int], rules: Optional[Dict[str, Any]] = None):
        super().__init__(lobby_code, player_ids, rules)
        
        # Validate player count
        if len(player_ids) < 2 or len(player_ids) > 4:
            raise ValueError("Ludo requires 2-4 players")
        
        # Parse custom rules
        self.pieces_per_player = self.rules.get("pieces_per_player", self.PIECES_PER_PLAYER)
        # Convert string "yes"/"no" to boolean or accept boolean values directly
        # Frontend sends "yes"/"no" strings, tests might send booleans
        self.six_grants_extra_turn = self._parse_bool_rule("six_grants_extra_turn", True)
        self.exact_roll_to_finish = self._parse_bool_rule("exact_roll_to_finish", True)
        self.capture_sends_home = self._parse_bool_rule("capture_sends_home", True)
        
        # Map player IDs to player indices (0-3)
        self.player_index_map = {player_id: idx for idx, player_id in enumerate(player_ids)}
        
        # Track if current player gets an extra turn
        self.extra_turn_pending = False
        
        # Track if turn is complete (dice rolled AND move made, or no moves possible)
        self.turn_complete = True
    
    def _parse_bool_rule(self, rule_name: str, default: bool) -> bool:
        """
        Parse a boolean rule that may be specified as:
        - A boolean value (True/False) - from tests
        - A string value ("yes"/"no") - from frontend/GameRuleOption
        
        Returns:
            True if the value is True or "yes", False otherwise
        """
        value = self.rules.get(rule_name, "yes" if default else "no")
        if isinstance(value, bool):
            return value
        # Handle string values
        return str(value).lower() == "yes"
    
    def _initialize_game_specific_state(self) -> Dict[str, Any]:
        """Initialize Ludo game state with all pieces in yards"""
        
        # Initialize all pieces in yard (position = "yard")
        pieces = {}
        for player_idx, player_id in enumerate(self.player_ids):
            pieces[player_id] = []
            for piece_idx in range(self.pieces_per_player):
                piece_id = f"p{player_idx}_piece{piece_idx}"
                pieces[player_id].append({
                    "id": piece_id,
                    "position": "yard",  # "yard", "track_X", "home_X", or "finished"
                    "is_safe": False,
                })
        
        return {
            "pieces": pieces,
            "current_dice_roll": None,  # Will be set when turn starts
            "move_made": False,  # Track if player has made their move
            "extra_turn_pending": False,  # Track if player rolled a 6
            "dice_rolled": False,  # Track if dice has been rolled this turn
            "moves_history": [],  # Track move history for game replay
        }
    
    def _roll_dice(self) -> int:
        """Roll a six-sided die"""
        return random.randint(1, 6)
    
    def _get_player_index(self, player_id: int) -> int:
        """Get player index (0-3) from player ID"""
        return self.player_index_map[player_id]
    
    def _get_piece_position_value(self, position: str) -> tuple[str, int]:
        """
        Parse position string into type and value.
        
        Returns:
            Tuple of (position_type, value)
            - ("yard", 0) for pieces in yard
            - ("track", X) for pieces on main track (0-51)
            - ("home", X) for pieces in home path (0-5)
            - ("finished", 0) for pieces that reached home
        """
        if position == "yard":
            return ("yard", 0)
        elif position == "finished":
            return ("finished", 0)
        elif position.startswith("track_"):
            return ("track", int(position.split("_")[1]))
        elif position.startswith("home_"):
            return ("home", int(position.split("_")[1]))
        else:
            raise ValueError(f"Invalid position format: {position}")
    
    def _calculate_new_position(self, player_id: int, current_position: str, dice_roll: int) -> Optional[str]:
        """
        Calculate new position after moving dice_roll squares.
        
        Returns:
            New position string, or None if move is invalid
        """
        player_idx = self._get_player_index(player_id)
        pos_type, pos_value = self._get_piece_position_value(current_position)
        
        # Piece in yard - needs 6 to enter
        if pos_type == "yard":
            if dice_roll == 6:
                return f"track_{self.STARTING_POSITIONS[player_idx]}"
            else:
                return None  # Can't move from yard without rolling 6
        
        # Piece already finished
        if pos_type == "finished":
            return None  # Can't move finished pieces
        
        # Piece on main track
        if pos_type == "track":
            new_track_pos = pos_value + dice_roll
            home_entry = self.HOME_ENTRY_POSITIONS[player_idx]
            
            # Check if piece passes through or lands on home entry
            # Need to account for circular track
            squares_to_home = (home_entry - pos_value) % self.BOARD_SQUARES
            
            if dice_roll == squares_to_home:
                # Lands exactly on home entry, move to home path
                return "home_0"
            elif dice_roll > squares_to_home:
                # Overshoots home entry, enters home path
                overshoot = dice_roll - squares_to_home
                if overshoot <= self.HOME_PATH_LENGTH:
                    return f"home_{overshoot}"
                else:
                    # Overshoot home path entirely
                    if self.exact_roll_to_finish:
                        return None  # Invalid move - can't overshoot
                    else:
                        return "finished"  # Some variants allow this
            else:
                # Stays on main track
                new_track_pos = (pos_value + dice_roll) % self.BOARD_SQUARES
                return f"track_{new_track_pos}"
        
        # Piece in home path
        if pos_type == "home":
            new_home_pos = pos_value + dice_roll
            
            if new_home_pos == self.HOME_PATH_LENGTH:
                # Exactly reached finish
                return "finished"
            elif new_home_pos < self.HOME_PATH_LENGTH:
                # Still in home path
                return f"home_{new_home_pos}"
            else:
                # Overshot finish
                if self.exact_roll_to_finish:
                    return None  # Invalid - need exact roll
                else:
                    return "finished"  # Some variants allow
        
        return None
    
    def _is_safe_square(self, position: str, player_id: int) -> bool:
        """
        Check if a position is safe from capture.
        
        Safe positions:
        - Yard (not on board yet)
        - Home path
        - Finished
        - Designated safe squares on main track
        """
        pos_type, pos_value = self._get_piece_position_value(position)
        
        if pos_type in ["yard", "home", "finished"]:
            return True
        
        if pos_type == "track":
            return pos_value in self.SAFE_SQUARES
        
        return False
    
    def _get_pieces_at_position(self, game_state: Dict[str, Any], position: str, exclude_player: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all pieces at a given position, optionally excluding a player"""
        pieces_at_position = []
        
        for player_id, player_pieces in game_state["pieces"].items():
            if exclude_player is not None and str(player_id) == str(exclude_player):
                continue
            
            for piece in player_pieces:
                if piece["position"] == position:
                    pieces_at_position.append({
                        "player_id": int(player_id) if str(player_id).isdigit() else player_id,
                        "piece": piece
                    })
        
        return pieces_at_position
    
    def _can_piece_move(self, game_state: Dict[str, Any], player_id: int, piece: Dict[str, Any], dice_roll: int) -> bool:
        """Check if a specific piece can make a move with the given dice roll"""
        new_position = self._calculate_new_position(player_id, piece["position"], dice_roll)
        return new_position is not None
    
    def _get_valid_pieces(self, game_state: Dict[str, Any], player_id: int, dice_roll: int) -> List[Dict[str, Any]]:
        """Get list of pieces that can move with current dice roll"""
        valid_pieces = []
        # Ensure we use string key for player_id as JSON converts keys to strings
        player_pieces = game_state["pieces"][str(player_id)]
        
        for piece in player_pieces:
            if self._can_piece_move(game_state, player_id, piece, dice_roll):
                valid_pieces.append(piece)
        
        return valid_pieces
    
    def _validate_game_specific_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate a Ludo move.
        
        Move data can contain:
        - action: "roll_dice" or "move_piece"
        - piece_id: (for move_piece) ID of piece to move
        """
        # Check if move data has required fields
        if "action" not in move_data:
            return MoveValidationResult(False, "Move must contain 'action' field")
        
        action = move_data["action"]
        
        # Handle dice roll action
        if action == "roll_dice":
            if game_state["dice_rolled"]:
                return MoveValidationResult(False, "Dice already rolled this turn")
            return MoveValidationResult(True)
        
        # Handle piece movement action
        elif action == "move_piece":
            # Check if dice has been rolled
            if not game_state["dice_rolled"]:
                return MoveValidationResult(False, "Must roll dice before moving")
            
            if game_state["move_made"]:
                return MoveValidationResult(False, "Move already made this turn")
            
            # Check if piece_id is provided
            if "piece_id" not in move_data:
                return MoveValidationResult(False, "Must specify 'piece_id' for move_piece action")
            
            piece_id = move_data["piece_id"]
            dice_roll = game_state["current_dice_roll"]
            
            # Find the piece
            # Ensure we use string key for player_id as JSON converts keys to strings
            player_pieces = game_state["pieces"][str(player_id)]
            piece = next((p for p in player_pieces if p["id"] == piece_id), None)
            
            if piece is None:
                return MoveValidationResult(False, f"Piece {piece_id} not found")
            
            # Check if piece can move with current dice roll
            if not self._can_piece_move(game_state, player_id, piece, dice_roll):
                return MoveValidationResult(False, f"Piece {piece_id} cannot move with dice roll {dice_roll}")
            
            return MoveValidationResult(True)
        
        else:
            return MoveValidationResult(False, f"Invalid action: {action}")
    
    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a validated move to the game state"""
        action = move_data["action"]
        
        if action == "roll_dice":
            # Roll the dice
            dice_roll = self._roll_dice()
            game_state["current_dice_roll"] = dice_roll
            game_state["dice_rolled"] = True
            
            # Check if player rolled a 6 (grants extra turn)
            if dice_roll == 6 and self.six_grants_extra_turn:
                game_state["extra_turn_pending"] = True
                self.extra_turn_pending = True
            else:
                game_state["extra_turn_pending"] = False
                self.extra_turn_pending = False
            
            # Check if any moves are possible
            valid_pieces = self._get_valid_pieces(game_state, player_id, dice_roll)
            if valid_pieces:
                # Player can move, so turn is not complete
                self.turn_complete = False
            else:
                # No moves possible, turn is complete
                self.turn_complete = True
            
            # Record in history
            game_state["moves_history"].append({
                "player_id": player_id,
                "action": "roll_dice",
                "dice_value": dice_roll
            })
            
        elif action == "move_piece":
            # Sync extra_turn_pending from state (it was set during roll_dice)
            self.extra_turn_pending = game_state.get("extra_turn_pending", False)
            
            piece_id = move_data["piece_id"]
            dice_roll = game_state["current_dice_roll"]
            
            # Find and update the piece
            # Ensure we use string key for player_id as JSON converts keys to strings
            player_pieces = game_state["pieces"][str(player_id)]
            piece = next(p for p in player_pieces if p["id"] == piece_id)
            
            old_position = piece["position"]
            new_position = self._calculate_new_position(player_id, old_position, dice_roll)
            
            # Handle captures
            if self.capture_sends_home and not self._is_safe_square(new_position, player_id):
                captured_pieces = self._get_pieces_at_position(game_state, new_position, exclude_player=player_id)
                for captured_info in captured_pieces:
                    captured_info["piece"]["position"] = "yard"
                    # Record capture in history
                    game_state["moves_history"].append({
                        "player_id": player_id,
                        "action": "capture",
                        "captured_player": captured_info["player_id"],
                        "captured_piece": captured_info["piece"]["id"]
                    })
            
            # Move the piece
            piece["position"] = new_position
            piece["is_safe"] = self._is_safe_square(new_position, player_id)
            
            # Mark move as made
            game_state["move_made"] = True
            
            # Record move in history
            game_state["moves_history"].append({
                "player_id": player_id,
                "action": "move_piece",
                "piece_id": piece_id,
                "from": old_position,
                "to": new_position,
                "dice_roll": dice_roll
            })
            
            # Move made, turn is complete
            self.turn_complete = True
        
        return game_state
    
    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        """Check if any player has won (all pieces finished)"""
        for player_id, player_pieces in game_state["pieces"].items():
            finished_count = sum(1 for piece in player_pieces if piece["position"] == "finished")
            
            if finished_count == self.pieces_per_player:
                # This player has won!
                self.game_result = GameResult.PLAYER_WIN
                # Ensure winner_id is int
                winner_id_int = int(player_id) if str(player_id).isdigit() else player_id
                self.winner_id = winner_id_int
                return GameResult.PLAYER_WIN, winner_id_int
        
        # Game still in progress
        return GameResult.IN_PROGRESS, None
    
    def advance_turn(self):
        """Advance to next player's turn, respecting extra turns from rolling 6"""
        # If turn is not complete (waiting for move), don't advance
        if not self.turn_complete:
            return

        # Only advance if no extra turn is pending
        if not self.extra_turn_pending:
            super().advance_turn()
        else:
            # Extra turn - same player goes again
            self.extra_turn_pending = False
    
    def start_turn(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new turn - reset turn-specific state"""
        # If turn is not complete, preserve state
        if not self.turn_complete:
            return game_state

        game_state = super().start_turn(game_state)
        
        # Reset turn state
        game_state["current_dice_roll"] = None
        game_state["dice_rolled"] = False
        game_state["move_made"] = False
        
        # Sync extra_turn_pending
        # If self.extra_turn_pending is False but game_state is True, it means we consumed it
        if game_state.get("extra_turn_pending", False) and not self.extra_turn_pending:
            game_state["extra_turn_pending"] = False
        
        # Update extra turn flag
        self.extra_turn_pending = game_state.get("extra_turn_pending", False)
        
        return game_state
    
    @classmethod
    def get_game_name(cls) -> str:
        """Get the game name"""
        return "ludo"
    
    @classmethod
    def get_game_info(cls) -> GameInfo:
        """Get static Ludo game information"""
        return GameInfo(
            game_name=cls.get_game_name(),
            display_name="Ludo",
            description="Classic Ludo board game. Race your pieces around the board and be the first to get all 4 pieces home!",
            min_players=2,
            max_players=4,
            supported_rules={
                "pieces_per_player": GameRuleOption(
                    type="integer",
                    allowed_values=[2, 3, 4],
                    default=4,
                    description="Number of pieces each player controls"
                ),
                "six_grants_extra_turn": GameRuleOption(
                    type="string",
                    allowed_values=["yes", "no"],
                    default="yes",
                    description="Whether rolling a 6 grants an extra turn"
                ),
                "exact_roll_to_finish": GameRuleOption(
                    type="string",
                    allowed_values=["yes", "no"],
                    default="yes",
                    description="Whether exact roll is needed to finish (vs. allowing overshoot)"
                ),
                "capture_sends_home": GameRuleOption(
                    type="string",
                    allowed_values=["yes", "no"],
                    default="yes",
                    description="Whether landing on opponent piece sends it back to yard"
                ),
                "timeout_type": GameRuleOption(
                    type="string",
                    allowed_values=["none", "total_time", "per_turn"],
                    default="none",
                    description="Type of timeout: 'none' (no timeout), 'total_time' (total time per player), or 'per_turn' (time limit per turn)"
                ),
                "timeout_seconds": GameRuleOption(
                    type="integer",
                    allowed_values=[30, 60, 120, 300, 600],
                    default=60,
                    description="Timeout duration in seconds. Only applies when timeout_type is not 'none'"
                )
            },
            turn_based=True,
            category="board_game",
            game_image_path="/static/images/games/ludo.png",
        )
