from django.urls import path
from .views import RequestExportView, DownloadExportView, ExportStatusView

urlpatterns = [
    path('conversations/<uuid:pk>/export/', RequestExportView.as_view(), name='request-export'),
    path('exports/<uuid:pk>/', ExportStatusView.as_view(), name='export-status'),
    path('exports/<uuid:pk>/download/', DownloadExportView.as_view(), name='download-export'),
]
