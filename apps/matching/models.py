"""
matching/models.py
Candidate-requisition match scores, pitch authorization, interview records.
Embeddings and scoring engine live in matching.services and matching.tasks.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class Match(BaseModel):
    """
    Computed match score between a candidate and a requisition.
    Recomputed on profile change, new requisition, or nightly batch.
    Factors JSON stores the breakdown: skills, level, timezone, auth, semantic.
    """
    candidate = models.ForeignKey(
        'candidates.Candidate', on_delete=models.CASCADE, related_name='matches'
    )
    requisition = models.ForeignKey(
        'ats.Requisition', on_delete=models.CASCADE, related_name='matches'
    )
    score = models.FloatField(default=0.0)  # 0.0-100.0
    factors = models.JSONField(default=dict)  # breakdown per factor
    model_version = models.CharField(max_length=50, blank=True)

    # Recruiter override
    override_score = models.FloatField(null=True, blank=True)
    override_reason = models.TextField(blank=True)
    override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'matching_match'
        unique_together = [('candidate', 'requisition')]
        ordering = ['-score']

    @property
    def effective_score(self) -> float:
        return self.override_score if self.override_score is not None else self.score

    def __str__(self):
        return f'Match({self.candidate} / {self.requisition}) = {self.effective_score:.1f}'


class PitchAuthorizationStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    AUTHORIZED = 'authorized', 'Authorized'
    DECLINED = 'declined', 'Declined'
    REVOKED = 'revoked', 'Revoked'


class PitchAuthorization(BaseModel):
    """
    Explicit candidate consent before their profile is sent to a client.
    Required for Submission. Revocation blocks future submissions, not past ones.
    snapshot_hash = SHA256 of candidate profile at time of authorization.
    """
    candidate = models.ForeignKey(
        'candidates.Candidate', on_delete=models.CASCADE, related_name='pitch_authorizations'
    )
    requisition = models.ForeignKey(
        'ats.Requisition', on_delete=models.CASCADE, related_name='pitch_authorizations'
    )
    status = models.CharField(
        max_length=20, choices=PitchAuthorizationStatus.choices,
        default=PitchAuthorizationStatus.REQUESTED
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    snapshot_hash = models.CharField(max_length=64, blank=True)  # SHA256 of profile at auth time
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'matching_pitch_authorization'
        unique_together = [('candidate', 'requisition')]

    def __str__(self):
        return f'PitchAuth({self.candidate} → {self.requisition}) = {self.status}'
