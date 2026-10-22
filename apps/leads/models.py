"""
leads/models.py
Inbound client leads from /hire and /contact forms.
Lead funnel: new → contacted → discovery_booked → qualified → converted | lost
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
    QUALIFIED = 'qualified', 'Qualified'
    CONVERTED = 'converted', 'Converted to Client'
    LOST = 'lost', 'Lost'


class SectorChoice(models.TextChoices):
    TECHNOLOGY = 'technology', 'Technology'
    HEALTHCARE = 'healthcare', 'Healthcare'
    BOTH = 'both', 'Both'


class Lead(BaseModel):
    source = models.CharField(max_length=30, choices=LeadSource.choices)
    status = models.CharField(max_length=30, choices=LeadStatus.choices, default=LeadStatus.NEW)

    # Contact info (PII - encrypted at rest)
    contact_name = EncryptedCharField(max_length=255)
    work_email = EncryptedEmailField()
    company = models.CharField(max_length=255)
    phone = EncryptedCharField(max_length=30, blank=True)

    # Needs
    sector = models.CharField(max_length=20, choices=SectorChoice.choices, blank=True)
    roles_needed = models.TextField(blank=True)
    headcount = models.PositiveSmallIntegerField(null=True, blank=True)
    engagement_model = models.CharField(max_length=50, blank=True)  # direct_hire, staff_aug, eor
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
    booking_data = models.JSONField(null=True, blank=True)  # Cal.com booking details
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
        return f'{self.company} - {self.status}'
