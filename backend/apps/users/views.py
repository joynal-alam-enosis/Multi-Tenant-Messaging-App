from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.cognito import get_cognito_client_id, get_cognito_user_pool_id
from apps.users.models import User
from apps.users.serializers import UserMeSerializer, UserSearchSerializer


class LoginView(APIView):
    """
    Legacy DRF Token login (kept during Cognito migration).

    Prefer Cognito InitiateAuth from the frontend (Phase 4). This endpoint
    remains so the current UI keeps working until Token auth is removed.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        user = authenticate(request, email=email, password=password)
        if user is not None:
            token, _ = Token.objects.get_or_create(user=user)
            return Response(
                {
                    "token": token.key,
                    "user": UserMeSerializer(user).data,
                    "auth_mode": "drf_token",
                    "warning": (
                        "Legacy Token login. Migrate to Cognito Bearer tokens "
                        "(see docs/MINISTACK_COGNITO_PLAN.md)."
                    ),
                }
            )
        return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    """Return the authenticated local user profile (Cognito Bearer or DRF Token)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserMeSerializer(request.user).data)


class CognitoConfigView(APIView):
    """
    Public Cognito client settings for the SPA (no secrets — public app client).

    The browser uses these IDs with USER_PASSWORD_AUTH against MiniStack/AWS.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "user_pool_id": get_cognito_user_pool_id(),
                "client_id": get_cognito_client_id(),
                "region": getattr(settings, "AWS_REGION", "us-east-1"),
            }
        )


class UserSearchView(generics.ListAPIView):
    serializer_class = UserSearchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        queryset = User.objects.select_related("tenant").exclude(id=self.request.user.id)
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )
        return queryset
