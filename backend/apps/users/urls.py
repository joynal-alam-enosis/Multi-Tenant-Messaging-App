from django.urls import path
from .views import LoginView, MeView, UserSearchView, CognitoConfigView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/cognito-config/", CognitoConfigView.as_view(), name="cognito-config"),
    path("users/search/", UserSearchView.as_view(), name="user-search"),
]
