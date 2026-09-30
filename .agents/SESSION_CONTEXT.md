# Session Context — Analysis Snapshot

> Created for ongoing work sessions. Does **not** replace `MEMORY.md` or `SYSTEM_DESIGN.md`.
> Update this file when making session-specific notes; update `MEMORY.md` only with user permission after real phase/decision changes.

**Analyzed:** 2026-09-29

---

## What This Project Is

Cross-tenant 1:1 messaging: users in different orgs (tenants) can DM each other. Stack: Django/DRF + Channels + Celery + PostgreSQL + Redis + React/TS/Vite, all via Docker Compose.

**Status per MEMORY.md:** Phases 1–7 marked complete (backend, REST, WebSocket, Celery export, frontend, Docker, tests).

---

## Governance Map (do not edit without permission)

| File | Role |
|------|------|
| `SYSTEM_DESIGN.md` | Authoritative architecture, data model, API, WS protocol |
| `GEMINI.md` | Always-on project rules |
| `backend/GEMINI.md` | Backend coding standards |
| `frontend/GEMINI.md` | Frontend coding standards |
| `AGENTS.md` | Approval gates + safety restrictions |
| `.agents/MEMORY.md` | Decisions + progress + gotchas |
| `IMPLEMENTATION_PLAN.md` | Step-by-step build guide (historical) |
| `.agents/skills/*` | On-demand patterns (6 skills) |

### Skills

1. `django-backend` — models, serializers, views, migrations
2. `react-frontend` — components, hooks, TanStack Query, WS client
3. `api-authorization` — endpoint contract + authz rules
4. `websocket-realtime` — Channels, middleware, dedup
5. `docker-deployment` — Compose, Dockerfiles, env
6. `testing-strategy` — pytest fixtures, critical cases

### Hard rules from AGENTS.md

- Ask before: git write, builds, installs, scripts (`docker compose exec`), new deps/services
- Never modify governance files without permission
- Docker-first: no host `python`/`npm`/`pip`
- Stay aligned with `SYSTEM_DESIGN.md` unless discussed

---

## Key Architecture (implemented)

- **Tenants** → **Users** (email login, DRF Token auth — not JWT)
- **Conversation** + **ConversationParticipant** (per-user star / unread / last_read)
- **Message** (app label `chat_messages` to avoid Django contrib clash)
- **ExportTask** + Celery async JSON export
- Inbox Redis cache-aside: `inbox:{user_id}:{filter}`, TTL ~45s, invalidate on mutations
- WS: `ws/chat/?token=...`, personal groups `user_{id}`, events: `new_message`, `message_read`, `conversation_updated`

### Seed users (password: `password123`)

- Acme: alice, bob, charlie `@acme.com`
- Globex: dave, eve, frank `@globex.com`
- Pre-seeded: Alice↔Bob, Alice↔Dave, Bob↔Eve

---

## Docs vs Code — Notable Divergences

These are useful when planning changes; design docs describe the *target* layout more than the *current* frontend.

| Area | Design / skills say | Actual codebase |
|------|---------------------|-----------------|
| Frontend layout | Nested `components/inbox/`, `conversation/`, `hooks/useConversations.ts`, `api/conversations.ts`, etc. | Flatter: `Inbox.tsx`, `ConversationView.tsx`, `UserSearch.tsx`; API calls often via `apiClient` inside components |
| Frontend API modules | `conversations.ts`, `messages.ts`, `users.ts`, `exports.ts` | Only `api/client.ts` |
| Routing | Separate inbox + `/conversations/:id` pages | Single `/` layout with sidebar selection state |
| Postgres image | postgres:16 in design | `postgres:15-alpine` in compose |
| Compose service name | `celery-worker` | `celery_worker` |
| Backend GEMINI `BaseModel` | Shared BaseModel with UUID + created_at | Models define UUID/fields inline (no shared BaseModel) |
| Export volume | Named volume `backend_exports` | Backend bind-mount `./backend:/app` (exports under app tree) |

Backend apps, URLs, permissions, cache, WS middleware/consumer, tests suite, and seed command largely match the design.

---

## Working Ports

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- WS: `ws://localhost:8000/ws/chat/?token=<token>`

---

## Active initiative — MiniStack Cognito auth

- **Plan doc:** `docs/MINISTACK_COGNITO_PLAN.md`
- **Phase 1–3:** Complete (user verified / seed in code)
- **Phase 4 (code done):** Login uses Cognito InitiateAuth via Vite `/aws-cognito` proxy; Bearer on REST; `/api/auth/cognito-config/`
- **Next:** Recreate frontend so Vite proxy is picked up; log in as alice@acme.com / Password123!
- **No new npm packages** (AWS JSON protocol over fetch)

## Ready for Changes

Next work should start from user-requested changes. Before implementing:

1. Confirm whether change needs design/API/WS contract updates (needs ask)
2. Activate the matching skill for patterns
3. Prefer editing existing files; ask before builds/tests/deps
