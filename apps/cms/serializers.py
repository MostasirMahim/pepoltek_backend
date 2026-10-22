"""
cms/serializers.py
DRF serializers for CMS content management API.
"""
from rest_framework import serializers
from .models import SiteContent


class SiteContentPublishSerializer(serializers.Serializer):
    """Input serializer for publish and save-draft endpoints."""
    data = serializers.JSONField(
        help_text='The full structured content payload for this block.'
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=500,
        help_text='Optional editor notes describing what changed.',
    )


class SiteContentRollbackSerializer(serializers.Serializer):
    """Input serializer for rollback endpoint."""
    target_version = serializers.IntegerField(min_value=1)


class SiteContentVersionSerializer(serializers.ModelSerializer):
    """Serializer for history list."""
    author_name = serializers.SerializerMethodField()
    key_display = serializers.CharField(source='get_key_display', read_only=True)

    class Meta:
        model = SiteContent
        fields = [
            'id', 'key', 'key_display', 'version', 'data', 'notes',
            'is_published', 'author_name', 'created_at', 'updated_at',
        ]

    def get_author_name(self, obj) -> str:
        if obj.author:
            return obj.author.full_name or obj.author.email
        return 'System'


class CaseStudySerializer(serializers.Serializer):
    """Validates a single case study entry."""
    slug = serializers.SlugField(max_length=120)
    title = serializers.CharField(max_length=250)
    sector = serializers.ChoiceField(choices=['tech', 'healthcare', 'finance', 'other'])
    sectorLabel = serializers.CharField(max_length=100)
    client = serializers.CharField(max_length=150)
    timeline = serializers.CharField(max_length=80)
    summary = serializers.CharField(max_length=600)
    challenge = serializers.CharField()
    solution = serializers.CharField()
    metrics = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=8,
    )
    quote = serializers.DictField(required=False, allow_null=True)


class CaseStudiesPayloadSerializer(serializers.Serializer):
    """Wraps the full case studies list for bulk publish."""
    studies = serializers.ListField(
        child=CaseStudySerializer(),
        min_length=0,
    )
