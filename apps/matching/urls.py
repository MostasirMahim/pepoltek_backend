from django.urls import path
from .views import ReverseSearchView, PitchSubmissionView, CandidatePitchRequestsView

urlpatterns = [
    path('reverse-search/', ReverseSearchView.as_view(), name='matching-reverse-search'),
    path('pitch-requests/', CandidatePitchRequestsView.as_view(), name='matching-pitch-requests'),
    path('pitch/<uuid:id>/', PitchSubmissionView.as_view(), name='matching-pitch-submit'),
]

