# Frontend Production Build with Nginx — Implementation Plan

> **Current**: Vite dev server (`npm run dev`) on port 3000 with proxy to backend/ministack  
> **Target**: Nginx serving static build (`npm run build` → `dist/`) with reverse proxy to backend

---

## 1. Architecture Comparison

| Aspect | Dev (Current) | Production (Target) |
|--------|---------------|---------------------|
| **Server** | Vite dev server (Node) | Nginx (static files) + Backend API |
| **Build** | On-demand HMR | Pre-built `dist/` (ESBuild/Rollup) |
| **Proxy** | Vite proxy middleware | Nginx `proxy_pass` |
| **Port** | 3000 (Vite) | 80/443 (Nginx) |
| **Cognito** | Vite proxy `/aws-cognito` → ministack | Nginx proxy `/aws-cognito` → ministack |
| **API** | Vite proxy `/api` → backend | Nginx proxy `/api` → backend |
| **WS** | Vite proxy `/ws` → backend | Nginx proxy `/ws` → backend |

---

## 2. Changes Required

### 2.1 Frontend Dockerfile (Multi-stage)

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2.2 Nginx Configuration (`frontend/nginx.conf`)

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback - serve index.html for client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Static assets - long cache
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy to backend
    location /ws/ {
        proxy_pass http://backend:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }

    # Cognito proxy to MiniStack
    location /aws-cognito/ {
        proxy_pass http://ministack:4566/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
}
```

### 2.3 docker-compose.yml Updates

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "80:80"  # or 3000:80 for local dev convenience
  depends_on:
    - backend
    - ministack
  # No volumes needed (static files baked in image)
```

### 2.4 Vite Config Updates

- Remove `server.proxy` (not used in production)
- Ensure `base: '/'` for correct asset paths
- Environment variables at build time: `VITE_API_URL`, `VITE_WS_URL`, `VITE_AWS_ENDPOINT_URL`

---

## 3. Environment Variables

| Variable | Dev | Production |
|----------|-----|------------|
| `VITE_API_URL` | `/api` (proxied) | `/api` (proxied via nginx) |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | `ws://yourdomain.com/ws` |
| `VITE_AWS_ENDPOINT_URL` | `/aws-cognito` (proxied) | `/aws-cognito` (proxied via nginx) |

---

## 4. Implementation Steps

| Step | Task | Files |
|------|------|-------|
| 1 | Create multi-stage `frontend/Dockerfile` | `frontend/Dockerfile` |
| 2 | Create `frontend/nginx.conf` | `frontend/nginx.conf` |
| 3 | Update `vite.config.ts` for production | `vite.config.ts` |
| 4 | Update `docker-compose.yml` frontend service | `docker-compose.yml` |
| 5 | Test build locally | `docker compose build frontend` |
| 6 | Test full stack | `docker compose up` |

---

## 5. Key Considerations

| Concern | Solution |
|---------|----------|
| **Client-side routing** | Nginx `try_files $uri $uri/ /index.html` |
| **Asset caching** | `expires 1y` for `/assets/` with content hashes |
| **API/WebSocket proxy** | Nginx `proxy_pass` to `backend:8000` |
| **Cognito proxy** | Nginx proxies `/aws-cognito/` to `ministack:4566` |
| **CORS** | Handled by nginx proxy (no CORS needed for same-origin) |
| **Env vars** | Build-time for Vite, runtime for nginx (via envsubst if needed) |

---

## 6. Dev vs Prod Workflow

```bash
# Development (current)
docker compose up --build  # Uses vite dev server

# Production build test
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build

# Production deploy
docker compose -f docker-compose.prod.yml up -d
```

---

## 7. Optional Enhancements

- **HTTPS**: Add certbot/Let's Encrypt or use reverse proxy (Traefik/Cloudflare)
- **Compression**: `gzip on` in nginx for text assets
- **CSP Headers**: Content Security Policy for XSS protection
- **Health Check**: `/health` endpoint in nginx
- **Multi-arch**: Build for `linux/amd64,linux/arm64` for cloud deploy

---

## 8. Migration Checklist

- [ ] Multi-stage Dockerfile created
- [ ] nginx.conf created with all proxy rules
- [ ] vite.config.ts updated (remove dev proxy, set base)
- [ ] docker-compose.yml updated for frontend
- [ ] `.dockerignore` includes `node_modules`, `dist`, `.git`
- [ ] Build passes: `docker compose build frontend`
- [ ] Full stack runs: `docker compose up`
- [ ] Login → Cognito → API → WebSocket all work
- [ ] Static assets load with correct cache headers
- [ ] SPA routing works (refresh on `/conversations/xxx`)