# app/services/games/soccer_engine.py

from typing import Dict, Any, Optional, List, Tuple
from services.game_engine_interface import (
    GameEngineInterface,
    MoveValidationResult,
    GameResult,
)
from schemas.game_schema import GameInfo, GameRuleOption


class SoccerEngine(GameEngineInterface):
    """
    Paper soccer game engine implementation.
    
    Rules implemented:
    - Start from the center of the pitch
    - Move the ball in 8 directions (king move)
    - You cannot draw the same segment twice
    - If you land on a node that already had a segment, or on the boundary,
      you keep the turn (bonus move)
    - A player loses when the ball enters their goal or when the player to move
      has no legal moves
    """

    # Direction vectors (dx, dy)
    DIRECTIONS: Dict[str, Tuple[int, int]] = {
        "N": (0, -1),
        "NE": (1, -1),
        "E": (1, 0),
        "SE": (1, 1),
        "S": (0, 1),
        "SW": (-1, 1),
        "W": (-1, 0),
        "NW": (-1, -1),
    }

    def __init__(self, lobby_code: str, player_ids: List[int], rules: Optional[Dict[str, Any]] = None):
        super().__init__(lobby_code, player_ids, rules)

        if len(player_ids) != 2:
            raise ValueError("Paper soccer requires exactly 2 players")

        # Pitch configuration via presets
        self.pitch_size = self.rules.get("pitch_size", "medium")
        pitch_presets = {
            "small": {"field_width": 7, "field_height": 9, "goal_width": 3},
            "medium": {"field_width": 9, "field_height": 13, "goal_width": 3},
            "large": {"field_width": 11, "field_height": 17, "goal_width": 5},
        }
        if self.pitch_size not in pitch_presets:
            raise ValueError("Unsupported pitch_size. Use: small, medium, or large")

        preset = pitch_presets[self.pitch_size]
        self.field_width = preset["field_width"]
        self.field_height = preset["field_height"]
        self.goal_width = preset["goal_width"]

        self.center_x = self.field_width // 2
        self.center_y = self.field_height // 2
        self.goal_start_x = (self.field_width - self.goal_width) // 2
        self.goal_end_x = self.goal_start_x + self.goal_width - 1

        # Player 0 defends the top goal, player 1 defends the bottom goal
        self.top_goal_defender = player_ids[0]
        self.bottom_goal_defender = player_ids[1]

        # Track whether the last move granted a bonus turn
        self._extra_turn_granted = False

    def _initialize_game_specific_state(self) -> Dict[str, Any]:
        """Set up the initial pitch, ball position, and tracking structures."""
        start_pos = {"x": self.center_x, "y": self.center_y}
        return {
            "field": {
                "width": self.field_width,
                "height": self.field_height,
                "goal_width": self.goal_width,
                "goal_x_start": self.goal_start_x,
                "goal_x_end": self.goal_end_x,
                "top_goal_defender": self.top_goal_defender,
                "bottom_goal_defender": self.bottom_goal_defender,
            },
            "ball_position": start_pos,
            "move_count": 0,
            "lines": [],  # List of {"from": {...}, "to": {...}, "player_id": ...}
            "visited_edges": [],  # Stored as string keys for easy lookup
            "node_degrees": {self._node_key(start_pos): 0},
            "last_move": None,
            "extra_turn_awarded": False,
            "available_moves": self._legal_moves_from_position([], start_pos),
        }

    def _validate_game_specific_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> MoveValidationResult:
        """
        Validate a paper soccer move.

        Move data can be provided as:
        - {"direction": "N" | "NE" | "E" | "SE" | "S" | "SW" | "W" | "NW"}
        - {"to_x": int, "to_y": int}
        """
        ball_pos = game_state["ball_position"]

        # Resolve the target position and delta
        target, delta = self._resolve_target(ball_pos, move_data)
        if target is None:
            return MoveValidationResult(False, "Move must include 'direction' or 'to_x'/'to_y'")

        dx, dy = delta
        if dx == 0 and dy == 0:
            return MoveValidationResult(False, "Move cannot stay in place")
        if abs(dx) > 1 or abs(dy) > 1:
            return MoveValidationResult(False, "Move must be to an adjacent node (8 directions)")

        if not self._is_reachable_node(ball_pos, target["x"], target["y"]):
            return MoveValidationResult(False, "Target position is outside the playable area")

        # If we're on an edge, only moves that go inward are allowed (no moves parallel to the boundary)
        if not self._edge_move_allowed(ball_pos, delta, target):
            return MoveValidationResult(False, "Moves along the border are not allowed; move inward instead")

        # Check if this segment was already drawn
        edge_key = self._edge_key(ball_pos, target)
        if edge_key in set(game_state.get("visited_edges", [])):
            return MoveValidationResult(False, "This line segment has already been used")

        return MoveValidationResult(True)

    def apply_move(self, game_state: Dict[str, Any], player_id: int, move_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a validated move, update tracking, and flag bonus turns."""
        ball_pos = game_state["ball_position"]
        target, _ = self._resolve_target(ball_pos, move_data)
        if target is None:
            return game_state  # Should not happen after validation

        # Check existing connections at the destination before we add the new line
        dest_key = self._node_key(target)
        node_degrees = game_state.get("node_degrees", {})
        previous_degree_at_dest = node_degrees.get(dest_key, 0)

        # Register the new edge
        edge_key = self._edge_key(ball_pos, target)
        visited_edges = set(game_state.get("visited_edges", []))
        visited_edges.add(edge_key)
        game_state["visited_edges"] = list(visited_edges)

        node_degrees[self._node_key(ball_pos)] = node_degrees.get(self._node_key(ball_pos), 0) + 1
        node_degrees[dest_key] = node_degrees.get(dest_key, 0) + 1
        game_state["node_degrees"] = node_degrees

        # Record the line and move metadata
        line_entry = {
            "from": {"x": ball_pos["x"], "y": ball_pos["y"]},
            "to": {"x": target["x"], "y": target["y"]},
            "player_id": player_id,
        }
        game_state["lines"].append(line_entry)
        game_state["move_count"] += 1
        game_state["last_move"] = {
            "player_id": player_id,
            "from": line_entry["from"],
            "to": line_entry["to"],
        }

        # Move the ball
        game_state["ball_position"] = target

        # Determine if this grants an extra turn (hit boundary or existing node)
        extra_turn = self._should_award_extra_turn(target, previous_degree_at_dest)
        self._extra_turn_granted = extra_turn
        game_state["extra_turn_awarded"] = extra_turn

        # Pre-compute available moves for the next player (use updated edges)
        game_state["available_moves"] = self._legal_moves_from_position(game_state["visited_edges"], target)

        return game_state

    def check_game_result(self, game_state: Dict[str, Any]) -> tuple[GameResult, Optional[int]]:
        """Check if the ball entered a goal or if the next player is stuck."""
        ball_pos = game_state["ball_position"]

        # Goal check
        defender = self._goal_defender_for_position(ball_pos)
        if defender is not None:
            self.game_result = GameResult.PLAYER_WIN
            winner_id = next(pid for pid in self.player_ids if pid != defender)
            self.winner_id = winner_id
            return GameResult.PLAYER_WIN, winner_id

        # No-move check for the player whose turn is next
        available = game_state.get("available_moves")
        if available is None:
            available = self._legal_moves_from_position(game_state.get("visited_edges", []), ball_pos)

        next_player_index = self.current_turn_index if self._extra_turn_granted else (self.current_turn_index + 1) % len(self.player_ids)
        if not available:
            self.game_result = GameResult.PLAYER_WIN
            winner_id = next(pid for i, pid in enumerate(self.player_ids) if i != next_player_index)
            self.winner_id = winner_id
            return GameResult.PLAYER_WIN, winner_id

        return GameResult.IN_PROGRESS, None

    def advance_turn(self):
        """
        Override to support bonus turns.
        If the last move granted an extra turn, keep the same player; otherwise, rotate.
        """
        if self._extra_turn_granted:
            self._extra_turn_granted = False
            return
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)

    # Helpers
    def _resolve_target(self, ball_pos: Dict[str, int], move_data: Dict[str, Any]) -> tuple[Optional[Dict[str, int]], Tuple[int, int]]:
        """Return the target position and delta based on direction or explicit coordinates."""
        if "direction" in move_data:
            direction = str(move_data["direction"]).upper()
            if direction not in self.DIRECTIONS:
                return None, (0, 0)
            dx, dy = self.DIRECTIONS[direction]
            return {"x": ball_pos["x"] + dx, "y": ball_pos["y"] + dy}, (dx, dy)

        if "to_x" in move_data and "to_y" in move_data:
            try:
                to_x = int(move_data["to_x"])
                to_y = int(move_data["to_y"])
            except (TypeError, ValueError):
                return None, (0, 0)
            return {"x": to_x, "y": to_y}, (to_x - ball_pos["x"], to_y - ball_pos["y"])

        return None, (0, 0)

    def _is_within_field(self, x: int, y: int) -> bool:
        """Check if coordinates are inside the rectangular field (excluding goals)."""
        height = 0 <= y < self.field_height
        width = 0 <= x < self.field_width
        return height and width

    def _is_goal_node(self,ball_pos: Dict[str, int], x: int, y: int) -> bool:
        """Check if the coordinates are inside one of the goal openings."""
        return (
            self.goal_start_x <= x <= self.goal_end_x
            and (y == -1 or y == self.field_height)
            and ball_pos['x'] >= self.goal_start_x and ball_pos["x"] <= self.goal_end_x
        )


    def _is_reachable_node(self,ball_pos: Dict[str, int], x: int, y: int) -> bool:
        """Reachable nodes are inside the field or inside the goal openings."""
        return self._is_within_field(x, y) or self._is_goal_node(ball_pos,x, y) 

    def _edge_move_allowed(self, position: Dict[str, int], delta: Tuple[int, int], target: Optional[Dict[str, int]] = None) -> bool:
        """
        When on a boundary node, disallow moves that run parallel to the edge.
        Only moves that go inward from each touched edge are allowed.
        """
        dx, dy = delta
        if not self._is_boundary_node(position):
            return True
        
        x = position["x"]
        y = position["y"]

        target_x = x + dx if target is None else target["x"]
        target_y = y + dy if target is None else target["y"]

        # Allow moving outward into a goal opening (scoring)
        if self._is_goal_node(position,target_x, target_y):
            return True

        if (x == self.goal_start_x and target_x > x and dy == 0):
            return True
        if (x == self.goal_end_x and target_x < x and dy == 0):
            return True

        # Moving away from left edge requires dx > 0, from right edge dx < 0, etc.
        if position["x"] == 0 and dx <= 0:
            return False
        if position["x"] == self.field_width - 1 and dx >= 0:
            return False
        if position["y"] == 0 and dy <= 0:
            return False
        if position["y"] == self.field_height - 1 and dy >= 0:
            return False

        return True

    def _edge_key(self, start: Dict[str, int], end: Dict[str, int]) -> str:
        """Store edges as undirected strings for fast repeat checks."""
        a = (start["x"], start["y"])
        b = (end["x"], end["y"])
        if a <= b:
            first, second = a, b
        else:
            first, second = b, a
        return f"{first[0]},{first[1]}-{second[0]},{second[1]}"

    def _node_key(self, pos: Dict[str, int]) -> str:
        return f"{pos['x']},{pos['y']}"

    def _should_award_extra_turn(self, pos: Dict[str, int], previous_degree: int) -> bool:
        """
        Bonus turn when landing on:
        - A boundary node (touching the wall)
        - A node that already had at least one segment attached
        """

        return previous_degree > 0 or self._is_boundary_node(pos)

    def _is_boundary_node(self, pos: Dict[str, int]) -> bool:
        """Boundary nodes lie on the rectangle edges (excluding goals outside the field)."""
        if not self._is_within_field(pos["x"], pos["y"]):
            return False
        return (
            pos["x"] == 0
            or pos["x"] == self.field_width - 1
            or 
            ((pos["y"] == 0 or pos["y"] == self.field_height - 1)
            and (pos["x"] <= self.goal_start_x or pos["x"] >= self.goal_end_x))
        )



    def _goal_defender_for_position(self, pos: Dict[str, int]) -> Optional[int]:
        """Return the defender whose goal the ball is in, or None."""
        if self.goal_start_x <= pos["x"] <= self.goal_end_x:
            if pos["y"] == -1:
                return self.top_goal_defender
            if pos["y"] == self.field_height:
                return self.bottom_goal_defender
        return None

    def _legal_moves_from_position(self, visited_edges: List[str], position: Dict[str, int]) -> List[Dict[str, int]]:
        """List all legal destinations from the current ball position."""
        visited = set(visited_edges)
        moves = []
        for dx, dy in self.DIRECTIONS.values():
            target_x = position["x"] + dx
            target_y = position["y"] + dy
            if not self._is_reachable_node(position,target_x, target_y):
                continue
            if not self._edge_move_allowed(position, (dx, dy), {"x": target_x, "y": target_y}):
                continue
            edge_key = self._edge_key(position, {"x": target_x, "y": target_y})
            if edge_key in visited:
                continue
            moves.append({"x": target_x, "y": target_y})
        return moves

    @classmethod
    def get_game_name(cls) -> str:
        return "soccer"

    @classmethod
    def get_game_info(cls) -> GameInfo:
        """Expose static info for the paper soccer game."""
        return GameInfo(
            game_name=cls.get_game_name(),
            display_name="Soccer",
            description="Draw lines to move the ball across the grid. Reach your opponent's goal or trap them without moves.",
            min_players=2,
            max_players=2,
            supported_rules={
                "pitch_size": GameRuleOption(
                    type="string",
                    allowed_values=["small", "medium", "large"],
                    default="medium",
                    description="Preset pitch sizes: small (7x9), medium (9x13), large (11x17)."
                ),
                "timeout_type": GameRuleOption(
                    type="string",
                    allowed_values=["none", "total_time", "per_turn"],
                    default="none",
                    description="Timeout handling: none, total_time per player, or per_turn."
                ),
                "timeout_seconds": GameRuleOption(
                    type="integer",
                    allowed_values=[10, 15, 30, 60, 120, 300, 600],
                    default=300,
                    description="Timeout duration in seconds when a timeout is enabled."
                ),
            },
            turn_based=True,
            category="strategy",
            game_image_path="/images/games/soccer.png",
        )
