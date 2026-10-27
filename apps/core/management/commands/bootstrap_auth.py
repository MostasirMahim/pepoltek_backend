"""
apps/core/management/commands/bootstrap_auth.py

Bootstrap Script 1 of 4: Authentication, RBAC Role Groups, Choice Matrix, and Bounty Catalog.
Strict House Style Rule: Zero em dashes in all strings and output.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.accounts.models import User, UserRole, RoleChoice, UserStatus, RoleDefinition
from apps.accounts.permissions import ROLE_CAPABILITIES
from apps.config_center.models import ConfigVersion
from apps.config_center.default_taxonomies import DEFAULT_TAXONOMY_DATA
from apps.config_center.services import publish_config
from apps.referrals.models import BountyType


class Command(BaseCommand):
    help = "Bootstrap Auth: Superadmin user, system roles, permissions, choice matrix, and bounty types."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== [1/4] Bootstrapping Auth & Core Infrastructure ==="))

        # 1. Super Admin Account
        admin_email = "admin@pepoltek.com"
        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "full_name": "Executive Super Administrator",
                "status": UserStatus.ACTIVE,
                "is_staff": True,
                "is_superuser": True,
                "mfa_enabled": False,
            }
        )
        admin_user.set_password("Password123!")
        admin_user.status = UserStatus.ACTIVE
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        UserRole.objects.get_or_create(user=admin_user, role=RoleChoice.SUPER_ADMIN)
        UserRole.objects.get_or_create(user=admin_user, role=RoleChoice.ADMIN)
        self.stdout.write(self.style.SUCCESS(f"  [OK] Super Admin user verified: {admin_user.email} (Roles: SUPER_ADMIN, ADMIN)"))

        # 2. RBAC System Roles & Clearances
        roles_seeded = 0
        for code, info in ROLE_CAPABILITIES.items():
            role_def, r_created = RoleDefinition.objects.get_or_create(
                code=code,
                defaults={
                    "name": info["name"],
                    "category": info["category"],
                    "description": info.get("description", ""),
                    "scope": info.get("scope", ""),
                    "permissions": info.get("permissions", []),
                    "is_system_role": True,
                }
            )
            if not r_created:
                role_def.name = info["name"]
                role_def.category = info["category"]
                role_def.description = info.get("description", "")
                role_def.scope = info.get("scope", "")
                role_def.permissions = info.get("permissions", [])
                role_def.is_system_role = True
                role_def.save()
            roles_seeded += 1

        self.stdout.write(self.style.SUCCESS(f"  [OK] RBAC System Roles verified: {roles_seeded} roles seeded."))

        # 3. Choice Matrix / Taxonomy Configuration
        active_taxonomy = ConfigVersion.objects.filter(
            key=ConfigVersion.Key.SKILL_TAXONOMY,
            is_active=True
        ).first()

        if not active_taxonomy:
            active_taxonomy = publish_config(
                key=ConfigVersion.Key.SKILL_TAXONOMY,
                data=DEFAULT_TAXONOMY_DATA,
                author=admin_user,
                notes="Bootstrap seed of master candidate choice and taxonomy matrix",
            )
            self.stdout.write(self.style.SUCCESS(f"  [OK] Choice Matrix published as ConfigVersion {active_taxonomy.version}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"  [OK] Active Choice Matrix verified at ConfigVersion {active_taxonomy.version}."))

        # 4. Standard Referral Bounty Types Catalog
        bounties_data = [
            {
                "name": "Senior Cloud & Distributed Systems Specialist",
                "amount": Decimal("1500.00"),
                "validity_days": 90,
                "sort_order": 1,
                "description": "Enterprise bounty for verified senior cloud infrastructure and distributed systems specialists.",
            },
            {
                "name": "Critical Care ICU Registered Nurse (RN)",
                "amount": Decimal("2000.00"),
                "validity_days": 90,
                "sort_order": 2,
                "description": "Clinical placement bounty for board-certified ICU registered nurses with active licensure.",
            },
            {
                "name": "Standard Engineering Role Bounty",
                "amount": Decimal("1000.00"),
                "validity_days": 60,
                "sort_order": 3,
                "description": "Standard referral bonus for mid-level to senior full-stack and backend engineers.",
            },
            {
                "name": "Clinical Specialist & Allied Health Bounty",
                "amount": Decimal("1200.00"),
                "validity_days": 60,
                "sort_order": 4,
                "description": "Clinical referral bonus for specialized physical therapists, nurse practitioners, and allied health staff.",
            },
        ]

        bounties_count = 0
        for b in bounties_data:
            BountyType.objects.update_or_create(
                name=b["name"],
                defaults={
                    "amount": b["amount"],
                    "validity_days": b["validity_days"],
                    "description": b["description"],
                    "sort_order": b["sort_order"],
                    "is_active": True,
                }
            )
            bounties_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [OK] Referral Bounty Catalog: {bounties_count} standard bounty types verified."))
        self.stdout.write(self.style.SUCCESS("=== [1/4] Auth, RBAC, Choices & Bounties Completed Successfully ===\n"))
