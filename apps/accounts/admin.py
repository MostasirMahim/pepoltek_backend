from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import User, UserRole, ConsentRecord


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ['email', 'full_name', 'status', 'mfa_enabled', 'created_at']
    list_filter = ['status', 'auth_provider', 'mfa_enabled']
    search_fields = ['email', 'full_name', 'referral_code']
    readonly_fields = ['id', 'referral_code', 'created_at', 'updated_at', 'last_login_at']
    ordering = ['-created_at']


@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = ['user', 'role', 'created_at']
    list_filter = ['role']
    search_fields = ['user__email']
    autocomplete_fields = ['user']


@admin.register(ConsentRecord)
class ConsentRecordAdmin(ModelAdmin):
    list_display = ['user', 'policy_type', 'policy_version', 'agreed', 'agreed_at']
    list_filter = ['policy_type', 'agreed']
    search_fields = ['user__email']
    readonly_fields = ['user', 'policy_type', 'policy_version', 'agreed', 'agreed_at', 'ip_address']

    def has_add_permission(self, request):
        return False  # Consent records are immutable - never add via admin

    def has_change_permission(self, request, obj=None):
        return False
