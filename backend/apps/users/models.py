import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model. Every user belongs to one tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="users",
    )
    email = models.EmailField(unique=True)
    # Cognito User Pool subject (`sub`). Null until the user authenticates via Cognito
    # or is linked by seed/admin.
    cognito_sub = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text="Amazon Cognito user `sub` claim",
    )

    # Use email as the login field instead of username
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["tenant"], name="users_user_tenant__79c011_idx"),
            # Name must match users.0002_user_cognito_sub
            models.Index(fields=["cognito_sub"], name="users_user_cognito_a1b2c3_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.email})"
