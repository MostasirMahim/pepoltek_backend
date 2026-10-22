"""
audit/models.py
Append-only audit trail. No UPDATE or DELETE allowed on this table.
Captures: actor, action, entity type, entity ID, before/after state, IP, timestamp.
"""
from django.db import models
from django.conf import settings
import uuid


class AuditLog(models.Model):
    """
    Immutable audit record. Written by audit.services.record().
    DB-level: REVOKE UPDATE, DELETE from app DB user in production.
    """

    class Action(models.TextChoices):
        # Auth
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        REGISTER = 'register', 'Register'
        PASSWORD_RESET = 'password_reset', 'Password Reset'
        MFA_SETUP = 'mfa_setup', 'MFA Setup'
        # Data
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete (Soft)'
        # Files
        UPLOAD = 'upload', 'File Upload'
        SCAN_PASS = 'scan_pass', 'Malware Scan Passed'
        SCAN_FAIL = 'scan_fail', 'Malware Scan Failed'
        PARSE_START = 'parse_start', 'Parse Started'
        PARSE_DONE = 'parse_done', 'Parse Done'
        PARSE_APPLIED = 'parse_applied', 'Parse Applied to Profile'
        # Workflow
        STAGE_MOVE = 'stage_move', 'Pipeline Stage Move'
        PITCH_AUTHORIZED = 'pitch_authorized', 'Pitch Authorized'
        PITCH_DECLINED = 'pitch_declined', 'Pitch Declined'
        PITCH_REVOKED = 'pitch_revoked', 'Pitch Revoked'
        SUBMISSION_SENT = 'submission_sent', 'Shortlist Submitted to Client'
        # Vetting
        CREDENTIAL_VERIFIED = 'credential_verified', 'Credential Verified'
        CREDENTIAL_REJECTED = 'credential_rejected', 'Credential Rejected'
        CREDENTIAL_EXPIRED = 'credential_expired', 'Credential Auto-Expired'
        # Matching
        MATCH_OVERRIDE = 'match_override', 'Match Score Overridden'
        # Payout
        PAYOUT_APPROVED = 'payout_approved', 'Payout Approved'
        PAYOUT_PAID = 'payout_paid', 'Payout Marked Paid'
        PAYOUT_CANCELLED = 'payout_cancelled', 'Payout Cancelled'
        # Admin
        CONFIG_CHANGE = 'config_change', 'Config Version Published'
        ROLE_ASSIGN = 'role_assign', 'Role Assigned'
        ROLE_REVOKE = 'role_revoke', 'Role Revoked'
        # Security
        LOCKOUT = 'lockout', 'Account Locked Out'
        DATA_EXPORT = 'data_export', 'Data Export Requested'
        DELETE_REQUEST = 'delete_request', 'Account Deletion Requested'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',  # no reverse accessor
        db_column='actor_id',
    )
    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    entity = models.CharField(max_length=100, db_index=True)  # e.g. 'Application'
    entity_id = models.CharField(max_length=100, db_index=True)  # UUID or int as string
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    extra = models.JSONField(null=True, blank=True)  # free-form context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity', 'entity_id']),
            models.Index(fields=['actor', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        actor = self.actor.email if self.actor else 'system'
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {actor} - {self.action} on {self.entity}({self.entity_id})'
