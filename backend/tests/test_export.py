import pytest
from unittest.mock import patch
from apps.exports.models import ExportTask

@pytest.mark.django_db
@patch('apps.exports.views.export_conversation.delay')
def test_export_creates_task(mock_delay, alice_client, alice_bob_conversation, alice):
    res = alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/export/')
    assert res.status_code == 202
    
    task_id = res.data['id']
    task = ExportTask.objects.get(id=task_id)
    assert task.status == ExportTask.Status.PENDING
    assert task.user == alice
    mock_delay.assert_called_once_with(str(task.id))

@pytest.mark.django_db
def test_completed_export_can_be_downloaded(alice_client, alice_bob_conversation, alice, tmp_path):
    # Mocking completed export
    file_path = tmp_path / "test_export.json"
    file_path.write_text("{}")
    
    task = ExportTask.objects.create(
        user=alice,
        conversation=alice_bob_conversation,
        status=ExportTask.Status.COMPLETED,
        file_path=str(file_path)
    )

    res = alice_client.get(f'/api/exports/{task.id}/download/')
    assert res.status_code == 200
    assert res.headers['Content-Disposition'] == f'attachment; filename="conversation_export_{task.id}.json"'
