"""
ats/tasks.py
Celery background tasks for ATS operations, including the automated 24-hour interview reminder queue.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
from django.core.mail import send_mail
from django.conf import settings
from .models import Interview, InterviewStatus

logger = logging.getLogger('pepoltek.ats.tasks')


@shared_task(queue='notify')
def dispatch_interview_reminders():
    """
    Periodic task: inspects scheduled interviews starting in 23h45m to 24h15m,
    and dispatches 24-hour reminders to candidate and panel members.
    """
    now = timezone.now()
    window_start = now + timedelta(hours=23, minutes=45)
    window_end = now + timedelta(hours=24, minutes=15)

    due_interviews = Interview.objects.filter(
        status=InterviewStatus.SCHEDULED,
        reminder_24h_dispatched=False,
        scheduled_start__gte=window_start,
        scheduled_start__lte=window_end,
    ).select_related(
        'application__candidate__user',
        'application__requisition__client',
        'lead_interviewer'
    ).prefetch_related('assignments__staff_user')

    dispatched_count = 0
    for interview in due_interviews:
        try:
            cand_user = interview.application.candidate.user
            cand_name = interview.application.candidate.full_name or cand_user.get_full_name() or 'Candidate'
            cand_email = cand_user.email
            req_title = interview.application.requisition.title
            client_name = interview.application.requisition.client.name if interview.application.requisition.client else "Pepoltek Client Partner"
            start_str = interview.scheduled_start.strftime('%A, %B %d, %Y at %I:%M %p %Z')

            # 1. Send candidate reminder
            if cand_email:
                send_mail(
                    subject=f"Reminder: Your Technical Interview for {req_title} is in 24 Hours",
                    message=(
                        f"Hello {cand_name},\n\n"
                        f"This is a reminder that your technical interview session for the {req_title} position "
                        f"with {client_name} is scheduled in 24 hours:\n\n"
                        f"Date and Time: {start_str}\n"
                        f"Interview Format: {interview.get_interview_type_display()}\n"
                        f"Meeting Room: {interview.meeting_link or 'Link will be accessible in your dashboard'}\n\n"
                        f"Candidate Preparation Notes:\n"
                        f"{interview.candidate_notes or 'Please ensure a quiet environment with your camera and microphone tested.'}\n\n"
                        f"Access your candidate dashboard to review preparation guidelines:\n"
                        f"{settings.FRONTEND_URL}/candidate/interviews\n\n"
                        f"Best regards,\nPepoltek Recruitment Operations"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[cand_email],
                    fail_silently=True,
                )

            # 2. Send panel members reminders
            panel_emails = []
            if interview.lead_interviewer and interview.lead_interviewer.email:
                panel_emails.append(interview.lead_interviewer.email)
            for assignment in interview.assignments.all():
                if assignment.staff_user.email and assignment.staff_user.email not in panel_emails:
                    panel_emails.append(assignment.staff_user.email)

            if panel_emails:
                send_mail(
                    subject=f"Panel Reminder: {cand_name} Technical Interview in 24 Hours",
                    message=(
                        f"Attention Panel Members,\n\n"
                        f"You are scheduled on the interview panel for candidate {cand_name} "
                        f"applying for {req_title} ({client_name}).\n\n"
                        f"Date and Time: {start_str}\n"
                        f"Interview Format: {interview.get_interview_type_display()}\n"
                        f"Meeting Room: {interview.meeting_link}\n\n"
                        f"Internal Panel Brief:\n"
                        f"{interview.internal_brief or 'Review candidate CV profile and prepare competency scorecard.'}\n\n"
                        f"Direct Evaluation Scorecard:\n"
                        f"{settings.FRONTEND_URL}/recruiter/interviews/{interview.id}\n\n"
                        f"Pepoltek Talent Operations"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=panel_emails,
                    fail_silently=True,
                )

            interview.reminder_24h_dispatched = True
            interview.reminder_24h_dispatched_at = timezone.now()
            interview.save(update_fields=['reminder_24h_dispatched', 'reminder_24h_dispatched_at'])
            dispatched_count += 1
        except Exception as e:
            logger.error(f"Failed to dispatch 24h reminder for interview {interview.id}: {str(e)}")

    return f"Dispatched {dispatched_count} interview reminders."
