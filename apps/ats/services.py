"""
ats/services.py
Business services for ATS pipeline, interview lifecycle, and stage transitions.
Strict House Style Rule: Zero em dashes or en dashes throughout.
"""
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from apps.accounts.models import User
from .models import (
    Application,
    Interview,
    InterviewPanelAssignment,
    InterviewStatus,
    PanelRole,
    InterviewType,
)


def ensure_interview_for_application(application: Application, actor=None, interview_type: str = None) -> Interview:
    """
    Automatically creates a formal Interview session when an application reaches the Interview stage.
    Ensures zero duplicate interviews are generated for the same application.
    Assigns lead interviewer, Google Meet coordinates, candidate preparation notes, and panel assignments.
    """
    existing = Interview.objects.filter(
        application=application,
        status__in=[
            InterviewStatus.SCHEDULED,
            InterviewStatus.CONFIRMED,
            InterviewStatus.IN_PROGRESS,
            InterviewStatus.COMPLETED,
        ]
    ).first()
    if existing:
        return existing

    # Determine default interview format based on requisition sector
    req = application.requisition
    sector_str = (getattr(req, 'sector', '') or '').lower() if req else ''

    if not interview_type:
        if any(h in sector_str for h in ['health', 'clinical', 'nurse', 'doctor', 'physician', 'medical']):
            interview_type = InterviewType.CLINICAL_BOARD
        elif any(t in sector_str for t in ['tech', 'software', 'engineer', 'data', 'cloud', 'developer']):
            interview_type = InterviewType.TECHNICAL_CODING
        else:
            interview_type = InterviewType.BEHAVIORAL_LEADERSHIP

    # Scheduled for 2 business days later at 14:00 UTC
    now = timezone.now()
    scheduled_start = (now + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    scheduled_end = scheduled_start + timedelta(minutes=60)

    # Google Meet link
    app_uuid_compact = str(application.id).replace('-', '')
    meeting_link = f"https://meet.google.com/pek-{app_uuid_compact[:3]}-{app_uuid_compact[3:6]}"

    cand_name = application.candidate.full_name if application.candidate else 'Candidate'
    req_title = req.title if req else 'Open Requisition'
    title = f"Interview: {cand_name} for {req_title}"

    # Determine lead interviewer
    lead_user = application.owner
    if not lead_user and req and req.assigned_recruiter:
        lead_user = req.assigned_recruiter
    if not lead_user and actor and isinstance(actor, User) and actor.is_staff:
        lead_user = actor
    if not lead_user:
        lead_user = User.objects.filter(is_staff=True).first()

    interview = Interview.objects.create(
        application=application,
        title=title,
        interview_type=interview_type,
        round_number=1,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        timezone='UTC',
        meeting_link=meeting_link,
        status=InterviewStatus.SCHEDULED,
        lead_interviewer=lead_user,
        candidate_notes=(
            f"Interview session for {req_title}. "
            "Please join via the Google Meet link 5 minutes before scheduled start with camera and microphone active."
        ),
        internal_brief=(
            f"Candidate dossier and assessment review for {cand_name}. "
            f"Requisition: {req_title}. Review submitted portfolio and vetting scores prior to session."
        ),
    )

    if lead_user:
        InterviewPanelAssignment.objects.get_or_create(
            interview=interview,
            staff_user=lead_user,
            defaults={'role': PanelRole.LEAD_INTERVIEWER, 'has_confirmed': True}
        )

    cand_user = application.candidate.user if application.candidate else None
    if cand_user and cand_user.email:
        start_str = interview.scheduled_start.strftime('%A, %B %d, %Y at %I:%M %p %Z')
        try:
            send_mail(
                subject=f"Pepoltek Interview Scheduled: {req_title}",
                message=(
                    f"Hello {cand_name},\n\n"
                    f"Your interview session for the {req_title} position has been scheduled.\n\n"
                    f"Session: {interview.title}\n"
                    f"Date and Time: {start_str}\n"
                    f"Meeting Link: {interview.meeting_link}\n\n"
                    f"Preparation Notes:\n"
                    f"{interview.candidate_notes}\n\n"
                    f"Best regards,\nPepoltek Recruitment Operations"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[cand_user.email],
                fail_silently=True,
            )
        except Exception:
            pass

    return interview
