# Implementation Plan — Cross-Tenant Messaging Application

> **Purpose**: A granular, step-by-step build plan. Each step explains **what** to build, **why** it matters, **what you'll learn**, and **exactly which files** to create or modify. Steps are ordered so each one builds on the previous — no forward references, no guessing.

---

## How to Use This Plan

1. **Work through steps in order** — each step depends on previous ones.
2. **Each step has a "Verify" section** — confirm the step works before moving on.
3. **Files listed are exact paths** — no ambiguity about where code goes.
4. **Code patterns are in the skills** — read the relevant skill from `.agents/skills/` for templates.
5. **Follow the rules** — `GEMINI.md` and `AGENTS.md` apply at all times.

### 🐳 The Docker-First Workflow
- **Zero Local Setup**: You do NOT need Python or Node.js installed on your host machine.
- **Write locally, run in Docker**: Create the files on your host machine (they will be volume-mounted into the containers).
- **Commands**: **Never** run `python manage.py ...`, `pytest`, or `npm ...` locally. Use `docker compose exec backend python manage.py ...` or let the `docker-compose.yml` entrypoint handle it.
- **Dependencies**: Add them to `requirements.txt` or `package.json`, then run `docker compose up --build`.

---

## Phase 1: Project Scaffolding

> **What you'll learn**: How Django projects are structured, how Python packaging works, and why we separate config from apps.

### Step 1.1 — Create the Backend Django Project

**What**: Initialize the Django project skeleton with the correct directory layout.

**Why**: Django needs a specific project structure. We put the project configuration in `config/` (not the default project name) so the settings, URLs, and ASGI config live in a clean, predictable location.

**Files to create**:
```
backend/
├── config/
│   ├── __init__.py          # Makes config/ a Python package
│   ├── settings.py          # All Django settings
│   ├── urls.py              # Root URL configuration
│   ├── asgi.py              # ASGI entry point (needed later for WebSocket)
│   ├── wsgi.py              # WSGI entry point (fallback)
│   └── celery.py            # Celery app (just the skeleton for now)
├── apps/
│   └── __init__.py          # Makes apps/ a Python package
├── manage.py                # Django CLI entry point
└── requirements.txt         # Python dependencies
```

**`requirements.txt` contents** (exact packages):
```
django>=5.0,<6.0
djangorestframework>=3.15,<4.0
django-cors-headers>=4.3,<5.0
channels>=4.0,<5.0
channels-redis>=4.2,<5.0
daphne>=4.1,<5.0
celery>=5.4,<6.0
redis>=5.0,<6.0
django-redis>=5.4,<6.0
psycopg2-binary>=2.9,<3.0
python-dotenv>=1.0,<2.0
```

**`config/settings.py` must configure**:
- `SECRET_KEY` from environment variable (`os.environ.get`)
- `INSTALLED_APPS` with: `daphne`, `rest_framework`, `corsheaders`, and `channels` (no custom apps yet)
- `DATABASES` using `DATABASE_URL` env var, parsed manually or with a helper
- `CACHES` with Redis backend (DB 0)
- `CHANNEL_LAYERS` with Redis channel layer (also uses Redis)
- `REST_FRAMEWORK` with `TokenAuthentication` and `IsAuthenticated` defaults
- `CORS_ALLOWED_ORIGINS` from env var
- `AUTH_USER_MODEL` set to `"users.User"` (we'll create the model in Step 1.3)
- `ASGI_APPLICATION` set to `"config.asgi.application"`

**`config/urls.py`**: Just the admin URL for now — API URLs added later.

**`config/asgi.py`**: Basic ASGI application — WebSocket routing added in Phase 3.

**`config/celery.py`**: Celery app skeleton with `autodiscover_tasks()`.

**`manage.py`**: Standard Django manage.py pointing to `config.settings`.

**What you learn**:
- Django project vs app distinction
- Why settings are configured through environment variables (12-factor app)
- How ASGI differs from WSGI (async support for WebSocket)
- Package pinning in requirements.txt

**Verify**: The file structure exists and is syntactically valid Python. Don't run anything yet — we don't have a database.

---

### Step 1.2 — Create the Tenants App

**What**: Build the `Tenant` model — the simplest model in the system.

**Why**: Starting with the simplest model teaches Django model basics without complexity. Tenants are a dependency for Users, so they must exist first.

**Files to create**:
```
backend/apps/tenants/
├── __init__.py
├── apps.py                  # AppConfig with name = "apps.tenants"
├── models.py                # Tenant model
├── serializers.py           # TenantSerializer
├── admin.py                 # Register Tenant in Django admin
└── migrations/              # Auto-generated (empty for now)
    └── __init__.py
```

**`models.py`** — The Tenant model:
```python
import uuid
from django.db import models

class Tenant(models.Model):
    """An organization/company. Users belong to exactly one tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
```

**`serializers.py`**:
```python
from rest_framework import serializers
from .models import Tenant

class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenant data. Used nested inside user responses."""
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]
```

**`apps.py`**:
```python
from django.apps import AppConfig

class TenantsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenants"
    verbose_name = "Tenants"
```

**`admin.py`**: Register `Tenant` with `list_display = ["name", "slug", "created_at"]`.

**Update `config/settings.py`**: Add `"apps.tenants"` to `INSTALLED_APPS`.

**What you learn**:
- Django model field types (`UUIDField`, `CharField`, `SlugField`, `DateTimeField`)
- `auto_now_add=True` — automatic timestamp on creation
- Model `Meta` class for ordering and other options
- DRF serializers — how models become JSON
- Django admin registration

**Verify**: File structure is correct. Model has UUID pk, name, slug, created_at.

---

### Step 1.3 — Create the Users App (Custom User Model)

**What**: Build a custom User model that extends Django's `AbstractUser` and links to a Tenant.

**Why**: Django's default User model doesn't have a tenant field. We **must** define `AUTH_USER_MODEL` before the first migration — changing it later is extremely painful. This teaches custom user models, which is a real-world Django pattern.

**Files to create**:
```
backend/apps/users/
├── __init__.py
├── apps.py                  # AppConfig with name = "apps.users"
├── models.py                # Custom User model
├── serializers.py           # UserSearchSerializer (safe fields only)
├── views.py                 # Empty for now
├── urls.py                  # Empty for now
├── admin.py                 # Register User in Django admin
└── migrations/
    └── __init__.py
```

**`models.py`** — Custom User:
```python
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Custom user model. Every user belongs to one tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="users",
    )
    email = models.EmailField(unique=True)

    # Use email as the login field instead of username
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.email})"
```

**`serializers.py`** — Safe user serializer (NEVER expose passwords):
```python
from rest_framework import serializers
from .models import User

class UserSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for user search results.
    SECURITY: Only exposes safe fields. Never includes password,
    last_login, is_superuser, is_staff, or token fields.
    """
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "tenant_id", "tenant_name"]
```

**Update `config/settings.py`**: Add `"apps.users"` to `INSTALLED_APPS`.

**Confirm** `AUTH_USER_MODEL = "users.User"` is already set (from Step 1.1).

**What you learn**:
- `AbstractUser` vs `AbstractBaseUser` — when to use each
- `ForeignKey` relationships (User → Tenant)
- `USERNAME_FIELD` — changing Django's login identifier
- Database indexes and why they matter
- Serializer field safety — explicitly listing fields vs `__all__`
- `related_name` — how Django creates reverse relationships

**Verify**: User model has UUID pk, tenant FK, email as unique login field. Serializer exposes only 6 safe fields.

---

### Step 1.4 — Create the Conversations App

**What**: Build the `Conversation` and `ConversationParticipant` models — the core of the messaging system.

**Why**: This is the most architecturally important model. The separate `ConversationParticipant` table is what makes per-user starred state and unread counts possible. This is a classic **join table pattern** with extra fields.

**Files to create**:
```
backend/apps/conversations/
├── __init__.py
├── apps.py
├── models.py                # Conversation + ConversationParticipant
├── serializers.py           # Empty for now (built in Phase 2)
├── views.py                 # Empty for now
├── urls.py                  # Empty for now
├── permissions.py           # Empty for now
├── cache.py                 # Empty for now
├── admin.py
└── migrations/
    └── __init__.py
```

**`models.py`**:
```python
import uuid
from django.conf import settings
from django.db import models

class Conversation(models.Model):
    """
    A 1-on-1 conversation between exactly two users.
    The same pair of users must never have two separate conversations (idempotent).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["-last_activity_at"]),
        ]

    def __str__(self) -> str:
        participants = self.participants.select_related("user").all()
        names = [p.user.email for p in participants]
        return f"Conversation: {' ↔ '.join(names)}"


class ConversationParticipant(models.Model):
    """
    Join table between Conversation and User.
    Stores per-user state: starred, unread count, last read timestamp.
    Each conversation has exactly 2 participants.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participations",
    )
    is_starred = models.BooleanField(default=False)
    unread_count = models.IntegerField(default=0)
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent the same user from being added twice to the same conversation
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_participant",
            )
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} in {self.conversation_id}"
```

**Update `config/settings.py`**: Add `"apps.conversations"` to `INSTALLED_APPS`.

**What you learn**:
- **Join table pattern**: Why a separate model is better than ManyToManyField when you need extra fields
- `UniqueConstraint` — database-level enforcement of business rules
- `related_name` — `conversation.participants` gives all ConversationParticipant objects
- `settings.AUTH_USER_MODEL` — referencing the User model indirectly (best practice)
- `-last_activity_at` index — descending index for "most recent first" queries
- `on_delete=models.CASCADE` — what happens when a parent is deleted

**Verify**: Two models exist. `ConversationParticipant` has unique constraint on (conversation, user). Conversation has `last_activity_at` with descending index.

---

### Step 1.5 — Create the Messages App

**What**: Build the `Message` model — what users actually send to each other.

**Why**: Messages are the core data of a chat app. This model is straightforward but has important relationships — it belongs to both a Conversation and a sender (User).

**⚠️ GOTCHA**: Django has a built-in `django.contrib.messages` framework. Our app `apps.messages` must use a different `label` in its AppConfig to avoid conflicts.

**Files to create**:
```
backend/apps/messages/
├── __init__.py
├── apps.py                  # AppConfig with label = "chat_messages"
├── models.py                # Message model
├── serializers.py           # Empty for now
├── views.py                 # Empty for now
├── urls.py                  # Empty for now
├── consumers.py             # Empty for now (WebSocket — Phase 3)
├── admin.py
└── migrations/
    └── __init__.py
```

**`apps.py`** — IMPORTANT: Custom label to avoid conflict:
```python
from django.apps import AppConfig

class MessagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.messages"
    label = "chat_messages"    # Avoids conflict with django.contrib.messages
    verbose_name = "Chat Messages"
```

**`models.py`**:
```python
import uuid
from django.conf import settings
from django.db import models

class Message(models.Model):
    """A single text message within a conversation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender"]),
        ]

    def __str__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.sender.email}: {preview}"
```

**Update `config/settings.py`**: Add `"apps.messages"` to `INSTALLED_APPS`.

**What you learn**:
- App label conflicts and how to resolve them with `label` in AppConfig
- `TextField` vs `CharField` — unlimited length text
- Compound indexes — `(conversation, created_at)` speeds up "all messages in a conversation sorted by time"
- `related_name` patterns — `conversation.messages`, `user.sent_messages`

**Verify**: Model has UUID pk, FK to Conversation, FK to User (sender), content, is_read, created_at. AppConfig uses `label = "chat_messages"`.

---

### Step 1.6 — Create the Exports App

**What**: Build the `ExportTask` model — tracks async export jobs.

**Why**: This is the simplest model in the system but introduces an important concept: **tracking async task state in the database**. Celery runs the job, but PostgreSQL records the status so the frontend can poll for completion.

**Files to create**:
```
backend/apps/exports/
├── __init__.py
├── apps.py
├── models.py                # ExportTask model
├── tasks.py                 # Empty for now (Celery task — Phase 4)
├── serializers.py           # Empty for now
├── views.py                 # Empty for now
├── urls.py                  # Empty for now
├── admin.py
└── migrations/
    └── __init__.py
```

**`models.py`**:
```python
import uuid
from django.conf import settings
from django.db import models

class ExportTask(models.Model):
    """Tracks an async conversation export job."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="export_tasks",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="export_tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    file_path = models.CharField(max_length=500, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Export {self.id} ({self.status})"
```

**Update `config/settings.py`**: Add `"apps.exports"` to `INSTALLED_APPS`.

**What you learn**:
- `TextChoices` — Django's enum pattern for status fields
- State machine concept — PENDING → PROCESSING → COMPLETED/FAILED
- `blank=True, default=""` vs `null=True` — string fields should never be NULL in Django
- How databases track async job state (alternative to keeping everything in memory)

**Verify**: Model has status field with 4 choices, file_path, error_message, FK to User and Conversation.

---

### Step 1.7 — Create the Seed Data Management Command

**What**: Build a Django management command that populates the database with test data.

**Why**: Having consistent seed data means everyone (and every test) starts from the same baseline. Management commands are Django's way of adding CLI tools.

**Files to create**:
```
backend/apps/users/management/
├── __init__.py
└── commands/
    ├── __init__.py
    └── seed.py              # The management command
```

**`seed.py`** must:
1. Create 2 tenants: "Acme Corp" (slug: `acme`) and "Globex Inc" (slug: `globex`)
2. Create 6 users (3 per tenant) using `get_or_create` for idempotency:
   - `alice@acme.com` (Alice Johnson), `bob@acme.com` (Bob Williams), `charlie@acme.com` (Charlie Brown)
   - `dave@globex.com` (Dave Smith), `eve@globex.com` (Eve Davis), `frank@globex.com` (Frank Miller)
   - All passwords: `password123`
3. Create 3 conversations with sample messages:
   - Alice ↔ Bob (same tenant, 3-4 messages)
   - Alice ↔ Dave (cross-tenant, 3-4 messages)
   - Bob ↔ Eve (cross-tenant, 3-4 messages)
4. Create DRF auth tokens for all users (for API/WebSocket auth)
5. Use `get_or_create` everywhere — running `seed` twice must not create duplicates
6. Print a summary showing created users with their auth tokens

**The command class**:
```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Seed the database with test tenants, users, conversations, and messages"

    def handle(self, *args, **options):
        # ... implementation ...
        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))
```

**What you learn**:
- Django management commands — custom CLI tools
- `get_or_create()` — idempotent database operations
- `set_password()` — why you never store raw passwords
- DRF Token model — how token auth works
- `self.stdout.write` with styles — colored CLI output

**Verify**: Command file exists. Uses `get_or_create`. Creates 2 tenants, 6 users, 3 conversations with messages, and auth tokens.

---

## Phase 2: REST API

> **What you'll learn**: How to build a complete REST API — serializers transform data, views handle requests, permissions enforce security, and URL routing connects it all.

### Step 2.1 — Auth Login Endpoint

**What**: Build a login endpoint that accepts email + password and returns an auth token.

**Why**: Every subsequent API call needs authentication. This is the first endpoint we build because all others depend on it.

**Files to modify/create**:
- `backend/apps/users/views.py` — `LoginView`
- `backend/apps/users/urls.py` — URL pattern
- `backend/config/urls.py` — Include users URLs

**`LoginView`**:
- Method: `POST`
- URL: `/api/auth/login/`
- Request body: `{"email": "...", "password": "..."}`
- Response: `{"token": "...", "user": {id, email, first_name, last_name, tenant_name}}`
- No authentication required (obviously — this IS the login)
- Use Django's `authenticate()` and DRF's `Token.objects.get_or_create()`

**What you learn**:
- DRF's `APIView` class
- `authentication_classes = []` and `permission_classes = []` to make an endpoint public
- Django's `authenticate()` function
- Token-based authentication flow

**Verify**: Endpoint accepts email/password, returns token and user info. Returns 400 for invalid credentials.

---

### Step 2.2 — User Search Endpoint

**What**: Build a search endpoint that finds users by name or email.

**Why**: Users need to find people to message. This endpoint powers the "new conversation" flow. It's also our first **security-critical** endpoint — it must never expose passwords.

**Files to modify**:
- `backend/apps/users/views.py` — `UserSearchView`
- `backend/apps/users/urls.py` — URL pattern

**`UserSearchView`**:
- Method: `GET`
- URL: `/api/users/search/?q=alice`
- Query param: `q` — searches `first_name`, `last_name`, and `email` (case-insensitive)
- Response: List of matching users (using `UserSearchSerializer` from Step 1.3)
- Must use `select_related("tenant")` to avoid N+1 queries
- Must exclude the requesting user from results (you can't message yourself)
- Must require authentication

**What you learn**:
- `Q` objects for OR queries in Django ORM
- `icontains` for case-insensitive text search
- `select_related` — SQL JOIN to avoid N+1 queries
- `request.query_params` in DRF
- Why serializers are security boundaries

**Verify**: Search finds users by partial name/email. Response contains only safe fields (no password, no is_staff, etc.). Requesting user is excluded from results.

---

### Step 2.3 — Conversation Permissions

**What**: Build the `IsConversationParticipant` permission class.

**Why**: This single class enforces the most important security rule in the system: "you can only access conversations you're part of." Building it before the views means security is designed in from the start, not bolted on later.

**File to modify**:
- `backend/apps/conversations/permissions.py`

**Implementation**:
```python
from rest_framework.permissions import BasePermission
from .models import ConversationParticipant

class IsConversationParticipant(BasePermission):
    """
    Permission check: the requesting user must be a participant
    in the conversation being accessed.

    Used on all conversation detail, message, star, and export endpoints.
    """
    message = "You are not a participant in this conversation."

    def has_object_permission(self, request, view, obj):
        return ConversationParticipant.objects.filter(
            conversation=obj,
            user=request.user,
        ).exists()
```

**What you learn**:
- DRF custom permissions — `has_permission` vs `has_object_permission`
- Why object-level permissions matter (list vs detail views)
- The `message` attribute for custom error messages

**Verify**: Permission class exists. Checks `ConversationParticipant` table for the requesting user.

---

### Step 2.4 — Conversation Serializers

**What**: Build serializers for inbox list and conversation detail views.

**Why**: Serializers define what data the frontend receives. The inbox serializer is especially important because it needs to show the **other participant** (not the requesting user), the **last message preview**, and the **per-user starred/unread state**.

**File to modify**:
- `backend/apps/conversations/serializers.py`

**Two serializers needed**:

1. **`ConversationListSerializer`** (for inbox):
   - `id` — Conversation UUID
   - `other_participant` — Nested user info of the OTHER person (not the requester)
   - `last_message` — Text preview of the most recent message (or null)
   - `last_activity_at` — When the last message was sent
   - `created_at` — When the conversation started
   - `is_starred` — **The requesting user's** starred state (from ConversationParticipant)
   - `unread_count` — **The requesting user's** unread count (from ConversationParticipant)
   - Uses `SerializerMethodField` for `other_participant`, `is_starred`, `unread_count`
   - Requires `context["request"]` to know who the "current user" is

2. **`ConversationCreateSerializer`** (for creating):
   - Input: `user_id` — the UUID of the other user
   - Validates that the user exists and is not the requesting user

**What you learn**:
- `SerializerMethodField` — computed fields that need request context
- Serializer context — passing `request` through to the serializer
- How the **same data** looks different depending on who's asking (Alice sees Dave as the "other participant", Dave sees Alice)
- Input vs output serializers — different shapes for read and write

**Verify**: `ConversationListSerializer` outputs 7 fields including `other_participant` with tenant info. `is_starred` and `unread_count` are per-user.

---

### Step 2.5 — Inbox Caching Logic

**What**: Build the Redis cache-aside helper functions.

**Why**: The inbox is the most frequently accessed endpoint. Caching it for 30-60 seconds dramatically reduces database load. This step builds the caching layer that the inbox view will use.

**File to modify**:
- `backend/apps/conversations/cache.py`

**Functions to implement**:

```python
from django.core.cache import cache

INBOX_CACHE_TTL = 45  # seconds

def get_inbox_cache_key(user_id: str, filter_type: str = "all") -> str:
    """Generate a consistent cache key for a user's inbox."""
    return f"inbox:{user_id}:{filter_type}"

def get_cached_inbox(user_id: str, filter_type: str = "all"):
    """Get inbox data from cache. Returns None on cache miss."""
    return cache.get(get_inbox_cache_key(user_id, filter_type))

def set_inbox_cache(user_id: str, filter_type: str, data):
    """Store inbox data in cache with TTL."""
    cache.set(get_inbox_cache_key(user_id, filter_type), data, INBOX_CACHE_TTL)

def invalidate_inbox_cache(user_id: str) -> None:
    """
    Invalidate ALL inbox cache variants for a user.
    Called after: new message, read message, star/unstar, new conversation.
    """
    cache.delete_many([
        get_inbox_cache_key(user_id, "all"),
        get_inbox_cache_key(user_id, "unread"),
        get_inbox_cache_key(user_id, "starred"),
    ])
```

**What you learn**:
- Cache-aside pattern — check cache first, fall back to DB, populate cache
- `django.core.cache` API — `get`, `set`, `delete_many`
- Cache key design — why user_id + filter_type creates unique keys
- TTL (Time To Live) — cache auto-expires after N seconds
- Cache invalidation — the hardest problem in computer science

**Verify**: Four functions exist. `invalidate_inbox_cache` deletes all 3 filter variants. TTL is between 30-60 seconds.

---

### Step 2.6 — Inbox View (List Conversations)

**What**: Build the main inbox endpoint — lists the current user's conversations with filters and search.

**Why**: The inbox is the app's home screen. It combines several concepts: queryset filtering, caching, pagination, and user-scoped data access.

**File to modify**:
- `backend/apps/conversations/views.py`
- `backend/apps/conversations/urls.py`
- `backend/config/urls.py` — include conversations URLs

**Endpoint**:
- Method: `GET`
- URL: `/api/conversations/`
- Query params: `filter` (all|unread|starred), `search` (text)
- Response: List of conversations using `ConversationListSerializer`
- **SECURITY**: Queryset is filtered to `request.user` only — a user NEVER sees someone else's conversations

**View logic**:
1. Check Redis cache for this user + filter combination
2. If cache hit → return cached data
3. If cache miss:
   a. Query `Conversation` objects where user is a participant
   b. Apply filter (unread: `unread_count > 0`, starred: `is_starred = True`)
   c. Apply search (match participant name or message content)
   d. Order by `-last_activity_at`
   e. Serialize with `ConversationListSerializer`
   f. Store in Redis cache
   g. Return response

**What you learn**:
- Queryset scoping for multi-tenant security
- `filter()` chaining in Django ORM
- Annotation and subqueries for complex filters
- Integration with the cache layer from Step 2.5
- How one endpoint handles multiple filter modes

**Verify**: Returns only conversations where the user is a participant. Supports `filter` param (all/unread/starred). Caches responses. Returns serialized data with other_participant, last_message, unread_count, is_starred.

---

### Step 2.7 — Create Conversation (Idempotent)

**What**: Build the endpoint to start a new conversation or return an existing one.

**Why**: This teaches **idempotent design** — one of the most important API design patterns. No matter how many times you call it with the same pair, you get the same conversation back.

**File to modify**:
- `backend/apps/conversations/views.py` — add create action

**Endpoint**:
- Method: `POST`
- URL: `/api/conversations/`
- Request body: `{"user_id": "target-user-uuid"}`
- Response:
  - `200 OK` + existing conversation (if pair already exists)
  - `201 Created` + new conversation (if pair is new)

**Logic**:
1. Validate `user_id` exists and is not the requesting user
2. Check if a conversation already exists for this pair:
   ```python
   existing = Conversation.objects.filter(
       participants__user=request.user
   ).filter(
       participants__user=target_user
   ).first()
   ```
3. If exists → return it with status `200`
4. If not → create `Conversation`, create two `ConversationParticipant` entries, invalidate cache for both users, return with status `201`

**What you learn**:
- Idempotent API design — same input always gives same result
- Chained `.filter()` for "conversations where BOTH users are participants"
- Different HTTP status codes for "found existing" vs "created new"
- Cache invalidation on write operations

**Verify**: Creating the same pair twice returns the same conversation ID. Second call returns 200, not 201. Two ConversationParticipant records are created.

---

### Step 2.8 — Conversation Detail & Star/Unstar

**What**: Build the detail view and star toggle endpoint.

**File to modify**:
- `backend/apps/conversations/views.py`

**Two endpoints**:

1. **Conversation Detail**:
   - Method: `GET`
   - URL: `/api/conversations/{id}/`
   - Permission: `IsConversationParticipant`
   - Response: Full conversation data

2. **Star/Unstar**:
   - Method: `PATCH`
   - URL: `/api/conversations/{id}/star/`
   - Permission: `IsConversationParticipant`
   - **SECURITY**: Only modifies the **requesting user's** `ConversationParticipant.is_starred` — NEVER the other participant's
   - Response: Updated `is_starred` value
   - Must invalidate the requesting user's inbox cache

**What you learn**:
- Object-level permissions in action
- DRF `@action` decorator for custom endpoints
- Per-user state — the same conversation has different star states for each participant
- Why `self.get_object()` triggers permission checks

**Verify**: Non-participants get 403. Starring a conversation for Alice doesn't change Dave's star state. Cache is invalidated.

---

### Step 2.9 — Message Serializers

**What**: Build the serializer for messages.

**File to create/modify**:
- `backend/apps/messages/serializers.py`

**`MessageSerializer`**:
- `id` — UUID
- `sender` — Nested: `{id, first_name, last_name, tenant_name}`
- `content` — Message text
- `is_read` — Boolean
- `created_at` — Timestamp

**`MessageCreateSerializer`**:
- Input: `content` (text, required, non-empty)
- Sender is set from `request.user` (not from input — security!)

**What you learn**:
- Read vs write serializers — different shapes for GET vs POST
- Why sender comes from `request.user`, not request body (prevents spoofing)
- Nested serializer reuse

**Verify**: Read serializer includes sender with tenant_name. Write serializer accepts only `content`.

---

### Step 2.10 — Message List & Send Endpoints

**What**: Build endpoints to list messages in a conversation and send new messages.

**Files to modify**:
- `backend/apps/messages/views.py`
- `backend/apps/messages/urls.py`
- `backend/config/urls.py` — include message URLs

**Two endpoints**:

1. **List Messages**:
   - Method: `GET`
   - URL: `/api/conversations/{id}/messages/`
   - Permission: `IsConversationParticipant`
   - Returns messages ordered by `created_at` ascending
   - Use `select_related("sender__tenant")` to avoid N+1

2. **Send Message**:
   - Method: `POST`
   - URL: `/api/conversations/{id}/messages/`
   - Permission: `IsConversationParticipant`
   - Request body: `{"content": "Hello!"}`
   - On success, **also**:
     a. Update `conversation.last_activity_at` to now
     b. Increment the **other participant's** `unread_count` by 1 (using `F()` expression)
     c. Invalidate inbox cache for **both** participants
   - Response: The created message (201)

**What you learn**:
- `F()` expressions — atomic database increment without race conditions
- `select_related` for JOINs across multiple tables
- Side effects of write operations (updating related models, cache invalidation)
- URL nesting — messages live under conversations

**Verify**: Only participants can list/send. Sending a message increments the OTHER user's unread_count. `last_activity_at` is updated. Both users' caches are invalidated.

---

### Step 2.11 — Mark Messages as Read

**What**: Build the endpoint to mark all messages in a conversation as read.

**File to modify**:
- `backend/apps/messages/views.py`

**Endpoint**:
- Method: `POST`
- URL: `/api/conversations/{id}/messages/read/`
- Permission: `IsConversationParticipant`
- Logic:
  1. Mark all unread messages from the OTHER user as `is_read = True`
  2. Reset the requesting user's `unread_count` to 0
  3. Set `last_read_at` to now
  4. Invalidate the requesting user's inbox cache
- Response: `{"status": "ok"}`

**What you learn**:
- Bulk update with `queryset.update()`
- Why we only mark messages from the OTHER user (you don't "read" your own messages)
- Resetting counters atomically

**Verify**: After marking as read, `unread_count` is 0. Only messages from the other user are marked. Cache is invalidated.

---

## Phase 3: Real-Time (WebSocket)

> **What you'll learn**: How WebSocket connections work, how Django Channels handles async communication, and how to push events from a synchronous REST view to an async WebSocket consumer via Redis.

### Step 3.1 — ASGI Configuration

**What**: Configure Django's ASGI application to route HTTP and WebSocket traffic.

**Files to modify**:
- `backend/config/asgi.py`
- `backend/routing.py` (create new)

**`config/asgi.py`** must:
- Use `ProtocolTypeRouter` to separate HTTP and WebSocket traffic
- HTTP goes to standard Django
- WebSocket goes through `TokenAuthMiddleware` → `URLRouter` → `ChatConsumer`

**`routing.py`** must:
- Define `websocket_urlpatterns` list
- Map `ws/chat/` to `ChatConsumer`

**What you learn**:
- ASGI protocol routing — how one server handles both HTTP and WebSocket
- The middleware pipeline for WebSocket connections
- URL routing for WebSocket (similar to HTTP URL routing but separate)

**Verify**: `asgi.py` uses `ProtocolTypeRouter`. `routing.py` maps `ws/chat/` to the consumer.

---

### Step 3.2 — WebSocket Auth Middleware

**What**: Build middleware that authenticates WebSocket connections via token in query string.

**File to create**:
- `backend/middleware.py`

**Logic**:
1. Parse `token` from the WebSocket query string: `ws://host/ws/chat/?token=abc123`
2. Look up the token in `rest_framework.authtoken.models.Token`
3. If valid → set `scope["user"]` to the token's user
4. If invalid → set `scope["user"]` to `AnonymousUser`
5. Use `@database_sync_to_async` for the database lookup (Channels runs async)

**What you learn**:
- WebSocket authentication differs from HTTP (no headers, use query params)
- `database_sync_to_async` — bridging sync Django ORM and async Channels
- The `scope` dictionary — WebSocket's equivalent of HTTP `request`
- Middleware pattern in Django Channels

**Verify**: Valid token → authenticated user in scope. Invalid/missing token → AnonymousUser.

---

### Step 3.3 — Chat Consumer

**What**: Build the WebSocket consumer that manages user connections and receives pushed events.

**File to modify**:
- `backend/apps/messages/consumers.py`

**`ChatConsumer`** must:
- On `connect`:
  1. Get the user from `self.scope["user"]`
  2. If anonymous → reject connection (`await self.close()`)
  3. Set `self.group_name = f"user_{self.user.id}"`
  4. Join the group: `await self.channel_layer.group_add(self.group_name, self.channel_name)`
  5. Accept the connection: `await self.accept()`
- On `disconnect`:
  1. Leave the group: `await self.channel_layer.group_discard(...)`
- Event handlers (called when the channel layer delivers a group message):
  - `async def new_message(self, event)` → forward to client as JSON
  - `async def message_read(self, event)` → forward to client as JSON
  - `async def conversation_updated(self, event)` → forward to client as JSON

**What you learn**:
- `AsyncJsonWebsocketConsumer` — async WebSocket handler
- Channel groups — pub/sub within Django Channels
- The relationship between channel group names and event routing
- Why the consumer is **passive** — it doesn't process messages, it just receives pushes

**Verify**: Consumer joins `user_{id}` group on connect. Rejects anonymous users. Has 3 event handlers.

---

### Step 3.4 — Push WebSocket Events from REST Views

**What**: Modify the Send Message view (Step 2.10) and Mark as Read view (Step 2.11) to push WebSocket events after database writes.

**Files to modify**:
- `backend/apps/messages/views.py` — add WebSocket push after creating a message
- Create a helper: `backend/apps/messages/utils.py` — `send_ws_event()` function

**Helper function**:
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_ws_event(user_id: str, event_type: str, data: dict) -> None:
    """Push an event to a user's personal WebSocket channel group."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {"type": event_type, "data": data},
    )
```

**When sending a message**, push to the **recipient** (not the sender):
```python
send_ws_event(
    user_id=str(recipient.user.id),
    event_type="new_message",
    data={
        "conversation_id": str(conversation.id),
        "message": MessageSerializer(message).data,
    },
)
```

**When marking as read**, push to the **other participant** (they see the read receipt):
```python
send_ws_event(
    user_id=str(other_participant.user.id),
    event_type="message_read",
    data={
        "conversation_id": str(conversation.id),
        "reader_id": str(request.user.id),
        "read_at": timezone.now().isoformat(),
    },
)
```

**What you learn**:
- `get_channel_layer()` — accessing the channel layer from synchronous code
- `async_to_sync` — calling async code from sync views
- Event type naming — must match the consumer method name (`new_message` → `async def new_message`)
- Why we push to the recipient, not the sender

**Verify**: When a message is sent via REST, a WebSocket event is pushed to the recipient's group. When messages are marked as read, a read receipt is pushed to the other participant.

---

## Phase 4: Celery & Export

> **What you'll learn**: How Celery distributes work across processes, how to track async task state, and how to serve generated files.

### Step 4.1 — Celery Configuration

**What**: Configure the Celery app to use Redis as its message broker.

**File to modify**:
- `backend/config/celery.py` — complete the skeleton from Step 1.1
- `backend/config/__init__.py` — ensure Celery app is loaded on Django startup

**`config/celery.py`**:
- Create a Celery app named `"config"`
- Set `broker_url` from `CELERY_BROKER_URL` env var
- Set `result_backend` to the same Redis URL
- Call `autodiscover_tasks()` to find tasks in all installed apps

**`config/__init__.py`**:
```python
from .celery import app as celery_app
__all__ = ("celery_app",)
```

**What you learn**:
- Celery architecture — broker (Redis) dispatches tasks to workers
- `autodiscover_tasks()` — automatically finds `tasks.py` in each Django app
- Why the Celery app is imported in `__init__.py` (ensures it's loaded when Django starts)

**Verify**: Celery app is configured with Redis broker. `__init__.py` exports it.

---

### Step 4.2 — Export Celery Task

**What**: Build the Celery task that exports a conversation to a JSON file.

**File to modify**:
- `backend/apps/exports/tasks.py`

**Task logic**:
1. Accept `export_task_id` as argument
2. Update ExportTask status to `PROCESSING`
3. Fetch the conversation and all its messages (ordered by `created_at`)
4. Build a JSON structure with conversation metadata and all messages
5. Write to a file in the `exports/` directory
6. Update ExportTask: status=`COMPLETED`, file_path=path
7. If any error: status=`FAILED`, error_message=str(error)
8. Wrap everything in try/except

**JSON export format**:
```json
{
  "conversation_id": "uuid",
  "participants": ["alice@acme.com", "dave@globex.com"],
  "exported_at": "2026-09-24T12:00:00Z",
  "messages": [
    {
      "sender": "alice@acme.com",
      "content": "Hello!",
      "timestamp": "2026-09-24T10:00:00Z",
      "is_read": true
    }
  ]
}
```

**What you learn**:
- `@shared_task` decorator — makes a function a Celery task
- Task error handling — graceful failure with status tracking
- File I/O in Python — `json.dump` to files
- Why the task receives an ID, not the object (serialization across processes)

**Verify**: Task updates status through PENDING → PROCESSING → COMPLETED/FAILED. Creates a valid JSON file. Error handling catches exceptions.

---

### Step 4.3 — Export API Endpoints

**What**: Build endpoints to request an export and download the result.

**Files to modify**:
- `backend/apps/exports/serializers.py`
- `backend/apps/exports/views.py`
- `backend/apps/exports/urls.py`
- `backend/config/urls.py` — include exports URLs

**Two endpoints**:

1. **Request Export**:
   - Method: `POST`
   - URL: `/api/conversations/{id}/export/`
   - Permission: `IsConversationParticipant`
   - Logic: Create ExportTask, call `export_conversation.delay(task_id)`, return 202 Accepted
   - Response: `{"id": "task-uuid", "status": "pending"}`

2. **Download Export**:
   - Method: `GET`
   - URL: `/api/exports/{id}/download/`
   - Permission: Must be the user who requested the export
   - Logic: Check status is `COMPLETED`, serve the file
   - Use `FileResponse` for streaming the file

**What you learn**:
- `.delay()` — dispatching a Celery task asynchronously
- HTTP 202 Accepted — "I got your request, it's being processed"
- `FileResponse` — serving files from Django
- Status polling pattern — frontend checks back for completion

**Verify**: POST creates ExportTask and dispatches Celery task. GET serves file when complete, returns 404/400 when not ready.

---

## Phase 5: Frontend

> **What you'll learn**: React component architecture, TypeScript for type safety, TanStack Query for server state, WebSocket for real-time updates, and how the frontend connects to every backend endpoint you built.

### Step 5.1 — React Project Setup

**What**: Initialize the React project with Vite, TypeScript, and Tailwind CSS.

**Files to create**:
```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   └── types/
│       └── index.ts
├── index.html
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── vite.config.ts
└── package.json
```

**`package.json` dependencies**:
- `react`, `react-dom`
- `react-router-dom`
- `@tanstack/react-query`
- `axios`
- `typescript`
- `tailwindcss`, `postcss`, `autoprefixer`
- `@types/react`, `@types/react-dom`

**`src/types/index.ts`**: Define all TypeScript interfaces (Tenant, User, Conversation, Message, ExportTask, WSEvent) as specified in the react-frontend skill.

**What you learn**:
- Vite — fast modern build tool
- TypeScript strict mode — catching errors at compile time
- Tailwind CSS setup — utility-first styling
- Why types are defined centrally

**Verify**: Project skeleton exists. TypeScript types are defined. Tailwind is configured.

---

### Step 5.2 — API Client & Auth Context

**What**: Build the Axios HTTP client and authentication context.

**Files to create**:
```
frontend/src/
├── api/
│   └── client.ts
└── contexts/
    └── AuthContext.tsx
```

**`api/client.ts`**:
- Create Axios instance with base URL from `VITE_API_URL`
- Add request interceptor that attaches `Authorization: Token xxx` header
- Read token from `localStorage`

**`AuthContext.tsx`**:
- Store `user` and `token` in React state
- `login(email, password)` — calls `/api/auth/login/`, stores token in localStorage
- `logout()` — clears token from localStorage
- `isAuthenticated` computed from token presence
- Provide via React Context

**What you learn**:
- Axios interceptors — automatic header injection
- React Context — sharing auth state across components
- localStorage for token persistence
- Why the API client is a separate module (separation of concerns)

**Verify**: API client attaches auth header. Context provides login/logout/user. Token persists in localStorage.

---

### Step 5.3 — Login Page

**What**: Build the login page — email/password form.

**Files to create**:
```
frontend/src/
├── pages/
│   └── LoginPage.tsx
└── App.tsx              # Update with routing
```

**`LoginPage.tsx`**:
- Email and password inputs
- Submit button
- Error message display for invalid credentials
- On success → redirect to inbox
- Tailwind styled form centered on page

**`App.tsx`**:
- Set up React Router with routes:
  - `/login` → LoginPage
  - `/` → InboxPage (protected, redirect to login if unauthenticated)
  - `/conversations/:id` → ConversationPage (protected)
- Wrap with `QueryClientProvider` (TanStack Query) and `AuthProvider`

**What you learn**:
- React Router v6 routing
- Protected routes — redirecting unauthenticated users
- Form handling in React
- Provider nesting (QueryClient → Auth → Router)

**Verify**: Login form works. Invalid credentials show error. Success redirects to inbox.

---

### Step 5.4 — Inbox View (Conversation List)

**What**: Build the inbox — the main screen showing all conversations.

**Files to create**:
```
frontend/src/
├── api/
│   └── conversations.ts
├── hooks/
│   └── useConversations.ts
├── components/
│   ├── layout/
│   │   └── AppLayout.tsx
│   ├── inbox/
│   │   ├── InboxView.tsx
│   │   ├── ConversationItem.tsx
│   │   ├── InboxFilters.tsx
│   │   └── InboxSearch.tsx
│   └── common/
│       ├── LoadingSpinner.tsx
│       ├── ErrorState.tsx
│       ├── UnreadBadge.tsx
│       └── StarIcon.tsx
└── pages/
    └── InboxPage.tsx
```

**`api/conversations.ts`**: Functions that call the backend:
- `fetchConversations(filter, search)` → `GET /api/conversations/`
- `createConversation(userId)` → `POST /api/conversations/`
- `toggleStar(conversationId)` → `PATCH /api/conversations/{id}/star/`

**`hooks/useConversations.ts`**: TanStack Query hook:
- `useConversations(filter, search)` → `useQuery` with key `['conversations', filter, search]`
- `useCreateConversation()` → `useMutation` that invalidates conversations
- `useToggleStar()` → `useMutation` that invalidates conversations

**`InboxView.tsx`** must show:
- Search bar at top
- Filter tabs: All | Unread | Starred
- List of `ConversationItem` components
- Loading spinner while fetching
- Empty state when no conversations
- Error state on failure

**`ConversationItem.tsx`** must show:
- Other participant's name + tenant name
- Last message preview (truncated)
- Relative time (e.g., "2 min ago")
- Unread badge (red circle with count)
- Star icon (yellow filled or gray outline)
- Click → navigate to `/conversations/{id}`

**What you learn**:
- TanStack Query — `useQuery` for data fetching, `useMutation` for writes
- Query key design — `['conversations', filter, search]` auto-refetches when params change
- Component composition — InboxView orchestrates smaller components
- Loading/error/empty state handling pattern
- Relative time formatting

**Verify**: Inbox shows conversations. Filters work (all/unread/starred). Search works. Star toggle works. Click navigates to conversation.

---

### Step 5.5 — Conversation View (Messages)

**What**: Build the chat view — message history, composer, send button.

**Files to create**:
```
frontend/src/
├── api/
│   └── messages.ts
├── hooks/
│   └── useMessages.ts
├── components/
│   └── conversation/
│       ├── ConversationView.tsx
│       ├── MessageList.tsx
│       ├── MessageBubble.tsx
│       ├── MessageComposer.tsx
│       └── EmptyState.tsx
└── pages/
    └── ConversationPage.tsx
```

**`api/messages.ts`**: Functions:
- `fetchMessages(conversationId)` → `GET /api/conversations/{id}/messages/`
- `sendMessage(conversationId, content)` → `POST /api/conversations/{id}/messages/`
- `markAsRead(conversationId)` → `POST /api/conversations/{id}/messages/read/`

**`hooks/useMessages.ts`**: TanStack Query hooks:
- `useMessages(conversationId)` → `useQuery`
- `useSendMessage(conversationId)` → `useMutation` with optimistic append
- `useMarkAsRead(conversationId)` → `useMutation`

**`ConversationView.tsx`** must:
- Fetch messages on mount
- Mark as read on mount (if there are unread messages)
- Show `MessageList` with scrollable area
- Show `MessageComposer` at bottom
- Auto-scroll to bottom on new messages
- Handle loading, error, empty states

**`MessageBubble.tsx`** must:
- Right-aligned + indigo background for sender's messages
- Left-aligned + gray background for other's messages
- Show sender name + tenant name
- Show timestamp
- Show read status (checkmark or similar)

**`MessageComposer.tsx`** must:
- Text input (multiline)
- Send button
- Disable send while mutation is pending
- Clear input after successful send
- Submit on Enter (Shift+Enter for newline)

**What you learn**:
- Optimistic updates — message appears instantly before server confirms
- Auto-scrolling with `useRef` and `scrollIntoView`
- Message bubble alignment based on sender
- Input handling — Enter to send, Shift+Enter for newline
- Mutation callbacks — `onSuccess` to clear input and update cache

**Verify**: Messages display correctly. Sender's messages are right-aligned. Send works. Auto-scrolls on new messages. Loading/error/empty states handled.

---

### Step 5.6 — User Search (Start New Conversation)

**What**: Build the user search panel — find people to message across tenants.

**Files to create**:
```
frontend/src/
├── api/
│   └── users.ts
├── hooks/
│   └── useUserSearch.ts
└── components/
    └── users/
        ├── UserSearch.tsx
        └── UserResult.tsx
```

**`api/users.ts`**:
- `searchUsers(query)` → `GET /api/users/search/?q=query`

**`hooks/useUserSearch.ts`**:
- `useUserSearch(query)` → `useQuery` with `enabled: query.length >= 2` (don't search on empty/single char)

**`UserSearch.tsx`**:
- Search input with debounce (300ms)
- List of `UserResult` components
- "No results" empty state
- Triggered by a "New Conversation" button in the inbox

**`UserResult.tsx`**:
- Shows: full name, email, tenant name (crucial for cross-tenant visibility)
- Click → calls `createConversation(userId)` → navigates to the conversation

**What you learn**:
- Debounced search — don't fire API call on every keystroke
- `enabled` option in TanStack Query — conditional fetching
- Cross-tenant UX — showing tenant name helps users identify the right person
- Composing hooks — UserSearch uses both `useUserSearch` and `useCreateConversation`

**Verify**: Search finds users across tenants. Tenant name is visible. Click creates/opens conversation. Debounce prevents excessive API calls.

---

### Step 5.7 — WebSocket Integration

**What**: Connect the frontend to the WebSocket server for real-time updates.

**Files to create**:
```
frontend/src/
├── utils/
│   └── websocket.ts
└── hooks/
    └── useWebSocket.ts
```

**`utils/websocket.ts`**: WebSocket manager class:
- `connect(token)` — establish connection to `ws://host/ws/chat/?token=xxx`
- `on(eventType, handler)` — register event handlers
- `disconnect()` — close connection
- Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, 16s)
- Max 5 reconnection attempts

**`hooks/useWebSocket.ts`**: React hook that:
1. Connects WebSocket on mount (if authenticated)
2. Registers handlers for each event type:
   - `new_message` → `queryClient.setQueryData` to append message (with deduplication by `message.id`), then `invalidateQueries(['conversations'])`
   - `message_read` → `invalidateQueries(['messages', conversationId])`
   - `conversation_updated` → `invalidateQueries(['conversations'])`
3. Disconnects on unmount
4. Place in `AppLayout.tsx` so it's active for all authenticated pages

**DEDUPLICATION IS CRITICAL**:
```typescript
// When appending a new message from WebSocket:
queryClient.setQueryData<Message[]>(
  ['messages', conversationId],
  (old = []) => {
    // DEDUP: Skip if message already exists (from HTTP response or previous push)
    if (old.some(m => m.id === newMessage.id)) return old;
    return [...old, newMessage];
  }
);
```

**What you learn**:
- WebSocket lifecycle — connect, message, close, error
- Exponential backoff — smart reconnection strategy
- Cache manipulation — `setQueryData` for instant updates
- Deduplication — preventing duplicate messages when WS + HTTP overlap
- Query invalidation — triggering refetches from WebSocket events

**Verify**: WebSocket connects on login. New messages appear instantly. Inbox updates when messages arrive. No duplicate messages after refetch.

---

### Step 5.8 — Export UI

**What**: Add export functionality — request export, poll for status, download file.

**Files to create**:
```
frontend/src/
├── api/
│   └── exports.ts
└── hooks/
    └── useExport.ts
```

**`api/exports.ts`**:
- `requestExport(conversationId)` → `POST /api/conversations/{id}/export/`
- `getExportStatus(taskId)` → `GET /api/exports/{id}/`  (if you have a status endpoint)
- `downloadExport(taskId)` → `GET /api/exports/{id}/download/` (opens download)

**`hooks/useExport.ts`**:
- `useRequestExport()` → `useMutation`
- On success, show a toast/notification with status
- Poll for completion using `useQuery` with `refetchInterval` when status is `pending`/`processing`
- When `completed`, show download link/button

**UI Integration**:
- Add an "Export" button in the conversation header
- Show export status (pending → processing → completed → download link)

**What you learn**:
- Polling pattern with TanStack Query — `refetchInterval` for periodic checks
- File downloads in the browser
- Async task UX — showing progress for long-running operations

**Verify**: Export button triggers task. Status updates from pending to completed. File downloads successfully.

---

## Phase 6: Docker & Deployment

> **What you'll learn**: How Docker containerizes applications, how Docker Compose orchestrates multi-service systems, and how health checks ensure services start in the right order.

### Step 6.1 — Backend Dockerfile

**What**: Create the Dockerfile for the Django backend.

**File to create**: `backend/Dockerfile`

**Must include**: Python 3.12 slim base, system deps (gcc, libpq-dev for psycopg2), pip install from requirements.txt, copy source code, expose port 8000.

**What you learn**: Multi-stage thinking (system deps → Python deps → app code), layer caching in Docker.

---

### Step 6.2 — Frontend Dockerfile

**What**: Create the Dockerfile for the React frontend.

**File to create**: `frontend/Dockerfile`

**Must include**: Node 20 alpine base, npm ci for deterministic installs, copy source, expose port 3000.

**What you learn**: `npm ci` vs `npm install`, Alpine images for small size.

---

### Step 6.3 — Docker Compose

**What**: Create docker-compose.yml that wires everything together.

**File to create**: `docker-compose.yml` (project root)

**5 services**: db, redis, backend, celery-worker, frontend. With health checks, depends_on with conditions, shared volumes for exports, environment variables.

**What you learn**: Service orchestration, health checks, dependency ordering, named volumes, environment variable management.

---

### Step 6.4 — README Documentation

**What**: Write a comprehensive README.

**File to create**: `README.md` (project root)

**Must cover**:
- Architecture overview (with diagram reference to SYSTEM_DESIGN.md)
- Prerequisites (Docker, Docker Compose)
- Quick start (`docker compose up --build`)
- Seed data (tenants, users, passwords, auth tokens)
- API endpoints summary
- WebSocket testing with wscat
- Running tests
- Celery worker logs
- Troubleshooting common issues

**What you learn**: Technical documentation as a deliverable.

---

## Phase 7: Testing

> **What you'll learn**: How to write tests that verify security, data integrity, and business logic — the tests that actually matter.

### Step 7.1 — Test Setup (conftest.py + factories)

**Files to create**:
- `backend/tests/__init__.py`
- `backend/tests/conftest.py` — Shared pytest fixtures
- `backend/pytest.ini` or `backend/pyproject.toml` — pytest configuration

**Fixtures**: `acme_tenant`, `globex_tenant`, `alice`, `bob`, `dave`, `alice_client`, `dave_client`, `alice_dave_conversation`, etc.

---

### Step 7.2 — Authorization Tests

**File to create**: `backend/tests/test_permissions.py`

**Must test**:
1. Non-participant cannot GET conversation detail → 403
2. Non-participant cannot send message → 403
3. Non-participant cannot star conversation → 403
4. Non-participant cannot export conversation → 403
5. Unauthenticated user gets 401 on all endpoints

---

### Step 7.3 — Inbox & Conversation Tests

**File to create**: `backend/tests/test_conversations_api.py`

**Must test**:
1. Inbox returns only user's conversations (isolation)
2. Inbox filter=unread works
3. Inbox filter=starred works
4. Conversation creation is idempotent (same ID returned twice)
5. Star state is per-user (Alice's star doesn't affect Dave)

---

### Step 7.4 — Message Tests

**File to create**: `backend/tests/test_messages_api.py`

**Must test**:
1. Send message returns 201
2. Sending increments other user's unread_count
3. Mark as read resets unread_count to 0
4. Messages are ordered by created_at

---

### Step 7.5 — User Search Safety Tests

**File to create**: `backend/tests/test_user_search.py`

**Must test**:
1. Search returns matching users
2. Response never contains password, last_login, is_superuser, is_staff
3. Requesting user is excluded from results
4. Cross-tenant search works

---

### Step 7.6 — Cache Tests

**File to create**: `backend/tests/test_cache.py`

**Must test**:
1. Inbox response is cached (second request doesn't hit DB)
2. Cache is invalidated after sending a message
3. Cache is invalidated after starring/unstarring
4. Cache is invalidated for both participants on new message

---

### Step 7.7 — WebSocket Tests

**File to create**: `backend/tests/test_websocket.py`

**Must test**:
1. Valid token → connection accepted
2. No token → connection rejected
3. Invalid token → connection rejected

---

### Step 7.8 — Export Tests

**File to create**: `backend/tests/test_export.py`

**Must test**:
1. Export request creates ExportTask with status=pending
2. Celery task updates status to completed
3. Completed export can be downloaded
4. Failed export has error_message

---

## Summary — The Complete Step Map

| Phase | Steps | What You Build | What You Learn |
|-------|-------|----------------|----------------|
| **1. Scaffolding** | 1.1–1.7 | Django project, 5 models, seed data | Django architecture, ORM, relationships, migrations |
| **2. REST API** | 2.1–2.11 | 11 endpoints, permissions, caching | DRF, serializers, permissions, Redis caching |
| **3. Real-Time** | 3.1–3.4 | WebSocket consumer, event pushing | Django Channels, ASGI, async/sync bridge |
| **4. Celery** | 4.1–4.3 | Export task + endpoints | Task queues, async processing, file generation |
| **5. Frontend** | 5.1–5.8 | Complete React app | React, TypeScript, TanStack Query, WebSocket |
| **6. Docker** | 6.1–6.4 | Containerized deployment | Docker, Compose, service orchestration |
| **7. Testing** | 7.1–7.8 | 30+ test cases | pytest, authorization testing, integration tests |

**Total: 7 phases, 30 steps, ~80 files**
