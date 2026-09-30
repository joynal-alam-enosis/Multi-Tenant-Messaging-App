"""
Validate Cognito Access Tokens (JWT) and map them to local User rows.

Supports MiniStack locally (AWS_ENDPOINT_URL) and real AWS Cognito in production.
Legacy DRF Token auth remains configured alongside this class during migration.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from jwt import PyJWKClient
from rest_framework import authentication, exceptions

from apps.users.cognito import get_cognito_client_id, get_cognito_user_pool_id

logger = logging.getLogger(__name__)
User = get_user_model()

# Cache JWKS clients by URI (process-local)
_jwks_clients: dict[str, PyJWKClient] = {}


def get_cognito_issuer(user_pool_id: str | None = None) -> str:
    """Cognito-compatible issuer URL (also used by MiniStack JWT `iss`)."""
    pool_id = user_pool_id or get_cognito_user_pool_id()
    region = getattr(settings, "AWS_REGION", "us-east-1")
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"


def get_jwks_uri(user_pool_id: str | None = None) -> str:
    """
    JWKS URL for signature verification.

    MiniStack serves JWKS on the gateway:
      {AWS_ENDPOINT_URL}/{pool_id}/.well-known/jwks.json
    Real AWS:
      https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json
    """
    pool_id = user_pool_id or get_cognito_user_pool_id()
    endpoint = getattr(settings, "AWS_ENDPOINT_URL", None)
    if endpoint:
        return f"{endpoint.rstrip('/')}/{pool_id}/.well-known/jwks.json"
    region = getattr(settings, "AWS_REGION", "us-east-1")
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    if jwks_uri not in _jwks_clients:
        _jwks_clients[jwks_uri] = PyJWKClient(jwks_uri, cache_keys=True)
    return _jwks_clients[jwks_uri]


def decode_cognito_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a Cognito access (or id) token.

    When COGNITO_VERIFY_JWT is False (useful for some MiniStack stub tokens),
    claims are decoded without signature verification but exp/iss/client checks
    still apply when present.
    """
    pool_id = get_cognito_user_pool_id()
    client_id = get_cognito_client_id()
    if not pool_id:
        raise exceptions.AuthenticationFailed("Cognito user pool is not configured")

    issuer = get_cognito_issuer(pool_id)
    # Read at runtime to support test env vars set after settings import
    _verify_jwt_env = os.environ.get("COGNITO_VERIFY_JWT", "").strip().lower()
    if _verify_jwt_env in ("1", "true", "yes"):
        verify_signature = True
    elif _verify_jwt_env in ("0", "false", "no"):
        verify_signature = False
    else:
        verify_signature = getattr(settings, "AWS_ENDPOINT_URL", None) is None

    options = {
        "verify_signature": verify_signature,
        "verify_exp": True,
        "verify_iss": True,
        "require": ["exp", "iss", "sub"],
    }

    try:
        if verify_signature:
            jwks_client = _get_jwks_client(get_jwks_uri(pool_id))
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                issuer=issuer,
                options=options,
                leeway=30,
            )
        else:
            claims = jwt.decode(
                token,
                options={**options, "verify_signature": False},
                issuer=issuer,
                leeway=30,
            )
    except jwt.PyJWTError as exc:
        logger.info("Cognito JWT validation failed: %s", exc)
        raise exceptions.AuthenticationFailed("Invalid or expired Cognito token") from exc

    token_use = claims.get("token_use")
    if token_use and token_use not in ("access", "id"):
        raise exceptions.AuthenticationFailed("Unsupported Cognito token_use")

    # Access tokens use client_id; ID tokens use aud
    token_client = claims.get("client_id") or claims.get("aud")
    if client_id and token_client and token_client != client_id:
        raise exceptions.AuthenticationFailed("Token client does not match configured app client")

    return claims


def resolve_local_user(claims: dict[str, Any]) -> Any:
    """
    Map Cognito claims to a local User.

    1) Match cognito_sub
    2) Else match email and link cognito_sub (seeded users)
    Full JIT create (new tenant assignment) is deferred — tenant is Django-owned (D2).
    """
    sub = claims.get("sub")
    if not sub:
        raise exceptions.AuthenticationFailed("Token missing sub")

    user = User.objects.select_related("tenant").filter(cognito_sub=sub).first()
    if user:
        if not user.is_active:
            raise exceptions.AuthenticationFailed("User is inactive")
        return user

    email = claims.get("email") or claims.get("username")
    if email:
        user = User.objects.select_related("tenant").filter(email__iexact=email).first()
        if user:
            if not user.is_active:
                raise exceptions.AuthenticationFailed("User is inactive")
            user.cognito_sub = sub
            user.save(update_fields=["cognito_sub"])
            return user

    raise exceptions.AuthenticationFailed(
        "No local user linked to this Cognito identity. Seed or create the Django user first."
    )


class CognitoJWTAuthentication(authentication.BaseAuthentication):
    """
    DRF authentication: Authorization: Bearer <cognito_access_token>
    """

    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8")
        if not header:
            return None

        parts = header.split()
        if len(parts) == 0:
            return None
        if parts[0] != self.keyword:
            # Not a Bearer token — allow TokenAuthentication to handle "Token …"
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Invalid Bearer authorization header")

        claims = decode_cognito_token(parts[1])
        user = resolve_local_user(claims)
        return (user, claims)

    def authenticate_header(self, request) -> str:
        return self.keyword
