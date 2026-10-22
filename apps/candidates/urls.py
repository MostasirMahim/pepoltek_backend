from django.urls import path
from .views import (
    CandidateMeView,
    CandidateDashboardAggregationView,
    CandidateCredentialsView,
    CandidateCredentialDetailView,
    CandidateDocumentsView,
    CandidateDocumentDetailView,
    CandidateExportDataView,
    CandidateDeleteRequestView,
    CandidateApplicationsView,
    CandidatePitchToggleView,
    CandidateIntakeView,
)

urlpatterns = [
    path('me/', CandidateMeView.as_view(), name='candidate-me'),
    path('me/dashboard/', CandidateDashboardAggregationView.as_view(), name='candidate-dashboard'),
    path('me/credentials/', CandidateCredentialsView.as_view(), name='candidate-credentials'),
    path('me/credentials/<uuid:id>/', CandidateCredentialDetailView.as_view(), name='candidate-credential-detail'),
    path('me/documents/', CandidateDocumentsView.as_view(), name='candidate-documents'),
    path('me/documents/<uuid:id>/', CandidateDocumentDetailView.as_view(), name='candidate-document-detail'),
    path('me/export/', CandidateExportDataView.as_view(), name='candidate-export'),
    path('me/delete-request/', CandidateDeleteRequestView.as_view(), name='candidate-delete-request'),
    path('applications/', CandidateApplicationsView.as_view(), name='candidate-applications'),
    path('pitch/', CandidatePitchToggleView.as_view(), name='candidate-pitch-toggle'),
    path('intake/', CandidateIntakeView.as_view(), name='candidate-intake'),
]
