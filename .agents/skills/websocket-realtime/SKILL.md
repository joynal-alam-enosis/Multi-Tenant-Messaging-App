---
name: websocket-realtime
description: >-
  Use this skill when implementing, debugging, or modifying real-time WebSocket
  functionality — Django Channels consumers, Redis channel layer, frontend WebSocket
  client, or real-time message delivery and deduplication.
---

# WebSocket & Real-Time Skill

## Architecture Overview

```
Browser (WS Client) ←→ Daphne (ASGI) ←→ Django Channels Consumer ←→ Redis (Channel Layer)
```

- **One WebSocket connection per authenticated user**
- Each user joins a **personal group**: `user_{user_id}`
- Messages are pushed to the **recipient's group**, not the sender's
- Redis PubSub is the channel layer backend

## Backend: Django Channels Setup

### ASGI Configuration (config/asgi.py)
```python
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from middleware import TokenAuthMiddleware
import routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": TokenAuthMiddleware(
        URLRouter(routing.websocket_urlpatterns)
    ),
})
```

### WebSocket URL Routing (routing.py)
```python
from django.urls import re_path
from apps.messages.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/$', ChatConsumer.as_asgi()),
]
```

### Token Auth Middleware (middleware.py)
```python
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token
from urllib.parse import parse_qs

class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope.get("query_string", b"").decode())
        token_key = query_string.get("token", [None])[0]
        
        if token_key:
            scope["user"] = await self.get_user(token_key)
        else:
            from django.contrib.auth.models import AnonymousUser
            scope["user"] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user(self, token_key):
        try:
            token = Token.objects.select_related('user').get(key=token_key)
            return token.user
        except Token.DoesNotExist:
            from django.contrib.auth.models import AnonymousUser
            return AnonymousUser()
```

### Consumer Implementation (apps/messages/consumers.py)
```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
            await self.close()
            return
        
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
    
    # Handler for each event type — method name must match the "type" field
    async def new_message(self, event):
        await self.send_json(event)
    
    async def message_read(self, event):
        await self.send_json(event)
    
    async def conversation_updated(self, event):
        await self.send_json(event)
```

### Sending Events from Views

When a message is sent via the REST API, push to WebSocket:

```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_websocket_event(user_id, event_type, data):
    """Send a WebSocket event to a specific user's channel group."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "type": event_type,       # e.g., "new_message"
            "data": data,
        }
    )

# Usage in message creation view:
def create_message(request, conversation_id):
    # ... save message to DB ...
    
    # Push to recipient (NOT sender)
    for participant in conversation.participants.exclude(user=request.user):
        send_websocket_event(
            user_id=str(participant.user.id),
            event_type="new_message",
            data={
                "conversation_id": str(conversation_id),
                "message": MessageSerializer(message).data,
            }
        )
```

## Frontend: WebSocket Client

### Connection Manager (src/utils/websocket.ts)
```typescript
class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private handlers: Map<string, (data: any) => void> = new Map();

  connect(token: string) {
    const wsUrl = `${import.meta.env.VITE_WS_URL}/chat/?token=${token}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const handler = this.handlers.get(message.type);
      if (handler) handler(message.data);
    };

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect(token);
        }, 1000 * Math.pow(2, this.reconnectAttempts)); // Exponential backoff
      }
    };

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };
  }

  on(type: string, handler: (data: any) => void) {
    this.handlers.set(type, handler);
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }
}
```

### Deduplication Strategy

**CRITICAL**: When a WebSocket push and an HTTP refetch both deliver the same message, we must not show it twice.

```typescript
// In the WebSocket handler:
queryClient.setQueryData<Message[]>(
  ['messages', conversationId],
  (oldMessages = []) => {
    // Check if message already exists by ID
    if (oldMessages.some(m => m.id === newMessage.id)) {
      return oldMessages; // Skip duplicate
    }
    return [...oldMessages, newMessage];
  }
);
```

**When deduplication applies:**
1. Alice sends a message → HTTP response adds it to her UI
2. Alice also receives a WebSocket push for her own message (if implemented) → dedup by ID
3. TanStack Query refetches on focus → existing messages already in cache → dedup by ID

## Redis Channel Layer Settings

```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],  # or parse from REDIS_URL
            'capacity': 1500,
            'expiry': 10,
        },
    },
}
```

## Testing WebSocket Connections

### Manual Testing
```bash
# Install wscat
npm install -g wscat

# Connect as a user (get token from login endpoint first)
wscat -c "ws://localhost:8000/ws/chat/?token=YOUR_TOKEN_HERE"

# In another terminal, send a message via API
curl -X POST http://localhost:8000/api/conversations/{id}/messages/ \
  -H "Authorization: Token SENDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello via WebSocket!"}'

# The wscat terminal should show the new_message event
```

### Automated Testing
```python
import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application

@pytest.mark.asyncio
async def test_websocket_connects_with_valid_token(alice):
    token = Token.objects.create(user=alice)
    communicator = WebsocketCommunicator(
        application, f"/ws/chat/?token={token.key}"
    )
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()

@pytest.mark.asyncio
async def test_websocket_rejects_without_token():
    communicator = WebsocketCommunicator(application, "/ws/chat/")
    connected, _ = await communicator.connect()
    assert not connected
```
