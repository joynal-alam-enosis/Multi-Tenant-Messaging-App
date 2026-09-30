"""
WebSocket authentication middleware.

Accepts `?token=` as either:
- Cognito Access JWT (Bearer-style value, Preferred going forward), or
- Legacy DRF Token key (during migration).
"""
from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed


@database_sync_to_async
def get_user_from_token(token_key: str):
    """Resolve a WebSocket token to a Django user (Cognito JWT or DRF Token)."""
    # Cognito JWTs are three base64 segments separated by dots
    if token_key.count(".") == 2:
        try:
            from apps.users.authentication import decode_cognito_token, resolve_local_user

            claims = decode_cognito_token(token_key)
            return resolve_local_user(claims)
        except AuthenticationFailed:
            return AnonymousUser()
        except Exception:
            return AnonymousUser()

    try:
        token = Token.objects.select_related("user").get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()


class TokenAuthMiddleware:
    """
    Authenticate WebSocket connections via token query string.
    Example: ws://host/ws/chat/?token=<access_jwt_or_drf_token>
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        token_key = query_params.get("token", [None])[0]

        if token_key:
            scope["user"] = await get_user_from_token(token_key)
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    return TokenAuthMiddleware(inner)
