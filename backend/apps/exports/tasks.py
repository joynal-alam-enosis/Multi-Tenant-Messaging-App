import json
from celery import shared_task
from django.utils import timezone
from apps.exports.models import ExportTask
from apps.messages.models import Message
from apps.exports.s3 import get_export_bucket_name, ensure_bucket_exists, upload_export

@shared_task
def export_conversation(export_task_id: str):
    try:
        task = ExportTask.objects.select_related('conversation').get(id=export_task_id)
        task.status = ExportTask.Status.PROCESSING
        task.save()

        conversation = task.conversation
        messages = Message.objects.filter(conversation=conversation).select_related('sender').order_by('created_at')

        # Build JSON
        participants = [p.user.email for p in conversation.participants.select_related('user').all()]
        
        data = {
            "conversation_id": str(conversation.id),
            "participants": participants,
            "exported_at": timezone.now().isoformat(),
            "messages": []
        }

        for msg in messages:
            data["messages"].append({
                "sender": msg.sender.email,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "is_read": msg.is_read
            })

        # Upload to S3
        bucket = ensure_bucket_exists()
        s3_key = f"exports/{task.user_id}/{task.id}.json"
        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        
        etag = upload_export(bucket, s3_key, json_bytes)

        # Update task with S3 info
        task.status = ExportTask.Status.COMPLETED
        task.s3_bucket = bucket
        task.s3_key = s3_key
        task.s3_etag = etag
        task.completed_at = timezone.now()
        task.save()

    except Exception as e:
        if 'task' in locals():
            task.status = ExportTask.Status.FAILED
            task.error_message = str(e)
            task.save()
        raise e