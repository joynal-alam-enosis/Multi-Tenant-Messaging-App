# Backend Rules

These rules apply to all code within the `backend/` directory.

## Python Standards
- Python 3.12+ features are allowed.
- Use type hints on **every** function signature.
- Use `from __future__ import annotations` at the top of every module.
- Follow PEP 8 — max line length 120 characters.
- Use double quotes for strings.

## Django Patterns
- All models inherit from a shared `BaseModel` with UUID `id` and `created_at`.
- All views use DRF class-based views (ViewSets or APIViews) — **never** function-based views.
- All serializers explicitly list `fields` — **never** use `fields = '__all__'`.
- All querysets in views are scoped to `request.user` — no unscoped queries.
- Use `select_related` / `prefetch_related` to avoid N+1 queries.

## Import Order
1. Standard library
2. Third-party (Django, DRF, Channels, Celery)
3. Local apps (`from apps.users.models import User`)

## Security Reminders
- **Never** return `password`, `password_hash`, or token fields in any serializer.
- **Never** use `raw()` SQL without parameterized queries.
- **Always** check participant membership before any conversation/message operation.
- **Always** invalidate Redis inbox cache after mutations.

## Database Migrations
- Run `python manage.py makemigrations` after any model change.
- Review the generated migration before applying.
- Never edit a migration that has already been applied in production.

## Testing
- Test files go in `backend/tests/`.
- Use `@pytest.mark.django_db` on all database tests.
- Use `APIClient` with `force_authenticate` for API tests.
