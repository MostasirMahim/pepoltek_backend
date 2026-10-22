import hashlib
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
    ReadinessTier,
    Document,
    DocumentType,
    ScanStatus,
)
from .serializers import (
    CandidateProfileSerializer,
    CandidateApplicationItemSerializer,
    CandidateIntakeSerializer,
)
from apps.ats.models import Application

User = get_user_model()


class CandidateMeView(APIView):
    """
    GET/PUT/PATCH /api/v1/candidates/me/
    Retrieve or update profile and readiness stats for the authenticated candidate.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'data': None})

        candidate, _ = Candidate.objects.get_or_create(
            user=request.user,
            defaults={
                'full_name': request.user.full_name or request.user.email.split('@')[0],
                'sector': SectorChoice.TECHNOLOGY,
                'level': ExperienceLevel.SENIOR,
                'readiness_tier': ReadinessTier.READY,
                'profile_strength': 85,
                'open_to_work': True,
            }
        )
        serializer = CandidateProfileSerializer(candidate)
        return Response({'data': serializer.data})

    def patch(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        candidate = get_object_or_404(Candidate, user=request.user)
        serializer = CandidateProfileSerializer(candidate, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'data': serializer.data})


class CandidateApplicationsView(APIView):
    """
    GET /api/v1/candidates/applications/
    Retrieve application pipeline entries for candidate dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'data': []})

        candidate = Candidate.objects.filter(user=request.user).first()
        if not candidate:
            return Response({'data': []})

        applications = Application.objects.filter(candidate=candidate).select_related('requisition', 'requisition__client')
        serializer = CandidateApplicationItemSerializer(applications, many=True)
        return Response({'data': serializer.data})


class CandidatePitchToggleView(APIView):
    """
    PATCH /api/v1/candidates/pitch/
    Toggle anonymous pitch authorization.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        authorized = request.data.get('authorized', True)
        if request.user.is_authenticated:
            candidate = Candidate.objects.filter(user=request.user).first()
            if candidate:
                candidate.open_to_work = bool(authorized)
                candidate.save(update_fields=['open_to_work', 'updated_at'])

        return Response({
            'data': {
                'open_to_work': bool(authorized),
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

        # Map salary
        expected_comp = None
        if data.get('expected_salary'):
            try:
                expected_comp = int(float(data['expected_salary']))
            except (ValueError, TypeError):
                pass

        # Candidate profile
        candidate, _ = Candidate.objects.get_or_create(
            user=user,
            defaults={
                'full_name': full_name,
                'sector': sector,
                'level': level,
                'phone': data.get('phone', ''),
                'location': data.get('current_location', ''),
                'domain': data.get('current_job_title', ''),
                'work_auth': work_auth,
                'engagement_prefs': data.get('engagement_prefs', []),
                'expected_comp_min': expected_comp,
                'expected_comp_max': expected_comp,
                'linkedin_url': data.get('linkedin_profile', ''),
                'open_to_work': data.get('profile_visible', True),
                'profile_strength': 85,
                'readiness_tier': ReadinessTier.READY,
            }
        )

        # Update candidate fields if already existing
        candidate.full_name = full_name
        candidate.sector = sector
        candidate.level = level
        if data.get('phone'):
            candidate.phone = data['phone']
        if data.get('current_location'):
            candidate.location = data['current_location']
        if data.get('current_job_title'):
            candidate.domain = data['current_job_title']
        if work_auth:
            candidate.work_auth = work_auth
        if data.get('engagement_prefs'):
            candidate.engagement_prefs = data['engagement_prefs']
        if expected_comp:
            candidate.expected_comp_min = expected_comp
            candidate.expected_comp_max = expected_comp
        if data.get('linkedin_profile'):
            candidate.linkedin_url = data['linkedin_profile']
        candidate.open_to_work = data.get('profile_visible', True)
        candidate.save()

        # Handle file upload if present
        cv_file = request.FILES.get('cv')
        if cv_file:
            content = cv_file.read()
            file_hash = hashlib.sha256(content).hexdigest()
            Document.objects.create(
                candidate=candidate,
                doc_type=DocumentType.RESUME,
                storage_key=f'resumes/{candidate.id}/{cv_file.name}',
                original_filename=cv_file.name,
                mime_type=cv_file.content_type or 'application/octet-stream',
                size_bytes=cv_file.size,
                sha256=file_hash,
                scan_status=ScanStatus.CLEAN,
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
