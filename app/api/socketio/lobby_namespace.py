# app/api/socketio/lobby_namespace.py

import socketio
from infrastructure.socketio_manager import sio, manager, AuthNamespace
from infrastructure.redis_connection import get_redis
from services.lobby_service import LobbyService
from models.registered_user import RegisteredUser
from schemas.lobby_schema import (
    CreateLobbyRequest,
    JoinLobbyRequest,
    LeaveLobbyRequest,
    UpdateLobbySettingsRequest,
    TransferHostRequest,
    KickMemberRequest,
    ToggleReadyRequest,
    LobbyResponse,
    LobbyCreatedResponse,
    LobbyJoinedResponse,
    LobbyLeftResponse,
    LobbyMemberJoinedEvent,
    LobbyMemberLeftEvent,
    LobbyHostTransferredEvent,
    LobbySettingsUpdatedEvent,
    MemberKickedEvent,
    MemberReadyChangedEvent,
    PublicLobbiesResponse,
    LobbyClosedEvent,
    LobbyErrorResponse,
    LobbyMemberResponse,
)
from pydantic import ValidationError
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
import logging

logger = logging.getLogger(__name__)


class LobbyNamespace(AuthNamespace):
    """Socket.IO namespace for lobby functionality"""

    async def handle_connect(self, sid, environ, user: RegisteredUser):
        """Namespace-specific connect hook called after successful auth."""
        logger.info(f"Client authenticated and connected to /lobby: {sid} (User: {user.id}, Email: {user.email})")
        
        # Check if user is already in a lobby and rejoin
        try:
            redis = get_redis()
            lobby_code = await LobbyService.get_user_lobby(redis, user.id)
            
            if lobby_code:
                # User is in a lobby, join the Socket.IO room
                await self.enter_room(sid, lobby_code)
                
                # Send current lobby state
                lobby = await LobbyService.get_lobby(redis, lobby_code)
                if lobby:
                    lobby_response = LobbyResponse(
                        lobby_code=lobby["lobby_code"],
                        host_id=lobby["host_id"],
                        max_players=lobby["max_players"],
                        current_players=lobby["current_players"],
                        is_public=lobby.get("is_public", False),
                        members=[LobbyMemberResponse(**m) for m in lobby["members"]],
                        created_at=lobby["created_at"]
                    )
                    await self.emit('lobby_state', lobby_response.model_dump(mode='json'), room=sid)
                    logger.info(f"User {user.id} rejoined lobby {lobby_code}")
        except Exception as e:
            logger.error(f"Error checking user lobby on connect: {str(e)}")
    
    async def handle_disconnect(self, sid):
        """Called when client disconnects - leave lobby on disconnect"""
        user_id = manager.get_user_id(sid)
        if not user_id:
            return
        
        logger.info(f"User {user_id} disconnected from /lobby")
        
        # Note: We don't automatically remove from lobby on disconnect
        # User can reconnect and rejoin. Lobby cleanup happens on explicit leave or timeout
    
    async def on_create_lobby(self, sid, data):
        """
        Create a new lobby
        
        Expected data: {"max_players": int (2-6, default 6)}
        """
        try:
            # Validate input
            try:
                request = CreateLobbyRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_nickname = manager.get_nickname(user_id)
            if not user_nickname:
                # Fetch from database if not cached
                user = await self.get_authenticated_user(sid)
                if not user:
                    error_response = LobbyErrorResponse(
                        message='User not found',
                        error_code='USER_NOT_FOUND'
                    )
                    await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                    return
                user_nickname = user.nickname
            
            # Create lobby
            redis = get_redis()
            user = await self.get_authenticated_user(sid)
            lobby = await LobbyService.create_lobby(
                redis=redis,
                host_id=user_id,
                host_nickname=user_nickname,
                host_pfp_path=user.pfp_path if user else None,
                max_players=request.max_players,
                is_public=request.is_public
            )
            
            # Join Socket.IO room
            await self.enter_room(sid, lobby["lobby_code"])
            
            # Send response to creator
            response = LobbyCreatedResponse(lobby_code=lobby["lobby_code"])
            await self.emit('lobby_created', response.model_dump(mode='json'), room=sid)
            
            # Send full lobby state
            lobby_response = LobbyResponse(
                lobby_code=lobby["lobby_code"],
                host_id=lobby["host_id"],
                max_players=lobby["max_players"],
                current_players=lobby["current_players"],
                is_public=lobby.get("is_public", False),
                members=[LobbyMemberResponse(**m) for m in lobby["members"]],
                created_at=lobby["created_at"]
            )
            await self.emit('lobby_state', lobby_response.model_dump(mode='json'), room=sid)
            
            logger.info(f"User {user_id} created lobby {lobby['lobby_code']}")
            
        except BadRequestException as e:
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code='BAD_REQUEST',
                details=e.details
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error creating lobby: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to create lobby',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_join_lobby(self, sid, data):
        """
        Join an existing lobby
        
        Expected data: {"lobby_code": str (6 chars)}
        """
        try:
            # Validate input
            try:
                request = JoinLobbyRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_nickname = manager.get_nickname(user_id)
            user = None
            if not user_nickname:
                user = await self.get_authenticated_user(sid)
                if not user:
                    error_response = LobbyErrorResponse(
                        message='User not found',
                        error_code='USER_NOT_FOUND'
                    )
                    await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                    return
                user_nickname = user.nickname
            
            # Get user for pfp_path if not already fetched
            if not user:
                user = await self.get_authenticated_user(sid)
            
            # Join lobby
            redis = get_redis()
            lobby = await LobbyService.join_lobby(
                redis=redis,
                lobby_code=request.lobby_code,
                user_id=user_id,
                user_nickname=user_nickname,
                user_pfp_path=user.pfp_path if user else None
            )
            
            # Join Socket.IO room
            await self.enter_room(sid, request.lobby_code)
            
            # Send response to joiner
            lobby_response = LobbyResponse(
                lobby_code=lobby["lobby_code"],
                host_id=lobby["host_id"],
                max_players=lobby["max_players"],
                current_players=lobby["current_players"],
                is_public=lobby.get("is_public", False),
                members=[LobbyMemberResponse(**m) for m in lobby["members"]],
                created_at=lobby["created_at"]
            )
            response = LobbyJoinedResponse(lobby=lobby_response)
            await self.emit('lobby_joined', response.model_dump(mode='json'), room=sid)
            
            # Notify all members in lobby about new member
            new_member = next(m for m in lobby["members"] if m["user_id"] == user_id)
            member_joined_event = LobbyMemberJoinedEvent(
                member=LobbyMemberResponse(**new_member),
                current_players=lobby["current_players"]
            )
            await self.emit('member_joined', member_joined_event.model_dump(mode='json'), room=request.lobby_code, skip_sid=sid)
            
            logger.info(f"User {user_id} joined lobby {request.lobby_code}")
            
        except (NotFoundException, BadRequestException) as e:
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code='NOT_FOUND' if isinstance(e, NotFoundException) else 'BAD_REQUEST',
                details=e.details if hasattr(e, 'details') else None
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error joining lobby: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to join lobby',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_leave_lobby(self, sid, data):
        """
        Leave current lobby
        
        Expected data: {"lobby_code": str (6 chars)}
        """
        try:
            # Validate input
            try:
                request = LeaveLobbyRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_nickname = manager.get_nickname(user_id)
            
            # Leave lobby
            redis = get_redis()
            result = await LobbyService.leave_lobby(
                redis=redis,
                lobby_code=request.lobby_code,
                user_id=user_id
            )
            
            # Leave Socket.IO room
            await self.leave_room(sid, request.lobby_code)
            
            # Send response to leaver
            response = LobbyLeftResponse()
            await self.emit('lobby_left', response.model_dump(mode='json'), room=sid)
            
            # If lobby still exists
            if result is not None:
                # Notify remaining members
                # Get updated lobby to get current player count
                updated_lobby = await LobbyService.get_lobby(redis, request.lobby_code)
                current_players = len(updated_lobby["members"]) if updated_lobby else 0
                
                member_left_event = LobbyMemberLeftEvent(
                    user_id=user_id,
                    nickname=user_nickname or "Unknown",
                    current_players=current_players
                )
                await self.emit('member_left', member_left_event.model_dump(mode='json'), room=request.lobby_code)
                
                # If host was transferred
                if result.get("host_transferred"):
                    host_transfer_event = LobbyHostTransferredEvent(
                        old_host_id=result["old_host_id"],
                        new_host_id=result["new_host_id"],
                        new_host_nickname=result["new_host_nickname"]
                    )
                    await self.emit('host_transferred', host_transfer_event.model_dump(mode='json'), room=request.lobby_code)
                
                logger.info(f"User {user_id} left lobby {request.lobby_code}")
            else:
                # Lobby was closed
                logger.info(f"Lobby {request.lobby_code} closed after last member left")
            
        except (NotFoundException, BadRequestException) as e:
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code='NOT_FOUND' if isinstance(e, NotFoundException) else 'BAD_REQUEST',
                details=e.details if hasattr(e, 'details') else None
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error leaving lobby: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to leave lobby',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_update_settings(self, sid, data):
        """
        Update lobby settings (host only)
        
        Expected data: {"max_players": int (2-6)}
        """
        try:
            # Validate input
            try:
                request = UpdateLobbySettingsRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get user's current lobby
            redis = get_redis()
            lobby_code = await LobbyService.get_user_lobby(redis, user_id)
            if not lobby_code:
                error_response = LobbyErrorResponse(
                    message='You are not in a lobby',
                    error_code='NOT_IN_LOBBY'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Update settings
            lobby = await LobbyService.update_lobby_settings(
                redis=redis,
                lobby_code=lobby_code,
                user_id=user_id,
                max_players=request.max_players,
                is_public=request.is_public
            )
            
            # Notify all members
            settings_updated_event = LobbySettingsUpdatedEvent(
                max_players=request.max_players,
                is_public=request.is_public
            )
            await self.emit('settings_updated', settings_updated_event.model_dump(mode='json'), room=lobby_code)
            
            logger.info(f"User {user_id} updated lobby {lobby_code} settings")
            
        except (NotFoundException, BadRequestException, ForbiddenException) as e:
            error_code = 'NOT_FOUND' if isinstance(e, NotFoundException) else \
                        'FORBIDDEN' if isinstance(e, ForbiddenException) else 'BAD_REQUEST'
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code=error_code,
                details=e.details if hasattr(e, 'details') else None
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error updating lobby settings: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to update settings',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_transfer_host(self, sid, data):
        """
        Transfer host privileges to another member (host only)
        
        Expected data: {"new_host_id": int}
        """
        try:
            # Validate input
            try:
                request = TransferHostRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get user's current lobby
            redis = get_redis()
            lobby_code = await LobbyService.get_user_lobby(redis, user_id)
            if not lobby_code:
                error_response = LobbyErrorResponse(
                    message='You are not in a lobby',
                    error_code='NOT_IN_LOBBY'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Transfer host
            result = await LobbyService.transfer_host(
                redis=redis,
                lobby_code=lobby_code,
                current_host_id=user_id,
                new_host_id=request.new_host_id
            )
            
            # Notify all members
            host_transfer_event = LobbyHostTransferredEvent(
                old_host_id=result["old_host_id"],
                new_host_id=result["new_host_id"],
                new_host_nickname=result["new_host_nickname"]
            )
            await self.emit('host_transferred', host_transfer_event.model_dump(mode='json'), room=lobby_code)
            
            logger.info(f"Host transferred from {user_id} to {request.new_host_id} in lobby {lobby_code}")
            
        except (NotFoundException, BadRequestException, ForbiddenException) as e:
            error_code = 'NOT_FOUND' if isinstance(e, NotFoundException) else \
                        'FORBIDDEN' if isinstance(e, ForbiddenException) else 'BAD_REQUEST'
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code=error_code,
                details=e.details if hasattr(e, 'details') else None
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error transferring host: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to transfer host',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_get_lobby(self, sid, data):
        """
        Get current lobby state
        
        Expected data: {} (optional, gets user's current lobby)
        """
        try:
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get user's current lobby
            redis = get_redis()
            lobby_code = await LobbyService.get_user_lobby(redis, user_id)
            if not lobby_code:
                error_response = LobbyErrorResponse(
                    message='You are not in a lobby',
                    error_code='NOT_IN_LOBBY'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            lobby = await LobbyService.get_lobby(redis, lobby_code)
            if not lobby:
                error_response = LobbyErrorResponse(
                    message='Lobby not found',
                    error_code='NOT_FOUND'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Send lobby state
            lobby_response = LobbyResponse(
                lobby_code=lobby["lobby_code"],
                host_id=lobby["host_id"],
                max_players=lobby["max_players"],
                current_players=lobby["current_players"],
                is_public=lobby.get("is_public", False),
                members=[LobbyMemberResponse(**m) for m in lobby["members"]],
                created_at=lobby["created_at"]
            )
            await self.emit('lobby_state', lobby_response.model_dump(mode='json'), room=sid)
            
        except Exception as e:
            logger.error(f"Error getting lobby: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to get lobby',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_get_public_lobbies(self, sid, data):
        """
        Get all public lobbies
        
        Expected data: {} (no parameters needed)
        """
        try:
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get all public lobbies
            redis = get_redis()
            lobbies = await LobbyService.get_all_public_lobbies(redis)
            
            # Convert to response format
            lobbies_response = [
                LobbyResponse(
                    lobby_code=lobby["lobby_code"],
                    host_id=lobby["host_id"],
                    max_players=lobby["max_players"],
                    current_players=lobby["current_players"],
                    is_public=lobby.get("is_public", False),
                    members=[LobbyMemberResponse(**m) for m in lobby["members"]],
                    created_at=lobby["created_at"]
                )
                for lobby in lobbies
            ]
            
            response = PublicLobbiesResponse(
                lobbies=lobbies_response,
                total=len(lobbies_response)
            )
            await self.emit('public_lobbies', response.model_dump(mode='json'), room=sid)
            
        except Exception as e:
            logger.error(f"Error getting public lobbies: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to get public lobbies',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_kick_member(self, sid, data):
        """
        Kick a member from lobby (host only)
        
        Expected data: {"user_id": int}
        """
        try:
            # Validate input
            try:
                request = KickMemberRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Get user's current lobby
            redis = get_redis()
            lobby_code = await LobbyService.get_user_lobby(redis, user_id)
            if not lobby_code:
                error_response = LobbyErrorResponse(
                    message='You are not in a lobby',
                    error_code='NOT_IN_LOBBY'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Kick member
            result = await LobbyService.kick_member(
                redis=redis,
                lobby_code=lobby_code,
                host_id=user_id,
                user_id_to_kick=request.user_id
            )
            
            # Get kicked user's sid to force disconnect from lobby room
            kicked_sid = manager.get_sid(request.user_id)
            if kicked_sid:
                await self.leave_room(kicked_sid, lobby_code)
                # Notify kicked user
                await self.emit('kicked_from_lobby', {
                    'lobby_code': lobby_code,
                    'message': 'You have been kicked from the lobby'
                }, room=kicked_sid)
            
            # Notify all remaining members
            member_kicked_event = MemberKickedEvent(
                user_id=result["user_id"],
                nickname=result["nickname"],
                kicked_by_id=user_id
            )
            await self.emit('member_kicked', member_kicked_event.model_dump(mode='json'), room=lobby_code)
            
            logger.info(f"User {request.user_id} kicked from lobby {lobby_code} by host {user_id}")
            
        except (NotFoundException, BadRequestException, ForbiddenException) as e:
            error_code = 'NOT_FOUND' if isinstance(e, NotFoundException) else \
                        'FORBIDDEN' if isinstance(e, ForbiddenException) else 'BAD_REQUEST'
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code=error_code,
                details=e.details if hasattr(e, 'details') else None
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error kicking member: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to kick member',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
    
    async def on_toggle_ready(self, sid, data):
        """
        Toggle ready status for current user
        
        Expected data: {"lobby_code": str}
        """
        try:
            # Validate input
            try:
                request = ToggleReadyRequest(**data)
            except ValidationError as e:
                error_response = LobbyErrorResponse(
                    message='Invalid data format',
                    error_code='VALIDATION_ERROR',
                    details={'errors': e.errors()}
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            user_id = manager.get_user_id(sid)
            if not user_id:
                error_response = LobbyErrorResponse(
                    message='Not authenticated',
                    error_code='AUTH_ERROR'
                )
                await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
                return
            
            # Toggle ready status
            redis = get_redis()
            result = await LobbyService.toggle_ready(
                redis=redis,
                lobby_code=request.lobby_code,
                user_id=user_id
            )
            
            # Notify all members in the lobby
            ready_event = MemberReadyChangedEvent(
                user_id=result["user_id"],
                nickname=result["nickname"],
                is_ready=result["is_ready"]
            )
            await self.emit('member_ready_changed', ready_event.model_dump(mode='json'), room=request.lobby_code)
            
            logger.info(f"User {user_id} toggled ready to {result['is_ready']} in lobby {request.lobby_code}")
            
        except (NotFoundException, BadRequestException) as e:
            error_code = 'NOT_FOUND' if isinstance(e, NotFoundException) else 'BAD_REQUEST'
            error_response = LobbyErrorResponse(
                message=e.message,
                error_code=error_code,
                details=e.details if hasattr(e, 'details') else None
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)
        except Exception as e:
            logger.error(f"Error toggling ready: {str(e)}")
            error_response = LobbyErrorResponse(
                message='Failed to toggle ready status',
                error_code='INTERNAL_ERROR'
            )
            await self.emit('lobby_error', error_response.model_dump(mode='json'), room=sid)


# Register the namespace
sio.register_namespace(LobbyNamespace('/lobby'))
