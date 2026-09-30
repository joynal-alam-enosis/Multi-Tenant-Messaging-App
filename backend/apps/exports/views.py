import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from apps.conversations.models import Conversation
from apps.conversations.permissions import IsConversationParticipant
from .models import ExportTask
from .tasks import export_conversation
from .s3 import get_s3_client
from botocore.exceptions import ClientError

class RequestExportView(APIView):
    permission_classes = [IsAuthenticated, IsConversationParticipant]

    def post(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk)
        self.check_object_permissions(self.request, conv)

        task = ExportTask.objects.create(
            user=request.user,
            conversation=conv,
            status=ExportTask.Status.PENDING
        )
        
        # Dispatch Celery task
        export_conversation.delay(str(task.id))

        return Response({
            "id": str(task.id),
            "status": task.status
        }, status=status.HTTP_202_ACCEPTED)


class ExportStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        task = get_object_or_404(ExportTask, pk=pk, user=request.user)
        return Response({
            "id": str(task.id),
            "status": task.status
        })


class DownloadExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        task = get_object_or_404(ExportTask, pk=pk, user=request.user)
        
        if task.status != ExportTask.Status.COMPLETED:
            return Response({"error": "Export is not ready yet."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Prefer S3 fields; stream from S3 through Django (proxy)
        if task.s3_bucket and task.s3_key:
            client = get_s3_client()
            try:
                obj = client.get_object(Bucket=task.s3_bucket, Key=task.s3_key)
                response = FileResponse(
                    obj["Body"],
                    as_attachment=True,
                    filename=f"conversation_export_{task.id}.json",
                    content_type=obj.get("ContentType", "application/json"),
                )
                return response
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchKey":
                    return Response({"error": "Export file not found in S3."}, status=status.HTTP_404_NOT_FOUND)
                return Response({"error": f"Failed to download export: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as e:
                return Response({"error": f"Failed to download export: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        # Backward compat: serve local file if S3 fields not set
        if not task.file_path or not os.path.exists(task.file_path):
            return Response({"error": "Export file not found."}, status=status.HTTP_404_NOT_FOUND)
            
        response = FileResponse(open(task.file_path, 'rb'), as_attachment=True, filename=f"conversation_export_{task.id}.json")
        return response