"""
apps/cms/management/commands/seed_case_studies.py

Management command to seed production-grade Technical Case Studies.
Runs seed_case_studies() from .seed_files.seed_case_studies.

Usage:
  python manage.py seed_case_studies

Strict House Style Rule: Zero em dashes in all strings and output.
"""
import sys
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Seeds authentic production Technical Case Studies into the database."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding Technical Case Studies ==="))
        seed_dir = str(settings.BASE_DIR / ".seed_files")
        if seed_dir not in sys.path:
            sys.path.insert(0, seed_dir)

        from seed_case_studies import seed_case_studies
        seed_case_studies()
        self.stdout.write(self.style.SUCCESS("=== Technical Case Studies Seed Completed Successfully ==="))
