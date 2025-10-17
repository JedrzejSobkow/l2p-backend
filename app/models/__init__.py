# app/models/__init__.py

from models.registered_user import RegisteredUser
from models.friendship import Friendship

__all__ = ["RegisteredUser", "Friendship"]
