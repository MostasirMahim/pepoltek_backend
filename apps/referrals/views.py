"""
referrals/views.py
API endpoints for Refer & Earn network, candidate referrals, Admin Escrow & Payout Cockpit,
and the BountyType admin catalog CRUD.
"""
from decimal import Decimal
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.accounts.permissions import IsAdminOrSuperAdmin, IsStaffMember
from .selectors import (
    get_admin_payout_summary,
    list_admin_ledger_entries,
    get_user_referral_summary,
    list_admin_referrals,
    list_recruiter_referrals,
    list_bounty_types,
)
from .services import (
    approve_payout,
    disburse_payout,
    cancel_payout,
    submit_direct_referral,
    seed_referral_sample_data,
    admin_update_referral_stage,
    recruiter_update_referral,
    seed_recruiter_sample_referrals,
    create_bounty_type,
    update_bounty_type,
)
from .models import BountyType


class AdminLedgerSummaryView(APIView):
    """
    GET /api/v1/referrals/admin/summary/
    Return real-time financial escrow telemetry and double-entry ledger rows.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        seed_referral_sample_data()

        status_filter = request.query_params.get('status', 'all')
        search_query = request.query_params.get('search', '')

        telemetry = get_admin_payout_summary()
        records = list_admin_ledger_entries(status_filter=status_filter, search=search_query)

        return Response({
            'data': {
                'telemetry': telemetry,
                'records': records,
            }
        }, status=status.HTTP_200_OK)


class AdminApprovePayoutView(APIView):
    """
    POST /api/v1/referrals/admin/payouts/<int:entry_id>/approve/
    Approve a pending referral bounty payout.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, entry_id):
        entry = approve_payout(
            ledger_entry_id=entry_id,
            admin_user=request.user,
            request=request,
        )
        return Response({
            'data': {
                'id': f'LEDGER-{entry.id:04d}',
                'raw_id': entry.id,
                'status': entry.status,
                'status_display': 'Approved for Wire',
                'approved_by': entry.approved_by.email if entry.approved_by else None,
                'approved_at': entry.approved_at.isoformat() if entry.approved_at else None,
                'message': f'Ledger entry LEDGER-{entry.id:04d} approved successfully.',
            }
        }, status=status.HTTP_200_OK)


class AdminDisbursePayoutView(APIView):
    """
    POST /api/v1/referrals/admin/payouts/<int:entry_id>/disburse/
    Mark payout as Paid with an external bank wire / ACH / PayPal transaction reference.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, entry_id):
        paid_reference = request.data.get('paid_reference', '')
        payment_method = request.data.get('payment_method', 'bank_wire')
        note = request.data.get('note', '')

        entry = disburse_payout(
            ledger_entry_id=entry_id,
            admin_user=request.user,
            paid_reference=paid_reference,
            payment_method=payment_method,
            note=note,
            request=request,
        )
        return Response({
            'data': {
                'id': f'LEDGER-{entry.id:04d}',
                'raw_id': entry.id,
                'status': entry.status,
                'status_display': 'Cleared and Settled',
                'paid_reference': entry.paid_reference,
                'paid_at': entry.paid_at.isoformat() if entry.paid_at else None,
                'message': f'Ledger entry LEDGER-{entry.id:04d} disbursed under reference {entry.paid_reference}.',
            }
        }, status=status.HTTP_200_OK)


class AdminCancelPayoutView(APIView):
    """
    POST /api/v1/referrals/admin/payouts/<int:entry_id>/cancel/
    Cancel or reject a pending payout with an audit reason.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, entry_id):
        reason = request.data.get('reason', 'Administrative cancellation')
        entry = cancel_payout(
            ledger_entry_id=entry_id,
            admin_user=request.user,
            reason=reason,
            request=request,
        )
        return Response({
            'data': {
                'id': f'LEDGER-{entry.id:04d}',
                'raw_id': entry.id,
                'status': entry.status,
                'status_display': 'Cancelled / Reversed',
                'message': f'Ledger entry LEDGER-{entry.id:04d} cancelled.',
            }
        }, status=status.HTTP_200_OK)


class ReferralSummaryView(APIView):
    """
    GET /api/v1/referrals/summary/
    Live candidate/referrer dashboard ledger and earnings.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        seed_referral_sample_data()
        data = get_user_referral_summary(request.user)
        return Response({'data': data}, status=status.HTTP_200_OK)


class DirectReferralSubmitView(APIView):
    """
    POST /api/v1/referrals/submit/
    Direct candidate referral submitted by an authenticated user.
    If requisition_id is provided and the job is bounty-enabled, scope is SPECIFIC_JOB.
    Otherwise scope is GENERAL_CANDIDATE (earns only first-job bounty).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get('referred_name', '').strip()
        email = request.data.get('referred_email', '').strip()
        role = request.data.get('target_role', '').strip()
        notes = request.data.get('notes', '').strip()
        requisition_id = request.data.get('requisition_id', None)

        if not name or not email:
            return Response(
                {'error': {'code': 'INVALID_INPUT', 'message': 'Candidate name and email are required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        referral = submit_direct_referral(
            referrer_user=request.user,
            referred_name=name,
            referred_email=email,
            target_role=role,
            notes=notes,
            requisition_id=requisition_id,
            request=request,
        )
        return Response({
            'data': {
                'id': str(referral.id),
                'referred_name': referral.referred_name,
                'referred_email': referral.referred_email,
                'stage': referral.stage,
                'referral_scope': referral.referral_scope,
                'requisition_id': str(referral.requisition_id) if referral.requisition_id else None,
                'message': f'Referral invitation recorded for {referral.referred_name}.',
            }
        }, status=status.HTTP_201_CREATED)


class ReferralTrackView(APIView):
    """
    POST /api/v1/referrals/track/<str:code>/
    Record referral link attribution hit and validate referral code.
    """
    permission_classes = [AllowAny]

    def post(self, request, code):
        from apps.accounts.models import User

        clean_code = code.strip().upper()
        referrer = User.objects.filter(referral_code__iexact=clean_code).first()

        response = Response({
            'data': {
                'code': clean_code,
                'valid': referrer is not None,
                'attributed': True,
                'message': 'Referral attribution cookie set.' if referrer else 'Unknown referral code.',
            }
        }, status=status.HTTP_200_OK)

        if referrer:
            response.set_cookie(
                key='pepoltek_ref',
                value=clean_code,
                max_age=90 * 24 * 60 * 60,  # 90 days
                httponly=True,
                samesite='Lax',
            )
        return response


class AdminReferralsPipelineView(APIView):
    """
    GET /api/v1/referrals/admin/pipeline/
    List all platform referrals with stage filtering, candidate relations,
    bounty metadata, and funnel telemetry.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        seed_referral_sample_data()

        stage_filter = request.query_params.get('stage', 'all')
        referral_type = request.query_params.get('type', 'all')
        search_query = request.query_params.get('search', '')

        result = list_admin_referrals(
            stage_filter=stage_filter,
            referral_type=referral_type,
            search=search_query
        )

        return Response({
            'data': result
        }, status=status.HTTP_200_OK)


class AdminUpdateReferralStageView(APIView):
    """
    PATCH /api/v1/referrals/admin/<uuid:referral_id>/stage/
    Update the pipeline stage of a referral.
    If stage is set to 'placed', applies bounty scope rules before minting escrow entry.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def patch(self, request, referral_id):
        new_stage = request.data.get('stage')
        if not new_stage:
            return Response({
                'error': {
                    'code': 'missing_stage',
                    'message': 'Parameter "stage" is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        raw_bounty = request.data.get('bounty_amount')
        bounty_amount = None
        if raw_bounty is not None:
            try:
                bounty_amount = Decimal(str(raw_bounty))
            except Exception:
                bounty_amount = None

        note = request.data.get('note', '')
        placement_requisition_id = request.data.get('placement_requisition_id')

        referral, created_ledger = admin_update_referral_stage(
            referral_id=str(referral_id),
            new_stage=new_stage,
            admin_user=request.user,
            bounty_amount=bounty_amount,
            note=note,
            placement_requisition_id=placement_requisition_id,
            request=request,
        )

        ledger_data = None
        if created_ledger:
            ledger_data = {
                'id': f'LEDGER-{created_ledger.id:04d}',
                'raw_id': created_ledger.id,
                'amount': float(created_ledger.amount),
                'amount_display': f"${created_ledger.amount:,.2f}",
                'status': created_ledger.status,
                'milestone': created_ledger.milestone,
                'bounty_type': created_ledger.bounty_type.name if created_ledger.bounty_type else None,
            }

        return Response({
            'data': {
                'id': f'REF-{str(referral.id).replace("-", "")[:8].upper()}',
                'raw_id': str(referral.id),
                'stage': referral.stage,
                'stage_display': referral.get_stage_display() if hasattr(referral, 'get_stage_display') else referral.stage,
                'referral_scope': referral.referral_scope,
                'bounty_locked': referral.bounty_locked,
                'created_ledger': ledger_data,
                'message': f'Referral stage updated to {referral.stage}.',
            }
        }, status=status.HTTP_200_OK)


class RecruiterReferralsPipelineView(APIView):
    """
    GET /api/v1/referrals/recruiter/
    List candidate referrals for recruiter oversight with pipeline telemetry,
    requisition bindings, and open bounty-enabled requisition options for fast-track matching.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        seed_recruiter_sample_referrals()

        stage_filter = request.query_params.get('stage', 'all')
        search_query = request.query_params.get('search', '')

        result = list_recruiter_referrals(
            stage_filter=stage_filter,
            search=search_query
        )

        return Response({
            'data': result
        }, status=status.HTTP_200_OK)


class RecruiterUpdateReferralView(APIView):
    """
    PATCH /api/v1/referrals/recruiter/<uuid:referral_id>/
    Recruiter updates candidate referral stage and/or links candidate to an open Requisition.
    Bounty scope rules apply on placement.
    """
    permission_classes = [IsStaffMember]

    def patch(self, request, referral_id):
        new_stage = request.data.get('stage')
        if not new_stage:
            return Response({
                'error': {
                    'code': 'missing_stage',
                    'message': 'Parameter "stage" is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        requisition_id = request.data.get('requisition_id')

        raw_bounty = request.data.get('bounty_amount')
        bounty_amount = None
        if raw_bounty is not None:
            try:
                bounty_amount = Decimal(str(raw_bounty))
            except Exception:
                bounty_amount = None

        note = request.data.get('note', '')

        referral, created_ledger = recruiter_update_referral(
            referral_id=str(referral_id),
            new_stage=new_stage,
            recruiter_user=request.user,
            requisition_id=requisition_id,
            bounty_amount=bounty_amount,
            note=note,
            request=request,
        )

        ledger_data = None
        if created_ledger:
            ledger_data = {
                'id': f'LEDGER-{created_ledger.id:04d}',
                'raw_id': created_ledger.id,
                'amount': float(created_ledger.amount),
                'amount_display': f"${created_ledger.amount:,.2f}",
                'status': created_ledger.status,
                'milestone': created_ledger.milestone,
                'bounty_type': created_ledger.bounty_type.name if created_ledger.bounty_type else None,
            }

        return Response({
            'data': {
                'id': f'REF-{str(referral.id).replace("-", "")[:8].upper()}',
                'raw_id': str(referral.id),
                'stage': referral.stage,
                'stage_display': referral.get_stage_display() if hasattr(referral, 'get_stage_display') else referral.stage,
                'referral_scope': referral.referral_scope,
                'bounty_locked': referral.bounty_locked,
                'requisition_id': str(referral.requisition_id) if referral.requisition_id else None,
                'requisition_title': referral.requisition.title if referral.requisition else 'Unassigned Requisition',
                'created_ledger': ledger_data,
                'message': f'Referral updated to {referral.stage}.',
            }
        }, status=status.HTTP_200_OK)


# ─── BountyType Catalog CRUD (Admin Only) ─────────────────────────────────────

class AdminBountyTypesView(APIView):
    """
    GET  /api/v1/referrals/bounty-types/   - List all bounty types (active + inactive).
    POST /api/v1/referrals/bounty-types/   - Create a new bounty type.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        seed_referral_sample_data()  # ensures defaults exist
        types = list_bounty_types(include_inactive=True)
        return Response({'data': types}, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data
        name = data.get('name', '').strip()
        raw_amount = data.get('amount')
        description = data.get('description', '')
        currency = data.get('currency', 'USD')
        validity_days = int(data.get('validity_days', 90))
        sort_order = int(data.get('sort_order', 0))

        if not name:
            return Response(
                {'error': {'code': 'MISSING_NAME', 'message': 'Bounty type name is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount = Decimal(str(raw_amount))
        except Exception:
            return Response(
                {'error': {'code': 'INVALID_AMOUNT', 'message': 'A valid numeric amount is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bt = create_bounty_type(
            name=name,
            amount=amount,
            description=description,
            currency=currency,
            validity_days=validity_days,
            sort_order=sort_order,
            admin_user=request.user,
            request=request,
        )
        return Response({
            'data': _bounty_type_to_dict(bt),
            'message': f'Bounty type "{bt.name}" created successfully.',
        }, status=status.HTTP_201_CREATED)


class AdminBountyTypeDetailView(APIView):
    """
    PATCH  /api/v1/referrals/bounty-types/<uuid:bounty_type_id>/  - Update bounty type.
    DELETE /api/v1/referrals/bounty-types/<uuid:bounty_type_id>/  - Deactivate bounty type.
    """
    permission_classes = [IsAdminOrSuperAdmin]

    def patch(self, request, bounty_type_id):
        data = request.data
        fields = {}
        if 'name' in data:
            fields['name'] = data['name']
        if 'description' in data:
            fields['description'] = data['description']
        if 'amount' in data:
            try:
                fields['amount'] = Decimal(str(data['amount']))
            except Exception:
                return Response(
                    {'error': {'code': 'INVALID_AMOUNT', 'message': 'Invalid amount value.'}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if 'currency' in data:
            fields['currency'] = data['currency']
        if 'validity_days' in data:
            fields['validity_days'] = int(data['validity_days'])
        if 'sort_order' in data:
            fields['sort_order'] = int(data['sort_order'])
        if 'is_active' in data:
            fields['is_active'] = bool(data['is_active'])

        bt = update_bounty_type(
            bounty_type_id=str(bounty_type_id),
            admin_user=request.user,
            request=request,
            **fields,
        )
        return Response({
            'data': _bounty_type_to_dict(bt),
            'message': f'Bounty type "{bt.name}" updated.',
        }, status=status.HTTP_200_OK)

    def delete(self, request, bounty_type_id):
        bt = update_bounty_type(
            bounty_type_id=str(bounty_type_id),
            admin_user=request.user,
            request=request,
            is_active=False,
        )
        return Response({
            'data': {'id': str(bt.id), 'is_active': False},
            'message': f'Bounty type "{bt.name}" deactivated.',
        }, status=status.HTTP_200_OK)


class PublicBountyTypesView(APIView):
    """
    GET /api/v1/referrals/bounty-types/public/
    List active bounty types for job board and recruiter job creation form.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        types = list_bounty_types(include_inactive=False)
        return Response({'data': types}, status=status.HTTP_200_OK)


def _bounty_type_to_dict(bt: BountyType) -> dict:
    return {
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
