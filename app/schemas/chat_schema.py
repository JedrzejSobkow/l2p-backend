# app/schemas/chat_schema.py

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message"""
    content: str = Field(..., min_length=1, max_length=10000)


class ChatMessageResponse(BaseModel):
    """Schema for chat message response"""
    sender_nickname: str
    content: str
    created_at: datetime
    is_mine: bool  # True if the message was sent by the current user
    
    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    """Schema for paginated chat history response"""
    messages: list[ChatMessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    friend_nickname: str
