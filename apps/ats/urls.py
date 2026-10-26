from django.urls import path
from .views import (
    PublicJobsListView,
    PublicJobDetailView,
    PublicJobApplyView,
    RecruiterRequisitionsView,
    RecruiterRequisitionDetailView,
    RecruiterPipelineView,
    RecruiterCandidatesListView,
    RecruiterInterviewsListView,
    RecruiterAnalyticsView,
    RecruiterSubmissionsView,
    RecruiterSubmissionDetailView,
    RecruiterSubmissionExportView,
    RecruiterRequisitionApplicationsView,
    RecruiterClientsListView,
    RecruiterClientDetailView,
    RecruiterSourceCandidateView,
    RecruiterApplicationDetailView,
    RecruiterApplicationNoteView,
)

urlpatterns = [
    # Public candidate endpoints
    path('jobs/', PublicJobsListView.as_view(), name='ats-public-jobs-list'),
    path('jobs/<uuid:id>/', PublicJobDetailView.as_view(), name='ats-public-job-detail'),
    path('jobs/<uuid:id>/apply/', PublicJobApplyView.as_view(), name='ats-public-job-apply'),

    # Recruiter staff workspace endpoints
    path('requisitions/', RecruiterRequisitionsView.as_view(), name='ats-requisitions-list'),
    path('requisitions/<uuid:id>/', RecruiterRequisitionDetailView.as_view(), name='ats-requisition-detail'),
    path('requisitions/<uuid:id>/applications/', RecruiterRequisitionApplicationsView.as_view(), name='ats-requisition-applications'),
    path('applications/<uuid:id>/', RecruiterApplicationDetailView.as_view(), name='ats-application-detail'),
    path('applications/<uuid:id>/notes/', RecruiterApplicationNoteView.as_view(), name='ats-application-notes'),
    path('pipeline/', RecruiterPipelineView.as_view(), name='ats-pipeline'),
    path('candidates/', RecruiterCandidatesListView.as_view(), name='ats-candidates'),
    path('candidates/source/', RecruiterSourceCandidateView.as_view(), name='ats-candidate-source'),
    path('interviews/', RecruiterInterviewsListView.as_view(), name='ats-interviews'),
    path('analytics/', RecruiterAnalyticsView.as_view(), name='ats-analytics'),
    path('submissions/', RecruiterSubmissionsView.as_view(), name='ats-submissions-list'),
    path('submissions/<uuid:id>/', RecruiterSubmissionDetailView.as_view(), name='ats-submission-detail'),
    path('submissions/<uuid:id>/export/', RecruiterSubmissionExportView.as_view(), name='ats-submission-export'),

    # Client records management (ATS-01)
    path('clients/', RecruiterClientsListView.as_view(), name='ats-clients-list'),
    path('clients/<uuid:id>/', RecruiterClientDetailView.as_view(), name='ats-client-detail'),
]

