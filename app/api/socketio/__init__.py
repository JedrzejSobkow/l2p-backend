# app/api/socketio/__init__.py

"""
Socket.IO namespaces for real-time features

Active namespaces:
- /chat: Real-time chat messaging
- /lobby: Game lobby management
- /game: Turn-based game engine

To add a new namespace:
1. Create a new file: <feature>_namespace.py
2. Inherit from AuthNamespace (handles authentication automatically) or BaseNamespace (no auth)
3. For AuthNamespace, implement optional callbacks:
   - handle_connect(self, sid, environ, user) - called after successful auth
   - handle_disconnect(self, sid) - called before disconnection
4. Register it: sio.register_namespace(YourNamespace('/your-path'))
5. Import it here
"""

from infrastructure.socketio_manager import sio, manager

# Import namespaces to register them
from .chat_namespace import ChatNamespace
from .lobby_namespace import LobbyNamespace
from .game_namespace import GameNamespace


__all__ = ['sio', 'manager', 'ChatNamespace', 'LobbyNamespace', 'GameNamespace']
