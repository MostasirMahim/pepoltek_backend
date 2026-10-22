from rest_framework import serializers
from .models import Lead, LeadSource, LeadStatus, SectorChoice


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
