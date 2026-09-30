from rest_framework import serializers
from .models import User


class UserMeSerializer(serializers.ModelSerializer):
    """Safe profile payload for /api/auth/me/ and login responses."""

    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "tenant_id", "tenant_name"]


class UserSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for user search results.
    SECURITY: Only exposes safe fields. Never includes password,
    last_login, is_superuser, is_staff, or token fields.
    """

    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "tenant_id", "tenant_name"]
