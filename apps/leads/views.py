from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.accounts.permissions import IsStaffMember
from django.shortcuts import get_object_or_404
from .models import Lead, LeadStatus
from .serializers import LeadCreateSerializer, LeadBookingSerializer


class LeadCreateView(APIView):
    """
    POST /api/v1/leads/ - Public lead intake from /hire, /contact, or /calculator forms.
    GET /api/v1/leads/ - Staff-only review of inbound leads.
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsStaffMember()]

    def get(self, request):
        leads = Lead.objects.all().order_by('-created_at')[:50]
        data = [
            {
                'id': str(l.id),
                'contact_name': l.contact_name,
                'email': l.email,
                'company': l.company,
                'status': l.status,
                'booking_data': l.booking_data,
                'created_at': l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ]
        return Response({'data': data})

    def post(self, request):
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()

        return Response(
            {
                'data': {
                    'id': str(lead.id),
                    'contact_name': lead.contact_name,
                    'company': lead.company,
                    'status': lead.status,
                    'message': 'Lead received successfully.',
                }
            },
            status=status.HTTP_201_CREATED,
        )


class LeadBookingView(APIView):
    """
    POST /api/v1/leads/<id>/book/
    Schedule instant discovery consultation for an existing lead.
    """
    permission_classes = [AllowAny]

    def post(self, request, id):
        lead = get_object_or_404(Lead, id=id)
        serializer = LeadBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking_info = lead.booking_data or {}
        booking_info.update({
            'selected_slot': serializer.validated_data['slot'],
            'booking_notes': serializer.validated_data.get('notes', ''),
        })

        lead.booking_data = booking_info
        lead.status = LeadStatus.DISCOVERY_BOOKED
        lead.save(update_fields=['booking_data', 'status', 'updated_at'])

        return Response(
            {
                'data': {
                    'id': str(lead.id),
                    'status': lead.status,
                    'booking_data': lead.booking_data,
                    'message': 'Discovery consultation scheduled successfully.',
                }
            },
            status=status.HTTP_200_OK,
        )
