import pytest
from apps.conversations.models import ConversationParticipant

@pytest.mark.django_db
def test_inbox_returns_only_user_conversations(alice_client, alice_bob_conversation, dave):
    # Dave has no conversations, so if we use dave_client, it should be empty
    response = alice_client.get('/api/conversations/')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['id'] == str(alice_bob_conversation.id)

@pytest.mark.django_db
def test_inbox_filter_unread(alice_client, alice_bob_conversation, alice):
    participant = ConversationParticipant.objects.get(conversation=alice_bob_conversation, user=alice)
    participant.unread_count = 5
    participant.save()

    response = alice_client.get('/api/conversations/?filter=unread')
    assert len(response.data) == 1

    participant.unread_count = 0
    participant.save()

    from django.core.cache import cache
    cache.clear()

    response2 = alice_client.get('/api/conversations/?filter=unread')
    assert len(response2.data) == 0

@pytest.mark.django_db
def test_inbox_filter_starred(alice_client, alice_bob_conversation, alice):
    response = alice_client.get('/api/conversations/?filter=starred')
    assert len(response.data) == 0

    alice_client.patch(f'/api/conversations/{alice_bob_conversation.id}/star/')
    response2 = alice_client.get('/api/conversations/?filter=starred')
    assert len(response2.data) == 1

@pytest.mark.django_db
def test_conversation_creation_idempotent(alice_client, alice, dave):
    # First creation
    res1 = alice_client.post('/api/conversations/', {"user_id": str(dave.id)})
    assert res1.status_code == 201
    
    # Second creation
    res2 = alice_client.post('/api/conversations/', {"user_id": str(dave.id)})
    assert res2.status_code == 200
    assert res1.data['id'] == res2.data['id']

@pytest.mark.django_db
def test_star_state_is_per_user(alice_client, bob_client, alice_bob_conversation):
    alice_client.patch(f'/api/conversations/{alice_bob_conversation.id}/star/')
    
    res_alice = alice_client.get(f'/api/conversations/{alice_bob_conversation.id}/')
    assert res_alice.data['is_starred'] is True

    res_bob = bob_client.get(f'/api/conversations/{alice_bob_conversation.id}/')
    assert res_bob.data['is_starred'] is False
