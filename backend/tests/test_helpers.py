"""
Test helpers for Cognito JWT authentication.

Provides utilities to create valid Cognito-style JWT tokens for testing
without requiring a running MiniStack/Cognito instance.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings


# Generate a test RSA key pair once at module load
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_public_key = _test_private_key.public_key()

_test_private_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

_test_public_pem = _test_public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")

# Get JWK from the public key
_test_jwk_dict = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_test_public_key))
_test_jwk = {
    "kty": "RSA",
    "kid": "test-key-1",
    "use": "sig",
    "alg": "RS256",
    "n": _test_jwk_dict["n"],
    "e": _test_jwk_dict["e"],
}


def get_test_jwk() -> dict[str, Any]:
    """Return a test JWK (RSA key) for signing test JWTs."""
    return _test_jwk


def get_test_jwks() -> dict[str, list[dict[str, Any]]]:
    """Return a JWKS with the test key."""
    return {"keys": [_test_jwk]}


def create_cognito_access_token(
    *,
    sub: str | None = None,
    email: str | None = None,
    username: str | None = None,
    client_id: str | None = None,
    token_use: str = "access",
    exp_delta: int = 3600,
    **extra_claims: Any,
) -> str:
    """
    Create a signed Cognito Access Token (JWT) for testing.
    
    Args:
        sub: Cognito user sub (defaults to random UUID)
        email: User email
        username: Username (typically email for Cognito)
        client_id: Cognito app client ID (defaults to settings.COGNITO_CLIENT_ID)
        token_use: "access" or "id"
        exp_delta: Token expiration in seconds from now
        **extra_claims: Additional claims to include
    
    Returns:
        Signed JWT string
    """
    sub = sub or str(uuid.uuid4())
    now = int(time.time())
    
    # Use the same resolution logic as the authentication code
    from apps.users.cognito import get_cognito_user_pool_id, get_cognito_client_id
    pool_id = get_cognito_user_pool_id() or "us-east-1_testpool"
    region = getattr(settings, "AWS_REGION", "us-east-1")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
    audience = client_id or get_cognito_client_id() or "test-client-id"
    
    claims = {
        "sub": sub,
        "iss": issuer,
        "client_id": audience,
        "origin_jti": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "token_use": token_use,
        "scope": "openid email profile",
        "auth_time": now,
        "exp": now + exp_delta,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "username": username or email or sub,
    }
    
    if email:
        claims["email"] = email
        claims["email_verified"] = True
    
    claims.update(extra_claims)
    
    # Sign with test private key
    return jwt.encode(
        claims,
        _test_private_pem,
        algorithm="RS256",
        headers={"kid": "test-key-1"}
    )


def create_cognito_id_token(
    *,
    sub: str | None = None,
    email: str | None = None,
    aud: str | None = None,
    exp_delta: int = 3600,
    **extra_claims: Any,
) -> str:
    """Create a signed Cognito ID Token (JWT) for testing."""
    return create_cognito_access_token(
        sub=sub,
        email=email,
        client_id=aud,
        token_use="id",
        exp_delta=exp_delta,
        **extra_claims,
    )


def auth_header_for_user(user, token_type: str = "Bearer") -> dict[str, str]:
    """
    Generate Authorization header for a test user.
    
    Creates a Cognito JWT with the user's cognito_sub and email.
    """
    from apps.users.models import User
    
    if isinstance(user, User):
        sub = user.cognito_sub or str(uuid.uuid4())
        email = user.email
    else:
        sub = str(user)
        email = f"{user}@test.com"
    
    token = create_cognito_access_token(sub=sub, email=email)
    return {"HTTP_AUTHORIZATION": f"{token_type} {token}"}