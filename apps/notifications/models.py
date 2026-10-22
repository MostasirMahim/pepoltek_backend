"""
notifications/models.py
In-app notification center and email preference settings.
Email sending via Celery task (notify queue) using django-anymail.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class NotificationChannel(models.TextChoices):
    EMAIL = 'email', 'Email'
    IN_APP = 'in_app', 'In-App'


class Notification(BaseModel):
    """In-app notification. Email notifications are tracked separately via send logs."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    notification_type = models.CharField(max_length=50, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    payload = models.JSONField(default=dict)  # extra context (e.g. application_id)
    channel = models.CharField(
        max_length=10, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP
    )
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications_notification'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'read_at'])]

    def __str__(self):
        return f'{self.user.email} - {self.notification_type}'


class NotificationPreference(BaseModel):
    """User opt-in/out per notification type and channel."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_prefs'
    )
    notification_type = models.CharField(max_length=50)
    channel = models.CharField(max_length=10, choices=NotificationChannel.choices)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'notifications_preference'
        unique_together = [('user', 'notification_type', 'channel')]
