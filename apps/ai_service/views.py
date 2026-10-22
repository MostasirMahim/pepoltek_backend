"""
ai_service/views.py
Staff and recruiter inspection and test endpoints for the AI multi-provider system.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

from .services import get_ai_status, nl_query_to_filter, parse_resume


class AIStatusView(APIView):
    """
    GET /api/v1/ai/status/
    Returns real-time status, active failover priority, and detected API keys.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report = get_ai_status()
        return Response(report, status=status.HTTP_200_OK)


class AINLSearchView(APIView):
    """
    POST /api/v1/ai/nl-search/
    Parses natural language recruiter search query into structured filter chips.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get("query", "").strip()
        if not query:
            return Response({"error": "Query string is required."}, status=status.HTTP_400_BAD_REQUEST)
        filters = nl_query_to_filter(query)
        return Response({"query": query, "filters": filters}, status=status.HTTP_200_OK)


class AITestParseView(APIView):
    """
    POST /api/v1/ai/test-parse/
    Test CV parsing against the prioritized AI failover chain.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        raw_text = request.data.get("text", "").strip()
        if not raw_text:
            return Response({"error": "Resume text is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            parsed = parse_resume(raw_text=raw_text, document_id="TEST-INSPECTION")
            return Response(parsed, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
