# app/api/routes/chat/__init__.py

"""
Chat module containing HTTP and Socket.IO handlers for real-time messaging
"""

from .socketio_handlers import sio, manager
from .http_handlers import router

__all__ = ['sio', 'manager', 'router']
