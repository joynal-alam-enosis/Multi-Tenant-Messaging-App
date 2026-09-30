from rest_framework import serializers
from .models import Conversation, ConversationParticipant
from apps.users.serializers import UserSearchSerializer

class ConversationListSerializer(serializers.ModelSerializer):
    other_participant = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "other_participant",
            "last_message",
            "last_activity_at",
            "created_at",
            "is_starred",
            "unread_count",
        ]

    def get_other_participant(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        for participant in obj.participants.all():
            if participant.user_id != request.user.id:
                return UserSearchSerializer(participant.user).data
        return None

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            content = last_msg.content
            return content[:50] + "..." if len(content) > 50 else content
        return None

    def get_is_starred(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        for participant in obj.participants.all():
            if participant.user_id == request.user.id:
                return participant.is_starred
        return False

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        for participant in obj.participants.all():
            if participant.user_id == request.user.id:
                return participant.unread_count
        return 0

class ConversationCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()

    def validate_user_id(self, value):
        from apps.users.models import User
        request = self.context.get("request")
        if request and request.user.id == value:
            raise serializers.ValidationError("Cannot create a conversation with yourself.")
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value
