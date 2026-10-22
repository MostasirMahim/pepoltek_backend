"""
cms/selectors.py
Read-only query functions for CMS content.
"""
from .models import SiteContent


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
