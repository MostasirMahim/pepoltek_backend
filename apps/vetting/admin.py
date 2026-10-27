# vetting/admin.py
from django.contrib import admin
from .models import AssessmentTemplate, ApplicationVetting, VettingAnswer, VettingScore, Credential


@admin.register(AssessmentTemplate)
class AssessmentTemplateAdmin(admin.ModelAdmin):
    list_display  = ['title', 'category', 'sector', 'total_marks', 'is_active', 'version', 'created_by', 'created_at']
    list_filter   = ['category', 'sector', 'is_active']
    search_fields = ['title', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']


@admin.register(ApplicationVetting)
class ApplicationVettingAdmin(admin.ModelAdmin):
    list_display  = ['id', 'application', 'template', 'status', 'primary_validator', 'final_score', 'deadline']
    list_filter   = ['status']
    search_fields = ['application__id', 'template__title']
    readonly_fields = ['assigned_by', 'final_score', 'created_at', 'updated_at']
    filter_horizontal = ['secondary_validators']


@admin.register(VettingAnswer)
class VettingAnswerAdmin(admin.ModelAdmin):
    list_display  = ['id', 'vetting', 'submitted_by', 'subtotal_score', 'is_final_submission', 'created_at']
    list_filter   = ['is_final_submission']
    readonly_fields = ['submitted_by', 'created_at']


@admin.register(VettingScore)
class VettingScoreAdmin(admin.ModelAdmin):
    list_display  = ['vetting', 'scored_by', 'score', 'verdict', 'scored_at']
    list_filter   = ['verdict']
    readonly_fields = ['scored_by', 'scored_at', 'created_at']


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display  = ['name', 'candidate', 'kind', 'status', 'expires_on', 'verified_by']
    list_filter   = ['status', 'kind']
    search_fields = ['name', 'jurisdiction']
    readonly_fields = ['verified_by', 'verified_at', 'created_at', 'updated_at']

