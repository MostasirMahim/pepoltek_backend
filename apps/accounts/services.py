"""
accounts/services.py
All auth business logic. Views call these functions - never do DB writes in views.
"""
import logging
from django.db import transaction

from .models import User, UserRole, RoleChoice, ConsentRecord

logger = logging.getLogger(__name__)


@transaction.atomic
def register_user(
    *,
    email: str,
    password: str,
    full_name: str = '',
    referral_code: str | None = None,
    ip_address: str = '',
    user_agent: str = '',
    consents: list[dict] | None = None,
) -> User:
    """
    Create a new user account.
    - Normalises email, sets Argon2 password hash
    - Assigns default roles: CANDIDATE + REFERRER + LEARNER
    - Attributes referral if a valid code is provided
    - Records consent records
    """
    if User.objects.filter(email__iexact=email).exists():
        from rest_framework.exceptions import ValidationError
        raise ValidationError({'email': 'An account with this email already exists.'})

    referred_by = None
    if referral_code:
        try:
            referrer = User.objects.get(referral_code=referral_code)
            if referrer.email.lower() != email.lower():  # block self-referral
                referred_by = referrer
        except User.DoesNotExist:
            pass  # invalid code, ignore silently

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        referred_by=referred_by,
    )

    # Every registered user gets these 3 default personas
    default_roles = [RoleChoice.CANDIDATE, RoleChoice.REFERRER, RoleChoice.LEARNER]
    UserRole.objects.bulk_create([
        UserRole(user=user, role=role) for role in default_roles
    ])

    # Record consent events
    if consents:
        for c in consents:
            ConsentRecord.objects.create(
                user=user,
                policy_type=c['policy_type'],
                policy_version=c.get('policy_version', ''),
                agreed=c.get('agreed', True),
                ip_address=ip_address,
                user_agent=user_agent,
            )

    logger.info('User registered: %s (referred_by=%s)', user.email, referred_by)
    return user


def assign_role(user: User, role: str, scope_client_id=None) -> UserRole:
    """Grant a role to an existing user. Idempotent."""
    obj, _ = UserRole.objects.get_or_create(
        user=user, role=role, scope_client_id=scope_client_id
    )
    return obj


def revoke_role(user: User, role: str) -> None:
    """Remove a role. Safe to call even if role is not assigned."""
    UserRole.objects.filter(user=user, role=role).delete()


def record_consent(user: User, policy_type: str, policy_version: str,
                   agreed: bool, ip_address: str, user_agent: str = '') -> ConsentRecord:
    """Append a new consent row. Never mutate existing rows."""
    return ConsentRecord.objects.create(
        user=user,
        policy_type=policy_type,
        policy_version=policy_version,
        agreed=agreed,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def revoke_all_user_tokens(target_user: User) -> int:
    """
    Revoke all active refresh tokens for the given user, immediately
    invalidating current active authentication sessions.
    """
    count = 0
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        for t in OutstandingToken.objects.filter(user=target_user):
            _, created = BlacklistedToken.objects.get_or_create(token=t)
            if created:
                count += 1
    except Exception as e:
        logger.warning('Token revocation encountered exception for user %s: %s', target_user.id, e)
    return count


@transaction.atomic
def admin_set_user_status(*, user_id: str, is_active: bool, status_val: str, admin_user, request=None) -> User:
    """
    Activate or suspend a user account, revoking active sessions if suspended.
    """
    from rest_framework.exceptions import ValidationError, NotFound
    from apps.audit.services import record as record_audit
    from apps.audit.models import AuditLog
    from .models import UserStatus

    clean_id = str(user_id).replace("USR-", "").replace("-", "")
    user = None
    try:
        user = User.objects.filter(id=user_id).first()
    except Exception:
        pass

    if not user:
        for u in User.objects.all():
            u_clean = str(u.id).replace("-", "")
            if clean_id.lower() in u_clean.lower() or u_clean.lower().startswith(clean_id.lower()):
                user = u
                break

    if not user:
        raise NotFound("User account not found.")

    if admin_user and str(user.id) == str(admin_user.id):
        raise ValidationError("Self-suspension is blocked. You cannot deactivate your own active session.")

    before_state = {
        'status': user.status,
        'is_active': user.is_active,
    }

    user.is_active = is_active
    user.status = status_val
    user.save(update_fields=['is_active', 'status'])

    # Invalidate sessions if deactivated or suspended
    if not is_active or status_val == UserStatus.SUSPENDED:
        revoke_all_user_tokens(user)

    record_audit(
        action=AuditLog.Action.UPDATE,
        entity='User',
        entity_id=str(user.id),
        actor=admin_user,
        before=before_state,
        after={'status': user.status, 'is_active': user.is_active},
        request=request,
    )
    return user


@transaction.atomic
def admin_decommission_user(*, user_id: str, admin_user, reason: str = '', request=None) -> tuple[User, str]:
    """
    Decommission a user account, revoke all sessions, and anonymize PII
    under GDPR / Right-to-be-Forgotten compliance while preserving relational ledger integrity.
    """
    from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
    from apps.audit.services import record as record_audit
    from apps.audit.models import AuditLog
    from .models import UserStatus

    clean_id = str(user_id).replace("USR-", "").replace("-", "")
    user = None
    try:
        user = User.objects.filter(id=user_id).first()
    except Exception:
        pass

    if not user:
        for u in User.objects.all():
            u_clean = str(u.id).replace("-", "")
            if clean_id.lower() in u_clean.lower() or u_clean.lower().startswith(clean_id.lower()):
                user = u
                break

    if not user:
        raise NotFound("User account not found.")

    if admin_user and str(user.id) == str(admin_user.id):
        raise ValidationError("Self-decommission is blocked. You cannot delete your own administrative account.")

    if user.is_superuser and admin_user and not admin_user.is_superuser:
        raise PermissionDenied("Only a Super Administrator can decommission another Super Administrator.")

    before_state = {
        'email': user.email,
        'full_name': user.full_name,
        'status': user.status,
        'is_active': user.is_active,
    }

    original_email = user.email
    anonymized_email = f"decommissioned_{user.id.hex[:8]}@anonymized.pepoltek.internal"

    user.is_active = False
    user.status = UserStatus.INACTIVE
    user.email = anonymized_email
    user.full_name = "Decommissioned User"
    user.save(update_fields=['is_active', 'status', 'email', 'full_name'])

    revoke_all_user_tokens(user)

    record_audit(
        action=AuditLog.Action.DELETE,
        entity='User',
        entity_id=str(user.id),
        actor=admin_user,
        before=before_state,
        after={'status': 'decommissioned', 'is_active': False, 'email': anonymized_email},
        extra={'original_email': original_email, 'reason': reason or 'Admin decommission'},
        request=request,
    )
    return user, original_email

