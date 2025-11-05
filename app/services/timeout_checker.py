# app/services/timeout_checker.py

import asyncio
import json
import logging
from redis.asyncio import Redis
from services.game_service import GameService
from services.game_engine_interface import GameResult
from schemas.game_schema import GameEndedEvent

logger = logging.getLogger(__name__)


class TimeoutChecker:
    """
    Redis keyspace notification-based timeout checker.
    Listens for expired timeout keys and triggers game end when they expire.
    """
    
    TIMEOUT_KEY_PREFIX = "game_timeout:"
    
    def __init__(self, redis: Redis, socketio_manager):
        self.redis = redis
        self.sio = socketio_manager
        self.is_running = False
        self.pubsub = None
        
    async def start(self):
        """Start listening for Redis keyspace notifications"""
        if self.is_running:
            logger.warning("TimeoutChecker is already running")
            return
            
        self.is_running = True
        logger.info("TimeoutChecker started - listening for Redis key expirations")
        
        try:
            # Enable keyspace notifications for expired events
            await self.redis.config_set("notify-keyspace-events", "Ex")
            
            # Subscribe to expired key events
            self.pubsub = self.redis.pubsub()
            await self.pubsub.psubscribe(f"__keyevent@0__:expired")
            
            # Listen for expired keys
            async for message in self.pubsub.listen():
                if not self.is_running:
                    break
                    
                try:
                    if message and message["type"] == "pmessage":
                        expired_key = message["data"].decode() if isinstance(message["data"], bytes) else message["data"]
                        
                        # Check if it's a game timeout key
                        if expired_key.startswith(self.TIMEOUT_KEY_PREFIX):
                            lobby_code = expired_key.replace(self.TIMEOUT_KEY_PREFIX, "")
                            await self._handle_timeout(lobby_code)
                            
                except Exception as e:
                    logger.error(f"Error processing expired key message: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error in timeout checker: {e}", exc_info=True)
        finally:
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()
    
    def stop(self):
        """Stop the timeout checker"""
        self.is_running = False
        logger.info("TimeoutChecker stopped")
    
    async def _handle_timeout(self, lobby_code: str):
        """Handle a game timeout when the Redis key expires"""
        try:
            logger.info(f"Timeout key expired for lobby {lobby_code}")
            
            # Load game state and engine
            engine = await GameService._load_engine(self.redis, lobby_code)
            if not engine:
                logger.warning(f"Engine not found for lobby {lobby_code}")
                return
            
            state_raw = await self.redis.get(GameService._game_state_key(lobby_code))
            if not state_raw:
                logger.warning(f"Game state not found for lobby {lobby_code}")
                return
            
            game_state = json.loads(state_raw)
            
            # Skip if game is already ended
            if game_state.get("result") != "in_progress":
                logger.info(f"Game in lobby {lobby_code} already ended")
                return
            
            # Check for timeout (should be true since key expired)
            timeout_occurred, winner_id = engine.check_timeout(game_state)
            
            if timeout_occurred:
                # Check if game ends or turn is skipped
                if winner_id is not None or engine.game_result != GameResult.IN_PROGRESS:
                    # Game ended by timeout
                    logger.info(f"Processing timeout for lobby {lobby_code}. Winner: {winner_id}")
                    
                    # Update game state
                    game_state["result"] = GameResult.TIMEOUT.value
                    game_state["winner_id"] = winner_id
                    
                    # Save to Redis
                    await self.redis.set(
                        GameService._game_state_key(lobby_code),
                        json.dumps(game_state),
                        ex=GameService.GAME_TTL
                    )
                    
                    # Clear timeout key
                    await GameService._clear_timeout_key(self.redis, lobby_code)
                    
                    # Broadcast game ended event to all players in the room
                    end_event = GameEndedEvent(
                        lobby_code=lobby_code,
                        result=GameResult.TIMEOUT.value,
                        winner_id=winner_id,
                        game_state=game_state
                    )
                    
                    # Emit to the /game namespace, to the specific lobby room
                    await self.sio.emit(
                        "game_ended",
                        end_event.dict(),
                        room=lobby_code,
                        namespace="/game"
                    )
                    
                    logger.info(f"Broadcasted timeout event for lobby {lobby_code}")
                else:
                    # Turn is skipped, game continues
                    logger.info(f"Turn skipped due to timeout in lobby {lobby_code}")
                    
                    # Consume time and advance turn
                    game_state = engine.consume_turn_time(game_state)
                    engine.advance_turn()
                    game_state["current_turn_player_id"] = engine.current_player_id
                    game_state = engine.start_turn(game_state)
                    
                    # Save updated state
                    await self.redis.set(
                        GameService._game_state_key(lobby_code),
                        json.dumps(game_state),
                        ex=GameService.GAME_TTL
                    )
                    await GameService._save_engine(self.redis, engine)
                    
                    # Set new timeout key for next player
                    await GameService._set_timeout_key(self.redis, engine, game_state, lobby_code)
                    
                    # Broadcast turn skipped event
                    from schemas.game_schema import MoveMadeEvent
                    skip_event = MoveMadeEvent(
                        lobby_code=lobby_code,
                        player_id=engine.player_ids[engine.current_turn_index - 1],  # Previous player who timed out
                        move_data={"skipped": True, "reason": "timeout"},
                        game_state=game_state,
                        current_turn_player_id=engine.current_player_id
                    )
                    
                    await self.sio.emit(
                        "move_made",
                        skip_event.dict(),
                        room=lobby_code,
                        namespace="/game"
                    )
                    
                    logger.info(f"Broadcasted turn skip event for lobby {lobby_code}")
            else:
                logger.warning(f"Timeout key expired but check_timeout returned false for lobby {lobby_code}")
                
        except Exception as e:
            logger.error(f"Error handling timeout for lobby {lobby_code}: {e}", exc_info=True)
    
    @staticmethod
    def get_timeout_key(lobby_code: str) -> str:
        """Get the Redis key name for a lobby's timeout"""
        return f"{TimeoutChecker.TIMEOUT_KEY_PREFIX}{lobby_code}"
