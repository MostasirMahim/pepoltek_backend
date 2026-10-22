"""
config_center/management/commands/seed_taxonomy_matrix.py
Seeds the baseline candidate choice and taxonomy matrix as ConfigVersion 1.
Strict House Style Rule: Zero em dashes or en dashes throughout.
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.config_center.models import ConfigVersion
from apps.config_center.default_taxonomies import DEFAULT_TAXONOMY_DATA
from apps.config_center.services import publish_config


class Command(BaseCommand):
    help = "Seed baseline candidate choice and taxonomy matrix into ConfigVersion"

    def handle(self, *args, **options):
        existing = ConfigVersion.objects.filter(
            key=ConfigVersion.Key.SKILL_TAXONOMY,
            is_active=True
        ).first()

        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f"Active taxonomy matrix already exists (version {existing.version}). Skipping seed."
                )
            )
            return

        admin = User.objects.filter(is_staff=True).first()
        version = publish_config(
            key=ConfigVersion.Key.SKILL_TAXONOMY,
            data=DEFAULT_TAXONOMY_DATA,
            author=admin,
            notes="Initial seed of candidate taxonomy matrix from platform specifications",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded baseline taxonomy matrix as version {version.version}."
            )
        )
