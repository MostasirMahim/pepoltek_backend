"""
resumes/models.py
Upload ingestion and parse tracking.
Parse states: queued → scanning → extracting → parsing → done | failed | quarantined
"""
from django.db import models
from apps.core.models import BaseModel
from apps.candidates.models import Document


class ParseStatus(models.TextChoices):
    QUEUED = 'queued', 'Queued'
    SCANNING = 'scanning', 'Scanning for Malware'
    EXTRACTING = 'extracting', 'Extracting Text'
    PARSING = 'parsing', 'AI Parsing'
    DONE = 'done', 'Done'
    FAILED = 'failed', 'Failed'
    QUARANTINED = 'quarantined', 'Quarantined (Infected)'


class ResumeParse(BaseModel):
    """
    One parse per document upload attempt. Output stored as JSONB.
    Never writes directly to Candidate profile - candidate must review and apply.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='parses')
    status = models.CharField(max_length=20, choices=ParseStatus.choices, default=ParseStatus.QUEUED)

    # Provenance - stored for re-runs and audit
    model_name = models.CharField(max_length=100, blank=True)  # e.g. 'gpt-4o'
    model_version = models.CharField(max_length=50, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)  # e.g. 'v2.1'

    # Results
    raw_text = models.TextField(blank=True)  # extracted text before LLM
    output = models.JSONField(null=True, blank=True)  # structured extraction
    field_confidence = models.JSONField(null=True, blank=True)  # {field: 0.0-1.0}

    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    # Applied
    applied_at = models.DateTimeField(null=True, blank=True)  # when candidate confirmed

    class Meta:
        db_table = 'resumes_parse'
        ordering = ['-created_at']

    def __str__(self):
        return f'Parse({self.document.original_filename}) - {self.status}'
