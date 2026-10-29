"""
candidates/models.py
Candidate profile, skills, documents, and credential placeholders.
Candidate is 1:1 with User. Created at end of intake flow.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from encrypted_model_fields.fields import EncryptedCharField


class SectorChoice(models.TextChoices):
    TECHNOLOGY = 'technology', 'Technology'
    HEALTHCARE = 'healthcare', 'Healthcare'


class ExperienceLevel(models.TextChoices):
    JUNIOR = 'junior', 'Junior'
    MID = 'mid', 'Mid-Level'
    SENIOR = 'senior', 'Senior'
    LEAD = 'lead', 'Lead / Architect'
    DIRECTOR = 'director', 'Director / Head'
    C_LEVEL = 'c_level', 'C-Level / Executive'


class WorkAuth(models.TextChoices):
    OPT = 'opt', 'OPT / STEM OPT'
    H1B = 'h1b', 'H-1B'
    GREEN_CARD = 'green_card', 'Green Card'
    US_CITIZEN = 'us_citizen', 'US Citizen'
    INTERNATIONAL_REMOTE = 'international_remote', 'International Remote Specialist'


class EngagementType(models.TextChoices):
    W2 = 'w2', 'W2 Employee'
    C2C = 'c2c', 'Corp-to-Corp (C2C)'
    INDIE_1099 = '1099', '1099 Independent Contractor'
    DIRECT_HIRE = 'direct_hire', 'Direct Hire / Full-Time'


class VettingStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    IN_PROGRESS = 'in_progress', 'In Progress'
    VETTED = 'vetted', 'Vetted'
    NOT_SUITABLE = 'not_suitable', 'Not Suitable'


class ReadinessTier(models.TextChoices):
    UNRATED = 'unrated', 'Unrated'
    EMERGING = 'emerging', 'Emerging'
    READY = 'ready', 'Ready'
    ELITE = 'elite', 'Elite'


class Candidate(BaseModel):
    """
    Core candidate profile. Extended by CandidateSkill and Credential.
    PII encrypted at rest. embedding used by matching engine (pgvector).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidate'
    )

    # Encrypted PII
    full_name = EncryptedCharField(max_length=255)
    phone = EncryptedCharField(max_length=30, blank=True)

    # Profile picture stored in S3 private bucket (optional)
    profile_picture = models.CharField(max_length=500, blank=True, null=True)  # S3 object key

    sector = models.CharField(max_length=20, choices=SectorChoice.choices)
    domain = models.CharField(max_length=100, blank=True)  # e.g. Backend, Nursing
    level = models.CharField(max_length=20, choices=ExperienceLevel.choices)

    location = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    work_auth = models.CharField(max_length=30, choices=WorkAuth.choices, blank=True)
    engagement_prefs = models.JSONField(default=list)  # list of EngagementType values

    expected_comp_min = models.PositiveIntegerField(null=True, blank=True)  # annual USD
    expected_comp_max = models.PositiveIntegerField(null=True, blank=True)
    availability_date = models.DateField(null=True, blank=True)
    open_to_work = models.BooleanField(default=True)

    # Tech-specific & Bio
    portfolio_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    desired_hourly_rate = models.CharField(max_length=50, blank=True)
    skills_cache = models.JSONField(default=list, blank=True)

    # Data rights & account deletion requests
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)

    # Computed scores (updated by workers)
    profile_strength = models.PositiveSmallIntegerField(default=0)  # 0-100
    cv_score = models.PositiveSmallIntegerField(default=0)         # 0-100
    vetting_status = models.CharField(
        max_length=20, choices=VettingStatus.choices, default=VettingStatus.NOT_STARTED
    )
    readiness_tier = models.CharField(
        max_length=20, choices=ReadinessTier.choices, default=ReadinessTier.UNRATED
    )

    # pgvector embedding vector (float array generated via apps.ai_service.services.generate_candidate_embedding)
    embedding = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'candidates_candidate'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sector', 'level']),
            models.Index(fields=['vetting_status']),
            models.Index(fields=['open_to_work']),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.sector} / {self.level})'

    def generate_embedding_vector(self) -> list[float]:
        try:
            from apps.ai_service.services import generate_candidate_embedding
            # Strips protected attributes (age, gender, nationality, religion) per Technical SRS 9.2
            skills_list = self.skills_cache if isinstance(self.skills_cache, list) else []
            text_parts = [
                f"Domain: {self.domain}",
                f"Sector: {self.sector}",
                f"Level: {self.level}",
                f"Skills: {', '.join(skills_list)}",
                f"Bio: {self.bio[:600]}",
                f"Location: {self.location}",
                f"WorkAuth: {self.work_auth}",
                f"Engagement: {', '.join(self.engagement_prefs) if isinstance(self.engagement_prefs, list) else str(self.engagement_prefs)}",
            ]
            full_text = " ".join(text_parts)
            return generate_candidate_embedding(full_text)
        except Exception:
            return [0.0] * 1536

    def save(self, *args, **kwargs):
        if not self.embedding:
            try:
                self.embedding = self.generate_embedding_vector()
            except Exception:
                pass
        super().save(*args, **kwargs)



class SkillTaxonomy(BaseModel):
    """
    Admin-editable skill and specialty taxonomy.
    Tech skills and healthcare specialties share this table, distinguished by type.
    """

    class SkillType(models.TextChoices):
        TECH = 'tech', 'Technology'
        CLINICAL = 'clinical', 'Clinical / Healthcare'

    name = models.CharField(max_length=100, unique=True)
    skill_type = models.CharField(max_length=10, choices=SkillType.choices)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    aliases = models.JSONField(default=list)  # for fuzzy matching
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'candidates_skill_taxonomy'
        ordering = ['name']

    def __str__(self):
        return self.name


class CandidateSkill(BaseModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(SkillTaxonomy, on_delete=models.PROTECT, related_name='+')
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    proficiency = models.CharField(
        max_length=20,
        choices=[('basic', 'Basic'), ('proficient', 'Proficient'), ('expert', 'Expert')],
        default='proficient',
    )
    source = models.CharField(
        max_length=20,
        choices=[('parsed', 'Parsed from CV'), ('manual', 'Self-Reported'), ('assessed', 'Assessed')],
        default='parsed',
    )

    class Meta:
        db_table = 'candidates_candidate_skill'
        unique_together = [('candidate', 'skill')]

    def __str__(self):
        return f'{self.candidate.full_name} - {self.skill.name}'


class DocumentType(models.TextChoices):
    RESUME = 'resume', 'CV / Resume'
    COVER_LETTER = 'cover_letter', 'Cover / Motivation Letter'
    LICENSE = 'license', 'Professional License'
    CERTIFICATION = 'certification', 'Certification'
    OTHER = 'other', 'Other'


class ScanStatus(models.TextChoices):
    PENDING = 'pending', 'Pending Scan'
    CLEAN = 'clean', 'Clean'
    INFECTED = 'infected', 'Infected / Quarantined'
    ERROR = 'error', 'Scan Error'


class Document(BaseModel):
    """
    Candidate-uploaded file. Stored in private S3 bucket.
    Magic-byte validation and ClamAV scan before any processing.
    """
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DocumentType.choices)
    storage_key = models.CharField(max_length=500)  # S3 object key
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    version = models.PositiveSmallIntegerField(default=1)
    scan_status = models.CharField(
        max_length=20, choices=ScanStatus.choices, default=ScanStatus.PENDING
    )
    scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'candidates_document'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['candidate', 'doc_type'])]

    def __str__(self):
        return f'{self.original_filename} ({self.doc_type})'
