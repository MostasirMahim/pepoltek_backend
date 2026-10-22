"""
core/models.py
Abstract base model shared by every domain entity.
All domain models inherit BaseModel. Never instantiate directly.
"""
import uuid
from django.db import models
from django.utils import timezone


def generate_uuid7():
    """UUID v7 - timestamp-ordered, good for DB primary keys."""
    try:
        import uuid6
        return uuid6.uuid7()
    except ImportError:
        # Fallback to uuid4 if uuid6 not installed
        return uuid.uuid4()


class ActiveManager(models.Manager):
    """Default manager - excludes soft-deleted records."""
    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Unfiltered manager including archived records. Use explicitly."""
    pass


class BaseModel(models.Model):
    """
    Abstract base for all domain models.
    - UUIDv7 primary key (time-ordered, index-friendly)
    - UTC timestamps
    - Soft deletion via archived_at (default manager hides archived rows)
    """
    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Default manager hides archived rows
    objects = ActiveManager()
    # Use BaseModel.all_objects.filter(...) to include archived
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def archive(self):
        """Soft-delete this record. Cascades must be handled in services."""
        self.archived_at = timezone.now()
        self.save(update_fields=['archived_at', 'updated_at'])

    def restore(self):
        """Undo soft-delete."""
        self.archived_at = None
        self.save(update_fields=['archived_at', 'updated_at'])

    @property
    def is_archived(self):
        return self.archived_at is not None
