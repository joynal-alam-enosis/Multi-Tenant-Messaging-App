# Cross-Tenant Messaging Application — Project Rules

## Project Overview

This is a real-time cross-tenant messaging application. Users from different tenants (organizations) can exchange direct messages. The system uses Django + DRF on the backend, React + TypeScript on the frontend, PostgreSQL for persistence, Redis for caching and WebSocket channel layer, Celery for async tasks, and Docker Compose to orchestrate everything.

**Always refer to `SYSTEM_DESIGN.md` in the project root for the authoritative architecture and data model.**

---

## Directory Structure Convention

```
messaging-app/
├── backend/               # Django project
│   ├── config/            # Django settings, URLs, ASGI, Celery
│   └── apps/              # Django apps (tenants, users, conversations, messages, exports)
├── frontend/              # React + TypeScript + Vite
│   └── src/
├── docker-compose.yml
├── SYSTEM_DESIGN.md
└── README.md
```

---

## General Rules (Always Apply)

### Code Quality
- Write clean, readable code with meaningful variable and function names.
- Add docstrings to all Django models, serializers, views, and permissions.
- Add JSDoc comments to all React components and hooks.
- Use type hints in all Python function signatures.
- Use TypeScript strict mode — no `any` types unless absolutely necessary.

### Git & Commits
- Write descriptive commit messages in imperative mood.
- Keep commits atomic — one logical change per commit.

### Security — NEVER Violate
- **Never** expose user passwords, tokens, or sensitive fields in API responses.
- **Never** allow a user to access another user's inbox or conversations they don't participate in.
- **Never** allow a user to modify another user's star/read state.
- **Always** validate that the requesting user is a participant before any conversation/message operation.
- **Always** use parameterized queries (Django ORM handles this — never use raw SQL without parameters).

### Architecture Constraints
- PostgreSQL is the **source of truth** for all data.
- Redis is used **only** for caching (inbox, 30-60s TTL) and as the Django Channels channel layer.
- Celery is used **only** for async tasks (conversation export). Do not use Celery for real-time features.
- WebSocket connections use Django Channels with Redis as the channel layer backend.
- Each user gets a personal channel group: `user_{user_id}`.

---

## Backend Rules (Django)

### Models
- Use UUIDs as primary keys on all models.
- The `Conversation` model must not duplicate for the same user pair — enforce idempotency.
- `ConversationParticipant` is a separate join table with per-user `is_starred`, `unread_count`, and `last_read_at`.
- `last_activity_at` lives on `Conversation`, updated whenever a new message is sent.
- Add database indexes as specified in `SYSTEM_DESIGN.md` section 3.

### Serializers
- User search serializer must expose **only**: `id`, `email`, `first_name`, `last_name`, `tenant` (id + name).
- Never include `password`, `password_hash`, `last_login`, `is_superuser`, `is_staff`, or any token fields.

### Views & Permissions
- Use DRF ViewSets or APIViews, not function-based views.
- Create a custom `IsConversationParticipant` permission class.
- Inbox endpoint must filter conversations to `request.user` only.
- All conversation/message endpoints must check participant membership.

### Caching
- Cache inbox responses in Redis with keys: `inbox:{user_id}:{filter}` (TTL 30-60s).
- Invalidate **both** participants' caches when: message sent, message read, conversation starred/unstarred, conversation created.
- Use `django.core.cache` with the Redis backend.

### WebSocket Consumers
- Authenticate via token in query string.
- Add user to their personal group on connect: `user_{user_id}`.
- Remove from group on disconnect.
- Push `new_message`, `message_read`, and `conversation_updated` event types.

### Celery Tasks
- Export task: fetch all messages, write to JSON file, update `ExportTask` model status.
- Handle failures gracefully — set status to `FAILED` with error message.

---

## Frontend Rules (React + TypeScript)

### State Management
- Use TanStack Query for all server state (conversations, messages, user search).
- Use React local state only for UI state (selected filter, search input, selected conversation).
- **Never** store server data in `useState` — always use TanStack Query cache.

### WebSocket Integration
- Single WebSocket connection per authenticated user.
- On `new_message`: use `queryClient.setQueryData` to append the message (with deduplication by `message.id`), then `invalidateQueries(['conversations'])` for inbox.
- On `message_read`: update the message's `is_read` in the query cache.
- **Deduplication**: Always check `message.id` before appending to prevent duplicates when WebSocket push and HTTP refetch overlap.

### Components
- Every component must handle: loading state, error state, empty state.
- Use Tailwind CSS for styling.
- Show tenant name alongside user name in all user-facing displays.
- Unread badge must show count from server, not local calculation.

### API Client
- Use Axios with a base instance that includes the auth token header.
- All API calls go through the `api/` directory — components never call `fetch` or `axios` directly.

---

## Testing Rules

- Use `pytest` + `pytest-django` for backend tests.
- Test authorization on every endpoint: verify 403 for non-participants.
- Test conversation idempotency: creating the same pair twice returns the same conversation.
- Test that user search never leaks sensitive fields.
- Test cache invalidation: after sending a message, the cache should be cleared.
- Use `@pytest.mark.django_db` for all database tests.
- Use React Testing Library for frontend component tests.

---

## Docker Rules

- All services defined in a single `docker-compose.yml`.
- Backend uses Daphne (ASGI) to serve both HTTP and WebSocket.
- Celery worker uses the same Docker image as the backend.
- PostgreSQL data persisted via a named volume.
- Redis does not need persistence (cache + ephemeral channel layer).
- Environment variables for database URLs, Redis URLs, and secret keys — never hardcode credentials.
