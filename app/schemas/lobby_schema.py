# app/schemas/lobby_schema.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ================ Request Models (HTTP & WebSocket) ================

class CreateLobbyRequest(BaseModel):
    """Request to create a new lobby"""
    max_players: int = Field(default=6, ge=2, le=6, description="Maximum number of players (2-6)")


class JoinLobbyRequest(BaseModel):
    """Request to join a lobby via code"""
    lobby_code: str = Field(..., min_length=6, max_length=6, description="6-digit lobby code")
    
    @field_validator('lobby_code')
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Lobby code must be alphanumeric")
        return v.upper()


class UpdateLobbySettingsRequest(BaseModel):
    """Request to update lobby settings (only host can do this)"""
    max_players: int = Field(..., ge=2, le=6, description="Maximum number of players (2-6)")


class TransferHostRequest(BaseModel):
    """Request to transfer host privileges to another member"""
    new_host_id: int = Field(..., description="User ID of the new host")


class LeaveLobbyRequest(BaseModel):
    """Request to leave a lobby"""
    lobby_code: str = Field(..., min_length=6, max_length=6, description="6-digit lobby code")


# ================ Response Models ================

class LobbyMemberResponse(BaseModel):
    """Information about a lobby member"""
    user_id: int
    nickname: str
    is_host: bool
    joined_at: datetime


class LobbyResponse(BaseModel):
    """Complete lobby information"""
    lobby_code: str
    host_id: int
    max_players: int
    current_players: int
    members: List[LobbyMemberResponse]
    created_at: datetime


class LobbyCreatedResponse(BaseModel):
    """Response when lobby is created"""
    lobby_code: str
    message: str = "Lobby created successfully"


class LobbyJoinedResponse(BaseModel):
    """Response when user joins lobby"""
    lobby: LobbyResponse
    message: str = "Joined lobby successfully"


class LobbyLeftResponse(BaseModel):
    """Response when user leaves lobby"""
    message: str = "Left lobby successfully"


# ================ WebSocket Event Models ================

class LobbyMemberJoinedEvent(BaseModel):
    """Event emitted when a member joins the lobby"""
    member: LobbyMemberResponse
    current_players: int
    message: str = "A new member has joined"


class LobbyMemberLeftEvent(BaseModel):
    """Event emitted when a member leaves the lobby"""
    user_id: int
    nickname: str
    current_players: int
    message: str = "A member has left"


class LobbyHostTransferredEvent(BaseModel):
    """Event emitted when host is transferred"""
    old_host_id: int
    new_host_id: int
    new_host_nickname: str
    message: str = "Host has been transferred"


class LobbySettingsUpdatedEvent(BaseModel):
    """Event emitted when lobby settings are updated"""
    max_players: int
    message: str = "Lobby settings updated"


class LobbyClosedEvent(BaseModel):
    """Event emitted when lobby is closed/disbanded"""
    reason: str = "Lobby has been closed"
    message: str = "Lobby closed"


class LobbyErrorResponse(BaseModel):
    """Error response for lobby operations"""
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None
