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
