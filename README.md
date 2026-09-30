# Cross-Tenant Messaging App

A real-time cross-tenant messaging application built with Django, React, PostgreSQL, Redis, Celery, and **Amazon Cognito (via MiniStack locally)**.

## Architecture

Please refer to `SYSTEM_DESIGN.md` for the comprehensive system architecture, database schema, and component flow.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

1. Clone the repository and navigate to the root directory.
2. Build and start the containers:
   ```bash
   docker compose up --build
   ```
3. The backend API runs on `http://localhost:8000`.
4. The React frontend runs on `http://localhost:3000`.

*Note: The backend automatically runs database migrations, bootstraps Cognito, and seeds test data on startup.*

## Authentication (Cognito / MiniStack)

This app uses **Amazon Cognito** for authentication. Locally, **MiniStack** (a local AWS emulator) runs on port 4566 to provide Cognito User Pools, JWT issuance, and JWKS.

- **Frontend**: Calls Cognito `InitiateAuth` (USER_PASSWORD_AUTH) directly → receives Access/ID/Refresh JWTs → calls `GET /api/auth/me/` to fetch local user profile.
- **Backend**: Validates `Authorization: Bearer <access_token>` via JWKS from Cognito/MiniStack. Maps `sub` claim to local `User.cognito_sub` (JIT sync on first login).
- **WebSocket**: Connects with `?token=<access_token>`. Accepts Cognito Access JWT (or legacy DRF Token during migration).

### Legacy Login (Deprecated)
`POST /api/auth/login/` returns a DRF Token for backward compatibility during migration.

## Test Users & Seed Data

The database is pre-seeded with 2 tenants and 6 users. Demo password is `Password123!` (Cognito policy: upper, lower, number, symbol). Override with `SEED_PASSWORD`.

Cognito (MiniStack) is bootstrapped on backend startup. Pool/client IDs are written to `backend/cognito_state.json`.

**Acme Corp:**
- alice@acme.com
- bob@acme.com
- charlie@acme.com

**Globex Inc:**
- dave@globex.com
- eve@globex.com
- frank@globex.com

All users exist in both Cognito (MiniStack) and Django, linked by `cognito_sub`.

## API Endpoints

- `GET /api/auth/cognito-config/` - Public Cognito pool/client IDs for the SPA
- `GET /api/auth/me/` - Current user profile (Bearer JWT or legacy Token)
- `GET /api/users/search/?q=` - Search users across tenants
- `GET /api/conversations/?filter={all|unread|starred}` - Inbox list (cached)
- `POST /api/conversations/` - Create a new conversation (idempotent)
- `GET /api/conversations/{id}/messages/` - List messages
- `POST /api/conversations/{id}/messages/` - Send a message
- `POST /api/conversations/{id}/messages/read/` - Mark messages as read
- `POST /api/conversations/{id}/export/` - Request a JSON export
- `GET /api/exports/{id}/download/` - Download completed export

## WebSocket Endpoints

- `ws://localhost:8000/ws/chat/?token={access_token}` - Main WebSocket connection for real-time events.

## Running Tests

```bash
# Backend tests
docker compose exec backend pytest -v

# Frontend tests (when available)
docker compose exec frontend npm test
```

## Troubleshooting

- **Database Errors**: If you encounter errors, you can reset the database by deleting the `postgres_data` volume: `docker compose down -v`.
- **Celery Export Not Working**: Ensure the `celery_worker` container is running and healthy. Exports are saved to the `backend/exports/` directory, which is shared via a volume.
- **MiniStack Not Healthy**: Check logs with `docker compose logs ministack`. Ensure port 4566 is not in use.
- **Cognito JWT Validation Fails**: For local development, `COGNITO_VERIFY_JWT=false` is set (MiniStack stub tokens). In production, use real AWS Cognito with verification enabled.
- **Test Database Migrations**: If schema changes, run `docker compose exec backend python manage.py migrate` before tests.

## Production Deployment

1. Set `AWS_ENDPOINT_URL` to empty/unset to use real AWS Cognito.
2. Create a real Cognito User Pool and App Client in AWS Console.
3. Set `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_VERIFY_JWT=true`.
4. Use strong `DJANGO_SECRET_KEY`, `DEBUG=False`.
5. Configure `CORS_ALLOWED_ORIGINS` for your production domain.
6. Use HTTPS/WSS (reverse proxy with TLS termination).

## Project Structure

```
.
├── backend/                 # Django project
│   ├── config/              # Settings, URLs, ASGI, Celery
│   ├── apps/                # Django apps (tenants, users, conversations, messages, exports)
│   ├── tests/               # Backend tests (pytest)
│   └── requirements.txt
├── frontend/                # React + TypeScript + Vite
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml       # 6 services: db, redis, ministack, backend, celery-worker, frontend
├── SYSTEM_DESIGN.md         # Comprehensive architecture documentation
├── .agents/MEMORY.md        # Project memory and decisions log
└── README.md
```

## Key Technologies

- **Backend**: Django 5, DRF, Django Channels, Daphne, Celery, PostgreSQL 16, Redis 7
- **Auth**: Amazon Cognito (MiniStack locally), JWT (RS256), JWKS validation
- **Frontend**: React 18, TypeScript, Vite, TanStack Query, Tailwind CSS
- **Real-time**: WebSocket via Django Channels + Redis Channel Layer
- **Deployment**: Docker Compose, MiniStack (local Cognito emulator)