import pytest

@pytest.mark.django_db
def test_search_returns_matching_users(alice_client, bob, dave):
    res = alice_client.get('/api/users/search/?q=bob')
    assert len(res.data) == 1
    assert res.data[0]['email'] == bob.email

@pytest.mark.django_db
def test_search_omits_sensitive_fields(alice_client, bob):
    res = alice_client.get('/api/users/search/?q=bob')
    user_data = res.data[0]
    assert 'password' not in user_data
    assert 'is_staff' not in user_data
    assert 'is_superuser' not in user_data
    assert 'tenant_name' in user_data

@pytest.mark.django_db
def test_search_excludes_requesting_user(alice_client, alice):
    res = alice_client.get('/api/users/search/?q=alice')
    assert len(res.data) == 0

@pytest.mark.django_db
def test_cross_tenant_search_works(alice_client, dave):
    res = alice_client.get('/api/users/search/?q=dave')
    assert len(res.data) == 1
    assert res.data[0]['email'] == dave.email
