"""
referrals/services.py
Business transactions for referral tracking and immutable double-entry payout ledgers.

Bounty Scope Rules (enforced here):
- GENERAL_CANDIDATE scope: earns only the FIRST job bounty after placement.
  bounty_locked=True is set after first mint; subsequent placements do NOT earn another bounty.
- SPECIFIC_JOB scope: earns bounty ONLY if the placed requisition matches the referral's
  linked requisition. Placing the same candidate on a different job yields no bounty.
- Bounty amount is read from requisition.bounty_type.amount (structured catalog).
  Falls back to requisition.bounty_amount (legacy flat field), then DEFAULT_BOUNTY_AMOUNT.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound

from apps.audit.models import AuditLog
from apps.audit.services import record as record_audit
from .models import (
    Referral, LedgerEntry, PayoutStatus, ReferralType,
    ReferralStage, ReferralSource, ReferralScope, BountyType,
)

DEFAULT_BOUNTY_AMOUNT = Decimal('1500.00')


def _resolve_bounty_amount_and_type(referral, bounty_amount_override=None):
    """
    Resolve the bounty amount and BountyType for a placement event.
    Priority: explicit override > requisition.bounty_type > requisition.bounty_amount (legacy) > DEFAULT.
    Returns (amount: Decimal, bounty_type_instance: BountyType | None)
    """
    if bounty_amount_override and bounty_amount_override > 0:
        return bounty_amount_override, None

    req = referral.requisition
    if req and req.bounty_type_id and req.bounty_enabled:
        bt = req.bounty_type
        if bt:
            return bt.amount, bt

    if req and req.bounty_amount and req.bounty_amount > 0:
        return req.bounty_amount, None

    return DEFAULT_BOUNTY_AMOUNT, None


def _can_mint_bounty(referral, placement_requisition_id=None) -> tuple[bool, str]:
    """
    Check whether a bounty can be minted for this referral given the scope rules.
    Returns (eligible: bool, reason: str)
    """
    # Must have a bounty-enabled requisition somewhere
    req = referral.requisition
    is_bounty_eligible = (req and req.bounty_enabled and req.bounty_type_id) or (req and req.bounty_amount)

    if referral.referral_scope == ReferralScope.SPECIFIC_JOB:
        # Specific-job scope: only mint if placed in the exact same requisition
        if not req:
            return False, 'Specific-job referral has no linked requisition.'
        if placement_requisition_id and str(req.id) != str(placement_requisition_id):
            return False, 'Specific-job referral: candidate placed in a different requisition. No bounty earned.'
        if not is_bounty_eligible:
            return False, 'Linked requisition is not bounty-enabled.'
        return True, 'ok'

    # GENERAL_CANDIDATE scope: earns only the first job bounty
    if referral.bounty_locked:
        return False, 'General invite: bounty already minted for this referral (first-job rule). Locked.'
    if not is_bounty_eligible:
        return False, 'No bounty-enabled requisition linked to this referral.'
    return True, 'ok'


@transaction.atomic
def approve_payout(*, ledger_entry_id: int, admin_user, request=None) -> LedgerEntry:
    """
    Approve a pending payout in the escrow ledger.
    """
    entry = LedgerEntry.objects.select_for_update().filter(id=ledger_entry_id).first()
    if not entry:
        raise NotFound("Ledger entry not found.")

    if entry.status == PayoutStatus.PAID:
        raise ValidationError("This payout has already been paid and cleared.")

    before_state = {'status': entry.status}
    entry.status = PayoutStatus.APPROVED
    entry.approved_by = admin_user
    entry.approved_at = timezone.now()
    entry.save(update_fields=['status', 'approved_by', 'approved_at'])

    record_audit(
        action=AuditLog.Action.PAYOUT_APPROVED,
        entity='LedgerEntry',
        entity_id=entry.id,
        actor=admin_user,
        before=before_state,
        after={'status': entry.status, 'approved_by': admin_user.email},
        extra={'amount': str(entry.amount), 'currency': entry.currency},
        request=request,
    )
    return entry


@transaction.atomic
def disburse_payout(
    *,
    ledger_entry_id: int,
    admin_user,
    paid_reference: str,
    payment_method: str = 'bank_wire',
    note: str = '',
    request=None
) -> LedgerEntry:
    """
    Mark an approved payout as Paid with an external transaction reference string.
    """
    if not paid_reference or not paid_reference.strip():
        raise ValidationError("External transaction/wire reference is required to disburse funds.")

    entry = LedgerEntry.objects.select_for_update().filter(id=ledger_entry_id).first()
    if not entry:
        raise NotFound("Ledger entry not found.")

    if entry.status == PayoutStatus.PAID:
        raise ValidationError("This payout has already been marked as Paid.")

    before_state = {'status': entry.status, 'paid_reference': entry.paid_reference}
    entry.status = PayoutStatus.PAID
    entry.paid_reference = paid_reference.strip()
    entry.paid_at = timezone.now()
    if not entry.approved_by:
        entry.approved_by = admin_user
        entry.approved_at = timezone.now()
    if note:
        entry.note = f"{entry.note} | Disbursed via {payment_method}: {note}".strip(" |")
    else:
        entry.note = f"{entry.note} | Disbursed via {payment_method}".strip(" |")

    entry.save(update_fields=['status', 'paid_reference', 'paid_at', 'approved_by', 'approved_at', 'note'])

    record_audit(
        action=AuditLog.Action.PAYOUT_PAID,
        entity='LedgerEntry',
        entity_id=entry.id,
        actor=admin_user,
        before=before_state,
        after={
            'status': entry.status,
            'paid_reference': entry.paid_reference,
            'paid_at': entry.paid_at.isoformat(),
        },
        extra={'amount': str(entry.amount), 'payment_method': payment_method},
        request=request,
    )
    return entry


@transaction.atomic
def cancel_payout(*, ledger_entry_id: int, admin_user, reason: str, request=None) -> LedgerEntry:
    """
    Cancel a pending or approved payout entry with an audit reason.
    """
    entry = LedgerEntry.objects.select_for_update().filter(id=ledger_entry_id).first()
    if not entry:
        raise NotFound("Ledger entry not found.")

    if entry.status == PayoutStatus.PAID:
        raise ValidationError("Cannot cancel a payout that has already been cleared and paid. Issue a reversing entry instead.")

    before_state = {'status': entry.status}
    entry.status = PayoutStatus.CANCELLED
    entry.note = f"{entry.note} | Cancelled by {admin_user.email}: {reason}".strip(" |")
    entry.save(update_fields=['status', 'note'])

    record_audit(
        action=AuditLog.Action.PAYOUT_CANCELLED,
        entity='LedgerEntry',
        entity_id=entry.id,
        actor=admin_user,
        before=before_state,
        after={'status': entry.status, 'reason': reason},
        extra={'amount': str(entry.amount)},
        request=request,
    )
    return entry


@transaction.atomic
def submit_direct_referral(
    *,
    referrer_user,
    referred_name: str,
    referred_email: str,
    target_role: str = '',
    notes: str = '',
    requisition_id: str = None,
    request=None
) -> Referral:
    """
    Direct candidate referral submitted by an authenticated user (REF-03).
    Self-referral is strictly prevented.
    If requisition_id is provided, scope is set to SPECIFIC_JOB.
    Otherwise, scope is GENERAL_CANDIDATE (earns first-job bounty only).
    """
    from apps.ats.models import Requisition

    clean_email = referred_email.strip().lower()
    if clean_email == referrer_user.email.strip().lower():
        raise ValidationError("Self-referral is blocked. You cannot refer your own account.")

    # Check for duplicate pending referral
    existing = Referral.objects.filter(
        referrer=referrer_user,
        referred_email__iexact=clean_email
    ).first()
    if existing:
        return existing

    scope = ReferralScope.GENERAL_CANDIDATE
    linked_req = None
    if requisition_id:
        linked_req = Requisition.objects.filter(id=requisition_id, bounty_enabled=True).first()
        if linked_req:
            scope = ReferralScope.SPECIFIC_JOB

    referral = Referral.objects.create(
        referrer=referrer_user,
        referral_type=ReferralType.CANDIDATE,
        source=ReferralSource.DIRECT,
        stage=ReferralStage.SUBMITTED,
        referral_scope=scope,
        referred_name=referred_name.strip(),
        referred_email=clean_email,
        requisition=linked_req,
    )

    record_audit(
        action=AuditLog.Action.CREATE,
        entity='Referral',
        entity_id=str(referral.id),
        actor=referrer_user,
        after={
            'referred_email': clean_email,
            'stage': referral.stage,
            'scope': scope,
            'requisition_id': str(linked_req.id) if linked_req else None,
        },
        request=request,
    )
    return referral


@transaction.atomic
def admin_update_referral_stage(
    *,
    referral_id: str,
    new_stage: str,
    admin_user,
    bounty_amount: Decimal = None,
    note: str = '',
    placement_requisition_id: str = None,
    request=None
) -> tuple[Referral, LedgerEntry | None]:
    """
    Administrative stage transition for a referral.
    If advanced to 'placed', applies bounty scope rules before minting a LedgerEntry.
    """
    clean_stage = (new_stage or '').strip().lower()
    if clean_stage not in ReferralStage.values:
        raise ValidationError(f"Invalid stage '{new_stage}'. Must be one of: {', '.join(ReferralStage.values)}")

    referral = Referral.objects.select_for_update().filter(id=referral_id).first()
    if not referral:
        raise NotFound("Referral record not found.")

    before_stage = referral.stage
    referral.stage = clean_stage
    referral.save(update_fields=['stage', 'updated_at'])

    record_audit(
        action=AuditLog.Action.UPDATE,
        entity='Referral',
        entity_id=str(referral.id),
        actor=admin_user,
        before={'stage': before_stage},
        after={'stage': referral.stage, 'note': note},
        request=request,
    )

    created_ledger = None
    if clean_stage == ReferralStage.PLACED:
        eligible, reason = _can_mint_bounty(referral, placement_requisition_id)

        if eligible:
            existing_ledger = LedgerEntry.objects.filter(
                referral=referral,
                milestone='placed'
            ).exclude(status=PayoutStatus.CANCELLED).first()

            if not existing_ledger:
                mint_amount, bounty_type_obj = _resolve_bounty_amount_and_type(referral, bounty_amount)
                created_ledger = LedgerEntry.objects.create(
                    user=referral.referrer,
                    referral=referral,
                    amount=mint_amount,
                    currency=bounty_type_obj.currency if bounty_type_obj else 'USD',
                    milestone='placed',
                    bounty_type=bounty_type_obj,
                    status=PayoutStatus.PENDING,
                    note=f"Placement bounty auto-generated on stage change to Placed. Scope: {referral.referral_scope}. {note}".strip(' :')
                )

                # Lock general-scope referrals after first mint
                if referral.referral_scope == ReferralScope.GENERAL_CANDIDATE:
                    referral.bounty_locked = True
                    referral.save(update_fields=['bounty_locked'])

                record_audit(
                    action=AuditLog.Action.CREATE,
                    entity='LedgerEntry',
                    entity_id=created_ledger.id,
                    actor=admin_user,
                    after={
                        'amount': str(mint_amount),
                        'currency': created_ledger.currency,
                        'milestone': 'placed',
                        'status': PayoutStatus.PENDING,
                        'bounty_type': bounty_type_obj.name if bounty_type_obj else 'legacy',
                        'scope': referral.referral_scope,
                        'beneficiary': referral.referrer.email,
                    },
                    request=request,
                )
        else:
            record_audit(
                action=AuditLog.Action.UPDATE,
                entity='Referral',
                entity_id=str(referral.id),
                actor=admin_user,
                after={'bounty_skipped': True, 'reason': reason},
                request=request,
            )

    return referral, created_ledger


@transaction.atomic
def recruiter_update_referral(
    *,
    referral_id: str,
    new_stage: str,
    recruiter_user,
    requisition_id: str = None,
    bounty_amount: Decimal = None,
    note: str = '',
    request=None
) -> tuple[Referral, LedgerEntry | None]:
    """
    Recruiter updates candidate referral stage and/or links to an open Requisition.
    Bounty scope rules apply on placement.
    """
    from apps.ats.models import Requisition

    clean_stage = (new_stage or '').strip().lower()
    if clean_stage not in ReferralStage.values:
        raise ValidationError(f"Invalid stage '{new_stage}'. Must be one of: {', '.join(ReferralStage.values)}")

    referral = Referral.objects.select_for_update().filter(id=referral_id).first()
    if not referral:
        raise NotFound("Referral record not found.")

    before_stage = referral.stage
    before_req = str(referral.requisition_id) if referral.requisition_id else None

    referral.stage = clean_stage
    update_fields = ['stage', 'updated_at']

    if requisition_id:
        req = Requisition.objects.filter(id=requisition_id).first()
        if req:
            referral.requisition = req
            # If a specific job is linked and scope was general, upgrade to specific
            if referral.referral_scope == ReferralScope.GENERAL_CANDIDATE and req.bounty_enabled:
                referral.referral_scope = ReferralScope.SPECIFIC_JOB
                update_fields.append('referral_scope')
            update_fields.append('requisition')

    referral.save(update_fields=update_fields)

    record_audit(
        action=AuditLog.Action.UPDATE,
        entity='Referral',
        entity_id=str(referral.id),
        actor=recruiter_user,
        before={'stage': before_stage, 'requisition': before_req},
        after={
            'stage': referral.stage,
            'requisition': str(referral.requisition_id) if referral.requisition_id else None,
            'scope': referral.referral_scope,
            'note': note,
        },
        request=request,
    )

    created_ledger = None
    if clean_stage == ReferralStage.PLACED:
        placement_req_id = str(referral.requisition_id) if referral.requisition_id else None
        eligible, reason = _can_mint_bounty(referral, placement_req_id)

        if eligible:
            existing_ledger = LedgerEntry.objects.filter(
                referral=referral,
                milestone='placed'
            ).exclude(status=PayoutStatus.CANCELLED).first()

            if not existing_ledger:
                mint_amount, bounty_type_obj = _resolve_bounty_amount_and_type(referral, bounty_amount)
                created_ledger = LedgerEntry.objects.create(
                    user=referral.referrer,
                    referral=referral,
                    amount=mint_amount,
                    currency=bounty_type_obj.currency if bounty_type_obj else 'USD',
                    milestone='placed',
                    bounty_type=bounty_type_obj,
                    status=PayoutStatus.PENDING,
                    note=f"Recruiter placement bounty for {referral.referred_name or 'Candidate'}. Scope: {referral.referral_scope}. {note}".strip(' :')
                )

                # Lock general-scope referrals after first mint
                if referral.referral_scope == ReferralScope.GENERAL_CANDIDATE:
                    referral.bounty_locked = True
                    referral.save(update_fields=['bounty_locked'])

                record_audit(
                    action=AuditLog.Action.CREATE,
                    entity='LedgerEntry',
                    entity_id=created_ledger.id,
                    actor=recruiter_user,
                    after={
                        'amount': str(mint_amount),
                        'currency': created_ledger.currency,
                        'milestone': 'placed',
                        'status': PayoutStatus.PENDING,
                        'bounty_type': bounty_type_obj.name if bounty_type_obj else 'legacy',
                        'scope': referral.referral_scope,
                        'beneficiary': referral.referrer.email,
                    },
                    request=request,
                )

    return referral, created_ledger


@transaction.atomic
def create_bounty_type(
    *,
    name: str,
    amount: Decimal,
    description: str = '',
    currency: str = 'USD',
    validity_days: int = 90,
    sort_order: int = 0,
    admin_user,
    request=None
) -> BountyType:
    """
    Create a new BountyType catalog entry (admin only).
    """
    if not name or not name.strip():
        raise ValidationError("Bounty type name is required.")
    if not amount or amount <= 0:
        raise ValidationError("Bounty amount must be greater than zero.")

    bt = BountyType.objects.create(
        name=name.strip(),
        description=description.strip(),
        amount=amount,
        currency=currency.upper()[:3],
        validity_days=validity_days,
        sort_order=sort_order,
        is_active=True,
    )

    record_audit(
        action=AuditLog.Action.CREATE,
        entity='BountyType',
        entity_id=str(bt.id),
        actor=admin_user,
        after={
            'name': bt.name,
            'amount': str(bt.amount),
            'currency': bt.currency,
            'validity_days': bt.validity_days,
        },
        request=request,
    )
    return bt


@transaction.atomic
def update_bounty_type(
    *,
    bounty_type_id: str,
    admin_user,
    request=None,
    **fields
) -> BountyType:
    """
    Update an existing BountyType (name, description, amount, validity_days, is_active, sort_order).
    """
    bt = BountyType.objects.filter(id=bounty_type_id).first()
    if not bt:
        raise NotFound("BountyType not found.")

    before = {
        'name': bt.name, 'amount': str(bt.amount),
        'validity_days': bt.validity_days, 'is_active': bt.is_active,
    }

    allowed = ['name', 'description', 'amount', 'currency', 'validity_days', 'sort_order', 'is_active']
    update_fields = []
    for key in allowed:
        if key in fields and fields[key] is not None:
            setattr(bt, key, fields[key])
            update_fields.append(key)

    if update_fields:
        update_fields.append('updated_at')
        bt.save(update_fields=update_fields)

    record_audit(
        action=AuditLog.Action.UPDATE,
        entity='BountyType',
        entity_id=str(bt.id),
        actor=admin_user,
        before=before,
        after={'name': bt.name, 'amount': str(bt.amount), 'is_active': bt.is_active},
        request=request,
    )
    return bt


def seed_referral_sample_data():
    """
    Seed initial realistic referral records and double-entry ledger rows
    if the table is currently empty, so the Escrow & Payouts Cockpit
    immediately demonstrates the live payout queue.
    Also seeds default BountyTypes if none exist.
    """
    from apps.accounts.models import User

    # Seed default BountyTypes if empty
    if not BountyType.objects.exists():
        _seed_default_bounty_types()

    if Referral.objects.exists():
        return

    admin = User.objects.filter(is_staff=True).first()
    first_user = User.objects.first()
    if not first_user:
        return

    standard_bt = BountyType.objects.filter(is_active=True).first()

    # 1. Placed and Paid
    ref1 = Referral.objects.create(
        referrer=first_user,
        referral_type=ReferralType.CANDIDATE,
        source=ReferralSource.DIRECT,
        stage=ReferralStage.PLACED,
        referral_scope=ReferralScope.GENERAL_CANDIDATE,
        bounty_locked=True,
        referred_name="Marcus Vance",
        referred_email="marcus.vance@example.com",
    )
    LedgerEntry.objects.create(
        user=first_user,
        referral=ref1,
        amount=standard_bt.amount if standard_bt else Decimal("1500.00"),
        currency="USD",
        milestone="90d_guarantee_passed",
        bounty_type=standard_bt,
        status=PayoutStatus.PAID,
        approved_by=admin,
        approved_at=timezone.now() - timezone.timedelta(days=12),
        paid_reference="WIRE-2026-CHASE-09281",
        paid_at=timezone.now() - timezone.timedelta(days=11),
        note="Initial cohort placement bounty reconciled via Chase wire.",
    )

    # 2. Approved awaiting wire disbursement
    ref2 = Referral.objects.create(
        referrer=first_user,
        referral_type=ReferralType.CANDIDATE,
        source=ReferralSource.LINK,
        stage=ReferralStage.PLACED,
        referral_scope=ReferralScope.GENERAL_CANDIDATE,
        bounty_locked=True,
        referred_name="Elena Rostova",
        referred_email="elena.rostova@example.com",
    )
    LedgerEntry.objects.create(
        user=first_user,
        referral=ref2,
        amount=standard_bt.amount if standard_bt else Decimal("1200.00"),
        currency="USD",
        milestone="placed",
        bounty_type=standard_bt,
        status=PayoutStatus.APPROVED,
        approved_by=admin,
        approved_at=timezone.now() - timezone.timedelta(days=2),
        note="Candidate verified in FinTech Core Requisition. Milestone sign-off complete.",
    )

    # 3. Pending Approval
    ref3 = Referral.objects.create(
        referrer=first_user,
        referral_type=ReferralType.CANDIDATE,
        source=ReferralSource.DIRECT,
        stage=ReferralStage.INTERVIEWED,
        referral_scope=ReferralScope.GENERAL_CANDIDATE,
        referred_name="David K. Chen",
        referred_email="david.chen@example.com",
    )
    LedgerEntry.objects.create(
        user=first_user,
        referral=ref3,
        amount=standard_bt.amount if standard_bt else Decimal("1500.00"),
        currency="USD",
        milestone="placed",
        bounty_type=standard_bt,
        status=PayoutStatus.PENDING,
        note="Final round client panel scheduled.",
    )


def _seed_default_bounty_types():
    """Seed the default admin-managed bounty type catalog."""
    defaults = [
        {
            'name': 'Standard Placement Bounty',
            'description': 'Standard referral bounty for technology and general role placements.',
            'amount': Decimal('1500.00'),
            'validity_days': 90,
            'sort_order': 1,
        },
        {
            'name': 'Senior Specialist Bounty',
            'description': 'Premium bounty for senior-level and principal specialist placements.',
            'amount': Decimal('2500.00'),
            'validity_days': 90,
            'sort_order': 2,
        },
        {
            'name': 'Healthcare Clinical Bounty',
            'description': 'Clinical healthcare specialist referral bounty including ICU and OR roles.',
            'amount': Decimal('2000.00'),
            'validity_days': 90,
            'sort_order': 3,
        },
        {
            'name': 'Urgent Priority Bounty',
            'description': 'Accelerated bounty for critical Priority-1 roles requiring immediate fill.',
            'amount': Decimal('3000.00'),
            'validity_days': 60,
            'sort_order': 4,
        },
    ]
    for d in defaults:
        BountyType.objects.get_or_create(name=d['name'], defaults=d)


def seed_recruiter_sample_referrals():
    """
    Ensure rich seed data for Recruiter Referral Management testing.
    """
    from apps.accounts.models import User
    from apps.ats.models import Requisition

    if Referral.objects.filter(referral_type=ReferralType.CANDIDATE).count() >= 4:
        return

    referrer = User.objects.filter(is_staff=False).first() or User.objects.first()
    if not referrer:
        return

    standard_bt = BountyType.objects.filter(is_active=True).first()
    req_tech = Requisition.objects.filter(sector='technology', bounty_enabled=True).first()
    req_health = Requisition.objects.filter(sector='healthcare', bounty_enabled=True).first()

    # Fallback to any open req if no bounty-enabled ones exist yet
    if not req_tech:
        req_tech = Requisition.objects.filter(sector='technology').first()
    if not req_health:
        req_health = Requisition.objects.filter(sector='healthcare').first()

    samples = [
        ("Kavita Raman", "kavita.raman@example.com", ReferralStage.SUBMITTED,
         ReferralScope.GENERAL_CANDIDATE, req_tech,
         "Referred senior cloud architect with AWS and Terraform mastery."),
        ("Julian Thorne", "julian.thorne@example.com", ReferralStage.SCREENED,
         ReferralScope.SPECIFIC_JOB, req_tech,
         "Specialist passed initial technical screening; role match approved."),
        ("Nurse Patricia Hall", "patricia.hall@example.com", ReferralStage.INTERVIEWED,
         ReferralScope.SPECIFIC_JOB, req_health,
         "ICU Nurse specialist completed clinical sprint panel."),
        ("Devon Brooks", "devon.brooks@example.com", ReferralStage.PLACED,
         ReferralScope.GENERAL_CANDIDATE, req_tech,
         "Placed in Distributed Golang Core Requisition. 90-day retention tracking active."),
    ]

    for name, email, stage, scope, target_req, note in samples:
        ref, created = Referral.objects.get_or_create(
            referred_email=email,
            defaults={
                'referrer': referrer,
                'referral_type': ReferralType.CANDIDATE,
                'source': ReferralSource.DIRECT,
                'stage': stage,
                'referral_scope': scope,
                'referred_name': name,
                'requisition': target_req,
                'bounty_locked': stage == ReferralStage.PLACED,
            }
        )
        if created and stage == ReferralStage.PLACED and target_req and (target_req.bounty_enabled or target_req.bounty_amount):
            mint_amount, bt_obj = _resolve_bounty_amount_and_type(ref)
            LedgerEntry.objects.get_or_create(
                referral=ref,
                milestone='placed',
                defaults={
                    'user': referrer,
                    'amount': mint_amount,
                    'currency': bt_obj.currency if bt_obj else 'USD',
                    'bounty_type': bt_obj,
                    'status': PayoutStatus.APPROVED,
                    'note': f"Placement bounty for {name} ({note})",
                }
            )
