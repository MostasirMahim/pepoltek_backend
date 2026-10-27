from django.contrib import admin
from .models import Lead, LeadActivityLog, ContactInquiry


class LeadActivityLogInline(admin.TabularInline):
    model = LeadActivityLog
    extra = 0
    readonly_fields = ('actor', 'action', 'from_status', 'to_status', 'note', 'created_at')
    can_delete = False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('company', 'contact_name', 'status', 'source', 'sector', 'headcount', 'timeline', 'owner', 'created_at')
    list_filter = ('status', 'source', 'sector', 'timeline')
    search_fields = ('company', 'contact_name', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'converted_at')
    inlines = [LeadActivityLogInline]


@admin.register(LeadActivityLog)
class LeadActivityLogAdmin(admin.ModelAdmin):
    list_display = ('lead', 'actor', 'action', 'from_status', 'to_status', 'created_at')
    list_filter = ('action', 'to_status')
    search_fields = ('lead__company', 'note')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'category', 'subject', 'status', 'responder', 'responded_at', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('name', 'email', 'subject', 'message', 'response_notes')
    readonly_fields = ('created_at', 'updated_at')
