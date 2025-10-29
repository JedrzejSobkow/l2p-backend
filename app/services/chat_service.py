# app/services/chat_service.py

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import joinedload, aliased
from models.chat_message import ChatMessage
from models.friendship import Friendship
from models.registered_user import RegisteredUser
from schemas.chat_schema import (
    ChatMessageResponse, 
    ChatHistoryResponse, 
    PresignedUploadResponse,
    ConversationResponse,
    RecentConversationsResponse
)
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
    ValidationException,
    InternalServerException
)
from infrastructure.minio_connection import minio_connection
from config.settings import settings
import uuid
from datetime import datetime as dt


class ChatService:
    """Service for managing chat messages between friends"""
    
    @staticmethod
    async def generate_image_upload_url(
        session: AsyncSession,
        user_id: int,
        friend_id: int,
        filename: str,
        content_type: str
    ) -> PresignedUploadResponse:
        """
        Generate presigned upload URL for chat image
        
        Args:
            session: Database session
            user_id: ID of the current user
            friend_id: ID of the friend
            filename: Original filename
            content_type: MIME type of the image
            
        Returns:
            Dictionary with upload_url, object_name, image_path, and expires_in_minutes
            
        Raises:
            ValidationException: If content type is invalid
            NotFoundException: If friendship not found
            ForbiddenException: If user not authorized
        """
        # Validate content type
        if content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise ValidationException(
                message="Invalid image type",
                details={
                    "content_type": content_type,
                    "allowed_types": settings.ALLOWED_IMAGE_TYPES
                }
            )
        
        # Verify friendship exists
        friendship, _, _ = await ChatService.get_friendship_by_id(
            session=session,
            user_id=user_id,
            friend_id=friend_id
        )
        
        # Generate unique filename
        file_extension = filename.split('.')[-1] if '.' in filename else 'jpg'
        object_name = f"chat-images/{friendship.id_friendship}/{dt.utcnow().strftime('%Y%m%d')}/{uuid.uuid4()}.{file_extension}"
        
        # Generate presigned URL
        try:
            upload_url = minio_connection.get_presigned_upload_url(
                object_name=object_name,
                expires_minutes=15
            )
        except Exception as e:
            raise InternalServerException(
                message="Failed to generate upload URL",
                details={"error": str(e)}
            )
        
        image_path = f"{settings.MINIO_BUCKET_NAME}/{object_name}"
        
        return {
            "upload_url": upload_url,
            "object_name": object_name,
            "image_path": image_path,
            "expires_in_minutes": 15
        }
    
    @staticmethod
    async def get_friendship_by_id(
        session: AsyncSession,
        user_id: int,
        friend_id: int
    ) -> Tuple[Friendship, RegisteredUser, RegisteredUser]:
        """
        Get friendship between two users using friend's ID
        
        Args:
            session: Database session
            user_id: ID of the current user
            friend_id: ID of the friend
            
        Returns:
            Tuple of (Friendship, current_user, friend_user)
            
        Raises:
            NotFoundException: If friend not found
            ForbiddenException: If not friends with current user
        """
        # Get both users in a single query using joined load
        users_query = select(RegisteredUser).where(
            RegisteredUser.id.in_([user_id, friend_id]),
            RegisteredUser.is_active == True
        )
        result = await session.execute(users_query)
        users = result.scalars().all()
        
        if len(users) != 2:
            raise NotFoundException(
                message="One or both users not found",
                details={"user_id": user_id, "friend_id": friend_id}
            )
        
        current_user = next((u for u in users if u.id == user_id), None)
        friend = next((u for u in users if u.id == friend_id), None)
        
        # Check if friendship exists (in either direction) and is accepted
        friendship_query = select(Friendship).where(
            and_(
                or_(
                    and_(
                        Friendship.user_id_1 == user_id,
                        Friendship.user_id_2 == friend_id
                    ),
                    and_(
                        Friendship.user_id_1 == friend_id,
                        Friendship.user_id_2 == user_id
                    )
                ),
                Friendship.status == "accepted"
            )
        )
        
        result = await session.execute(friendship_query)
        friendship = result.scalar_one_or_none()
        
        if not friendship:
            raise ForbiddenException(
                message="You must be friends with this user to chat",
                details={"user_id": user_id, "friend_id": friend_id}
            )
        
        return friendship, current_user, friend
    
    @staticmethod
    async def save_message(
        session: AsyncSession,
        friendship_id: int,
        sender_id: int,
        content: str = None,
        image_path: str = None
    ) -> ChatMessage:
        """
        Save a new chat message
        
        Args:
            session: Database session
            friendship_id: ID of the friendship
            sender_id: ID of the message sender
            content: Message content (optional if image is provided)
            image_path: Path to already uploaded image in MinIO
            
        Returns:
            Created chat message
        """
        # Validate that at least content or image is provided
        if not content and not image_path:
            raise BadRequestException(
                message="Either content or image must be provided"
            )
        
        # Create message
        message = ChatMessage(
            friendship_id=friendship_id,
            sender_id=sender_id,
            content=content,
            image_path=image_path
        )
        
        session.add(message)
        await session.commit()
        await session.refresh(message)
        
        return message
    
    @staticmethod
    async def get_chat_history(
        session: AsyncSession,
        user_id: int,
        friend_id: int,
        before_message_id: Optional[int] = None,
        limit: int = 50
    ) -> ChatHistoryResponse:
        """
        Get chat history with a friend (cursor-based pagination)
        
        This uses cursor-based pagination to avoid duplicates when new messages
        arrive between requests. The client should:
        1. First request: don't provide before_message_id
        2. Subsequent requests: provide the ID of the oldest message from previous response
        
        Args:
            session: Database session
            user_id: ID of the current user
            friend_id: ID of the friend
            before_message_id: Get messages before this message ID (for pagination)
            limit: Maximum number of messages to return
            
        Returns:
            ChatHistoryResponse with messages and pagination info
        """
        # Get friendship
        friendship, current_user, friend = await ChatService.get_friendship_by_id(
            session, user_id, friend_id
        )
        
        # Count total messages (useful for UI)
        count_query = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.friendship_id == friendship.id_friendship
        )
        count_result = await session.execute(count_query)
        total = count_result.scalar()
        
        # Build query for messages
        messages_query = select(ChatMessage).where(
            ChatMessage.friendship_id == friendship.id_friendship
        )
        
        # Apply cursor if provided
        if before_message_id is not None:
            messages_query = messages_query.where(
                ChatMessage.id_message < before_message_id
            )
        
        # Order by ID descending (newest first) and limit
        messages_query = messages_query.options(
            joinedload(ChatMessage.sender)
        ).order_by(ChatMessage.id_message.desc()).limit(limit)
        
        result = await session.execute(messages_query)
        messages = result.scalars().all()
        
        # Transform to response format using ChatMessageResponse
        message_list = [
            ChatMessageResponse(
                id=msg.id_message,
                sender_id=msg.sender_id,
                sender_nickname=msg.sender.nickname,
                content=msg.content,
                image_url=ChatService._get_image_url(msg.image_path) if msg.image_path else None,
                created_at=msg.created_at.isoformat(),
                is_mine=(msg.sender_id == user_id)
            )
            for msg in messages
        ]
        
        # Determine if there are more messages
        has_more = len(messages) == limit
        
        # Get the cursor for next page (ID of the oldest message in current batch)
        next_cursor = messages[-1].id_message if messages else None
        
        return ChatHistoryResponse(
            messages=message_list,
            total=total,
            limit=limit,
            has_more=has_more,
            next_cursor=next_cursor,
            friend_user_id=friend.id,
            friend_nickname=friend.nickname
        )
    
    @staticmethod
    async def verify_chat_access(
        session: AsyncSession,
        friendship_id: int,
        user_id: int
    ) -> bool:
        """
        Verify that a user has access to a friendship chat
        
        Args:
            session: Database session
            friendship_id: ID of the friendship
            user_id: ID of the user to verify
            
        Returns:
            True if user has access, False otherwise
        """
        # Get friendship
        query = select(Friendship).where(
            Friendship.id_friendship == friendship_id
        )
        
        result = await session.execute(query)
        friendship = result.scalar_one_or_none()
        
        if not friendship:
            return False
        
        # Check if user is part of the friendship
        if friendship.user_id_1 == user_id or friendship.user_id_2 == user_id:
            return True
        
        return False
    
    @staticmethod
    async def get_recent_conversations(
        session: AsyncSession,
        user_id: int,
        limit: int = 20
    ) -> RecentConversationsResponse:
        """
        Get user's recent conversations sorted by last message time
        
        Args:
            session: Database session
            user_id: ID of the current user
            limit: Maximum number of conversations to return
            
        Returns:
            RecentConversationsResponse with list of conversations
        """
        # Subquery to get the last message for each friendship
        last_message_subq = (
            select(
                ChatMessage.friendship_id,
                func.max(ChatMessage.created_at).label('last_message_time')
            )
            .group_by(ChatMessage.friendship_id)
            .subquery()
        )
        
        # Get friendships where user is involved
        User1 = aliased(RegisteredUser)
        User2 = aliased(RegisteredUser)
        
        query = (
            select(
                Friendship,
                User1,
                User2,
                last_message_subq.c.last_message_time,
                ChatMessage.content.label('last_message_content'),
                ChatMessage.sender_id.label('last_sender_id')
            )
            .join(User1, Friendship.user_id_1 == User1.id)
            .join(User2, Friendship.user_id_2 == User2.id)
            .outerjoin(
                last_message_subq,
                Friendship.id_friendship == last_message_subq.c.friendship_id
            )
            .outerjoin(
                ChatMessage,
                and_(
                    ChatMessage.friendship_id == Friendship.id_friendship,
                    ChatMessage.created_at == last_message_subq.c.last_message_time
                )
            )
            .where(
                and_(
                    or_(
                        Friendship.user_id_1 == user_id,
                        Friendship.user_id_2 == user_id
                    ),
                    Friendship.status == "accepted"
                )
            )
            .order_by(desc(last_message_subq.c.last_message_time))
            .limit(limit)
        )
        
        result = await session.execute(query)
        rows = result.all()
        
        conversations = []
        for row in rows:
            friendship, user1, user2, last_time, last_content, last_sender = row
            
            # Determine who is the friend (not the current user)
            if friendship.user_id_1 == user_id:
                friend = user2
            else:
                friend = user1
            
            # Count unread messages (messages where sender is NOT current user and created after last read)
            # For now, we'll just return all info without read tracking
            unread_count = 0  # TODO: Implement read tracking if needed
            
            conversations.append(ConversationResponse(
                friendship_id=friendship.id_friendship,
                friend_id=friend.id,
                friend_nickname=friend.nickname,
                friend_email=friend.email,
                last_message_time=last_time.isoformat() if last_time else None,
                last_message_content=last_content,
                last_message_is_mine=last_sender == user_id if last_sender else None,
                unread_count=unread_count
            ))
        
        return RecentConversationsResponse(conversations=conversations)
    
    @staticmethod
    def validate_image_path(image_path: str, friendship_id: int, verify_exists: bool = True) -> bool:
        """
        Validate that an image path is legitimate for the given friendship
        
        Checks:
        1. Path format matches expected pattern: {bucket}/chat-images/{friendship_id}/{date}/{uuid}.{ext}
        2. Friendship ID in path matches the current friendship
        3. File exists in MinIO (optional, controlled by verify_exists)
        
        Args:
            image_path: Path to validate (format: bucket/chat-images/...)
            friendship_id: ID of the current friendship
            verify_exists: Whether to check if file actually exists in MinIO (default True)
            
        Returns:
            True if valid
            
        Raises:
            ValidationException: If path is invalid
            ForbiddenException: If path doesn't match friendship
            NotFoundException: If image file not found
        """
        if not image_path:
            return True  # No image is fine
        
        # Expected format: {bucket}/chat-images/{friendship_id}/{date}/{uuid}.{ext}
        parts = image_path.split('/')
        
        # Validate structure
        if len(parts) < 5:
            raise ValidationException(
                message="Invalid image_path format",
                details={"image_path": image_path}
            )
        
        # Check bucket name
        if parts[0] != settings.MINIO_BUCKET_NAME:
            raise ValidationException(
                message="Invalid bucket in image_path",
                details={"expected_bucket": settings.MINIO_BUCKET_NAME, "actual_bucket": parts[0]}
            )
        
        # Check it's in chat-images directory
        if parts[1] != "chat-images":
            raise ValidationException(
                message="Invalid path: must be in chat-images directory",
                details={"image_path": image_path}
            )
        
        # Check friendship ID matches
        try:
            path_friendship_id = int(parts[2])
        except ValueError:
            raise ValidationException(
                message="Invalid friendship_id in image_path",
                details={"image_path": image_path}
            )
        
        if path_friendship_id != friendship_id:
            raise ForbiddenException(
                message="Image path does not belong to this conversation",
                details={"expected_friendship_id": friendship_id, "actual_friendship_id": path_friendship_id}
            )
        
        # Optionally verify file exists in MinIO
        if verify_exists:
            object_name = image_path.replace(f"{settings.MINIO_BUCKET_NAME}/", "")
            try:
                if not minio_connection.file_exists(object_name):
                    raise NotFoundException(
                        message="Image file not found in storage",
                        details={"object_name": object_name}
                    )
            except (NotFoundException, ValidationException, ForbiddenException):
                raise  # Re-raise domain exceptions
            except Exception as e:
                # Log but don't fail on storage check errors
                import logging
                logging.warning(f"Could not verify file existence for {object_name}: {e}")
        
        return True
    
    @staticmethod
    async def process_send_message(
        session: AsyncSession,
        user_id: int,
        friend_user_id: int,
        content: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> dict:
        """
        Process sending a message
        
        Args:
            session: Database session
            user_id: ID of the message sender
            friend_user_id: ID of the recipient
            content: Message content (optional if image is provided)
            image_path: Path to uploaded image (optional if content is provided)
            
        Returns:
            Dictionary containing message data, sender info, and recipient info
            
        Raises:
            ValidationException: If validation fails
            NotFoundException: If users not found
            ForbiddenException: If users are not friends
        """
        # Get friendship and user details
        friendship, current_user, friend = await ChatService.get_friendship_by_id(
            session=session,
            user_id=user_id,
            friend_id=friend_user_id
        )
        
        # Validate image_path if provided
        if image_path:
            ChatService.validate_image_path(image_path, friendship.id_friendship)
        
        # Save message to database
        message = await ChatService.save_message(
            session=session,
            friendship_id=friendship.id_friendship,
            sender_id=user_id,
            content=content,
            image_path=image_path
        )
        
        # Get image URL if image_path is provided
        image_url = None
        if image_path:
            image_url = ChatService._get_image_url(image_path)
        
        # Return all data needed for socket emission
        return {
            'message': {
                'id': message.id_message,
                'sender_id': user_id,
                'sender_nickname': current_user.nickname,
                'content': content,
                'image_url': image_url,
                'created_at': message.created_at.isoformat(),
                'friendship_id': friendship.id_friendship
            },
            'sender': {
                'id': current_user.id,
                'nickname': current_user.nickname
            },
            'recipient': {
                'id': friend.id,
                'nickname': friend.nickname
            }
        }
    
    @staticmethod
    def _get_image_url(image_path: str) -> Optional[str]:
        """
        Get a presigned URL for an image stored in MinIO
        
        Returns a temporary, secure URL that expires after IMAGE_URL_EXPIRY_HOURS.
        
        Args:
            image_path: Path to the image in MinIO (format: bucket/object_name)
            
        Returns:
            Presigned URL to access the image (valid for 24 hours by default)
        """
        if not image_path:
            return None
        
        # Extract object name from path (remove bucket prefix if present)
        object_name = image_path.replace(f"{settings.MINIO_BUCKET_NAME}/", "")
        
        try:
            return minio_connection.get_file_url(
                object_name,
                expires_hours=settings.IMAGE_URL_EXPIRY_HOURS
            )
        except Exception as e:
            # Log error but don't fail the whole request
            import logging
            logging.error(f"Failed to get image URL for {image_path}: {e}")
            return None
