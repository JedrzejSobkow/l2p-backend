# app/tests/test_soccer_engine.py

import pytest
from services.games.soccer_engine import SoccerEngine
from services.game_engine_interface import GameResult


class TestSoccerEngine:
    """Tests for SoccerEngine"""
    
    def test_initialization_default(self):
        """Test default medium pitch initialization"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        assert engine.lobby_code == "TEST123"
        assert engine.player_ids == [1, 2]
        assert engine.pitch_size == "medium"
        assert engine.field_width == 9
        assert engine.field_height == 13
        assert engine.goal_width == 3
        assert engine.center_x == 4
        assert engine.center_y == 6
        assert engine.goal_start_x == 3
        assert engine.goal_end_x == 5
        assert engine.top_goal_defender == 1
        assert engine.bottom_goal_defender == 2
        assert engine._extra_turn_granted is False
        
    def test_initialization_small_pitch(self):
        """Test small pitch initialization"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        
        assert engine.pitch_size == "small"
        assert engine.field_width == 7
        assert engine.field_height == 9
        assert engine.goal_width == 3
        
    def test_initialization_large_pitch(self):
        """Test large pitch initialization"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "large"})
        
        assert engine.pitch_size == "large"
        assert engine.field_width == 11
        assert engine.field_height == 17
        assert engine.goal_width == 5
        
    def test_initialization_invalid_pitch_size(self):
        """Test that initialization fails with invalid pitch size"""
        with pytest.raises(ValueError, match="not in allowed values"):
            SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "huge"})
    
    def test_initialization_invalid_player_count(self):
        """Test that initialization fails with wrong number of players"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            SoccerEngine("TEST123", [1, 2, 3])
            
    def test_initialization_single_player(self):
        """Test that initialization fails with only one player"""
        with pytest.raises(ValueError, match="exactly 2 players"):
            SoccerEngine("TEST123", [1])
    
    def test_initialize_game_state(self):
        """Test game state initialization"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert "field" in state
        assert state["field"]["width"] == 9
        assert state["field"]["height"] == 13
        assert state["field"]["goal_width"] == 3
        assert state["field"]["top_goal_defender"] == 1
        assert state["field"]["bottom_goal_defender"] == 2
        assert state["ball_position"] == {"x": 4, "y": 6}
        assert state["move_count"] == 0
        assert state["lines"] == []
        assert state["visited_edges"] == []
        assert state["node_degrees"] == {"4,6": 0}
        assert state["last_move"] is None
        assert state["extra_turn_awarded"] is False
        assert len(state["available_moves"]) == 8  # All 8 directions from center
        
    def test_validate_move_valid_direction(self):
        """Test valid move validation using direction"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"direction": "N"})
        
        assert result.valid is True
        assert result.error_message is None
        
    def test_validate_move_valid_coordinates(self):
        """Test valid move validation using coordinates"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"to_x": 5, "to_y": 5})
        
        assert result.valid is True
        
    def test_validate_move_all_directions(self):
        """Test all 8 direction moves are valid from center"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        for direction in directions:
            result = engine.validate_move(state, 1, {"direction": direction})
            assert result.valid is True, f"Direction {direction} should be valid"
    
    def test_validate_move_lowercase_direction(self):
        """Test lowercase direction is accepted"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"direction": "ne"})
        
        assert result.valid is True
        
    def test_validate_move_invalid_direction(self):
        """Test validation fails for invalid direction"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"direction": "INVALID"})
        
        assert result.valid is False
        assert "direction" in result.error_message or "to_x" in result.error_message
        
    def test_validate_move_no_move_data(self):
        """Test validation fails when no direction or coordinates provided"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {})
        
        assert result.valid is False
        assert "direction" in result.error_message or "to_x" in result.error_message
        
    def test_validate_move_stay_in_place(self):
        """Test validation fails for zero movement"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"to_x": 4, "to_y": 6})
        
        assert result.valid is False
        assert "stay in place" in result.error_message
        
    def test_validate_move_too_far(self):
        """Test validation fails for movement beyond adjacent nodes"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"to_x": 6, "to_y": 6})
        
        assert result.valid is False
        assert "adjacent node" in result.error_message
        
    def test_validate_move_invalid_coordinates_type(self):
        """Test validation fails for invalid coordinate types"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"to_x": "invalid", "to_y": 5})
        
        assert result.valid is False
        
    def test_validate_move_out_of_bounds(self):
        """Test validation fails for out of bounds position"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result = engine.validate_move(state, 1, {"to_x": 20, "to_y": 20})
        
        assert result.valid is False
        assert "adjacent node" in result.error_message or "outside the playable area" in result.error_message
        
    def test_validate_move_duplicate_edge(self):
        """Test validation fails for using the same line segment twice"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Make first move
        state = engine.apply_move(state, 1, {"direction": "N"})
        engine.advance_turn()
        
        # Try to use same edge (reverse direction)
        result = engine.validate_move(state, 2, {"direction": "S"})
        
        assert result.valid is False
        assert "already been used" in result.error_message
        
    def test_apply_move_basic(self):
        """Test applying a basic move"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.apply_move(state, 1, {"direction": "N"})
        
        assert state["ball_position"] == {"x": 4, "y": 5}
        assert state["move_count"] == 1
        assert len(state["lines"]) == 1
        assert state["lines"][0]["from"] == {"x": 4, "y": 6}
        assert state["lines"][0]["to"] == {"x": 4, "y": 5}
        assert state["lines"][0]["player_id"] == 1
        assert len(state["visited_edges"]) == 1
        assert state["last_move"]["player_id"] == 1
        
    def test_apply_move_with_coordinates(self):
        """Test applying a move using coordinates"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.apply_move(state, 1, {"to_x": 5, "to_y": 7})
        
        assert state["ball_position"] == {"x": 5, "y": 7}
        assert state["move_count"] == 1
        
    def test_apply_move_updates_node_degrees(self):
        """Test that node degrees are tracked correctly"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.apply_move(state, 1, {"direction": "N"})
        
        assert state["node_degrees"]["4,6"] == 1  # Starting node
        assert state["node_degrees"]["4,5"] == 1  # Destination node
        
    def test_extra_turn_on_boundary(self):
        """Test that extra turn is awarded when hitting a boundary"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        state = engine.initialize_game_state()
        
        # Move to boundary (left edge)
        state = engine.apply_move(state, 1, {"direction": "W"})
        state = engine.apply_move(state, 1, {"direction": "W"})
        state = engine.apply_move(state, 1, {"direction": "W"})
        
        # Should have extra turn when reaching x=0
        assert state["extra_turn_awarded"] is True
        assert engine._extra_turn_granted is True
        
    def test_extra_turn_on_visited_node(self):
        """Test that extra turn is awarded when landing on a visited node"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Move to create a node with degree > 0
        state = engine.apply_move(state, 1, {"direction": "N"})  # Ball at 4,5
        engine.advance_turn()
        state = engine.apply_move(state, 2, {"direction": "N"})  # Ball at 4,4
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "E"})  # Ball at 5,4
        engine.advance_turn()
        state = engine.apply_move(state, 2, {"direction": "S"})  # Ball at 5,5 - this node connects to 4,5 which has degree 2
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "W"})  # Ball at 4,5 - revisit node with degree > 0
        
        # Landing on a node with existing connections grants extra turn
        assert state["extra_turn_awarded"] is True
        
    def test_no_extra_turn_on_new_node(self):
        """Test that no extra turn is awarded on fresh nodes"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state = engine.apply_move(state, 1, {"direction": "N"})
        
        # First move to a fresh interior node should not grant extra turn
        assert state["extra_turn_awarded"] is False
        assert engine._extra_turn_granted is False
        
    def test_advance_turn_normal(self):
        """Test normal turn advancement"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        assert engine.current_player_id == 1
        engine.advance_turn()
        assert engine.current_player_id == 2
        engine.advance_turn()
        assert engine.current_player_id == 1
        
    def test_advance_turn_with_extra_turn(self):
        """Test that turn doesn't advance when extra turn is granted"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        state = engine.initialize_game_state()
        
        # Move to boundary to get extra turn
        state = engine.apply_move(state, 1, {"direction": "W"})
        state = engine.apply_move(state, 1, {"direction": "W"})
        state = engine.apply_move(state, 1, {"direction": "W"})
        
        assert engine.current_player_id == 1
        engine.advance_turn()  # Should stay player 1
        assert engine.current_player_id == 1
        assert engine._extra_turn_granted is False  # Flag cleared after advance
        
    def test_check_game_result_in_progress(self):
        """Test game result when game is still in progress"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
        
    def test_check_game_result_top_goal(self):
        """Test win condition when ball enters top goal"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        state = engine.initialize_game_state()
        
        # Move ball to top goal area (y=-1)
        # Start at center (3, 4), move to goal opening
        state = engine.apply_move(state, 1, {"direction": "N"})
        engine.advance_turn()
        state = engine.apply_move(state, 2, {"direction": "N"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "N"})
        engine.advance_turn()
        state = engine.apply_move(state, 2, {"direction": "N"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "N"})  # Should reach y=-1
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 2  # Player 2 wins (player 1 defended top goal)
        
    def test_check_game_result_bottom_goal(self):
        """Test win condition when ball enters bottom goal"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        state = engine.initialize_game_state()
        
        # Move ball to bottom goal area
        state = engine.apply_move(state, 1, {"direction": "S"})
        engine.advance_turn()
        state = engine.apply_move(state, 2, {"direction": "S"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "S"})
        engine.advance_turn()
        state = engine.apply_move(state, 2, {"direction": "S"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "S"})  # Should reach bottom goal
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1  # Player 1 wins (player 2 defended bottom goal)
        
    def test_check_game_result_no_moves_available(self):
        """Test win condition when player has no legal moves"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Simulate a trapped position by marking all edges as visited
        state["ball_position"] = {"x": 0, "y": 0}  # Corner
        state["visited_edges"] = [
            "0,0-0,1",
            "0,0-1,0",
            "0,0-1,1",
        ]
        state["available_moves"] = []
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner is not None
        
    def test_available_moves_computed(self):
        """Test that available moves are computed after each move"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        initial_moves = len(state["available_moves"])
        assert initial_moves == 8
        
        state = engine.apply_move(state, 1, {"direction": "N"})
        
        # Available moves should be updated
        assert "available_moves" in state
        assert len(state["available_moves"]) > 0
        
    def test_edge_key_consistency(self):
        """Test that edge keys are consistent regardless of direction"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        key1 = engine._edge_key({"x": 1, "y": 1}, {"x": 2, "y": 2})
        key2 = engine._edge_key({"x": 2, "y": 2}, {"x": 1, "y": 1})
        
        assert key1 == key2
        
    def test_node_key(self):
        """Test node key generation"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        key = engine._node_key({"x": 3, "y": 5})
        
        assert key == "3,5"
        
    def test_is_within_field(self):
        """Test field boundary checking"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        assert engine._is_within_field(0, 0) is True
        assert engine._is_within_field(8, 12) is True
        assert engine._is_within_field(-1, 0) is False
        assert engine._is_within_field(0, -1) is False
        assert engine._is_within_field(9, 0) is False
        assert engine._is_within_field(0, 13) is False
        
    def test_is_goal_node_top_goal(self):
        """Test top goal node detection"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # Ball at goal entrance
        ball_pos = {"x": 4, "y": 0}
        assert engine._is_goal_node(ball_pos, 4, -1) is True
        
    def test_is_goal_node_bottom_goal(self):
        """Test bottom goal node detection"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # Ball at goal entrance
        ball_pos = {"x": 4, "y": 12}
        assert engine._is_goal_node(ball_pos, 4, 13) is True
        
    def test_is_goal_node_outside_goal_range(self):
        """Test that positions outside goal width are not goal nodes"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        ball_pos = {"x": 0, "y": 0}
        assert engine._is_goal_node(ball_pos, 0, -1) is False
        
    def test_is_reachable_node(self):
        """Test reachable node detection"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        ball_pos = {"x": 4, "y": 0}
        assert engine._is_reachable_node(ball_pos, 4, 5) is True
        assert engine._is_reachable_node(ball_pos, 4, -1) is True  # Goal
        assert engine._is_reachable_node(ball_pos, 20, 20) is False
        
    def test_is_boundary_node_corners(self):
        """Test boundary node detection at corners"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        assert engine._is_boundary_node({"x": 0, "y": 0}) is True
        assert engine._is_boundary_node({"x": 8, "y": 0}) is True
        assert engine._is_boundary_node({"x": 0, "y": 12}) is True
        assert engine._is_boundary_node({"x": 8, "y": 12}) is True
        
    def test_is_boundary_node_edges(self):
        """Test boundary node detection at edges"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        assert engine._is_boundary_node({"x": 0, "y": 6}) is True  # Left edge
        assert engine._is_boundary_node({"x": 8, "y": 6}) is True  # Right edge
        assert engine._is_boundary_node({"x": 4, "y": 0}) is False  # Top edge in goal area
        assert engine._is_boundary_node({"x": 4, "y": 12}) is False  # Bottom edge in goal area
        assert engine._is_boundary_node({"x": 2, "y": 0}) is True  # Top edge outside goal
        assert engine._is_boundary_node({"x": 6, "y": 12}) is True  # Bottom edge outside goal
        
    def test_is_boundary_node_interior(self):
        """Test that interior nodes are not boundary nodes"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        assert engine._is_boundary_node({"x": 4, "y": 6}) is False
        
    def test_is_boundary_node_outside_field(self):
        """Test that positions outside field are not boundary nodes"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        assert engine._is_boundary_node({"x": -1, "y": 5}) is False
        assert engine._is_boundary_node({"x": 4, "y": -1}) is False
        
    def test_goal_defender_for_position_top_goal(self):
        """Test goal defender detection for top goal"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        defender = engine._goal_defender_for_position({"x": 4, "y": -1})
        assert defender == 1  # Top goal defender
        
    def test_goal_defender_for_position_bottom_goal(self):
        """Test goal defender detection for bottom goal"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        defender = engine._goal_defender_for_position({"x": 4, "y": 13})
        assert defender == 2  # Bottom goal defender
        
    def test_goal_defender_for_position_not_in_goal(self):
        """Test that non-goal positions return None"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        defender = engine._goal_defender_for_position({"x": 4, "y": 6})
        assert defender is None
        
    def test_goal_defender_for_position_outside_goal_width(self):
        """Test that positions outside goal width return None"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        defender = engine._goal_defender_for_position({"x": 0, "y": -1})
        assert defender is None
        
    def test_edge_move_allowed_from_interior(self):
        """Test that all moves are allowed from interior nodes"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        position = {"x": 4, "y": 6}
        assert engine._edge_move_allowed(position, (1, 0)) is True
        assert engine._edge_move_allowed(position, (-1, 0)) is True
        assert engine._edge_move_allowed(position, (0, 1)) is True
        assert engine._edge_move_allowed(position, (0, -1)) is True
        
    def test_edge_move_allowed_from_left_boundary(self):
        """Test edge moves from left boundary"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        position = {"x": 0, "y": 6}
        assert engine._edge_move_allowed(position, (1, 0)) is True  # Inward OK
        assert engine._edge_move_allowed(position, (-1, 0)) is False  # Outward blocked
        assert engine._edge_move_allowed(position, (0, 1)) is False  # Parallel blocked
        
    def test_edge_move_allowed_from_right_boundary(self):
        """Test edge moves from right boundary"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        position = {"x": 8, "y": 6}
        assert engine._edge_move_allowed(position, (-1, 0)) is True  # Inward OK
        assert engine._edge_move_allowed(position, (1, 0)) is False  # Outward blocked
        
    def test_edge_move_allowed_from_top_boundary(self):
        """Test edge moves from top boundary"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        position = {"x": 2, "y": 0}  # Outside goal area
        assert engine._edge_move_allowed(position, (0, 1)) is True  # Inward OK
        assert engine._edge_move_allowed(position, (0, -1)) is False  # Outward blocked
        
    def test_edge_move_allowed_from_bottom_boundary(self):
        """Test edge moves from bottom boundary"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        position = {"x": 2, "y": 12}  # Outside goal area
        assert engine._edge_move_allowed(position, (0, -1)) is True  # Inward OK
        assert engine._edge_move_allowed(position, (0, 1)) is False  # Outward blocked
        
    def test_edge_move_allowed_into_goal(self):
        """Test that moves into goal openings are allowed"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        position = {"x": 4, "y": 0}
        target = {"x": 4, "y": -1}
        assert engine._edge_move_allowed(position, (0, -1), target) is True
        
    def test_edge_move_allowed_goal_boundary_horizontal(self):
        """Test horizontal moves at goal boundaries"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # At left edge of goal opening
        position = {"x": 3, "y": 0}
        target = {"x": 4, "y": 0}
        assert engine._edge_move_allowed(position, (1, 0), target) is True
        
        # At right edge of goal opening
        position = {"x": 5, "y": 0}
        target = {"x": 4, "y": 0}
        assert engine._edge_move_allowed(position, (-1, 0), target) is True
        
    def test_legal_moves_from_center(self):
        """Test legal moves from center position"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        moves = engine._legal_moves_from_position([], {"x": 4, "y": 6})
        
        assert len(moves) == 8  # All 8 directions available
        
    def test_legal_moves_from_corner(self):
        """Test legal moves from corner position"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        moves = engine._legal_moves_from_position([], {"x": 0, "y": 0})
        
        # From corner (0,0), only diagonal SE move is allowed due to edge restrictions
        assert len(moves) >= 1
        assert {"x": 1, "y": 1} in moves
        
    def test_legal_moves_with_visited_edges(self):
        """Test that visited edges are excluded from legal moves"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        visited = ["4,5-4,6"]  # Block move north (normalized edge key)
        moves = engine._legal_moves_from_position(visited, {"x": 4, "y": 6})
        
        assert len(moves) == 7  # 8 - 1 blocked
        assert {"x": 4, "y": 5} not in moves  # North move should be blocked
        
    def test_legal_moves_near_goal(self):
        """Test legal moves near goal opening"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        moves = engine._legal_moves_from_position([], {"x": 4, "y": 0})
        
        # Should include move into goal
        goal_move = {"x": 4, "y": -1}
        assert goal_move in moves
        
    def test_get_game_name(self):
        """Test game name retrieval"""
        assert SoccerEngine.get_game_name() == "soccer"
        
    def test_get_game_info(self):
        """Test game info retrieval"""
        info = SoccerEngine.get_game_info()
        
        assert info.game_name == "soccer"
        assert info.display_name == "Soccer"
        assert info.min_players == 2
        assert info.max_players == 2
        assert info.turn_based is True
        assert info.category == "strategy"
        assert "pitch_size" in info.supported_rules
        assert "timeout_type" in info.supported_rules
        assert "timeout_seconds" in info.supported_rules
        
    def test_get_game_info_pitch_size_options(self):
        """Test pitch size rule options"""
        info = SoccerEngine.get_game_info()
        
        pitch_rule = info.supported_rules["pitch_size"]
        assert pitch_rule.type == "string"
        assert pitch_rule.default == "medium"
        assert "small" in pitch_rule.allowed_values
        assert "medium" in pitch_rule.allowed_values
        assert "large" in pitch_rule.allowed_values
        
    def test_get_game_info_timeout_options(self):
        """Test timeout rule options"""
        info = SoccerEngine.get_game_info()
        
        timeout_type = info.supported_rules["timeout_type"]
        assert timeout_type.type == "string"
        assert timeout_type.default == "none"
        
        timeout_seconds = info.supported_rules["timeout_seconds"]
        assert timeout_seconds.type == "integer"
        assert timeout_seconds.default == 300
        
    def test_complex_game_sequence(self):
        """Test a complex sequence of moves"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 1 moves
        state = engine.apply_move(state, 1, {"direction": "N"})
        engine.advance_turn()
        assert engine.current_player_id == 2
        
        # Player 2 moves
        state = engine.apply_move(state, 2, {"direction": "E"})
        engine.advance_turn()
        assert engine.current_player_id == 1
        
        # Player 1 cannot move W as it would reuse an edge - move NW instead
        state = engine.apply_move(state, 1, {"direction": "NW"})
        
        assert state["move_count"] == 3
        assert len(state["lines"]) == 3
        assert len(state["visited_edges"]) == 3
        
    def test_apply_move_invalid_move_data(self):
        """Test that apply_move handles invalid move data gracefully"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Apply move with invalid data (should return unchanged state)
        result_state = engine.apply_move(state, 1, {"invalid": "data"})
        
        # State should remain unchanged
        assert result_state["ball_position"] == state["ball_position"]
        assert result_state["move_count"] == 0
        
    def test_check_game_result_computes_available_moves(self):
        """Test that check_game_result computes available moves when not present"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Remove available_moves to test computation
        state.pop("available_moves", None)
        
        result, winner = engine.check_game_result(state)
        
        # Should still work correctly
        assert result == GameResult.IN_PROGRESS
        
    def test_multiple_extra_turns_sequence(self):
        """Test sequence with multiple consecutive extra turns"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        state = engine.initialize_game_state()
        
        # Move to left boundary
        state = engine.apply_move(state, 1, {"direction": "W"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "W"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "W"})
        engine.advance_turn()
        
        # Now at boundary, should still be player 1
        assert engine.current_player_id == 1
        
        # Move along boundary (should grant another extra turn)
        state = engine.apply_move(state, 1, {"direction": "N"})
        engine.advance_turn()
        
        assert engine.current_player_id == 1  # Still player 1 due to boundary
        
    def test_should_award_extra_turn_scenarios(self):
        """Test various scenarios for extra turn awards"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # Fresh interior node - no extra turn
        assert engine._should_award_extra_turn({"x": 4, "y": 6}, 0) is False
        
        # Node with previous connections - extra turn
        assert engine._should_award_extra_turn({"x": 4, "y": 6}, 1) is True
        
        # Boundary node - extra turn
        assert engine._should_award_extra_turn({"x": 0, "y": 6}, 0) is True
        
        # Boundary node with connections - extra turn
        assert engine._should_award_extra_turn({"x": 0, "y": 6}, 2) is True
        
    def test_resolve_target_with_none_delta(self):
        """Test resolve target with various edge cases"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # No valid direction or coordinates
        target, delta = engine._resolve_target({"x": 4, "y": 6}, {"invalid": "data"})
        assert target is None
        assert delta == (0, 0)
        
    def test_edge_move_from_goal_entrance(self):
        """Test moves from goal entrance positions"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # Position at top of field in goal area
        position = {"x": 4, "y": 0}
        
        # Moving into goal should be allowed
        target = {"x": 4, "y": -1}
        assert engine._edge_move_allowed(position, (0, -1), target) is True
        
    def test_all_directions_blocked_scenario(self):
        """Test scenario where all directions from a position are blocked"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Manually set up a trapped scenario - use normalized edge keys
        state["ball_position"] = {"x": 4, "y": 6}
        state["visited_edges"] = [
            "4,5-4,6", "4,6-5,5", "4,6-5,6", "4,6-5,7",
            "4,6-4,7", "3,7-4,6", "3,6-4,6", "3,5-4,6"
        ]
        state["available_moves"] = []  # Explicitly set no available moves
        
        moves = engine._legal_moves_from_position(state["visited_edges"], state["ball_position"])
        assert len(moves) == 0
        
        result, winner = engine.check_game_result(state)
        assert result == GameResult.PLAYER_WIN
        assert winner is not None
        
    def test_validate_move_wrong_turn(self):
        """Test move validation for wrong player's turn"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Current player is 1
        result = engine.validate_move(state, 2, {"direction": "N"})
        
        assert result.valid is False
        assert "not your turn" in result.error_message
        
    def test_validate_move_edge_move_not_allowed(self):
        """Test validation fails when edge move is not allowed from boundary"""
        engine = SoccerEngine("TEST123", [1, 2], rules={"pitch_size": "small"})
        state = engine.initialize_game_state()
        
        # Move to left boundary
        state = engine.apply_move(state, 1, {"direction": "W"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "W"})
        engine.advance_turn()
        state = engine.apply_move(state, 1, {"direction": "W"})
        # Now at x=0
        engine.advance_turn()
        
        # Try to move parallel to boundary (south along left edge)
        result = engine.validate_move(state, 1, {"direction": "S"})
        
        assert result.valid is False
        assert "border" in result.error_message or "inward" in result.error_message
        
    def test_validate_move_not_reachable(self):
        """Test validation fails for unreachable positions"""
        engine = SoccerEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Move ball to top-left corner
        state["ball_position"] = {"x": 0, "y": 0}
        
        # Try to move northwest (out of bounds but adjacent)
        result = engine.validate_move(state, 1, {"to_x": -1, "to_y": -1})
        
        assert result.valid is False
        assert "outside the playable area" in result.error_message or "adjacent node" in result.error_message
        
    def test_edge_move_from_goal_start_boundary(self):
        """Test edge moves from goal start boundary position"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # Position at goal_start_x boundary
        position = {"x": 3, "y": 0}  # goal_start_x = 3
        target = {"x": 4, "y": 0}
        
        # Moving right from goal start should be allowed
        assert engine._edge_move_allowed(position, (1, 0), target) is True
        
    def test_edge_move_from_goal_end_boundary(self):
        """Test edge moves from goal end boundary position"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # Position at goal_end_x boundary  
        position = {"x": 5, "y": 0}  # goal_end_x = 5
        target = {"x": 4, "y": 0}
        
        # Moving left from goal end should be allowed
        assert engine._edge_move_allowed(position, (-1, 0), target) is True
        
    def test_edge_move_scoring_into_goal(self):
        """Test that moving into goal from goal entrance is allowed"""
        engine = SoccerEngine("TEST123", [1, 2])
        
        # At goal entrance, moving into goal
        position = {"x": 4, "y": 0}
        target = {"x": 4, "y": -1}  # Into top goal
        
        # This should be allowed (scoring)
        assert engine._edge_move_allowed(position, (0, -1), target) is True
        
        # Test from boundary position (corner of goal opening) without target parameter
        # This hits line 270 - return True after _is_goal_node check
        position_at_boundary = {"x": 3, "y": 0}  # Left edge of goal opening
        assert engine._edge_move_allowed(position_at_boundary, (0, -1)) is True
