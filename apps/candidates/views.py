"""
candidates/views.py
DRF views for candidate workspace, profile CRUD, aggregated dashboard,
credentials, documents, applications, pitch toggle, and GDPR data rights.
Views call services and selectors.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import (
    Candidate,
    SectorChoice,
    ExperienceLevel,
    WorkAuth,
    DocumentType,
)
from .serializers import (
    CandidateProfileSerializer,
    CandidateApplicationItemSerializer,
    CandidateIntakeSerializer,
    CandidateCredentialSerializer,
    CandidateCreateCredentialSerializer,
    CandidateDocumentSerializer,
)
from . import selectors
from . import services
from apps.ats.models import Application

User = get_user_model()


class CandidateMeView(APIView):
    """
    GET/PATCH /api/v1/candidates/me/
    Retrieve or update profile and readiness stats for the authenticated candidate.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        serializer = CandidateProfileSerializer(candidate)
        return Response({'data': serializer.data})

    def patch(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        updated_candidate = services.update_candidate_profile(
            candidate=candidate,
            data=request.data,
            user=request.user,
            request=request,
        )
        serializer = CandidateProfileSerializer(updated_candidate)
        return Response({'data': serializer.data})


class CandidateDashboardAggregationView(APIView):
    """
    GET /api/v1/candidates/me/dashboard/
    Retrieve aggregated cockpit telemetry, profile strength, next best action,
    pipeline statistics, and upcoming interview calls (SRS CAN-08).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        dashboard_data = selectors.get_candidate_dashboard_aggregation(candidate)
        return Response({'data': dashboard_data})


class CandidateCredentialsView(APIView):
    """
    GET/POST /api/v1/candidates/me/credentials/
    List or add professional licenses and certifications (SRS CAN-04, VET-04).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        credentials = selectors.get_candidate_credentials(candidate)
        serializer = CandidateCredentialSerializer(credentials, many=True)
        return Response({'data': serializer.data})

    def post(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        validator = CandidateCreateCredentialSerializer(data=request.data)
        validator.is_valid(raise_exception=True)

        credential = services.create_candidate_credential(
            candidate=candidate,
            data=validator.validated_data,
            user=request.user,
            request=request,
        )
        serializer = CandidateCredentialSerializer(credential)
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)


class CandidateCredentialDetailView(APIView):
    """
    DELETE /api/v1/candidates/me/credentials/<uuid:id>/
    Delete a candidate license or certification.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        candidate = selectors.get_candidate_for_user(request.user)
        deleted = services.delete_candidate_credential(
            candidate=candidate,
            credential_id=id,
            user=request.user,
            request=request,
        )
        if not deleted:
            return Response({'error': 'Credential not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'data': {'success': True, 'message': 'Credential deleted successfully.'}})


class CandidateDocumentsView(APIView):
    """
    GET/POST /api/v1/candidates/me/documents/
    List or upload candidate CVs, resumes, or certificates (SRS CAN-09, PAR-01).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        documents = selectors.get_candidate_documents(candidate)
        serializer = CandidateDocumentSerializer(documents, many=True)
        return Response({'data': serializer.data})

    def post(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        file_obj = request.FILES.get('file') or request.FILES.get('cv')
        if not file_obj:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        doc_type = request.data.get('doc_type', DocumentType.RESUME)
        doc = services.create_candidate_document(
            candidate=candidate,
            file_obj=file_obj,
            doc_type=doc_type,
            user=request.user,
            request=request,
        )
        serializer = CandidateDocumentSerializer(doc)
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)


class CandidateDocumentDetailView(APIView):
    """
    DELETE /api/v1/candidates/me/documents/<uuid:id>/
    Delete a candidate document.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        candidate = selectors.get_candidate_for_user(request.user)
        deleted = services.delete_candidate_document(
            candidate=candidate,
            document_id=id,
            user=request.user,
            request=request,
        )
        if not deleted:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'data': {'success': True, 'message': 'Document deleted successfully.'}})


class CandidateExportDataView(APIView):
    """
    POST /api/v1/candidates/me/export/
    GDPR right to data portability (SRS CAN-09).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        export_payload = services.export_candidate_data(
            candidate=candidate,
            user=request.user,
            request=request,
        )
        return Response({'data': export_payload})


class CandidateDeleteRequestView(APIView):
    """
    POST /api/v1/candidates/me/delete-request/
    GDPR right to erasure (SRS CAN-09).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        reason = request.data.get('reason', 'GDPR user-requested account deletion')
        result = services.request_candidate_deletion(
            candidate=candidate,
            reason=reason,
            user=request.user,
            request=request,
        )
        return Response({'data': result})


class CandidateApplicationsView(APIView):
    """
    GET /api/v1/candidates/applications/
    Retrieve application pipeline entries for candidate dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        applications = Application.objects.filter(candidate=candidate).select_related(
            'requisition', 'requisition__client'
        )
        serializer = CandidateApplicationItemSerializer(applications, many=True)
        return Response({'data': serializer.data})


class CandidatePitchToggleView(APIView):
    """
    PATCH /api/v1/candidates/pitch/
    Toggle anonymous pitch authorization.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        candidate = selectors.get_candidate_for_user(request.user)
        authorized = request.data.get('authorized', True)
        updated_candidate = services.toggle_open_to_work(
            candidate=candidate,
            open_to_work=authorized,
            user=request.user,
            request=request,
        )

        return Response({
            'data': {
                'open_to_work': updated_candidate.open_to_work,
                'message': 'Pitch authorization status updated.',
            }
        })


class CandidateIntakeView(APIView):
    """
    POST /api/v1/candidates/intake/
    Public or authenticated intake for candidates joining the talent network.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = CandidateIntakeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data['email'].strip().lower()
        full_name = data['full_name'].strip()

        # Find or create user
        if request.user.is_authenticated:
            user = request.user
        else:
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(email=email, full_name=full_name)

        # Map sector
        sector_val = str(data.get('sector', 'technology')).lower()
        if 'health' in sector_val:
            sector = SectorChoice.HEALTHCARE
        else:
            sector = SectorChoice.TECHNOLOGY

        # Map experience level
        level_val = str(data.get('level', 'senior')).lower()
        valid_levels = [c[0] for c in ExperienceLevel.choices]
        level = level_val if level_val in valid_levels else ExperienceLevel.SENIOR

        # Map work auth
        work_auth_val = str(data.get('work_auth', '')).lower()
        valid_auths = [c[0] for c in WorkAuth.choices]
        work_auth = work_auth_val if work_auth_val in valid_auths else ''

        candidate = selectors.get_candidate_for_user(user)
        services.update_candidate_profile(
            candidate=candidate,
            data={
                'full_name': full_name,
                'sector': sector,
                'level': level,
                'phone': data.get('phone', ''),
                'location': data.get('current_location', ''),
                'domain': data.get('current_job_title', ''),
                'work_auth': work_auth,
                'engagement_prefs': data.get('engagement_prefs', []),
                'linkedin_url': data.get('linkedin_profile', ''),
                'open_to_work': data.get('profile_visible', True),
            },
            user=user,
            request=request,
        )

        # Handle file upload if present
        cv_file = request.FILES.get('cv')
        if cv_file:
            services.create_candidate_document(
                candidate=candidate,
                file_obj=cv_file,
                doc_type=DocumentType.RESUME,
                user=user,
                request=request,
            )

        return Response({
            'data': {
                'candidate_id': str(candidate.id),
                'full_name': candidate.full_name,
                'sector': candidate.sector,
                'level': candidate.level,
                'status': 'submitted',
                'message': 'Profile and CV successfully submitted to talent network.',
            }
        }, status=status.HTTP_201_CREATED)
