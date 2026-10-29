"""
cms/models.py
Wagtail headless CMS models for marketing pages, case studies, and insights.
Provides headless API endpoints consumed by Next.js frontend via ISR.

Also contains SiteContent: a lightweight, versioned JSON store for managing
all public website content blocks (hero, services, about, navigation, etc.)
from the admin panel without requiring a code deploy.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel
from wagtail.api import APIField
from wagtail.images.models import AbstractImage, AbstractRendition, Image


class CustomImage(AbstractImage):
    """Custom image model allowing alt-text and asset metadata."""
    alt_text = models.CharField(max_length=255, blank=True, default='')

    admin_form_fields = Image.admin_form_fields + (
        'alt_text',
    )

    class Meta:
        verbose_name = 'Image'
        verbose_name_plural = 'Images'


class CustomRendition(AbstractRendition):
    """Rendition model required for CustomImage."""
    image = models.ForeignKey(
        CustomImage,
        on_delete=models.CASCADE,
        related_name='renditions'
    )

    class Meta:
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class StandardPage(Page):
    """Standard generic content page for about, privacy policy, terms, etc."""
    intro = models.CharField(max_length=250, blank=True)
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('intro'),
        FieldPanel('body'),
    ]

    api_fields = [
        APIField('intro'),
        APIField('body'),
    ]


class InsightArticlePage(Page):
    """Insights / Blog article page for thought leadership and industry news."""
    published_date = models.DateField("Post date", auto_now_add=True)
    summary = models.TextField(blank=True)
    author_name = models.CharField(max_length=100, default='Pepoltek Team')
    body = RichTextField()
    hero_image = models.ForeignKey(
        'cms.CustomImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    content_panels = Page.content_panels + [
        FieldPanel('author_name'),
        FieldPanel('summary'),
        FieldPanel('hero_image'),
        FieldPanel('body'),
    ]

    api_fields = [
        APIField('published_date'),
        APIField('author_name'),
        APIField('summary'),
        APIField('hero_image'),
        APIField('body'),
    ]


# ---------------------------------------------------------------------------
# SiteContent: lightweight CMS for all public page content blocks
# ---------------------------------------------------------------------------

class SiteContent(models.Model):
    """
    Versioned content store for all public website sections.
    Each record represents one named content block (e.g. 'homepage_hero',
    'services_list', 'case_studies_list', 'about_page', 'site_navigation').

    Rules:
    - Append-only: never update rows directly, always create new version.
    - Only one row per (key, is_published=True) at any time.
    - Full revision history is preserved forever.
    """

    class Key(models.TextChoices):
        HOMEPAGE = 'homepage', 'Homepage Master Content'
        HOMEPAGE_HERO = 'homepage_hero', 'Homepage Hero Section'
        HOMEPAGE_STATS = 'homepage_stats', 'Homepage Stats & Metrics'
        HOMEPAGE_SECTIONS = 'homepage_sections', 'Homepage Section Blocks'
        SERVICES_LIST = 'services_list', 'Services Page Content'
        CASE_STUDIES = 'case_studies', 'Case Studies'
        ABOUT_PAGE = 'about_page', 'About Page Content'
        SITE_NAVIGATION = 'site_navigation', 'Site Navigation Links'
        CONTACT_INFO = 'contact_info', 'Contact Information'
        FOOTER_CONTENT = 'footer_content', 'Footer Content'
        CTA_BANNERS = 'cta_banners', 'CTA Banners'
        HEALTHCARE_PAGE = 'healthcare_page', 'Healthcare & Compliance Page'

    key = models.CharField(
        max_length=60,
        choices=Key.choices,
        db_index=True,
    )
    version = models.PositiveIntegerField()
    data = models.JSONField(
        help_text='Structured content for this block. Schema varies per key.'
    )
    notes = models.TextField(
        blank=True,
        help_text='Optional editor notes describing this change.'
    )
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Only one published version per key at a time.',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cms_site_content'
        unique_together = [('key', 'version')]
        ordering = ['key', '-version']
        indexes = [
            models.Index(fields=['key', 'is_published']),
        ]
        verbose_name = 'Site Content Block'
        verbose_name_plural = 'Site Content Blocks'

    def __str__(self):
        status = '(published)' if self.is_published else '(draft)'
        return f'{self.get_key_display()} v{self.version} {status}'


# ---------------------------------------------------------------------------
# CaseStudy: dedicated relational model for Technical Case Studies
# ---------------------------------------------------------------------------

class CaseStudy(BaseModel):
    """
    Dedicated database model for Technical Case Studies and Architecture Blueprints.
    Inherits UUIDv7 primary key, UTC timestamps, and soft deletion from BaseModel.
    """

    class Category(models.TextChoices):
        ENTERPRISE_WEB = 'Enterprise Web Apps', 'Enterprise Web Apps'
        HEALTHTECH_EMR = 'Health-Tech & EMR', 'Health-Tech & EMR'
        SAAS = 'SaaS', 'SaaS Platforms'
        CLOUD_INFRA = 'Cloud Infrastructure', 'Cloud Infrastructure'

    class Sector(models.TextChoices):
        TECH = 'tech', 'Technology & Cloud'
        HEALTHCARE = 'healthcare', 'Healthcare & Clinical'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    slug = models.SlugField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text='Unique URL slug for this technical case study.',
    )
    title = models.CharField(
        max_length=255,
        help_text='Primary case study headline.',
    )
    subtitle = models.CharField(
        max_length=350,
        blank=True,
        default='',
        help_text='Sub-headline or technical subtitle.',
    )
    category = models.CharField(
        max_length=80,
        choices=Category.choices,
        default=Category.ENTERPRISE_WEB,
        db_index=True,
    )
    sector = models.CharField(
        max_length=20,
        choices=Sector.choices,
        default=Sector.TECH,
        db_index=True,
    )
    sector_label = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Human-readable sector tag e.g. Technology & Cloud.',
    )
    client_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Client or enterprise partner name (e.g. Global NeoBank Enterprise).',
    )
    client_industry = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Industry vertical of the client.',
    )
    timeframe = models.CharField(
        max_length=120,
        blank=True,
        default='7-day deployment sprint',
        help_text='Sprint or deployment duration (e.g. 7-day deployment sprint, 3 Months).',
    )
    badge = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Optional highlight badge text (e.g. Enterprise HR-Tech).',
    )
    endpoint = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Technical endpoint or verification target (e.g. portal.pepoltek.ai / audit).',
    )
    project_type = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='System type (e.g. Enterprise SaaS & Internal Platform).',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether to feature this study on the homepage Systems Built section.',
    )
    order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text='Display ordering weight (lower numbers appear first).',
    )
    hero_image = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Hero or diagram preview image URL.',
    )

    # Narrative content
    summary = models.TextField(
        blank=True,
        default='',
        help_text='Executive summary of results and business outcome.',
    )
    challenge = models.TextField(
        blank=True,
        default='',
        help_text='Technical bottleneck or business challenge faced by client.',
    )
    solution = models.TextField(
        blank=True,
        default='',
        help_text='Architecture and staffing delivery strategy implemented.',
    )
    content = models.TextField(
        blank=True,
        default='',
        help_text='In-depth rich text HTML content created via the CMS rich text editor.',
    )
    business_impact = models.TextField(
        blank=True,
        default='',
        help_text='Measured business ROI and operational impact.',
    )

    # Structured technical blueprint specifications (JSON)
    requirements = models.JSONField(
        default=list,
        blank=True,
        help_text='List of key technical and compliance requirements.',
    )
    architecture = models.JSONField(
        default=dict,
        blank=True,
        help_text='Architecture schema dict: overview, diagramDescription, microservices, databaseSchema.',
    )
    tech_stack = models.JSONField(
        default=list,
        blank=True,
        help_text='List of tech stack badges (e.g. Python, Docker, Next.js).',
    )
    validation_logs = models.JSONField(
        default=list,
        blank=True,
        help_text='Audit and benchmark logs: list of { timestamp, module, status, detail }.',
    )
    metrics = models.JSONField(
        default=list,
        blank=True,
        help_text='Key outcome proof metrics: list of { label, value, improvement/baseline }.',
    )
    test_coverage = models.JSONField(
        default=dict,
        blank=True,
        help_text='Test coverage dict: { unit, integration, e2e }.',
    )
    quote = models.JSONField(
        default=dict,
        blank=True,
        help_text='Client or stakeholder quote: { text, author, title }.',
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='case_studies',
    )

    class Meta:
        db_table = 'cms_case_study'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['status', 'sector']),
            models.Index(fields=['status', 'category']),
            models.Index(fields=['is_featured', 'status']),
        ]
        verbose_name = 'Case Study'
        verbose_name_plural = 'Case Studies'

    def __str__(self):
        return f'{self.title} ({self.get_category_display()}) [{self.status}]'
