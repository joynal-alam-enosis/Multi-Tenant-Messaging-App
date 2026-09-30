import pytest
from apps.conversations.models import Conversation, ConversationParticipant

@pytest.mark.django_db
def test_non_participant_cannot_get_conversation(dave_client, alice_bob_conversation):
    response = dave_client.get(f'/api/conversations/{alice_bob_conversation.id}/')
    assert response.status_code == 404

@pytest.mark.django_db
def test_non_participant_cannot_send_message(dave_client, alice_bob_conversation):
    response = dave_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/', {"content": "Snooping"})
    assert response.status_code == 403

@pytest.mark.django_db
def test_non_participant_cannot_star_conversation(dave_client, alice_bob_conversation):
    response = dave_client.patch(f'/api/conversations/{alice_bob_conversation.id}/star/')
    assert response.status_code == 404

@pytest.mark.django_db
def test_non_participant_cannot_export_conversation(dave_client, alice_bob_conversation):
    response = dave_client.post(f'/api/conversations/{alice_bob_conversation.id}/export/')
    assert response.status_code == 403

@pytest.mark.django_db
def test_unauthenticated_gets_401(api_client, alice_bob_conversation):
    endpoints = [
        f'/api/conversations/',
        f'/api/conversations/{alice_bob_conversation.id}/',
        f'/api/conversations/{alice_bob_conversation.id}/messages/',
        f'/api/conversations/{alice_bob_conversation.id}/star/',
    ]
    for url in endpoints:
        assert api_client.get(url).status_code == 401 or api_client.post(url).status_code == 401
