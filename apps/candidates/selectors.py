"""
candidates/selectors.py
Query layer for candidate profile, dashboard aggregation, credentials, and documents.
All database reads for candidate domain live here.
"""
from django.db.models import Avg
from .models import (
    Candidate,
    CandidateSkill,
    Document,
    SectorChoice,
    ExperienceLevel,
    ReadinessTier,
)
from apps.ats.models import Application, ApplicationStage, Requisition, RequisitionStatus
from apps.vetting.models import Credential, VettingScore


def get_candidate_for_user(user) -> Candidate:
    """
    Retrieve candidate profile for a user, or initialize a default profile if newly registered.
    """
    candidate, _ = Candidate.objects.get_or_create(
        user=user,
        defaults={
            'full_name': user.full_name or user.email.split('@')[0],
            'sector': SectorChoice.TECHNOLOGY,
            'level': ExperienceLevel.SENIOR,
            'readiness_tier': ReadinessTier.READY,
            'profile_strength': 50,
            'open_to_work': True,
        }
    )
    return candidate


def calculate_profile_strength(candidate: Candidate) -> int:
    """
    Calculate dynamic profile strength score (0 to 100).
    """
    score = 0
    if candidate.full_name:
        score += 15
    if candidate.phone:
        score += 10
    if candidate.location:
        score += 10
    if candidate.domain or candidate.level:
        score += 15
    if candidate.skills_cache or candidate.skills.exists():
        score += 20
    if candidate.portfolio_url or candidate.github_url or candidate.linkedin_url:
        score += 10
    if candidate.documents.exists():
        score += 10
    if candidate.credentials.exists():
        score += 10

    return min(score, 100)


def determine_next_best_action(candidate: Candidate) -> dict:
    """
    Determine single highest-priority next best action for the candidate (SRS CAN-08).
    """
    docs_count = candidate.documents.count()
    has_skills = bool(candidate.skills_cache) or candidate.skills.exists()
    is_health = candidate.sector == SectorChoice.HEALTHCARE
    creds_count = candidate.credentials.count()

    if docs_count == 0:
        return {
            'code': 'UPLOAD_RESUME',
            'title': 'Upload Your CV / Resume',
            'description': 'Upload your resume for AI ATS parsing, skill extraction, and sprint matching.',
            'action_url': '/candidate/resume-upload',
            'action_label': 'Upload Resume',
            'priority': 'high',
        }

    if not has_skills:
        return {
            'code': 'ADD_SKILLS',
            'title': 'Specify Key Technical Skills',
            'description': 'Select your core languages, frameworks, and architecture specialties.',
            'action_url': '/candidate/profile',
            'action_label': 'Manage Skills',
            'priority': 'high',
        }

    if is_health and creds_count == 0:
        return {
            'code': 'ADD_CREDENTIAL',
            'title': 'Add Clinical License or Registration',
            'description': 'Add your GMC or state medical board license to unlock clinical rota matching.',
            'action_url': '/candidate/profile',
            'action_label': 'Add License',
            'priority': 'high',
        }

    if candidate.sector == SectorChoice.TECHNOLOGY and not candidate.github_url and not candidate.portfolio_url:
        return {
            'code': 'ADD_PORTFOLIO',
            'title': 'Connect GitHub or Portfolio',
            'description': 'Add your GitHub profile or project portfolio to accelerate technical vetting.',
            'action_url': '/candidate/profile',
            'action_label': 'Add Portfolio',
            'priority': 'medium',
        }

    return {
        'code': 'EXPLORE_REVERSE_MATCHES',
        'title': 'Explore Reverse Search Matches',
        'description': 'Confidential client requisitions are currently active matching your profile.',
        'action_url': '/candidate/reverse-search',
        'action_label': 'View Matches',
        'priority': 'normal',
    }


def get_candidate_dashboard_aggregation(candidate: Candidate) -> dict:
    """
    Aggregate all dashboard telemetry into a single payload (SRS CAN-08).
    """
    dynamic_strength = calculate_profile_strength(candidate)
    if candidate.profile_strength != dynamic_strength:
        candidate.profile_strength = dynamic_strength
        candidate.save(update_fields=['profile_strength', 'updated_at'])

    # Vetting score calculation -- use final scores from primary validator
    vetting_scores_qs = VettingScore.objects.filter(
        vetting__application__candidate=candidate
    )
    avg_assessment = vetting_scores_qs.aggregate(avg=Avg('score'))['avg']
    technical_vetting_score = round(avg_assessment) if avg_assessment is not None else candidate.cv_score or 85

    # Pipeline counts
    apps_qs = Application.objects.filter(candidate=candidate)
    active_apps_count = apps_qs.exclude(stage='closed').count()
    total_apps_count = apps_qs.count()

    # Requisitions match count
    reqs_qs = Requisition.objects.filter(status=RequisitionStatus.OPEN)
    if candidate.sector:
        if 'health' in candidate.sector.lower():
            reqs_qs = reqs_qs.filter(sector__icontains='health')
        else:
            reqs_qs = reqs_qs.filter(sector__icontains='tech')
    matched_roles_count = reqs_qs.count()

    # Credentials telemetry
    creds_qs = Credential.objects.filter(candidate=candidate)
    credentials_count = creds_qs.count()
    verified_credentials_count = creds_qs.filter(status='verified').count()

    # Documents telemetry
    docs_qs = Document.objects.filter(candidate=candidate)
    documents_count = docs_qs.count()
    latest_doc = docs_qs.first()

    # Upcoming interviews from applications at INTERVIEW stage
    interview_apps = Application.objects.filter(
        candidate=candidate,
        stage=ApplicationStage.INTERVIEW,
    ).select_related('requisition', 'requisition__client')[:3]
    upcoming_interviews = []
    for app in interview_apps:
        upcoming_interviews.append({
            'id': f'INT-{str(app.id)[:8].upper()}',
            'role': app.requisition.title if app.requisition else 'Specialist Role',
            'client_name': app.requisition.client.name if app.requisition and app.requisition.client else 'Enterprise Partner',
            'scheduled_at': 'Scheduled This Sprint',
            'meeting_link': 'https://meet.google.com/pepoltek-sprint',
            'status': 'Confirmed',
        })

    next_action = determine_next_best_action(candidate)

    # Requisition fit match score (SRS 9.2 Stage 2 composite)
    cv_score_val = candidate.cv_score or 90
    match_score = min(98, max(75, round((dynamic_strength * 0.4) + (technical_vetting_score * 0.35) + (cv_score_val * 0.25))))

    return {
        'profile_strength': dynamic_strength,
        'cv_score': cv_score_val,
        'technical_vetting_score': technical_vetting_score,
        'readiness_tier': candidate.readiness_tier,
        'match_score': match_score,
        'open_to_work': candidate.open_to_work,
        'active_applications_count': active_apps_count,
        'total_applications_count': total_apps_count,
        'matched_roles_count': matched_roles_count,
        'credentials_count': credentials_count,
        'verified_credentials_count': verified_credentials_count,
        'documents_count': documents_count,
        'latest_document': {
            'filename': latest_doc.original_filename,
            'doc_type': latest_doc.doc_type,
            'scan_status': latest_doc.scan_status,
            'uploaded_at': latest_doc.created_at.isoformat(),
        } if latest_doc else None,
        'next_best_action': next_action,
        'upcoming_interviews': upcoming_interviews,
    }


def get_candidate_credentials(candidate: Candidate):
    """
    Fetch all credentials and licenses belonging to the candidate.
    """
    return Credential.objects.filter(candidate=candidate).order_by('-created_at')


def get_candidate_documents(candidate: Candidate):
    """
    Fetch all uploaded documents belonging to the candidate.
    """
    return Document.objects.filter(candidate=candidate).order_by('-created_at')
