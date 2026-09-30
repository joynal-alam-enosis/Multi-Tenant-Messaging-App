import uuid
from django.conf import settings
from django.db import models

class ExportTask(models.Model):
    """Tracks an async conversation export job."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="export_tasks",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="export_tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Legacy local file path (kept for backward compat during migration)
    file_path = models.CharField(max_length=500, blank=True, default="")
    # S3 storage fields
    s3_bucket = models.CharField(max_length=255, blank=True, default="")
    s3_key = models.CharField(max_length=500, blank=True, default="")
    s3_etag = models.CharField(max_length=100, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Export {self.id} ({self.status})"
