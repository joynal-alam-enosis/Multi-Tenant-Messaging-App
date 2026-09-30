import os

# Set test environment variables BEFORE Django settings are loaded
os.environ.setdefault("COGNITO_VERIFY_JWT", "false")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")


def pytest_configure(config):
    """Ensure test settings are applied before Django loads."""
    # Re-read settings with test env vars
    from django.conf import settings
    if not settings.configured:
        settings.COGNITO_VERIFY_JWT = False


import pytest
from rest_framework.test import APIClient
from apps.tenants.models import Tenant
from apps.users.models import User
from apps.conversations.models import Conversation, ConversationParticipant

from django.core.cache import cache

from tests.test_helpers import auth_header_for_user, create_cognito_access_token


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def acme_tenant(db):
    return Tenant.objects.create(name="Acme Corp", slug="acme")


@pytest.fixture
def globex_tenant(db):
    return Tenant.objects.create(name="Globex Inc", slug="globex")


@pytest.fixture
def alice(db, acme_tenant):
    user = User.objects.create(
        email="alice@acme.com",
        username="alice",
        first_name="Alice",
        last_name="A",
        tenant=acme_tenant,
        cognito_sub="alice-cognito-sub-123",
    )
    user.set_unusable_password()
    user.save()
    return user


@pytest.fixture
def bob(db, acme_tenant):
    user = User.objects.create(
        email="bob@acme.com",
        username="bob",
        first_name="Bob",
        last_name="B",
        tenant=acme_tenant,
        cognito_sub="bob-cognito-sub-456",
    )
    user.set_unusable_password()
    user.save()
    return user


@pytest.fixture
def dave(db, globex_tenant):
    user = User.objects.create(
        email="dave@globex.com",
        username="dave",
        first_name="Dave",
        last_name="D",
        tenant=globex_tenant,
        cognito_sub="dave-cognito-sub-789",
    )
    user.set_unusable_password()
    user.save()
    return user


@pytest.fixture
def alice_client(alice):
    client = APIClient()
    headers = auth_header_for_user(alice)
    client.credentials(**headers)
    return client


@pytest.fixture
def bob_client(bob):
    client = APIClient()
    headers = auth_header_for_user(bob)
    client.credentials(**headers)
    return client


@pytest.fixture
def dave_client(dave):
    client = APIClient()
    headers = auth_header_for_user(dave)
    client.credentials(**headers)
    return client


@pytest.fixture
def alice_bob_conversation(db, alice, bob):
    conv = Conversation.objects.create()
    ConversationParticipant.objects.create(conversation=conv, user=alice)
    ConversationParticipant.objects.create(conversation=conv, user=bob)
    return conv


@pytest.fixture
def cognito_access_token():
    """Factory fixture to create Cognito access tokens for arbitrary users."""
    def _make_token(sub: str, email: str, **kwargs):
        return create_cognito_access_token(sub=sub, email=email, **kwargs)
    return _make_token