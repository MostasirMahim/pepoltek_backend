"""
cms/selectors.py
Read-only query functions for CMS content and Case Studies.
"""
from django.db.models import Q, Count
from .models import SiteContent, CaseStudy


def get_published_block(key: str):
    """Return the currently published SiteContent for a key, or None."""
    return SiteContent.objects.filter(key=key, is_published=True).first()


def list_all_published() -> list:
    """Return one record per key: the current published version."""
    published = SiteContent.objects.filter(is_published=True).select_related('author')
    return list(published)


def list_versions_for_key(key: str, limit: int = 20):
    """Return all versions for a key, newest first."""
    return (
        SiteContent.objects
        .filter(key=key)
        .select_related('author')
        .order_by('-version')[:limit]
    )


def get_content_keys() -> list:
    """Return all available SiteContent keys with their display labels."""
    return [
        {'key': k, 'label': v}
        for k, v in SiteContent.Key.choices
    ]


# ---------------------------------------------------------------------------
# Case Study Selectors
# ---------------------------------------------------------------------------

def get_case_study_by_id(case_study_id):
    """Return a single CaseStudy by UUID primary key or None."""
    try:
        return CaseStudy.objects.select_related('author').get(id=case_study_id)
    except CaseStudy.DoesNotExist:
        return None


def get_case_study_by_slug(slug: str, published_only: bool = True):
    """Return a single CaseStudy by unique slug or None."""
    qs = CaseStudy.objects.select_related('author')
    if published_only:
        qs = qs.filter(status=CaseStudy.Status.PUBLISHED)
    return qs.filter(slug=slug).first()


def list_case_studies(
    sector: str | None = None,
    category: str | None = None,
    status: str | None = None,
    is_featured: bool | None = None,
    search: str | None = None,
    limit: int | None = None,
):
    """
    List case studies with optional filtering by sector, category, status,
    featured flag, and search query.
    """
    qs = CaseStudy.objects.select_related('author').order_by('order', '-created_at')

    if sector and sector != 'all':
        qs = qs.filter(sector=sector)

    if category and category != 'all':
        qs = qs.filter(category=category)

    if status and status != 'all':
        qs = qs.filter(status=status)

    if is_featured is not None:
        qs = qs.filter(is_featured=is_featured)

    if search:
        search_terms = search.strip()
        qs = qs.filter(
            Q(title__icontains=search_terms) |
            Q(slug__icontains=search_terms) |
            Q(client_name__icontains=search_terms) |
            Q(summary__icontains=search_terms) |
            Q(badge__icontains=search_terms)
        )

    if limit:
        qs = qs[:limit]

    return qs


def get_case_studies_kpis() -> dict:
    """Return telemetry KPI summary across all case studies."""
    total = CaseStudy.objects.count()
    published = CaseStudy.objects.filter(status=CaseStudy.Status.PUBLISHED).count()
    drafts = CaseStudy.objects.filter(status=CaseStudy.Status.DRAFT).count()
    tech = CaseStudy.objects.filter(sector=CaseStudy.Sector.TECH).count()
    healthcare = CaseStudy.objects.filter(sector=CaseStudy.Sector.HEALTHCARE).count()
    featured = CaseStudy.objects.filter(is_featured=True).count()

    return {
        'total': total,
        'published': published,
        'drafts': drafts,
        'tech': tech,
        'healthcare': healthcare,
        'featured': featured,
    }

