# app/api/socketio/game_namespace.py

import socketio
from infrastructure.socketio_manager import sio, manager, AuthNamespace
from infrastructure.redis_connection import get_redis
from services.game_service import GameService
from services.lobby_service import LobbyService
from models.registered_user import RegisteredUser
from schemas.game_schema import (
    CreateGameRequest,
    MakeMoveRequest,
    ForfeitGameRequest,
    GameCreatedResponse,
    MoveProcessedResponse,
    GameResultResponse,
    GameStartedEvent,
    MoveMadeEvent,
    GameEndedEvent,
    PlayerForfeitedEvent,
    GameErrorResponse,
    GameStateResponse,
)
from pydantic import ValidationError
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
import logging

logger = logging.getLogger(__name__)


class GameNamespace(AuthNamespace):
    """
    Socket.IO namespace for turn-based game functionality.
    
    Games run in rooms named after their lobby codes.
    Each game is bound to a lobby and players must be lobby members.
    """

    async def handle_connect(self, sid, environ, user: RegisteredUser):
        """Handle connection to game namespace"""
        logger.info(f"Client connected to /game: {sid} (User: {user.id})")
        
        # Check if user is in a lobby with an active game
        redis = get_redis()
        user_lobby = await redis.get(LobbyService._user_lobby_key(user.id))
        
        if user_lobby:
            lobby_code = user_lobby.decode() if isinstance(user_lobby, bytes) else user_lobby
            
            # Check if there's an active game
            game = await GameService.get_game(redis, lobby_code)
            if game:
                # Join the game room
                await self.enter_room(sid, lobby_code)
                logger.info(f"User {user.id} auto-joined game room {lobby_code}")
                
                # Send current game state
                await self.emit(
                    "game_state",
                    GameStateResponse(**game).model_dump(mode='json'),
                    room=sid
                )

    async def handle_disconnect(self, sid):
        """Handle disconnection from game namespace"""
        logger.info(f"Client disconnected from /game: {sid}")

    async def on_create_game(self, sid, data):
        """
        Create a new game for the user's lobby.
        
        Event: create_game
        Data: {game_name: str, rules?: dict}
        """
        redis = get_redis()
        
        try:
            # Get authenticated user
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = GameErrorResponse(
                    error="Not authenticated",
                    details={"message": "Authentication required"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            user = await self.get_authenticated_user(sid)
            if not user:
                error_response = GameErrorResponse(
                    error="User not found",
                    details={"message": "Could not retrieve user information"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            # Validate request
            request = CreateGameRequest(**data)
            
            # Get user's lobby
            user_lobby = await redis.get(LobbyService._user_lobby_key(user.id))
            if not user_lobby:
                raise BadRequestException(
                    message="You are not in a lobby",
                    details={"user_id": user.id}
                )
            
            lobby_code = user_lobby.decode() if isinstance(user_lobby, bytes) else user_lobby
            
            # Get lobby details
            lobby = await LobbyService.get_lobby(redis, lobby_code)
            if not lobby:
                raise NotFoundException(
                    message="Lobby not found",
                    details={"lobby_code": lobby_code}
                )
            
            # Check if user is the host
            if lobby["host_id"] != user.id:
                raise ForbiddenException(
                    message="Only the lobby host can start a game",
                    details={"lobby_code": lobby_code, "host_id": lobby["host_id"]}
                )
            
            # Get player IDs from lobby members
            player_ids = [member["user_id"] for member in lobby["members"]]
            
            # Create the game
            game_result = await GameService.create_game(
                redis=redis,
                lobby_code=lobby_code,
                game_name=request.game_name,
                player_ids=player_ids,
                rules=request.rules
            )
            
            # Join the creator to the game room
            await self.enter_room(sid, lobby_code)
            
            # Note: Other players will be added to the room when they connect to /game namespace
            # (handled in handle_connect method)
            
            # Send game started event to the creator
            event = GameStartedEvent(
                lobby_code=lobby_code,
                game_name=game_result["game_name"],
                game_state=game_result["game_state"],
                game_info=game_result["game_info"],
                current_turn_player_id=game_result["current_turn_player_id"]
            )
            await self.emit("game_started", event.model_dump(mode='json'), room=sid)
            
            # Also broadcast to the room (in case other players are already connected)
            await self.emit("game_started", event.model_dump(mode='json'), room=lobby_code)
            
            logger.info(f"Game '{request.game_name}' created for lobby {lobby_code}")
            
        except ValidationError as e:
            error_response = GameErrorResponse(
                error="Validation error",
                details={"errors": e.errors()}
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
            
        except (NotFoundException, BadRequestException, ForbiddenException) as e:
            error_response = GameErrorResponse(
                error=e.message,
                details=e.details
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
            
        except Exception as e:
            logger.error(f"Error creating game: {e}", exc_info=True)
            error_response = GameErrorResponse(
                error="Failed to create game",
                details={"message": str(e)}
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)

    async def on_make_move(self, sid, data):
        """
        Make a move in the game.
        
        Event: make_move
        Data: {move_data: dict}
        """
        redis = get_redis()
        
        try:
            # Get authenticated user
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = GameErrorResponse(
                    error="Not authenticated",
                    details={"message": "Authentication required"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            user = await self.get_authenticated_user(sid)
            if not user:
                error_response = GameErrorResponse(
                    error="User not found",
                    details={"message": "Could not retrieve user information"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            # Validate request
            request = MakeMoveRequest(**data)
            
            # Get user's lobby
            user_lobby = await redis.get(LobbyService._user_lobby_key(user.id))
            if not user_lobby:
                raise BadRequestException(
                    message="You are not in a lobby",
                    details={"user_id": user.id}
                )
            
            lobby_code = user_lobby.decode() if isinstance(user_lobby, bytes) else user_lobby
            
            # Process the move
            move_result = await GameService.make_move(
                redis=redis,
                lobby_code=lobby_code,
                player_id=user.id,
                move_data=request.move_data
            )
            
            # Broadcast move to all players in the room
            move_event = MoveMadeEvent(
                lobby_code=lobby_code,
                player_id=user.id,
                move_data=request.move_data,
                game_state=move_result["game_state"],
                current_turn_player_id=move_result.get("current_turn_player_id")
            )
            await self.emit("move_made", move_event.model_dump(mode='json'), room=lobby_code)
            
            # If game ended, broadcast game ended event
            if move_result["result"] != "in_progress":
                end_event = GameEndedEvent(
                    lobby_code=lobby_code,
                    result=move_result["result"],
                    winner_id=move_result["winner_id"],
                    game_state=move_result["game_state"]
                )
                await self.emit("game_ended", end_event.model_dump(mode='json'), room=lobby_code)
            
            logger.info(f"Move made by user {user.id} in lobby {lobby_code}")
            
        except ValidationError as e:
            error_response = GameErrorResponse(
                error="Validation error",
                details={"errors": e.errors()}
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
            
        except (NotFoundException, BadRequestException, ForbiddenException) as e:
            error_response = GameErrorResponse(
                error=e.message,
                details=e.details
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
            
        except Exception as e:
            logger.error(f"Error making move: {e}", exc_info=True)
            error_response = GameErrorResponse(
                error="Failed to make move",
                details={"message": str(e)}
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)

    async def on_forfeit(self, sid, data):
        """
        Forfeit the current game.
        
        Event: forfeit
        Data: {}
        """
        redis = get_redis()
        
        try:
            # Get authenticated user
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = GameErrorResponse(
                    error="Not authenticated",
                    details={"message": "Authentication required"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            user = await self.get_authenticated_user(sid)
            if not user:
                error_response = GameErrorResponse(
                    error="User not found",
                    details={"message": "Could not retrieve user information"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get user's lobby
            user_lobby = await redis.get(LobbyService._user_lobby_key(user.id))
            if not user_lobby:
                raise BadRequestException(
                    message="You are not in a lobby",
                    details={"user_id": user.id}
                )
            
            lobby_code = user_lobby.decode() if isinstance(user_lobby, bytes) else user_lobby
            
            # Process forfeit
            forfeit_result = await GameService.forfeit_game(
                redis=redis,
                lobby_code=lobby_code,
                player_id=user.id
            )
            
            # Broadcast forfeit event to all players
            forfeit_event = PlayerForfeitedEvent(
                lobby_code=lobby_code,
                player_id=user.id,
                winner_id=forfeit_result["winner_id"],
                game_state=forfeit_result["game_state"]
            )
            await self.emit("player_forfeited", forfeit_event.model_dump(mode='json'), room=lobby_code)
            
            # Broadcast game ended event
            end_event = GameEndedEvent(
                lobby_code=lobby_code,
                result=forfeit_result["result"],
                winner_id=forfeit_result["winner_id"],
                game_state=forfeit_result["game_state"]
            )
            await self.emit("game_ended", end_event.model_dump(mode='json'), room=lobby_code)
            
            logger.info(f"User {user.id} forfeited game in lobby {lobby_code}")
            
        except (NotFoundException, BadRequestException, ForbiddenException) as e:
            error_response = GameErrorResponse(
                error=e.message,
                details=e.details
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
            
        except Exception as e:
            logger.error(f"Error forfeiting game: {e}", exc_info=True)
            error_response = GameErrorResponse(
                error="Failed to forfeit game",
                details={"message": str(e)}
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)

    async def on_get_game_state(self, sid, data):
        """
        Get the current game state.
        
        Event: get_game_state
        Data: {}
        """
        redis = get_redis()
        
        try:
            # Get authenticated user
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = GameErrorResponse(
                    error="Not authenticated",
                    details={"message": "Authentication required"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            user = await self.get_authenticated_user(sid)
            if not user:
                error_response = GameErrorResponse(
                    error="User not found",
                    details={"message": "Could not retrieve user information"}
                )
                await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get user's lobby
            user_lobby = await redis.get(LobbyService._user_lobby_key(user.id))
            if not user_lobby:
                raise BadRequestException(
                    message="You are not in a lobby",
                    details={"user_id": user.id}
                )
            
            lobby_code = user_lobby.decode() if isinstance(user_lobby, bytes) else user_lobby
            
            # Get game state
            game = await GameService.get_game(redis, lobby_code)
            if not game:
                raise NotFoundException(
                    message="No active game found",
                    details={"lobby_code": lobby_code}
                )
            
            # Send game state to requester
            response = GameStateResponse(**game)
            await self.emit("game_state", response.model_dump(mode='json'), room=sid)
            
        except (NotFoundException, BadRequestException) as e:
            error_response = GameErrorResponse(
                error=e.message,
                details=e.details
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)
            
        except Exception as e:
            logger.error(f"Error getting game state: {e}", exc_info=True)
            error_response = GameErrorResponse(
                error="Failed to get game state",
                details={"message": str(e)}
            )
            await self.emit("game_error", error_response.model_dump(mode='json'), room=sid)


# Register the namespace
sio.register_namespace(GameNamespace('/game'))
