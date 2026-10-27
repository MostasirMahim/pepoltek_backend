"""
apps/core/management/commands/bootstrap_all.py

Master Runner: Executes all 4 bootstrap commands in exact sequential order:
1. bootstrap_auth (SuperAdmin, Roles, Permissions, Choice Matrix, Bounties)
2. bootstrap_users (Staff, Validators, Referrers, Validator Profiles)
3. bootstrap_jobs (Clients, Candidates, Requisitions, Assessment Templates, Connected Applications)
4. bootstrap_cms (Site Navigation, Homepage 9 Sections, Collections)

Strict House Style Rule: Zero em dashes in all strings and output.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Master Bootstrap: Sequentially runs bootstrap_auth, bootstrap_users, bootstrap_jobs, and bootstrap_cms."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("================================================================="))
        self.stdout.write(self.style.MIGRATE_HEADING("   PEPOLTEK PLATFORM MASTER PRODUCTION BOOTSTRAP INITIALIZER     "))
        self.stdout.write(self.style.MIGRATE_HEADING("=================================================================\n"))

        # Step 1
        call_command("bootstrap_auth")

        # Step 2
        call_command("bootstrap_users")

        # Step 3
        call_command("bootstrap_jobs")

        # Step 4
        call_command("bootstrap_cms")

        self.stdout.write(self.style.SUCCESS("================================================================="))
        self.stdout.write(self.style.SUCCESS("   ALL 4 BOOTSTRAP SCRIPTS COMPLETED SUCCESSFULLY!              "))
        self.stdout.write(self.style.SUCCESS("================================================================="))
        self.stdout.write("All platform models, roles, staff accounts, jobs, and CMS content are ready.\n")
