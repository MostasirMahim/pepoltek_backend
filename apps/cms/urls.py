from django.urls import path
from .views import (
    # Public
    PublicSiteContentView,
    CaseStudiesListView,
    CaseStudyDetailView,
    # Admin
    AdminContentBlocksOverviewView,
    AdminContentBlockDetailView,
    AdminContentPublishView,
    AdminContentDraftView,
    AdminContentRollbackView,
    AdminContentHistoryView,
)

urlpatterns = [
    # ---- Public ----
    path('site/<str:key>/', PublicSiteContentView.as_view(), name='cms-site-content'),
    path('case-studies/', CaseStudiesListView.as_view(), name='cms-case-studies-list'),
    path('case-studies/<str:slug>/', CaseStudyDetailView.as_view(), name='cms-case-study-detail'),

    # ---- Admin ----
    path('admin/blocks/', AdminContentBlocksOverviewView.as_view(), name='cms-admin-blocks-overview'),
    path('admin/blocks/<str:key>/', AdminContentBlockDetailView.as_view(), name='cms-admin-block-detail'),
    path('admin/blocks/<str:key>/publish/', AdminContentPublishView.as_view(), name='cms-admin-block-publish'),
    path('admin/blocks/<str:key>/draft/', AdminContentDraftView.as_view(), name='cms-admin-block-draft'),
    path('admin/blocks/<str:key>/rollback/', AdminContentRollbackView.as_view(), name='cms-admin-block-rollback'),
    path('admin/blocks/<str:key>/history/', AdminContentHistoryView.as_view(), name='cms-admin-block-history'),
]
