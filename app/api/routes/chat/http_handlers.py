# app/api/routes/chat/http_handlers.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.postgres_connection import get_db_session
from infrastructure.minio_connection import minio_connection
from services.chat_service import ChatService
from api.routes.auth import current_active_user
from models.registered_user import RegisteredUser
from config.settings import settings
from schemas.chat_schema import PresignedUploadRequest, PresignedUploadResponse
from typing import Optional
import uuid
from datetime import datetime as dt

router = APIRouter(prefix="/chat", tags=["chat"])




@router.post("/get-upload-url", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    request: PresignedUploadRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get a presigned URL for uploading an image directly to MinIO
    
    This is the recommended method for uploading images as it:
    1. Doesn't load the image through the backend server
    2. Provides better performance and scalability
    3. Reduces server bandwidth usage
    
    Workflow:
    1. Client calls this endpoint with filename and content type
    2. Server validates friendship and returns presigned upload URL
    3. Client uploads image directly to MinIO using the presigned URL (PUT request)
    4. Client calls send_message Socket.IO event with image_path to save message
    
    Args:
        request: Upload request with friend nickname, filename, and content type
        session: Database session
        current_user: Authenticated user
        
    Returns:
        Presigned upload URL and object information
    """
    # Validate content type
    if request.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image type. Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
        )
    
    # Verify friendship exists
    friendship, _, _ = await ChatService.get_friendship(
        session=session,
        user_id=current_user.id,
        friend_nickname=request.friend_nickname
    )
    
    # Generate unique filename
    file_extension = request.filename.split('.')[-1] if '.' in request.filename else 'jpg'
    object_name = f"chat-images/{friendship.id_friendship}/{dt.utcnow().strftime('%Y%m%d')}/{uuid.uuid4()}.{file_extension}"
    
    # Generate presigned upload URL
    try:
        upload_url = minio_connection.get_presigned_upload_url(
            object_name=object_name,
            expires_minutes=15
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        )
    
    image_path = f"{settings.MINIO_BUCKET_NAME}/{object_name}"
    
    return PresignedUploadResponse(
        upload_url=upload_url,
        object_name=object_name,
        image_path=image_path,
        expires_in_minutes=15
    )


@router.get("/history/{friend_nickname}")
async def get_chat_history_http(
    friend_nickname: str,
    before_message_id: Optional[int] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session),
    current_user: RegisteredUser = Depends(current_active_user)
):
    """
    Get chat history via HTTP
    
    Args:
        friend_nickname: Nickname of the friend
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
        friend_nickname=friend_nickname,
        before_message_id=before_message_id,
        limit=limit
    )
    
    return history
