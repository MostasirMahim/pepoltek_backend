"""
ai_service/urls.py
Endpoints for AI status, search parsing, and test endpoints.
"""
from django.urls import path
from .views import AIStatusView, AINLSearchView, AITestParseView, AICandidateSearchView

app_name = "ai_service"

urlpatterns = [
    path("status/", AIStatusView.as_view(), name="ai-status"),
    path("nl-search/", AINLSearchView.as_view(), name="ai-nl-search"),
    path("candidate-search/", AICandidateSearchView.as_view(), name="ai-candidate-search"),
    path("test-parse/", AITestParseView.as_view(), name="ai-test-parse"),
]

