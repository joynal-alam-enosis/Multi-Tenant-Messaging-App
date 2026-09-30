---
name: docker-deployment
description: >-
  Use this skill when working with Docker, Docker Compose, Dockerfiles, container
  configuration, environment variables, or deployment setup for the messaging application.
---

# Docker & Deployment Skill

## Docker Compose Architecture

6 services in a single `docker-compose.yml`:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `db` | postgres:16 | 5432 | PostgreSQL database |
| `redis` | redis:7-alpine | 6379 | Cache + Channel Layer |
| `ministack` | ministackorg/ministack | 4566 | AWS Cognito emulator (User Pools, JWT, JWKS) |
| `backend` | Custom (Python 3.12) | 8000 | Django ASGI (Daphne) |
| `celery-worker` | Same as backend | — | Async task processing |
| `frontend` | Custom (Node 20) | 3000 | React dev server / Nginx |

## docker-compose.yml Template

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: messaging
      POSTGRES_USER: messaging_user
      POSTGRES_PASSWORD: messaging_pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U messaging_user -d messaging"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  ministack:
    image: ministackorg/ministack:latest
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
      timeout: 5s
      retries: 5
      start_period: 10s

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      sh -c "python manage.py bootstrap_cognito &&
             python manage.py migrate &&
             python manage.py seed || true &&
             daphne -b 0.0.0.0 -p 8000 config.asgi:application"
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://messaging_user:messaging_pass@db:5432/messaging
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - AWS_ENDPOINT_URL=http://ministack:4566
      - AWS_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=test
      - AWS_SECRET_ACCESS_KEY=test
      - COGNITO_POOL_NAME=messaging-app
      - COGNITO_CLIENT_NAME=messaging-web
      - COGNITO_VERIFY_JWT=false
      - DJANGO_SECRET_KEY=dev-secret-key-change-in-production
      - DEBUG=True
      - ALLOWED_HOSTS=*
      - CORS_ALLOWED_ORIGINS=http://localhost:3000
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      ministack:
        condition: service_healthy

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A config worker -l info
    environment:
      - DATABASE_URL=postgres://messaging_user:messaging_pass@db:5432/messaging
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - AWS_ENDPOINT_URL=http://ministack:4566
      - AWS_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=test
      - AWS_SECRET_ACCESS_KEY=test
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      ministack:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000/api
      - VITE_WS_URL=ws://localhost:8000/ws
      - VITE_AWS_ENDPOINT_URL=/aws-cognito
      - VITE_AWS_REGION=us-east-1
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
      - ministack

volumes:
  postgres_data:
  ministack_state:
  backend_exports:
```

## Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Default command (overridden by docker-compose)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
```

## Frontend Dockerfile

```dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

## Environment Variables Reference

| Variable | Service | Description |
|----------|---------|-------------|
| `DATABASE_URL` | backend, celery | PostgreSQL connection string |
| `REDIS_URL` | backend, celery | Redis for caching (DB 0) |
| `CELERY_BROKER_URL` | backend, celery | Redis for Celery (DB 1) |
| `AWS_ENDPOINT_URL` | backend, celery, frontend | MiniStack endpoint (http://ministack:4566) |
| `AWS_REGION` | backend, celery, frontend | AWS region (us-east-1) |
| `AWS_ACCESS_KEY_ID` | backend, celery | Dummy key for MiniStack |
| `AWS_SECRET_ACCESS_KEY` | backend, celery | Dummy secret for MiniStack |
| `COGNITO_POOL_NAME` | backend | Cognito User Pool name |
| `COGNITO_CLIENT_NAME` | backend | Cognito App Client name |
| `COGNITO_VERIFY_JWT` | backend | Skip JWT signature verify for MiniStack (false) |
| `DJANGO_SECRET_KEY` | backend, celery | Django secret key |
| `DEBUG` | backend | Django debug mode |
| `ALLOWED_HOSTS` | backend | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | backend | Frontend origin for CORS |
| `VITE_API_URL` | frontend | Backend API base URL |
| `VITE_WS_URL` | frontend | WebSocket base URL |
| `VITE_AWS_ENDPOINT_URL` | frontend | Vite proxy path for Cognito (/aws-cognito) |
| `VITE_AWS_REGION` | frontend | AWS region |

## Commands Reference

```bash
# Start everything
docker compose up --build

# Start in detached mode
docker compose up -d --build

# View logs
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose logs -f ministack

# Run migrations manually
docker compose exec backend python manage.py migrate

# Seed data manually (includes Cognito bootstrap)
docker compose exec backend python manage.py seed

# Run backend tests
docker compose exec backend pytest -v

# Django shell
docker compose exec backend python manage.py shell

# Stop everything
docker compose down

# Stop and remove volumes (full reset)
docker compose down -v
```

## Health Check Strategy
- PostgreSQL: `pg_isready` check before backend starts
- Redis: `redis-cli ping` check before backend starts
- MiniStack: HTTP health check on `/_ministack/health` before backend starts
- Backend depends on db, redis, and ministack being healthy
- Celery worker depends on db, redis, and ministack being healthy
- Frontend depends on backend and ministack being up

## Volume Strategy
- `postgres_data`: Named volume for PostgreSQL persistence across restarts
- `ministack_state`: Named volume for MiniStack persistence (User Pool IDs survive restarts)
- `backend_exports`: Shared volume between backend and celery-worker for export files
- Redis: No volume needed (ephemeral cache + channel layer)

## Production Notes
- Set `AWS_ENDPOINT_URL` to empty/unset to use real AWS Cognito
- Use real Cognito User Pool ID and Client ID (from `bootstrap_cognito` output or AWS Console)
- Set `COGNITO_VERIFY_JWT=true` (default when `AWS_ENDPOINT_URL` is not set)
- Use strong `DJANGO_SECRET_KEY`
- Set `DEBUG=False`
- Configure `CORS_ALLOWED_ORIGINS` for production domain
- Use HTTPS/WSS in production (reverse proxy with TLS termination)