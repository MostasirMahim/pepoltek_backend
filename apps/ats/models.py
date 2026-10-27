"""
ats/models.py
Internal recruitment workspace models.
Client, Requisition, Application pipeline, Submission, Interview, Placement.
No client logins in MVP - clients are internal entities managed by Pepoltek staff (D-01).
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from encrypted_model_fields.fields import EncryptedCharField, EncryptedEmailField


class DeliveryChannel(models.TextChoices):
    EMAIL = 'email', 'Email'
    IM = 'im', 'Instant Messaging'
    CLIENT_ATS = 'client_ats', 'Client ATS Upload'
    PORTAL = 'portal', 'Client Portal (Post-GTM)'


class Client(BaseModel):
    """Hiring organisation. Staff-managed. No login in MVP."""
    name = models.CharField(max_length=255)
    sector = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    terms = models.JSONField(default=dict, blank=True)  # engagement terms
    delivery_channel = models.CharField(
        max_length=20, choices=DeliveryChannel.choices, default=DeliveryChannel.EMAIL
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='owned_clients'
    )

    class Meta:
        db_table = 'ats_client'
        ordering = ['name']

    def __str__(self):
        return self.name


class ClientContact(BaseModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts')
    full_name = models.CharField(max_length=255)
    email = EncryptedEmailField()
    phone = EncryptedCharField(max_length=30, blank=True)
    role_title = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'ats_client_contact'

    def __str__(self):
        return f'{self.full_name} @ {self.client.name}'


class RequisitionVisibility(models.TextChoices):
    PRIVATE = 'private', 'Private (Internal Only)'
    PUBLISHED_JOB = 'published_job', 'Published Job'
    PUBLISHED_GIG = 'published_gig', 'Published Gig'
    BOUNTY = 'bounty', 'Bounty Job'


class RequisitionStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    OPEN = 'open', 'Open'
    ON_HOLD = 'on_hold', 'On Hold'
    FILLED = 'filled', 'Filled'
    CANCELLED = 'cancelled', 'Cancelled'


class Requisition(BaseModel):
    """A client hiring need. Can be private or public (job/gig/bounty)."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='requisitions')
    title = models.CharField(max_length=255)
    sector = models.CharField(max_length=20)
    level = models.CharField(max_length=30, blank=True)
    headcount = models.PositiveSmallIntegerField(default=1)
    skills = models.JSONField(default=list)  # list of skill names (taxonomy-mapped later)
    must_haves = models.JSONField(default=dict)  # hard filter requirements
    engagement = models.CharField(max_length=30, blank=True)
    visa_requirements = models.JSONField(default=list)
    timezone = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255, blank=True)
    budget_min = models.PositiveIntegerField(null=True, blank=True)
    budget_max = models.PositiveIntegerField(null=True, blank=True)
    visibility = models.CharField(
        max_length=20, choices=RequisitionVisibility.choices, default=RequisitionVisibility.PRIVATE
    )
    # --- Bounty System ---
    bounty_enabled = models.BooleanField(
        default=False,
        help_text='Recruiter opts in to enable referral bounty for this job post.'
    )
    bounty_type = models.ForeignKey(
        'referrals.BountyType', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='requisitions',
        help_text='Structured bounty type (name, amount, validity) selected by recruiter.'
    )
    bounty_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='[LEGACY] Flat bounty amount. Use bounty_type instead for new records.'
    )
    # ---------------------
    status = models.CharField(
        max_length=20, choices=RequisitionStatus.choices, default=RequisitionStatus.DRAFT
    )
    priority = models.PositiveSmallIntegerField(default=3)  # 1=urgent, 5=low
    discovery = models.JSONField(default=dict, blank=True)  # discovery profile (BA-owned)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='owned_requisitions'
    )
    embedding = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'ats_requisition'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'visibility']),
            models.Index(fields=['sector', 'level']),
        ]

    def __str__(self):
        return f'{self.title} ({self.client.name})'

    def generate_embedding_vector(self) -> list[float]:
        try:
            from apps.ai_service.services import generate_candidate_embedding
            text_parts = [
                f"Title: {self.title}",
                f"Sector: {self.sector}",
                f"Level: {self.level}",
                f"Skills: {', '.join(self.skills) if isinstance(self.skills, list) else ''}",
                f"Engagement: {self.engagement}",
                f"Location: {self.location}",
                f"Description: {self.description[:1000]}",
            ]
            if isinstance(self.discovery, dict):
                reqs = self.discovery.get('requirements', [])
                if reqs:
                    text_parts.append(f"Requirements: {', '.join(reqs) if isinstance(reqs, list) else str(reqs)}")
            full_text = " ".join(text_parts)
            return generate_candidate_embedding(full_text)
        except Exception:
            return [0.0] * 1536

    def save(self, *args, **kwargs):
        if not self.embedding:
            try:
                self.embedding = self.generate_embedding_vector()
            except Exception:
                pass
        super().save(*args, **kwargs)



class ApplicationStage(models.TextChoices):
    DISCOVERY = 'discovery', '1 - Discovery'
    MARKET_MAPPING = 'market_mapping', '2 - Market Mapping'
    TECHNICAL_VETTING = 'technical_vetting', '3 - Technical Vetting'
    INTERVIEW = 'interview', '4 - Client Interview'
    CLOSED = 'closed', '5 - Closed / Integrated'
    REJECTED = 'rejected', 'Rejected'
    WITHDRAWN = 'withdrawn', 'Withdrawn'


class ApplicationSource(models.TextChoices):
    APPLIED = 'applied', 'Candidate Applied'
    SOURCED = 'sourced', 'Sourced by Recruiter'
    REVERSE = 'reverse', 'Reverse Search'
    REFERRAL = 'referral', 'Referral'


class Application(BaseModel):
    """One candidate + one requisition = one Application. Pipeline tracked here."""
    candidate = models.ForeignKey(
        'candidates.Candidate', on_delete=models.CASCADE, related_name='applications'
    )
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='applications')
    stage = models.CharField(
        max_length=30, choices=ApplicationStage.choices, default=ApplicationStage.MARKET_MAPPING
    )
    sub_stage = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=20, choices=ApplicationSource.choices)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='owned_applications'
    )

    class Meta:
        db_table = 'ats_application'
        unique_together = [('candidate', 'requisition')]
        indexes = [
            models.Index(fields=['stage']),
            models.Index(fields=['requisition', 'stage']),
        ]

    def __str__(self):
        return f'{self.candidate} → {self.requisition} [{self.stage}]'


class ApplicationEvent(models.Model):
    """Append-only log of every pipeline stage move."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='events')
    from_stage = models.CharField(max_length=30, blank=True)
    to_stage = models.CharField(max_length=30)
    sub_stage = models.CharField(max_length=50, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    note = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ats_application_event'
        ordering = ['timestamp']


class Submission(BaseModel):
    """A recruiter-built shortlist package sent to a client."""
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='submissions')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='submissions'
    )
    channel = models.CharField(max_length=20, choices=DeliveryChannel.choices)
    sent_at = models.DateTimeField(null=True, blank=True)
    export_document_key = models.CharField(max_length=500, blank=True)  # S3 key
    items = models.JSONField(default=list)  # [{application_id, notes, revealed_fields}]

    class Meta:
        db_table = 'ats_submission'
        ordering = ['-created_at']


class Placement(BaseModel):
    """Successful hire record with guarantee tracking."""
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='placement')
    start_date = models.DateField()
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    guarantee_until = models.DateField(null=True, blank=True)  # 90-day guarantee
    checkins = models.JSONField(default=dict)  # 30/60/90-day check-in status

    class Meta:
        db_table = 'ats_placement'


class InterviewType(models.TextChoices):
    TECHNICAL_CODING = 'technical_coding', 'Technical Coding'
    SYSTEM_DESIGN = 'system_design', 'System Design'
    CLINICAL_BOARD = 'clinical_board', 'Clinical Board'
    BEHAVIORAL_LEADERSHIP = 'behavioral_leadership', 'Behavioral & Leadership'
    CLIENT_FINAL = 'client_final', 'Client Final Round'


class InterviewStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    CONFIRMED = 'confirmed', 'Confirmed'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    RESCHEDULED = 'rescheduled', 'Rescheduled'
    CANCELLED = 'cancelled', 'Cancelled'
    NO_SHOW = 'no_show', 'No Show'


class PanelRole(models.TextChoices):
    LEAD_INTERVIEWER = 'lead_interviewer', 'Lead Interviewer'
    TECHNICAL_ASSESSOR = 'technical_assessor', 'Technical Assessor'
    CLINICAL_VALIDATOR = 'clinical_validator', 'Clinical Validator'
    CLIENT_OBSERVER = 'client_observer', 'Client Observer'


class RecommendationChoice(models.TextChoices):
    STRONG_HIRE = 'strong_hire', 'Strong Hire'
    HIRE = 'hire', 'Hire'
    NEUTRAL = 'neutral', 'Neutral'
    DO_NOT_HIRE = 'do_not_hire', 'Do Not Hire'


class Interview(BaseModel):
    """
    RPO Technical and Client Interview session.
    Belongs to an Application in the ATS pipeline.
    """
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='interviews'
    )
    title = models.CharField(max_length=255)
    interview_type = models.CharField(
        max_length=60, choices=InterviewType.choices, default=InterviewType.TECHNICAL_CODING
    )
    round_number = models.PositiveSmallIntegerField(default=1)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    timezone = models.CharField(max_length=50, default='UTC')
    meeting_link = models.URLField(max_length=500, blank=True)
    status = models.CharField(
        max_length=25, choices=InterviewStatus.choices, default=InterviewStatus.SCHEDULED
    )
    lead_interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='led_interviews'
    )
    panel_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='InterviewPanelAssignment', related_name='panel_interviews', blank=True
    )
    candidate_notes = models.TextField(blank=True)
    internal_brief = models.TextField(blank=True)
    reminder_24h_dispatched = models.BooleanField(default=False)
    reminder_24h_dispatched_at = models.DateTimeField(null=True, blank=True)
    reminder_1h_dispatched = models.BooleanField(default=False)

    class Meta:
        db_table = 'ats_interview'
        ordering = ['scheduled_start']
        indexes = [
            models.Index(fields=['status', 'scheduled_start']),
            models.Index(fields=['reminder_24h_dispatched', 'scheduled_start']),
        ]

    def __str__(self):
        return f'{self.title} ({self.application.candidate}) - {self.status}'


class InterviewPanelAssignment(BaseModel):
    """
    Associates staff users with an interview and records their role and confirmation.
    """
    interview = models.ForeignKey(
        Interview, on_delete=models.CASCADE, related_name='assignments'
    )
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interview_assignments'
    )
    role = models.CharField(
        max_length=30, choices=PanelRole.choices, default=PanelRole.TECHNICAL_ASSESSOR
    )
    has_confirmed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'ats_interview_panel_assignment'
        unique_together = [('interview', 'staff_user')]

    def __str__(self):
        user_display = self.staff_user.get_full_name() or self.staff_user.email
        return f'{user_display} -> {self.interview.title} ({self.role})'


class InterviewEvaluation(BaseModel):
    """
    Formal scorecard submitted by an interview panelist.
    """
    interview = models.ForeignKey(
        Interview, on_delete=models.CASCADE, related_name='evaluations'
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_evaluations'
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    recommendation = models.CharField(
        max_length=20, choices=RecommendationChoice.choices
    )
    competency_scores = models.JSONField(default=list, blank=True)
    feedback = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ats_interview_evaluation'
        unique_together = [('interview', 'evaluator')]
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Evaluation for {self.interview.title} by {self.evaluator.email}: {self.score} ({self.recommendation})'

