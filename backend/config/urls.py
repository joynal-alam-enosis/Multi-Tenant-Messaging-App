from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.users.urls')),
    path('api/', include('apps.conversations.urls')),
    path('api/', include('apps.messages.urls')),
    path('api/', include('apps.exports.urls')),
]
