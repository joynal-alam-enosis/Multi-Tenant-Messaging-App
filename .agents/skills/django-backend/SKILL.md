---
name: django-backend-development
description: >-
  Use this skill when building or modifying the Django backend — models, serializers,
  views, permissions, URL routing, management commands, or database migrations for
  the messaging application.
---

# Django Backend Development Skill

## Technology Stack
- Python 3.12
- Django 5.x
- Django REST Framework 3.x
- Django Channels 4.x
- Daphne (ASGI server)
- PostgreSQL 16
- Redis 7 (cache + channel layer)
- Celery 5.x

## Project Layout

```
backend/
├── config/
│   ├── __init__.py
│   ├── settings.py          # Main settings (DB, cache, channels, celery, auth)
│   ├── urls.py              # Root URL configuration
│   ├── asgi.py              # ASGI application with Channels routing
│   ├── wsgi.py              # WSGI fallback
│   └── celery.py            # Celery app setup with autodiscover
│
├── apps/
│   ├── __init__.py
│   ├── tenants/
│   │   ├── __init__.py
│   │   ├── models.py        # Tenant(id, name, slug, created_at)
│   │   ├── serializers.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── users/
│   │   ├── __init__.py
│   │   ├── models.py        # Custom User extending AbstractUser, FK to Tenant
│   │   ├── serializers.py   # UserSearchSerializer (safe fields only)
│   │   ├── views.py         # UserSearchView — search by name or email
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── conversations/
│   │   ├── __init__.py
│   │   ├── models.py        # Conversation, ConversationParticipant
│   │   ├── serializers.py   # ConversationListSerializer, ConversationDetailSerializer
│   │   ├── views.py         # InboxViewSet, create/get, star/unstar
│   │   ├── urls.py
│   │   ├── permissions.py   # IsConversationParticipant
│   │   ├── cache.py         # get_cached_inbox(), invalidate_inbox_cache()
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── messages/
│   │   ├── __init__.py
│   │   ├── models.py        # Message(id, conversation, sender, content, is_read, created_at)
│   │   ├── serializers.py
│   │   ├── views.py         # Send, list, mark-as-read
│   │   ├── urls.py
│   │   ├── consumers.py     # ChatConsumer (WebSocket)
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   └── exports/
│       ├── __init__.py
│       ├── models.py        # ExportTask(id, user, conversation, status, file_path, timestamps)
│       ├── tasks.py         # Celery task: export_conversation
│       ├── views.py         # RequestExportView, DownloadExportView
│       ├── serializers.py
│       ├── urls.py
│       ├── admin.py
│       └── apps.py
│
├── routing.py               # WebSocket URL routing (ws/chat/)
├── middleware.py            # TokenAuthMiddleware for WebSocket
├── manage.py
├── requirements.txt
├── Dockerfile
└── seed.py                  # Management command or script for seed data
```

## Model Design Patterns

### All models MUST use UUID primary keys:
```python
import uuid
from django.db import models

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
```

### Conversation idempotency — always check before creating:
```python
from django.db.models import Q

def get_or_create_conversation(user1, user2):
    """Return existing conversation or create a new one. Never duplicates."""
    conversation = Conversation.objects.filter(
        participants__user=user1
    ).filter(
        participants__user=user2
    ).first()
    
    if conversation:
        return conversation, False  # existed
    
    conversation = Conversation.objects.create()
    ConversationParticipant.objects.create(conversation=conversation, user=user1)
    ConversationParticipant.objects.create(conversation=conversation, user=user2)
    return conversation, True  # created
```

### Unread count — increment on send, reset on read:
```python
# When a message is sent:
ConversationParticipant.objects.filter(
    conversation=conversation, user=recipient
).update(unread_count=F('unread_count') + 1)

# When messages are marked as read:
ConversationParticipant.objects.filter(
    conversation=conversation, user=reader
).update(unread_count=0, last_read_at=timezone.now())
```

## Permission Pattern

```python
from rest_framework.permissions import BasePermission

class IsConversationParticipant(BasePermission):
    """Only allow access if the user is a participant in the conversation."""
    def has_object_permission(self, request, view, obj):
        return obj.participants.filter(user=request.user).exists()
```

## Redis Cache Pattern

```python
from django.core.cache import cache

INBOX_CACHE_TTL = 45  # seconds (between 30-60)

def get_cached_inbox(user_id, filter_type='all'):
    cache_key = f"inbox:{user_id}:{filter_type}"
    data = cache.get(cache_key)
    if data is None:
        data = _fetch_inbox_from_db(user_id, filter_type)
        cache.set(cache_key, data, INBOX_CACHE_TTL)
    return data

def invalidate_inbox_cache(user_id):
    cache.delete_many([
        f"inbox:{user_id}:all",
        f"inbox:{user_id}:unread",
        f"inbox:{user_id}:starred",
    ])
```

## WebSocket Consumer Pattern

```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
    
    async def new_message(self, event):
        await self.send_json(event)
    
    async def message_read(self, event):
        await self.send_json(event)
    
    async def conversation_updated(self, event):
        await self.send_json(event)
```

## Settings Checklist

When configuring `settings.py`, ensure:
- [ ] `AUTH_USER_MODEL` points to custom User model
- [ ] `CHANNEL_LAYERS` configured with Redis backend
- [ ] `CACHES` configured with Redis backend (different DB number than channels)
- [ ] `CELERY_BROKER_URL` set to Redis
- [ ] `REST_FRAMEWORK` has default authentication and permission classes
- [ ] `CORS_ALLOWED_ORIGINS` includes the frontend URL
- [ ] Database configured for PostgreSQL

## Seed Data Command

Create a management command `python manage.py seed` that creates:
- 2 tenants: "Acme Corp" (slug: acme), "Globex Inc" (slug: globex)
- 3 users per tenant (alice, bob, charlie @ acme; dave, eve, frank @ globex)
- Pre-seeded conversations with sample messages
- All passwords: `password123`
- Command must be **idempotent** — running it twice doesn't create duplicates
