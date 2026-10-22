"""
core/views.py
System-level endpoints: health check, version info.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import django
import sys


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/v1/health/
    Used by load balancers and uptime monitors.
    """
    return Response({
        'status': 'ok',
        'python': sys.version,
        'django': django.get_version(),
    })
