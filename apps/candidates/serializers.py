"""
candidates/serializers.py
DRF serializers for candidate profile, dashboard aggregation, credentials, and documents.
"""
from rest_framework import serializers
from .models import Candidate, Document
from apps.ats.models import Application
from apps.vetting.models import Credential


class CandidateProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    referral_code = serializers.CharField(source='user.referral_code', read_only=True)
    skills = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            'id',
            'full_name',
            'email',
            'phone',
            'sector',
            'domain',
            'level',
            'location',
            'timezone',
            'work_auth',
            'engagement_prefs',
            'desired_hourly_rate',
            'availability_date',
            'open_to_work',
            'portfolio_url',
            'github_url',
            'linkedin_url',
            'bio',
            'skills',
            'profile_strength',
            'cv_score',
            'vetting_status',
            'readiness_tier',
            'referral_code',
        ]

    def get_skills(self, obj: Candidate) -> list[str]:
        if obj.skills_cache:
            return obj.skills_cache
        return list(obj.skills.values_list('skill__name', flat=True))


class CandidateCredentialSerializer(serializers.ModelSerializer):
    issued_on = serializers.DateField(format='%Y-%m-%d', required=False, allow_null=True)
    expires_on = serializers.DateField(format='%Y-%m-%d', required=False, allow_null=True)

    class Meta:
        model = Credential
        fields = [
            'id',
            'kind',
            'name',
            'license_number',
            'jurisdiction',
            'issued_on',
            'expires_on',
            'status',
            'verified_at',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'verified_at', 'created_at']


class CandidateCreateCredentialSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Credential.Kind.choices, default=Credential.Kind.LICENSE)
    name = serializers.CharField(max_length=255)
    license_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    jurisdiction = serializers.CharField(max_length=100, required=False, allow_blank=True)
    issued_on = serializers.DateField(required=False, allow_null=True)
    expires_on = serializers.DateField(required=False, allow_null=True)


class CandidateDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id',
            'doc_type',
            'original_filename',
            'size_bytes',
            'version',
            'scan_status',
            'created_at',
        ]
        read_only_fields = ['id', 'original_filename', 'size_bytes', 'version', 'scan_status', 'created_at']


class CandidateApplicationItemSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='requisition.title', read_only=True)
    requisition_title = serializers.CharField(source='requisition.title', read_only=True)
    requisition_id = serializers.CharField(source='requisition.id', read_only=True)
    client_name = serializers.CharField(source='requisition.client.name', read_only=True)
    location = serializers.CharField(source='requisition.location', read_only=True)
    sector = serializers.CharField(source='requisition.sector', read_only=True)
    level = serializers.CharField(source='requisition.level', read_only=True)
    headcount = serializers.IntegerField(source='requisition.headcount', read_only=True)
    skills = serializers.JSONField(source='requisition.skills', read_only=True)
    budget_min = serializers.IntegerField(source='requisition.budget_min', read_only=True)
    budget_max = serializers.IntegerField(source='requisition.budget_max', read_only=True)
    visibility = serializers.CharField(source='requisition.visibility', read_only=True)
    bounty_amount = serializers.DecimalField(
        source='requisition.bounty_amount', max_digits=8, decimal_places=2, read_only=True
    )

    description = serializers.CharField(source='requisition.description', read_only=True)
    events = serializers.SerializerMethodField()
    interview_details = serializers.SerializerMethodField()
    pitch_status = serializers.SerializerMethodField()
    pitch_authorized = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id',
            'job_title',
            'requisition_title',
            'requisition_id',
            'client_name',
            'location',
            'sector',
            'level',
            'headcount',
            'skills',
            'budget_min',
            'budget_max',
            'visibility',
            'bounty_amount',
            'stage',
            'sub_stage',
            'source',
            'description',
            'events',
            'interview_details',
            'pitch_status',
            'pitch_authorized',
            'created_at',
        ]

    def get_pitch_status(self, obj):
        try:
            from apps.matching.models import PitchAuthorization
            pa = PitchAuthorization.objects.filter(candidate=obj.candidate, requisition=obj.requisition).first()
            if pa:
                return pa.status
            return 'authorized' if obj.sub_stage == 'Pitch Authorized' else 'requested'
        except Exception:
            return 'requested'

    def get_pitch_authorized(self, obj):
        try:
            from apps.matching.models import PitchAuthorization, PitchAuthorizationStatus
            pa = PitchAuthorization.objects.filter(candidate=obj.candidate, requisition=obj.requisition).first()
            if pa:
                return pa.status == PitchAuthorizationStatus.AUTHORIZED
            return obj.sub_stage == 'Pitch Authorized'
        except Exception:
            return False

    def get_events(self, obj):
        try:
            ev_list = obj.events.all().order_by('-timestamp')[:10]
            return [
                {
                    'id': str(e.id),
                    'from_stage': e.from_stage,
                    'to_stage': e.to_stage,
                    'sub_stage': e.sub_stage,
                    'note': e.note,
                    'timestamp': e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in ev_list
            ]
        except Exception:
            return []

    def get_interview_details(self, obj):
        if obj.stage == 'interview':
            return {
                'scheduled_time': 'Tomorrow at 2:00 PM EST',
                'panel': 'Lead Architect & Client Technical Squad',
                'meeting_link': 'https://meet.google.com/pepoltek-sprint',
                'status': 'Confirmed',
            }
        return None


class CandidateIntakeSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    current_location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    sector = serializers.CharField(max_length=20, default='technology')
    current_job_title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    level = serializers.CharField(max_length=20, default='senior')
    years_of_experience = serializers.IntegerField(required=False, default=0)
    domain_skills = serializers.CharField(required=False, allow_blank=True)
    work_auth = serializers.CharField(max_length=30, required=False, allow_blank=True)
    engagement_prefs = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    current_salary = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    expected_salary = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    financial_benefits = serializers.CharField(required=False, allow_blank=True)
    english_proficiency = serializers.CharField(required=False, allow_blank=True)
    notice_period = serializers.CharField(required=False, allow_blank=True)
    interested_roles = serializers.CharField(required=False, allow_blank=True)
    industry_preference = serializers.CharField(required=False, allow_blank=True)
    dream_companies = serializers.CharField(required=False, allow_blank=True)
    reason_for_job_change = serializers.CharField(required=False, allow_blank=True)
    important_criteria = serializers.CharField(required=False, allow_blank=True)
    linkedin_profile = serializers.URLField(required=False, allow_blank=True)
    achievement = serializers.CharField(required=False, allow_blank=True)
    profile_visible = serializers.BooleanField(required=False, default=True)
    source = serializers.CharField(required=False, allow_blank=True)
    referral_name = serializers.CharField(required=False, allow_blank=True)
