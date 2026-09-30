from rest_framework import serializers
from .models import Message

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "sender", "content", "is_read", "created_at"]

    def get_sender(self, obj):
        return {
            "id": str(obj.sender.id),
            "first_name": obj.sender.first_name,
            "last_name": obj.sender.last_name,
            "tenant_name": obj.sender.tenant.name if obj.sender.tenant else None
        }

class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["content"]
