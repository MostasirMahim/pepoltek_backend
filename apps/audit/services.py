"""
audit/services.py
Single function to write audit records. Called from services.py in every app.
Never call this from views or serializers.
"""
import logging
from .models import AuditLog

logger = logging.getLogger(__name__)


def record(
    *,
    action: str,
    entity: str,
    entity_id,
    actor=None,
    before: dict | None = None,
    after: dict | None = None,
    extra: dict | None = None,
    request=None,
) -> AuditLog:
    """
    Write an immutable audit event.

    Usage:
        from apps.audit.services import record
        from apps.audit.models import AuditLog

        record(
            action=AuditLog.Action.STAGE_MOVE,
            entity='Application',
            entity_id=str(application.id),
            actor=request.user,
            before={'stage': 'market_mapping'},
            after={'stage': 'technical_vetting'},
            request=request,
        )
    """
    ip = None
    ua = ''
    if request:
        ip = _get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')

    try:
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            before=before,
            after=after,
            extra=extra,
            ip_address=ip,
            user_agent=ua,
        )
    except Exception as e:
        # Audit failure must never break the main transaction
        logger.error('Failed to write audit log: action=%s entity=%s error=%s', action, entity, e)
        return None


def _get_client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
