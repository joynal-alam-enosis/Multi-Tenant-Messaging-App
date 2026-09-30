# Project Memory — Cross-Tenant Messaging Application

> This file tracks architectural decisions, progress, and context that should persist across development sessions.

---

## Key Decisions Made

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | UUID primary keys on all models | Prevents ID enumeration attacks; distributed-friendly | 2026-09-24 |
| 2 | Separate `ConversationParticipant` join table | Per-user starred state, unread count, last_read_at | 2026-09-24 |
| 3 | `last_activity_at` on `Conversation` model | Fast inbox sorting without joining to messages | 2026-09-24 |
| 4 | Personal WebSocket groups (`user_{id}`) | Simple routing — push to recipient's group only | 2026-09-24 |
| 5 | Cache-aside pattern for inbox (30-60s TTL) | Reduces DB load; invalidate on every mutation | 2026-09-24 |
| 6 | Idempotent conversation creation | Check existing pair before INSERT; return 200 vs 201 | 2026-09-24 |
| 7 | **Cognito JWT auth (Bearer) via MiniStack** | Replaces DRF Token; managed identity, standard JWT, MFA-ready | 2026-09-29 |
| 8 | Daphne as ASGI server | Handles both HTTP and WebSocket in a single process | 2026-09-24 |
| 9 | Redis DB 0 for cache, DB 1 for Celery broker | Logical separation without separate Redis instances | 2026-09-24 |
| 10 | TanStack Query for all server state | Caching, refetching, optimistic updates, WebSocket integration | 2026-09-24 |
| 11 | Docker-first development workflow | Zero local setup. All processes (Python, Node, DB) run entirely in Docker containers via `docker compose`. | 2026-09-24 |
| 12 | MiniStack as local Cognito emulator | Full Cognito API compatibility locally; no AWS account needed for dev | 2026-09-29 |
| 13 | `cognito_sub` on User model (not PK) | Links Django user to Cognito identity; avoids FK rewrites | 2026-09-29 |
| 14 | Tenant only in Django (not Cognito) | Phase 1 simplicity; tenant assignment via seed/admin | 2026-09-29 |
| 15 | JIT local user sync on first JWT | Resilient to drift; seed provides demo users | 2026-09-29 |

---

## Seed Data

| Tenant | Users | Passwords |
|--------|-------|-----------|
| Acme Corp (slug: `acme`) | alice@acme.com, bob@acme.com, charlie@acme.com | `Password123!` |
| Globex Inc (slug: `globex`) | dave@globex.com, eve@globex.com, frank@globex.com | `Password123!` |

> **Note:** Passwords are Cognito-compliant (min 8 chars, uppercase, lowercase, number, symbol). Override with `SEED_PASSWORD` env var.

**Pre-seeded conversations:**
- Alice ↔ Bob (same tenant)
- Alice ↔ Dave (cross-tenant)
- Bob ↔ Eve (cross-tenant)

Both Cognito users (in MiniStack/AWS) and local Django users are created/linked via `bootstrap_cognito` and `seed` management commands.

---

## Development Progress

- [x] **Phase 1: Backend Foundation**
  - [x] Django project setup (`config/`)
  - [x] Tenant model + migration
  - [x] Custom User model + migration
  - [x] Conversation + ConversationParticipant models
  - [x] Message model
  - [x] ExportTask model
  - [x] Seed data management command

- [x] **Phase 2: REST API**
  - [x] Auth endpoint (Cognito config + me)
  - [x] User search endpoint
  - [x] Inbox endpoint (with caching)
  - [x] Conversation create/get (idempotent)
  - [x] Conversation detail
  - [x] Star/unstar endpoint
  - [x] Message list (paginated)
  - [x] Send message endpoint
  - [x] Mark messages as read
  - [x] Permissions (`IsConversationParticipant`)

- [x] **Phase 3: Real-Time**
  - [x] ASGI configuration
  - [x] WebSocket auth middleware (Cognito JWT + legacy DRF Token)
  - [x] ChatConsumer (connect, disconnect, event handlers)
  - [x] Push events from REST views to WebSocket

- [x] **Phase 4: Celery & Export**
  - [x] Celery configuration
  - [x] Export task
  - [x] Request export endpoint
  - [x] Download export endpoint

- [x] **Phase 5: Frontend**
  - [x] React project setup (Vite + TypeScript + Tailwind)
  - [x] API client (Axios instance, Bearer tokens, auto-refresh)
  - [x] Auth context + login page (Cognito InitiateAuth)
  - [x] Inbox view (conversation list, filters, search)
  - [x] Conversation view (messages, composer)
  - [x] User search (cross-tenant)
  - [x] WebSocket integration
  - [x] Export UI

- [x] **Phase 6: Docker & Deployment**
  - [x] Backend Dockerfile
  - [x] Frontend Dockerfile
  - [x] docker-compose.yml (with ministack service)
  - [x] Health checks
  - [x] README documentation

- [x] **Phase 7: Testing**
  - [x] Inbox isolation tests
  - [x] Participant permission tests
  - [x] Star isolation tests
  - [x] Idempotency tests
  - [x] User search safety tests
  - [x] Cache invalidation tests
  - [x] WebSocket tests (Cognito JWT validation)
  - [x] Export tests

- [x] **Phase 8: Cognito Integration (Ministack)**
  - [x] MiniStack service in Docker Compose
  - [x] `bootstrap_cognito` management command (idempotent pool/client)
  - [x] `User.cognito_sub` field + migration
  - [x] `CognitoJWTAuthentication` (JWKS validation, runtime env var check)
  - [x] Seed command creates Cognito users + links local users
  - [x] Frontend: Cognito InitiateAuth, token refresh, GlobalSignOut
  - [x] Test helpers for Cognito JWT (RSA key pair, runtime verification toggle)

---

## Known Gotchas

1. **Django `messages` app conflict**: The built-in `django.contrib.messages` will conflict with our `apps.messages` app name. Consider using `chat_messages` or a different label in `AppConfig`.
2. **WebSocket token in query string**: Less secure than headers but WebSocket API doesn't support custom headers. Acceptable for development; in production use secure WebSocket (wss://) and short-lived tokens.
3. **Celery worker needs same codebase**: The celery-worker container uses the same Docker image as the backend. Any code change requires rebuilding both.
4. **Redis DB numbers**: Cache = DB 0, Celery = DB 1, Channel Layer = default (DB 0). Adjust if conflicts arise.
5. **CORS**: Frontend on port 3000, backend on port 8000. Must configure `django-cors-headers` with `CORS_ALLOWED_ORIGINS`.
6. **MiniStack JWT signature verification**: MiniStack stub tokens may not verify with real JWKS. Use `COGNITO_VERIFY_JWT=false` locally (default when `AWS_ENDPOINT_URL` is set). Production uses real Cognito with verification enabled.
5. **Settings import-time caching**: `COGNITO_VERIFY_JWT` in settings.py is read at import time. Authentication module reads env var at runtime for tests. For production, set env vars before container start.
6. **Test database migrations**: Run `docker compose exec backend python manage.py migrate` before tests if schema changes.