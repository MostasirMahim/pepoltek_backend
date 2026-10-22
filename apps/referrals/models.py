"""
referrals/models.py
Referral system: unique codes (on User), attribution tracking, double-entry ledger.
Every registered user is automatically a REFERRER (D-03).
Self-referral is blocked in attribution logic.

Bounty Rules:
- Not every job post is bounty-able. Recruiter opts in by selecting a BountyType when publishing.
- BountyType catalog is admin-managed (name, price, validity_days).
- GENERAL_CANDIDATE scope: earns only the FIRST job bounty after placement (bounty_locked prevents repeat).
- SPECIFIC_JOB scope: earns bounty ONLY if placed in the exact requisition linked at referral time.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class ReferralType(models.TextChoices):
    CANDIDATE = 'candidate', 'Candidate Referral'
    CLIENT_LEAD = 'client_lead', 'Client Lead Referral'


class ReferralStage(models.TextChoices):
    SUBMITTED = 'submitted', 'Submitted'
    SCREENED = 'screened', 'Screened'
    INTERVIEWED = 'interviewed', 'Interviewed'
    PLACED = 'placed', 'Placed'
    REJECTED = 'rejected', 'Rejected'
    DUPLICATE = 'duplicate', 'Duplicate'
    # Client referral stages
    CONTACTED = 'contacted', 'Client Contacted'
    QUALIFIED = 'qualified', 'Client Qualified'
    CONTRACT_SIGNED = 'contract_signed', 'Contract Signed'
    LOST = 'lost', 'Lost'


class ReferralSource(models.TextChoices):
    LINK = 'link', 'Referral Link (/r/{code})'
    DIRECT = 'direct', 'Direct Submission'


class ReferralScope(models.TextChoices):
    GENERAL_CANDIDATE = 'general', 'General Candidate Invite'
    SPECIFIC_JOB = 'specific_job', 'Specific Job Referral'


class BountyType(BaseModel):
    """
    Admin-managed catalog of structured bounty reward tiers.
    Recruiters attach one BountyType to a Requisition when publishing a bounty-enabled job.
    Defines the bounty name, payout amount, and validity window.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    validity_days = models.PositiveIntegerField(
        default=90,
        help_text='Days from referral date within which placement must occur to earn this bounty.'
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'referrals_bounty_type'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f'{self.name} ({self.currency} {self.amount})'


class Referral(BaseModel):
    """
    One row per referral event.
    For candidate referrals: candidate field is set after they accept the invite.
    For client referrals: lead field is set when the lead is created.

    Scope rules enforced in services.py:
    - GENERAL_CANDIDATE: earns only the first job bounty (bounty_locked=True after first mint).
    - SPECIFIC_JOB: earns bounty only if placed in the exact linked requisition.
    """
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_made'
    )
    referral_type = models.CharField(max_length=20, choices=ReferralType.choices)
    source = models.CharField(max_length=10, choices=ReferralSource.choices)
    stage = models.CharField(max_length=20, choices=ReferralStage.choices, default=ReferralStage.SUBMITTED)
    referral_scope = models.CharField(
        max_length=20,
        choices=ReferralScope.choices,
        default=ReferralScope.GENERAL_CANDIDATE,
        help_text='General invite = first placement bounty only. Specific job = only that job bounty.'
    )
    bounty_locked = models.BooleanField(
        default=False,
        help_text='True after first bounty minted for general-scope referrals. Prevents double-earning.'
    )

    # One of these is set depending on referral_type
    candidate = models.ForeignKey(
        'candidates.Candidate', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referrals'
    )
    lead = models.ForeignKey(
        'leads.Lead', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referrals'
    )
    requisition = models.ForeignKey(
        'ats.Requisition', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referrals'
    )

    # Direct submission fields (before candidate creates account)
    referred_name = models.CharField(max_length=255, blank=True)
    referred_email = models.EmailField(blank=True)

    class Meta:
        db_table = 'referrals_referral'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.referrer.email} referred {self.referral_type} [{self.stage}] scope={self.referral_scope}'


class PayoutStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    PAID = 'paid', 'Paid'
    CANCELLED = 'cancelled', 'Cancelled'


class LedgerEntry(models.Model):
    """
    Double-entry style immutable payout ledger.
    Never update a row - corrections are made by creating a reversing entry.
    Admin approval required before Paid. Payment reference required to mark Paid.
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ledger_entries'
    )
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name='ledger_entries')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    milestone = models.CharField(max_length=50)  # e.g. 'placed', '90d_guarantee_passed'
    bounty_type = models.ForeignKey(
        BountyType, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ledger_entries',
        help_text='The BountyType catalog entry that determined this payout amount.'
    )
    status = models.CharField(max_length=20, choices=PayoutStatus.choices, default=PayoutStatus.PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_reference = models.CharField(max_length=255, blank=True)  # external payment ID
    paid_at = models.DateTimeField(null=True, blank=True)
    reverses_entry = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = 'referrals_ledger_entry'
        ordering = ['-created_at']

    def __str__(self):
        return f'Ledger({self.user.email} {self.amount}{self.currency}) - {self.status}'
