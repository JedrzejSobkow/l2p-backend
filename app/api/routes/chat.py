# app/api/routes/chat.py

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict
from models.registered_user import RegisteredUser
from schemas.chat_schema import ChatHistoryResponse
from services.chat_service import ChatService
from infrastructure.postgres_connection import postgres_connection
from api.routes.auth import current_active_user
import json
import math
from models.registered_user import RegisteredUser as DBRegisteredUser


# Dependency to get database session
async def get_db_session():
    """Get database session"""
    if not postgres_connection.session_factory:
        raise RuntimeError("Database not connected")
    
    async with postgres_connection.session_factory() as session:
        yield session


# Create router
chat_router = APIRouter(prefix="/chat", tags=["Chat"])


class ConnectionManager:
    """Manages WebSocket connections for real-time chat"""
    
    def __init__(self):
        # Maps user_id to their WebSocket connection
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect a user's WebSocket"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: int):
        """Disconnect a user's WebSocket"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json(message)
            except Exception:
                # Connection is broken, remove it
                self.disconnect(user_id)


# Global connection manager instance
manager = ConnectionManager()


@chat_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time chat
    
    Connect with: ws://host/chat/ws?token=<your_jwt_token>
    
    Send messages as JSON:
    {
        "friend_nickname": "friend_username",
        "content": "Hello!"
    }
    
    Receive messages as JSON:
    {
        "type": "message",
        "sender_nickname": "friend_username",
        "content": "Hello!",
        "created_at": "2025-10-21T12:00:00",
        "is_mine": false
    }
    or
    {
        "type": "error",
        "detail": "Error message"
    }
    """
    # Authenticate user from token
    from infrastructure.auth_config import get_jwt_strategy
    from jose import jwt, JWTError
    from config.settings import settings
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        user_email = payload.get("sub")
        
        if not user_email:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Get database session
        async with postgres_connection.session_factory() as session:
            # Get the user from database
            from sqlalchemy import select
            db_user_query = select(DBRegisteredUser).where(
                DBRegisteredUser.email == user_email,
                DBRegisteredUser.is_active == True
            )
            result = await session.execute(db_user_query)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            user_id = db_user.id
            
            # Connect the WebSocket
            await manager.connect(websocket, user_id)
            
            try:
                while True:
                    # Receive message from WebSocket
                    data = await websocket.receive_text()
                    
                    try:
                        message_data = json.loads(data)
                        friend_nickname = message_data.get("friend_nickname")
                        content = message_data.get("content")
                        
                        if not friend_nickname or not content:
                            await websocket.send_json({
                                "type": "error",
                                "detail": "Both 'friend_nickname' and 'content' are required"
                            })
                            continue
                        
                        # Validate content length
                        if len(content) < 1 or len(content) > 10000:
                            await websocket.send_json({
                                "type": "error",
                                "detail": "Content must be between 1 and 10000 characters"
                            })
                            continue
                        
                        # Get or create friend chat
                        friend_chat, current_user, friend = await ChatService.get_or_create_friend_chat(
                            session, user_id, friend_nickname
                        )
                        
                        # Save message to database
                        saved_message = await ChatService.save_message(
                            session, friend_chat.id_friend_chat, user_id, content
                        )
                        
                        # Prepare response message
                        response_message = {
                            "type": "message",
                            "sender_nickname": current_user.nickname,
                            "content": saved_message.content,
                            "created_at": saved_message.created_at.isoformat()
                        }
                        
                        # Send confirmation to sender
                        await websocket.send_json({
                            **response_message,
                            "is_mine": True
                        })
                        
                        # Send message to recipient if they're online
                        await manager.send_personal_message(
                            {
                                **response_message,
                                "is_mine": False
                            },
                            friend.id
                        )
                        
                    except json.JSONDecodeError:
                        await websocket.send_json({
                            "type": "error",
                            "detail": "Invalid JSON format"
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "detail": str(e)
                        })
                        
            except WebSocketDisconnect:
                manager.disconnect(user_id)
                
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except Exception as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


@chat_router.get("/history/{friend_nickname}", response_model=ChatHistoryResponse)
async def get_chat_history(
    friend_nickname: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Number of messages per page"),
    current_user: RegisteredUser = Depends(current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get chat history with a friend (paginated, newest first)
    
    - **friend_nickname**: Nickname of the friend
    - **page**: Page number (default: 1)
    - **page_size**: Number of messages per page (default: 50, max: 100)
    
    Returns paginated list of messages with the friend.
    """
    messages, total, friend_nick = await ChatService.get_chat_history(
        session=session,
        user_id=current_user.id,
        friend_nickname=friend_nickname,
        page=page,
        page_size=page_size
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return ChatHistoryResponse(
        messages=messages,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        friend_nickname=friend_nick
    )
