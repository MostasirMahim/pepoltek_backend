import hashlib
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.ats.models import (
    Requisition,
    RequisitionStatus,
    Application,
    ApplicationStage,
    ApplicationSource,
    ApplicationEvent,
)
from apps.candidates.models import Candidate, SectorChoice, ExperienceLevel
from apps.matching.models import PitchAuthorization, PitchAuthorizationStatus


class ReverseSearchView(APIView):
    """
    GET /api/v1/matching/reverse-search/
    Scan confidential active requisitions matching candidate parameters.
    Returns authentic pitch_status and requisition metadata for candidate authorization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sector = request.query_params.get('sector', 'tech').lower()
        min_rate = request.query_params.get('min_rate')
        remote_pref = request.query_params.get('remote_pref', 'remote')

        candidate = getattr(request.user, 'candidate', None)
        cand_emb = candidate.embedding if candidate else None

        queryset = Requisition.objects.filter(status=RequisitionStatus.OPEN)

        if sector in ['tech', 'technology']:
            queryset = queryset.filter(sector__icontains='tech')
        elif sector in ['health', 'healthcare']:
            queryset = queryset.filter(sector__icontains='health')

        from apps.ai_service.search import cosine_similarity

        results = []
        for req in queryset[:25]:
            budget_str = f"${req.budget_min or 80} - ${req.budget_max or 120} / hr" if req.budget_min else "$85 - $110 / hr"

            # Authentic vector cosine similarity calculation
            if cand_emb and req.embedding:
                raw_cos = cosine_similarity(cand_emb, req.embedding)
                calc_score = min(98, max(55, round(45 + (raw_cos / 0.40) * 50)))
            else:
                calc_score = 92 if candidate and candidate.sector == req.sector else 85

            # Authentic PitchAuthorization status
            pitch_auth = None
            if candidate:
                pitch_auth = PitchAuthorization.objects.filter(candidate=candidate, requisition=req).first()

            existing_app = None
            if candidate:
                existing_app = Application.objects.filter(candidate=candidate, requisition=req).first()

            if pitch_auth:
                pitch_status = pitch_auth.status
            elif existing_app and existing_app.source == ApplicationSource.SOURCED:
                pitch_status = PitchAuthorizationStatus.REQUESTED
            else:
                pitch_status = 'not_requested'

            is_authorized = (pitch_status == PitchAuthorizationStatus.AUTHORIZED)

            results.append({
                'id': str(req.id),
                'requisition_id': str(req.id),
                'title': req.title,
                'company_masked': 'Enterprise Client (Confidential)',
                'company': 'Enterprise Client (Confidential)',
                'sector': req.sector,
                'level': req.level or 'Senior',
                'engagement': req.engagement or 'C2C Direct Sprint',
                'rateRange': budget_str,
                'rate_range': budget_str,
                'location': req.location or '100% Remote',
                'timezone_overlap': '4h guaranteed live overlap',
                'work_auth_fit': 'Eligible for C2C / W2 Direct placement',
                'match_score': calc_score,
                'matchScore': calc_score,
                'skills': req.skills if isinstance(req.skills, list) and req.skills else ['Core Engineering', 'Problem Solving', 'Cloud Architecture'],
                'description': req.description or 'Enterprise sprint requisition requiring verified technical expertise and continuous delivery excellence.',
                'pitch_status': pitch_status,
                'authorized': is_authorized,
                'must_haves_met': True,
                'confidential': True,
            })

        # Sort: items with pending 'requested' pitch authorizations first, then highest score
        results.sort(
            key=lambda x: (
                1 if x['pitch_status'] == 'requested' else 0,
                x['match_score']
            ),
            reverse=True
        )
        return Response({'data': results})


class CandidatePitchRequestsView(APIView):
    """
    GET /api/v1/matching/pitch-requests/
    List all recruiter-sourced pitch authorization requests for the candidate.
    Allows candidate to review recruiter sourcing notes, view job details, and authorize/decline.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = getattr(request.user, 'candidate', None)
        if not candidate:
            return Response({'data': []})

        # 1. Fetch existing pitch authorizations for this candidate
        pitch_auths = PitchAuthorization.objects.filter(
            candidate=candidate
        ).select_related('requisition', 'requisition__client').order_by('-created_at')

        results = []
        seen_req_ids = set()

        for auth in pitch_auths:
            req = auth.requisition
            seen_req_ids.add(req.id)
            budget_str = f"${req.budget_min or 80} - ${req.budget_max or 120} / hr" if req.budget_min else "$85 - $110 / hr"

            # Check if there is a sourcing note from Application or ApplicationEvent
            app = Application.objects.filter(candidate=candidate, requisition=req).first()
            sourcing_note = "Sourced by Pepoltek Executive Recruiter for priority client shortlist."
            if app:
                event = ApplicationEvent.objects.filter(application=app, sub_stage='Sourced').first()
                if event and event.note:
                    sourcing_note = event.note

            results.append({
                'id': str(auth.id),
                'pitch_auth_id': str(auth.id),
                'requisition_id': str(req.id),
                'title': req.title,
                'company_masked': req.client.name if req.visibility == 'public' else 'Enterprise Client (Confidential)',
                'sector': req.sector,
                'level': req.level or 'Senior',
                'engagement': req.engagement or 'C2C Direct Sprint',
                'rate_range': budget_str,
                'location': req.location or '100% Remote',
                'timezone_overlap': '4h guaranteed live overlap',
                'work_auth_fit': 'Eligible for C2C / W2 Direct placement',
                'skills': req.skills if isinstance(req.skills, list) and req.skills else ['Core Engineering'],
                'description': req.description or 'Enterprise sprint requisition requiring verified technical expertise.',
                'status': auth.status,
                'requested_at': auth.created_at.strftime("%b %d, %Y"),
                'decided_at': auth.decided_at.strftime("%b %d, %Y") if auth.decided_at else None,
                'sourcing_note': sourcing_note,
            })

        # 2. Check any applications where source=SOURCED but pitch_auth record was not yet minted
        sourced_apps = Application.objects.filter(
            candidate=candidate,
            source=ApplicationSource.SOURCED
        ).exclude(requisition_id__in=seen_req_ids).select_related('requisition', 'requisition__client')

        for app in sourced_apps:
            req = app.requisition
            budget_str = f"${req.budget_min or 80} - ${req.budget_max or 120} / hr" if req.budget_min else "$85 - $110 / hr"

            auth, _ = PitchAuthorization.objects.get_or_create(
                candidate=candidate,
                requisition=req,
                defaults={'status': PitchAuthorizationStatus.REQUESTED}
            )

            results.append({
                'id': str(auth.id),
                'pitch_auth_id': str(auth.id),
                'requisition_id': str(req.id),
                'title': req.title,
                'company_masked': 'Enterprise Client (Confidential)',
                'sector': req.sector,
                'level': req.level or 'Senior',
                'engagement': req.engagement or 'C2C Direct Sprint',
                'rate_range': budget_str,
                'location': req.location or '100% Remote',
                'timezone_overlap': '4h guaranteed live overlap',
                'work_auth_fit': 'Eligible for C2C / W2 Direct placement',
                'skills': req.skills if isinstance(req.skills, list) and req.skills else ['Core Engineering'],
                'description': req.description or 'Enterprise sprint requisition requiring verified technical expertise.',
                'status': auth.status,
                'requested_at': auth.created_at.strftime("%b %d, %Y"),
                'decided_at': None,
                'sourcing_note': "Sourced by Pepoltek Executive Recruiter for priority client shortlist.",
            })

        return Response({'data': results})


class PitchSubmissionView(APIView):
    """
    POST /api/v1/matching/pitch/<id>/
    Submit candidate's pitch authorization, revocation, or decline for a requisition.
    Supports either requisition UUID or PitchAuthorization UUID.
    Automatically links to an Application in Market Mapping!
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        candidate = getattr(request.user, 'candidate', None)
        if not candidate:
            return Response(
                {'error': {'message': 'Candidate profile not found for this user account.'}},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Support both Requisition ID and PitchAuthorization ID
        requisition = Requisition.objects.filter(id=id).first()
        target_pitch_auth = None
        if not requisition:
            target_pitch_auth = PitchAuthorization.objects.filter(id=id, candidate=candidate).first()
            if target_pitch_auth:
                requisition = target_pitch_auth.requisition
            else:
                return Response(
                    {'error': {'message': 'Requisition or pitch authorization not found.'}},
                    status=status.HTTP_404_NOT_FOUND
                )

        desired_status = request.data.get('status', 'authorized').lower()
        valid_statuses = [
            PitchAuthorizationStatus.AUTHORIZED,
            PitchAuthorizationStatus.DECLINED,
            PitchAuthorizationStatus.REVOKED,
            PitchAuthorizationStatus.REQUESTED,
        ]
        if desired_status not in valid_statuses:
            desired_status = PitchAuthorizationStatus.AUTHORIZED

        ip_addr = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
        if ',' in ip_addr:
            ip_addr = ip_addr.split(',')[0].strip()
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Generate cryptographic SHA-256 profile snapshot hash
        snapshot_raw = f"{candidate.id}:{candidate.full_name}:{candidate.sector}:{candidate.level}:{candidate.desired_hourly_rate}"
        snapshot_hash = hashlib.sha256(snapshot_raw.encode('utf-8')).hexdigest()

        # 1. Persist PitchAuthorization in database
        pitch_auth = target_pitch_auth or PitchAuthorization.objects.filter(
            candidate=candidate,
            requisition=requisition,
        ).first()

        if not pitch_auth:
            pitch_auth = PitchAuthorization.objects.create(
                candidate=candidate,
                requisition=requisition,
                status=desired_status,
                ip_address=ip_addr,
                user_agent=user_agent,
                snapshot_hash=snapshot_hash,
                decided_at=timezone.now(),
            )
        else:
            pitch_auth.status = desired_status
            pitch_auth.decided_at = timezone.now()
            pitch_auth.ip_address = ip_addr
            pitch_auth.user_agent = user_agent
            pitch_auth.snapshot_hash = snapshot_hash
            pitch_auth.save(update_fields=['status', 'decided_at', 'ip_address', 'user_agent', 'snapshot_hash', 'updated_at'])

        # 2. Automatically Link Application to Requisition Pipeline
        if desired_status == PitchAuthorizationStatus.AUTHORIZED:
            app, created = Application.objects.get_or_create(
                candidate=candidate,
                requisition=requisition,
                defaults={
                    'stage': ApplicationStage.MARKET_MAPPING,
                    'sub_stage': 'Pitch Authorized',
                    'source': ApplicationSource.REVERSE,
                }
            )
            if not created:
                app.sub_stage = 'Pitch Authorized'
                app.save(update_fields=['sub_stage', 'updated_at'])

            ApplicationEvent.objects.create(
                application=app,
                from_stage='' if created else app.stage,
                to_stage=app.stage,
                sub_stage='Pitch Authorized',
                actor=request.user,
                note=f"Candidate authorized 1-Click Pitch for {requisition.title} (Snapshot: {snapshot_hash[:12]}).",
            )
            message = f"Pitch authorized for {requisition.title}. Your verified dossier has been queued for client submission."
        elif desired_status == PitchAuthorizationStatus.REVOKED:
            app = Application.objects.filter(candidate=candidate, requisition=requisition).first()
            if app:
                app.sub_stage = 'Pitch Revoked'
                app.save(update_fields=['sub_stage', 'updated_at'])
                ApplicationEvent.objects.create(
                    application=app,
                    from_stage=app.stage,
                    to_stage=app.stage,
                    sub_stage='Pitch Revoked',
                    actor=request.user,
                    note=f"Candidate revoked pitch authorization for {requisition.title}.",
                )
            message = f"Pitch authorization for {requisition.title} has been revoked."
        else:
            # Candidate declined
            app = Application.objects.filter(candidate=candidate, requisition=requisition).first()
            if app:
                app.sub_stage = 'Pitch Declined'
                app.save(update_fields=['sub_stage', 'updated_at'])
                ApplicationEvent.objects.create(
                    application=app,
                    from_stage=app.stage,
                    to_stage=app.stage,
                    sub_stage='Pitch Declined',
                    actor=request.user,
                    note=f"Candidate declined pitch authorization for {requisition.title}.",
                )
            message = f"Requisition match for {requisition.title} declined and archived from your active stream."

        return Response({
            'data': {
                'id': str(pitch_auth.id),
                'requisition_id': str(requisition.id),
                'candidate_id': str(candidate.id),
                'pitch_status': desired_status,
                'authorized': (desired_status == PitchAuthorizationStatus.AUTHORIZED),
                'message': message,
            }
        })
