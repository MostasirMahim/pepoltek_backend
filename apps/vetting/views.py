from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Avg, Count, Q, Case, When
from django.utils import timezone

from .models import (
    AssessmentTemplate,
    ApplicationVetting,
    VettingAnswer,
    VettingScore,
    Credential,
    ValidatorProfile,
    ValidatorSector,
    ValidatorClearance,
    CredentialStatus,
)
from apps.candidates.models import Candidate, ReadinessTier, VettingStatus
from .serializers import (
    AssessmentTemplateListSerializer,
    AssessmentTemplateDetailSerializer,
    AssessmentTemplateWriteSerializer,
    ApplicationVettingListSerializer,
    ApplicationVettingDetailSerializer,
    ApplicationVettingCreateSerializer,
    ApplicationVettingUpdateSerializer,
    VettingAnswerSerializer,
    VettingAnswerWriteSerializer,
    VettingScoreSerializer,
    VettingScoreWriteSerializer,
    CredentialSerializer,
)
from . import services


# ---------------------------------------------------------------------------
# Helper permission check
# ---------------------------------------------------------------------------

def _is_staff_or_admin(user) -> bool:
    if user.is_superuser or user.is_staff:
        return True
    roles = getattr(user, 'get_roles', lambda: [])()
    return bool({'RECRUITER', 'ADMIN', 'SUPER_ADMIN', 'TECH_VALIDATOR', 'CREDENTIAL_OFFICER'} & set(roles))


# ---------------------------------------------------------------------------
# AssessmentTemplate  -- CRUD for admins/recruiters
# ---------------------------------------------------------------------------

class AssessmentTemplateViewSet(viewsets.ModelViewSet):
    """
    list:   GET  /api/v1/vetting/templates/
    create: POST /api/v1/vetting/templates/
    detail: GET  /api/v1/vetting/templates/{id}/
    update: PATCH /api/v1/vetting/templates/{id}/
    archive: POST /api/v1/vetting/templates/{id}/archive/
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = AssessmentTemplate.objects.filter(archived_at__isnull=True).select_related(
            'created_by'
        ).prefetch_related('vettings')
        sector   = self.request.query_params.get('sector')
        category = self.request.query_params.get('category')
        if sector:
            qs = qs.filter(sector=sector)
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return AssessmentTemplateListSerializer
        if self.action in ('create', 'partial_update'):
            return AssessmentTemplateWriteSerializer
        return AssessmentTemplateDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        template = self.get_object()
        services.archive_assessment_template(instance=template)
        return Response({'detail': 'Template archived.'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# ApplicationVetting  -- assignment management
# ---------------------------------------------------------------------------

class ApplicationVettingViewSet(viewsets.ModelViewSet):
    """
    list:   GET  /api/v1/vetting/vettings/
    create: POST /api/v1/vetting/vettings/
    detail: GET  /api/v1/vetting/vettings/{id}/
    update: PATCH /api/v1/vetting/vettings/{id}/
    answers: GET/POST /api/v1/vetting/vettings/{id}/answers/
    submit_score: POST /api/v1/vetting/vettings/{id}/score/
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs   = ApplicationVetting.objects.select_related(
            'template', 'primary_validator', 'assigned_by',
            'application__candidate__user', 'application__requisition'
        ).prefetch_related('secondary_validators')

        # Filter by ?application=<uuid>
        app_id = self.request.query_params.get('application')
        if app_id:
            qs = qs.filter(application_id=app_id)

        # Filter by ?template=<uuid>
        template_id = self.request.query_params.get('template')
        if template_id:
            qs = qs.filter(template_id=template_id)

        # Validators see only their own assignments unless staff
        if not _is_staff_or_admin(user):
            qs = qs.filter(primary_validator=user) | qs.filter(secondary_validators=user)
        return qs.distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return ApplicationVettingListSerializer
        if self.action == 'create':
            return ApplicationVettingCreateSerializer
        if self.action == 'partial_update':
            return ApplicationVettingUpdateSerializer
        return ApplicationVettingDetailSerializer

    @action(detail=True, methods=['get', 'post'], url_path='answers')
    def answers(self, request, pk=None):
        vetting = self.get_object()
        if request.method == 'GET':
            serializer = VettingAnswerSerializer(
                vetting.answers.all(), many=True, context={'request': request}
            )
            return Response(serializer.data)

        # POST -- submit answer
        serializer = VettingAnswerWriteSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        answer = services.submit_vetting_answer(
            actor                    = request.user,
            vetting                  = vetting,
            criterion_scores         = data.get('criterion_scores', []),
            notes                    = data.get('notes', ''),
            attachments              = data.get('attachments', []),
            candidate_submission_url = data.get('candidate_submission_url', ''),
            candidate_notes          = data.get('candidate_notes', ''),
            is_final_submission      = data.get('is_final_submission', False),
        )
        return Response(
            VettingAnswerSerializer(answer, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get', 'post'], url_path='score')
    def score(self, request, pk=None):
        vetting = self.get_object()
        if request.method == 'GET':
            if not hasattr(vetting, 'score_record'):
                return Response({'detail': 'Not scored yet.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                VettingScoreSerializer(vetting.score_record, context={'request': request}).data
            )

        # POST -- submit final score (primary validator only)
        serializer = VettingScoreWriteSerializer(
            data=request.data,
            context={'request': request, 'vetting': vetting}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        score_record = services.submit_final_score(
            actor    = request.user,
            vetting  = vetting,
            score    = data['score'],
            verdict  = data['verdict'],
            feedback = data.get('feedback', ''),
        )
        return Response(
            VettingScoreSerializer(score_record, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Credential  -- healthcare licence management
# ---------------------------------------------------------------------------

class CredentialViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = CredentialSerializer
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = Credential.objects.select_related('verified_by', 'candidate')
        candidate_id = self.request.query_params.get('candidate')
        if candidate_id:
            qs = qs.filter(candidate_id=candidate_id)
        return qs


# ---------------------------------------------------------------------------
# Validator Workspace Endpoints (Tech & Healthcare Validators)
# ---------------------------------------------------------------------------

class ValidatorDashboardView(APIView):
    """
    GET /api/v1/vetting/validator/dashboard/
    Unified command cockpit for Technical Validators and Healthcare Credential Officers.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        roles = user.get_roles() if hasattr(user, 'get_roles') else []
        is_staff = user.is_superuser or user.is_staff or bool(
            {'TECH_VALIDATOR', 'CREDENTIAL_OFFICER', 'RECRUITER', 'ADMIN', 'SUPER_ADMIN'} & set(roles)
        )
        if not is_staff:
            return Response(
                {'error': {'code': 'FORBIDDEN', 'message': 'Validator privileges required.'}},
                status=status.HTTP_403_FORBIDDEN
            )

        # 1. Fetch or create ValidatorProfile
        is_cred_officer = 'CREDENTIAL_OFFICER' in roles
        profile, _ = ValidatorProfile.objects.get_or_create(
            user=user,
            defaults={
                'sector': ValidatorSector.HEALTHCARE if is_cred_officer else ValidatorSector.TECHNOLOGY,
                'specialization': 'Clinical Licensure & Critical Care' if is_cred_officer else 'Distributed Systems & Architecture',
                'clearance_level': ValidatorClearance.LEVEL_3 if is_cred_officer else ValidatorClearance.LEVEL_2,
                'max_active_assignments': 6,
                'total_evaluations_completed': 0,
                'average_scoring_turnaround_hours': 6.0,
            }
        )

        # 2. Telemetry
        is_admin = user.is_superuser or bool({'ADMIN', 'SUPER_ADMIN'} & set(roles))

        if is_admin:
            tech_assignments_qs = ApplicationVetting.objects.all()
        else:
            tech_assignments_qs = ApplicationVetting.objects.filter(
                Q(primary_validator=user) | Q(secondary_validators=user)
            )

        pending_tech_count = tech_assignments_qs.filter(
            status__in=[
                ApplicationVetting.Status.PENDING,
                ApplicationVetting.Status.IN_PROGRESS,
                ApplicationVetting.Status.SUBMITTED,
            ]
        ).count()

        completed_tech_count = tech_assignments_qs.filter(
            status__in=[
                ApplicationVetting.Status.SCORED,
                ApplicationVetting.Status.PASSED,
                ApplicationVetting.Status.FAILED,
            ]
        ).count()

        avg_score = tech_assignments_qs.filter(final_score__isnull=False).aggregate(
            avg=Avg('final_score')
        )['avg']

        unverified_creds_count = Credential.objects.filter(status=CredentialStatus.UNVERIFIED).count()
        verified_by_user_count = Credential.objects.filter(verified_by=user).count()

        telemetry = {
            'pending_evaluations': pending_tech_count,
            'completed_evaluations': completed_tech_count,
            'pending_credentials': unverified_creds_count,
            'verified_credentials': verified_by_user_count,
            'average_score': round(float(avg_score), 1) if avg_score else None,
            'clearance_level': profile.get_clearance_level_display(),
            'sector': profile.get_sector_display(),
        }

        # 3. Technical Queue Serialized
        tech_records = []
        for vetting in tech_assignments_qs.select_related(
            'application__candidate__user',
            'application__requisition',
            'template',
            'primary_validator'
        ).prefetch_related('answers')[:30]:
            cand = vetting.application.candidate
            req = vetting.application.requisition
            answers_list = []
            for ans in vetting.answers.all().order_by('-created_at')[:3]:
                answers_list.append({
                    'id': str(ans.id),
                    'candidate_submission_url': ans.candidate_submission_url,
                    'candidate_notes': ans.candidate_notes,
                    'notes': ans.notes,
                    'subtotal_score': ans.subtotal_score,
                    'criterion_scores': ans.criterion_scores,
                    'is_final': ans.is_final_submission,
                    'submitted_at': ans.created_at.strftime('%b %d, %Y %H:%M'),
                })

            tech_records.append({
                'id': str(vetting.id),
                'status': vetting.status,
                'status_display': vetting.get_status_display(),
                'pass_threshold': vetting.pass_threshold,
                'final_score': vetting.final_score,
                'decision_notes': vetting.decision_notes,
                'recruiter_notes': vetting.recruiter_notes,
                'scheduled_start': vetting.scheduled_start.strftime('%b %d, %Y') if vetting.scheduled_start else None,
                'started_at': vetting.started_at.strftime('%b %d, %Y') if vetting.started_at else None,
                'completed_at': vetting.completed_at.strftime('%b %d, %Y') if vetting.completed_at else None,
                'is_primary_validator': vetting.primary_validator_id == user.id,
                'template': {
                    'id': str(vetting.template.id),
                    'title': vetting.template.title,
                    'name': vetting.template.title,
                    'sector': vetting.template.sector,
                    'category': vetting.template.category,
                    'total_marks': vetting.template.total_marks,
                    'marks_distribution': vetting.template.marks_distribution,
                    'rubric_criteria': vetting.template.marks_distribution,
                    'instructions': vetting.template.instructions,
                    'description': vetting.template.description,
                },
                'candidate': {
                    'id': str(cand.id),
                    'name': cand.full_name or cand.user.email,
                    'email': cand.user.email,
                    'sector': cand.sector,
                    'level': cand.get_level_display() if hasattr(cand, 'get_level_display') else cand.level,
                    'domain': cand.domain,
                    'readiness_tier': cand.readiness_tier,
                    'portfolio_url': cand.portfolio_url,
                    'github_url': cand.github_url,
                    'linkedin_url': cand.linkedin_url,
                },
                'requisition': {
                    'id': str(req.id),
                    'title': req.title,
                    'sector': req.sector,
                    'target_level': req.level,
                },
                'answers': answers_list,
            })

        # 4. Credential Queue Serialized
        cred_records = []
        cred_qs = Credential.objects.select_related('candidate__user', 'verified_by').order_by(
            Case(
                When(status=CredentialStatus.UNVERIFIED, then=0),
                default=1
            ),
            '-created_at'
        )[:30]

        for cred in cred_qs:
            c = cred.candidate
            cred_records.append({
                'id': str(cred.id),
                'name': cred.name,
                'kind': cred.kind,
                'kind_display': cred.get_kind_display(),
                'license_number': cred.license_number,
                'jurisdiction': cred.jurisdiction,
                'issued_on': str(cred.issued_on) if cred.issued_on else None,
                'expires_on': str(cred.expires_on) if cred.expires_on else None,
                'status': cred.status,
                'status_display': cred.get_status_display(),
                'verification_method': cred.verification_method,
                'rejection_reason': cred.rejection_reason,
                'verified_at': cred.verified_at.strftime('%b %d, %Y %H:%M') if cred.verified_at else None,
                'verified_by': cred.verified_by.full_name or cred.verified_by.email if cred.verified_by else None,
                'candidate': {
                    'id': str(c.id),
                    'name': c.full_name or c.user.email,
                    'email': c.user.email,
                    'sector': c.sector,
                    'level': c.get_level_display() if hasattr(c, 'get_level_display') else c.level,
                    'readiness_tier': c.readiness_tier,
                }
            })

        return Response({
            'data': {
                'profile': {
                    'email': user.email,
                    'full_name': user.full_name or user.email,
                    'roles': roles,
                    'sector': profile.sector,
                    'sector_display': profile.get_sector_display(),
                    'specialization': profile.specialization,
                    'clearance_level': profile.clearance_level,
                    'clearance_display': profile.get_clearance_level_display(),
                    'max_active_assignments': profile.max_active_assignments,
                    'total_evaluations_completed': profile.total_evaluations_completed,
                    'average_scoring_turnaround_hours': profile.average_scoring_turnaround_hours,
                    'bio': profile.bio,
                },
                'telemetry': telemetry,
                'technical_queue': tech_records,
                'credential_queue': cred_records,
            }
        }, status=status.HTTP_200_OK)


class ValidatorGradeView(APIView):
    """
    POST /api/v1/vetting/validator/grade/
    Submit evaluation rubric grade, verdict, qualitative feedback,
    and update candidate readiness tier.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        vetting_id = request.data.get('vetting_id')
        score = request.data.get('score')
        verdict = request.data.get('verdict', '').lower()
        feedback = request.data.get('feedback', '')
        readiness_tier = request.data.get('readiness_tier', '').lower()
        criterion_scores = request.data.get('criterion_scores', [])

        if not vetting_id or score is None:
            return Response(
                {'error': {'code': 'INVALID_INPUT', 'message': 'vetting_id and score are required.'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        vetting = get_object_or_404(
            ApplicationVetting.objects.select_related('application__candidate', 'primary_validator'),
            id=vetting_id
        )

        user = request.user
        roles = set(user.get_roles() if hasattr(user, 'get_roles') else [])
        is_authorized = (
            user.is_superuser
            or vetting.primary_validator_id == user.id
            or bool({'TECH_VALIDATOR', 'ADMIN', 'SUPER_ADMIN'} & roles)
        )
        if not is_authorized:
            return Response(
                {'error': {'code': 'FORBIDDEN', 'message': 'Only the assigned validator or tech assessor may grade.'}},
                status=status.HTTP_403_FORBIDDEN
            )

        score_int = int(score)
        if score_int < 0 or score_int > 100:
            return Response(
                {'error': {'code': 'INVALID_SCORE', 'message': 'Score must be between 0 and 100.'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not verdict:
            verdict = 'pass' if score_int >= vetting.pass_threshold else 'fail'

        # Record answer review breakdown if criterion scores provided
        if criterion_scores:
            services.submit_vetting_answer(
                actor=user,
                vetting=vetting,
                criterion_scores=criterion_scores,
                notes=feedback,
                is_final_submission=True,
            )

        # Create/Update score record
        score_record = services.submit_final_score(
            actor=user,
            vetting=vetting,
            score=score_int,
            verdict=verdict,
            feedback=feedback,
        )

        # Update candidate readiness tier and vetting status
        candidate = vetting.application.candidate
        if verdict == 'pass':
            candidate.vetting_status = VettingStatus.VETTED
            if readiness_tier in [ReadinessTier.READY, ReadinessTier.ELITE, ReadinessTier.EMERGING]:
                candidate.readiness_tier = readiness_tier
            else:
                candidate.readiness_tier = ReadinessTier.ELITE if score_int >= 90 else ReadinessTier.READY
        else:
            candidate.vetting_status = VettingStatus.NOT_SUITABLE
            candidate.readiness_tier = ReadinessTier.EMERGING

        candidate.save(update_fields=['vetting_status', 'readiness_tier', 'updated_at'])

        # Increment validator profile counter
        if hasattr(user, 'validator_profile'):
            user.validator_profile.total_evaluations_completed += 1
            user.validator_profile.save(update_fields=['total_evaluations_completed', 'updated_at'])

        return Response({
            'data': {
                'vetting_id': str(vetting.id),
                'score': score_int,
                'verdict': verdict,
                'status': vetting.status,
                'candidate_readiness_tier': candidate.readiness_tier,
                'candidate_vetting_status': candidate.vetting_status,
                'message': f'Assessment graded successfully: {score_int}/100 ({verdict.upper()}).',
            }
        }, status=status.HTTP_200_OK)


class ValidatorVerifyCredentialView(APIView):
    """
    POST /api/v1/vetting/validator/verify-credential/
    Verify or reject candidate clinical license with primary source auditing evidence.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        credential_id = request.data.get('credential_id')
        target_status = request.data.get('status', '').lower()
        verification_method = request.data.get('verification_method', 'State Board Primary Source Verification')
        rejection_reason = request.data.get('rejection_reason', '')

        if not credential_id or target_status not in ['verified', 'rejected']:
            return Response(
                {'error': {'code': 'INVALID_INPUT', 'message': 'credential_id and status (verified|rejected) are required.'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        cred = get_object_or_404(Credential.objects.select_related('candidate'), id=credential_id)

        user = request.user
        roles = set(user.get_roles() if hasattr(user, 'get_roles') else [])
        is_authorized = (
            user.is_superuser
            or user.is_staff
            or bool({'CREDENTIAL_OFFICER', 'ADMIN', 'SUPER_ADMIN'} & roles)
        )
        if not is_authorized:
            return Response(
                {'error': {'code': 'FORBIDDEN', 'message': 'Credential Officer privileges required.'}},
                status=status.HTTP_403_FORBIDDEN
            )

        cred.status = CredentialStatus.VERIFIED if target_status == 'verified' else CredentialStatus.REJECTED
        cred.verified_by = user
        cred.verified_at = timezone.now()
        cred.verification_method = verification_method
        if rejection_reason:
            cred.rejection_reason = rejection_reason
        cred.save()

        # Update candidate vetting status if verified
        candidate = cred.candidate
        if target_status == 'verified':
            candidate.vetting_status = VettingStatus.VETTED
            if candidate.readiness_tier == ReadinessTier.UNRATED:
                candidate.readiness_tier = ReadinessTier.READY
            candidate.save(update_fields=['vetting_status', 'readiness_tier', 'updated_at'])

        # Increment validator profile counter
        if hasattr(user, 'validator_profile'):
            user.validator_profile.total_evaluations_completed += 1
            user.validator_profile.save(update_fields=['total_evaluations_completed', 'updated_at'])

        return Response({
            'data': {
                'id': str(cred.id),
                'name': cred.name,
                'status': cred.status,
                'status_display': cred.get_status_display(),
                'verified_by': user.full_name or user.email,
                'verified_at': cred.verified_at.isoformat(),
                'verification_method': cred.verification_method,
                'message': f'Credential {cred.name} successfully marked as {cred.get_status_display()}.',
            }
        }, status=status.HTTP_200_OK)


class ValidatorsListView(APIView):
    """
    GET /api/v1/vetting/validators/
    Returns active technical validators and credential officers for vetting assignment.
    Accessible to recruiters, admins, and staff members.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_staff_or_admin(request.user):
            return Response(
                {'error': {'code': 'FORBIDDEN', 'message': 'Staff or recruiter privileges required.'}},
                status=status.HTTP_403_FORBIDDEN
            )

        from apps.accounts.models import User

        profiles = ValidatorProfile.objects.filter(is_active=True).select_related('user')
        profile_map = {p.user_id: p for p in profiles}

        users_qs = User.objects.filter(is_active=True)

        validators_data = []
        for u in users_qs:
            roles = set(u.get_roles() if hasattr(u, 'get_roles') else [])
            has_validator_role = bool({'TECH_VALIDATOR', 'CREDENTIAL_OFFICER'} & roles)
            has_profile = u.id in profile_map

            if has_validator_role or has_profile:
                prof = profile_map.get(u.id)
                sector = prof.sector if prof else ('healthcare' if 'CREDENTIAL_OFFICER' in roles else 'technology')
                specialization = prof.specialization if prof else (
                    'Clinical Licensure & Regulatory Compliance' if sector == 'healthcare' else 'Distributed Systems & Cloud Architecture'
                )
                clearance = prof.get_clearance_level_display() if prof else 'Senior Validator'

                active_assignments = ApplicationVetting.objects.filter(
                    primary_validator=u,
                    status__in=[
                        ApplicationVetting.Status.PENDING,
                        ApplicationVetting.Status.IN_PROGRESS,
                        ApplicationVetting.Status.SUBMITTED,
                    ]
                ).count()

                validators_data.append({
                    'id': str(u.id),
                    'user_id': str(u.id),
                    'email': u.email,
                    'full_name': u.full_name or u.email,
                    'roles': list(roles),
                    'sector': sector,
                    'specialization': specialization,
                    'clearance_level': clearance,
                    'active_assignments': active_assignments,
                })

        return Response({'data': validators_data}, status=status.HTTP_200_OK)



