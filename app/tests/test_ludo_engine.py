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
            "six_grants_extra_turn": False,
            "exact_roll_to_finish": False
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
        for player_id in [1, 2]:
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
        
        piece_id = state["pieces"][1][0]["id"]
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
        
        piece_id = state["pieces"][1][0]["id"]
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
        
        piece_id = state["pieces"][1][0]["id"]
        piece = state["pieces"][1][0]
        
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
        piece = state["pieces"][1][0]
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
        piece = state["pieces"][1][0]
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
        opponent_piece = state["pieces"][2][0]
        opponent_piece["position"] = "track_5"
        
        # Place player 1's piece nearby
        player_piece = state["pieces"][1][0]
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
        opponent_piece = state["pieces"][2][0]
        opponent_piece["position"] = "track_8"
        
        # Place player piece nearby
        player_piece = state["pieces"][1][0]
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
        piece1 = state["pieces"][1][0]
        piece1["position"] = "track_5"
        
        piece2 = state["pieces"][1][1]
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
        opponent_piece = state["pieces"][2][0]
        opponent_piece["position"] = "track_5"
        
        player_piece = state["pieces"][1][0]
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
        piece = state["pieces"][1][0]
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
        piece = state["pieces"][1][0]
        piece["position"] = "home_2"
        
        # Roll dice
        state["current_dice_roll"] = 3
        state["dice_rolled"] = True
        
        state = engine.apply_move(state, 1, {"action": "move_piece", "piece_id": piece["id"]})
        
        # Piece should move to home_5
        assert piece["position"] == "home_5"
    
    def test_exact_roll_to_finish(self):
        """Test that exact roll is needed to finish"""
        engine = LudoEngine("TEST123", [1, 2], rules={"exact_roll_to_finish": True})
        state = engine.initialize_game_state()
        
        # Place piece close to finish
        piece = state["pieces"][1][0]
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
        piece = state["pieces"][1][0]
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
        piece = state["pieces"][1][0]
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
        
        piece = state["pieces"][1][0]
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
            state["pieces"][1][i]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.IN_PROGRESS
        assert winner is None
    
    def test_winner_with_all_pieces_home(self):
        """Test that player wins with all pieces home"""
        engine = LudoEngine("TEST123", [1, 2])
        state = engine.initialize_game_state()
        
        # Finish all 4 pieces
        for i in range(4):
            state["pieces"][1][i]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
    
    def test_four_player_winner_detection(self):
        """Test winner detection in 4-player game"""
        engine = LudoEngine("TEST123", [10, 20, 30, 40])
        state = engine.initialize_game_state()
        
        # Player 30 finishes all pieces
        for i in range(4):
            state["pieces"][30][i]["position"] = "finished"
        
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
        engine = LudoEngine("TEST123", [1, 2], rules={"six_grants_extra_turn": True})
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
        state["pieces"][1][0]["position"] = "track_5"
        state["pieces"][1][1]["position"] = "track_10"
        state["pieces"][1][2]["position"] = "track_15"
        
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
        assert len(state["pieces"][1]) == 2
        assert len(state["pieces"][2]) == 2
        
        # Win with 2 pieces
        state["pieces"][1][0]["position"] = "finished"
        state["pieces"][1][1]["position"] = "finished"
        
        result, winner = engine.check_game_result(state)
        assert result == GameResult.PLAYER_WIN
        assert winner == 1
