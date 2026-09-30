import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application
from apps.users.models import User

from tests.test_helpers import create_cognito_access_token


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_valid_cognito_token_accepted(alice):
    """Test that a valid Cognito Access JWT is accepted for WebSocket connection."""
    token = create_cognito_access_token(
        sub=alice.cognito_sub,
        email=alice.email,
    )
    
    communicator = WebsocketCommunicator(
        application, f"/ws/chat/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_no_token_rejected():
    """Test that connection without token is rejected."""
    communicator = WebsocketCommunicator(application, "/ws/chat/")
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_invalid_token_rejected():
    """Test that connection with invalid token is rejected."""
    communicator = WebsocketCommunicator(
        application, "/ws/chat/?token=invalid.token.value"
    )
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_expired_token_rejected(alice):
    """Test that expired Cognito token is rejected."""
    # Create an expired token (exp 1 second ago)
    token = create_cognito_access_token(
        sub=alice.cognito_sub,
        email=alice.email,
        exp_delta=-1,
    )
    
    communicator = WebsocketCommunicator(
        application, f"/ws/chat/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_audience_token_rejected(alice):
    """Test that token with wrong client_id (audience) is rejected."""
    token = create_cognito_access_token(
        sub=alice.cognito_sub,
        email=alice.email,
        client_id="wrong-client-id",
    )
    
    communicator = WebsocketCommunicator(
        application, f"/ws/chat/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unknown_user_token_rejected():
    """Test that token for non-existent local user is rejected."""
    token = create_cognito_access_token(
        sub="unknown-sub-123",
        email="unknown@test.com",
    )
    
    communicator = WebsocketCommunicator(
        application, f"/ws/chat/?token={token}"
    )
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()