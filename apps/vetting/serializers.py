# vetting/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import (
    AssessmentTemplate,
    ApplicationVetting,
    VettingAnswer,
    VettingScore,
    Credential,
    CredentialStatus,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared lightweight user repr
# ---------------------------------------------------------------------------

class ValidatorUserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'full_name', 'email']


# ---------------------------------------------------------------------------
# AssessmentTemplate
# ---------------------------------------------------------------------------

class AssessmentTemplateListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    vettings_count = serializers.IntegerField(source='vettings.count', read_only=True)
    criteria_count = serializers.SerializerMethodField()

    class Meta:
        model  = AssessmentTemplate
        fields = [
            'id', 'title', 'category', 'sector', 'description', 'instructions',
            'total_marks', 'is_active', 'version', 'created_by_name', 'created_at',
            'marks_distribution', 'prerequisites', 'allowed_validator_roles',
            'vettings_count', 'criteria_count',
        ]

    def get_criteria_count(self, obj):
        return len(obj.marks_distribution) if isinstance(obj.marks_distribution, list) else 0


class AssessmentTemplateDetailSerializer(serializers.ModelSerializer):
    created_by = ValidatorUserSerializer(read_only=True)
    vettings_count = serializers.IntegerField(source='vettings.count', read_only=True)
    vettings = serializers.SerializerMethodField()

    class Meta:
        model  = AssessmentTemplate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'version']

    def get_vettings(self, obj):
        vettings_qs = obj.vettings.select_related(
            'primary_validator', 'application__candidate__user', 'application__requisition'
        ).all()
        return ApplicationVettingListSerializer(vettings_qs, many=True).data


class AssessmentTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssessmentTemplate
        exclude = ['created_by', 'version', 'created_at', 'updated_at', 'archived_at']

    def validate_marks_distribution(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('marks_distribution must be a list.')
        total = sum(item.get('max_points', 0) for item in value)
        if total > 100:
            raise serializers.ValidationError(
                f'Sum of max_points ({total}) exceeds 100.'
            )
        return value

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# ApplicationVetting
# ---------------------------------------------------------------------------

class ApplicationVettingListSerializer(serializers.ModelSerializer):
    template_id        = serializers.UUIDField(source='template.id', read_only=True)
    template_title     = serializers.CharField(source='template.title', read_only=True)
    template_category  = serializers.CharField(source='template.category', read_only=True)
    template_sector    = serializers.CharField(source='template.sector', read_only=True)
    total_marks        = serializers.IntegerField(source='template.total_marks', read_only=True)
    marks_distribution = serializers.JSONField(source='template.marks_distribution', read_only=True)
    instructions       = serializers.CharField(source='template.instructions', read_only=True)
    candidate_name     = serializers.CharField(source='application.candidate.user.full_name', read_only=True, default='')
    job_title          = serializers.CharField(source='application.requisition.title', read_only=True, default='')
    primary_validator  = ValidatorUserSerializer(read_only=True)
    is_overdue         = serializers.BooleanField(read_only=True)
    application_id     = serializers.UUIDField(read_only=True)
    target_due_date    = serializers.DateTimeField(source='deadline', read_only=True)

    class Meta:
        model  = ApplicationVetting
        fields = [
            'id', 'application_id', 'candidate_name', 'job_title',
            'template_id', 'template_title', 'template_category', 'template_sector',
            'total_marks', 'marks_distribution', 'instructions',
            'status', 'final_score', 'pass_threshold',
            'scheduled_start', 'deadline', 'target_due_date', 'primary_validator', 'is_overdue',
            'created_at',
        ]


class ApplicationVettingDetailSerializer(serializers.ModelSerializer):
    template           = AssessmentTemplateListSerializer(read_only=True)
    primary_validator  = ValidatorUserSerializer(read_only=True)
    secondary_validators = ValidatorUserSerializer(many=True, read_only=True)
    assigned_by        = ValidatorUserSerializer(read_only=True)
    is_overdue         = serializers.BooleanField(read_only=True)
    target_due_date    = serializers.DateTimeField(source='deadline', read_only=True)

    class Meta:
        model  = ApplicationVetting
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'final_score']


class ApplicationVettingCreateSerializer(serializers.ModelSerializer):
    secondary_validator_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False, default=list
    )

    class Meta:
        model  = ApplicationVetting
        fields = [
            'application', 'template', 'scheduled_start', 'deadline',
            'primary_validator', 'secondary_validator_ids',
            'recruiter_notes', 'pass_threshold',
        ]

    def create(self, validated_data):
        secondary_ids = validated_data.pop('secondary_validator_ids', [])
        actor = self.context['request'].user
        validated_data['assigned_by'] = actor
        vetting = super().create(validated_data)
        if secondary_ids:
            vetting.secondary_validators.set(secondary_ids)

        # Immediately advance the application to Stage 3: Technical Vetting
        app = vetting.application
        if app.stage in ['discovery', 'market_mapping']:
            from apps.ats.models import ApplicationStage, ApplicationEvent
            from_stage = app.stage
            app.stage = ApplicationStage.TECHNICAL_VETTING
            app.sub_stage = 'Assessment Dispatched'
            app.save(update_fields=['stage', 'sub_stage', 'updated_at'])
            ApplicationEvent.objects.create(
                application=app,
                from_stage=from_stage,
                to_stage=ApplicationStage.TECHNICAL_VETTING,
                sub_stage='Assessment Dispatched',
                actor=actor,
                note=f"Technical vetting assessment '{vetting.template.title}' dispatched. Target Due Date: {vetting.deadline.strftime('%Y-%m-%d') if vetting.deadline else 'Pending'}."
            )
        return vetting


class ApplicationVettingUpdateSerializer(serializers.ModelSerializer):
    secondary_validator_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        model  = ApplicationVetting
        fields = [
            'status', 'scheduled_start', 'deadline',
            'primary_validator', 'secondary_validator_ids',
            'recruiter_notes', 'pass_threshold', 'decision_notes',
        ]

    def update(self, instance, validated_data):
        secondary_ids = validated_data.pop('secondary_validator_ids', None)
        instance = super().update(instance, validated_data)
        if secondary_ids is not None:
            instance.secondary_validators.set(secondary_ids)
        return instance


# ---------------------------------------------------------------------------
# VettingAnswer
# ---------------------------------------------------------------------------

class VettingAnswerSerializer(serializers.ModelSerializer):
    submitted_by = ValidatorUserSerializer(read_only=True)

    class Meta:
        model  = VettingAnswer
        fields = '__all__'
        read_only_fields = ['id', 'vetting', 'submitted_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['submitted_by'] = self.context['request'].user
        return super().create(validated_data)


class VettingAnswerWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VettingAnswer
        exclude = ['submitted_by', 'created_at', 'updated_at', 'archived_at']
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['submitted_by'] = self.context['request'].user
        return super().create(validated_data)

    def validate_criterion_scores(self, value):
        for item in value:
            if item.get('awarded_points', 0) > item.get('max_points', 0):
                raise serializers.ValidationError(
                    f"awarded_points exceeds max_points for criterion '{item.get('criterion')}'."
                )
        return value


# ---------------------------------------------------------------------------
# VettingScore
# ---------------------------------------------------------------------------

class VettingScoreSerializer(serializers.ModelSerializer):
    scored_by = ValidatorUserSerializer(read_only=True)

    class Meta:
        model  = VettingScore
        fields = '__all__'
        read_only_fields = ['id', 'vetting', 'scored_by', 'scored_at', 'created_at', 'updated_at']


class VettingScoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VettingScore
        fields = ['score', 'verdict', 'feedback']

    def validate(self, attrs):
        vetting = self.context['vetting']
        request = self.context['request']
        # Only primary validator may score
        if vetting.primary_validator_id != request.user.id and not request.user.is_superuser:
            raise serializers.ValidationError(
                'Only the designated primary validator may submit a final score.'
            )
        if hasattr(vetting, 'score_record'):
            raise serializers.ValidationError(
                'A final score has already been submitted for this vetting.'
            )
        return attrs

    def create(self, validated_data):
        validated_data['vetting']    = self.context['vetting']
        validated_data['scored_by']  = self.context['request'].user
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Credential
# ---------------------------------------------------------------------------

class CredentialSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True)

    class Meta:
        model  = Credential
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'verified_by', 'verified_at']

