from django.contrib import admin
from .models import (
    Client,
    Requisition,
    Application,
    ApplicationEvent,
    Submission,
    Placement,
    Interview,
    InterviewPanelAssignment,
    InterviewEvaluation,
)


class InterviewPanelAssignmentInline(admin.TabularInline):
    model = InterviewPanelAssignment
    extra = 1


class InterviewEvaluationInline(admin.StackedInline):
    model = InterviewEvaluation
    extra = 0
    readonly_fields = ['submitted_at']


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'application',
        'interview_type',
        'round_number',
        'scheduled_start',
        'status',
        'lead_interviewer',
        'reminder_24h_dispatched',
    ]
    list_filter = ['status', 'interview_type', 'reminder_24h_dispatched', 'scheduled_start']
    search_fields = ['title', 'application__candidate__user__email', 'application__candidate__user__first_name', 'application__candidate__user__last_name']
    inlines = [InterviewPanelAssignmentInline, InterviewEvaluationInline]


@admin.register(InterviewEvaluation)
class InterviewEvaluationAdmin(admin.ModelAdmin):
    list_display = ['interview', 'evaluator', 'score', 'recommendation', 'submitted_at']
    list_filter = ['recommendation', 'submitted_at']
    search_fields = ['interview__title', 'evaluator__email', 'evaluator__first_name', 'evaluator__last_name']


admin.site.register(Client)
admin.site.register(Requisition)
admin.site.register(Application)
admin.site.register(ApplicationEvent)
admin.site.register(Submission)
admin.site.register(Placement)
