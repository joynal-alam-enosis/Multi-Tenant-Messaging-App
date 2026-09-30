import pytest
from unittest.mock import patch
from apps.conversations.cache import get_cached_inbox

@pytest.mark.django_db
@patch('apps.conversations.views.get_cached_inbox')
@patch('apps.conversations.views.set_inbox_cache')
def test_inbox_cached(mock_set, mock_get, alice_client, alice):
    mock_get.return_value = None
    alice_client.get('/api/conversations/')
    mock_get.assert_called_with(str(alice.id), 'all')
    mock_set.assert_called()

@pytest.mark.django_db
@patch('apps.messages.views.invalidate_inbox_cache')
def test_cache_invalidated_after_sending_message(mock_invalidate, alice_client, alice_bob_conversation, alice, bob):
    alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/', {"content": "Test"})
    assert mock_invalidate.call_count == 2 # Once for alice, once for bob

@pytest.mark.django_db
@patch('apps.conversations.views.invalidate_inbox_cache')
def test_cache_invalidated_after_starring(mock_invalidate, alice_client, alice_bob_conversation, alice):
    alice_client.patch(f'/api/conversations/{alice_bob_conversation.id}/star/')
    mock_invalidate.assert_called_once_with(str(alice.id))
