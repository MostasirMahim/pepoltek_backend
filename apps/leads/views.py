from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import IsStaffMember
from apps.ats.models import Client, ClientContact, Requisition, RequisitionVisibility
from .models import (
    Lead,
    LeadActivityLog,
    ContactInquiry,
    LeadStatus,
    ContactStatus,
)
from .serializers import (
    LeadCreateSerializer,
    LeadBookingSerializer,
    LeadListSerializer,
    LeadDetailSerializer,
    LeadStatusUpdateSerializer,
    LeadNoteCreateSerializer,
    LeadConvertSerializer,
    ContactInquiryCreateSerializer,
    ContactInquiryListSerializer,
    ContactInquiryDetailSerializer,
    ContactInquiryUpdateSerializer,
)

User = get_user_model()


class LeadCreateView(APIView):
    """
    POST /api/v1/leads/ - Public lead intake from hire forms, "Hire Fast" modal, or calculator.
    GET /api/v1/leads/ - Staff-only review and listing of inbound employer leads with metrics.
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsStaffMember()]

    def get(self, request):
        queryset = Lead.objects.select_related('owner', 'converted_client').prefetch_related('activity_logs').all().order_by('-created_at')

        # Filters
        status_filter = request.query_params.get('status')
        sector_filter = request.query_params.get('sector')
        search_query = request.query_params.get('search')

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if sector_filter:
            queryset = queryset.filter(sector=sector_filter)
        if search_query:
            queryset = queryset.filter(
                models_search(search_query)
            )

        # Metrics for dashboard header
        all_leads = Lead.objects.all()
        counts = {
            'total': all_leads.count(),
            'new': all_leads.filter(status=LeadStatus.NEW).count(),
            'contacted': all_leads.filter(status=LeadStatus.CONTACTED).count(),
            'discovery': all_leads.filter(status__in=[LeadStatus.DISCOVERY_BOOKED, LeadStatus.DISCOVERY_RUNNING]).count(),
            'qualified': all_leads.filter(status=LeadStatus.QUALIFIED).count(),
            'converted': all_leads.filter(status=LeadStatus.CONVERTED).count(),
        }

        serializer = LeadListSerializer(queryset[:100], many=True)
        return Response({
            'data': serializer.data,
            'metrics': counts,
        })

    def post(self, request):
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()

        # Create initial audit log
        LeadActivityLog.objects.create(
            lead=lead,
            actor=request.user if request.user.is_authenticated else None,
            action='lead_created',
            to_status=lead.status,
            note=f'Inbound lead submitted via {lead.get_source_display()}. Initial roles: {lead.roles_needed or "General hiring"}.'
        )

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


def models_search(query):
    from django.db.models import Q
    return (
        Q(company__icontains=query) |
        Q(roles_needed__icontains=query) |
        Q(notes__icontains=query)
    )


class LeadDetailView(APIView):
    """
    GET /api/v1/leads/<id>/ - Staff-only detailed view with audit trail.
    PATCH /api/v1/leads/<id>/ - Staff-only update of status or owner with audit logging.
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        lead = get_object_or_404(
            Lead.objects.select_related('owner', 'converted_client').prefetch_related('activity_logs__actor'),
            id=id
        )
        serializer = LeadDetailSerializer(lead)
        return Response({'data': serializer.data})

    def patch(self, request, id):
        lead = get_object_or_404(Lead, id=id)
        serializer = LeadStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prev_status = lead.status
        new_status = serializer.validated_data.get('status')
        owner_id = serializer.validated_data.get('owner_id')
        note = serializer.validated_data.get('note', '')

        status_changed = False
        owner_changed = False

        if new_status and new_status != prev_status:
            lead.status = new_status
            status_changed = True

        if 'owner_id' in serializer.validated_data:
            if owner_id:
                new_owner = get_object_or_404(User, id=owner_id)
                if lead.owner != new_owner:
                    lead.owner = new_owner
                    owner_changed = True
            else:
                lead.owner = None
                owner_changed = True

        lead.save()

        # Audit log creation
        if status_changed:
            LeadActivityLog.objects.create(
                lead=lead,
                actor=request.user,
                action='status_change',
                from_status=prev_status,
                to_status=new_status,
                note=note or f'Status updated to {lead.get_status_display()}.',
            )
        elif owner_changed:
            owner_label = lead.owner.get_full_name() or lead.owner.email if lead.owner else 'Unassigned'
            LeadActivityLog.objects.create(
                lead=lead,
                actor=request.user,
                action='owner_assigned',
                note=f'Owner assigned to {owner_label}. {note}'.strip(),
            )
        elif note:
            LeadActivityLog.objects.create(
                lead=lead,
                actor=request.user,
                action='note_added',
                note=note,
            )

        updated_lead = Lead.objects.select_related('owner', 'converted_client').prefetch_related('activity_logs__actor').get(id=id)
        return Response({'data': LeadDetailSerializer(updated_lead).data})


class LeadNoteView(APIView):
    """
    POST /api/v1/leads/<id>/notes/ - Append internal staff note to lead activity log.
    """
    permission_classes = [IsStaffMember]

    def post(self, request, id):
        lead = get_object_or_404(Lead, id=id)
        serializer = LeadNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note_content = serializer.validated_data['note']
        activity = LeadActivityLog.objects.create(
            lead=lead,
            actor=request.user,
            action='note_added',
            note=note_content,
        )

        return Response({
            'data': {
                'id': str(activity.id),
                'actor_name': request.user.get_full_name() or request.user.email,
                'action': activity.action,
                'note': activity.note,
                'created_at': activity.created_at.isoformat(),
            }
        }, status=status.HTTP_201_CREATED)


class LeadConvertView(APIView):
    """
    POST /api/v1/leads/<id>/convert/
    Staff-only action: Convert qualified lead to authentic ATS Client and initial Requisition.
    """
    permission_classes = [IsStaffMember]

    def post(self, request, id):
        lead = get_object_or_404(Lead, id=id)
        if lead.status == LeadStatus.CONVERTED and lead.converted_client:
            return Response(
                {'error': f'Lead has already been converted to Client: {lead.converted_client.name}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LeadConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client_name = serializer.validated_data.get('client_name') or lead.company
        req_title = serializer.validated_data.get('requisition_title') or lead.roles_needed or f'Talent Search - {client_name}'
        sector = serializer.validated_data.get('sector') or lead.sector or 'technology'
        headcount = serializer.validated_data.get('headcount') or lead.headcount or 1
        delivery_channel = serializer.validated_data.get('delivery_channel') or lead.preferred_delivery_channel or 'email'
        note = serializer.validated_data.get('note', '')

        with transaction.atomic():
            # 1. Create ATS Client
            client = Client.objects.create(
                name=client_name,
                sector=sector,
                delivery_channel=delivery_channel,
                owner=lead.owner or request.user,
            )

            # 2. Create primary ClientContact
            ClientContact.objects.create(
                client=client,
                full_name=lead.contact_name,
                email=lead.work_email,
                phone=lead.phone or '',
                is_primary=True,
                role_title='Hiring Sponsor',
            )

            # 3. Create initial Requisition
            requisition = Requisition.objects.create(
                client=client,
                title=req_title,
                sector=sector,
                headcount=headcount,
                engagement=lead.engagement_model or 'staff_aug',
                visibility=RequisitionVisibility.PRIVATE,
            )

            # 4. Update Lead status
            prev_status = lead.status
            lead.status = LeadStatus.CONVERTED
            lead.converted_client = client
            lead.converted_at = timezone.now()
            lead.save()

            # 5. Log audit trail
            conversion_note = f'Converted to Client "{client.name}" and opened Requisition "{requisition.title}".'
            if note:
                conversion_note += f' Notes: {note}'

            LeadActivityLog.objects.create(
                lead=lead,
                actor=request.user,
                action='converted',
                from_status=prev_status,
                to_status=LeadStatus.CONVERTED,
                note=conversion_note,
            )

        return Response({
            'data': {
                'lead_id': str(lead.id),
                'client_id': str(client.id),
                'client_name': client.name,
                'requisition_id': str(requisition.id),
                'requisition_title': requisition.title,
                'message': f'Lead successfully converted to client "{client.name}" and requisition created.',
            }
        }, status=status.HTTP_200_OK)


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
            'booked_at': timezone.now().isoformat(),
        })

        lead.booking_data = booking_info
        prev_status = lead.status
        lead.status = LeadStatus.DISCOVERY_BOOKED
        lead.save(update_fields=['booking_data', 'status', 'updated_at'])

        LeadActivityLog.objects.create(
            lead=lead,
            actor=request.user if request.user.is_authenticated else None,
            action='consultation_booked',
            from_status=prev_status,
            to_status=LeadStatus.DISCOVERY_BOOKED,
            note=f"Free consultation booked for slot: {serializer.validated_data['slot']}",
        )

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


class ContactInquiryCreateView(APIView):
    """
    POST /api/v1/leads/contacts/ - Public general contact submission from /contact page.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ContactInquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inquiry = serializer.save()

        return Response(
            {
                'data': {
                    'id': str(inquiry.id),
                    'name': inquiry.name,
                    'email': inquiry.email,
                    'category': inquiry.category,
                    'subject': inquiry.subject,
                    'status': inquiry.status,
                    'message': 'Your inquiry has been received. Our team will review and respond promptly.',
                }
            },
            status=status.HTTP_201_CREATED,
        )


class ContactInquiryListView(APIView):
    """
    GET /api/v1/leads/contacts/admin/ - Staff-only review of inbound contact inquiries.
    """
    permission_classes = [IsStaffMember]

    def get(self, request):
        queryset = ContactInquiry.objects.select_related('responder').all().order_by('-created_at')

        status_filter = request.query_params.get('status')
        category_filter = request.query_params.get('category')
        search_query = request.query_params.get('search')

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(subject__icontains=search_query) |
                Q(message__icontains=search_query)
            )

        all_inquiries = ContactInquiry.objects.all()
        counts = {
            'total': all_inquiries.count(),
            'new': all_inquiries.filter(status=ContactStatus.NEW).count(),
            'in_progress': all_inquiries.filter(status=ContactStatus.IN_PROGRESS).count(),
            'responded': all_inquiries.filter(status=ContactStatus.RESPONDED).count(),
            'closed': all_inquiries.filter(status=ContactStatus.CLOSED).count(),
        }

        serializer = ContactInquiryListSerializer(queryset[:100], many=True)
        return Response({
            'data': serializer.data,
            'metrics': counts,
        })


class ContactInquiryDetailView(APIView):
    """
    GET /api/v1/leads/contacts/admin/<id>/ - Staff-only detail of general inquiry.
    PATCH /api/v1/leads/contacts/admin/<id>/ - Staff-only update status, responder, response notes.
    """
    permission_classes = [IsStaffMember]

    def get(self, request, id):
        inquiry = get_object_or_404(ContactInquiry.objects.select_related('responder'), id=id)
        serializer = ContactInquiryDetailSerializer(inquiry)
        return Response({'data': serializer.data})

    def patch(self, request, id):
        inquiry = get_object_or_404(ContactInquiry, id=id)
        serializer = ContactInquiryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if 'status' in serializer.validated_data:
            inquiry.status = serializer.validated_data['status']
            if inquiry.status == ContactStatus.RESPONDED and not inquiry.responded_at:
                inquiry.responded_at = timezone.now()

        if 'response_notes' in serializer.validated_data:
            inquiry.response_notes = serializer.validated_data['response_notes']

        if 'responder_id' in serializer.validated_data:
            resp_id = serializer.validated_data['responder_id']
            if resp_id:
                inquiry.responder = get_object_or_404(User, id=resp_id)
            else:
                inquiry.responder = None
        elif not inquiry.responder and request.user.is_authenticated:
            # Auto-assign current staff user if not set
            inquiry.responder = request.user

        inquiry.save()

        updated_inquiry = ContactInquiry.objects.select_related('responder').get(id=id)
        return Response({'data': ContactInquiryDetailSerializer(updated_inquiry).data})
