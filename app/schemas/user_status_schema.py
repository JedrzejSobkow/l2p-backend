from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class UserStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    IN_GAME = "in_game"

class UserStatusUpdateEvent(BaseModel):
    user_id: int
    status: UserStatus
    game_name: Optional[str] = None
    last_seen: Optional[datetime] = None

class FriendRequestEvent(BaseModel):
    sender_id: int
    sender_nickname: str
    sender_pfp_path: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class FriendRemovedEvent(BaseModel):
    friend_id: int

class FriendStatusListResponse(BaseModel):
    statuses: List[UserStatusUpdateEvent]
