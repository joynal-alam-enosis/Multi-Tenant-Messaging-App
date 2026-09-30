from rest_framework.permissions import BasePermission
from .models import ConversationParticipant

class IsConversationParticipant(BasePermission):
    """
    Permission check: the requesting user must be a participant
    in the conversation being accessed.

    Used on all conversation detail, message, star, and export endpoints.
    """
    message = "You are not a participant in this conversation."

    def has_object_permission(self, request, view, obj):
        return ConversationParticipant.objects.filter(
            conversation=obj,
            user=request.user,
        ).exists()
