"""
leads/models.py
Inbound client leads from /hire, "I want to hire fast" modal, and calculator forms,
plus general contact inquiries from /contact.
Lead funnel: new -> contacted -> discovery_booked -> discovery_running -> qualified -> converted | lost
On conversion: creates Client + first Requisition in ATS.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from encrypted_model_fields.fields import EncryptedCharField, EncryptedEmailField


class LeadSource(models.TextChoices):
    HIRE_FORM = 'hire_form', 'Hire Fast Form'
    CONTACT_FORM = 'contact_form', 'Contact Form'
    CALCULATOR = 'calculator', 'Hiring Calculator'
    REFERRAL = 'referral', 'Referral'
    DIRECT = 'direct', 'Direct Outreach'


class LeadStatus(models.TextChoices):
    NEW = 'new', 'New'
    CONTACTED = 'contacted', 'Contacted'
    DISCOVERY_BOOKED = 'discovery_booked', 'Discovery Booked'
    DISCOVERY_RUNNING = 'discovery_running', 'Discovery Running'
    QUALIFIED = 'qualified', 'Qualified'
    CONVERTED = 'converted', 'Converted to Client'
    LOST = 'lost', 'Lost'


class SectorChoice(models.TextChoices):
    TECHNOLOGY = 'technology', 'Technology'
    HEALTHCARE = 'healthcare', 'Healthcare'
    BOTH = 'both', 'Both'


class EngagementModelChoice(models.TextChoices):
    STAFF_AUG = 'staff_aug', 'Staff Augmentation'
    DEDICATED_POD = 'dedicated_pod', 'Dedicated Engineering Squad'
    DIRECT_HIRE = 'direct_hire', 'Direct Hire Placement'
    EOR = 'eor', 'Employer of Record (EOR)'


class TimelineChoice(models.TextChoices):
    IMMEDIATE = 'immediate', 'Immediate (Within 7 Days)'
    TWO_WEEKS = 'two_weeks', '2 Weeks'
    ONE_MONTH = 'one_month', '1 Month'
    FLEXIBLE = 'flexible', 'Flexible'


class Lead(BaseModel):
    source = models.CharField(max_length=30, choices=LeadSource.choices, default=LeadSource.HIRE_FORM)
    status = models.CharField(max_length=30, choices=LeadStatus.choices, default=LeadStatus.NEW)

    # Contact info (PII - encrypted at rest)
    contact_name = EncryptedCharField(max_length=255)
    work_email = EncryptedEmailField()
    company = models.CharField(max_length=255)
    phone = EncryptedCharField(max_length=50, blank=True)

    # Needs
    sector = models.CharField(max_length=20, choices=SectorChoice.choices, blank=True, default=SectorChoice.TECHNOLOGY)
    roles_needed = models.TextField(blank=True)
    headcount = models.PositiveSmallIntegerField(default=1)
    engagement_model = models.CharField(max_length=50, blank=True, default='staff_aug')
    timeline = models.CharField(max_length=30, choices=TimelineChoice.choices, default=TimelineChoice.IMMEDIATE)
    estimated_budget = models.CharField(max_length=100, blank=True)
    preferred_delivery_channel = models.CharField(max_length=30, blank=True, default='email')
    start_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Attribution
    utm = models.JSONField(default=dict, blank=True)
    calculator_snapshot = models.JSONField(null=True, blank=True)
    referral_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referred_leads'
    )

    # Ownership & Booking
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='owned_leads'
    )
    booking_data = models.JSONField(null=True, blank=True)  # Consultation slot
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_client = models.ForeignKey(
        'ats.Client', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='source_lead'
    )

    # Spam protection
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        db_table = 'leads_lead'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['owner']),
        ]

    def __str__(self):
        return f'{self.company} ({self.contact_name}) - {self.status}'


class LeadActivityLog(BaseModel):
    """
    Append-only audit trail of staff actions, status updates, and internal notes on a lead.
    """
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    action = models.CharField(max_length=50)  # status_change, owner_assigned, note_added, converted
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = 'leads_activity_log'
        ordering = ['-created_at']

    def __str__(self):
        actor_name = self.actor.get_full_name() or self.actor.email if self.actor else 'System'
        return f'{actor_name} on {self.lead.company}: {self.action}'


class ContactCategory(models.TextChoices):
    GENERAL = 'general', 'General Inquiry'
    PARTNERSHIP = 'partnership', 'Strategic Partnership'
    TALENT_SUPPORT = 'talent_support', 'Talent & Candidate Support'
    PRESS_MEDIA = 'press_media', 'Press & Media'
    FEEDBACK = 'feedback', 'Platform Feedback'


class ContactStatus(models.TextChoices):
    NEW = 'new', 'New'
    IN_PROGRESS = 'in_progress', 'In Progress'
    RESPONDED = 'responded', 'Responded'
    CLOSED = 'closed', 'Closed'


class ContactInquiry(BaseModel):
    """
    General inbound contact inquiries from /contact.
    Separated from commercial employer hiring leads.
    """
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=30, choices=ContactCategory.choices, default=ContactCategory.GENERAL)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=30, choices=ContactStatus.choices, default=ContactStatus.NEW)
    responder = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='handled_inquiries'
    )
    response_notes = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'leads_contact_inquiry'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f'{self.name} [{self.category}]: {self.subject} ({self.status})'
