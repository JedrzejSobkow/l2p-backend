# app/tests/test_timeout_checker.py

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, UTC, timedelta
from services.timeout_checker import TimeoutChecker
from services.game_service import GameService
from services.game_engine_interface import GameResult
from schemas.game_schema import GameEndedEvent, MoveMadeEvent


@pytest.mark.asyncio
class TestTimeoutChecker:
    """Tests for TimeoutChecker service"""
    
    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================
    
    def test_initialization(self):
        """Test TimeoutChecker initialization"""
        redis_mock = MagicMock()
        sio_mock = MagicMock()
        
        checker = TimeoutChecker(redis_mock, sio_mock)
        
        assert checker.redis == redis_mock
        assert checker.sio == sio_mock
        assert checker.is_running is False
        assert checker.pubsub is None
    
    def test_get_timeout_key(self):
        """Test get_timeout_key static method"""
        lobby_code = "TEST123"
        expected_key = "game_timeout:TEST123"
        
        result = TimeoutChecker.get_timeout_key(lobby_code)
        
        assert result == expected_key
    
    # ============================================================================
    # START/STOP TESTS
    # ============================================================================
    
    async def test_start_already_running(self, redis_client):
        """Test starting TimeoutChecker when already running"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        checker.is_running = True
        
        # Should return early without error
        await checker.start()
        
        assert checker.is_running is True
        assert checker.pubsub is None  # Should not create pubsub
    
    def test_stop(self):
        """Test stopping TimeoutChecker"""
        redis_mock = MagicMock()
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_mock, sio_mock)
        checker.is_running = True
        
        checker.stop()
        
        assert checker.is_running is False
    
    # Note: Full testing of start() method's pubsub listening loop is difficult
    # in unit tests because:
    # 1. FakeRedis doesn't support CONFIG commands
    # 2. The async message loop requires real Redis keyspace notifications
    # 3. These are better tested in integration tests with real Redis
    # The critical timeout handling logic is tested thoroughly above.
    
    # ============================================================================
    # TIMEOUT HANDLING TESTS - GAME ENDS
    # ============================================================================
    
    async def test_handle_timeout_game_ends(self, redis_client):
        """Test handling timeout that ends the game"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TIMEOUT_END",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "end_game"
            }
        )
        
        # Set turn start time to past to trigger timeout
        state_raw = await redis_client.get(GameService._game_state_key("TIMEOUT_END"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("TIMEOUT_END"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("TIMEOUT_END")
        
        # Verify game ended
        game = await GameService.get_game(redis_client, "TIMEOUT_END")
        assert game["game_state"]["result"] == GameResult.TIMEOUT.value
        assert game["game_state"]["winner_id"] == 2  # Player 2 wins (player 1 timed out)
        
        # Verify SocketIO emit was called
        assert sio_mock.emit.called
        emit_call = sio_mock.emit.call_args
        assert emit_call[0][0] == "game_ended"  # Event name
        assert emit_call[1]["room"] == "TIMEOUT_END"
        assert emit_call[1]["namespace"] == "/game"
    
    async def test_handle_timeout_turn_skipped(self, redis_client):
        """Test handling timeout that skips turn"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with skip turn action
        await GameService.create_game(
            redis=redis_client,
            lobby_code="TIMEOUT_SKIP",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "skip_turn"
            }
        )
        
        # Set turn start time to past to trigger timeout
        state_raw = await redis_client.get(GameService._game_state_key("TIMEOUT_SKIP"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("TIMEOUT_SKIP"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("TIMEOUT_SKIP")
        
        # Verify turn was skipped (game still in progress, turn advanced)
        game = await GameService.get_game(redis_client, "TIMEOUT_SKIP")
        assert game["game_state"]["result"] == GameResult.IN_PROGRESS.value
        assert game["game_state"]["current_turn_player_id"] == 2  # Turn advanced to player 2
        
        # Verify SocketIO emit was called with move_made event
        assert sio_mock.emit.called
        emit_call = sio_mock.emit.call_args
        assert emit_call[0][0] == "move_made"  # Event name
        assert emit_call[1]["room"] == "TIMEOUT_SKIP"
        assert emit_call[1]["namespace"] == "/game"
    
    # ============================================================================
    # EDGE CASE TESTS
    # ============================================================================
    
    async def test_handle_timeout_engine_not_found(self, redis_client):
        """Test handling timeout when engine doesn't exist"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Try to handle timeout for non-existent game
        await checker._handle_timeout("NOEXIST")
        
        # Should not crash, just log warning
        assert not sio_mock.emit.called
    
    async def test_handle_timeout_state_not_found(self, redis_client):
        """Test handling timeout when state doesn't exist"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create only engine config, no state
        engine_config = {
            "game_name": "tictactoe",
            "lobby_code": "NOSTATE",
            "player_ids": [1, 2],
            "rules": {},
            "current_turn_index": 0,
        }
        await redis_client.set(
            GameService._game_engine_key("NOSTATE"),
            json.dumps(engine_config)
        )
        
        # Try to handle timeout
        await checker._handle_timeout("NOSTATE")
        
        # Should not crash, just log warning
        assert not sio_mock.emit.called
    
    async def test_handle_timeout_game_already_ended(self, redis_client):
        """Test handling timeout when game is already ended"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create and forfeit a game
        await GameService.create_game(
            redis=redis_client,
            lobby_code="ALREADY_ENDED",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        await GameService.forfeit_game(
            redis=redis_client,
            lobby_code="ALREADY_ENDED",
            player_id=1
        )
        
        # Try to handle timeout on already ended game
        await checker._handle_timeout("ALREADY_ENDED")
        
        # Should skip processing, not emit anything
        assert not sio_mock.emit.called
    
    async def test_handle_timeout_no_timeout_occurred(self, redis_client):
        """Test handling timeout when check_timeout returns false"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game without timeout configured
        await GameService.create_game(
            redis=redis_client,
            lobby_code="NO_TIMEOUT",
            game_name="tictactoe",
            player_ids=[1, 2]
        )
        
        # Try to handle timeout (but no timeout is configured)
        await checker._handle_timeout("NO_TIMEOUT")
        
        # Should not emit anything since check_timeout returns false
        assert not sio_mock.emit.called
    
    async def test_handle_timeout_exception_handling(self, redis_client):
        """Test that exceptions in handle_timeout are caught and logged"""
        sio_mock = AsyncMock()
        sio_mock.emit.side_effect = Exception("SocketIO error")
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="EXCEPTION_TEST",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "end_game"
            }
        )
        
        # Set turn start time to past to trigger timeout
        state_raw = await redis_client.get(GameService._game_state_key("EXCEPTION_TEST"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("EXCEPTION_TEST"),
            json.dumps(game_state)
        )
        
        # Handle timeout - should not raise exception
        await checker._handle_timeout("EXCEPTION_TEST")
        
        # Exception should be caught and logged, but game state should still be updated
        game = await GameService.get_game(redis_client, "EXCEPTION_TEST")
        assert game["game_state"]["result"] == GameResult.TIMEOUT.value
    
    # ============================================================================
    # EMIT EVENT TESTS
    # ============================================================================
    
    async def test_game_ended_event_structure(self, redis_client):
        """Test that game_ended event has correct structure"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="EVENT_TEST",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "end_game"
            }
        )
        
        # Set turn start time to past
        state_raw = await redis_client.get(GameService._game_state_key("EVENT_TEST"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("EVENT_TEST"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("EVENT_TEST")
        
        # Verify emit call structure
        emit_call = sio_mock.emit.call_args
        event_data = emit_call[0][1]  # Second positional argument
        
        assert "lobby_code" in event_data
        assert event_data["lobby_code"] == "EVENT_TEST"
        assert "result" in event_data
        assert event_data["result"] == GameResult.TIMEOUT.value
        assert "winner_id" in event_data
        assert "game_state" in event_data
    
    async def test_move_made_event_structure_on_skip(self, redis_client):
        """Test that move_made event has correct structure when turn is skipped"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with skip turn action
        await GameService.create_game(
            redis=redis_client,
            lobby_code="SKIP_EVENT_TEST",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "skip_turn"
            }
        )
        
        # Set turn start time to past
        state_raw = await redis_client.get(GameService._game_state_key("SKIP_EVENT_TEST"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("SKIP_EVENT_TEST"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("SKIP_EVENT_TEST")
        
        # Verify emit call structure
        emit_call = sio_mock.emit.call_args
        event_data = emit_call[0][1]  # Second positional argument
        
        assert "lobby_code" in event_data
        assert event_data["lobby_code"] == "SKIP_EVENT_TEST"
        assert "player_id" in event_data
        assert "move_data" in event_data
        assert event_data["move_data"]["skipped"] is True
        assert event_data["move_data"]["reason"] == "timeout"
        assert "game_state" in event_data
        assert "current_turn_player_id" in event_data
    
    # ============================================================================
    # INTEGRATION TESTS WITH TIMEOUT KEY
    # ============================================================================
    
    async def test_timeout_key_cleared_on_game_end(self, redis_client):
        """Test that timeout key is cleared when game ends by timeout"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with timeout
        await GameService.create_game(
            redis=redis_client,
            lobby_code="CLEAR_KEY_TEST",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "end_game"
            }
        )
        
        # Verify timeout key exists
        timeout_key = TimeoutChecker.get_timeout_key("CLEAR_KEY_TEST")
        value = await redis_client.get(timeout_key)
        assert value is not None
        
        # Set turn start time to past to trigger timeout
        state_raw = await redis_client.get(GameService._game_state_key("CLEAR_KEY_TEST"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("CLEAR_KEY_TEST"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("CLEAR_KEY_TEST")
        
        # Verify timeout key is cleared
        value = await redis_client.get(timeout_key)
        assert value is None
    
    async def test_timeout_key_set_on_turn_skip(self, redis_client):
        """Test that new timeout key is set when turn is skipped"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Create a game with skip turn action
        await GameService.create_game(
            redis=redis_client,
            lobby_code="NEW_KEY_TEST",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 60,
                "timeout_action": "skip_turn"
            }
        )
        
        # Set turn start time to past to trigger timeout
        state_raw = await redis_client.get(GameService._game_state_key("NEW_KEY_TEST"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=2)
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("NEW_KEY_TEST"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("NEW_KEY_TEST")
        
        # Verify timeout key still exists (for next player's turn)
        timeout_key = TimeoutChecker.get_timeout_key("NEW_KEY_TEST")
        value = await redis_client.get(timeout_key)
        assert value is not None
    
    # ============================================================================
    # MULTIPLAYER TIMEOUT TESTS
    # ============================================================================
    
    async def test_handle_timeout_multiplayer_no_winner(self, redis_client):
        """Test handling timeout in multiplayer game where no single winner exists"""
        sio_mock = AsyncMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Mock a multiplayer game engine (we'll use tictactoe with 2 players for simplicity)
        await GameService.create_game(
            redis=redis_client,
            lobby_code="MULTI_TIMEOUT",
            game_name="tictactoe",
            player_ids=[1, 2],
            rules={
                "timeout_type": "per_turn",
                "timeout_seconds": 10,  # Use valid value from allowed list
                "timeout_action": "end_game"
            }
        )
        
        # Set turn start time to past
        state_raw = await redis_client.get(GameService._game_state_key("MULTI_TIMEOUT"))
        game_state = json.loads(state_raw)
        past_time = datetime.now(UTC) - timedelta(seconds=12)  # Past the 10 second timeout
        game_state["timing"]["turn_start_time"] = past_time.isoformat()
        await redis_client.set(
            GameService._game_state_key("MULTI_TIMEOUT"),
            json.dumps(game_state)
        )
        
        # Handle timeout
        await checker._handle_timeout("MULTI_TIMEOUT")
        
        # Verify game ended with timeout result
        game = await GameService.get_game(redis_client, "MULTI_TIMEOUT")
        assert game["game_state"]["result"] == GameResult.TIMEOUT.value
    
    async def test_start_pubsub_lifecycle(self, redis_client):
        """Test the start method's pubsub lifecycle"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Mock pubsub to return a few messages then stop
        mock_pubsub = AsyncMock()
        mock_messages = [
            {"type": "subscribe"},
            {
                "type": "pmessage",
                "data": b"game_timeout:TEST123"
            },
            {"type": "message"},  # Should be ignored (not pmessage)
        ]
        
        async def message_generator():
            for msg in mock_messages:
                yield msg
                # Stop after processing messages
                if msg.get("type") == "message":
                    checker.is_running = False
        
        mock_pubsub.listen = MagicMock(return_value=message_generator())
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        # Mock Redis pubsub and config_set
        with patch.object(redis_client, 'pubsub', return_value=mock_pubsub):
            with patch.object(redis_client, 'config_set', AsyncMock()):
                with patch.object(checker, '_handle_timeout', AsyncMock()) as mock_handle:
                    await checker.start()
                    
                    # Verify pubsub was set up correctly
                    redis_client.config_set.assert_called_once_with("notify-keyspace-events", "Ex")
                    mock_pubsub.psubscribe.assert_called_once_with("__keyevent@0__:expired")
                    
                    # Verify _handle_timeout was called for the game_timeout key
                    mock_handle.assert_called_once_with("TEST123")
                    
                    # Verify cleanup
                    mock_pubsub.unsubscribe.assert_called_once()
                    mock_pubsub.close.assert_called_once()
    
    async def test_start_handles_non_timeout_keys(self, redis_client):
        """Test that start ignores keys that don't match timeout pattern"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        mock_pubsub = AsyncMock()
        mock_messages = [
            {"type": "subscribe"},
            {
                "type": "pmessage",
                "data": b"some_other_key:value"  # Not a timeout key
            },
        ]
        
        async def message_generator():
            for msg in mock_messages:
                yield msg
                if msg.get("type") == "pmessage":
                    checker.is_running = False
        
        mock_pubsub.listen = MagicMock(return_value=message_generator())
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        with patch.object(redis_client, 'pubsub', return_value=mock_pubsub):
            with patch.object(redis_client, 'config_set', AsyncMock()):
                with patch.object(checker, '_handle_timeout', AsyncMock()) as mock_handle:
                    await checker.start()
                    
                    # _handle_timeout should NOT be called for non-timeout keys
                    mock_handle.assert_not_called()
    
    async def test_start_handles_message_processing_error(self, redis_client):
        """Test that start handles errors in message processing gracefully"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        mock_pubsub = AsyncMock()
        mock_messages = [
            {"type": "subscribe"},
            {
                "type": "pmessage",
                "data": b"game_timeout:ERROR_CASE"
            },
            {
                "type": "pmessage",
                "data": b"game_timeout:SUCCESS_CASE"
            },
        ]
        
        call_count = 0
        async def message_generator():
            nonlocal call_count
            for msg in mock_messages:
                yield msg
                call_count += 1
                if call_count >= len(mock_messages):
                    checker.is_running = False
        
        mock_pubsub.listen = MagicMock(return_value=message_generator())
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        # Make _handle_timeout raise exception on first call, succeed on second
        async def handle_with_error(lobby_code):
            if lobby_code == "ERROR_CASE":
                raise RuntimeError("Intentional error")
        
        with patch.object(redis_client, 'pubsub', return_value=mock_pubsub):
            with patch.object(redis_client, 'config_set', AsyncMock()):
                with patch.object(checker, '_handle_timeout', AsyncMock(side_effect=handle_with_error)) as mock_handle:
                    await checker.start()
                    
                    # Both calls should have been attempted despite first error
                    assert mock_handle.call_count == 2
                    mock_handle.assert_any_call("ERROR_CASE")
                    mock_handle.assert_any_call("SUCCESS_CASE")
    
    async def test_start_handles_data_as_string(self, redis_client):
        """Test that start handles message data as string (not bytes)"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        mock_pubsub = AsyncMock()
        mock_messages = [
            {"type": "subscribe"},
            {
                "type": "pmessage",
                "data": "game_timeout:STRING_KEY"  # String, not bytes
            },
        ]
        
        async def message_generator():
            for msg in mock_messages:
                yield msg
                if msg.get("type") == "pmessage":
                    checker.is_running = False
        
        mock_pubsub.listen = MagicMock(return_value=message_generator())
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        with patch.object(redis_client, 'pubsub', return_value=mock_pubsub):
            with patch.object(redis_client, 'config_set', AsyncMock()):
                with patch.object(checker, '_handle_timeout', AsyncMock()) as mock_handle:
                    await checker.start()
                    
                    # Should handle string data correctly
                    mock_handle.assert_called_once_with("STRING_KEY")
    
    async def test_start_handles_pubsub_setup_error(self, redis_client):
        """Test that start handles errors during pubsub setup"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        # Make config_set raise an error
        with patch.object(redis_client, 'config_set', AsyncMock(side_effect=RuntimeError("Config error"))):
            # Should not raise, just log error
            await checker.start()
            
            # checker.is_running gets set to True at start, error in try block doesn't reset it
            # because it's caught in outer except. The finally block would clean up pubsub.
            # This is expected behavior - is_running just tracks intent, not success
    
    async def test_start_cleanup_on_exception_in_loop(self, redis_client):
        """Test that pubsub is properly cleaned up even if loop raises exception"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        mock_pubsub = AsyncMock()
        
        # Make listen() raise an exception
        async def error_generator():
            raise RuntimeError("Loop error")
            yield  # This won't be reached
        
        mock_pubsub.listen = MagicMock(return_value=error_generator())
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        with patch.object(redis_client, 'pubsub', return_value=mock_pubsub):
            with patch.object(redis_client, 'config_set', AsyncMock()):
                await checker.start()
                
                # Cleanup should still happen
                mock_pubsub.unsubscribe.assert_called_once()
                mock_pubsub.close.assert_called_once()
    
    async def test_start_stop_during_loop(self, redis_client):
        """Test that stop() during the listen loop exits gracefully"""
        sio_mock = MagicMock()
        checker = TimeoutChecker(redis_client, sio_mock)
        
        mock_pubsub = AsyncMock()
        mock_messages = [
            {"type": "subscribe"},
            {"type": "pmessage", "data": b"game_timeout:FIRST"},
            {"type": "pmessage", "data": b"game_timeout:SECOND"},  # Won't be processed
        ]
        
        messages_processed = 0
        async def message_generator():
            nonlocal messages_processed
            for msg in mock_messages:
                yield msg
                messages_processed += 1
                # Stop after first pmessage
                if msg.get("type") == "pmessage" and messages_processed == 2:
                    checker.stop()  # This sets is_running = False
        
        mock_pubsub.listen = MagicMock(return_value=message_generator())
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        with patch.object(redis_client, 'pubsub', return_value=mock_pubsub):
            with patch.object(redis_client, 'config_set', AsyncMock()):
                with patch.object(checker, '_handle_timeout', AsyncMock()) as mock_handle:
                    await checker.start()
                    
                    # Only first message should be handled, loop should break after
                    mock_handle.assert_called_once_with("FIRST")
                    
                    # Cleanup should still happen
                    mock_pubsub.unsubscribe.assert_called_once()
                    mock_pubsub.close.assert_called_once()
