# app/services/game_service.py

import json
from typing import Dict, Any, Optional, List, Type
from datetime import datetime, UTC
from redis.asyncio import Redis
from services.game_engine_interface import (
    GameEngineInterface,
    GameResult,
    MoveValidationResult,
)
from services.games import GAME_ENGINES
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
import logging

logger = logging.getLogger(__name__)


class GameService:
    """Service for managing game state and logic using Redis"""
    
    # Redis key patterns
    GAME_STATE_KEY_PREFIX = "game_state:"
    GAME_ENGINE_KEY_PREFIX = "game_engine:"
    LOBBY_GAME_KEY_PREFIX = "lobby_game:"
    GAME_TTL = 3600 * 2  # 2 hours TTL for games
    
    # Registry of available game engines
    GAME_ENGINES = GAME_ENGINES
    
    @staticmethod
    def _game_state_key(lobby_code: str) -> str:
        """Get Redis key for game state"""
        return f"{GameService.GAME_STATE_KEY_PREFIX}{lobby_code}"
    
    @staticmethod
    def _game_engine_key(lobby_code: str) -> str:
        """Get Redis key for game engine configuration"""
        return f"{GameService.GAME_ENGINE_KEY_PREFIX}{lobby_code}"
    
    @staticmethod
    def _lobby_game_key(lobby_code: str) -> str:
        """Get Redis key for lobby-game mapping"""
        return f"{GameService.LOBBY_GAME_KEY_PREFIX}{lobby_code}"
    
    @staticmethod
    def get_available_games() -> List[str]:
        """Get list of available game types"""
        return list(GameService.GAME_ENGINES.keys())
    
    @staticmethod
    async def create_game(
        redis: Redis,
        lobby_code: str,
        game_name: str,
        identifiers: List[str],
        rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new game instance bound to a lobby.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code this game is bound to
            game_name: Name of the game type (e.g., 'tictactoe')
            identifiers: List of player identifiers participating (e.g., ['user:123', 'guest:uuid'])
            rules: Optional custom rules for the game
            
        Returns:
            Dictionary with game initialization details
            
        Raises:
            BadRequestException: If game already exists for lobby or invalid game name
        """
        # Check if game already exists for this lobby
        existing_game = await redis.exists(GameService._game_state_key(lobby_code))
        if existing_game:
            # Check if existing game is finished
            state_raw = await redis.get(GameService._game_state_key(lobby_code))
            if state_raw:
                state_data = json.loads(state_raw)
                game_result = state_data.get("result")
                
                # If game is still in progress, don't allow creating a new one
                if game_result == GameResult.IN_PROGRESS.value:
                    raise BadRequestException(
                        message="A game is already in progress for this lobby",
                        details={"lobby_code": lobby_code}
                    )
                
                # If game is finished, delete it to make room for new game
                logger.info(f"Deleting finished game (result: {game_result}) to create new game for lobby {lobby_code}")
                await GameService.delete_game(redis, lobby_code)
        
        # Validate game name
        if game_name not in GameService.GAME_ENGINES:
            raise BadRequestException(
                message=f"Unknown game type: {game_name}",
                details={
                    "available_games": GameService.get_available_games(),
                    "requested_game": game_name
                }
            )
        
        # Create game engine instance
        engine_class = GameService.GAME_ENGINES[game_name]
        try:
            engine = engine_class(lobby_code, identifiers, rules)
        except ValueError as e:
            raise BadRequestException(
                message=f"Failed to create game: {str(e)}",
                details={"game_name": game_name, "identifiers": identifiers}
            )
        
        # Initialize game state
        game_state = engine.initialize_game_state()
        
        # Add metadata to game state
        now = datetime.now(UTC)
        game_state["created_at"] = now.isoformat()
        game_state["current_turn_identifier"] = engine.current_player_id
        game_state["result"] = GameResult.IN_PROGRESS.value
        game_state["winner_identifier"] = None
        
        # Start the first turn's timer
        game_state = engine.start_turn(game_state)
        
        # Prepare engine configuration for storage
        engine_config = {
            "game_name": game_name,
            "lobby_code": lobby_code,
            "identifiers": identifiers,
            "rules": rules or {},
            "current_turn_index": engine.current_turn_index,
        }
        
        # Store in Redis
        async with redis.pipeline(transaction=True) as pipe:
            # Store game state
            pipe.set(
                GameService._game_state_key(lobby_code),
                json.dumps(game_state),
                ex=GameService.GAME_TTL
            )
            
            # Store engine configuration
            pipe.set(
                GameService._game_engine_key(lobby_code),
                json.dumps(engine_config),
                ex=GameService.GAME_TTL
            )
            
            # Map lobby to game
            pipe.set(
                GameService._lobby_game_key(lobby_code),
                game_name,
                ex=GameService.GAME_TTL
            )
            
            await pipe.execute()
        
        # Set initial timeout key if timeout is configured
        await GameService._set_timeout_key(redis, engine, game_state, lobby_code)
        
        # Extend guest sessions for all guest players
        from services.guest_service import GuestService
        for identifier in identifiers:
            if identifier.startswith("guest:"):
                guest_id = identifier.split(":", 1)[1]
                await GuestService.extend_guest_session(redis, guest_id)
        
        logger.info(f"Game '{game_name}' created for lobby {lobby_code} with identifiers {identifiers}")
        
        # Get static game info
        engine_class = GameService.GAME_ENGINES[game_name]
        game_info = engine_class.get_game_info()
        
        return {
            "lobby_code": lobby_code,
            "game_name": game_name,
            "game_state": game_state,
            "game_info": game_info,
            "current_turn_identifier": engine.current_player_id,
            "created_at": now,
        }
    
    @staticmethod
    async def get_game(redis: Redis, lobby_code: str) -> Optional[Dict[str, Any]]:
        """
        Get current game state and configuration.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            
        Returns:
            Dictionary with game state and config or None if not found
        """
        # Get game state and engine config
        state_raw, config_raw = await redis.mget([
            GameService._game_state_key(lobby_code),
            GameService._game_engine_key(lobby_code)
        ])
        
        if not state_raw or not config_raw:
            return None
        
        game_state = json.loads(state_raw)
        engine_config = json.loads(config_raw)
        
        return {
            "game_state": game_state,
            "engine_config": engine_config,
            "lobby_code": lobby_code,
        }
    
    @staticmethod
    async def _load_engine(redis: Redis, lobby_code: str) -> Optional[GameEngineInterface]:
        """
        Load and reconstruct the game engine from Redis.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            
        Returns:
            GameEngineInterface instance or None if not found
        """
        config_raw = await redis.get(GameService._game_engine_key(lobby_code))
        if not config_raw:
            return None
        
        config = json.loads(config_raw)
        
        game_name = config["game_name"]
        if game_name not in GameService.GAME_ENGINES:
            logger.error(f"Unknown game type in storage: {game_name}")
            return None
        
        # Reconstruct engine
        engine_class = GameService.GAME_ENGINES[game_name]
        engine = engine_class(
            config["lobby_code"],
            config["identifiers"],
            config["rules"]
        )
        
        # Restore turn state
        engine.current_turn_index = config["current_turn_index"]
        
        return engine
    
    @staticmethod
    async def _save_engine(redis: Redis, engine: GameEngineInterface):
        """
        Save the game engine state to Redis.
        
        Args:
            redis: Redis client
            engine: GameEngineInterface instance
        """
        engine_config = {
            "game_name": engine.get_game_name(),
            "lobby_code": engine.lobby_code,
            "identifiers": engine.player_ids,
            "rules": engine.rules,
            "current_turn_index": engine.current_turn_index,
        }
        
        await redis.set(
            GameService._game_engine_key(engine.lobby_code),
            json.dumps(engine_config),
            ex=GameService.GAME_TTL
        )
    
    @staticmethod
    async def make_move(
        redis: Redis,
        lobby_code: str,
        identifier: str,
        move_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a player's move.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            identifier: Identifier of the player making the move (e.g., 'user:123' or 'guest:uuid')
            move_data: Move data specific to the game
            
        Returns:
            Dictionary with updated game state and result
            
        Raises:
            NotFoundException: If game not found
            BadRequestException: If move is invalid
        """
        # Load engine and game state
        engine = await GameService._load_engine(redis, lobby_code)
        if not engine:
            raise NotFoundException(
                message="Game not found",
                details={"lobby_code": lobby_code}
            )
        
        state_raw = await redis.get(GameService._game_state_key(lobby_code))
        if not state_raw:
            raise NotFoundException(
                message="Game state not found",
                details={"lobby_code": lobby_code}
            )
        
        game_state = json.loads(state_raw)
        
        # Check for timeout before validating move
        timeout_occurred, timeout_winner_identifier = engine.check_timeout(game_state)
        if timeout_occurred:
            # Check if this ends the game or just skips the turn
            if timeout_winner_identifier is not None or engine.game_result != GameResult.IN_PROGRESS:
                # Game ended by timeout
                game_state["result"] = GameResult.TIMEOUT.value
                game_state["winner_identifier"] = timeout_winner_identifier
                
                # Save the timeout result
                await redis.set(
                    GameService._game_state_key(lobby_code),
                    json.dumps(game_state),
                    ex=GameService.GAME_TTL
                )
                
                raise BadRequestException(
                    message="Time limit exceeded - game ended",
                    details={"result": "timeout", "winner_identifier": timeout_winner_identifier}
                )
            else:
                # Turn is skipped, advance to next player
                logger.info(f"Player {identifier} timed out - skipping turn in lobby {lobby_code}")
                game_state = engine.consume_turn_time(game_state)
                engine.advance_turn()
                game_state["current_turn_identifier"] = engine.current_player_id
                game_state = engine.start_turn(game_state)
                
                # Save state and update timeout key
                await redis.set(
                    GameService._game_state_key(lobby_code),
                    json.dumps(game_state),
                    ex=GameService.GAME_TTL
                )
                await GameService._save_engine(redis, engine)
                await GameService._set_timeout_key(redis, engine, game_state, lobby_code)
                
                raise BadRequestException(
                    message="Time limit exceeded - your turn was skipped",
                    details={"skipped": True, "current_turn_identifier": engine.current_player_id}
                )
        
        # Validate move
        validation_result = engine.validate_move(game_state, identifier, move_data)
        if not validation_result.valid:
            raise BadRequestException(
                message=validation_result.error_message or "Invalid move",
                details={"move_data": move_data}
            )
        
        # Apply move
        game_state = engine.apply_move(game_state, identifier, move_data)
        
        # Consume time used for this move
        game_state = engine.consume_turn_time(game_state)
        
        # Check game result
        result, winner_identifier = engine.check_game_result(game_state)
        
        # Update metadata
        game_state["result"] = result.value
        game_state["winner_identifier"] = winner_identifier
        
        # Advance turn if game is still in progress
        if result == GameResult.IN_PROGRESS:
            engine.advance_turn()
            game_state["current_turn_identifier"] = engine.current_player_id
            # Start the next turn's timer
            game_state = engine.start_turn(game_state)
        
        # Save updated state
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(
                GameService._game_state_key(lobby_code),
                json.dumps(game_state),
                ex=GameService.GAME_TTL
            )
            await GameService._save_engine(redis, engine)
            await pipe.execute()
        
        # Update timeout key for next turn or clear it if game ended
        if result == GameResult.IN_PROGRESS:
            await GameService._set_timeout_key(redis, engine, game_state, lobby_code)
        else:
            await GameService._clear_timeout_key(redis, lobby_code)
        
        # Extend guest session if player is a guest
        if identifier.startswith("guest:"):
            from services.guest_service import GuestService
            guest_id = identifier.split(":", 1)[1]
            await GuestService.extend_guest_session(redis, guest_id)
        
        logger.info(f"Move processed for lobby {lobby_code} by identifier {identifier}. Result: {result.value}")
        
        return {
            "game_state": game_state,
            "result": result.value,
            "winner_identifier": winner_identifier,
            "current_turn_identifier": game_state.get("current_turn_identifier"),
        }
    
    @staticmethod
    async def forfeit_game(
        redis: Redis,
        lobby_code: str,
        identifier: str
    ) -> Dict[str, Any]:
        """
        Handle a player forfeiting the game.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            identifier: Identifier of the player forfeiting (e.g., 'user:123' or 'guest:uuid')
            
        Returns:
            Dictionary with updated game state
            
        Raises:
            NotFoundException: If game not found
        """
        # Load engine and game state
        engine = await GameService._load_engine(redis, lobby_code)
        if not engine:
            raise NotFoundException(
                message="Game not found",
                details={"lobby_code": lobby_code}
            )
        
        state_raw = await redis.get(GameService._game_state_key(lobby_code))
        if not state_raw:
            raise NotFoundException(
                message="Game state not found",
                details={"lobby_code": lobby_code}
            )
        
        game_state = json.loads(state_raw)
        
        # Process forfeit
        result, winner_identifier = engine.forfeit_game(identifier)
        
        # Update game state
        game_state["result"] = result.value
        game_state["winner_identifier"] = winner_identifier
        game_state["forfeited_by"] = identifier
        
        # Save updated state
        await redis.set(
            GameService._game_state_key(lobby_code),
            json.dumps(game_state),
            ex=GameService.GAME_TTL
        )
        
        # Clear timeout key since game ended
        await GameService._clear_timeout_key(redis, lobby_code)
        
        logger.info(f"Player {identifier} forfeited game in lobby {lobby_code}")
        
        return {
            "game_state": game_state,
            "result": result.value,
            "winner_identifier": winner_identifier,
        }
    
    @staticmethod
    async def handle_player_left(
        redis: Redis,
        lobby_code: str,
        identifier: str
    ) -> Dict[str, Any]:
        """
        Handle a player leaving the lobby during an active game.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            identifier: Identifier of the player who left (e.g., 'user:123' or 'guest:uuid')
            
        Returns:
            Dictionary with updated game state
            
        Raises:
            NotFoundException: If game not found
        """
        # Load engine and game state
        engine = await GameService._load_engine(redis, lobby_code)
        if not engine:
            raise NotFoundException(
                message="Game not found",
                details={"lobby_code": lobby_code}
            )
        
        state_raw = await redis.get(GameService._game_state_key(lobby_code))
        if not state_raw:
            raise NotFoundException(
                message="Game state not found",
                details={"lobby_code": lobby_code}
            )
        
        game_state = json.loads(state_raw)
        
        # Process player leaving - determine winner (other player)
        result, winner_identifier = engine.forfeit_game(identifier)
        
        # Update game state with player_left result instead of forfeit
        game_state["result"] = GameResult.PLAYER_LEFT.value
        game_state["winner_identifier"] = winner_identifier
        game_state["left_by"] = identifier
        
        # Save updated state
        await redis.set(
            GameService._game_state_key(lobby_code),
            json.dumps(game_state),
            ex=GameService.GAME_TTL
        )
        
        # Clear timeout key since game ended
        await GameService._clear_timeout_key(redis, lobby_code)
        
        logger.info(f"Player {identifier} left game in lobby {lobby_code}")
        
        return {
            "game_state": game_state,
            "result": GameResult.PLAYER_LEFT.value,
            "winner_identifier": winner_identifier,
        }
    
    @staticmethod
    async def get_timing_info(redis: Redis, lobby_code: str) -> Optional[Dict[str, Any]]:
        """
        Get timing information for the current game.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            
        Returns:
            Dictionary with timing information or None if game not found
        """
        engine = await GameService._load_engine(redis, lobby_code)
        if not engine:
            return None
        
        state_raw = await redis.get(GameService._game_state_key(lobby_code))
        if not state_raw:
            return None
        
        game_state = json.loads(state_raw)
        timing = game_state.get("timing", {})
        
        # Build timing info response
        timing_info = {
            "timeout_type": timing.get("timeout_type", "none"),
            "timeout_seconds": timing.get("timeout_seconds", 0),
            "current_identifier": engine.current_player_id,
        }
        
        # Add player-specific time remaining
        if timing.get("timeout_type") != "none":
            player_times = {}
            for identifier in engine.player_ids:
                remaining_time = engine.get_remaining_time(game_state, identifier)
                player_times[str(identifier)] = remaining_time
            timing_info["player_time_remaining"] = player_times
        
        return timing_info
    
    @staticmethod
    async def _set_timeout_key(redis: Redis, engine, game_state: Dict[str, Any], lobby_code: str):
        """
        Set a Redis key with TTL for game timeout.
        When the key expires, it triggers a keyspace notification that ends the game.
        
        Args:
            redis: Redis client
            engine: Game engine instance
            game_state: Current game state
            lobby_code: The lobby code
        """
        from services.timeout_checker import TimeoutChecker
        from services.game_engine_interface import TimeoutType
        
        # Only set timeout key if timeout is configured
        if engine.timeout_type == TimeoutType.NONE:
            return
        
        # Get remaining time for current player
        remaining_time = engine.get_remaining_time(game_state)
        
        if remaining_time is None or remaining_time <= 0:
            # No time remaining, don't set key (game should end)
            return
        
        # Set a Redis key that expires when time runs out
        # We add 1 second buffer to account for Redis timing precision
        ttl_seconds = int(remaining_time) + 1
        timeout_key = TimeoutChecker.get_timeout_key(lobby_code)
        
        await redis.set(timeout_key, "timeout", ex=ttl_seconds)
        logger.debug(f"Set timeout key for lobby {lobby_code} with TTL {ttl_seconds}s")
    
    @staticmethod
    async def _clear_timeout_key(redis: Redis, lobby_code: str):
        """
        Clear the timeout key when game ends.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
        """
        from services.timeout_checker import TimeoutChecker
        
        timeout_key = TimeoutChecker.get_timeout_key(lobby_code)
        await redis.delete(timeout_key)
        logger.debug(f"Cleared timeout key for lobby {lobby_code}")
    
    @staticmethod
    async def update_player_elos(redis: Redis, lobby_code: str, game_state: dict):
        """
        Update ELO scores for players after game end.
        Supports multi-player games with variable adjustments.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
            game_state: The final game state containing winner information
        """
        try:
            # Get game engine to calculate adjustment
            engine = await GameService._load_engine(redis, lobby_code)
            if not engine:
                return
            
            # Calculate adjustments for all players
            adjustments = engine.calculate_elo_adjustments(game_state)
            
            if not adjustments:
                return
            
            # Update users in DB
            from infrastructure.postgres_connection import postgres_connection
            from sqlalchemy import update
            from models.registered_user import RegisteredUser
            
            async with postgres_connection.session_factory() as session:
                for player_id, adjustment in adjustments.items():
                    if adjustment == 0:
                        continue
                    
                    # Extract numeric ID from identifier format (e.g., 'user:123' -> 123)
                    # Skip non-user identifiers (e.g., guests)
                    if not player_id.startswith('user:'):
                        continue
                    
                    try:
                        numeric_id = int(player_id.split(':', 1)[1])
                    except (IndexError, ValueError):
                        logger.warning(f"Could not extract numeric ID from identifier: {player_id}")
                        continue
                        
                    await session.execute(
                        update(RegisteredUser)
                        .where(RegisteredUser.id == numeric_id)
                        .values(elo=RegisteredUser.elo + adjustment)
                    )
                
                await session.commit()
                
            logger.info(f"Updated ELOs for lobby {lobby_code}: {adjustments}")
            
        except Exception as e:
            logger.error(f"Failed to update ELOs: {e}", exc_info=True)
    
    @staticmethod
    async def delete_game(redis: Redis, lobby_code: str):
        """
        Delete a game and clean up all related data.
        
        Args:
            redis: Redis client
            lobby_code: The lobby code
        """
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(GameService._game_state_key(lobby_code))
            pipe.delete(GameService._game_engine_key(lobby_code))
            pipe.delete(GameService._lobby_game_key(lobby_code))
            await pipe.execute()
        
        # Also clear timeout key
        await GameService._clear_timeout_key(redis, lobby_code)
        
        logger.info(f"Game deleted for lobby {lobby_code}")
