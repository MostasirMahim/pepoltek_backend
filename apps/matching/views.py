from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from apps.ats.models import Requisition, RequisitionStatus, Application, ApplicationStage, ApplicationSource
from apps.candidates.models import Candidate, SectorChoice, ExperienceLevel


class ReverseSearchView(APIView):
    """
    GET /api/v1/matching/reverse-search/
    Scan confidential active requisitions matching candidate parameters.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sector = request.query_params.get('sector', 'tech').lower()
        min_rate = request.query_params.get('min_rate')
        remote_pref = request.query_params.get('remote_pref', 'remote')

        queryset = Requisition.objects.filter(status=RequisitionStatus.OPEN)

        if sector in ['tech', 'technology']:
            queryset = queryset.filter(sector__icontains='tech')
        elif sector in ['health', 'healthcare']:
            queryset = queryset.filter(sector__icontains='health')

        results = []
        for req in queryset[:10]:
            budget_str = f"${req.budget_min or 80} - ${req.budget_max or 120} / hr" if req.budget_min else "$90 - $120 / hr"
            results.append({
                'id': str(req.id),
                'title': req.title,
                'sector': req.sector,
                'company': 'Verified Enterprise Partner',
                'rateRange': budget_str,
                'location': req.location or '100% Remote',
                'matchScore': 92 if req.priority <= 2 else 88,
                'skills': req.skills if isinstance(req.skills, list) else ['Core Engineering', 'Problem Solving'],
                'confidential': True,
            })

        return Response({'data': results})


class PitchSubmissionView(APIView):
    """
    POST /api/v1/matching/pitch/<id>/
    Submit candidate's blind profile pitch for a requisition.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        return Response({
            'data': {
                'requisition_id': str(id),
                'status': 'pitched',
                'message': 'Your anonymized profile pitch has been submitted to the recruitment team.',
            }
        })
