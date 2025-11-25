from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class UserStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    IN_GAME = "in_game"
    IN_LOBBY = "in_lobby"

class UserStatusUpdateEvent(BaseModel):
    user_id: int
    status: UserStatus
    game_name: Optional[str] = None
    last_seen: Optional[datetime] = None
    lobby_code: Optional[str] = None
    lobby_filled_slots: Optional[int] = None
    lobby_max_slots: Optional[int] = None

class FriendRequestEvent(BaseModel):
    sender_id: int
    sender_nickname: str
    sender_pfp_path: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class FriendRemovedEvent(BaseModel):
    friend_id: int

class FriendStatusListResponse(BaseModel):
    statuses: List[UserStatusUpdateEvent]
