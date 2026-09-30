---
name: api-design-and-authorization
description: >-
  Use this skill when designing, implementing, or modifying REST API endpoints,
  serializers, permissions, or WebSocket protocols for the messaging application.
  Also use when working on authentication, authorization, or API security.
---

# API Design & Authorization Skill

## REST API Endpoints Reference

| Method | Endpoint | Description | Auth | Permission |
|--------|----------|-------------|------|------------|
| `GET` | `/api/auth/cognito-config/` | Get Cognito pool/client IDs for frontend | None | None |
| `GET` | `/api/auth/me/` | Get current user profile (after Cognito login) | Bearer | Authenticated |
| `GET` | `/api/users/search/?q=` | Search users | Bearer | Authenticated |
| `GET` | `/api/conversations/` | List inbox | Bearer | Own only |
| `POST` | `/api/conversations/` | Create/get conversation | Bearer | Authenticated |
| `GET` | `/api/conversations/{id}/` | Conversation detail | Bearer | Participant |
| `PATCH` | `/api/conversations/{id}/star/` | Toggle star | Bearer | Participant |
| `GET` | `/api/conversations/{id}/messages/` | List messages | Bearer | Participant |
| `POST` | `/api/conversations/{id}/messages/` | Send message | Bearer | Participant |
| `POST` | `/api/conversations/{id}/messages/read/` | Mark read | Bearer | Participant |
| `POST` | `/api/conversations/{id}/export/` | Request export | Bearer | Participant |
| `GET` | `/api/exports/{id}/download/` | Download export | Bearer | Owner |

> **Legacy (deprecated):** `POST /api/auth/login/` — DRF Token login, retained during migration. Frontend uses Cognito `InitiateAuth` directly.

## Authorization Rules — CRITICAL

These rules are non-negotiable and must be enforced on every relevant endpoint:

### 1. Inbox Isolation
```python
# A user may ONLY list their own conversations
def get_queryset(self):
    return Conversation.objects.filter(
        participants__user=self.request.user
    ).order_by('-last_activity_at')
```

### 2. Participant-Only Access
```python
# A user may ONLY access conversations where they are a participant
class IsConversationParticipant(BasePermission):
    message = "You are not a participant in this conversation."
    
    def has_object_permission(self, request, view, obj):
        return ConversationParticipant.objects.filter(
            conversation=obj, user=request.user
        ).exists()
```

### 3. Star Isolation
```python
# A user must NOT be able to star another user's conversation state
# The star endpoint only modifies the requesting user's ConversationParticipant
def toggle_star(self, request, pk=None):
    conversation = self.get_object()  # permission checked here
    participant = ConversationParticipant.objects.get(
        conversation=conversation, user=request.user  # ONLY their own
    )
    participant.is_starred = not participant.is_starred
    participant.save()
```

### 4. Message Access
```python
# A user may ONLY send/read messages in conversations where they are a participant
# This is enforced by checking participant status BEFORE any message operation
```

### 5. User Search Safety
```python
# User search must NOT expose passwords, tokens, or sensitive internal fields
class UserSearchSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'tenant_name']
        # NEVER include: password, last_login, is_superuser, is_staff, date_joined, groups, user_permissions
```

### 6. Conversation Idempotency
```python
# There must NOT be two separate conversations for the same pair
# Always check for existing conversation before creating
def create(self, request):
    target_user_id = request.data.get('user_id')
    target_user = User.objects.get(id=target_user_id)
    
    # Check for existing conversation
    existing = Conversation.objects.filter(
        participants__user=request.user
    ).filter(
        participants__user=target_user
    ).first()
    
    if existing:
        return Response(
            ConversationSerializer(existing).data,
            status=status.HTTP_200_OK  # 200, not 201
        )
    
    # Create new
    conversation = Conversation.objects.create()
    ConversationParticipant.objects.create(conversation=conversation, user=request.user)
    ConversationParticipant.objects.create(conversation=conversation, user=target_user)
    return Response(
        ConversationSerializer(conversation).data,
        status=status.HTTP_201_CREATED
    )
```

### 7. Cross-Tenant Messaging
```python
# Cross-tenant messaging is allowed ONLY after the target user is explicitly selected
# This means: no implicit cross-tenant access, no tenant-wide broadcasts
# The target user must be explicitly chosen via user search → conversation creation
```

## Inbox Query Parameters

```
GET /api/conversations/?filter=all          # All conversations
GET /api/conversations/?filter=unread       # Only with unread_count > 0
GET /api/conversations/?filter=starred      # Only starred
GET /api/conversations/?search=hello        # Search by participant name or message text
GET /api/conversations/?ordering=-last_activity_at  # Sort (default)
```

## Response Formats

### Inbox Item
```json
{
  "id": "uuid",
  "other_participant": {
    "id": "uuid",
    "email": "dave@globex.com",
    "first_name": "Dave",
    "last_name": "Smith",
    "tenant_name": "Globex Inc"
  },
  "last_message": "Hello there!",
  "last_activity_at": "2026-09-24T10:00:00Z",
  "created_at": "2026-09-20T08:00:00Z",
  "is_starred": false,
  "unread_count": 3
}
```

### Message
```json
{
  "id": "uuid",
  "sender": {
    "id": "uuid",
    "first_name": "Alice",
    "last_name": "Johnson",
    "tenant_name": "Acme Corp"
  },
  "content": "Hello!",
  "is_read": true,
  "created_at": "2026-09-24T10:00:00Z"
}
```

## Authentication (Cognito JWT)

### Token Acquisition (Frontend)
```typescript
// Frontend calls Cognito directly (USER_PASSWORD_AUTH)
const tokens = await initiatePasswordAuth(email, password);
// tokens: { accessToken, idToken, refreshToken }
// Then: GET /api/auth/me/ → local user profile
```

### Django Validation
```python
# apps.users.authentication.CognitoJWTAuthentication
# - Authorization: Bearer <cognito_access_token>
# - Validates via JWKS from Cognito/MiniStack
# - Checks: exp, iss, aud/client_id, token_use
# - Maps sub → local User.cognito_sub (JIT sync on first login)
```

### WebSocket Protocol

#### Connection
```
ws://localhost:8000/ws/chat/?token=<cognito_access_token>
```
Accepts Cognito Access JWT (Bearer-style) or legacy DRF Token during migration.

#### Server → Client Events
```jsonc
// New message
{"type": "new_message", "data": {"conversation_id": "uuid", "message": {...}}}

// Read receipt
{"type": "message_read", "data": {"conversation_id": "uuid", "reader_id": "uuid", "read_at": "..."}}

// Conversation updated (inbox refresh signal)
{"type": "conversation_updated", "data": {"conversation_id": "uuid", "last_message": "...", "last_activity_at": "...", "unread_count": 3}}
```

## Error Response Format
```json
{
  "detail": "You are not a participant in this conversation."
}
```

HTTP status codes:
- `400` — Bad request (validation error)
- `401` — Not authenticated
- `403` — Not authorized (not a participant)
- `404` — Resource not found
- `200` — Success (existing resource returned)
- `201` — Created (new resource)
- `202` — Accepted (async task queued)