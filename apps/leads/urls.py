from django.urls import path
from .views import LeadCreateView, LeadBookingView

urlpatterns = [
    path('', LeadCreateView.as_view(), name='lead-create'),
    path('<uuid:id>/book/', LeadBookingView.as_view(), name='lead-book-consultation'),
]
