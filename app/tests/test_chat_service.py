"""
Unit tests for ChatService

Tests cover:
- Generating image upload URLs
- Getting friendship by ID
- Saving messages
- Getting chat history
- Verifying chat access
- Getting recent conversations
- Validating image paths
- Processing send message
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.registered_user import RegisteredUser
from models.friendship import Friendship
from models.chat_message import ChatMessage
from services.chat_service import ChatService
from exceptions.domain_exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
    ValidationException,
    InternalServerException
)
from datetime import datetime


@pytest.mark.unit
class TestGenerateImageUploadUrl:
    """Test cases for generate_image_upload_url method"""
    
    @patch('services.chat_service.minio_connection')
    async def test_generate_upload_url_success(
        self,
        mock_minio,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test successfully generating an image upload URL"""
        # Arrange
        mock_minio.get_presigned_upload_url.return_value = "https://minio.example.com/upload/test.jpg"
        
        # Act
        result = await ChatService.generate_image_upload_url(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id,
            filename="photo.jpg",
            content_type="image/jpeg"
        )
        
        # Assert
        assert result is not None
        assert "upload_url" in result
        assert "object_name" in result
        assert "image_path" in result
        assert "expires_in_minutes" in result
        assert result["upload_url"] == "https://minio.example.com/upload/test.jpg"
        assert f"chat-images/{accepted_friendship.id_friendship}" in result["object_name"]
        assert result["expires_in_minutes"] == 15
        mock_minio.get_presigned_upload_url.assert_called_once()
    
    async def test_generate_upload_url_invalid_content_type(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test generating upload URL with invalid content type"""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            await ChatService.generate_image_upload_url(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=test_user_3.id,
                filename="document.pdf",
                content_type="application/pdf"
            )
        
        assert exc_info.value.message == "Invalid image type"
        assert "content_type" in exc_info.value.details
    
    async def test_generate_upload_url_not_friends(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test generating upload URL when users are not friends"""
        # Act & Assert
        with pytest.raises(ForbiddenException) as exc_info:
            await ChatService.generate_image_upload_url(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=test_user_3.id,
                filename="photo.jpg",
                content_type="image/jpeg"
            )
        
        assert exc_info.value.message == "You must be friends with this user to chat"
    
    @patch('services.chat_service.minio_connection')
    async def test_generate_upload_url_minio_error(
        self,
        mock_minio,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test generating upload URL when MinIO fails"""
        # Arrange
        mock_minio.get_presigned_upload_url.side_effect = Exception("MinIO connection error")
        
        # Act & Assert
        with pytest.raises(InternalServerException) as exc_info:
            await ChatService.generate_image_upload_url(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=test_user_3.id,
                filename="photo.jpg",
                content_type="image/jpeg"
            )
        
        assert exc_info.value.message == "Failed to generate upload URL"


@pytest.mark.unit
class TestGetFriendshipById:
    """Test cases for get_friendship_by_id method"""
    
    async def test_get_friendship_success(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test successfully getting a friendship"""
        # Act
        friendship, current_user, friend = await ChatService.get_friendship_by_id(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id
        )
        
        # Assert
        assert friendship is not None
        assert friendship.id_friendship == accepted_friendship.id_friendship
        assert current_user.id == test_user_1.id
        assert friend.id == test_user_3.id
    
    async def test_get_friendship_reverse_direction(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting friendship in reverse direction"""
        # Act
        friendship, current_user, friend = await ChatService.get_friendship_by_id(
            session=db_session,
            user_id=test_user_3.id,
            friend_id=test_user_1.id
        )
        
        # Assert
        assert friendship is not None
        assert friendship.id_friendship == accepted_friendship.id_friendship
        assert current_user.id == test_user_3.id
        assert friend.id == test_user_1.id
    
    async def test_get_friendship_user_not_found(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test getting friendship when user doesn't exist"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await ChatService.get_friendship_by_id(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=99999
            )
        
        assert exc_info.value.message == "One or both users not found"
    
    async def test_get_friendship_inactive_user(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        inactive_user: RegisteredUser
    ):
        """Test getting friendship with inactive user"""
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            await ChatService.get_friendship_by_id(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=inactive_user.id
            )
        
        assert exc_info.value.message == "One or both users not found"
    
    async def test_get_friendship_not_friends(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting friendship when users are not friends"""
        # Act & Assert
        with pytest.raises(ForbiddenException) as exc_info:
            await ChatService.get_friendship_by_id(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=test_user_3.id
            )
        
        assert exc_info.value.message == "You must be friends with this user to chat"
    
    async def test_get_friendship_pending_status(
        self,
        db_session: AsyncSession,
        pending_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting friendship when status is pending"""
        # Act & Assert
        with pytest.raises(ForbiddenException) as exc_info:
            await ChatService.get_friendship_by_id(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=test_user_3.id
            )
        
        assert exc_info.value.message == "You must be friends with this user to chat"


@pytest.mark.unit
class TestSaveMessage:
    """Test cases for save_message method"""
    
    async def test_save_message_with_content(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser
    ):
        """Test saving a text message"""
        # Act
        message = await ChatService.save_message(
            session=db_session,
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_1.id,
            content="Hello, friend!"
        )
        
        # Assert
        assert message is not None
        assert message.id_message is not None
        assert message.friendship_id == accepted_friendship.id_friendship
        assert message.sender_id == test_user_1.id
        assert message.content == "Hello, friend!"
        assert message.image_path is None
    
    async def test_save_message_with_image(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser
    ):
        """Test saving an image message"""
        # Act
        message = await ChatService.save_message(
            session=db_session,
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_1.id,
            image_path="l2p-bucket/chat-images/1/20231029/test.jpg"
        )
        
        # Assert
        assert message is not None
        assert message.content is None
        assert message.image_path == "l2p-bucket/chat-images/1/20231029/test.jpg"
    
    async def test_save_message_with_both(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser
    ):
        """Test saving a message with both content and image"""
        # Act
        message = await ChatService.save_message(
            session=db_session,
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_1.id,
            content="Check this out!",
            image_path="l2p-bucket/chat-images/1/20231029/test.jpg"
        )
        
        # Assert
        assert message is not None
        assert message.content == "Check this out!"
        assert message.image_path == "l2p-bucket/chat-images/1/20231029/test.jpg"
    
    async def test_save_message_no_content_or_image(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser
    ):
        """Test saving a message without content or image"""
        # Act & Assert
        with pytest.raises(BadRequestException) as exc_info:
            await ChatService.save_message(
                session=db_session,
                friendship_id=accepted_friendship.id_friendship,
                sender_id=test_user_1.id
            )
        
        assert exc_info.value.message == "Either content or image must be provided"


@pytest.mark.unit
class TestGetChatHistory:
    """Test cases for get_chat_history method"""
    
    async def test_get_chat_history_empty(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting chat history when no messages exist"""
        # Act
        result = await ChatService.get_chat_history(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id
        )
        
        # Assert
        assert result is not None
        assert len(result.messages) == 0
        assert result.total == 0
        assert result.has_more is False
        assert result.next_cursor is None
        assert result.friend_user_id == test_user_3.id
        assert result.friend_nickname == test_user_3.nickname
    
    async def test_get_chat_history_with_messages(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting chat history with messages"""
        # Arrange - Create some messages
        for i in range(3):
            msg = ChatMessage(
                friendship_id=accepted_friendship.id_friendship,
                sender_id=test_user_1.id if i % 2 == 0 else test_user_3.id,
                content=f"Message {i+1}"
            )
            db_session.add(msg)
        await db_session.commit()
        
        # Act
        result = await ChatService.get_chat_history(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id
        )
        
        # Assert
        assert len(result.messages) == 3
        assert result.total == 3
        assert result.has_more is False
        # Messages should be ordered newest first
        assert result.messages[0].content == "Message 3"
        assert result.messages[2].content == "Message 1"
    
    async def test_get_chat_history_pagination(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test chat history pagination"""
        # Arrange - Create messages
        for i in range(10):
            msg = ChatMessage(
                friendship_id=accepted_friendship.id_friendship,
                sender_id=test_user_1.id,
                content=f"Message {i+1}"
            )
            db_session.add(msg)
        await db_session.commit()
        
        # Act - Get first page
        result1 = await ChatService.get_chat_history(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id,
            limit=5
        )
        
        # Assert first page
        assert len(result1.messages) == 5
        assert result1.has_more is True
        assert result1.next_cursor is not None
        
        # Act - Get second page
        result2 = await ChatService.get_chat_history(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id,
            before_message_id=result1.next_cursor,
            limit=5
        )
        
        # Assert second page - should get the remaining 5 messages with no more after
        assert len(result2.messages) == 5
        assert result2.has_more is False
        assert result2.next_cursor is None
        
        # Verify no overlap
        first_page_ids = {msg.id for msg in result1.messages}
        second_page_ids = {msg.id for msg in result2.messages}
        assert first_page_ids.isdisjoint(second_page_ids)
    
    async def test_get_chat_history_is_mine_flag(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test that is_mine flag is set correctly"""
        # Arrange
        msg1 = ChatMessage(
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_1.id,
            content="My message"
        )
        msg2 = ChatMessage(
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_3.id,
            content="Friend's message"
        )
        db_session.add(msg1)
        db_session.add(msg2)
        await db_session.commit()
        
        # Act
        result = await ChatService.get_chat_history(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id
        )
        
        # Assert
        for msg in result.messages:
            if msg.sender_id == test_user_1.id:
                assert msg.is_mine is True
            else:
                assert msg.is_mine is False
    
    @patch('services.chat_service.ChatService._get_image_url')
    async def test_get_chat_history_with_image(
        self,
        mock_get_image_url,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting chat history with image messages"""
        # Arrange
        mock_get_image_url.return_value = "https://minio.example.com/image.jpg"
        msg = ChatMessage(
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_1.id,
            content="Check this photo!",
            image_path="l2p-bucket/chat-images/1/20231029/test.jpg"
        )
        db_session.add(msg)
        await db_session.commit()
        
        # Act
        result = await ChatService.get_chat_history(
            session=db_session,
            user_id=test_user_1.id,
            friend_id=test_user_3.id
        )
        
        # Assert
        assert len(result.messages) == 1
        assert result.messages[0].image_url == "https://minio.example.com/image.jpg"
        mock_get_image_url.assert_called_once()
    
    async def test_get_chat_history_not_friends(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting chat history when not friends"""
        # Act & Assert
        with pytest.raises(ForbiddenException):
            await ChatService.get_chat_history(
                session=db_session,
                user_id=test_user_1.id,
                friend_id=test_user_3.id
            )


@pytest.mark.unit
class TestVerifyChatAccess:
    """Test cases for verify_chat_access method"""
    
    async def test_verify_chat_access_user1(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser
    ):
        """Test verifying access for user1 in friendship"""
        # Act
        result = await ChatService.verify_chat_access(
            session=db_session,
            friendship_id=accepted_friendship.id_friendship,
            user_id=test_user_1.id
        )
        
        # Assert
        assert result is True
    
    async def test_verify_chat_access_user2(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_3: RegisteredUser
    ):
        """Test verifying access for user2 in friendship"""
        # Act
        result = await ChatService.verify_chat_access(
            session=db_session,
            friendship_id=accepted_friendship.id_friendship,
            user_id=test_user_3.id
        )
        
        # Assert
        assert result is True
    
    async def test_verify_chat_access_unauthorized_user(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_2: RegisteredUser
    ):
        """Test verifying access for user not in friendship"""
        # Act
        result = await ChatService.verify_chat_access(
            session=db_session,
            friendship_id=accepted_friendship.id_friendship,
            user_id=test_user_2.id
        )
        
        # Assert
        assert result is False
    
    async def test_verify_chat_access_nonexistent_friendship(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test verifying access for non-existent friendship"""
        # Act
        result = await ChatService.verify_chat_access(
            session=db_session,
            friendship_id=99999,
            user_id=test_user_1.id
        )
        
        # Assert
        assert result is False


@pytest.mark.unit
class TestGetRecentConversations:
    """Test cases for get_recent_conversations method"""
    
    async def test_get_recent_conversations_empty(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test getting recent conversations when none exist"""
        # Act
        result = await ChatService.get_recent_conversations(
            session=db_session,
            user_id=test_user_1.id
        )
        
        # Assert
        assert result is not None
        assert len(result.conversations) == 0
    
    async def test_get_recent_conversations_with_messages(
        self,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test getting recent conversations with messages"""
        # Arrange - Create a message
        msg = ChatMessage(
            friendship_id=accepted_friendship.id_friendship,
            sender_id=test_user_1.id,
            content="Hello!"
        )
        db_session.add(msg)
        await db_session.commit()
        
        # Act
        result = await ChatService.get_recent_conversations(
            session=db_session,
            user_id=test_user_1.id
        )
        
        # Assert
        assert len(result.conversations) == 1
        conv = result.conversations[0]
        assert conv.friendship_id == accepted_friendship.id_friendship
        assert conv.friend_id == test_user_3.id
        assert conv.friend_nickname == test_user_3.nickname
        assert conv.last_message_content == "Hello!"
        assert conv.last_message_is_mine is True
    
    async def test_get_recent_conversations_sorted_by_time(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test that conversations are sorted by last message time"""
        # Arrange - Create two accepted friendships
        friendship1 = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_2.id,
            status="accepted"
        )
        friendship2 = Friendship(
            user_id_1=test_user_1.id,
            user_id_2=test_user_3.id,
            status="accepted"
        )
        db_session.add(friendship1)
        db_session.add(friendship2)
        await db_session.commit()
        await db_session.refresh(friendship1)
        await db_session.refresh(friendship2)
        
        # Create older message in friendship2
        msg1 = ChatMessage(
            friendship_id=friendship2.id_friendship,
            sender_id=test_user_3.id,
            content="Old message"
        )
        db_session.add(msg1)
        await db_session.commit()
        
        # Create newer message in friendship1
        msg2 = ChatMessage(
            friendship_id=friendship1.id_friendship,
            sender_id=test_user_2.id,
            content="New message"
        )
        db_session.add(msg2)
        await db_session.commit()
        
        # Act
        result = await ChatService.get_recent_conversations(
            session=db_session,
            user_id=test_user_1.id
        )
        
        # Assert - Most recent should be first (friendship1 with test_user_2 had newer message)
        assert len(result.conversations) == 2
        assert result.conversations[0].friend_id == test_user_2.id
        assert result.conversations[1].friend_id == test_user_3.id
    
    async def test_get_recent_conversations_friend_as_user2(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_2: RegisteredUser
    ):
        """Test that conversations work when friend is user2 in the friendship"""
        # Arrange - Create friendship where current user is user_id_2
        friendship = Friendship(
            user_id_1=test_user_2.id,  # Friend is user1
            user_id_2=test_user_1.id,  # Current user is user2
            status="accepted"
        )
        db_session.add(friendship)
        await db_session.commit()
        await db_session.refresh(friendship)
        
        # Create a message
        msg = ChatMessage(
            friendship_id=friendship.id_friendship,
            sender_id=test_user_2.id,
            content="Hello from user2 position!"
        )
        db_session.add(msg)
        await db_session.commit()
        
        # Act - Get conversations for test_user_1 (who is user_id_2 in the friendship)
        result = await ChatService.get_recent_conversations(
            session=db_session,
            user_id=test_user_1.id
        )
        
        # Assert - Should correctly identify test_user_2 as the friend
        assert len(result.conversations) == 1
        conv = result.conversations[0]
        assert conv.friend_id == test_user_2.id
        assert conv.friend_nickname == test_user_2.nickname
        assert conv.last_message_content == "Hello from user2 position!"
        assert conv.last_message_is_mine is False
    
    async def test_get_recent_conversations_limit(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser
    ):
        """Test conversation limit parameter"""
        # Arrange - Create multiple friendships
        for i in range(5):
            user = RegisteredUser(
                email=f"friend{i}@test.com",
                hashed_password="hashed",
                nickname=f"Friend{i}",
                is_active=True,
                is_superuser=False,
                is_verified=True
            )
            db_session.add(user)
        await db_session.commit()
        
        # Get users and create friendships
        result = await db_session.execute(
            select(RegisteredUser).where(RegisteredUser.nickname.like("Friend%"))
        )
        friends = result.scalars().all()
        
        for friend in friends:
            friendship = Friendship(
                user_id_1=test_user_1.id,
                user_id_2=friend.id,
                status="accepted"
            )
            db_session.add(friendship)
        await db_session.commit()
        
        # Act
        result = await ChatService.get_recent_conversations(
            session=db_session,
            user_id=test_user_1.id,
            limit=3
        )
        
        # Assert
        assert len(result.conversations) == 3


@pytest.mark.unit
class TestValidateImagePath:
    """Test cases for validate_image_path method"""
    
    def test_validate_image_path_none(self):
        """Test validating None image path"""
        # Act
        result = ChatService.validate_image_path(None, 1, verify_exists=False)
        
        # Assert
        assert result is True
    
    def test_validate_image_path_valid(self):
        """Test validating a valid image path"""
        # Act
        result = ChatService.validate_image_path(
            "l2p-bucket/chat-images/123/20231029/uuid.jpg",
            123,
            verify_exists=False
        )
        
        # Assert
        assert result is True
    
    def test_validate_image_path_invalid_format(self):
        """Test validating image path with invalid format"""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ChatService.validate_image_path(
                "invalid/path",
                123,
                verify_exists=False
            )
        
        assert exc_info.value.message == "Invalid image_path format"
    
    def test_validate_image_path_wrong_bucket(self):
        """Test validating image path with wrong bucket"""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ChatService.validate_image_path(
                "wrong-bucket/chat-images/123/20231029/uuid.jpg",
                123,
                verify_exists=False
            )
        
        assert exc_info.value.message == "Invalid bucket in image_path"
    
    def test_validate_image_path_wrong_directory(self):
        """Test validating image path not in chat-images directory"""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ChatService.validate_image_path(
                "l2p-bucket/wrong-dir/123/20231029/uuid.jpg",
                123,
                verify_exists=False
            )
        
        assert exc_info.value.message == "Invalid path: must be in chat-images directory"
    
    def test_validate_image_path_wrong_friendship_id(self):
        """Test validating image path with wrong friendship ID"""
        # Act & Assert
        with pytest.raises(ForbiddenException) as exc_info:
            ChatService.validate_image_path(
                "l2p-bucket/chat-images/456/20231029/uuid.jpg",
                123,
                verify_exists=False
            )
        
        assert exc_info.value.message == "Image path does not belong to this conversation"
    
    def test_validate_image_path_invalid_friendship_id(self):
        """Test validating image path with non-numeric friendship ID"""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ChatService.validate_image_path(
                "l2p-bucket/chat-images/abc/20231029/uuid.jpg",
                123,
                verify_exists=False
            )
        
        assert exc_info.value.message == "Invalid friendship_id in image_path"
    
    @patch('services.chat_service.minio_connection')
    def test_validate_image_path_file_not_exists(self, mock_minio):
        """Test validating image path when file doesn't exist"""
        # Arrange
        mock_minio.file_exists.return_value = False
        
        # Act & Assert
        with pytest.raises(NotFoundException) as exc_info:
            ChatService.validate_image_path(
                "l2p-bucket/chat-images/123/20231029/uuid.jpg",
                123,
                verify_exists=True
            )
        
        assert exc_info.value.message == "Image file not found in storage"
    
    @patch('services.chat_service.minio_connection')
    def test_validate_image_path_file_existence_check_error(self, mock_minio):
        """Test validating image path when file existence check raises non-domain exception"""
        # Arrange - Mock file_exists to raise a generic exception (e.g., network error)
        mock_minio.file_exists.side_effect = Exception("Network error checking file")
        
        # Act - Should log warning but not raise exception
        result = ChatService.validate_image_path(
            "l2p-bucket/chat-images/123/20231029/uuid.jpg",
            123,
            verify_exists=True
        )
        
        # Assert - Should return True despite the error (graceful degradation)
        assert result is True
    
    @patch('services.chat_service.minio_connection')
    def test_validate_image_path_file_exists_success(self, mock_minio):
        """Test validating image path when file exists"""
        # Arrange
        mock_minio.file_exists.return_value = True
        
        # Act
        result = ChatService.validate_image_path(
            "l2p-bucket/chat-images/123/20231029/uuid.jpg",
            123,
            verify_exists=True
        )
        
        # Assert
        assert result is True
        mock_minio.file_exists.assert_called_once_with("chat-images/123/20231029/uuid.jpg")


@pytest.mark.unit
class TestProcessSendMessage:
    """Test cases for process_send_message method"""
    
    @patch('services.chat_service.ChatService._get_image_url')
    async def test_process_send_message_text_only(
        self,
        mock_get_image_url,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test processing a text-only message"""
        # Act
        result = await ChatService.process_send_message(
            session=db_session,
            user_id=test_user_1.id,
            friend_user_id=test_user_3.id,
            content="Hello, friend!"
        )

        # Assert
        assert result is not None
        assert "message" in result
        assert "sender" in result
        assert "recipient" in result
        assert result["message"]["content"] == "Hello, friend!"
        assert result["message"]["sender_id"] == test_user_1.id
        assert result["message"]["image_url"] is None
        assert result["sender"]["identifier"] == f"user:{test_user_1.id}"
        assert result["recipient"]["identifier"] == f"user:{test_user_3.id}"
    
    @patch('services.chat_service.ChatService.validate_image_path')
    @patch('services.chat_service.ChatService._get_image_url')
    async def test_process_send_message_with_image(
        self,
        mock_get_image_url,
        mock_validate,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test processing a message with image"""
        # Arrange
        mock_validate.return_value = True
        mock_get_image_url.return_value = "https://minio.example.com/image.jpg"
        image_path = f"l2p-bucket/chat-images/{accepted_friendship.id_friendship}/20231029/uuid.jpg"
        
        # Act
        result = await ChatService.process_send_message(
            session=db_session,
            user_id=test_user_1.id,
            friend_user_id=test_user_3.id,
            content="Check this out!",
            image_path=image_path
        )
        
        # Assert
        assert result["message"]["image_url"] == "https://minio.example.com/image.jpg"
        mock_validate.assert_called_once()
    
    async def test_process_send_message_not_friends(
        self,
        db_session: AsyncSession,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test processing message when users are not friends"""
        # Act & Assert
        with pytest.raises(ForbiddenException):
            await ChatService.process_send_message(
                session=db_session,
                user_id=test_user_1.id,
                friend_user_id=test_user_3.id,
                content="Hello!"
            )
    
    @patch('services.chat_service.ChatService.validate_image_path')
    async def test_process_send_message_invalid_image(
        self,
        mock_validate,
        db_session: AsyncSession,
        accepted_friendship: Friendship,
        test_user_1: RegisteredUser,
        test_user_3: RegisteredUser
    ):
        """Test processing message with invalid image path"""
        # Arrange
        mock_validate.side_effect = ValidationException("Invalid image path")
        
        # Act & Assert
        with pytest.raises(ValidationException):
            await ChatService.process_send_message(
                session=db_session,
                user_id=test_user_1.id,
                friend_user_id=test_user_3.id,
                image_path="invalid/path"
            )


@pytest.mark.unit
class TestGetImageUrl:
    """Test cases for _get_image_url method"""
    
    @patch('services.chat_service.minio_connection')
    def test_get_image_url_success(self, mock_minio):
        """Test successfully getting an image URL"""
        # Arrange
        mock_minio.get_file_url.return_value = "https://minio.example.com/image.jpg"
        
        # Act
        result = ChatService._get_image_url("l2p-bucket/chat-images/123/uuid.jpg")
        
        # Assert
        assert result == "https://minio.example.com/image.jpg"
        mock_minio.get_file_url.assert_called_once_with(
            "chat-images/123/uuid.jpg",
            expires_hours=24
        )
    
    def test_get_image_url_none(self):
        """Test getting image URL for None path"""
        # Act
        result = ChatService._get_image_url(None)
        
        # Assert
        assert result is None
    
    @patch('services.chat_service.minio_connection')
    def test_get_image_url_error(self, mock_minio):
        """Test getting image URL when MinIO fails"""
        # Arrange
        mock_minio.get_file_url.side_effect = Exception("MinIO error")
        
        # Act
        result = ChatService._get_image_url("l2p-bucket/chat-images/123/uuid.jpg")
        
        # Assert - Should return None instead of raising
        assert result is None
