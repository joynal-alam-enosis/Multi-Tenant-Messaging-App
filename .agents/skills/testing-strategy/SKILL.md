---
name: testing-strategy
description: >-
  Use this skill when writing, running, or debugging tests for the messaging application.
  Covers backend tests (pytest, Django test client, WebSocket tests) and frontend tests
  (React Testing Library, component tests).
---

# Testing Strategy Skill

## Backend Testing

### Tech Stack
- pytest + pytest-django
- pytest-asyncio (for WebSocket consumer tests)
- factory_boy (model factories)
- Django REST Framework's APIClient

### Test Structure
```
backend/tests/
├── conftest.py                    # Shared fixtures (users, tenants, conversations)
├── factories.py                   # Factory Boy factories
├── test_models.py                 # Model constraints and methods
├── test_conversations_api.py      # Inbox, create, star, idempotency
├── test_messages_api.py           # Send, list, mark read
├── test_permissions.py            # Authorization enforcement
├── test_user_search.py            # Search + safe field validation
├── test_cache.py                  # Redis cache hit/miss/invalidation
├── test_websocket.py              # WebSocket consumer tests
└── test_export.py                 # Celery task tests
```

### Shared Fixtures (conftest.py)

```python
import pytest
from apps.tenants.models import Tenant
from apps.users.models import User

@pytest.fixture
def acme_tenant(db):
    return Tenant.objects.create(name="Acme Corp", slug="acme")

@pytest.fixture
def globex_tenant(db):
    return Tenant.objects.create(name="Globex Inc", slug="globex")

@pytest.fixture
def alice(acme_tenant):
    return User.objects.create_user(
        email="alice@acme.com", password="password123",
        first_name="Alice", last_name="Johnson", tenant=acme_tenant
    )

@pytest.fixture
def dave(globex_tenant):
    return User.objects.create_user(
        email="dave@globex.com", password="password123",
        first_name="Dave", last_name="Smith", tenant=globex_tenant
    )

@pytest.fixture
def alice_dave_conversation(alice, dave):
    """Pre-created cross-tenant conversation."""
    from apps.conversations.models import Conversation, ConversationParticipant
    conv = Conversation.objects.create()
    ConversationParticipant.objects.create(conversation=conv, user=alice)
    ConversationParticipant.objects.create(conversation=conv, user=dave)
    return conv

@pytest.fixture
def alice_client(alice):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=alice)
    return client

@pytest.fixture
def dave_client(dave):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=dave)
    return client
```

### Critical Test Cases

Every one of these MUST pass before the application is considered complete:

#### 1. Inbox Isolation
```python
@pytest.mark.django_db
def test_user_cannot_see_other_users_inbox(alice_client, dave_client, alice_dave_conversation):
    """Alice's inbox shows the conversation, but a third user's inbox does not."""
    response = alice_client.get('/api/conversations/')
    assert len(response.data) == 1
    
    # Create a third user who is NOT in the conversation
    bob = User.objects.create_user(email="bob@acme.com", ...)
    bob_client = APIClient()
    bob_client.force_authenticate(user=bob)
    response = bob_client.get('/api/conversations/')
    assert len(response.data) == 0
```

#### 2. Participant-Only Conversation Access
```python
@pytest.mark.django_db
def test_non_participant_cannot_access_conversation(bob_client, alice_dave_conversation):
    response = bob_client.get(f'/api/conversations/{alice_dave_conversation.id}/')
    assert response.status_code == 403
```

#### 3. Participant-Only Message Sending
```python
@pytest.mark.django_db
def test_non_participant_cannot_send_message(bob_client, alice_dave_conversation):
    response = bob_client.post(
        f'/api/conversations/{alice_dave_conversation.id}/messages/',
        {'content': 'Intruder!'}
    )
    assert response.status_code == 403
```

#### 4. Star State Isolation
```python
@pytest.mark.django_db
def test_starring_does_not_affect_other_participant(alice_client, dave_client, alice_dave_conversation):
    # Alice stars
    alice_client.patch(f'/api/conversations/{alice_dave_conversation.id}/star/')
    
    # Alice sees it starred
    response = alice_client.get('/api/conversations/')
    assert response.data[0]['is_starred'] == True
    
    # Dave sees it NOT starred
    response = dave_client.get('/api/conversations/')
    assert response.data[0]['is_starred'] == False
```

#### 5. Conversation Idempotency
```python
@pytest.mark.django_db
def test_conversation_creation_is_idempotent(alice_client, dave):
    response1 = alice_client.post('/api/conversations/', {'user_id': str(dave.id)})
    response2 = alice_client.post('/api/conversations/', {'user_id': str(dave.id)})
    
    assert response1.data['id'] == response2.data['id']  # Same conversation
    assert response2.status_code == 200  # Not 201
```

#### 6. User Search Safety
```python
@pytest.mark.django_db
def test_user_search_does_not_expose_sensitive_fields(alice_client):
    response = alice_client.get('/api/users/search/?q=alice')
    user_data = response.data[0]
    
    assert 'password' not in user_data
    assert 'last_login' not in user_data
    assert 'is_superuser' not in user_data
    assert 'is_staff' not in user_data
    
    # Should include safe fields
    assert 'id' in user_data
    assert 'email' in user_data
    assert 'first_name' in user_data
    assert 'tenant_name' in user_data
```

#### 7. Cross-Tenant Messaging
```python
@pytest.mark.django_db
def test_cross_tenant_conversation_works(alice_client, dave):
    """Alice (Acme) can create a conversation with Dave (Globex)."""
    response = alice_client.post('/api/conversations/', {'user_id': str(dave.id)})
    assert response.status_code == 201
```

#### 8. Cache Invalidation
```python
@pytest.mark.django_db
def test_cache_invalidated_after_message(alice_client, alice, dave, alice_dave_conversation):
    from django.core.cache import cache
    
    # Prime the cache
    alice_client.get('/api/conversations/')
    assert cache.get(f'inbox:{alice.id}:all') is not None
    
    # Send a message
    alice_client.post(
        f'/api/conversations/{alice_dave_conversation.id}/messages/',
        {'content': 'Hello!'}
    )
    
    # Cache should be invalidated
    assert cache.get(f'inbox:{alice.id}:all') is None
```

### Running Tests
```bash
# All backend tests
cd backend && pytest -v

# Specific test file
pytest tests/test_permissions.py -v

# With coverage
pytest --cov=apps --cov-report=html
```

## Frontend Testing

### Tech Stack
- Vitest
- React Testing Library
- MSW (Mock Service Worker) for API mocking

### Test Patterns
```typescript
// Component renders loading state
test('shows loading spinner while fetching', () => {
  render(<InboxView />);
  expect(screen.getByRole('status')).toBeInTheDocument();
});

// Component renders data
test('shows conversation list', async () => {
  render(<InboxView />);
  expect(await screen.findByText('Dave Smith')).toBeInTheDocument();
  expect(screen.getByText('Globex Inc')).toBeInTheDocument();
});

// Component renders empty state
test('shows empty state when no conversations', async () => {
  server.use(rest.get('/api/conversations/', (req, res, ctx) => res(ctx.json([]))));
  render(<InboxView />);
  expect(await screen.findByText(/no conversations/i)).toBeInTheDocument();
});
```
