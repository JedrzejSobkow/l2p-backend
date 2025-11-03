# app/api/routes/lobby.py

from fastapi import APIRouter, Depends, HTTPException, status
from infrastructure.redis_connection import get_redis
from api.routes.auth import current_active_user
from models.registered_user import RegisteredUser
from services.lobby_service import LobbyService
from schemas.lobby_schema import (
    CreateLobbyRequest,
    JoinLobbyRequest,
    UpdateLobbySettingsRequest,
    TransferHostRequest,
    KickMemberRequest,
    LobbyResponse,
    LobbyCreatedResponse,
    LobbyJoinedResponse,
    LobbyMemberResponse,
    PublicLobbiesResponse,
)
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lobby", tags=["lobby"])


@router.post("", response_model=LobbyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_lobby(
    request: CreateLobbyRequest,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Create a new lobby
    
    - **max_players**: Maximum number of players (2-6, default 6)
    
    Returns lobby code for joining
    """
    try:
        redis = get_redis()
        lobby = await LobbyService.create_lobby(
            redis=redis,
            host_id=current_user.id,
            host_nickname=current_user.nickname,
            max_players=request.max_players,
            is_public=request.is_public
        )
        
        return LobbyCreatedResponse(lobby_code=lobby["lobby_code"])
        
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "details": e.details}
        )
    except Exception as e:
        logger.error(f"Error creating lobby: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create lobby"}
        )


@router.get("/public", response_model=PublicLobbiesResponse)
async def get_public_lobbies(
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get all public lobbies
    """
    try:
        redis = get_redis()
        lobbies = await LobbyService.get_all_public_lobbies(redis)
        
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
        
        return PublicLobbiesResponse(
            lobbies=lobbies_response,
            total=len(lobbies_response)
        )
        
    except Exception as e:
        logger.error(f"Error getting public lobbies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get public lobbies"}
        )


@router.get("/{lobby_code}", response_model=LobbyResponse)
async def get_lobby(
    lobby_code: str,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get lobby information by code
    
    - **lobby_code**: 6-character lobby code
    """
    try:
        redis = get_redis()
        lobby = await LobbyService.get_lobby(redis, lobby_code.upper())
        
        if not lobby:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Lobby not found"}
            )
        
        return LobbyResponse(
            lobby_code=lobby["lobby_code"],
            host_id=lobby["host_id"],
            max_players=lobby["max_players"],
            current_players=lobby["current_players"],
            is_public=lobby.get("is_public", False),
            members=[LobbyMemberResponse(**m) for m in lobby["members"]],
            created_at=lobby["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lobby: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get lobby"}
        )


@router.post("/{lobby_code}/join", response_model=LobbyJoinedResponse)
async def join_lobby(
    lobby_code: str,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Join an existing lobby
    
    - **lobby_code**: 6-character lobby code
    """
    try:
        redis = get_redis()
        lobby = await LobbyService.join_lobby(
            redis=redis,
            lobby_code=lobby_code.upper(),
            user_id=current_user.id,
            user_nickname=current_user.nickname
        )
        
        lobby_response = LobbyResponse(
            lobby_code=lobby["lobby_code"],
            host_id=lobby["host_id"],
            max_players=lobby["max_players"],
            current_players=lobby["current_players"],
            is_public=lobby.get("is_public", False),
            members=[LobbyMemberResponse(**m) for m in lobby["members"]],
            created_at=lobby["created_at"]
        )
        
        return LobbyJoinedResponse(lobby=lobby_response)
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message, "details": e.details}
        )
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "details": e.details}
        )
    except Exception as e:
        logger.error(f"Error joining lobby: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to join lobby"}
        )


@router.post("/{lobby_code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_lobby(
    lobby_code: str,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Leave current lobby
    
    - **lobby_code**: 6-character lobby code
    """
    try:
        redis = get_redis()
        await LobbyService.leave_lobby(
            redis=redis,
            lobby_code=lobby_code.upper(),
            user_id=current_user.id
        )
        
        return None
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message}
        )
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message}
        )
    except Exception as e:
        logger.error(f"Error leaving lobby: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to leave lobby"}
        )


@router.patch("/{lobby_code}/settings", response_model=LobbyResponse)
async def update_lobby_settings(
    lobby_code: str,
    request: UpdateLobbySettingsRequest,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Update lobby settings (host only)
    
    - **lobby_code**: 6-character lobby code
    - **max_players**: New maximum number of players (2-6)
    """
    try:
        redis = get_redis()
        lobby = await LobbyService.update_lobby_settings(
            redis=redis,
            lobby_code=lobby_code.upper(),
            user_id=current_user.id,
            max_players=request.max_players,
            is_public=request.is_public
        )
        
        return LobbyResponse(
            lobby_code=lobby["lobby_code"],
            host_id=lobby["host_id"],
            max_players=lobby["max_players"],
            current_players=lobby["current_players"],
            is_public=lobby.get("is_public", False),
            members=[LobbyMemberResponse(**m) for m in lobby["members"]],
            created_at=lobby["created_at"]
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message}
        )
    except ForbiddenException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": e.message}
        )
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "details": e.details}
        )
    except Exception as e:
        logger.error(f"Error updating lobby settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to update settings"}
        )


@router.post("/{lobby_code}/transfer-host", response_model=LobbyResponse)
async def transfer_host(
    lobby_code: str,
    request: TransferHostRequest,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Transfer host privileges to another member (host only)
    
    - **lobby_code**: 6-character lobby code
    - **new_host_id**: User ID of the new host
    """
    try:
        redis = get_redis()
        await LobbyService.transfer_host(
            redis=redis,
            lobby_code=lobby_code.upper(),
            current_host_id=current_user.id,
            new_host_id=request.new_host_id
        )
        
        # Get updated lobby state
        lobby = await LobbyService.get_lobby(redis, lobby_code.upper())
        
        return LobbyResponse(
            lobby_code=lobby["lobby_code"],
            host_id=lobby["host_id"],
            max_players=lobby["max_players"],
            current_players=lobby["current_players"],
            is_public=lobby.get("is_public", False),
            members=[LobbyMemberResponse(**m) for m in lobby["members"]],
            created_at=lobby["created_at"]
        )
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message}
        )
    except ForbiddenException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": e.message}
        )
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message}
        )
    except Exception as e:
        logger.error(f"Error transferring host: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to transfer host"}
        )


@router.post("/{lobby_code}/kick/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def kick_member(
    lobby_code: str,
    user_id: int,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Kick a member from lobby (host only)
    
    - **lobby_code**: 6-character lobby code
    - **user_id**: User ID of the member to kick
    """
    try:
        redis = get_redis()
        await LobbyService.kick_member(
            redis=redis,
            lobby_code=lobby_code.upper(),
            host_id=current_user.id,
            user_id_to_kick=user_id
        )
        
        return None
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message}
        )
    except ForbiddenException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": e.message}
        )
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message}
        )
    except Exception as e:
        logger.error(f"Error kicking member: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to kick member"}
        )


@router.get("/me/current", response_model=LobbyResponse)
async def get_my_lobby(
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get current user's lobby (if in one)
    """
    try:
        redis = get_redis()
        lobby_code = await LobbyService.get_user_lobby(redis, current_user.id)
        
        if not lobby_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "You are not in a lobby"}
            )
        
        lobby = await LobbyService.get_lobby(redis, lobby_code)
        
        if not lobby:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Lobby not found"}
            )
        
        return LobbyResponse(
            lobby_code=lobby["lobby_code"],
            host_id=lobby["host_id"],
            max_players=lobby["max_players"],
            current_players=lobby["current_players"],
            is_public=lobby.get("is_public", False),
            members=[LobbyMemberResponse(**m) for m in lobby["members"]],
            created_at=lobby["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user lobby: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get lobby"}
        )


@router.post("/{lobby_code}/ready", status_code=status.HTTP_200_OK)
async def toggle_ready(
    lobby_code: str,
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Toggle ready status for current user in the lobby
    
    - **lobby_code**: 6-character lobby code
    
    Returns updated member ready status
    """
    try:
        redis = get_redis()
        result = await LobbyService.toggle_ready(
            redis=redis,
            lobby_code=lobby_code.upper(),
            user_id=current_user.id
        )
        
        return {
            "message": f"Ready status toggled to {result['is_ready']}",
            "user_id": result["user_id"],
            "nickname": result["nickname"],
            "is_ready": result["is_ready"]
        }
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": e.message, "details": e.details}
        )
    except BadRequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "details": e.details}
        )
    except Exception as e:
        logger.error(f"Error toggling ready: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to toggle ready status"}
        )
