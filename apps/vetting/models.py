"""
vetting/models.py

Dynamic Assessment & Vetting System.
Replaces static AssessmentType TextChoices with a fully admin-managed workflow:

  AssessmentTemplate  -- recruiter/admin creates reusable assessment definitions
  ApplicationVetting  -- links an application to a template with validators & timing
  VettingAnswer       -- validator/recruiter submits candidate answers / artefacts
  VettingScore        -- primary validator posts final score (0-100) & decision
  Credential          -- healthcare licence tracking (unchanged)
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from encrypted_model_fields.fields import EncryptedCharField


# ---------------------------------------------------------------------------
# Sector choices -- mirrors Requisition.sector taxonomy
# ---------------------------------------------------------------------------

class SectorType(models.TextChoices):
    TECHNOLOGY = 'technology', 'Technology'
    HEALTHCARE = 'healthcare', 'Healthcare'
    BOTH       = 'both',       'Both / Cross-Sector'


# ---------------------------------------------------------------------------
# 1. AssessmentTemplate  (admin-/recruiter-managed library)
# ---------------------------------------------------------------------------

class AssessmentTemplate(BaseModel):
    """
    Reusable assessment definition created by admins or recruiters.
    Each template describes WHAT to assess, HOW to score it, and WHO can validate.
    """

    class Category(models.TextChoices):
        TECHNICAL   = 'technical',   'Technical Assessment'
        BEHAVIOURAL = 'behavioural', 'Behavioural Interview'
        PORTFOLIO   = 'portfolio',   'Repository / Portfolio Review'
        CLINICAL    = 'clinical',    'Clinical Assessment'
        CULTURE_FIT = 'culture_fit', 'Culture Fit'
        CUSTOM      = 'custom',      'Custom'

    # Identity
    title        = models.CharField(max_length=255)
    category     = models.CharField(max_length=100, default='technical')
    sector       = models.CharField(max_length=20, choices=SectorType.choices, default=SectorType.BOTH)
    description  = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text='Candidate-facing instructions.')

    # Scoring blueprint -- JSON list of {criterion, max_points, description}
    marks_distribution = models.JSONField(
        default=list,
        help_text='Array of {criterion, max_points, description}. Must sum <= 100.'
    )
    total_marks = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    # Requirements that must be present before assigning this template
    prerequisites = models.JSONField(
        default=list,
        help_text='List of prerequisite conditions (plain text).'
    )

    # Allowed validator roles (RoleChoice codes)
    allowed_validator_roles = models.JSONField(
        default=list,
        help_text='List of RoleChoice codes whose holders may act as validators.'
    )

    # Authoring
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='assessment_templates_created'
    )
    is_active = models.BooleanField(default=True)
    version   = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = 'vetting_assessment_template'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} (v{self.version}) [{self.sector}]'


# ---------------------------------------------------------------------------
# 2. ApplicationVetting  (per-application assignment)
# ---------------------------------------------------------------------------

class ApplicationVetting(BaseModel):
    """
    Links one Application to one AssessmentTemplate for a specific vetting round.
    Created by a recruiter when moving application from Stage 2 to Stage 3.
    """

    class Status(models.TextChoices):
        PENDING     = 'pending',     'Pending Start'
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED   = 'submitted',   'Answers Submitted'
        SCORED      = 'scored',      'Scored by Primary Validator'
        PASSED      = 'passed',      'Passed'
        FAILED      = 'failed',      'Failed'
        EXPIRED     = 'expired',     'Expired'

    application = models.ForeignKey(
        'ats.Application', on_delete=models.CASCADE, related_name='vettings'
    )
    template = models.ForeignKey(
        AssessmentTemplate, on_delete=models.PROTECT, related_name='vettings'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Timing window
    scheduled_start = models.DateTimeField(null=True, blank=True)
    deadline        = models.DateTimeField(null=True, blank=True)
    started_at      = models.DateTimeField(null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)

    # Validators
    primary_validator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='primary_vettings',
        help_text='Only this user can set the final score.'
    )
    secondary_validators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True, related_name='secondary_vettings',
        help_text='Supporting validators who may submit review notes.'
    )

    # Who assigned this vetting
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='vettings_assigned'
    )

    # Recruiter notes visible to validators
    recruiter_notes = models.TextField(blank=True)

    # Final outcome fields (populated once scored)
    final_score    = models.PositiveSmallIntegerField(null=True, blank=True)
    pass_threshold = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Minimum score to auto-mark as Passed.'
    )
    decision_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'vetting_application_vetting'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application', 'status']),
            models.Index(fields=['primary_validator', 'status']),
        ]

    def __str__(self):
        return f'Vetting({self.application_id}) [{self.status}]'

    @property
    def is_overdue(self) -> bool:
        from django.utils import timezone
        return bool(
            self.deadline and
            timezone.now() > self.deadline and
            self.status not in (
                self.Status.SCORED, self.Status.PASSED,
                self.Status.FAILED, self.Status.EXPIRED
            )
        )


# ---------------------------------------------------------------------------
# 3. VettingAnswer  (candidate artefacts / validator submissions)
# ---------------------------------------------------------------------------

class VettingAnswer(BaseModel):
    """
    Validator or recruiter records candidate responses / artefacts.
    Multiple answers per vetting allowed (one per criterion or partial saves).
    """

    vetting = models.ForeignKey(
        ApplicationVetting, on_delete=models.CASCADE, related_name='answers'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='vetting_answers_submitted'
    )

    # Criterion-level scoring: [{criterion, awarded_points, max_points, notes}]
    criterion_scores = models.JSONField(
        default=list,
        help_text='Array matching template marks_distribution.'
    )

    # Free-text overall notes from this validator
    notes = models.TextField(blank=True)

    # File attachments (S3 keys / URLs)
    # e.g. [{"label": "Repo Screenshot", "key": "s3://...", "content_type": "image/png"}]
    attachments = models.JSONField(default=list)

    # Candidate-submitted artefacts
    candidate_submission_url = models.URLField(blank=True)
    candidate_notes          = models.TextField(blank=True)

    # Subtotal computed by validator for their section
    subtotal_score = models.PositiveSmallIntegerField(null=True, blank=True)

    is_final_submission = models.BooleanField(
        default=False,
        help_text='True when validator marks this as their complete evaluation.'
    )

    class Meta:
        db_table = 'vetting_answer'
        ordering = ['-created_at']

    def __str__(self):
        return f'Answer({self.vetting_id}) by {self.submitted_by_id}'


# ---------------------------------------------------------------------------
# 4. VettingScore  (primary validator final verdict)
# ---------------------------------------------------------------------------

class VettingScore(BaseModel):
    """
    Immutable final score record, set exclusively by the primary validator.
    Creating this record triggers status update on ApplicationVetting.
    """

    vetting   = models.OneToOneField(
        ApplicationVetting, on_delete=models.CASCADE, related_name='score_record'
    )
    scored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name='vetting_scores_given'
    )
    score    = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    verdict  = models.CharField(max_length=10, choices=[('pass', 'Pass'), ('fail', 'Fail')])
    feedback = models.TextField(blank=True, help_text='Detailed feedback sent to recruiter.')
    scored_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vetting_score'

    def __str__(self):
        return f'Score {self.score}/100 ({self.verdict}) for Vetting {self.vetting_id}'

    def save(self, *args, **kwargs):
        """Auto-update parent vetting status and final_score on creation."""
        super().save(*args, **kwargs)
        vetting = self.vetting
        vetting.final_score = self.score
        vetting.status = (
            ApplicationVetting.Status.PASSED
            if self.score >= vetting.pass_threshold
            else ApplicationVetting.Status.FAILED
        )
        vetting.save(update_fields=['final_score', 'status', 'updated_at'])


# ---------------------------------------------------------------------------
# 5. Credential  (unchanged -- healthcare licence tracking)
# ---------------------------------------------------------------------------

class CredentialStatus(models.TextChoices):
    UNVERIFIED = 'unverified', 'Unverified'
    VERIFIED   = 'verified',   'Verified'
    REJECTED   = 'rejected',   'Rejected'
    EXPIRED    = 'expired',    'Expired'


class Credential(BaseModel):
    """
    Healthcare professional license or certification.
    Candidates submit at intake. Credential Officers verify (D-02).
    License number encrypted at rest.
    """
    class Kind(models.TextChoices):
        LICENSE       = 'license',       'Professional License'
        CERTIFICATION = 'certification', 'Certification'

    candidate      = models.ForeignKey(
        'candidates.Candidate', on_delete=models.CASCADE, related_name='credentials'
    )
    kind           = models.CharField(max_length=20, choices=Kind.choices)
    name           = models.CharField(max_length=255)
    license_number = EncryptedCharField(max_length=100, blank=True)  # PII
    jurisdiction   = models.CharField(max_length=100, blank=True)
    issued_on      = models.DateField(null=True, blank=True)
    expires_on     = models.DateField(null=True, blank=True, db_index=True)
    status         = models.CharField(
        max_length=20, choices=CredentialStatus.choices, default=CredentialStatus.UNVERIFIED
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='verified_credentials'
    )
    verified_at         = models.DateTimeField(null=True, blank=True)
    verification_method = models.CharField(max_length=100, blank=True)
    rejection_reason    = models.TextField(blank=True)
    evidence_document   = models.ForeignKey(
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


# ---------------------------------------------------------------------------
# 6. ValidatorProfile (Tech & Healthcare Validator Profiles)
# ---------------------------------------------------------------------------

class ValidatorSector(models.TextChoices):
    TECHNOLOGY   = 'technology',   'Technology'
    HEALTHCARE   = 'healthcare',   'Healthcare'
    CROSS_SECTOR = 'cross_sector', 'Cross-Sector'


class ValidatorClearance(models.TextChoices):
    LEVEL_1 = 'level_1', 'Level 1: Associate Assessor'
    LEVEL_2 = 'level_2', 'Level 2: Senior Validator'
    LEVEL_3 = 'level_3', 'Level 3: Lead Specialist / Credential Officer'


class ValidatorProfile(BaseModel):
    """
    Staff profile for users holding TECH_VALIDATOR or CREDENTIAL_OFFICER roles.
    Defines sector specialization, clearance level, concurrent limits,
    and review performance metrics.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='validator_profile'
    )
    sector = models.CharField(
        max_length=20, choices=ValidatorSector.choices, default=ValidatorSector.TECHNOLOGY
    )
    specialization = models.CharField(
        max_length=150, default='Distributed Systems & Architecture',
        help_text='Domain focus from choice matrix'
    )
    clearance_level = models.CharField(
        max_length=20, choices=ValidatorClearance.choices, default=ValidatorClearance.LEVEL_2
    )
    max_active_assignments = models.PositiveSmallIntegerField(default=5)
    total_evaluations_completed = models.PositiveIntegerField(default=0)
    average_scoring_turnaround_hours = models.FloatField(default=12.0)
    is_active = models.BooleanField(default=True)
    bio = models.TextField(blank=True)

    class Meta:
        db_table = 'vetting_validator_profile'
        ordering = ['user__email']

    def __str__(self):
        return f'{self.user.email} [{self.sector.upper()} - {self.clearance_level}]'

