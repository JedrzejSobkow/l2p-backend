import pytest
from services.games.checkers_engine import CheckersEngine
from services.game_engine_interface import MoveValidationResult, GameResult

@pytest.fixture
def checkers_engine():
    player_ids = [1, 2]
    rules = {
        "board_size": 8,
        "forced_capture": "Yes",  # Changed to string
        "flying_kings": "No",  # Changed to string
        "backward_capture": "Yes"  # Changed to string
    }
    return CheckersEngine("test_lobby", player_ids, rules)

def test_initialize_game_state(checkers_engine):
    game_state = checkers_engine.initialize_game_state()
    assert game_state["board"] is not None
    assert len(game_state["board"]) == 8
    assert game_state["move_count"] == 0
    assert game_state["result"] == GameResult.IN_PROGRESS.value

def test_validate_move_valid(checkers_engine):
    game_state = checkers_engine.initialize_game_state()
    move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1}
    result = checkers_engine._validate_game_specific_move(game_state, 1, move_data)
    assert result.valid  # Updated from 'is_valid' to 'valid'

def test_validate_move_invalid(checkers_engine):
    game_state = checkers_engine.initialize_game_state()
    move_data = {"from_row": 5, "from_col": 0, "to_row": 5, "to_col": 2}
    result = checkers_engine._validate_game_specific_move(game_state, 1, move_data)
    assert not result.valid  # Updated from 'is_valid' to 'valid'

def test_apply_move(checkers_engine):
    game_state = checkers_engine.initialize_game_state()
    move_data = {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1}
    updated_state = checkers_engine.apply_move(game_state, 1, move_data)
    assert updated_state["board"][5][0] is None
    assert updated_state["board"][4][1] == "w"

def test_check_game_result_in_progress(checkers_engine):
    game_state = checkers_engine.initialize_game_state()
    result, winner = checkers_engine.check_game_result(game_state)
    assert result == GameResult.IN_PROGRESS
    assert winner is None

def test_check_game_result_draw_by_repetition(checkers_engine):
    game_state = checkers_engine.initialize_game_state()
    board_hash = checkers_engine._hash_board(game_state["board"])
    game_state["position_history"] = [board_hash] * 3
    result, winner = checkers_engine.check_game_result(game_state)
    assert result == GameResult.DRAW
    assert winner is None
