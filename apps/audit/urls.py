from django.urls import path
from .views import AuditLogsListView

urlpatterns = [
    path('logs/', AuditLogsListView.as_view(), name='audit-logs-list'),
]
