"""
Cognito (MiniStack / AWS) client helpers and local state persistence.

Phase 1: bootstrap pool + client. Later phases use the same client for admin
user ops and JWT settings resolution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

COGNITO_STATE_FILENAME = "cognito_state.json"


def cognito_state_path() -> Path:
    """Path to the JSON file that stores pool/client IDs after bootstrap."""
    return Path(settings.BASE_DIR) / COGNITO_STATE_FILENAME


def load_cognito_state() -> dict[str, Any]:
    """Load bootstrap state from disk. Returns {} if missing or invalid."""
    path = cognito_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cognito_state(data: dict[str, Any]) -> Path:
    """Persist pool/client IDs for Django settings and operators."""
    path = cognito_state_path()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def get_cognito_user_pool_id() -> str:
    """Resolve user pool ID from env, then cognito_state.json."""
    env_value = os.environ.get("COGNITO_USER_POOL_ID", "").strip()
    if env_value:
        return env_value
    return str(load_cognito_state().get("user_pool_id") or "")


def get_cognito_client_id() -> str:
    """Resolve app client ID from env, then cognito_state.json."""
    env_value = os.environ.get("COGNITO_CLIENT_ID", "").strip()
    if env_value:
        return env_value
    return str(load_cognito_state().get("client_id") or "")


def get_cognito_idp_client() -> BaseClient:
    """
    Build a cognito-idp boto3 client.

    When AWS_ENDPOINT_URL is set (e.g. http://ministack:4566), traffic goes to
    MiniStack. When unset, the real AWS Cognito endpoint is used.
    """
    kwargs: dict[str, Any] = {
        "service_name": "cognito-idp",
        "region_name": getattr(settings, "AWS_REGION", os.environ.get("AWS_REGION", "us-east-1")),
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    }
    endpoint = getattr(settings, "AWS_ENDPOINT_URL", None) or os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(**kwargs)


def _list_all_user_pools(client: BaseClient) -> list[dict[str, Any]]:
    """List user pools (handles paginated and simple MiniStack responses)."""
    pools: list[dict[str, Any]] = []
    try:
        paginator = client.get_paginator("list_user_pools")
        for page in paginator.paginate(MaxResults=60):
            pools.extend(page.get("UserPools", []))
    except (BotoCoreError, ClientError, Exception):
        # Some emulators reject pagination tokens; fall back to a single call.
        response = client.list_user_pools(MaxResults=60)
        pools.extend(response.get("UserPools", []))
    return pools


def find_user_pool_by_name(client: BaseClient, pool_name: str) -> str | None:
    """Return the first User Pool ID whose name matches, or None."""
    for pool in _list_all_user_pools(client):
        if pool.get("Name") == pool_name:
            return pool.get("Id")
    return None


def _list_pool_clients(client: BaseClient, user_pool_id: str) -> list[dict[str, Any]]:
    """List app clients for a pool."""
    clients: list[dict[str, Any]] = []
    try:
        paginator = client.get_paginator("list_user_pool_clients")
        for page in paginator.paginate(UserPoolId=user_pool_id, MaxResults=60):
            clients.extend(page.get("UserPoolClients", []))
    except (BotoCoreError, ClientError, Exception):
        response = client.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
        clients.extend(response.get("UserPoolClients", []))
    return clients


def find_user_pool_client_by_name(
    client: BaseClient,
    user_pool_id: str,
    client_name: str,
) -> str | None:
    """Return the first app client ID whose name matches, or None."""
    for app_client in _list_pool_clients(client, user_pool_id):
        if app_client.get("ClientName") == client_name:
            return app_client.get("ClientId")
    return None


def ensure_user_pool_and_client(
    *,
    pool_name: str | None = None,
    client_name: str | None = None,
) -> dict[str, Any]:
    """
    Idempotently ensure a Cognito User Pool and public app client exist.

    Returns dict with user_pool_id, client_id, pool_name, client_name, region, endpoint.
    """
    pool_name = pool_name or getattr(settings, "COGNITO_POOL_NAME", "messaging-app")
    client_name = client_name or getattr(settings, "COGNITO_CLIENT_NAME", "messaging-web")
    client = get_cognito_idp_client()

    user_pool_id = find_user_pool_by_name(client, pool_name)
    created_pool = False
    if not user_pool_id:
        # Keep CreateUserPool args minimal for MiniStack compatibility; password
        # policy can be tightened later via UpdateUserPool if needed.
        try:
            response = client.create_user_pool(
                PoolName=pool_name,
                AutoVerifiedAttributes=["email"],
                UsernameAttributes=["email"],
                Policies={
                    "PasswordPolicy": {
                        "MinimumLength": 8,
                        "RequireUppercase": True,
                        "RequireLowercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": True,
                    }
                },
            )
        except ClientError:
            response = client.create_user_pool(PoolName=pool_name)
        user_pool_id = response["UserPool"]["Id"]
        created_pool = True

    app_client_id = find_user_pool_client_by_name(client, user_pool_id, client_name)
    created_client = False
    if not app_client_id:
        try:
            response = client.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                    "ALLOW_USER_SRP_AUTH",
                ],
                PreventUserExistenceErrors="ENABLED",
            )
        except ClientError:
            response = client.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                ],
            )
        app_client_id = response["UserPoolClient"]["ClientId"]
        created_client = True

    region = getattr(settings, "AWS_REGION", "us-east-1")
    endpoint = getattr(settings, "AWS_ENDPOINT_URL", "") or ""
    state = {
        "user_pool_id": user_pool_id,
        "client_id": app_client_id,
        "pool_name": pool_name,
        "client_name": client_name,
        "region": region,
        "endpoint": endpoint,
        "created_pool": created_pool,
        "created_client": created_client,
    }
    save_cognito_state(
        {
            "user_pool_id": user_pool_id,
            "client_id": app_client_id,
            "pool_name": pool_name,
            "client_name": client_name,
            "region": region,
            "endpoint": endpoint,
        }
    )
    return state


SEED_PASSWORD_DEFAULT = "Password123!"


def _attribute_map(user_payload: dict[str, Any]) -> dict[str, str]:
    """Flatten Cognito UserAttributes / Attributes list to a name→value map."""
    attrs = user_payload.get("UserAttributes") or user_payload.get("Attributes") or []
    return {item.get("Name", ""): item.get("Value", "") for item in attrs if item.get("Name")}


def get_cognito_user_sub(username: str, *, user_pool_id: str | None = None) -> str | None:
    """Return the Cognito `sub` for a username (email), or None if the user does not exist."""
    pool_id = user_pool_id or get_cognito_user_pool_id()
    if not pool_id:
        return None
    client = get_cognito_idp_client()
    try:
        response = client.admin_get_user(UserPoolId=pool_id, Username=username)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("UserNotFoundException", "ResourceNotFoundException"):
            return None
        raise
    return _attribute_map(response).get("sub") or response.get("Username")


def ensure_cognito_user(
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    user_pool_id: str | None = None,
) -> str:
    """
    Idempotently create a confirmed Cognito user with a permanent password.

    Returns the Cognito `sub` claim.
    """
    pool_id = user_pool_id or get_cognito_user_pool_id()
    if not pool_id:
        raise RuntimeError("Cognito user pool is not configured; run bootstrap_cognito first")

    client = get_cognito_idp_client()
    attributes = [
        {"Name": "email", "Value": email},
        {"Name": "email_verified", "Value": "true"},
    ]
    if first_name:
        attributes.append({"Name": "given_name", "Value": first_name})
    if last_name:
        attributes.append({"Name": "family_name", "Value": last_name})

    try:
        response = client.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=attributes,
            MessageAction="SUPPRESS",
        )
        created_payload = response.get("User") or {}
        sub = _attribute_map(created_payload).get("sub")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code != "UsernameExistsException":
            raise
        sub = None

    try:
        client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=email,
            Password=password,
            Permanent=True,
        )
    except ClientError:
        # MiniStack may already have a permanent password; continue to look up sub.
        pass

    try:
        client.admin_confirm_sign_up(UserPoolId=pool_id, Username=email)
    except ClientError:
        pass

    sub = sub or get_cognito_user_sub(email, user_pool_id=pool_id)
    if not sub:
        raise RuntimeError(f"Could not resolve Cognito sub for {email}")
    return sub
