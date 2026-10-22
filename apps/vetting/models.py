"""
vetting/models.py
Technical assessments, healthcare credential tracking, and verification.
Credentials: unverified → verified | rejected; verified → expired (automatic daily scan).
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from encrypted_model_fields.fields import EncryptedCharField


class Assessment(BaseModel):
    class AssessmentType(models.TextChoices):
        CODING_TEST = 'coding_test', 'Coding Test'
        SYSTEM_DESIGN = 'system_design', 'System Design Review'
        REPO_REVIEW = 'repo_review', 'Repository / Portfolio Review'
        BEHAVIORAL = 'behavioral', 'Behavioral Interview'
        CLINICAL = 'clinical', 'Clinical Assessment'

    candidate = models.ForeignKey(
        'candidates.Candidate', on_delete=models.CASCADE, related_name='assessments'
    )
    assessment_type = models.CharField(max_length=30, choices=AssessmentType.choices)
    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-100
    rubric = models.JSONField(default=dict)  # HEXACO / OCEAN / BEI template + scores
    notes = models.TextField(blank=True)
    attachments = models.JSONField(default=list)  # S3 keys
    assessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'vetting_assessment'
        ordering = ['-created_at']


class CredentialStatus(models.TextChoices):
    UNVERIFIED = 'unverified', 'Unverified'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'
    EXPIRED = 'expired', 'Expired'


class Credential(BaseModel):
    """
    Healthcare professional license or certification.
    Candidates submit at intake. Credential Officers verify (D-02).
    License number encrypted at rest.
    """
    class Kind(models.TextChoices):
        LICENSE = 'license', 'Professional License'
        CERTIFICATION = 'certification', 'Certification'

    candidate = models.ForeignKey(
        'candidates.Candidate', on_delete=models.CASCADE, related_name='credentials'
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    name = models.CharField(max_length=255)  # e.g. 'Registered Nurse License'
    license_number = EncryptedCharField(max_length=100, blank=True)  # PII
    jurisdiction = models.CharField(max_length=100, blank=True)  # issuing state/country
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=CredentialStatus.choices, default=CredentialStatus.UNVERIFIED
    )

    # Verification (Credential Officer only)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='verified_credentials'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_method = models.CharField(max_length=100, blank=True)
    rejection_reason = models.TextField(blank=True)
    evidence_document = models.ForeignKey(
        'candidates.Document', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        db_table = 'vetting_credential'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_on']),
            models.Index(fields=['candidate', 'status']),
        ]

    def __str__(self):
        return f'{self.name} ({self.candidate}) - {self.status}'
