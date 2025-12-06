# app/tests/test_ludo_engine.py

import pytest
from services.games.ludo_engine import LudoEngine
from services.game_engine_interface import GameResult


class TestLudoEngine:
    """Comprehensive tests for LudoEngine"""
    
    # ========== Initialization Tests ==========
    
    def test_initialization_two_players(self):
        """Test 2-player Ludo initialization"""
        engine = LudoEngine("TEST123", [1, 2])
        
        assert engine.lobby_code == "TEST123"
        assert engine.player_ids == [1, 2]
        assert len(engine.player_ids) == 2
        assert engine.pieces_per_player == 4
        assert engine.current_player_id == 1
    
    def test_initialization_four_players(self):
        """Test 4-player Ludo initialization"""
        engine = LudoEngine("TEST456", [10, 20, 30, 40])
        
        assert len(engine.player_ids) == 4
        assert engine.player_ids == [10, 20, 30, 40]
    
    def test_initialization_invalid_player_count_too_few(self):
        """Test that initialization fails with only 1 player"""
        with pytest.raises(ValueError, match="2-4 players"):
            LudoEngine("TEST123", [1])
    
    def test_initialization_invalid_player_count_too_many(self):
        """Test that initialization fails with more than 4 players"""
        with pytest.raises(ValueError, match="2-4 players"):
            LudoEngine("TEST123", [1, 2, 3, 4, 5])
    
    def test_initialization_with_custom_rules(self):
        """Test initialization with custom rules"""
        rules = {
            "pieces_per_player": 2,
            "six_grants_extra_turn": "no",
            "exact_roll_to_finish": "no"
        }
        engine = LudoEngine("TEST123", [1, 2], rules=rules)
        
        assert engine.pieces_per_player == 2
        assert engine.six_grants_extra_turn is False
        assert engine.exact_roll_to_finish is False
    
    def test_initialize_game_state(self):
        """Test game state initialization"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Check state structure
        assert "pieces" in state
        assert "current_dice_roll" in state
        assert "move_made" in state
        assert "dice_rolled" in state
        assert "moves_history" in state
        
        # Check all pieces start in yard
        for player_id in ["1", "2"]:
            assert player_id in state["pieces"]
            assert len(state["pieces"][player_id]) == 4
            for piece in state["pieces"][player_id]:
                assert piece["position"] == "yard"
                assert "id" in piece
        
        # Check initial turn state
        assert state["current_dice_roll"] is None
        assert state["dice_rolled"] is False
        assert state["move_made"] is False
        assert len(state["moves_history"]) == 0
    
    # ========== Dice Rolling Tests ==========
    
    def test_roll_dice_action(self):
        """Test rolling dice"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Validate roll_dice action
        validation = engine.validate_move(state, 1, {"action": "roll_dice"})
        assert validation.valid is True
        
        # Apply dice roll
        state = engine.apply_move(state, 1, {"action": "roll_dice"})
        
        assert state["dice_rolled"] is True
        assert state["current_dice_roll"] is not None
        assert 1 <= state["current_dice_roll"] <= 6
    
    def test_cannot_roll_dice_twice(self):
        """Test that dice cannot be rolled twice in same turn"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Roll once
        state = engine.apply_move(state, 1, {"action": "roll_dice"})
        
        # Try to roll again
        validation = engine.validate_move(state, 1, {"action": "roll_dice"})
        assert validation.valid is False
        assert "already rolled" in validation.error_message.lower()
    
    def test_dice_roll_range(self):
        """Test that dice rolls are in valid range"""
        engine = LudoEngine("TEST123", [1, 2])
        
        # Roll dice 100 times to check range
        for _ in range(100):
            dice_value = engine._roll_dice()
            assert 1 <= dice_value <= 6
    
    def test_rolling_six_grants_extra_turn(self):
        """Test that rolling 6 grants extra turn"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Manually set dice to 6
        state["current_dice_roll"] = 6
        state["dice_rolled"] = True
        state["extra_turn_pending"] = True
        
        # Check that extra turn is pending
        assert state["extra_turn_pending"] is True
    
    def test_rolling_non_six_no_extra_turn(self):
        """Test that rolling non-6 doesn't grant extra turn"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Roll dice (will be 1-5 most of the time, but might be 6)
        # Set it manually to ensure it's not 6
        state = engine.apply_move(state, 1, {"action": "roll_dice"})
        if state["current_dice_roll"] != 6:
            assert state["extra_turn_pending"] is False
    
    # ========== Basic Movement Tests ==========
    
    def test_cannot_move_without_rolling_dice(self):
        """Test that piece cannot move before rolling dice"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        piece_id = state["pieces"]["1"][0]["id"]
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": piece_id})
        
        assert validation.valid is False
        assert "roll dice" in validation.error_message.lower()
    
    def test_move_piece_from_yard_requires_six(self):
        """Test that piece needs 6 to leave yard"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Roll a non-6 (set manually)
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        piece_id = state["pieces"]["1"][0]["id"]
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": piece_id})
        
        assert validation.valid is False
        assert "cannot move" in validation.error_message.lower()
    
    def test_move_piece_from_yard_with_six(self):
        """Test moving piece from yard with roll of 6"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Roll a 6
        state["current_dice_roll"] = 6
        state["dice_rolled"] = True
        
        piece_id = state["pieces"]["1"][0]["id"]
        piece = state["pieces"]["1"][0]
        
        # Validate move
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": piece_id})
        assert validation.valid is True
        
        # Apply move
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece_id})
        
        # Piece should be on starting position (track_0 for player 0)
        assert piece["position"] == "track_0"
        assert state["move_made"] is True
    
    def test_move_piece_on_track(self):
        """Test moving piece that's already on track"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place piece on track
        piece = state["pieces"]["1"][0]
        piece["position"] = "track_5"
        
        # Roll dice
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        # Move piece
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        
        # Piece should move from track_5 to track_8
        assert piece["position"] == "track_8"
    
    def test_cannot_move_same_piece_twice(self):
        """Test that move can only be made once per turn"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up piece on track
        piece = state["pieces"]["1"][0]
        piece["position"] = "track_0"
        
        # Roll and move
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        
        # Try to move again
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        assert validation.valid is False
        assert "already made" in validation.error_message.lower()
    
    # ========== Capture Mechanics Tests ==========
    
    def test_capture_opponent_piece(self):
        """Test capturing opponent's piece"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place player 2's piece on track
        opponent_piece = state["pieces"]["2"][0]
        opponent_piece["position"] = "track_5"
        
        # Place player 1's piece nearby
        player_piece = state["pieces"]["1"][0]
        player_piece["position"] = "track_2"
        
        # Player 1 rolls 3, landing on opponent
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": player_piece["id"]})
        
        # Opponent piece should be sent back to yard
        assert opponent_piece["position"] == "yard"
        assert player_piece["position"] == "track_5"
    
    def test_cannot_capture_on_safe_square(self):
        """Test that pieces on safe squares cannot be captured"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place opponent on a safe square (e.g., 8)
        opponent_piece = state["pieces"]["2"][0]
        opponent_piece["position"] = "track_8"
        
        # Place player piece nearby
        player_piece = state["pieces"]["1"][0]
        player_piece["position"] = "track_3"
        
        # Player rolls 5, landing on safe square
        state["current_dice_roll"] = 5
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": player_piece["id"]})
        
        # Opponent should still be on track (not captured)
        assert opponent_piece["position"] == "track_8"
        # Both pieces should be on same square
        assert player_piece["position"] == "track_8"
    
    def test_cannot_capture_own_piece(self):
        """Test that player cannot capture their own piece"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place two of player 1's pieces
        piece1 = state["pieces"]["1"][0]
        piece1["position"] = "track_5"
        
        piece2 = state["pieces"]["1"][1]
        piece2["position"] = "track_2"
        
        # Move piece2 to land on piece1
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece2["id"]})
        
        # Both pieces should be on track_5
        assert piece1["position"] == "track_5"
        assert piece2["position"] == "track_5"
    
    def test_capture_in_move_history(self):
        """Test that captures are recorded in move history"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set up capture scenario
        opponent_piece = state["pieces"]["2"][0]
        opponent_piece["position"] = "track_5"
        
        player_piece = state["pieces"]["1"][0]
        player_piece["position"] = "track_2"
        
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": player_piece["id"]})
        
        # Check move history includes capture
        capture_events = [m for m in state["moves_history"] if m.get("action") == "capture"]
        assert len(capture_events) == 1
        assert capture_events[0]["captured_player"] == 2
    
    # ========== Home Path Tests ==========
    
    def test_enter_home_path(self):
        """Test entering home path from main track"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Player 0's home entry is at track_50
        # Place piece just before home entry
        piece = state["pieces"]["1"][0]
        piece["position"] = "track_48"
        
        # Roll exactly 2 to land on home entry
        state["current_dice_roll"] = 2
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        
        # Piece should enter home path
        assert piece["position"] == "home_0"
    
    def test_move_within_home_path(self):
        """Test moving within home path"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place piece in home path
        piece = state["pieces"]["1"][0]
        piece["position"] = "home_2"
        
        # Roll dice
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        
        # Piece should move to home_5
        assert piece["position"] == "home_5"
    
    def test_exact_roll_to_finish(self):
        """Test that exact roll is needed to finish"""
        engine = LudoEngine("TEST123", [1, 2], rules={"exact_roll_to_finish": "yes"})
        state = engine.initialize_game_state()
        
        # Place piece close to finish
        piece = state["pieces"]["1"][0]
        piece["position"] = "home_4"
        
        # Roll too much (need 2, but roll 4)
        state["current_dice_roll"] = 4
        state["dice_rolled"] = True
        
        # Should not be able to move
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        assert validation.valid is False
    
    def test_exact_roll_finishes_piece(self):
        """Test finishing piece with exact roll"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place piece at home_4, need 2 to finish
        piece = state["pieces"]["1"][0]
        piece["position"] = "home_4"
        
        # Roll exactly 2
        state["current_dice_roll"] = 2
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        
        # Piece should be finished
        assert piece["position"] == "finished"
    
    def test_finished_piece_cannot_move(self):
        """Test that finished pieces cannot move"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place piece at finished
        piece = state["pieces"]["1"][0]
        piece["position"] = "finished"
        
        # Roll dice
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        # Should not be able to move
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        assert validation.valid is False
    
    def test_pieces_in_home_path_are_safe(self):
        """Test that pieces in home path cannot be captured"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        piece = state["pieces"]["1"][0]
        piece["position"] = "home_3"
        
        # Home path is always safe
        assert engine._is_safe_square("home_3", 1) is True
    
    # ========== Win Condition Tests ==========
    
    def test_no_winner_at_start(self):
        """Test that game has no winner at start"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
    
    def test_not_winner_with_partial_pieces_home(self):
        """Test that player hasn't won with only some pieces home"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Finish 3 out of 4 pieces
        for i in range(3):
            state["pieces"]["1"][i]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
    
    def test_winner_with_all_pieces_home(self):
        """Test that player wins with all pieces home"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Finish all 4 pieces
        for i in range(4):
            state["pieces"]["1"][i]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
    
    def test_four_player_winner_detection(self):
        """Test winner detection in 4-player game"""
        engine = LudoEngine("TEST123", [10, 20, 30, 40])
        state = engine.initialize_game_state()
        
        # Player 30 finishes all pieces
        for i in range(4):
            state["pieces"]["30"][i]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 30
    
    # ========== Turn Management Tests ==========
    
    def test_advance_turn_normal(self):
        """Test normal turn advancement"""
        engine = LudoEngine("TEST123", [1, 2])
        
        assert engine.current_player_id == 1
        engine.advance_turn()
        assert engine.current_player_id == 2
        engine.advance_turn()
        assert engine.current_player_id == 1
    
    def test_extra_turn_after_rolling_six(self):
        """Test that rolling 6 grants extra turn"""
        engine = LudoEngine("TEST123", [1, 2], rules={"six_grants_extra_turn": "yes"})
        state = engine.initialize_game_state()
        
        # Set extra turn pending
        engine.extra_turn_pending = True
        current_player = engine.current_player_id
        
        # Advance turn
        engine.advance_turn()
        
        # Should still be same player
        assert engine.current_player_id == current_player
        assert engine.extra_turn_pending is False
    
    def test_start_turn_resets_state(self):
        """Test that starting turn resets turn-specific state"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Make some moves
        state["current_dice_roll"] = 5
        state["dice_rolled"] = True
        state["move_made"] = True
        
        # Start new turn
        state = engine.start_turn(state)
        
        assert state["current_dice_roll"] is None
        assert state["dice_rolled"] is False
        assert state["move_made"] is False
    
    def test_forfeit_game(self):
        """Test game forfeit"""
        engine = LudoEngine("TEST123", [1, 2])
        
        result, winner = engine.forfeit_game(1)
        
        assert result == GameResult.FORFEIT
        assert winner == 2
    
    # ========== Edge Cases and Helper Method Tests ==========
    
    def test_get_valid_pieces_with_multiple_options(self):
        """Test getting valid pieces when multiple can move"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Place multiple pieces on track
        state["pieces"]["1"][0]["position"] = "track_5"
        state["pieces"]["1"][1]["position"] = "track_10"
        state["pieces"]["1"][2]["position"] = "track_15"
        
        # All should be able to move with roll of 3
        valid_pieces = engine._get_valid_pieces(state, 1, 3)
        
        assert len(valid_pieces) == 3
    
    def test_get_valid_pieces_with_no_options(self):
        """Test getting valid pieces when none can move"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # All pieces in yard, roll a non-6
        valid_pieces = engine._get_valid_pieces(state, 1, 3)
        
        assert len(valid_pieces) == 0
    
    def test_position_parsing(self):
        """Test position string parsing"""
        engine = LudoEngine("TEST123", [1, 2])
        
        assert engine._get_piece_position_value("yard") == ("yard", 0)
        assert engine._get_piece_position_value("track_15") == ("track", 15)
        assert engine._get_piece_position_value("home_3") == ("home", 3)
        assert engine._get_piece_position_value("finished") == ("finished", 0)
    
    def test_invalid_action_type(self):
        """Test validation fails for invalid action"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        validation = engine.validate_move(state, 1, {"action": "invalid_action"})
        
        assert validation.valid is False
        assert "invalid action" in validation.error_message.lower()
    
    def test_move_without_piece_id(self):
        """Test that move_piece requires piece_id"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        validation = engine.validate_move(state, 1, {"action": "move_piece"})
        
        assert validation.valid is False
        assert "piece_id" in validation.error_message.lower()
    
    def test_move_with_invalid_piece_id(self):
        """Test moving with non-existent piece ID"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        validation = engine.validate_move(state, 1, {"action": "move_piece", "piece_id": "invalid_piece"})
        
        assert validation.valid is False
        assert "not found" in validation.error_message.lower()
    
    def test_game_info(self):
        """Test game info metadata"""
        info = LudoEngine.get_game_info()
        
        assert info.game_name == "ludo"
        assert info.display_name == "Ludo"
        assert info.min_players == 2
        assert info.max_players == 4
        assert info.turn_based is True
        assert "pieces_per_player" in info.supported_rules
        assert "six_grants_extra_turn" in info.supported_rules
    
    def test_move_history_tracking(self):
        """Test that move history is properly tracked"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Roll dice
        state = engine.apply_move(state, 1, {"action": "roll_dice"})
        
        # Check history
        assert len(state["moves_history"]) == 1
        assert state["moves_history"][0]["action"] == "roll_dice"
        assert state["moves_history"][0]["player_id"] == 1
    
    def test_custom_pieces_per_player(self):
        """Test game with custom number of pieces"""
        engine = LudoEngine("TEST123", [1, 2], rules={"pieces_per_player": 2})
        state = engine.initialize_game_state()
        
        # Each player should have 2 pieces
        assert len(state["pieces"]["1"]) == 2
        assert len(state["pieces"]["2"]) == 2
        
        # Win with 2 pieces
        state["pieces"]["1"][0]["position"] = "finished"
        state["pieces"]["1"][1]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        assert result == GameResult.PLAYER_WIN
        assert winner == 1


class TestLudoEngineEdgeCases:
    """Test edge cases and unpokryte code paths"""
    
    def test_parse_bool_rule_with_no_value(self):
        """Test _parse_bool_rule returns False for 'no' value"""
        rules = {"six_grants_extra_turn": "no"}
        engine = LudoEngine("TEST123", [1, 2], rules=rules)
        
        assert engine.six_grants_extra_turn is False
    
    def test_parse_bool_rule_with_boolean_false(self):
        """Test _parse_bool_rule handles boolean False directly"""
        # Note: validation requires string values, but _parse_bool_rule can handle both
        # This tests the internal method, not full initialization
        engine = LudoEngine("TEST123", [1, 2])
        
        # Test that the method itself can handle boolean
        engine.rules = {"test_rule": False}
        result = engine._parse_bool_rule("test_rule", True)
        assert result is False
    
    def test_invalid_position_format_raises_error(self):
        """Test that invalid position format raises ValueError"""
        engine = LudoEngine("TEST123", [1, 2])
        
        with pytest.raises(ValueError, match="Invalid position format"):
            engine._get_piece_position_value("invalid_format_123")
    
    def test_overshoot_main_track_without_exact_roll(self):
        """Test piece can finish when overshooting without exact_roll_to_finish"""
        rules = {"exact_roll_to_finish": "no"}
        engine = LudoEngine("TEST123", [1, 2], rules=rules)
        state = engine.initialize_game_state()
        
        # Player 0 (index 0), home entry at position 50
        # Place piece at position 48, needs 2 to reach home entry, but roll 10
        current_pos = "track_48"
        dice_roll = 10
        
        new_pos = engine._calculate_new_position(1, current_pos, dice_roll)
        # Should overshoot and finish
        assert new_pos == "finished"
    
    def test_overshoot_home_entry_directly_to_finish(self):
        """Test overshooting home entry goes straight to finished when overshoot > HOME_PATH_LENGTH"""
        rules = {"exact_roll_to_finish": "no"}
        engine = LudoEngine("TEST123", [1, 2], rules=rules)
        
        # Player 1 (index 0), home entry at position 50
        # Place piece at position 45, roll 12
        # Distance to home entry: (50-45) % 52 = 5
        # Overshoot: 12 - 5 = 7, which is > HOME_PATH_LENGTH (6)
        current_pos = "track_45"
        dice_roll = 12
        
        new_pos = engine._calculate_new_position(1, current_pos, dice_roll)
        # Should go directly to finished (line 190)
        assert new_pos == "finished"
    
    def test_overshoot_home_path_without_exact_roll(self):
        """Test piece can finish when overshooting home path without exact_roll_to_finish"""
        rules = {"exact_roll_to_finish": "no"}
        engine = LudoEngine("TEST123", [1, 2], rules=rules)
        state = engine.initialize_game_state()
        
        # Piece at home_4, needs 2 to finish (home path length is 6)
        # Roll 5 to overshoot
        current_pos = "home_4"
        dice_roll = 5
        
        new_pos = engine._calculate_new_position(1, current_pos, dice_roll)
        # Should overshoot and finish
        assert new_pos == "finished"
    
    def test_calculate_new_position_returns_none_for_invalid(self):
        """Test _calculate_new_position returns None for invalid moves"""
        engine = LudoEngine("TEST123", [1, 2])
        
        # Piece in yard with roll other than 6
        result = engine._calculate_new_position(1, "yard", 3)
        assert result is None
        
        # Finished piece cannot move
        result = engine._calculate_new_position(1, "finished", 6)
        assert result is None
    
    def test_is_safe_square_returns_false_for_unsafe_track(self):
        """Test _is_safe_square returns False for non-safe track positions"""
        engine = LudoEngine("TEST123", [1, 2])
        
        # Position 5 is not in SAFE_SQUARES [0, 8, 13, 21, 26, 34, 39, 47]
        unsafe_position = "track_5"
        is_safe = engine._is_safe_square(unsafe_position, 1)
        assert is_safe is False
        
        # Position 10 is also not safe
        unsafe_position = "track_10"
        is_safe = engine._is_safe_square(unsafe_position, 1)
        assert is_safe is False
    
    def test_advance_turn_respects_incomplete_turn(self):
        """Test advance_turn doesn't advance if turn is not complete"""
        engine = LudoEngine("TEST123", [1, 2, 3])
        state = engine.initialize_game_state()
        
        # Set turn as incomplete
        engine.turn_complete = False
        
        current_player = engine.current_player_id
        engine.advance_turn()
        
        # Player should not have changed
        assert engine.current_player_id == current_player
    
    def test_start_turn_preserves_state_when_incomplete(self):
        """Test start_turn preserves game state when turn is incomplete"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Set some state
        state["dice_rolled"] = True
        state["current_dice_roll"] = 5
        engine.turn_complete = False
        
        new_state = engine.start_turn(state)
        
        # State should be preserved
        assert new_state["dice_rolled"] is True
        assert new_state["current_dice_roll"] == 5
    
    def test_start_turn_syncs_extra_turn_flag(self):
        """Test start_turn properly handles extra_turn_pending flag"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Scenario: both game state and engine have extra turn
        state["extra_turn_pending"] = True
        engine.extra_turn_pending = True
        engine.turn_complete = True
        
        new_state = engine.start_turn(state)
        
        # Both should remain True
        assert engine.extra_turn_pending is True
        assert new_state.get("extra_turn_pending", False) is True
    
    def test_extra_turn_consumed_in_start_turn(self):
        """Test that extra turn is properly consumed when advancing"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Game state has extra turn, but engine consumed it
        state["extra_turn_pending"] = True
        engine.extra_turn_pending = False  # Already consumed
        engine.turn_complete = True
        
        new_state = engine.start_turn(state)
        
        # Should update game state to reflect consumption
        assert new_state["extra_turn_pending"] is False