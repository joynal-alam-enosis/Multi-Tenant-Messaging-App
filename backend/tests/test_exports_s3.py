"""
Tests for S3 export integration.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from rest_framework import status

from apps.exports.models import ExportTask
from apps.exports.s3 import get_s3_client, get_export_bucket_name


@pytest.mark.django_db
class TestS3Export:
    """Test S3 export functionality."""

    def test_get_export_bucket_name_from_settings(self, settings):
        settings.EXPORT_S3_BUCKET = "custom-bucket"
        assert get_export_bucket_name() == "custom-bucket"

    def test_get_export_bucket_name_default(self, settings):
        # Remove the setting to test default
        if hasattr(settings, 'EXPORT_S3_BUCKET'):
            delattr(settings, 'EXPORT_S3_BUCKET')
        assert get_export_bucket_name() == "messaging-exports"

    def test_get_s3_client_returns_boto3_client(self):
        client = get_s3_client()
        assert hasattr(client, 'put_object')
        assert hasattr(client, 'generate_presigned_url')
        assert hasattr(client, 'head_bucket')
        assert hasattr(client, 'get_object')

    @patch('apps.exports.s3.get_s3_client')
    def test_ensure_bucket_exists_creates_bucket(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )
        mock_get_client.return_value = mock_client

        from apps.exports.s3 import ensure_bucket_exists
        bucket = ensure_bucket_exists("test-bucket")

        assert bucket == "test-bucket"
        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        mock_client.create_bucket.assert_called_once_with(Bucket="test-bucket")

    @patch('apps.exports.s3.get_s3_client')
    def test_ensure_bucket_exists_returns_existing(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_get_client.return_value = mock_client

        from apps.exports.s3 import ensure_bucket_exists
        bucket = ensure_bucket_exists("existing-bucket")

        assert bucket == "existing-bucket"
        mock_client.head_bucket.assert_called_once_with(Bucket="existing-bucket")
        mock_client.create_bucket.assert_not_called()

    @patch('apps.exports.s3.get_s3_client')
    def test_upload_export(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.put_object.return_value = {"ETag": '"abc123"'}
        mock_get_client.return_value = mock_client

        from apps.exports.s3 import upload_export
        etag = upload_export("test-bucket", "test-key", b'{"data": "test"}')

        assert etag == "abc123"
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key",
            Body=b'{"data": "test"}',
            ContentType="application/json",
        )

    @patch('apps.exports.s3.get_s3_client')
    def test_generate_presigned_download_url(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://presigned.url/test"
        mock_get_client.return_value = mock_client

        from apps.exports.s3 import generate_presigned_download_url
        url = generate_presigned_download_url("test-bucket", "test-key", expires_in=1800)

        assert url == "https://presigned.url/test"
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "test-key"},
            ExpiresIn=1800,
        )


@pytest.mark.django_db
class TestExportTaskS3Fields:
    """Test ExportTask model S3 fields."""

    def test_export_task_has_s3_fields(self, alice, alice_bob_conversation):
        task = ExportTask.objects.create(
            user=alice,
            conversation=alice_bob_conversation,
            status=ExportTask.Status.PENDING
        )
        # S3 fields should exist and default to empty strings
        assert task.s3_bucket == ""
        assert task.s3_key == ""
        assert task.s3_etag == ""

    def test_export_task_s3_fields_can_be_set(self, alice, alice_bob_conversation):
        task = ExportTask.objects.create(
            user=alice,
            conversation=alice_bob_conversation,
            status=ExportTask.Status.COMPLETED,
            s3_bucket="test-bucket",
            s3_key="exports/user1/task1.json",
            s3_etag="abc123"
        )
        assert task.s3_bucket == "test-bucket"
        assert task.s3_key == "exports/user1/task1.json"
        assert task.s3_etag == "abc123"


@pytest.mark.django_db
class TestExportViewsS3:
    """Test export views with S3 integration."""

    @patch('apps.exports.tasks.export_conversation.delay')
    def test_request_export_creates_task(self, mock_delay, alice_client, alice_bob_conversation, alice):
        res = alice_client.post(f'/api/conversations/{alice_bob_conversation.id}/export/')
        assert res.status_code == status.HTTP_202_ACCEPTED
        
        task_id = res.data['id']
        task = ExportTask.objects.get(id=task_id)
        assert task.status == ExportTask.Status.PENDING
        assert task.user == alice
        mock_delay.assert_called_once_with(str(task.id))

    @patch('apps.exports.views.get_s3_client')
    def test_download_export_streams_from_s3(self, mock_get_client, alice_client, alice_bob_conversation, alice):
        """Test that download streams file from S3 through Django."""
        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b'{"test": "data"}'
        mock_body.__iter__ = lambda self: iter([b'{"test": "data"}'])
        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentType": "application/json",
        }
        mock_get_client.return_value = mock_client
        
        task = ExportTask.objects.create(
            user=alice,
            conversation=alice_bob_conversation,
            status=ExportTask.Status.COMPLETED,
            s3_bucket="test-bucket",
            s3_key="exports/user1/task1.json"
        )
        
        res = alice_client.get(f'/api/exports/{task.id}/download/')
        assert res.status_code == status.HTTP_200_OK
        assert res['Content-Type'] == 'application/json'
        assert 'attachment' in res['Content-Disposition']
        mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="exports/user1/task1.json")

    @patch('apps.exports.views.get_s3_client')
    def test_download_export_not_ready(self, mock_get_client, alice_client, alice_bob_conversation, alice):
        task = ExportTask.objects.create(
            user=alice,
            conversation=alice_bob_conversation,
            status=ExportTask.Status.PENDING,
        )
        
        res = alice_client.get(f'/api/exports/{task.id}/download/')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "not ready" in res.data['error'].lower()

    @patch('apps.exports.views.get_s3_client')
    def test_download_export_s3_not_found(self, mock_get_client, alice_client, alice_bob_conversation, alice):
        mock_client = MagicMock()
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        mock_get_client.return_value = mock_client
        
        task = ExportTask.objects.create(
            user=alice,
            conversation=alice_bob_conversation,
            status=ExportTask.Status.COMPLETED,
            s3_bucket="test-bucket",
            s3_key="exports/user1/task1.json"
        )
        
        res = alice_client.get(f'/api/exports/{task.id}/download/')
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in res.data['error'].lower()

    def test_download_export_fallback_to_local_file(self, alice_client, alice_bob_conversation, alice, tmp_path):
        """Test backward compatibility with local file_path."""
        # Create a local file
        file_path = tmp_path / "test_export.json"
        file_path.write_text('{"test": "data"}')
        
        task = ExportTask.objects.create(
            user=alice,
            conversation=alice_bob_conversation,
            status=ExportTask.Status.COMPLETED,
            file_path=str(file_path),  # Local file, no S3 fields
        )
        
        # Should serve local file via FileResponse
        res = alice_client.get(f'/api/exports/{task.id}/download/')
        assert res.status_code == status.HTTP_200_OK
        assert 'attachment' in res['Content-Disposition']


@pytest.mark.django_db
class TestBootstrapExportsBucketCommand:
    """Test the bootstrap_exports_bucket management command."""

    @patch('apps.exports.management.commands.bootstrap_exports_bucket.ensure_bucket_exists')
    def test_bootstrap_command_success(self, mock_ensure, alice_client):
        mock_ensure.return_value = "test-bucket"
        
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('bootstrap_exports_bucket', stdout=out)
        
        assert "Export bucket ready: test-bucket" in out.getvalue()
        mock_ensure.assert_called_once_with(None)

    @patch('apps.exports.management.commands.bootstrap_exports_bucket.ensure_bucket_exists')
    def test_bootstrap_command_with_bucket_name(self, mock_ensure):
        mock_ensure.return_value = "custom-bucket"
        
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('bootstrap_exports_bucket', '--bucket-name=custom-bucket', stdout=out)
        
        assert "Export bucket ready: custom-bucket" in out.getvalue()
        mock_ensure.assert_called_once_with("custom-bucket")