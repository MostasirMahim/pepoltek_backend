"""
referrals/selectors.py
Read-only database queries for referrals and payout ledgers.
"""
from decimal import Decimal
from django.db.models import Sum, Q
from .models import Referral, LedgerEntry, PayoutStatus, ReferralStage, ReferralType, ReferralSource, BountyType


def get_admin_payout_summary() -> dict:
    """
    Compute real-time financial metrics for the Escrow & Payouts Cockpit.
    """
    total_paid = LedgerEntry.objects.filter(status=PayoutStatus.PAID).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    pending_payouts = LedgerEntry.objects.filter(status=PayoutStatus.PENDING).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    approved_payouts = LedgerEntry.objects.filter(status=PayoutStatus.APPROVED).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    escrow_vault = pending_payouts + approved_payouts

    total_referrals_count = Referral.objects.count()
    active_referrers_count = Referral.objects.values('referrer_id').distinct().count()
    placed_referrals_count = Referral.objects.filter(stage=ReferralStage.PLACED).count()

    return {
        'escrow_vault_balance': float(escrow_vault),
        'total_paid_usd': float(total_paid),
        'pending_payouts_usd': float(pending_payouts),
        'approved_payouts_usd': float(approved_payouts),
        'total_referrals_count': total_referrals_count,
        'active_referrers_count': active_referrers_count,
        'placed_referrals_count': placed_referrals_count,
    }


def list_admin_ledger_entries(status_filter: str = 'all', search: str = '') -> list:
    """
    List ledger entries with relations, filterable by status and search.
    """
    qs = LedgerEntry.objects.select_related(
        'user', 'referral', 'referral__referrer', 'referral__candidate', 'referral__lead', 'referral__requisition', 'approved_by'
    ).order_by('-created_at')

    if status_filter and status_filter.lower() != 'all':
        qs = qs.filter(status=status_filter.lower())

    if search:
        s = search.strip()
        qs = qs.filter(
            Q(user__email__icontains=s) |
            Q(user__full_name__icontains=s) |
            Q(referral__referred_name__icontains=s) |
            Q(referral__referred_email__icontains=s) |
            Q(paid_reference__icontains=s) |
            Q(milestone__icontains=s)
        )

    records = []
    for entry in qs:
        candidate_name = entry.referral.referred_name or (
            entry.referral.candidate.full_name if entry.referral.candidate else ''
        ) or (
            entry.referral.lead.contact_name if entry.referral.lead else 'Referred Talent'
        )

        track_label = 'Technology Track'
        if entry.referral.requisition:
            track_label = entry.referral.requisition.title
        elif entry.referral.referral_type == 'client_lead':
            track_label = 'Enterprise Client Lead'

        status_map = {
            PayoutStatus.PENDING: 'Pending Approval',
            PayoutStatus.APPROVED: 'Approved for Wire',
            PayoutStatus.PAID: 'Cleared and Settled',
            PayoutStatus.CANCELLED: 'Cancelled / Reversed',
        }

        records.append({
            'id': f'LEDGER-{entry.id:04d}',
            'raw_id': entry.id,
            'referrer_email': entry.user.email,
            'referrer_name': entry.user.full_name or entry.user.email,
            'candidate_name': candidate_name,
            'track': track_label,
            'amount_usd': float(entry.amount),
            'amount_display': f"${entry.amount:,.2f}",
            'currency': entry.currency,
            'milestone': entry.milestone,
            'bounty_type': entry.bounty_type.name if entry.bounty_type else None,
            'status': entry.status,
            'status_display': status_map.get(entry.status, entry.status),
            'approved_by': entry.approved_by.email if entry.approved_by else None,
            'approved_at': entry.approved_at.isoformat() if entry.approved_at else None,
            'paid_reference': entry.paid_reference,
            'paid_at': entry.paid_at.isoformat() if entry.paid_at else None,
            'date': entry.created_at.strftime('%b %d, %Y'),
            'created_at': entry.created_at.isoformat(),
            'note': entry.note,
        })
    return records


def get_user_referral_summary(user) -> dict:
    """
    Get live referral summary and ledger entries for an authenticated user.
    """
    code = getattr(user, 'referral_code', 'PEP-REF-0000')

    entries = LedgerEntry.objects.filter(user=user).select_related('referral').order_by('-created_at')

    total_paid = entries.filter(status=PayoutStatus.PAID).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    pending_bounties = entries.filter(status=PayoutStatus.PENDING).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    referrals_count = Referral.objects.filter(referrer=user).count()

    ledger_rows = []
    for entry in entries:
        candidate_name = entry.referral.referred_name or 'Referred Talent'
        status_display = 'Pending Milestone'
        if entry.status == PayoutStatus.PAID:
            status_display = 'Paid'
        elif entry.status == PayoutStatus.APPROVED:
            status_display = 'Approved for Payout'
        elif entry.status == PayoutStatus.CANCELLED:
            status_display = 'Cancelled'

        ledger_rows.append({
            'id': f'ref-{entry.id:03d}',
            'candidate': candidate_name,
            'track': entry.milestone or 'Placement Bounty',
            'status': entry.referral.get_stage_display() if hasattr(entry.referral, 'get_stage_display') else entry.referral.stage,
            'bountyEarned': f"${entry.amount:,.2f}",
            'payoutStatus': status_display,
            'date': entry.created_at.strftime('%b %d, %Y'),
            'paidReference': entry.paid_reference or None,
        })

    return {
        'referral_code': code,
        'total_paid_usd': float(total_paid),
        'pending_bounties_usd': float(pending_bounties),
        'total_referrals_count': referrals_count,
        'ledger': ledger_rows,
    }


def list_admin_referrals(stage_filter: str = 'all', referral_type: str = 'all', search: str = '') -> dict:
    """
    List all platform referrals with stage filtering, candidate relations,
    bounty metadata, and pipeline conversion telemetry for Admin oversight.
    """
    qs = Referral.objects.select_related(
        'referrer', 'candidate', 'candidate__user', 'lead', 'requisition'
    ).prefetch_related('ledger_entries').order_by('-created_at')

    # Global Telemetry before stage filtering
    total_count = qs.count()
    active_scouts = qs.values('referrer_id').distinct().count()
    placed_count = qs.filter(stage=ReferralStage.PLACED).count()
    conversion_rate = round((placed_count / total_count * 100), 1) if total_count > 0 else 0.0

    stage_counts = {
        'all': total_count,
        'submitted': qs.filter(stage=ReferralStage.SUBMITTED).count(),
        'screened': qs.filter(stage=ReferralStage.SCREENED).count(),
        'interviewed': qs.filter(stage=ReferralStage.INTERVIEWED).count(),
        'placed': placed_count,
        'rejected': qs.filter(stage=ReferralStage.REJECTED).count(),
        'duplicate': qs.filter(stage=ReferralStage.DUPLICATE).count(),
    }

    # Apply stage filter
    if stage_filter and stage_filter.lower() != 'all':
        qs = qs.filter(stage=stage_filter.lower())

    # Apply referral type filter (candidate vs client_lead)
    if referral_type and referral_type.lower() != 'all':
        qs = qs.filter(referral_type=referral_type.lower())

    # Apply search query
    if search:
        s = search.strip()
        qs = qs.filter(
            Q(referrer__email__icontains=s) |
            Q(referrer__full_name__icontains=s) |
            Q(referred_name__icontains=s) |
            Q(referred_email__icontains=s) |
            Q(candidate__full_name__icontains=s) |
            Q(lead__company_name__icontains=s) |
            Q(lead__contact_name__icontains=s)
        )

    records = []
    for ref in qs:
        # Determine candidate or contact name
        candidate_name = ref.referred_name or (
            ref.candidate.full_name if ref.candidate else ''
        ) or (
            ref.lead.contact_name if ref.lead else 'Referred Talent'
        )

        # Determine contact email
        candidate_email = ref.referred_email or (
            ref.candidate.user.email if ref.candidate and ref.candidate.user else ''
        ) or (
            ref.lead.contact_email if ref.lead else ''
        )

        track_label = 'Technology Requisition'
        if ref.requisition:
            track_label = ref.requisition.title
        elif ref.referral_type == ReferralType.CLIENT_LEAD:
            track_label = ref.lead.company_name if ref.lead else 'Enterprise Client Lead'

        # Inspect latest payout ledger entry
        active_ledger = ref.ledger_entries.order_by('-created_at').first()
        bounty_info = {
            'has_bounty': active_ledger is not None,
            'amount_usd': float(active_ledger.amount) if active_ledger else 1500.0,
            'amount_display': f"${active_ledger.amount:,.2f}" if active_ledger else "$1,500.00",
            'status': active_ledger.status if active_ledger else None,
            'status_display': (
                'Cleared and Settled' if active_ledger and active_ledger.status == PayoutStatus.PAID else
                'Approved for Wire' if active_ledger and active_ledger.status == PayoutStatus.APPROVED else
                'Pending Escrow Approval' if active_ledger and active_ledger.status == PayoutStatus.PENDING else
                'Cancelled' if active_ledger and active_ledger.status == PayoutStatus.CANCELLED else
                'Unminted'
            ),
            'ledger_id': f'LEDGER-{active_ledger.id:04d}' if active_ledger else None,
            'raw_ledger_id': active_ledger.id if active_ledger else None,
            'paid_reference': active_ledger.paid_reference if active_ledger else None,
        }

        stage_human = {
            ReferralStage.SUBMITTED: 'Submitted',
            ReferralStage.SCREENED: 'Screened',
            ReferralStage.INTERVIEWED: 'Interviewed',
            ReferralStage.PLACED: 'Placed & Integrated',
            ReferralStage.REJECTED: 'Rejected',
            ReferralStage.DUPLICATE: 'Duplicate Claim',
            ReferralStage.CONTACTED: 'Client Contacted',
            ReferralStage.QUALIFIED: 'Client Qualified',
            ReferralStage.CONTRACT_SIGNED: 'Contract Signed',
            ReferralStage.LOST: 'Deal Lost',
        }.get(ref.stage, ref.stage)

        records.append({
            'id': f'REF-{str(ref.id).replace("-", "")[:8].upper()}',
            'raw_id': str(ref.id),
            'referrer': {
                'id': str(ref.referrer.id),
                'email': ref.referrer.email,
                'name': ref.referrer.full_name or ref.referrer.email,
                'referral_code': getattr(ref.referrer, 'referral_code', 'PEP-REF-0000'),
            },
            'candidate_name': candidate_name,
            'candidate_email': candidate_email,
            'candidate_id': str(ref.candidate.id) if ref.candidate else None,
            'referral_type': ref.referral_type,
            'referral_type_display': 'Candidate Nomination' if ref.referral_type == ReferralType.CANDIDATE else 'Client Lead',
            'source': ref.source,
            'source_display': 'Universal Link (/r/code)' if ref.source == ReferralSource.LINK else 'Direct Submission',
            'stage': ref.stage,
            'stage_display': stage_human,
            'referral_scope': ref.referral_scope,
            'bounty_locked': ref.bounty_locked,
            'track': track_label,
            'bounty': bounty_info,
            'date': ref.created_at.strftime('%b %d, %Y'),
            'created_at': ref.created_at.isoformat(),
        })

    return {
        'telemetry': {
            'total_referrals': total_count,
            'active_scouts': active_scouts,
            'placed_count': placed_count,
            'conversion_rate': conversion_rate,
            'stage_counts': stage_counts,
        },
        'records': records,
    }


def list_recruiter_referrals(stage_filter: str = 'all', search: str = '') -> dict:
    """
    List candidate referrals for Recruiter ATS with stage filtering, requisition associations,
    and open requisition options for fast-track matching.
    """
    from apps.ats.models import Requisition, RequisitionStatus

    qs = Referral.objects.filter(referral_type=ReferralType.CANDIDATE).select_related(
        'referrer', 'candidate', 'candidate__user', 'requisition', 'requisition__client'
    ).prefetch_related('ledger_entries').order_by('-created_at')

    total_count = qs.count()
    active_in_pipeline = qs.filter(
        stage__in=[ReferralStage.SUBMITTED, ReferralStage.SCREENED, ReferralStage.INTERVIEWED]
    ).count()
    placed_count = qs.filter(stage=ReferralStage.PLACED).count()

    total_bounties_usd = 0.0
    for ref in qs.filter(stage=ReferralStage.PLACED):
        l = ref.ledger_entries.exclude(status=PayoutStatus.CANCELLED).first()
        if l:
            total_bounties_usd += float(l.amount)
        else:
            total_bounties_usd += 1500.0

    stage_counts = {
        'all': total_count,
        'submitted': qs.filter(stage=ReferralStage.SUBMITTED).count(),
        'screened': qs.filter(stage=ReferralStage.SCREENED).count(),
        'interviewed': qs.filter(stage=ReferralStage.INTERVIEWED).count(),
        'placed': placed_count,
        'rejected': qs.filter(stage=ReferralStage.REJECTED).count(),
    }

    if stage_filter and stage_filter.lower() != 'all':
        qs = qs.filter(stage=stage_filter.lower())

    if search:
        s = search.strip()
        qs = qs.filter(
            Q(referrer__email__icontains=s) |
            Q(referrer__full_name__icontains=s) |
            Q(referred_name__icontains=s) |
            Q(referred_email__icontains=s) |
            Q(candidate__full_name__icontains=s) |
            Q(requisition__title__icontains=s)
        )

    records = []
    for ref in qs:
        candidate_name = ref.referred_name or (
            ref.candidate.full_name if ref.candidate else 'Referred Specialist'
        )
        candidate_email = ref.referred_email or (
            ref.candidate.user.email if ref.candidate and ref.candidate.user else ''
        )
        candidate_phone = str(ref.candidate.phone) if ref.candidate and ref.candidate.phone else ''

        active_ledger = ref.ledger_entries.order_by('-created_at').first()
        # Resolve bounty amount: ledger > bounty_type on req > legacy bounty_amount > default
        req = ref.requisition
        if active_ledger:
            bounty_val = float(active_ledger.amount)
        elif req and req.bounty_enabled and req.bounty_type:
            bounty_val = float(req.bounty_type.amount)
        elif req and req.bounty_amount:
            bounty_val = float(req.bounty_amount)
        else:
            bounty_val = 1500.0

        records.append({
            'id': f'REF-{str(ref.id).replace("-", "")[:8].upper()}',
            'raw_id': str(ref.id),
            'candidate_name': candidate_name,
            'candidate_email': candidate_email,
            'candidate_phone': candidate_phone,
            'candidate_id': str(ref.candidate.id) if ref.candidate else None,
            'referrer': {
                'id': str(ref.referrer.id),
                'email': ref.referrer.email,
                'name': ref.referrer.full_name or ref.referrer.email,
                'referral_code': getattr(ref.referrer, 'referral_code', 'PEP-REF-0000'),
            },
            'stage': ref.stage,
            'stage_display': ref.get_stage_display() if hasattr(ref, 'get_stage_display') else ref.stage,
            'referral_scope': ref.referral_scope,
            'bounty_locked': ref.bounty_locked,
            'requisition_id': str(ref.requisition.id) if ref.requisition else None,
            'requisition_title': ref.requisition.title if ref.requisition else 'Unassigned Requisition',
            'client_name': ref.requisition.client.name if ref.requisition and ref.requisition.client else 'General Pool',
            'sector': ref.requisition.sector if ref.requisition else 'technology',
            'bounty_enabled': req.bounty_enabled if req else False,
            'bounty_type_name': req.bounty_type.name if req and req.bounty_type else None,
            'bounty_amount': bounty_val,
            'bounty_status': active_ledger.status if active_ledger else 'pending',
            'bounty_status_display': (
                'Cleared and Settled' if active_ledger and active_ledger.status == PayoutStatus.PAID else
                'Approved for Wire' if active_ledger and active_ledger.status == PayoutStatus.APPROVED else
                'Pending Escrow Approval' if active_ledger and active_ledger.status == PayoutStatus.PENDING else
                'Pending Placement'
            ),
            'date': ref.created_at.strftime('%b %d, %Y'),
            'created_at': ref.created_at.isoformat(),
        })

    available_requisitions = [
        {
            'id': str(r.id),
            'title': r.title,
            'client_name': r.client.name if r.client else 'Pepoltek Client',
            'sector': r.sector,
            'bounty_enabled': r.bounty_enabled,
            'bounty_type_id': str(r.bounty_type_id) if r.bounty_type_id else None,
            'bounty_type_name': r.bounty_type.name if r.bounty_type else None,
            'bounty_amount': float(r.bounty_type.amount) if r.bounty_type else float(r.bounty_amount or 0.0),
            'headcount': r.headcount,
        }
        for r in Requisition.objects.filter(status=RequisitionStatus.OPEN).select_related('client', 'bounty_type')
    ]

    return {
        'telemetry': {
            'total_referrals': total_count,
            'active_in_pipeline': active_in_pipeline,
            'placed_specialists': placed_count,
            'total_bounties_usd': total_bounties_usd,
            'stage_counts': stage_counts,
        },
        'records': records,
        'available_requisitions': available_requisitions,
        'available_pods': available_requisitions,
    }


def list_bounty_types(include_inactive: bool = False) -> list:
    """
    List all BountyType catalog entries for admin management or recruiter job-creation dropdown.
    """
    qs = BountyType.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return [
        {
            'id': str(bt.id),
            'name': bt.name,
            'description': bt.description,
            'amount': float(bt.amount),
            'amount_display': f"${bt.amount:,.2f}",
            'currency': bt.currency,
            'validity_days': bt.validity_days,
            'is_active': bt.is_active,
            'sort_order': bt.sort_order,
            'created_at': bt.created_at.isoformat() if bt.created_at else None,
        }
        for bt in qs
    ]
