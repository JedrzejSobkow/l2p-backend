# app/api/routes/chat.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.postgres_connection import get_db_session
from services.chat_service import ChatService
from api.routes.auth import current_active_user
from models.registered_user import RegisteredUser
from schemas.chat_schema import (
    PresignedUploadRequest, 
    PresignedUploadResponse, 
    ChatHistoryResponse,
    RecentConversationsResponse
)
from typing import Optional

router = APIRouter(prefix="/chat", tags=["chat"])




@router.post("/get-upload-url", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    request: PresignedUploadRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get a presigned URL for uploading an image directly to MinIO
    
    Workflow:
    1. Client calls this endpoint with filename and content type
    2. Server validates friendship and returns presigned upload URL
    3. Client uploads image directly to MinIO using the presigned URL (PUT request)
    4. Client calls send_message Socket.IO event with image_path to save message
    
    Args:
        request: Upload request with friend user ID, filename, and content type
        session: Database session
        current_user: Authenticated user
        
    Returns:
        Presigned upload URL and object information
    """
    result = await ChatService.generate_image_upload_url(
        session=session,
        user_id=current_user.id,
        friend_id=request.friend_user_id,
        filename=request.filename,
        content_type=request.content_type
    )
    return result


@router.get("/history/{friend_user_id}", response_model=ChatHistoryResponse)
async def get_chat_history_http(
    friend_user_id: int,
    before_message_id: Optional[int] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get chat history via HTTP
    
    Args:
        friend_user_id: User ID of the friend
        before_message_id: Get messages before this ID (for pagination)
        limit: Number of messages to return (default 50)
        session: Database session
        current_user: Authenticated user
        
    Returns:
        Chat history with pagination info
    """
    history = await ChatService.get_chat_history(
        session=session,
        user_id=current_user.id,
        friend_id=friend_user_id,
        before_message_id=before_message_id,
        limit=limit
    )
    
    return history


@router.get("/conversations", response_model=RecentConversationsResponse)
async def get_recent_conversations(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of conversations to return"),
    session: AsyncSession = Depends(get_db_session),
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get user's recent conversations sorted by last message time
    
    This endpoint should be called on initial load of the chat interface.
    Real-time updates to conversations are handled via Socket.IO events.
    
    Args:
        limit: Maximum number of conversations to return (1-100, default 20)
        session: Database session
        current_user: Authenticated user
        
    Returns:
        List of recent conversations with friend info and last message details
    """
    conversations = await ChatService.get_recent_conversations(
        session=session,
        user_id=current_user.id,
        limit=limit
    )
    
    return conversations
