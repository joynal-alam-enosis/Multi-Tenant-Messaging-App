from django.urls import path
from .views import MessageListView, MessageReadView

urlpatterns = [
    path('conversations/<uuid:pk>/messages/', MessageListView.as_view(), name='message-list'),
    path('conversations/<uuid:pk>/messages/read/', MessageReadView.as_view(), name='message-read'),
]
