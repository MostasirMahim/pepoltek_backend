"""
academy/models.py
Talent Academy - courses, modules, enrollment, badges, user badges.
Phase 3. Managed by ADMIN / SUPER_ADMIN via Django Admin + Wagtail CMS.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class CourseStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    ARCHIVED = 'archived', 'Archived'


class Course(BaseModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    sector = models.CharField(max_length=20, blank=True)  # tech / healthcare / both
    status = models.CharField(max_length=20, choices=CourseStatus.choices, default=CourseStatus.DRAFT)
    cover_image_key = models.CharField(max_length=500, blank=True)
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        db_table = 'academy_course'
        ordering = ['title']

    def __str__(self):
        return self.title


class ModuleType(models.TextChoices):
    VIDEO = 'video', 'Video'
    TEXT = 'text', 'Article / Text'
    QUIZ = 'quiz', 'Quiz'
    EXTERNAL = 'external', 'External Link'


class CourseModule(BaseModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    module_type = models.CharField(max_length=20, choices=ModuleType.choices)
    content = models.JSONField(default=dict)  # type-specific: {url, text, questions[]}
    order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        db_table = 'academy_course_module'
        ordering = ['course', 'order']


class Enrollment(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments'
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    progress_pct = models.PositiveSmallIntegerField(default=0)  # 0-100
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'academy_enrollment'
        unique_together = [('user', 'course')]


class Badge(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_key = models.CharField(max_length=500, blank=True)
    rules = models.JSONField(default=dict)  # e.g. {course_id, min_score, assessment_type}

    class Meta:
        db_table = 'academy_badge'

    def __str__(self):
        return self.name


class UserBadge(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges'
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_to')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'academy_user_badge'
        unique_together = [('user', 'badge')]
