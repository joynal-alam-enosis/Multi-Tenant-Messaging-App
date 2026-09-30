# MiniStack Cognito Integration — Change Scope & Implementation Plan

> **Status:** In progress — Phase 4 (frontend Cognito login)  
> **Created:** 2026-09-29  
> **Updated:** 2026-09-29  
> **References:** [MiniStack Cognito docs](https://ministack.org/docs/services/cognito), [MiniStack Docker](https://ministack.org/docs), `SYSTEM_DESIGN.md`, `.agents/MEMORY.md`

### Accepted decisions (2026-09-29)

| # | Choice | Notes |
|---|--------|--------|
| D1 | **A** Frontend → Cognito directly | Django does not proxy login in Phase 1–4 |
| D2 | **C** Tenant only in Django | Assign on seed / admin |
| D3 | **A + seed** | JIT local user on first JWT; seed for demos |
| D4 | UUID PK + `cognito_sub` | No FK rewrites |
| D5 | WS `?token=` = Access JWT | Same query param, new token type |
| D6 | Persist MiniStack state | `PERSIST_STATE=1` + volume |
| D7 | Cognito-compliant seed passwords | e.g. `Password123!` (Phase 3) |

---

## 1. Goal

Replace **Django REST Framework Token authentication** with **Amazon Cognito–compatible auth**, using **[MiniStack](https://ministack.org/)** as the local Cognito emulator (User Pools + JWTs + optional Hosted UI / OIDC).

Cognito (via MiniStack locally, real AWS Cognito in production) becomes the system of record for:

- User credentials (password, reset, confirm signup)
- Authentication flows (login, refresh, logout / global sign-out)
- Issuing **Access / ID / Refresh** tokens (JWT)

Django remains the system of record for:

- Messaging domain data (tenants, conversations, messages, exports)
- Authorization (participant checks, inbox isolation)
- Local **user profile** linked to Cognito identity (`sub`)

---

## 2. What MiniStack Is (in this project)

| Item | Detail |
|------|--------|
| Product | Open-source AWS emulator (LocalStack-style), single gateway port **4566** |
| Cognito coverage | User Pools (`cognito-idp`), Identity Pools, OAuth2/OIDC (`/oauth2/*`, `/login`, JWKS) |
| Local client setup | `endpoint_url=http://localhost:4566` (from containers: `http://ministack:4566`), dummy keys `test`/`test` |
| Image | `ministackorg/ministack:latest` (pin a version in Compose) |
| Auth flow for local UX | Prefer `USER_PASSWORD_AUTH` (simple email/password); SRP/Hosted UI optional later |

MiniStack is **not** a replacement for Postgres/Redis in this app — only for **Cognito APIs**. Our existing `db` / `redis` / Django / Celery / React stack stays.

---

## 3. Current Auth (as-is)

```
Browser → POST /api/auth/login/ {email, password}
       ← { token: DRF Token key, user: {...} }

Browser → Authorization: Token <key>  (REST)
Browser → ws://.../ws/chat/?token=<key>  (WebSocket)

Django: authenticate() + rest_framework.authtoken.Token
User: AbstractUser with local password hash + tenant FK
Seed: creates users + Token rows
```

### Auth touchpoints today

| Layer | Files / areas |
|-------|----------------|
| Backend auth API | `apps/users/views.py` (`LoginView`) |
| DRF config | `config/settings.py` (`TokenAuthentication`, `rest_framework.authtoken`) |
| WebSocket auth | `middleware.py`, `config/asgi.py` |
| User model | `apps/users/models.py` (local password) |
| Seed | `apps/users/management/commands/seed.py` |
| Tests | `conftest.py`, `test_websocket.py`, auth-related API tests |
| Frontend login | `pages/LoginPage.tsx`, `contexts/AuthContext.tsx` |
| HTTP client | `api/client.ts` (`Authorization: Token …`) |
| WebSocket client | `utils/websocket.ts`, `hooks/useWebSocket.ts` |
| Docs | `SYSTEM_DESIGN.md`, `README.md`, `MEMORY.md` Decision #7, skills |

---

## 4. Target Architecture

```
┌──────────────────┐     InitiateAuth / Refresh      ┌─────────────────────┐
│  React Frontend  │ ───────────────────────────────► │  MiniStack Cognito  │
│  (login UI)      │ ◄── Access + Id + Refresh JWT ── │  :4566 (local)      │
└────────┬─────────┘                                  │  or AWS Cognito     │
         │                                            └─────────────────────┘
         │ Authorization: Bearer <AccessToken>
         │ WS: ?token=<AccessToken>
         ▼
┌──────────────────┐     Validate JWT (JWKS)          ┌─────────────────────┐
│  Django / DRF    │ ◄── optionally Admin* APIs ─────► │  MiniStack Cognito  │
│  + Channels      │     (seed, disable user, etc.)   │                     │
│                  │                                   └─────────────────────┘
│  Local User row  │── cognito_sub → Cognito user
│  + Tenant FK     │── messaging FKs unchanged
└──────────────────┘
```

### Responsibilities split

| Concern | Owner |
|---------|--------|
| Password / signup / reset / MFA (future) | Cognito |
| JWT issue & refresh | Cognito |
| JWT validation on API/WS | Django (JWKS from Cognito issuer / MiniStack) |
| Tenant membership | Django (see open decision §7) |
| Inbox / messages / permissions | Django (unchanged rules) |
| User directory search | Django local `User` table (synced from Cognito) |

### Recommended auth mode (Phase 1)

**Direct Cognito SDK auth from the frontend** with `USER_PASSWORD_AUTH` (keeps current email/password login UX):

1. Frontend calls Cognito `InitiateAuth` against MiniStack (or a thin Django proxy — see §7).
2. Stores `accessToken`, `idToken`, `refreshToken`.
3. Sends `Authorization: Bearer <accessToken>` to Django.
4. Django validates JWT, maps `sub` → local `User`, enforces existing permissions.

**Alternative (later):** Cognito Hosted UI / OAuth2 Authorization Code + PKCE via MiniStack `/oauth2/*`.

---

## 5. Change Scope

### 5.1 In scope (must change)

| Area | Change |
|------|--------|
| **Infra** | Add `ministack` service to `docker-compose.yml` (port 4566, healthcheck, optional state volume) |
| **User model** | Add `cognito_sub` (unique, indexed); stop relying on Django password for login (`set_unusable_password()` for Cognito-backed users) |
| **DRF auth** | Replace `TokenAuthentication` with JWT/Cognito authentication class |
| **Login API** | Deprecate or replace `POST /api/auth/login/` (Cognito becomes login; optional thin proxy endpoint) |
| **WebSocket** | Validate Cognito Access Token instead of DRF Token |
| **Seed** | Create Cognito User Pool + Client (idempotent bootstrap) + Cognito users + local User/Tenant/Conversation data |
| **Frontend auth** | Cognito client config, Bearer tokens, refresh handling, logout (`GlobalSignOut` / clear tokens) |
| **Deps** | Backend: `boto3`, `PyJWT` (+ cryptography); Frontend: `@aws-sdk/client-cognito-identity-provider` (or amazon-cognito-identity-js) |
| **Env** | `COGNITO_*` / `AWS_ENDPOINT_URL` / pool & client IDs |
| **Tests** | Fixtures issue/mock Cognito JWTs or use MiniStack in integration tests |
| **Docs** | Update README; propose updates to SYSTEM_DESIGN / MEMORY / skills (requires approval per AGENTS.md) |

### 5.2 Out of scope (unchanged)

| Area | Why |
|------|-----|
| Conversation / Message / Export models & business logic | Auth swap only |
| Participant permission rules | Same, still local User |
| Redis inbox cache & Channels groups | Same |
| Celery export pipeline | Same |
| Cross-tenant messaging product rules | Same |

### 5.3 Soft / deferred scope

| Item | Notes |
|------|-------|
| Cognito Hosted UI / PKCE | Optional Phase 2+ |
| Cognito Identity Pools (AWS creds) | Not needed for this API |
| MFA / software tokens | MiniStack supports APIs; product decision later |
| Real AWS Cognito prod cutover | Same code path; flip endpoint + pool IDs |
| Syncing Cognito → Django on attribute change | Start with JIT + seed; webhooks/Lambda later |
| Removing `rest_framework.authtoken` entirely | After migration verified |

---

## 6. Impacted Files (expected)

### New

```
backend/apps/users/authentication.py   # CognitoJWTAuthentication
backend/apps/users/cognito.py          # boto3 client helper (admin + optional proxy)
backend/scripts/bootstrap_cognito.py   # or management command: create pool/client
frontend/src/api/cognito.ts            # InitiateAuth, refresh, signOut
frontend/src/config/cognito.ts         # pool/client/endpoint from Vite env
docs/MINISTACK_COGNITO_PLAN.md         # this file
```

### Modify

```
docker-compose.yml
backend/requirements.txt
backend/config/settings.py
backend/middleware.py
backend/apps/users/models.py (+ migration)
backend/apps/users/views.py
backend/apps/users/urls.py
backend/apps/users/management/commands/seed.py
backend/tests/conftest.py (+ auth-related tests)
frontend/package.json
frontend/src/api/client.ts
frontend/src/contexts/AuthContext.tsx
frontend/src/pages/LoginPage.tsx
frontend/src/utils/websocket.ts
frontend/src/hooks/useWebSocket.ts
frontend/src/types/index.ts
README.md
```

### Governance updates (ask first)

```
SYSTEM_DESIGN.md          # §5 auth, §11 security, §12 seed
.agents/MEMORY.md         # Decision #7 override + progress
GEMINI.md / skills        # Token → Bearer JWT guidance
AGENTS.md                 # only if new approval rules needed
```

---

## 7. Open Decisions (need your input before build)

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| **D1** | Login path | **A)** Frontend → Cognito directly; **B)** Frontend → Django proxy → Cognito | **A** for simplicity; **B** if you want to hide Cognito client ID / keep one origin |
| **D2** | Tenant mapping | **A)** Custom attribute `custom:tenant_slug` on Cognito user; **B)** Cognito groups = tenants; **C)** Tenant only in Django (assign on seed / admin) | **C** for Phase 1 (least Cognito schema work); move to **A** when needed |
| **D3** | User provisioning | **A)** Just-in-time create local User on first validated JWT; **B)** Seed/admin only | **A + seed** (seed for demos; JIT for resilience) |
| **D4** | Local User PK | Keep UUID PK; store `cognito_sub` separately | **Yes** (avoid rewriting all FKs) |
| **D5** | Token on WebSocket | Keep `?token=` query param but value = Access JWT | **Yes** (minimal protocol change; document security note) |
| **D6** | MiniStack persistence | Ephemeral vs `PERSIST_STATE=1` volume | Persist pool IDs across restarts for DX |
| **D7** | Password policy | Cognito pool policy vs current `password123` | Seed passwords must meet Cognito policy (e.g. `Password123!`) — **breaking change for seed credentials** |

**Please confirm D1–D7** (or accept recommendations) before implementation starts.

---

## 8. Implementation Plan (phased)

### Phase 0 — Align & document

- [x] Analyze current auth + MiniStack Cognito capabilities
- [x] Write change scope + plan (`docs/MINISTACK_COGNITO_PLAN.md`)
- [x] Confirm open decisions D1–D7 (accepted recommendations)
- [ ] Get approval to update governance docs after decisions

### Phase 1 — Infrastructure (MiniStack in Compose)

1. [x] Add `ministack` service (`ministackorg/ministack`, port `4566`, healthcheck on `/_ministack/health`).
2. [x] Env vars for backend: `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `COGNITO_*`.
3. [x] Bootstrap management command `bootstrap_cognito`:
   - `CreateUserPool` (email as username/alias) — idempotent by pool name
   - `CreateUserPoolClient` (`USER_PASSWORD_AUTH` enabled, public client)
   - Persist IDs to `cognito_state.json` (and stdout)
4. [x] Verified by user (MiniStack health + bootstrap)

**Exit criteria:** Met — MiniStack healthy; pool + client IDs available.

### Phase 2 — Backend JWT auth + local user link

1. [x] `User.cognito_sub` field + migration (`0002_user_cognito_sub`)
2. [x] `CognitoJWTAuthentication` (JWKS; dual-auth with DRF Token during transition)
3. [x] WebSocket middleware accepts Cognito Access JWT (and legacy DRF Token)
4. [x] `GET /api/auth/me/`
5. [x] Link existing local users by email → `cognito_sub` on first JWT
6. [x] Apply migration (`0002`); model Index name aligned with migration so `makemigrations` is clean
7. [x] Migration check verified by user (`makemigrations --check`, `migrate`)


### Phase 2 — Backend JWT auth + local user link

1. Add deps: `boto3`, `PyJWT[crypto]` (versions pinned in `requirements.txt` — install only after approval).
2. Migration: `User.cognito_sub` (`CharField`, unique, nullable during transition).
3. Implement `CognitoJWTAuthentication`:
   - Parse `Authorization: Bearer …`
   - Fetch/cache JWKS from MiniStack (`/{pool_id}/.well-known/jwks.json` or Cognito-compatible path)
   - Validate `iss`, `aud`/`client_id`, `exp`, `token_use`
   - Resolve `User` by `cognito_sub` (= JWT `sub`); optional JIT create
4. Switch `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`.
5. Replace WebSocket middleware to validate same JWT.
6. Change or remove `LoginView`:
   - If D1=A: remove public password login from Django (or return 410 Gone)
   - If D1=B: proxy `InitiateAuth` and return Cognito tokens + local user profile
7. Add `GET /api/auth/me/` (recommended) so frontend can load local profile after Cognito login.

**Exit criteria:** Authenticated REST + WS work with Cognito Access Token; unauthenticated still 401.

### Phase 3 — Seed & user lifecycle

1. [x] Update `seed` command:
   - Ensure pool/client exist
   - `AdminCreateUser` + `AdminSetUserPassword` (permanent) for alice/bob/…
   - Create/update local Users with matching `cognito_sub` and tenants
   - DRF Token rows still created (dual-auth until Phase 5)
2. [x] Demo password is Cognito-compliant: `Password123!` (`SEED_PASSWORD` env override)
3. [ ] Optional admin helpers: disable Cognito user when Django `is_active=False` (deferred)
4. [x] Re-run seed and InitiateAuth smoke test (awaiting user verify)

**Exit criteria:** Seed → 6 Cognito users + local `cognito_sub`; `USER_PASSWORD_AUTH` returns JWTs.

### Phase 4 — Frontend

1. [x] Cognito client via fetch (no new npm package) + Vite proxy `/aws-cognito` → MiniStack
2. [x] `LoginPage`: `InitiateAuth` (`USER_PASSWORD_AUTH`) then `GET /api/auth/me/`
3. [x] `AuthContext`: access/id/refresh tokens; refresh on 401; logout + GlobalSignOut
4. [x] `api/client.ts`: `Bearer` for JWT, `Token` for legacy keys
5. [x] WebSocket still uses `?token=` (now the access JWT)
6. [x] `GET /api/auth/cognito-config/` for pool/client IDs
7. [ ] User verifies UI login at http://localhost:3000

### Phase 5 — Tests & cleanup

1. Test helpers: mint/validate tokens against MiniStack **or** mock JWKS + signed test JWTs.
2. Update websocket / permission / login tests.
3. Remove dead DRF Token usage from seed/tests; drop `rest_framework.authtoken` when safe.
4. Update README quick start + troubleshooting (MiniStack health, pool bootstrap).

### Phase 6 — Governance & production readiness

1. With permission: update `SYSTEM_DESIGN.md`, `MEMORY.md` (replace Decision #7), skills (`api-authorization`, `docker-deployment`).
2. Document prod switch: empty/unset `AWS_ENDPOINT_URL` → real Cognito; same pool attribute contract.
3. Security notes: short-lived access tokens; refresh storage; WS query-string token risk (prefer short TTL).

---

## 9. Suggested Token / Header Contract (API breaking change)

| Before | After |
|--------|--------|
| `Authorization: Token <drf_key>` | `Authorization: Bearer <cognito_access_token>` |
| `POST /api/auth/login/` → `{ token, user }` | Cognito tokens + `GET /api/auth/me/` → `{ user }` (shape of `user` kept stable) |
| `ws://…/ws/chat/?token=<drf_key>` | `ws://…/ws/chat/?token=<access_token>` |

Messaging REST paths (`/api/conversations/`, messages, exports, user search) stay the same; **only auth mechanism changes**.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| MiniStack JWT/`iss` quirks vs real Cognito | Abstract issuer/JWKS URL via settings; test against MiniStack; document prod issuer |
| Seed password policy mismatch | Change seed passwords; update README |
| Pool IDs lost on container recreate | Persist MiniStack state volume + bootstrap idempotency |
| Dual user stores drift | JIT sync on login; seed as source for demos; later AdminUpdateUserAttributes |
| AGENTS.md: new Docker service / packages | Ask before `docker compose` changes applied and before installs |
| Breaking existing clients/tests | Version the change in one PR; update all tests in same phase |
| Frontend talking to MiniStack CORS | Configure Cognito app client + MiniStack CORS / use Django proxy (D1=B) if browser blocked |

---

## 11. Effort Estimate (rough)

| Phase | Effort |
|-------|--------|
| Phase 1 Infra | S |
| Phase 2 Backend JWT | M |
| Phase 3 Seed | S–M |
| Phase 4 Frontend | M |
| Phase 5 Tests | M |
| Phase 6 Docs | S |
| **Total** | ~1–2 focused builds after decisions |

---

## 12. Next Step

1. Review this plan.
2. Confirm decisions **D1–D7** (or accept recommendations in §7).
3. Approve starting **Phase 1** (Compose + MiniStack + bootstrap) — will ask before any `docker compose` / package install commands per `AGENTS.md`.

---

## Appendix A — MiniStack Compose sketch (not applied yet)

```yaml
  ministack:
    image: ministackorg/ministack:latest  # pin version in real change
    ports:
      - "4566:4566"
    environment:
      - PERSIST_STATE=1
      - LOG_LEVEL=INFO
    volumes:
      - ministack_state:/tmp/ministack-state
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:4566/_ministack/health')"]
      interval: 10s
      timeout: 3s
      retries: 5
```

## Appendix B — Cognito client sketch (local)

```python
import boto3
import os

def cognito_idp():
    kwargs = {
        "region_name": os.environ.get("AWS_REGION", "us-east-1"),
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    }
    endpoint = os.environ.get("AWS_ENDPOINT_URL")  # http://ministack:4566 locally
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("cognito-idp", **kwargs)
```
