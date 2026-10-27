from django.urls import path
from .views import (
    ReferralSummaryView,
    ReferralTrackView,
    DirectReferralSubmitView,
    ReferralPayoutRequestView,
    AdminLedgerSummaryView,
    AdminApprovePayoutView,
    AdminDisbursePayoutView,
    AdminCancelPayoutView,
    AdminReferralsPipelineView,
    AdminUpdateReferralStageView,
    RecruiterReferralsPipelineView,
    RecruiterUpdateReferralView,
    AdminBountyTypesView,
    AdminBountyTypeDetailView,
    PublicBountyTypesView,
)

urlpatterns = [
    # Candidate & Public endpoints
    path('summary/', ReferralSummaryView.as_view(), name='referral-summary'),
    path('submit/', DirectReferralSubmitView.as_view(), name='referral-submit'),
    path('track/<str:code>/', ReferralTrackView.as_view(), name='referral-track'),
    path('request-payout/', ReferralPayoutRequestView.as_view(), name='referral-request-payout'),

    # Recruiter Referral Pipeline endpoints
    path('recruiter/', RecruiterReferralsPipelineView.as_view(), name='recruiter-referrals-pipeline'),
    path('recruiter/<uuid:referral_id>/', RecruiterUpdateReferralView.as_view(), name='recruiter-referral-update'),

    # Admin Escrow & Payout endpoints
    path('admin/summary/', AdminLedgerSummaryView.as_view(), name='admin-referral-summary'),
    path('admin/payouts/<int:entry_id>/approve/', AdminApprovePayoutView.as_view(), name='admin-payout-approve'),
    path('admin/payouts/<int:entry_id>/disburse/', AdminDisbursePayoutView.as_view(), name='admin-payout-disburse'),
    path('admin/payouts/<int:entry_id>/cancel/', AdminCancelPayoutView.as_view(), name='admin-payout-cancel'),

    # Admin Referral Pipeline endpoints
    path('admin/pipeline/', AdminReferralsPipelineView.as_view(), name='admin-referrals-pipeline'),
    path('admin/<uuid:referral_id>/stage/', AdminUpdateReferralStageView.as_view(), name='admin-referral-stage-update'),

    # BountyType Catalog CRUD (Admin)
    path('bounty-types/', AdminBountyTypesView.as_view(), name='admin-bounty-types-list'),
    path('bounty-types/public/', PublicBountyTypesView.as_view(), name='bounty-types-public'),
    path('bounty-types/<uuid:bounty_type_id>/', AdminBountyTypeDetailView.as_view(), name='admin-bounty-type-detail'),
]
