from rest_framework import serializers
from .models import Tenant

class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenant data. Used nested inside user responses."""
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]
