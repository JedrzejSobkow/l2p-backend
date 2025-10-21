# app/models/__init__.py

from models.registered_user import RegisteredUser
from models.friendship import Friendship
from models.friend_chat import FriendChat

__all__ = ["RegisteredUser", "Friendship", "FriendChat"]
