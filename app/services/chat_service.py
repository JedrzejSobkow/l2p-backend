# app/services/chat_service.py

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import joinedload
from models.chat_message import ChatMessage
from models.friend_chat import FriendChat
from models.friendship import Friendship
from models.registered_user import RegisteredUser
from schemas.chat_schema import ChatMessageResponse
from fastapi import HTTPException, status
import math


class ChatService:
    """Service for managing chat messages between friends"""
    
    @staticmethod
    async def get_or_create_friend_chat(
        session: AsyncSession,
        user_id: int,
        friend_nickname: str
    ) -> Tuple[FriendChat, RegisteredUser, RegisteredUser]:
        """
        Get or create a friend chat between two users
        
        Args:
            session: Database session
            user_id: ID of the current user
            friend_nickname: Nickname of the friend
            
        Returns:
            Tuple of (FriendChat, current_user, friend_user)
            
        Raises:
            HTTPException: If friend not found or not friends with current user
        """
        # Get friend by nickname
        friend_query = select(RegisteredUser).where(
            RegisteredUser.nickname == friend_nickname,
            RegisteredUser.is_active == True
        )
        result = await session.execute(friend_query)
        friend = result.scalar_one_or_none()
        
        if not friend:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with nickname '{friend_nickname}' not found"
            )
        
        # Get current user
        current_user_query = select(RegisteredUser).where(RegisteredUser.id == user_id)
        result = await session.execute(current_user_query)
        current_user = result.scalar_one_or_none()
        
        # Check if friendship exists (in either direction) and is accepted
        friendship_query = select(Friendship).where(
            and_(
                or_(
                    and_(
                        Friendship.user_id_1 == user_id,
                        Friendship.user_id_2 == friend.id
                    ),
                    and_(
                        Friendship.user_id_1 == friend.id,
                        Friendship.user_id_2 == user_id
                    )
                ),
                Friendship.status == "accepted"
            )
        ).options(joinedload(Friendship.friend_chat))
        
        result = await session.execute(friendship_query)
        friendship = result.scalar_one_or_none()
        
        if not friendship:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be friends with this user to chat"
            )
        
        # Get or create friend chat
        if friendship.friend_chat:
            friend_chat = friendship.friend_chat
        else:
            friend_chat = FriendChat(friendship_id=friendship.id_friendship)
            session.add(friend_chat)
            await session.commit()
            await session.refresh(friend_chat)
        
        return friend_chat, current_user, friend
    
    @staticmethod
    async def save_message(
        session: AsyncSession,
        friend_chat_id: int,
        sender_id: int,
        content: str
    ) -> ChatMessage:
        """
        Save a new chat message
        
        Args:
            session: Database session
            friend_chat_id: ID of the friend chat
            sender_id: ID of the message sender
            content: Message content
            
        Returns:
            Created chat message
        """
        message = ChatMessage(
            friend_chat_id=friend_chat_id,
            sender_id=sender_id,
            content=content
        )
        
        session.add(message)
        await session.commit()
        await session.refresh(message)
        
        return message
    
    @staticmethod
    async def get_chat_history(
        session: AsyncSession,
        user_id: int,
        friend_nickname: str,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ChatMessageResponse], int, str]:
        """
        Get chat history with a friend (paginated)
        
        Args:
            session: Database session
            user_id: ID of the current user
            friend_nickname: Nickname of the friend
            page: Page number (1-indexed)
            page_size: Number of messages per page
            
        Returns:
            Tuple of (list of messages, total count, friend_nickname)
        """
        # Get or verify friend chat exists
        friend_chat, current_user, friend = await ChatService.get_or_create_friend_chat(
            session, user_id, friend_nickname
        )
        
        # Count total messages
        count_query = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.friend_chat_id == friend_chat.id_friend_chat
        )
        count_result = await session.execute(count_query)
        total = count_result.scalar()
        
        # Get messages (ordered by newest first)
        offset = (page - 1) * page_size
        messages_query = select(ChatMessage).where(
            ChatMessage.friend_chat_id == friend_chat.id_friend_chat
        ).options(
            joinedload(ChatMessage.sender)
        ).order_by(ChatMessage.created_at.desc()).limit(page_size).offset(offset)
        
        result = await session.execute(messages_query)
        messages = result.scalars().all()
        
        # Transform to response format
        message_list = [
            ChatMessageResponse(
                sender_nickname=msg.sender.nickname,
                content=msg.content,
                created_at=msg.created_at,
                is_mine=(msg.sender_id == user_id)
            )
            for msg in messages
        ]
        
        return message_list, total, friend.nickname
    
    @staticmethod
    async def verify_chat_access(
        session: AsyncSession,
        friend_chat_id: int,
        user_id: int
    ) -> bool:
        """
        Verify that a user has access to a friend chat
        
        Args:
            session: Database session
            friend_chat_id: ID of the friend chat
            user_id: ID of the user to verify
            
        Returns:
            True if user has access, False otherwise
        """
        # Get friend chat with friendship
        query = select(FriendChat).where(
            FriendChat.id_friend_chat == friend_chat_id
        ).options(joinedload(FriendChat.friendship))
        
        result = await session.execute(query)
        friend_chat = result.scalar_one_or_none()
        
        if not friend_chat:
            return False
        
        friendship = friend_chat.friendship
        
        # Check if user is part of the friendship
        if friendship.user_id_1 == user_id or friendship.user_id_2 == user_id:
            return True
        
        return False
