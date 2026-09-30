import uuid
from django.conf import settings
from django.db import models

class Conversation(models.Model):
    """
    A 1-on-1 conversation between exactly two users.
    The same pair of users must never have two separate conversations (idempotent).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["-last_activity_at"]),
        ]

    def __str__(self) -> str:
        participants = self.participants.select_related("user").all()
        names = [p.user.email for p in participants]
        return f"Conversation: {' <-> '.join(names)}"

class ConversationParticipant(models.Model):
    """
    Join table between Conversation and User.
    Stores per-user state: starred, unread count, last read timestamp.
    Each conversation has exactly 2 participants.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participations",
    )
    is_starred = models.BooleanField(default=False)
    unread_count = models.IntegerField(default=0)
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_participant",
            )
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} in {self.conversation_id}"
