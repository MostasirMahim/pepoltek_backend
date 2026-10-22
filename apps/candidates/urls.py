from django.urls import path
from .views import (
    CandidateMeView,
    CandidateApplicationsView,
    CandidatePitchToggleView,
    CandidateIntakeView,
)

urlpatterns = [
    path('me/', CandidateMeView.as_view(), name='candidate-me'),
    path('applications/', CandidateApplicationsView.as_view(), name='candidate-applications'),
    path('pitch/', CandidatePitchToggleView.as_view(), name='candidate-pitch-toggle'),
    path('intake/', CandidateIntakeView.as_view(), name='candidate-intake'),
]

