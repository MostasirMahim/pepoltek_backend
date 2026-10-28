"""
apps/core/management/commands/bootstrap_users.py

Bootstrap Script 2 of 4: Staff accounts, validators, referrers, and validator profiles.
Strict House Style Rule: Zero em dashes in all strings and output.
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User, UserRole, RoleChoice, UserStatus
from apps.vetting.models import ValidatorProfile, ValidatorSector, ValidatorClearance
from apps.candidates.models import Candidate, SectorChoice, ExperienceLevel, WorkAuth, VettingStatus, ReadinessTier


class Command(BaseCommand):
    help = "Bootstrap Users: Seeds all staff accounts, validator profiles, and operational test personas."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== [2/5] Bootstrapping Staff Accounts & Operational Personas ==="))

        staff_specs = [
            {
                "email": "recruiter@pepoltek.com",
                "full_name": "Sarah Jenkins",
                "role": RoleChoice.RECRUITER,
                "is_staff": True,
                "validator": None,
            },
            {
                "email": "business_analyst@pepoltek.com",
                "full_name": "David Vance",
                "role": RoleChoice.BUSINESS_ANALYST,
                "is_staff": True,
                "validator": None,
            },
            {
                "email": "tech_validator@pepoltek.com",
                "full_name": "Dr. Marcus Vance",
                "role": RoleChoice.TECH_VALIDATOR,
                "is_staff": True,
                "validator": {
                    "sector": ValidatorSector.TECHNOLOGY,
                    "specialization": "Distributed Systems & Cloud Architecture",
                    "clearance": ValidatorClearance.LEVEL_2,
                    "max_reviews": 10,
                },
            },
            {
                "email": "credential_officer@pepoltek.com",
                "full_name": "Elena Rostova",
                "role": RoleChoice.CREDENTIAL_OFFICER,
                "is_staff": True,
                "validator": {
                    "sector": ValidatorSector.HEALTHCARE,
                    "specialization": "Clinical Licensure & Regulatory Compliance",
                    "clearance": ValidatorClearance.LEVEL_2,
                    "max_reviews": 15,
                },
            },
            {
                "email": "referrer@pepoltek.com",
                "full_name": "Alex Mercer",
                "role": RoleChoice.REFERRER,
                "is_staff": False,
                "validator": None,
            },
            {
                "email": "candidate@pepoltek.com",
                "full_name": "Test Candidate",
                "role": RoleChoice.CANDIDATE,
                "is_staff": False,
                "validator": None,
            },
        ]

        for spec in staff_specs:
            user, created = User.objects.get_or_create(
                email=spec["email"],
                defaults={
                    "full_name": spec["full_name"],
                    "status": UserStatus.ACTIVE,
                    "is_staff": spec["is_staff"],
                    "is_superuser": False,
                    "mfa_enabled": False,
                }
            )
            user.set_password("Password123!")
            user.full_name = spec["full_name"]
            user.status = UserStatus.ACTIVE
            user.is_staff = spec["is_staff"]
            user.save()

            UserRole.objects.get_or_create(user=user, role=spec["role"])

            # Provision Validator Profile if applicable
            if spec["validator"]:
                val_data = spec["validator"]
                ValidatorProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "sector": val_data["sector"],
                        "specialization": val_data["specialization"],
                        "clearance_level": val_data["clearance"],
                        "max_active_assignments": val_data["max_reviews"],
                        "is_active": True,
                    }
                )
                self.stdout.write(self.style.SUCCESS(f"  [OK] Staff: {user.email} ({spec['role']}) + ValidatorProfile ({val_data['sector']})"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] User: {user.email} ({spec['role']})"))

            # Ensure candidate profile exists if CANDIDATE role
            if spec["role"] == RoleChoice.CANDIDATE:
                cand, c_created = Candidate.objects.update_or_create(
                    user=user,
                    defaults={
                        "full_name": user.full_name,
                        "sector": SectorChoice.TECHNOLOGY,
                        "domain": "Full-Stack & Cloud",
                        "level": ExperienceLevel.SENIOR,
                        "desired_hourly_rate": "115",
                        "skills_cache": ["TypeScript", "Next.js", "React", "Python", "Cloud Architecture"],
                        "location": "San Francisco, United States",
                        "timezone": "PST / 4h Live Overlap",
                        "work_auth": WorkAuth.US_CITIZEN,
                        "engagement_prefs": ["c2c", "w2"],
                        "open_to_work": True,
                        "vetting_status": VettingStatus.VETTED,
                        "readiness_tier": ReadinessTier.READY,
                        "bio": "Senior Full-Stack Cloud Specialist with expertise in Next.js, React 19, and Python microservices.",
                    }
                )
                self.stdout.write(self.style.SUCCESS(f"  [OK] Linked Candidate Profile for {user.email}"))

        self.stdout.write(self.style.SUCCESS("=== [2/5] Staff Accounts & Operational Personas Completed Successfully ===\n"))
