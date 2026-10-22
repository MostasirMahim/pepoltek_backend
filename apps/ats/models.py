"""
ats/models.py
Internal recruitment workspace models.
Client, Requisition, Application pipeline, Submission, Interview, Placement.
No client logins in MVP - clients are internal entities managed by Pepoltek staff (D-01).
"""
from django.db import models
from django.conf import settings
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
    # embedding = VectorField(dimensions=1536, null=True)  # Phase 2 - pgvector

    class Meta:
        db_table = 'ats_requisition'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'visibility']),
            models.Index(fields=['sector', 'level']),
        ]

    def __str__(self):
        return f'{self.title} ({self.client.name})'


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
