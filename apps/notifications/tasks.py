"""
notifications/tasks.py
Async email sending via Celery notify queue.
All emails go through this - never send email synchronously from views.
"""
import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import Notification, NotificationChannel

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='notifications.send_email',
    queue='notify',
    max_retries=5,
    default_retry_delay=30,
    acks_late=True,
)
def send_email(self, *, to_email: str, subject: str, text_body: str,
               html_body: str = '', reply_to: str = '', notification_id: str = None):
    """
    Send a transactional email. Retries 5 times with backoff.
    Records sent_at on associated Notification if notification_id provided.
    """
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
            reply_to=[reply_to] if reply_to else [],
        )
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        msg.send()

        if notification_id:
            Notification.objects.filter(id=notification_id).update(sent_at=timezone.now())

        logger.info('Email sent to %s subject=%s', to_email, subject)
    except Exception as exc:
        logger.warning('Email failed to %s: %s (retry %s)', to_email, exc, self.request.retries)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@shared_task(
    name='notifications.notify_user',
    queue='notify',
    acks_late=True,
)
def notify_user(*, user_id: str, notification_type: str, title: str,
                body: str, payload: dict = None, send_email_too: bool = False,
                email_subject: str = '', email_text: str = ''):
    """
    Create an in-app Notification and optionally also send email.
    """
    from apps.accounts.models import User
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error('notify_user: user %s not found', user_id)
        return

    notif = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        payload=payload or {},
        channel=NotificationChannel.IN_APP,
    )

    if send_email_too and email_subject and email_text:
        send_email.apply_async(kwargs={
            'to_email': user.email,
            'subject': email_subject,
            'text_body': email_text,
            'notification_id': str(notif.id),
        })
