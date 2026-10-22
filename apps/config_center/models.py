"""
config_center/models.py
Versioned platform configuration - calculator rules, pricing tiers, matching weights,
bounty defaults, taxonomies. One append-only ConfigVersion per key.
Admin can publish a new version or rollback to any prior version.
"""
from django.db import models
from django.conf import settings


class ConfigVersion(models.Model):
    """
    Append-only config store. Never update rows - always insert a new version.
    The active version for a key is the one with is_active=True.
    """

    class Key(models.TextChoices):
        HIRING_CALCULATOR = 'hiring_calculator', 'Hiring Velocity Calculator'
        PRICING_TIERS = 'pricing_tiers', 'Pricing Tiers'
        BOUNTY_DEFAULTS = 'bounty_defaults', 'Bounty & Referral Defaults'
        MATCHING_WEIGHTS = 'matching_weights', 'Match Score Weights'
        TIMEZONE_MATRIX = 'timezone_matrix', 'Timezone Overlap Matrix'
        NAVIGATION = 'navigation', 'Site Navigation Menu'
        SKILL_TAXONOMY = 'skill_taxonomy', 'Skill & Specialty Taxonomy'
        EMAIL_TEMPLATES = 'email_templates', 'Email Template Config'

    key = models.CharField(max_length=50, choices=Key.choices, db_index=True)
    version = models.PositiveIntegerField()
    data = models.JSONField()
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'config_version'
        unique_together = [('key', 'version')]
        ordering = ['-version']
        indexes = [models.Index(fields=['key', 'is_active'])]

    def __str__(self):
        return f'{self.key} v{self.version} {"(active)" if self.is_active else ""}'
