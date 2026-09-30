import pytest
from apps.conversations.models import ConversationParticipant

@pytest.mark.django_db
def test_send_message(alice_client, alice_bob_conversation, bob):
    response = alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/', {"content": "Hello bob"})
    assert response.status_code == 201
    assert response.data['content'] == "Hello bob"

@pytest.mark.django_db
def test_sending_message_increments_unread_count(alice_client, alice_bob_conversation, bob):
    alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/', {"content": "Message 1"})
    alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/', {"content": "Message 2"})
    
    participant_bob = ConversationParticipant.objects.get(conversation=alice_bob_conversation, user=bob)
    assert participant_bob.unread_count == 2

@pytest.mark.django_db
def test_mark_as_read_resets_unread_count(alice_client, bob_client, alice_bob_conversation, bob):
    alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/', {"content": "Hello"})
    
    participant_bob = ConversationParticipant.objects.get(conversation=alice_bob_conversation, user=bob)
    assert participant_bob.unread_count == 1
    
    bob_client.post(f'/api/conversations/{alice_bob_conversation.id}/messages/read/')
    
    participant_bob.refresh_from_db()
    assert participant_bob.unread_count == 0
