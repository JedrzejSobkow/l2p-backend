# app/schemas/friendship_schema.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class FriendshipBase(BaseModel):
    """Base schema for friendship"""
    pass


class FriendshipCreate(FriendshipBase):
    """Schema for creating a friendship (friend request)"""
    nickname: str


class FriendshipResponse(BaseModel):
    """Schema for friendship response"""
    id_friendship: int
    user_id_1: int
    user_id_2: int
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class FriendshipWithUser(BaseModel):
    """Schema for friendship with user details"""
    id_friendship: int
    friend_id: int
    friend_nickname: str
    friend_pfp_path: Optional[str]
    friend_description: Optional[str]
    status: str
    created_at: datetime
    is_requester: bool  # True if current user sent the request
    
    model_config = ConfigDict(from_attributes=True)


class UserSearchResult(BaseModel):
    """Schema for user search results"""
    id: int
    nickname: str
    pfp_path: Optional[str]
    description: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class UserSearchResponse(BaseModel):
    """Schema for paginated user search response"""
    users: list[UserSearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int
