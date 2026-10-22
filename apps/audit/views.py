from rest_framework.views import APIView
from rest_framework.response import Response
from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import AuditLog


class AuditLogsListView(APIView):
    """
    GET /api/v1/audit/logs/
    Retrieve immutable audit log trail for governance and security review.
    Protected strictly by IsAdminOrSuperAdmin.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        logs = AuditLog.objects.all().order_by('-timestamp')[:50]
        data = [
            {
                'id': str(log.id),
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': str(log.entity_id) if log.entity_id else None,
                'actor_id': str(log.actor_id) if log.actor_id else None,
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'before_state': log.before_state,
                'after_state': log.after_state,
            }
            for log in logs
        ]
        return Response({'data': data})
