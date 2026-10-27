from django.urls import path
from .views import (
    LeadCreateView,
    LeadDetailView,
    LeadBookingView,
    LeadNoteView,
    LeadConvertView,
    ContactInquiryCreateView,
    ContactInquiryListView,
    ContactInquiryDetailView,
)

urlpatterns = [
    # Employer Leads
    path('', LeadCreateView.as_view(), name='lead-list-create'),
    path('<uuid:id>/', LeadDetailView.as_view(), name='lead-detail'),
    path('<uuid:id>/book/', LeadBookingView.as_view(), name='lead-book-consultation'),
    path('<uuid:id>/notes/', LeadNoteView.as_view(), name='lead-note-create'),
    path('<uuid:id>/convert/', LeadConvertView.as_view(), name='lead-convert'),

    # General Inquiries & Contacts
    path('contacts/', ContactInquiryCreateView.as_view(), name='contact-inquiry-create'),
    path('contacts/admin/', ContactInquiryListView.as_view(), name='contact-inquiry-admin-list'),
    path('contacts/admin/<uuid:id>/', ContactInquiryDetailView.as_view(), name='contact-inquiry-admin-detail'),
]
