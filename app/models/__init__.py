# app/models/__init__.py

from models.user import User
from models.registered_user import RegisteredUser
from models.friendship import Friendship

__all__ = ["User", "RegisteredUser", "Friendship"]
