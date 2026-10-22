"""
accounts/models.py
Custom User model, multi-persona UserRole, and ConsentRecord.
A single User can hold multiple roles simultaneously (CANDIDATE + REFERRER + LEARNER, etc.)
"""
import secrets
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField

from apps.core.models import BaseModel, generate_uuid7


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)


class UserStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    SUSPENDED = 'suspended', 'Suspended'
    PENDING_VERIFICATION = 'pending_verification', 'Pending Email Verification'


class AuthProvider(models.TextChoices):
    EMAIL = 'email', 'Email/Password'
    GOOGLE = 'google', 'Google OAuth'
    LINKEDIN = 'linkedin', 'LinkedIn OAuth'
    MAGIC_LINK = 'magic_link', 'Magic Link'


class User(AbstractBaseUser, PermissionsMixin):
    """
    Single unified user model for all personas: Candidate, Referrer, Learner, Staff.
    Password hashing: Argon2 (configured in settings.PASSWORD_HASHERS).
    Auth: JWT via httpOnly cookies (never localStorage).
    """
    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)

    auth_provider = models.CharField(
        max_length=20, choices=AuthProvider.choices, default=AuthProvider.EMAIL
    )
    status = models.CharField(
        max_length=30, choices=UserStatus.choices, default=UserStatus.PENDING_VERIFICATION
    )
    mfa_enabled = models.BooleanField(default=False)
    mfa_confirmed_at = models.DateTimeField(null=True, blank=True)

    # Referral system - every user gets a code on creation
    referral_code = models.CharField(max_length=12, unique=True, db_index=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='referred_users'
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        db_table = 'accounts_user'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['referral_code']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_unique_referral_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_unique_referral_code() -> str:
        """12-char alphanumeric, uppercase. Collision check done at save."""
        while True:
            code = secrets.token_urlsafe(9).upper()[:12]
            if not User.objects.filter(referral_code=code).exists():
                return code

    def has_role(self, role: str) -> bool:
        """Check if user holds a specific role."""
        return self.roles.filter(role=role).exists()

    def get_roles(self) -> list[str]:
        return list(self.roles.values_list('role', flat=True))

    def get_all_permissions_list(self) -> list[str]:
        """Returns aggregated list of clearances and permissions across all assigned roles."""
        if getattr(self, 'is_superuser', False):
            return ['*']
        roles = self.get_roles()
        perms = set()
        for r in roles:
            role_def = RoleDefinition.objects.filter(code=r).first()
            if role_def and role_def.permissions:
                perms.update(role_def.permissions)
        return sorted(list(perms))

    def record_login(self):
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])


class RoleChoice(models.TextChoices):
    CANDIDATE = 'CANDIDATE', 'Candidate'
    REFERRER = 'REFERRER', 'Referrer'
    LEARNER = 'LEARNER', 'Learner'
    RECRUITER = 'RECRUITER', 'Recruiter'
    BUSINESS_ANALYST = 'BUSINESS_ANALYST', 'Business Analyst'
    TECH_VALIDATOR = 'TECH_VALIDATOR', 'Tech Validator'
    CREDENTIAL_OFFICER = 'CREDENTIAL_OFFICER', 'Credential Officer'
    ADMIN = 'ADMIN', 'Admin'
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'


class RoleDefinition(BaseModel):
    """
    Role Group and Permissions Definition.
    Allows administrators to dynamically create new roles, update clearances,
    and configure granular capabilities.
    """
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='Internal Staff')
    description = models.TextField(blank=True)
    scope = models.CharField(max_length=255, blank=True)
    permissions = models.JSONField(default=list)
    is_system_role = models.BooleanField(default=False)

    class Meta:
        db_table = 'accounts_role_definition'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class UserRole(BaseModel):
    """
    One row per role assignment. A user can have multiple rows.
    scope_client_id: reserved for future multi-tenant client portal (D-01 post-GTM).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=50)
    scope_client_id = models.UUIDField(null=True, blank=True)  # future tenant scoping

    class Meta:
        db_table = 'accounts_user_role'
        unique_together = [('user', 'role', 'scope_client_id')]
        indexes = [models.Index(fields=['user', 'role'])]

    def __str__(self):
        return f'{self.user.email} - {self.role}'


class ConsentRecord(BaseModel):
    """
    Immutable consent capture. One row per consent event.
    Never update - append new rows when policy changes.
    """
    class PolicyType(models.TextChoices):
        TERMS = 'terms', 'Terms of Service'
        PRIVACY = 'privacy', 'Privacy Policy'
        DATA_PROCESSING = 'data_processing', 'Data Processing Consent'
        MARKETING = 'marketing', 'Marketing Communications'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consents')
    policy_type = models.CharField(max_length=30, choices=PolicyType.choices)
    policy_version = models.CharField(max_length=20)  # e.g. "2026-10-01"
    agreed = models.BooleanField()
    ip_address = EncryptedCharField(max_length=45)  # supports IPv6
    user_agent = models.TextField(blank=True)
    agreed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_consent_record'
        ordering = ['-agreed_at']

    def __str__(self):
        return f'{self.user.email} - {self.policy_type} v{self.policy_version}'
