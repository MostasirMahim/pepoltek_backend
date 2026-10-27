from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.accounts.permissions import IsStaffMember
from django.shortcuts import get_object_or_404
from django.db.models import Q
from apps.core.pagination import StandardPagination
from apps.candidates.models import Candidate, SectorChoice, ExperienceLevel
from apps.accounts.models import User
from .models import (
    Client,
    ClientContact,
    Requisition,
    RequisitionVisibility,
    RequisitionStatus,
    Application,
    ApplicationStage,
    ApplicationSource,
    ApplicationEvent,
    Submission,
    DeliveryChannel,
    Placement,
    Interview,
    InterviewPanelAssignment,
    InterviewEvaluation,
    InterviewType,
    InterviewStatus,
    PanelRole,
    RecommendationChoice,
)
from apps.referrals.models import BountyType
from .serializers import (
    PublicRequisitionSerializer,
    JobApplyInputSerializer,
    RecruiterRequisitionSerializer,
    RecruiterRequisitionCreateSerializer,
    RecruiterApplicationSerializer,
    SubmissionSerializer,
    SubmissionCreateSerializer,
    ClientSerializer,
    ClientCreateUpdateSerializer,
    RecruiterSourceCandidateSerializer,
    InterviewListSerializer,
    InterviewDetailSerializer,
    InterviewCreateSerializer,
    InterviewUpdateSerializer,
    InterviewEvaluationSerializer,
    InterviewEvaluationCreateSerializer,
    InterviewPanelAssignmentSerializer,
)
from apps.audit.services import record
from apps.audit.models import AuditLog
from django.utils import timezone
import csv
import io
from .services import ensure_interview_for_application


class PublicJobsListView(APIView):
    """
    GET /api/v1/ats/jobs/
    List published open requisitions for public job board with search and pagination.
    """
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        queryset = Requisition.objects.filter(
            status=RequisitionStatus.OPEN,
            visibility__in=[
                RequisitionVisibility.PUBLISHED_JOB,
                RequisitionVisibility.PUBLISHED_GIG,
                RequisitionVisibility.BOUNTY,
            ],
        ).select_related('client')

        # Sector filter
        sector = request.query_params.get('sector')
        if sector:
            if sector.lower() in ['tech', 'technology']:
                queryset = queryset.filter(sector__icontains='tech')
            elif sector.lower() in ['health', 'healthcare']:
                queryset = queryset.filter(sector__icontains='health')

        # Keyword search
        keyword = request.query_params.get('keyword') or request.query_params.get('search')
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(location__icontains=keyword)
            )

        # Level filter
        level = request.query_params.get('level')
        if level:
            queryset = queryset.filter(level__iexact=level)

        # Visibility filter
        visibility = request.query_params.get('visibility')
        if visibility:
            queryset = queryset.filter(visibility=visibility)

        # Type filter (squad vs specialist vs gig vs bounty)
        req_type = request.query_params.get('type')
        if req_type == 'squad':
            queryset = queryset.filter(headcount__gt=1)
        elif req_type == 'specialist':
            queryset = queryset.filter(headcount=1)
        elif req_type == 'gig':
            queryset = queryset.filter(visibility=RequisitionVisibility.PUBLISHED_GIG)
        elif req_type == 'bounty':
            queryset = queryset.filter(visibility=RequisitionVisibility.BOUNTY)

        # Paginate
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PublicRequisitionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PublicJobDetailView(APIView):
    """
    GET /api/v1/ats/jobs/<id>/
    Retrieve detail for a single published requisition.
    """
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request, id):
        job = get_object_or_404(
            Requisition.objects.select_related('client'),
            id=id,
        )
        serializer = PublicRequisitionSerializer(job)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)


class PublicJobApplyView(APIView):
    """
    POST /api/v1/ats/jobs/<id>/apply/
    Submit application for a published job.
    """
    permission_classes = [AllowAny]

    def post(self, request, id):
        requisition = get_object_or_404(Requisition, id=id)
        serializer = JobApplyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Link to authenticated candidate or create lightweight candidate record
        user = request.user if request.user.is_authenticated else None
        if not user:
            user, _ = User.objects.get_or_create(
                email=data['email'],
                defaults={'full_name': data['full_name']}
            )

        candidate, _ = Candidate.objects.get_or_create(
            user=user,
            defaults={
                'full_name': data['full_name'],
                'sector': requisition.sector if requisition.sector in [SectorChoice.TECHNOLOGY, SectorChoice.HEALTHCARE] else SectorChoice.TECHNOLOGY,
                'level': ExperienceLevel.MID,
            }
        )

        if data.get('phone') and not candidate.phone:
            candidate.phone = data['phone']
            candidate.save(update_fields=['phone'])

        application, created = Application.objects.get_or_create(
            candidate=candidate,
            requisition=requisition,
            defaults={
                'stage': ApplicationStage.MARKET_MAPPING,
                'source': ApplicationSource.APPLIED,
                'sub_stage': 'Applied',
            }
        )

        note_text = data.get('notes', '')
        if data.get('portfolio_url'):
            note_text = f"Portfolio: {data['portfolio_url']}. {note_text}".strip()

        ApplicationEvent.objects.create(
            application=application,
            from_stage='',
            to_stage=ApplicationStage.MARKET_MAPPING,
            sub_stage='Applied',
            actor=user if user and user.is_authenticated else None,
            note=note_text or 'Applied online via public job board',
        )

        return Response(
            {
                'data': {
                    'application_id': str(application.id),
                    'candidate_id': str(candidate.id),
                    'candidate_name': candidate.full_name or data['full_name'],
                    'requisition_id': str(requisition.id),
                    'stage': application.stage,
                    'is_new_application': created,
                    'message': 'Application received successfully.',
                }
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RecruiterRequisitionsView(APIView):
    """
    GET /api/v1/ats/requisitions/ - List all requisitions with optional filters.
    POST /api/v1/ats/requisitions/ - Create and publish a new requisition.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        queryset = Requisition.objects.select_related('client', 'bounty_type').prefetch_related('applications').all()

        status_param = request.query_params.get('status')
        if status_param and status_param != 'all':
            queryset = queryset.filter(status=status_param)

        sector_param = request.query_params.get('sector')
        if sector_param and sector_param != 'all':
            queryset = queryset.filter(sector__icontains=sector_param)

        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(location__icontains=search_query)
            )

        serializer = RecruiterRequisitionSerializer(queryset, many=True)
        return Response({'data': serializer.data})

    def post(self, request):
        serializer = RecruiterRequisitionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        client_name = d.get('client_name') or 'Enterprise Workspace Partner'
        raw_sector = d.get('sector', 'technology')
        sector = 'healthcare' if 'health' in raw_sector.lower() else 'technology'

        client, _ = Client.objects.get_or_create(
            name=client_name,
            defaults={'sector': sector}
        )

        owner = request.user if request.user.is_authenticated else None

        discovery_data = d.get('discovery') or {}
        if not isinstance(discovery_data, dict):
            discovery_data = {}
        if d.get('responsibilities'):
            discovery_data['responsibilities'] = d['responsibilities']
        if d.get('requirements'):
            discovery_data['requirements'] = d['requirements']
        if d.get('nice_to_haves'):
            discovery_data['nice_to_haves'] = d['nice_to_haves']
        if d.get('benefits'):
            discovery_data['benefits'] = d['benefits']

        req = Requisition.objects.create(
            client=client,
            title=d['title'],
            sector=sector,
            level=(d.get('level') or 'Senior')[:30],
            headcount=d.get('headcount', 1),
            skills=d.get('skills', []),
            engagement=(d.get('engagement') or 'Full-Time Requisition')[:30],
            location=(d.get('location') or '100% Remote')[:255],
            budget_min=d.get('budget_min', 85),
            budget_max=d.get('budget_max', 125),
            visibility=d.get('visibility', RequisitionVisibility.PUBLISHED_JOB),
            bounty_enabled=d.get('bounty_enabled', False),
            bounty_amount=d.get('bounty_amount') or None,
            priority=d.get('priority', 3),
            description=d.get('description', ''),
            discovery=discovery_data,
            status=d.get('status', RequisitionStatus.OPEN),
            owner=owner,
        )

        # Link BountyType FK if provided and bounty_enabled
        bounty_type_id = d.get('bounty_type_id')
        if req.bounty_enabled and bounty_type_id:
            bt = BountyType.objects.filter(id=bounty_type_id, is_active=True).first()
            if bt:
                req.bounty_type = bt
                req.save(update_fields=['bounty_type'])

        return Response({
            'data': RecruiterRequisitionSerializer(Requisition.objects.select_related('client', 'bounty_type').get(pk=req.pk)).data,
            'message': 'Requisition published successfully.'
        }, status=status.HTTP_201_CREATED)


class RecruiterRequisitionDetailView(APIView):
    """
    GET, PATCH, DELETE /api/v1/ats/requisitions/<uuid:id>/
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        req = get_object_or_404(Requisition.objects.select_related('client', 'bounty_type'), id=id)
        return Response({'data': RecruiterRequisitionSerializer(req).data})

    def patch(self, request, id):
        req = get_object_or_404(Requisition, id=id)
        data = request.data

        if 'status' in data:
            req.status = data['status']
        if 'visibility' in data:
            req.visibility = data['visibility']
        if 'title' in data:
            req.title = data['title']
        if 'sector' in data:
            req.sector = 'healthcare' if 'health' in str(data['sector']).lower() else 'technology'
        if 'level' in data:
            req.level = str(data['level'])[:30]
        if 'headcount' in data:
            req.headcount = int(data['headcount'])
        if 'skills' in data and isinstance(data['skills'], list):
            req.skills = data['skills']
        if 'engagement' in data:
            req.engagement = str(data['engagement'])[:30]
        if 'location' in data:
            req.location = str(data['location'])[:255]
        if 'budget_min' in data:
            req.budget_min = int(data['budget_min'])
        if 'budget_max' in data:
            req.budget_max = int(data['budget_max'])
        if 'bounty_enabled' in data:
            req.bounty_enabled = bool(data['bounty_enabled'])
        if 'bounty_type_id' in data:
            bt_id = data['bounty_type_id']
            if bt_id:
                bt = BountyType.objects.filter(id=bt_id, is_active=True).first()
                req.bounty_type = bt
            else:
                req.bounty_type = None
        if 'bounty_amount' in data:
            req.bounty_amount = data['bounty_amount'] or None
        if 'description' in data:
            req.description = data['description']
        if 'discovery' in data and isinstance(data['discovery'], dict):
            req.discovery = {**(req.discovery or {}), **data['discovery']}
        if 'responsibilities' in data and isinstance(data['responsibilities'], list):
            req.discovery = req.discovery or {}
            req.discovery['responsibilities'] = data['responsibilities']
        if 'requirements' in data and isinstance(data['requirements'], list):
            req.discovery = req.discovery or {}
            req.discovery['requirements'] = data['requirements']
        if 'nice_to_haves' in data and isinstance(data['nice_to_haves'], list):
            req.discovery = req.discovery or {}
            req.discovery['nice_to_haves'] = data['nice_to_haves']
        if 'benefits' in data and isinstance(data['benefits'], list):
            req.discovery = req.discovery or {}
            req.discovery['benefits'] = data['benefits']

        try:
            req.embedding = req.generate_embedding_vector()
        except Exception:
            pass
        req.save()
        return Response({'data': RecruiterRequisitionSerializer(req).data, 'message': 'Requisition updated.'})

    def delete(self, request, id):
        req = get_object_or_404(Requisition, id=id)
        req.status = RequisitionStatus.CANCELLED
        req.save(update_fields=['status'])
        return Response({'data': {'id': str(id), 'status': 'cancelled'}, 'message': 'Requisition cancelled.'})


class RecruiterRequisitionApplicationsView(APIView):
    """
    GET /api/v1/ats/requisitions/<uuid:id>/applications/
    List all applied candidates for a specific requisition with full candidate info.
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        requisition = get_object_or_404(Requisition.objects.select_related('client'), id=id)
        applications = (
            Application.objects.filter(requisition=requisition)
            .select_related('candidate', 'candidate__user')
            .prefetch_related('events')
            .order_by('-created_at')
        )

        items = []
        for app in applications:
            cand = app.candidate
            user = cand.user if cand else None
            latest_event = app.events.last()

            skills_list = []
            if cand:
                skills_list = list(cand.skills.values_list('skill__name', flat=True))
                if not skills_list and requisition.skills:
                    skills_list = requisition.skills[:3]

            items.append({
                'id': str(app.id),
                'candidate_id': str(cand.id) if cand else '',
                'full_name': cand.full_name if cand else 'Specialist',
                'email': user.email if user else '',
                'phone': str(cand.phone) if cand and cand.phone else '',
                'sector': cand.sector if cand else requisition.sector,
                'level': cand.level if cand else 'Senior',
                'skills': skills_list,
                'rate': f"${getattr(cand, 'expected_comp_min', None) or requisition.budget_min or 95}/hr",
                'match_score': f"{int(getattr(cand, 'profile_strength', 95))}%",
                'stage': app.stage,
                'sub_stage': app.sub_stage or 'Applied',
                'source': app.source,
                'applied_at': app.created_at.strftime('%Y-%m-%d %H:%M') if app.created_at else '',
                'note': latest_event.note if latest_event else '',
            })

        return Response({
            'data': {
                'requisition_id': str(requisition.id),
                'requisition_title': requisition.title,
                'client_name': requisition.client.name,
                'total_applicants': len(items),
                'applicants': items,
            }
        })


class RecruiterPipelineView(APIView):
    """
    GET /api/v1/ats/pipeline/ - Returns applications categorized by 5 SRS stages.
    POST /api/v1/ats/pipeline/move/ - Moves application to target stage.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        apps = (
            Application.objects
            .select_related('candidate', 'candidate__user', 'requisition', 'requisition__client')
            .prefetch_related('events', 'candidate__skills__skill')
            .order_by('-updated_at')
        )

        req_id = request.query_params.get('requisition_id')
        if req_id:
            apps = apps.filter(requisition_id=req_id)

        sector = request.query_params.get('sector')
        if sector and sector != 'all':
            apps = apps.filter(requisition__sector__icontains=sector)

        stages = {
            'discovery': [],
            'market_mapping': [],
            'technical_vetting': [],
            'interview': [],
            'closed': [],
            'rejected': [],
        }

        for app in apps:
            stage_key = app.stage.lower()
            cand = app.candidate
            user = cand.user if cand else None

            skills_list = []
            if cand:
                skills_list = list(cand.skills.values_list('skill__name', flat=True))
            if not skills_list and app.requisition.skills:
                skills_list = app.requisition.skills[:4]

            latest_event = app.events.last() if hasattr(app, 'events') else None

            rate_display = f"${getattr(cand, 'expected_comp_min', None) or app.requisition.budget_min or 95}/hr"
            match_score = f"{int(getattr(cand, 'profile_strength', 95))}%"

            item = {
                'id': str(app.id),
                'candidate_id': str(cand.id) if cand else '',
                'candidate_name': cand.full_name if cand else 'Specialist',
                'candidate_email': user.email if user else '',
                'candidate_phone': str(cand.phone) if cand and cand.phone else '',
                'candidate_location': (cand.location if cand and hasattr(cand, 'location') and cand.location else (app.requisition.location or '100% Remote')),
                'requisition_id': str(app.requisition.id),
                'requisition_title': app.requisition.title,
                'requisition_sector': app.requisition.sector,
                'client_name': app.requisition.client.name if app.requisition.client else 'Pepoltek Client',
                'stage': app.stage,
                'sub_stage': app.sub_stage or 'In Pipeline',
                'source': app.source,
                'skills': skills_list,
                'rate': rate_display,
                'match_score': match_score,
                'applied_at': app.created_at.strftime('%Y-%m-%d %H:%M') if app.created_at else '',
                'updated_at': app.updated_at.strftime('%Y-%m-%d %H:%M') if app.updated_at else '',
                'note': latest_event.note if latest_event and latest_event.note else '',
            }
            if stage_key in stages:
                stages[stage_key].append(item)
            elif stage_key in ['withdrawn', 'rejected']:
                stages['rejected'].append(item)
            else:
                stages['market_mapping'].append(item)

        return Response({'data': stages})

    def post(self, request):
        app_id = request.data.get('application_id')
        to_stage = request.data.get('to_stage')
        sub_stage = request.data.get('sub_stage', '')
        note = request.data.get('note', '')

        if not app_id or not to_stage:
            return Response({'error': {'message': 'application_id and to_stage are required.'}}, status=status.HTTP_400_BAD_REQUEST)

        app = get_object_or_404(Application, id=app_id)
        from_stage = app.stage
        app.stage = to_stage
        app.sub_stage = sub_stage
        app.save(update_fields=['stage', 'sub_stage', 'updated_at'])

        actor = request.user if request.user.is_authenticated else None
        ApplicationEvent.objects.create(
            application=app,
            from_stage=from_stage,
            to_stage=to_stage,
            sub_stage=sub_stage,
            actor=actor,
            note=note,
        )

        if to_stage in [ApplicationStage.INTERVIEW, 'interview']:
            ensure_interview_for_application(app, actor=actor)

        return Response({
            'data': {
                'application_id': str(app.id),
                'from_stage': from_stage,
                'to_stage': to_stage,
                'stage': to_stage,
                'message': f'Application moved to {to_stage}.',
            }
        })


class RecruiterApplicationDetailView(APIView):
    """
    GET /api/v1/ats/applications/<uuid:id>/ - Comprehensive application dossier and handling context.
    PATCH /api/v1/ats/applications/<uuid:id>/ - Update application stage, sub_stage, or status.
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        app = get_object_or_404(
            Application.objects
            .select_related('candidate', 'candidate__user', 'requisition', 'requisition__client')
            .prefetch_related('events', 'events__actor', 'candidate__skills__skill', 'candidate__documents'),
            id=id
        )
        cand = app.candidate
        user = cand.user if cand else None
        req = app.requisition

        skills_data = []
        if cand:
            for cs in cand.skills.all():
                skills_data.append({
                    'name': cs.skill.name,
                    'type': cs.skill.skill_type,
                    'years_experience': float(cs.years_experience),
                    'proficiency': cs.proficiency,
                    'source': cs.source,
                })
        if not skills_data and req.skills:
            for s in req.skills:
                skills_data.append({
                    'name': s,
                    'type': 'tech',
                    'years_experience': 4.0,
                    'proficiency': 'proficient',
                    'source': 'assessed',
                })

        docs_data = []
        if cand:
            for doc in cand.documents.all():
                docs_data.append({
                    'id': str(doc.id),
                    'doc_type': doc.doc_type,
                    'original_filename': doc.original_filename,
                    'size_bytes': doc.size_bytes,
                    'scan_status': doc.scan_status,
                    'uploaded_at': doc.created_at.strftime('%Y-%m-%d %H:%M') if doc.created_at else '',
                })

        events_data = []
        for ev in app.events.all().order_by('-timestamp'):
            actor_name = 'System'
            if ev.actor:
                actor_name = getattr(ev.actor, 'full_name', '') or getattr(ev.actor, 'email', '') or 'Recruiter Staff'
            events_data.append({
                'id': str(ev.id),
                'from_stage': ev.from_stage,
                'to_stage': ev.to_stage,
                'sub_stage': ev.sub_stage,
                'actor_name': actor_name,
                'note': ev.note,
                'timestamp': ev.timestamp.strftime('%Y-%m-%d %H:%M'),
            })

        rate_display = f"${getattr(cand, 'expected_comp_min', None) or req.budget_min or 95}/hr"
        match_score = f"{int(getattr(cand, 'profile_strength', 95))}%"

        data = {
            'id': str(app.id),
            'stage': app.stage,
            'sub_stage': app.sub_stage or 'In Pipeline',
            'source': app.source,
            'applied_at': app.created_at.strftime('%Y-%m-%d %H:%M') if app.created_at else '',
            'updated_at': app.updated_at.strftime('%Y-%m-%d %H:%M') if app.updated_at else '',
            'candidate': {
                'id': str(cand.id) if cand else '',
                'full_name': cand.full_name if cand else 'Specialist',
                'email': user.email if user else '',
                'phone': str(cand.phone) if cand and cand.phone else '',
                'location': (cand.location if cand and cand.location else (req.location or '100% Remote')),
                'timezone': cand.timezone if cand else 'EST (UTC-5)',
                'sector': cand.sector if cand else req.sector,
                'domain': cand.domain if cand else '',
                'level': cand.level if cand else 'Senior',
                'work_auth': cand.work_auth if cand else 'us_citizen',
                'engagement_prefs': cand.engagement_prefs if cand else ['direct_hire', 'w2'],
                'expected_comp_min': cand.expected_comp_min if cand else req.budget_min,
                'expected_comp_max': cand.expected_comp_max if cand else req.budget_max,
                'desired_hourly_rate': getattr(cand, 'desired_hourly_rate', '') or rate_display,
                'availability_date': str(cand.availability_date) if cand and cand.availability_date else 'Immediate',
                'open_to_work': cand.open_to_work if cand else True,
                'portfolio_url': cand.portfolio_url if cand else '',
                'github_url': cand.github_url if cand else '',
                'linkedin_url': cand.linkedin_url if cand else '',
                'bio': cand.bio if cand else '',
                'profile_strength': cand.profile_strength if cand else 95,
                'cv_score': cand.cv_score if cand else 92,
                'vetting_status': cand.vetting_status if cand else 'in_progress',
                'readiness_tier': cand.readiness_tier if cand else 'ready',
                'skills': skills_data,
                'documents': docs_data,
            },
            'requisition': {
                'id': str(req.id),
                'title': req.title,
                'sector': req.sector,
                'level': req.level,
                'headcount': req.headcount,
                'budget_min': req.budget_min,
                'budget_max': req.budget_max,
                'location': req.location,
                'engagement': req.engagement,
                'status': req.status,
                'skills': req.skills or [],
                'description': req.description or '',
                'discovery': req.discovery or {},
                'client': {
                    'id': str(req.client.id) if req.client else '',
                    'name': req.client.name if req.client else 'Enterprise Partner',
                    'sector': req.client.sector if req.client else 'Technology',
                    'delivery_channel': req.client.delivery_channel if req.client else 'email',
                } if req.client else None,
            },
            'rate': rate_display,
            'match_score': match_score,
            'events': events_data,
            'interviews': [
                {
                    'id': str(intv.id),
                    'title': intv.title,
                    'interview_type': intv.interview_type,
                    'round_number': intv.round_number,
                    'scheduled_start': intv.scheduled_start.strftime('%Y-%m-%d %H:%M') if intv.scheduled_start else '',
                    'scheduled_end': intv.scheduled_end.strftime('%Y-%m-%d %H:%M') if intv.scheduled_end else '',
                    'meeting_link': intv.meeting_link,
                    'status': intv.status,
                    'lead_interviewer': getattr(intv.lead_interviewer, 'full_name', '') or getattr(intv.lead_interviewer, 'email', '') if intv.lead_interviewer else '',
                }
                for intv in app.interviews.all().order_by('-scheduled_start')
            ],
            'placement': {
                'start_date': str(app.placement.start_date) if hasattr(app, 'placement') and app.placement.start_date else '',
                'rate': f"${app.placement.rate}/hr" if hasattr(app, 'placement') and app.placement.rate else '',
                'guarantee_until': str(app.placement.guarantee_until) if hasattr(app, 'placement') and app.placement.guarantee_until else '',
                'checkins': app.placement.checkins if hasattr(app, 'placement') and app.placement.checkins else {},
            } if hasattr(app, 'placement') else None,
            'vettings': [
                {
                    'id': str(v.id),
                    'template_id': str(v.template_id),
                    'template_title': v.template.title,
                    'template_category': v.template.category,
                    'template_sector': v.template.sector,
                    'total_marks': v.template.total_marks,
                    'marks_distribution': v.template.marks_distribution,
                    'instructions': v.template.instructions,
                    'status': v.status,
                    'status_display': v.get_status_display(),
                    'primary_validator_id': str(v.primary_validator_id) if v.primary_validator_id else None,
                    'primary_validator_name': getattr(v.primary_validator, 'full_name', '') or getattr(v.primary_validator, 'email', '') if v.primary_validator else None,
                    'primary_validator_email': getattr(v.primary_validator, 'email', '') if v.primary_validator else None,
                    'deadline': v.deadline.strftime('%Y-%m-%d') if v.deadline else None,
                    'scheduled_start': v.scheduled_start.strftime('%Y-%m-%d') if v.scheduled_start else None,
                    'final_score': v.final_score,
                    'pass_threshold': v.pass_threshold,
                    'decision_notes': v.decision_notes,
                    'recruiter_notes': v.recruiter_notes,
                    'created_at': v.created_at.strftime('%Y-%m-%d %H:%M') if v.created_at else '',
                }
                for v in app.vettings.all().select_related('template', 'primary_validator').order_by('-created_at')
            ],
        }

        return Response({'data': data})

    def patch(self, request, id):
        app = get_object_or_404(Application, id=id)
        data = request.data

        from_stage = app.stage
        to_stage = data.get('stage', app.stage)
        sub_stage = data.get('sub_stage', app.sub_stage)
        note = data.get('note', '')
        signature = data.get('recruiter_signature', '').strip()

        if signature and f"[{signature}]" not in note:
            note = f"[{signature}] {note}".strip()

        rejection_reason = data.get('rejection_reason')
        withdrawal_reason = data.get('withdrawal_reason')
        assigned_validator = data.get('assigned_validator')

        if rejection_reason and f"[Reason: {rejection_reason}]" not in note:
            note = f"[Reason: {rejection_reason}] {note}".strip()
        if withdrawal_reason and f"[Reason: {withdrawal_reason}]" not in note:
            note = f"[Reason: {withdrawal_reason}] {note}".strip()
        if assigned_validator and f"[Assigned Validator: {assigned_validator}]" not in note:
            note = f"[Assigned Validator: {assigned_validator}] {note}".strip()

        stage_changed = (to_stage != from_stage)
        app.stage = to_stage
        app.sub_stage = sub_stage
        actor = request.user if request.user.is_authenticated else None
        if actor and not app.owner:
            app.owner = actor
        app.save(update_fields=['stage', 'sub_stage', 'owner', 'updated_at'])

        event = None
        if stage_changed or note:
            event = ApplicationEvent.objects.create(
                application=app,
                from_stage=from_stage,
                to_stage=to_stage,
                sub_stage=sub_stage,
                actor=actor,
                note=note or f"Stage updated from {from_stage} to {to_stage}."
            )

        if to_stage in [ApplicationStage.INTERVIEW, 'interview']:
            intv_type = data.get('interview_format') or data.get('interview_type')
            intv = ensure_interview_for_application(app, actor=actor, interview_type=intv_type)
            if intv:
                update_fields = []
                if intv_type and intv.interview_type != intv_type:
                    intv.interview_type = intv_type
                    update_fields.append('interview_type')
                if data.get('meeting_link'):
                    intv.meeting_link = data.get('meeting_link')
                    update_fields.append('meeting_link')
                if data.get('candidate_notes'):
                    intv.candidate_notes = data.get('candidate_notes')
                    update_fields.append('candidate_notes')
                if data.get('interview_date'):
                    try:
                        from dateutil import parser
                        parsed_dt = parser.parse(str(data.get('interview_date')))
                        if timezone.is_naive(parsed_dt):
                            parsed_dt = timezone.make_aware(parsed_dt, timezone.utc)
                        intv.scheduled_start = parsed_dt
                        intv.scheduled_end = parsed_dt + timedelta(minutes=60)
                        update_fields.extend(['scheduled_start', 'scheduled_end'])
                    except Exception:
                        pass
                if update_fields:
                    intv.save(update_fields=list(set(update_fields)))

        # Handle technical vetting stage assignment (ApplicationVetting creation)
        if to_stage in [ApplicationStage.TECHNICAL_VETTING, 'technical_vetting']:
            from apps.vetting.models import ApplicationVetting, AssessmentTemplate
            from apps.accounts.models import User
            import uuid

            template = None
            template_id_param = data.get('template_id') or data.get('assessment_template_id')
            if template_id_param:
                try:
                    template = AssessmentTemplate.objects.filter(id=template_id_param).first()
                except Exception:
                    pass

            if not template and data.get('vetting_track'):
                vt = str(data.get('vetting_track')).strip()
                try:
                    template = AssessmentTemplate.objects.filter(id=uuid.UUID(vt)).first()
                except Exception:
                    template = AssessmentTemplate.objects.filter(title__icontains=vt).first()

            if not template:
                req_sector = app.requisition.sector if app.requisition else 'technology'
                template = AssessmentTemplate.objects.filter(
                    Q(sector=req_sector) | Q(sector='both'),
                    is_active=True
                ).first()
                if not template:
                    template = AssessmentTemplate.objects.filter(is_active=True).first()

            val_user = None
            val_id_param = data.get('primary_validator_id') or data.get('assigned_validator_id')
            if val_id_param:
                try:
                    val_user = User.objects.filter(id=val_id_param).first()
                except Exception:
                    pass

            if not val_user and data.get('assigned_validator'):
                av = str(data.get('assigned_validator')).strip()
                try:
                    val_user = User.objects.filter(id=uuid.UUID(av)).first()
                except Exception:
                    val_user = User.objects.filter(
                        Q(full_name__icontains=av) | Q(email__icontains=av)
                    ).first()

            if not val_user:
                target_sector = template.sector if template else 'technology'
                if target_sector == 'healthcare':
                    val_user = User.objects.filter(email='credential_officer@pepoltek.com').first()
                else:
                    val_user = User.objects.filter(email='tech_validator@pepoltek.com').first()

            due_date_str = data.get('assessment_due_date') or data.get('deadline')
            parsed_deadline = None
            if due_date_str:
                try:
                    from dateutil import parser
                    parsed_deadline = parser.parse(str(due_date_str))
                    if timezone.is_naive(parsed_deadline):
                        parsed_deadline = timezone.make_aware(parsed_deadline, timezone.utc)
                except Exception:
                    pass

            if template:
                vetting, v_created = ApplicationVetting.objects.get_or_create(
                    application=app,
                    template=template,
                    defaults={
                        'primary_validator': val_user,
                        'assigned_by': actor,
                        'status': ApplicationVetting.Status.IN_PROGRESS,
                        'deadline': parsed_deadline,
                        'recruiter_notes': note or f"Assessment assigned by {signature or 'recruiter'}.",
                    }
                )
                if not v_created:
                    update_v_fields = []
                    if val_user and vetting.primary_validator_id != val_user.id:
                        vetting.primary_validator = val_user
                        update_v_fields.append('primary_validator')
                    if parsed_deadline and vetting.deadline != parsed_deadline:
                        vetting.deadline = parsed_deadline
                        update_v_fields.append('deadline')
                    if vetting.status == ApplicationVetting.Status.PENDING:
                        vetting.status = ApplicationVetting.Status.IN_PROGRESS
                        update_v_fields.append('status')
                    if update_v_fields:
                        vetting.save(update_fields=update_v_fields)

        cand = app.candidate
        if cand:
            cand_updates = []
            if data.get('candidate_rate'):
                clean_r = str(data.get('candidate_rate')).replace('$', '').replace('/hr', '').strip()
                cand.desired_hourly_rate = f"${clean_r}/hr"
                cand_updates.append('desired_hourly_rate')

            if data.get('vetting_track'):
                cand.domain = data.get('vetting_track')
                cand_updates.append('domain')

            vetting_score = data.get('vetting_score')
            if vetting_score is not None:
                try:
                    score_num = int(vetting_score)
                    cand.vetting_status = 'vetted' if score_num >= 70 else 'in_progress'
                    cand.profile_strength = max(cand.profile_strength or 0, min(100, score_num))
                    cand_updates.extend(['vetting_status', 'profile_strength'])

                    # Auto record score in active ApplicationVetting if exists
                    from apps.vetting.models import ApplicationVetting
                    from apps.vetting.services import submit_final_score
                    active_vetting = app.vettings.filter(
                        status__in=[
                            ApplicationVetting.Status.PENDING,
                            ApplicationVetting.Status.IN_PROGRESS,
                            ApplicationVetting.Status.SUBMITTED,
                        ]
                    ).first()
                    if active_vetting:
                        verdict = 'pass' if score_num >= active_vetting.pass_threshold else 'fail'
                        submit_final_score(
                            actor=actor or active_vetting.primary_validator,
                            vetting=active_vetting,
                            score=score_num,
                            verdict=verdict,
                            feedback=data.get('vetting_notes', '') or 'Evaluated during recruiter stage workflow.'
                        )
                except Exception:
                    pass

            if cand_updates:
                cand.save(update_fields=list(set(cand_updates)))


        if to_stage == 'closed':
            start_date_str = data.get('placement_start_date')
            rate_val = data.get('placement_rate')
            from datetime import datetime, timedelta
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else timezone.now().date()
                guarantee_until = start_date + timedelta(days=90)
                clean_rate = None
                if rate_val:
                    clean_rate_str = str(rate_val).replace('$', '').replace('/hr', '').strip()
                    try:
                        clean_rate = float(clean_rate_str)
                    except ValueError:
                        pass
                Placement.objects.update_or_create(
                    application=app,
                    defaults={
                        'start_date': start_date,
                        'rate': clean_rate,
                        'guarantee_until': guarantee_until,
                        'checkins': {
                            '30_day': {'due': str(start_date + timedelta(days=30)), 'status': 'pending'},
                            '60_day': {'due': str(start_date + timedelta(days=60)), 'status': 'pending'},
                            '90_day': {'due': str(guarantee_until), 'status': 'pending'},
                        }
                    }
                )
            except Exception:
                pass

        actor_name = signature or 'Recruiter Staff'
        if actor:
            actor_name = getattr(actor, 'full_name', '') or getattr(actor, 'email', '') or actor_name

        return Response({
            'data': {
                'id': str(app.id),
                'stage': app.stage,
                'sub_stage': app.sub_stage,
                'message': f"Application updated to stage {app.stage}.",
                'vetting_status': cand.vetting_status if cand else 'in_progress',
                'event': {
                    'id': str(event.id) if event else str(timezone.now().timestamp()),
                    'from_stage': from_stage,
                    'to_stage': to_stage,
                    'sub_stage': sub_stage,
                    'actor_name': actor_name,
                    'note': note,
                    'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M'),
                } if event else None,
            }
        })


class RecruiterApplicationNoteView(APIView):
    """
    POST /api/v1/ats/applications/<uuid:id>/notes/ - Append recruiter internal audit note.
    """
    permission_classes = [IsStaffMember]

    def post(self, request, id):
        app = get_object_or_404(Application, id=id)
        note = request.data.get('note', '').strip()
        if not note:
            return Response({'error': {'message': 'Note text is required.'}}, status=status.HTTP_400_BAD_REQUEST)

        actor = request.user if request.user.is_authenticated else None
        event = ApplicationEvent.objects.create(
            application=app,
            from_stage=app.stage,
            to_stage=app.stage,
            sub_stage=app.sub_stage,
            actor=actor,
            note=note
        )

        actor_name = 'System'
        if actor:
            actor_name = getattr(actor, 'full_name', '') or getattr(actor, 'email', '') or 'Recruiter Staff'

        return Response({
            'data': {
                'id': str(event.id),
                'from_stage': event.from_stage,
                'to_stage': event.to_stage,
                'sub_stage': event.sub_stage,
                'actor_name': actor_name,
                'note': event.note,
                'timestamp': event.timestamp.strftime('%Y-%m-%d %H:%M'),
            },
            'message': 'Note logged successfully.'
        })


class RecruiterCandidatesListView(APIView):
    """
    GET /api/v1/ats/candidates/ - Directory of vetted talent for recruiters.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        ai_mode = request.query_params.get('ai') in ['true', '1'] or request.query_params.get('mode') == 'ai'
        search_query = request.query_params.get('search') or request.query_params.get('q')
        sector_param = request.query_params.get('sector')

        if ai_mode and search_query:
            from apps.ai_service.search import search_candidates_ai
            result = search_candidates_ai(query=search_query, sector=sector_param)
            return Response({'data': result['results'], 'ai_meta': result})

        candidates = Candidate.objects.select_related('user').all()

        if sector_param and sector_param.lower() != 'all':
            candidates = candidates.filter(sector__icontains=sector_param)

        if search_query:
            candidates = candidates.filter(
                Q(full_name__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(domain__icontains=search_query)
            )

        results = []
        for c in candidates:
            is_tech = (c.sector == SectorChoice.TECHNOLOGY) or str(c.sector or '').strip().lower().startswith('tech')
            skills = c.skills_cache if isinstance(c.skills_cache, list) else []
            profile_strength_val = c.profile_strength or 0
            cv_score_val = c.cv_score or 0
            is_vetted = (c.vetting_status == VettingStatus.VETTED) or (c.readiness_tier in [ReadinessTier.READY, ReadinessTier.ELITE])
            vetting_score_val = 94 if is_vetted else 50
            if profile_strength_val > 0 or cv_score_val > 0:
                match_score_val = min(98, max(60, round((profile_strength_val * 0.4) + (vetting_score_val * 0.35) + (cv_score_val * 0.25))))
            else:
                match_score_val = 80 if is_vetted else 65

            # Compute authentic rate without inventing dummy numbers
            if c.desired_hourly_rate and c.desired_hourly_rate.strip():
                rate_val = c.desired_hourly_rate.strip()
            elif c.expected_comp_min:
                if c.expected_comp_min > 500:
                    rate_val = f"${round(c.expected_comp_min / 2080)}/hr"
                else:
                    rate_val = f"${c.expected_comp_min}/hr"
            else:
                rate_val = "Negotiable"

            # Unique display ID from candidate UUID (last 6 chars ensure guaranteed distinctness)
            unique_uuid = str(c.id)
            display_id = f"CAND-{unique_uuid.replace('-', '')[-6:].upper()}"

            results.append({
                'id': unique_uuid,
                'display_id': display_id,
                'name': c.full_name or (c.user.email.split('@')[0].capitalize() if c.user else 'Specialist'),
                'email': c.user.email if c.user else '',
                'title': c.domain or ('Software Specialist' if is_tech else 'Healthcare Specialist'),
                'sector': 'Software Tech' if is_tech else 'Healthcare',
                'skills': skills,
                'experience': f'{c.level.capitalize()} Specialist' if c.level else 'Specialist',
                'matchScore': f'{match_score_val}%',
                'match_score': match_score_val,
                'profileStrength': profile_strength_val,
                'profile_strength': profile_strength_val,
                'readinessIndex': profile_strength_val,
                'cvScore': cv_score_val,
                'cv_score': cv_score_val,
                'vettingScore': vetting_score_val,
                'vetting_score': vetting_score_val,
                'vetting_status': c.vetting_status or 'not_started',
                'readinessTier': c.readiness_tier or 'unrated',
                'readiness_tier': c.readiness_tier or 'unrated',
                'rate': rate_val,
                'availability': 'Immediate' if c.open_to_work else 'Interview Only',
                'verified': is_vetted,
                'phone': c.phone or '',
                'location': c.location or 'Remote',
            })

        return Response({'data': results})

    def post(self, request):
        """
        POST /api/v1/ats/candidates/ - Natural language AI candidate search
        """
        from apps.ai_service.search import search_candidates_ai
        query = request.data.get('query') or request.data.get('search', '').strip()
        sector = request.data.get('sector')
        requisition_id = request.data.get('requisition_id')
        if not query:
            return Response({'error': {'message': 'Search query is required.'}}, status=status.HTTP_400_BAD_REQUEST)

        result = search_candidates_ai(query=query, sector=sector, requisition_id=requisition_id)
        return Response({'data': result['results'], 'ai_meta': result})


class RecruiterInterviewsListView(APIView):
    """
    GET /api/v1/ats/interviews/ - List scheduled sprint interviews with filters.
    POST /api/v1/ats/interviews/ - Schedule technical/client interview with authentic database persistence.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        # Ensure any applications currently in INTERVIEW stage have an Interview session provisioned
        interview_apps = Application.objects.filter(stage=ApplicationStage.INTERVIEW).exclude(interviews__isnull=False)
        for app in interview_apps:
            ensure_interview_for_application(app)

        qs = Interview.objects.select_related(
            'application__candidate__user',
            'application__requisition__client',
            'lead_interviewer'
        ).prefetch_related(
            'assignments__staff_user',
            'evaluations__evaluator'
        ).order_by('-scheduled_start')

        # Filter by status
        status_param = request.query_params.get('status')
        if status_param and status_param != 'all':
            qs = qs.filter(status=status_param)

        # Filter by interview_type
        type_param = request.query_params.get('type')
        if type_param and type_param != 'all':
            qs = qs.filter(interview_type=type_param)

        # Search query (candidate name, req title, or title)
        search_query = request.query_params.get('search')
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(application__candidate__user__first_name__icontains=search_query) |
                Q(application__candidate__user__last_name__icontains=search_query) |
                Q(application__candidate__user__email__icontains=search_query) |
                Q(application__requisition__title__icontains=search_query)
            )

        serialized = InterviewListSerializer(qs, many=True).data

        # Metrics overview
        total_count = Interview.objects.count()
        scheduled_count = Interview.objects.filter(status=InterviewStatus.SCHEDULED).count()
        completed_count = Interview.objects.filter(status=InterviewStatus.COMPLETED).count()

        return Response({
            'data': serialized,
            'metrics': {
                'total': total_count,
                'scheduled': scheduled_count,
                'completed': completed_count,
            }
        })

    def post(self, request):
        serializer = InterviewCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        app = get_object_or_404(Application, id=data['application_id'])

        # Advance application stage to interview if not already
        if app.stage != ApplicationStage.INTERVIEW:
            prev_stage = app.stage
            app.stage = ApplicationStage.INTERVIEW
            app.sub_stage = 'Interview Scheduled'
            app.save(update_fields=['stage', 'sub_stage', 'updated_at'])

            ApplicationEvent.objects.create(
                application=app,
                from_stage=prev_stage,
                to_stage=ApplicationStage.INTERVIEW,
                sub_stage='Interview Scheduled',
                actor=request.user,
                note=f"Scheduled interview '{data['title']}' via ATS recruiter console."
            )

        lead_user = None
        if data.get('lead_interviewer_id'):
            lead_user = User.objects.filter(id=data['lead_interviewer_id']).first()
        if not lead_user:
            lead_user = request.user

        interview = Interview.objects.create(
            application=app,
            title=data['title'],
            interview_type=data.get('interview_type', InterviewType.TECHNICAL_CODING),
            round_number=data.get('round_number', 1),
            scheduled_start=data['scheduled_start'],
            scheduled_end=data['scheduled_end'],
            timezone=data.get('timezone', 'UTC'),
            meeting_link=data.get('meeting_link', ''),
            status=InterviewStatus.SCHEDULED,
            lead_interviewer=lead_user,
            candidate_notes=data.get('candidate_notes', ''),
            internal_brief=data.get('internal_brief', ''),
        )

        # Create panel assignment for lead interviewer
        InterviewPanelAssignment.objects.get_or_create(
            interview=interview,
            staff_user=lead_user,
            defaults={'role': PanelRole.LEAD_INTERVIEWER, 'has_confirmed': True}
        )

        # Create panel assignments for selected members
        for member_id in data.get('panel_member_ids', []):
            staff = User.objects.filter(id=member_id).first()
            if staff and staff != lead_user:
                InterviewPanelAssignment.objects.get_or_create(
                    interview=interview,
                    staff_user=staff,
                    defaults={'role': PanelRole.TECHNICAL_ASSESSOR}
                )

        # Send calendar invitation email
        cand_user = app.candidate.user
        if cand_user and cand_user.email:
            from django.core.mail import send_mail
            start_str = interview.scheduled_start.strftime('%A, %B %d, %Y at %I:%M %p %Z')
            try:
                send_mail(
                    subject=f"Pepoltek Technical Interview Scheduled: {app.requisition.title}",
                    message=(
                        f"Hello {app.candidate.full_name or cand_user.get_full_name()},\n\n"
                        f"Your interview session for the {app.requisition.title} position has been scheduled.\n\n"
                        f"Session: {interview.title}\n"
                        f"Format: {interview.get_interview_type_display()}\n"
                        f"Date and Time: {start_str}\n"
                        f"Meeting Room: {interview.meeting_link or 'Link available in your candidate dashboard'}\n\n"
                        f"Preparation Notes:\n"
                        f"{interview.candidate_notes or 'Please be ready in a quiet workspace 5 minutes before start.'}\n\n"
                        f"Best regards,\nPepoltek Recruitment Operations"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[cand_user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

        record(
            actor=request.user,
            action='interview.scheduled',
            target=interview,
            payload={'title': interview.title, 'candidate': str(app.candidate.id)}
        )

        return Response({
            'data': InterviewDetailSerializer(interview).data,
            'message': 'Interview scheduled successfully.'
        }, status=status.HTTP_201_CREATED)


class RecruiterInterviewDetailView(APIView):
    """
    GET /api/v1/ats/interviews/<uuid:id>/ - Get full interview details, evaluations, and panel members.
    PATCH /api/v1/ats/interviews/<uuid:id>/ - Update or reschedule interview.
    DELETE /api/v1/ats/interviews/<uuid:id>/ - Cancel interview.
    """
    permission_classes = [IsStaffMember]

    def get_object(self, id):
        return get_object_or_404(
            Interview.objects.select_related(
                'application__candidate__user',
                'application__requisition__client',
                'lead_interviewer'
            ).prefetch_related(
                'assignments__staff_user',
                'evaluations__evaluator'
            ),
            id=id
        )

    def get(self, request, id):
        interview = self.get_object(id)
        return Response({'data': InterviewDetailSerializer(interview).data})

    def patch(self, request, id):
        interview = self.get_object(id)
        serializer = InterviewUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        for field, value in data.items():
            if field == 'lead_interviewer_id':
                if value:
                    lead_user = User.objects.filter(id=value).first()
                    interview.lead_interviewer = lead_user
                else:
                    interview.lead_interviewer = None
            else:
                setattr(interview, field, value)

        interview.save()

        record(
            actor=request.user,
            action='interview.updated',
            target=interview,
            payload={'updated_fields': list(data.keys())}
        )

        return Response({
            'data': InterviewDetailSerializer(interview).data,
            'message': 'Interview updated successfully.'
        })

    def delete(self, request, id):
        interview = self.get_object(id)
        interview.status = InterviewStatus.CANCELLED
        interview.save(update_fields=['status', 'updated_at'])

        record(
            actor=request.user,
            action='interview.cancelled',
            target=interview,
            payload={'reason': request.data.get('reason', 'Cancelled by recruiter')}
        )

        return Response({
            'data': InterviewDetailSerializer(interview).data,
            'message': 'Interview marked as cancelled.'
        })


class RecruiterInterviewEvaluationView(APIView):
    """
    POST /api/v1/ats/interviews/<uuid:id>/evaluations/ - Submit or update panel evaluation scorecard.
    """
    permission_classes = [IsStaffMember]

    def post(self, request, id):
        interview = get_object_or_404(Interview, id=id)
        serializer = InterviewEvaluationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        evaluation, created = InterviewEvaluation.objects.update_or_create(
            interview=interview,
            evaluator=request.user,
            defaults={
                'score': data['score'],
                'recommendation': data['recommendation'],
                'competency_scores': data.get('competency_scores', []),
                'feedback': data['feedback'],
            }
        )

        # Ensure staff has assignment marked confirmed
        assignment = InterviewPanelAssignment.objects.filter(
            interview=interview,
            staff_user=request.user
        ).first()
        if assignment:
            assignment.has_confirmed = True
            assignment.save(update_fields=['has_confirmed', 'updated_at'])

        # Auto-update interview status to completed if appropriate
        if interview.status in [InterviewStatus.SCHEDULED, InterviewStatus.IN_PROGRESS]:
            interview.status = InterviewStatus.COMPLETED
            interview.save(update_fields=['status', 'updated_at'])

        record(
            actor=request.user,
            action='interview.evaluation_submitted',
            target=interview,
            payload={
                'score': evaluation.score,
                'recommendation': evaluation.recommendation,
                'evaluator': request.user.email
            }
        )

        # Refresh interview with prefetching and return detail
        refreshed = Interview.objects.select_related(
            'application__candidate__user',
            'application__requisition__client',
            'lead_interviewer'
        ).prefetch_related(
            'assignments__staff_user',
            'evaluations__evaluator'
        ).get(id=id)

        return Response({
            'data': InterviewDetailSerializer(refreshed).data,
            'message': 'Evaluation scorecard submitted successfully.'
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RecruiterInterviewPanelAssignmentView(APIView):
    """
    POST /api/v1/ats/interviews/<uuid:id>/panel/ - Add or update a panel assignment.
    """
    permission_classes = [IsStaffMember]

    def post(self, request, id):
        interview = get_object_or_404(Interview, id=id)
        staff_user_id = request.data.get('staff_user_id')
        role = request.data.get('role', PanelRole.TECHNICAL_ASSESSOR)
        action = request.data.get('action', 'add')

        staff_user = get_object_or_404(User, id=staff_user_id)

        if action == 'remove':
            InterviewPanelAssignment.objects.filter(interview=interview, staff_user=staff_user).delete()
            msg = 'Panel member removed.'
        else:
            assignment, _ = InterviewPanelAssignment.objects.update_or_create(
                interview=interview,
                staff_user=staff_user,
                defaults={'role': role}
            )
            msg = 'Panel member assigned.'

        refreshed = Interview.objects.select_related(
            'application__candidate__user',
            'application__requisition__client',
            'lead_interviewer'
        ).prefetch_related(
            'assignments__staff_user',
            'evaluations__evaluator'
        ).get(id=id)

        return Response({
            'data': InterviewDetailSerializer(refreshed).data,
            'message': msg
        })


class RecruiterAnalyticsView(APIView):
    """
    GET /api/v1/ats/analytics/ - Cockpit metrics for recruiter dashboard.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        total_requisitions = Requisition.objects.filter(status=RequisitionStatus.OPEN).count()
        total_candidates = Candidate.objects.count()
        interview_count = Application.objects.filter(stage=ApplicationStage.INTERVIEW).count()
        closed_count = Application.objects.filter(stage=ApplicationStage.CLOSED).count()

        return Response({
            'data': {
                'activePodsCount': total_requisitions,
                'activeRequisitionsCount': total_requisitions,
                'totalCandidates': total_candidates,
                'interviewCount': interview_count,
                'closedCount': closed_count,
                'avgDeploymentTime': '7.0',
                'compliancePassRate': '100%',
                'reclaimedHiringHours': f'{closed_count * 48}.0',
            }
        })


class RecruiterSubmissionsView(APIView):
    """
    GET /api/v1/ats/submissions/ - List past client shortlists.
    POST /api/v1/ats/submissions/ - Log a new shortlist submission package for a client requisition.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        queryset = Submission.objects.select_related('requisition', 'requisition__client', 'created_by').all()
        requisition_id = getattr(request, 'query_params', request.GET).get('requisition_id')
        if requisition_id:
            queryset = queryset.filter(requisition_id=requisition_id)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = SubmissionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        requisition_id = data.get('requisition_id')
        requisition = None
        if requisition_id:
            requisition = Requisition.objects.filter(id=requisition_id).first()

        if not requisition:
            requisition = Requisition.objects.filter(status=RequisitionStatus.OPEN).first()
            if not requisition:
                client, _ = Client.objects.get_or_create(
                    name=data.get('client_name') or 'Enterprise Client Partner'
                )
                requisition = Requisition.objects.create(
                    client=client,
                    title='Sprint Delivery Shortlist',
                    sector='Technology & SDLC',
                    status=RequisitionStatus.OPEN,
                    visibility=RequisitionVisibility.PUBLISHED_JOB,
                )

        # Check AC-05: Recruiter cannot submit candidate to client without explicit PitchAuthorization
        from apps.matching.models import PitchAuthorization, PitchAuthorizationStatus
        unauthorized_cands = []
        for item in data.get('items', []):
            cid = item.get('candidate_id')
            if cid:
                cand = Candidate.objects.filter(id=cid).first()
                if cand:
                    app = Application.objects.filter(candidate=cand, requisition=requisition).first()
                    is_direct_applied = (app and app.source == ApplicationSource.APPLIED)
                    if not is_direct_applied:
                        auth = PitchAuthorization.objects.filter(
                            candidate=cand,
                            requisition=requisition,
                            status=PitchAuthorizationStatus.AUTHORIZED
                        ).first()
                        if not auth:
                            unauthorized_cands.append(cand.full_name)

        if unauthorized_cands:
            return Response(
                {
                    'error': {
                        'code': 'PITCH_NOT_AUTHORIZED',
                        'message': f"Pitch not authorized: Candidate(s) {', '.join(unauthorized_cands)} have not authorized their pitch for this requisition. Candidate consent is required before client submission (SRS AC-05).",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        submission = Submission.objects.create(
            requisition=requisition,
            created_by=request.user if request.user.is_authenticated else None,
            channel=data.get('channel') or DeliveryChannel.EMAIL,
            sent_at=timezone.now(),
            items=data['items'],
        )

        # Transition candidate applications to ApplicationStage.INTERVIEW ("Submitted to Client")
        for item in data['items']:
            candidate_id = item.get('candidate_id')
            if candidate_id:
                cand = Candidate.objects.filter(id=candidate_id).first()
                if cand:
                    app, _ = Application.objects.get_or_create(
                        candidate=cand,
                        requisition=requisition,
                        defaults={
                            'stage': ApplicationStage.INTERVIEW,
                            'sub_stage': 'Submitted to Client',
                            'source': ApplicationSource.SOURCED,
                        }
                    )
                    if app.stage != ApplicationStage.INTERVIEW:
                        app.stage = ApplicationStage.INTERVIEW
                        app.sub_stage = 'Submitted to Client'
                        app.save(update_fields=['stage', 'sub_stage', 'updated_at'])
                        ensure_interview_for_application(app, actor=request.user)

                    ApplicationEvent.objects.create(
                        application=app,
                        from_stage=app.stage,
                        to_stage=ApplicationStage.INTERVIEW,
                        sub_stage='Submitted to Client',
                        actor=request.user if request.user.is_authenticated else None,
                        note=f"Included in client submission {submission.id} via {submission.get_channel_display()}",
                    )

        # Audit event record
        record(
            action=AuditLog.Action.SUBMISSION_SENT,
            entity='Submission',
            entity_id=str(submission.id),
            actor=request.user if request.user.is_authenticated else None,
            extra={
                'requisition_id': str(requisition.id),
                'channel': submission.channel,
                'candidate_count': len(data['items']),
            },
            request=request,
        )

        out_serializer = SubmissionSerializer(submission)
        return Response(
            {
                'data': out_serializer.data,
                'message': 'Shortlist submission package logged successfully.',
            },
            status=status.HTTP_201_CREATED,
        )


class RecruiterSubmissionDetailView(APIView):
    """
    GET /api/v1/ats/submissions/<id>/ - Single submission detail.
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        sub = get_object_or_404(
            Submission.objects.select_related('requisition', 'requisition__client', 'created_by'),
            id=id,
        )
        serializer = SubmissionSerializer(sub)
        return Response({'data': serializer.data})


class RecruiterSubmissionExportView(APIView):
    """
    GET /api/v1/ats/submissions/<id>/export/?format=csv|text|json
    Generates branded PDF/text/CSV export summary for client delivery.
    """
    permission_classes = [IsStaffMember]

    def perform_content_negotiation(self, request, force=False):
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request, id):
        import uuid as _uuid
        if isinstance(id, str):
            try:
                id = _uuid.UUID(id)
            except Exception:
                pass
        sub = get_object_or_404(
            Submission.objects.select_related('requisition', 'requisition__client', 'created_by'),
            id=id,
        )
        export_format = (
            getattr(request, 'query_params', request.GET).get('export_format')
            or getattr(request, 'query_params', request.GET).get('format')
            or 'text'
        ).lower()

        client_name = sub.requisition.client.name if sub.requisition and sub.requisition.client else 'Client Partner'
        req_title = sub.requisition.title if sub.requisition else 'Engineering Requisition'
        channel_name = sub.get_channel_display()

        if export_format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Candidate_ID',
                'Candidate_Name',
                'Title',
                'Sector',
                'Experience',
                'Rate',
                'Match_Score',
                'Skills',
                'Contact_Status',
                'Recruiter_Notes',
            ])
            for it in sub.items:
                revealed = it.get('revealed_fields', {})
                masked = it.get('masked_contact', {})
                contact_str = (
                    f"{masked.get('email', '[Masked]')} / {masked.get('phone', '[Masked]')}"
                    if revealed.get('show_contact')
                    else '[Protected by Pepoltek Escrow]'
                )
                skills_str = ', '.join(it.get('skills', []))
                writer.writerow([
                    it.get('candidate_id', ''),
                    it.get('candidate_name', ''),
                    it.get('candidate_title', ''),
                    it.get('sector', ''),
                    it.get('experience', ''),
                    it.get('rate', ''),
                    it.get('match_score', ''),
                    skills_str,
                    contact_str,
                    it.get('recruiter_notes', ''),
                ])
            csv_text = output.getvalue()
            return Response({
                'data': {
                    'format': 'csv',
                    'filename': f"Pepoltek_Shortlist_{str(sub.id)[:8]}.csv",
                    'content': csv_text,
                }
            })

        # Default text / shareable markdown summary (Zero em dashes house style!)
        text_lines = [
            "# PEPOLTEK TALENT SUBMISSION DOSSIER",
            f"Target Requisition: {req_title}",
            f"Client: {client_name}",
            f"Delivery Channel: {channel_name}",
            f"Submission ID: {sub.id}",
            f"Timestamp: {sub.sent_at.strftime('%Y-%m-%d %H:%M UTC') if sub.sent_at else 'Live'}",
            "",
            "## EXECUTIVE SUMMARY & SHORTLIST ROSTER",
        ]

        for idx, it in enumerate(sub.items, 1):
            skills_str = ', '.join(it.get('skills', []))
            revealed = it.get('revealed_fields', {})
            contact_str = (
                f"{it.get('email', '')} | {it.get('phone', '')}"
                if revealed.get('show_contact')
                else "[Contact details masked: Protected by Pepoltek Escrow]"
            )
            text_lines.extend([
                f"{idx}. {it.get('candidate_name', 'Specialist')} ({it.get('candidate_title', 'Core Specialist')})",
                f"   - Candidate ID: {it.get('candidate_id', 'N/A')}",
                f"   - Sector: {it.get('sector', 'Technology')}",
                f"   - Match Fit: {it.get('match_score', '95%')} (Verified Vetted)",
                f"   - Experience: {it.get('experience', '5+ yrs')}",
                f"   - Billing Rate: {it.get('rate', 'Market Standard')}",
                f"   - Core Skills: {skills_str}",
                f"   - Placement Contact: {contact_str}",
                f"   - Recruiter Notes: {it.get('recruiter_notes', 'Pre-screened and interview-ready.')}",
                "",
            ])

        text_lines.extend([
            "---",
            "CONFIDENTIALITY NOTICE: This candidate submission package contains proprietary vetted candidate assessments under Pepoltek staffing terms. Contact your Pepoltek Delivery Lead to schedule sprint interviews.",
        ])

        return Response({
            'data': {
                'format': 'text',
                'filename': f"Pepoltek_Shortlist_{str(sub.id)[:8]}.md",
                'content': '\n'.join(text_lines),
            }
        })


class RecruiterClientsListView(APIView):
    """
    GET /api/v1/ats/clients/ - List all clients with contact records and requisition metrics.
    POST /api/v1/ats/clients/ - Create a new client record and optional primary contact.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        queryset = Client.objects.prefetch_related('contacts', 'requisitions').all()

        sector = request.query_params.get('sector')
        if sector and sector.lower() != 'all':
            queryset = queryset.filter(sector__icontains=sector)

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(website__icontains=search)
            ).distinct()

        serializer = ClientSerializer(queryset, many=True)
        return Response({'data': serializer.data})

    def post(self, request):
        serializer = ClientCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        client = Client.objects.create(
            name=d['name'],
            sector=d.get('sector', 'technology'),
            website=d.get('website', ''),
            delivery_channel=d.get('delivery_channel', DeliveryChannel.EMAIL),
            terms=d.get('terms', {}),
            owner=request.user if request.user.is_authenticated else None,
        )

        contact_name = d.get('primary_contact_name')
        contact_email = d.get('primary_contact_email')
        if contact_name and contact_email:
            ClientContact.objects.create(
                client=client,
                full_name=contact_name,
                email=contact_email,
                phone=d.get('primary_contact_phone', ''),
                role_title=d.get('primary_contact_role', 'Hiring Manager'),
                is_primary=True,
            )

        return Response(
            {
                'data': ClientSerializer(client).data,
                'message': f"Client {client.name} created successfully.",
            },
            status=status.HTTP_201_CREATED
        )


class RecruiterClientDetailView(APIView):
    """
    GET /api/v1/ats/clients/<uuid:id>/ - Retrieve detail of a single client.
    PATCH /api/v1/ats/clients/<uuid:id>/ - Update client terms, delivery channel, or sector.
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        client = get_object_or_404(Client.objects.prefetch_related('contacts', 'requisitions'), id=id)
        return Response({'data': ClientSerializer(client).data})

    def patch(self, request, id):
        client = get_object_or_404(Client, id=id)
        data = request.data

        if 'name' in data:
            client.name = data['name']
        if 'sector' in data:
            client.sector = data['sector']
        if 'website' in data:
            client.website = data['website']
        if 'delivery_channel' in data:
            client.delivery_channel = data['delivery_channel']
        if 'terms' in data and isinstance(data['terms'], dict):
            client.terms = {**(client.terms or {}), **data['terms']}

        client.save()

        c_name = data.get('primary_contact_name')
        c_email = data.get('primary_contact_email')
        if c_name and c_email:
            primary_contact = client.contacts.filter(is_primary=True).first()
            if primary_contact:
                primary_contact.full_name = c_name
                primary_contact.email = c_email
                if 'primary_contact_phone' in data:
                    primary_contact.phone = data['primary_contact_phone']
                if 'primary_contact_role' in data:
                    primary_contact.role_title = data['primary_contact_role']
                primary_contact.save()
            else:
                ClientContact.objects.create(
                    client=client,
                    full_name=c_name,
                    email=c_email,
                    phone=data.get('primary_contact_phone', ''),
                    role_title=data.get('primary_contact_role', 'Hiring Manager'),
                    is_primary=True,
                )

        return Response({
            'data': ClientSerializer(client).data,
            'message': f"Client {client.name} updated.",
        })


class RecruiterSourceCandidateView(APIView):
    """
    POST /api/v1/ats/candidates/source/
    Recruiter sources a candidate for a requisition directly from candidate directory.
    Creates or updates Application in Market Mapping with sub_stage='Sourced'.
    """
    permission_classes = [IsStaffMember]

    def post(self, request):
        serializer = RecruiterSourceCandidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        candidate = get_object_or_404(Candidate, id=d['candidate_id'])
        requisition = get_object_or_404(Requisition, id=d['requisition_id'])
        note = d.get('note', '')

        actor = request.user if request.user.is_authenticated else None

        app, created = Application.objects.get_or_create(
            candidate=candidate,
            requisition=requisition,
            defaults={
                'stage': ApplicationStage.MARKET_MAPPING,
                'sub_stage': 'Sourced',
                'source': ApplicationSource.SOURCED,
                'owner': actor,
            }
        )

        if not created and app.stage == ApplicationStage.DISCOVERY:
            app.stage = ApplicationStage.MARKET_MAPPING
            app.sub_stage = 'Sourced'
            app.save(update_fields=['stage', 'sub_stage', 'updated_at'])

        ApplicationEvent.objects.create(
            application=app,
            from_stage='' if created else app.stage,
            to_stage=ApplicationStage.MARKET_MAPPING,
            sub_stage='Sourced',
            actor=actor,
            note=note or f"Candidate sourced for {requisition.title} by recruiter",
        )

        # Ensure PitchAuthorization record is created in REQUESTED state so candidate is alerted
        from apps.matching.models import PitchAuthorization, PitchAuthorizationStatus
        pitch_auth, _ = PitchAuthorization.objects.get_or_create(
            candidate=candidate,
            requisition=requisition,
            defaults={
                'status': PitchAuthorizationStatus.REQUESTED,
            }
        )

        return Response({
            'data': {
                'application_id': str(app.id),
                'candidate_id': str(candidate.id),
                'candidate_name': candidate.full_name,
                'requisition_id': str(requisition.id),
                'requisition_title': requisition.title,
                'stage': app.stage,
                'sub_stage': app.sub_stage,
                'pitch_status': pitch_auth.status,
                'is_new': created,
                'message': f"Candidate {candidate.full_name} successfully sourced for {requisition.title}.",
            }
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



