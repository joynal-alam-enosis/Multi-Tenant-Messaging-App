# Agents Configuration

This file configures additional agent behavior for the workspace.

## ⛔ Approval Required — NEVER Skip These

The following actions **require explicit user permission** before execution. Do NOT proceed without asking and receiving a clear "yes" or approval:

1. **Git operations**: Do NOT `git commit`, `git push`, `git merge`, or any git write operation until the user explicitly says to do so.
2. **Building / applying changes**: Do NOT run build commands (`docker compose build`, `npm run build`, `python manage.py migrate`, etc.) without asking first.
3. **Installing packages**: Do NOT run `pip install`, `npm install`, `apt-get install`, or any package installation command without asking first. **(Note: All installations must happen inside Docker, never on the host).**
4. **Running scripts**: Do NOT execute scripts, management commands, or any `python`, `node`, `bash` commands without asking first. **Always run these via `docker compose exec`**.
5. **Integrating tools / services**: Do NOT add new dependencies, configure new services, or integrate third-party tools without asking first.

**How to handle this**: When you reach a step that requires any of the above, stop and ask the user for permission. Present what you want to run and why, then wait for approval.

## 🛡️ Safety Restrictions — NEVER Violate

### File Operations
- Do NOT delete or overwrite existing project files without asking. Creating new files is fine.
- Do NOT modify `SYSTEM_DESIGN.md`, `GEMINI.md`, `AGENTS.md`, or `.agents/MEMORY.md` without explicit permission — these are governance files.
- Do NOT remove or modify existing tests unless the user asks to change them.

### Database & Data
- Do NOT run destructive database commands (`DROP`, `TRUNCATE`, `flush`, `reset_db`) without asking.
- Do NOT modify existing migrations that have already been applied — always create new ones.
- Do NOT change the seed data structure without asking — other developers may depend on it.

### Secrets & Environment
- **Never** hardcode passwords, API keys, tokens, or secret keys in source code.
- **Never** log, print, or expose sensitive environment variables in responses.
- Always use environment variables (via `os.environ` or `.env` files) for credentials.
- Do NOT create or modify `.env` files without showing the user the contents first.

### Configuration Changes
- Do NOT change `settings.py` defaults for `AUTH_USER_MODEL`, `DATABASES`, `CHANNEL_LAYERS`, or `CACHES` without explaining why.
- Do NOT change `docker-compose.yml` port mappings, volume mounts, or service dependencies without asking.
- Do NOT add new Django apps to `INSTALLED_APPS` without asking.
- Do NOT add new npm packages to `package.json` without asking.

### Architecture Guardrails
- Do NOT deviate from the architecture in `SYSTEM_DESIGN.md` without discussing with the user first.
- Do NOT introduce new technologies, frameworks, or libraries not listed in the system design.
- Do NOT change the API contract (endpoint paths, request/response shapes) without asking.
- Do NOT change the WebSocket protocol (event types, payload structure) without asking.
- PostgreSQL is the **only** source of truth — never treat Redis as durable storage.

### Code Quality Gates
- Do NOT remove existing docstrings, comments, or type hints unless they are incorrect.
- Do NOT disable linting rules, type checks, or security validations.
- Do NOT use `# type: ignore`, `noqa`, `eslint-disable`, or similar suppression comments without explaining why.
- Do NOT introduce `any` types in TypeScript without documenting the reason.

## Memory

The project memory is stored at `.agents/MEMORY.md`. It tracks:
- Architectural decisions with rationale
- Development progress (checkbox tracker)
- Known gotchas and workarounds

**Always check `.agents/MEMORY.md` before starting work** to understand the current project state and avoid repeating completed steps.

**Update `.agents/MEMORY.md`** after completing any phase or making a significant architectural decision.

## Key References

| File | Purpose |
|------|---------|
| `SYSTEM_DESIGN.md` | Authoritative architecture and data model |
| `GEMINI.md` | Root-level always-on project rules |
| `backend/GEMINI.md` | Backend-specific coding rules |
| `frontend/GEMINI.md` | Frontend-specific coding rules |
| `.agents/MEMORY.md` | Progress tracker and decisions log |
| `.agents/skills/` | On-demand skill guides (6 skills) |

## Development Workflow

1. **Before any task**: Read `MEMORY.md` to see what's done and what's next.
2. **During development**: Follow the rules in `GEMINI.md` and the relevant subdirectory `GEMINI.md`.
3. **When implementing**: Activate the relevant skill for patterns and code templates.
4. **After completing a phase**: Update the progress checkboxes in `MEMORY.md`.
5. **When making a design decision**: Add it to the decisions table in `MEMORY.md`.
