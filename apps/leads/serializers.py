from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Lead,
    LeadActivityLog,
    ContactInquiry,
    LeadSource,
    LeadStatus,
    SectorChoice,
    TimelineChoice,
    ContactCategory,
    ContactStatus,
)

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name']

    def get_full_name(self, obj):
        name = getattr(obj, 'full_name', '') or getattr(obj, 'email', '')
        return name or 'Staff Member'


class LeadActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivityLog
        fields = [
            'id',
            'actor',
            'actor_name',
            'action',
            'from_status',
            'to_status',
            'note',
            'created_at',
        ]

    def get_actor_name(self, obj):
        if not obj.actor:
            return 'System'
        name = getattr(obj.actor, 'full_name', '') or getattr(obj.actor, 'email', '')
        return name or 'Staff Member'


class LeadCreateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    specialty_details = serializers.CharField(write_only=True, required=False, allow_blank=True)
    headcount_need = serializers.CharField(write_only=True, required=False, allow_blank=True)
    booking_slot = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Lead
        fields = [
            'id',
            'source',
            'contact_name',
            'work_email',
            'company',
            'phone',
            'sector',
            'roles_needed',
            'headcount',
            'engagement_model',
            'timeline',
            'estimated_budget',
            'preferred_delivery_channel',
            'start_date',
            'notes',
            'calculator_snapshot',
            'booking_data',
            'full_name',
            'email',
            'specialty_details',
            'headcount_need',
            'booking_slot',
        ]
        extra_kwargs = {
            'contact_name': {'required': False},
            'work_email': {'required': False},
            'source': {'required': False, 'default': LeadSource.HIRE_FORM},
        }

    def validate(self, attrs):
        # Normalize full_name -> contact_name
        if not attrs.get('contact_name') and attrs.get('full_name'):
            attrs['contact_name'] = attrs.pop('full_name')

        # Normalize email -> work_email
        if not attrs.get('work_email') and attrs.get('email'):
            attrs['work_email'] = attrs.pop('email')

        if not attrs.get('contact_name'):
            raise serializers.ValidationError({'contact_name': 'Contact name is required.'})

        if not attrs.get('work_email'):
            raise serializers.ValidationError({'work_email': 'Work email is required.'})

        # Normalize specialty_details -> roles_needed
        if attrs.get('specialty_details'):
            existing_roles = attrs.get('roles_needed', '')
            details = attrs.pop('specialty_details')
            attrs['roles_needed'] = f'{existing_roles} | {details}'.strip(' |')

        # Normalize headcount_need string ("2-5", "16+", etc.) into headcount integer
        if attrs.get('headcount_need'):
            raw = str(attrs.pop('headcount_need')).replace('+', '').split('-')[0].strip()
            try:
                attrs['headcount'] = int(raw)
            except ValueError:
                attrs['headcount'] = 1

        # Normalize booking_slot -> booking_data
        if attrs.get('booking_slot'):
            attrs['booking_data'] = {'selected_slot': attrs.pop('booking_slot')}

        # Validate sector
        sector_val = str(attrs.get('sector', '')).lower()
        if sector_val in ['tech', 'technology']:
            attrs['sector'] = SectorChoice.TECHNOLOGY
        elif sector_val in ['health', 'healthcare']:
            attrs['sector'] = SectorChoice.HEALTHCARE
        elif sector_val in ['both', 'hybrid']:
            attrs['sector'] = SectorChoice.BOTH

        return attrs


class LeadBookingSerializer(serializers.Serializer):
    slot = serializers.CharField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class LeadListSerializer(serializers.ModelSerializer):
    owner_details = UserSummarySerializer(source='owner', read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id',
            'company',
            'contact_name',
            'work_email',
            'phone',
            'source',
            'status',
            'sector',
            'headcount',
            'engagement_model',
            'timeline',
            'estimated_budget',
            'preferred_delivery_channel',
            'owner',
            'owner_details',
            'booking_data',
            'created_at',
            'converted_at',
        ]


class LeadDetailSerializer(serializers.ModelSerializer):
    owner_details = UserSummarySerializer(source='owner', read_only=True)
    activity_logs = LeadActivityLogSerializer(many=True, read_only=True)
    converted_client_details = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id',
            'company',
            'contact_name',
            'work_email',
            'phone',
            'source',
            'status',
            'sector',
            'roles_needed',
            'headcount',
            'engagement_model',
            'timeline',
            'estimated_budget',
            'preferred_delivery_channel',
            'start_date',
            'notes',
            'calculator_snapshot',
            'booking_data',
            'owner',
            'owner_details',
            'converted_client',
            'converted_client_details',
            'converted_at',
            'created_at',
            'updated_at',
            'activity_logs',
        ]

    def get_converted_client_details(self, obj):
        if not obj.converted_client:
            return None
        return {
            'id': str(obj.converted_client.id),
            'name': obj.converted_client.name,
            'sector': obj.converted_client.sector,
        }


class LeadStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LeadStatus.choices, required=False)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)


class LeadNoteCreateSerializer(serializers.Serializer):
    note = serializers.CharField(required=True, allow_blank=False)


class LeadConvertSerializer(serializers.Serializer):
    client_name = serializers.CharField(required=False, allow_blank=True)
    requisition_title = serializers.CharField(required=False, allow_blank=True)
    sector = serializers.CharField(required=False, allow_blank=True)
    headcount = serializers.IntegerField(required=False, min_value=1)
    delivery_channel = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)


class ContactInquiryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInquiry
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'category',
            'subject',
            'message',
            'created_at',
        ]


class ContactInquiryListSerializer(serializers.ModelSerializer):
    responder_details = UserSummarySerializer(source='responder', read_only=True)

    class Meta:
        model = ContactInquiry
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'category',
            'subject',
            'status',
            'responder',
            'responder_details',
            'responded_at',
            'created_at',
        ]


class ContactInquiryDetailSerializer(serializers.ModelSerializer):
    responder_details = UserSummarySerializer(source='responder', read_only=True)

    class Meta:
        model = ContactInquiry
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'category',
            'subject',
            'message',
            'status',
            'responder',
            'responder_details',
            'response_notes',
            'responded_at',
            'created_at',
            'updated_at',
        ]


class ContactInquiryUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ContactStatus.choices, required=False)
    response_notes = serializers.CharField(required=False, allow_blank=True)
    responder_id = serializers.UUIDField(required=False, allow_null=True)
