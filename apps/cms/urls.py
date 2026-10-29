from django.urls import path
from .views import (
    # Public
    PublicSiteContentView,
    CaseStudiesListView,
    CaseStudyDetailView,
    # Admin Blocks
    AdminContentBlocksOverviewView,
    AdminContentBlockDetailView,
    AdminContentPublishView,
    AdminContentDraftView,
    AdminContentRollbackView,
    AdminContentHistoryView,
    # Admin Case Studies
    AdminCaseStudiesListView,
    AdminCaseStudyCreateView,
    AdminCaseStudyDetailView,
)

urlpatterns = [
    # ---- Public ----
    path('site/<str:key>/', PublicSiteContentView.as_view(), name='cms-site-content'),
    path('case-studies/', CaseStudiesListView.as_view(), name='cms-case-studies-list'),
    path('case-studies/<str:slug>/', CaseStudyDetailView.as_view(), name='cms-case-study-detail'),

    # ---- Admin Blocks ----
    path('admin/blocks/', AdminContentBlocksOverviewView.as_view(), name='cms-admin-blocks-overview'),
    path('admin/blocks/<str:key>/', AdminContentBlockDetailView.as_view(), name='cms-admin-block-detail'),
    path('admin/blocks/<str:key>/publish/', AdminContentPublishView.as_view(), name='cms-admin-block-publish'),
    path('admin/blocks/<str:key>/draft/', AdminContentDraftView.as_view(), name='cms-admin-block-draft'),
    path('admin/blocks/<str:key>/rollback/', AdminContentRollbackView.as_view(), name='cms-admin-block-rollback'),
    path('admin/blocks/<str:key>/history/', AdminContentHistoryView.as_view(), name='cms-admin-block-history'),

    # ---- Admin Case Studies ----
    path('admin/case-studies/', AdminCaseStudiesListView.as_view(), name='cms-admin-case-studies-list'),
    path('admin/case-studies/create/', AdminCaseStudyCreateView.as_view(), name='cms-admin-case-study-create'),
    path('admin/case-studies/<uuid:id>/', AdminCaseStudyDetailView.as_view(), name='cms-admin-case-study-detail'),
]
