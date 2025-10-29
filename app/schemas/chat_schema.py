# app/schemas/chat_schema.py

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message via Socket.IO"""
    friend_user_id: int
    content: Optional[str] = None  # Optional if image_path is provided
    image_path: Optional[str] = None  # Optional if content is provided


class ChatMessageResponse(BaseModel):
    """Schema for chat message response"""
    id: int
    sender_id: int
    sender_nickname: str
    content: Optional[str]
    image_url: Optional[str]
    created_at: str  # ISO format datetime string
    is_mine: bool  # True if the message was sent by the current user
    
    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    """Schema for cursor-based paginated chat history response"""
    messages: list[ChatMessageResponse]
    total: int
    limit: int
    has_more: bool
    next_cursor: Optional[int]  # ID of the oldest message in current batch
    friend_user_id: int
    friend_nickname: str 


class PresignedUploadRequest(BaseModel):
    """Schema for requesting a presigned upload URL"""
    friend_user_id: int
    filename: str
    content_type: str
    content: Optional[str] = None


class PresignedUploadResponse(BaseModel):
    """Schema for presigned upload URL response"""
    upload_url: str
    object_name: str
    image_path: str
    expires_in_minutes: int = 15


class ConversationResponse(BaseModel):
    """Schema for a single conversation in the recent conversations list"""
    friendship_id: int
    friend_id: int
    friend_nickname: str
    friend_email: str
    last_message_time: Optional[str] = None  # ISO format datetime string
    last_message_content: Optional[str] = None
    last_message_is_mine: Optional[bool] = None
    unread_count: int = 0


class RecentConversationsResponse(BaseModel):
    """Schema for recent conversations list response"""
    conversations: list[ConversationResponse]
