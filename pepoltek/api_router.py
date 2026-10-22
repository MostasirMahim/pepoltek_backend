"""API router - aggregates all app-level URL routers under /api/v1/."""
from django.urls import path, include

urlpatterns = [
    path('auth/', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('candidates/', include('apps.candidates.urls')),
    path('documents/', include('apps.resumes.urls')),
    path('ats/', include('apps.ats.urls')),
    path('leads/', include('apps.leads.urls')),
    path('config/', include('apps.config_center.urls')),
    path('content/', include('apps.cms.urls')),
    path('matching/', include('apps.matching.urls')),
    path('referrals/', include('apps.referrals.urls')),
    path('academy/', include('apps.academy.urls')),
    path('vetting/', include('apps.vetting.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('audit/', include('apps.audit.urls')),
    path('ai/', include('apps.ai_service.urls')),
]

