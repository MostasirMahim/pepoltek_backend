"""
apps/core/management/commands/bootstrap_jobs.py

Bootstrap Script 3 of 4: Clients, Candidates, Requisitions, Assessment Templates, and Live Applications.
Strict House Style Rule: Zero em dashes in all strings and output.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User, UserRole, RoleChoice, UserStatus
from apps.ats.models import (
    Client,
    ClientContact,
    Requisition,
    RequisitionStatus,
    RequisitionVisibility,
    Application,
    ApplicationStage,
    ApplicationSource,
    ApplicationEvent,
)
from apps.candidates.models import Candidate, SectorChoice, ExperienceLevel, WorkAuth, VettingStatus, ReadinessTier
from apps.vetting.models import AssessmentTemplate, ApplicationVetting, Credential, CredentialStatus
from apps.matching.models import PitchAuthorization, PitchAuthorizationStatus
from apps.referrals.models import BountyType


class Command(BaseCommand):
    help = "Bootstrap Jobs: Seeds 2 clients, 2 candidates, 6 requisitions, assessment templates, and 2 connected applications."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== [3/5] Bootstrapping ATS Clients, Candidates, Jobs & Pipelines ==="))

        recruiter_user = User.objects.filter(email="recruiter@pepoltek.com").first() or User.objects.filter(is_staff=True).first()
        tech_val_user = User.objects.filter(email="tech_validator@pepoltek.com").first() or recruiter_user
        cred_off_user = User.objects.filter(email="credential_officer@pepoltek.com").first() or recruiter_user

        # --------------------------------------------------------------------
        # 1. Two Authentic Enterprise Clients
        # --------------------------------------------------------------------
        # Client 1: Technology
        client_tech, _ = Client.objects.update_or_create(
            name="Apex Cloud Systems",
            defaults={
                "sector": "technology",
                "website": "https://apexcloud.io",
                "delivery_channel": "email",
                "owner": recruiter_user,
                "terms": {"notes": "Enterprise multi-cloud financial infrastructure partner. Tier 1 compliance."},
            }
        )
        ClientContact.objects.update_or_create(
            client=client_tech,
            email="evelyn.vance@apexcloud.io",
            defaults={
                "full_name": "Evelyn Vance",
                "role_title": "Vice President of Infrastructure",
                "phone": "+1-415-555-0192",
                "is_primary": True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Client 1 (Tech): {client_tech.name} (Contact: Evelyn Vance)"))

        # Client 2: Healthcare
        client_health, _ = Client.objects.update_or_create(
            name="MedVanguard Health Network",
            defaults={
                "sector": "healthcare",
                "website": "https://medvanguard.org",
                "delivery_channel": "email",
                "owner": recruiter_user,
                "terms": {"notes": "Regional clinical hospital network operating 12 acute care facilities."},
            }
        )
        ClientContact.objects.update_or_create(
            client=client_health,
            email="a.finch@medvanguard.org",
            defaults={
                "full_name": "Dr. Alistair Finch",
                "role_title": "Chief Medical Officer & VP Operations",
                "phone": "+1-617-555-0321",
                "is_primary": True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Client 2 (Health): {client_health.name} (Contact: Dr. Alistair Finch)"))

        # --------------------------------------------------------------------
        # 2. Two Authentic Candidates (1 Tech, 1 Healthcare)
        # --------------------------------------------------------------------
        # Candidate 1: Technology
        cand1_user, _ = User.objects.get_or_create(
            email="sarah.connor@pepoltek.com",
            defaults={
                "full_name": "Sarah Connor",
                "status": UserStatus.ACTIVE,
                "is_staff": False,
            }
        )
        cand1_user.set_password("Password123!")
        cand1_user.save()
        UserRole.objects.get_or_create(user=cand1_user, role=RoleChoice.CANDIDATE)

        cand_tech, _ = Candidate.objects.update_or_create(
            user=cand1_user,
            defaults={
                "full_name": "Sarah Connor",
                "sector": SectorChoice.TECHNOLOGY,
                "domain": "Cloud Architecture",
                "level": ExperienceLevel.SENIOR,
                "desired_hourly_rate": "120",
                "skills_cache": ["AWS", "Kubernetes", "Terraform", "Go", "Docker", "PostgreSQL", "CI/CD"],
                "location": "New York, United States",
                "timezone": "EST / 4h Live Overlap",
                "work_auth": WorkAuth.US_CITIZEN,
                "engagement_prefs": ["c2c", "w2"],
                "open_to_work": True,
                "vetting_status": VettingStatus.VETTED,
                "readiness_tier": ReadinessTier.READY,
                "bio": "Senior Cloud Infrastructure Engineer with 8+ years experience scaling Kubernetes clusters and CI/CD pipelines.",
            }
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Candidate 1 (Tech): {cand_tech.full_name} ({cand1_user.email})"))

        # Candidate 2: Healthcare
        cand2_user, _ = User.objects.get_or_create(
            email="sarah.ahmed.rn@example.com",
            defaults={
                "full_name": "Sarah Ahmed, RN",
                "status": UserStatus.ACTIVE,
                "is_staff": False,
            }
        )
        cand2_user.set_password("Password123!")
        cand2_user.save()
        UserRole.objects.get_or_create(user=cand2_user, role=RoleChoice.CANDIDATE)

        cand_health, _ = Candidate.objects.update_or_create(
            user=cand2_user,
            defaults={
                "full_name": "Sarah Ahmed, RN",
                "sector": SectorChoice.HEALTHCARE,
                "domain": "Critical Care",
                "level": ExperienceLevel.LEAD,
                "desired_hourly_rate": "95",
                "skills_cache": ["Critical Care", "ICU Protocol", "BLS", "ACLS", "Patient Safety", "Clinical Charting"],
                "location": "Boston, United States",
                "timezone": "EST / Clinical Rotations",
                "work_auth": WorkAuth.US_CITIZEN,
                "engagement_prefs": ["w2", "direct_hire"],
                "open_to_work": True,
                "vetting_status": VettingStatus.VETTED,
                "readiness_tier": ReadinessTier.ELITE,
                "bio": "Lead Intensive Care Unit Registered Nurse with 10+ years acute triage and ventilator management experience.",
            }
        )

        # Ensure verified healthcare credential
        Credential.objects.update_or_create(
            candidate=cand_health,
            name="RN State Compact License",
            defaults={
                "kind": Credential.Kind.LICENSE,
                "license_number": "RN-MA-8849201",
                "jurisdiction": "Massachusetts / eNLC Multi-State",
                "status": CredentialStatus.VERIFIED,
                "verified_by": cred_off_user,
                "verified_at": timezone.now(),
                "verification_method": "Primary Source Registry Verification (NURSYS)",
            }
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Candidate 2 (Health): {cand_health.full_name} ({cand2_user.email}) + Verified RN License"))

        # --------------------------------------------------------------------
        # 3. Assessment Templates for Vetting Engine
        # --------------------------------------------------------------------
        tpl_tech, _ = AssessmentTemplate.objects.update_or_create(
            title="Distributed Systems & Cloud Architecture Review",
            defaults={
                "category": "cat-technical",
                "sector": "technology",
                "description": "Comprehensive review of cloud-native Kubernetes design, microservices partition tolerance, and infrastructure automation.",
                "instructions": "Review the reference enterprise deployment specification. Submit architecture recommendations and failure-mode analysis.",
                "total_marks": 100,
                "created_by": tech_val_user,
                "prerequisites": ["Kubernetes administration", "Microservices architecture", "Terraform IAC"],
                "allowed_validator_roles": ["TECH_VALIDATOR", "SUPER_ADMIN", "RECRUITER"],
                "marks_distribution": [
                    {"criterion": "Architecture Modularity & Scalability", "max_points": 30},
                    {"criterion": "Fault Tolerance & High Availability", "max_points": 30},
                    {"criterion": "Containerization & Kubernetes Manifests", "max_points": 20},
                    {"criterion": "Infrastructure as Code & CI/CD Delivery", "max_points": 20},
                ],
            }
        )

        tpl_health, _ = AssessmentTemplate.objects.update_or_create(
            title="Clinical Licensure & Critical Care Protocol Verification",
            defaults={
                "category": "cat-compliance",
                "sector": "healthcare",
                "description": "Evaluation of active state compact licensure, BLS/ACLS life support certifications, and ICU clinical triage benchmarks.",
                "instructions": "Verify candidate nursing registry verification records, ICU patient load history, and acute emergency interventions.",
                "total_marks": 100,
                "created_by": cred_off_user,
                "prerequisites": ["Active RN State Compact License", "Current BLS and ACLS Certifications"],
                "allowed_validator_roles": ["CREDENTIAL_OFFICER", "SUPER_ADMIN", "RECRUITER"],
                "marks_distribution": [
                    {"criterion": "State Nursing Board Licensure Verification", "max_points": 40},
                    {"criterion": "Life Support Certifications (BLS/ACLS)", "max_points": 30},
                    {"criterion": "ICU Acute Triage & Protocol Adherence", "max_points": 30},
                ],
            }
        )
        self.stdout.write(self.style.SUCCESS("  [OK] Assessment Templates: 2 production evaluation rubrics verified."))

        # --------------------------------------------------------------------
        # 4. Six Requisitions (3 Tech, 3 Healthcare)
        # --------------------------------------------------------------------
        bounty_tech = BountyType.objects.filter(name__icontains="Cloud").first() or BountyType.objects.first()
        bounty_health = BountyType.objects.filter(name__icontains="Nurse").first() or BountyType.objects.first()

        requisitions_data = [
            # Tech 1
            {
                "title": "Lead Cloud & DevOps Sprint Specialist",
                "client": client_tech,
                "sector": "technology",
                "level": "Senior",
                "engagement": "C2C Direct Sprint",
                "budget_min": 100,
                "budget_max": 130,
                "location": "100% Remote (US/Canada)",
                "timezone": "EST / CST Standup Overlap",
                "skills": ["AWS", "Kubernetes", "Terraform", "CI/CD", "Go"],
                "bounty_enabled": True,
                "bounty_type": bounty_tech,
                "description": "Enterprise cloud infrastructure squad requiring verified Kubernetes cluster orchestration, zero-downtime blue/green rollouts, and infrastructure as code automation.",
            },
            # Tech 2
            {
                "title": "Principal Distributed Systems Architect",
                "client": client_tech,
                "sector": "technology",
                "level": "Lead",
                "engagement": "C2C Direct Sprint",
                "budget_min": 130,
                "budget_max": 160,
                "location": "100% Remote",
                "timezone": "4h Live Standup Overlap",
                "skills": ["Go", "Rust", "Kafka", "Distributed Systems", "gRPC"],
                "bounty_enabled": True,
                "bounty_type": bounty_tech,
                "description": "High-throughput financial ledger processing squad building event-driven microservices with Raft consensus and sub-millisecond settlement times.",
            },
            # Tech 3
            {
                "title": "Senior Full-Stack TypeScript Engineer",
                "client": client_tech,
                "sector": "technology",
                "level": "Senior",
                "engagement": "W2 Contract",
                "budget_min": 95,
                "budget_max": 120,
                "location": "100% Remote (US)",
                "timezone": "EST Working Hours",
                "skills": ["TypeScript", "React", "Next.js", "Node.js", "PostgreSQL"],
                "bounty_enabled": False,
                "bounty_type": None,
                "description": "Client-facing enterprise web application engineering with React 19, Next.js Server Components, strict TypeScript types, and Tailwind styling.",
            },
            # Health 1
            {
                "title": "Intensive Care Unit (ICU) Registered Nurse",
                "client": client_health,
                "sector": "healthcare",
                "level": "Senior",
                "engagement": "Travel / 13-Week Sprint",
                "budget_min": 90,
                "budget_max": 115,
                "location": "Boston, MA (Onsite Acute Care)",
                "timezone": "Day & Night Shifts (3x12h)",
                "skills": ["Critical Care", "ICU Protocol", "BLS", "ACLS", "Patient Safety"],
                "bounty_enabled": True,
                "bounty_type": bounty_health,
                "description": "Acute ICU expansion unit staffing. Fast-track credentialing for state compact RNs with intensive care and ventilator management experience.",
            },
            # Health 2
            {
                "title": "Clinical Nurse Specialist & Compliance Auditor",
                "client": client_health,
                "sector": "healthcare",
                "level": "Lead",
                "engagement": "Direct Hire",
                "budget_min": 105,
                "budget_max": 135,
                "location": "Hybrid (Boston, MA)",
                "timezone": "Standard Clinical Hours",
                "skills": ["Clinical Compliance", "Nursing Audit", "Patient Safety", "HIPAA", "JCAHO"],
                "bounty_enabled": True,
                "bounty_type": bounty_health,
                "description": "Clinical quality leadership role overseeing nursing practice standards, documentation compliance, and hospital accreditation audits.",
            },
            # Health 3
            {
                "title": "Nurse Practitioner (Family & Emergency Care)",
                "client": client_health,
                "sector": "healthcare",
                "level": "Senior",
                "engagement": "W2 Contract",
                "budget_min": 115,
                "budget_max": 145,
                "location": "Cambridge, MA (Ambulatory Clinic)",
                "timezone": "Full Time Ambulatory Hours",
                "skills": ["Emergency Medicine", "Primary Care", "Diagnostic Assessment", "Prescriptive Authority"],
                "bounty_enabled": False,
                "bounty_type": None,
                "description": "Advanced practice registered nurse managing urgent care triage, diagnostic workups, and acute outpatient treatment protocols.",
            },
        ]

        created_reqs = []
        for rd in requisitions_data:
            existing = Requisition.objects.filter(title=rd["title"], client=rd["client"])
            if existing.count() > 1:
                req = existing.first()
                existing.exclude(id=req.id).delete()
            elif existing.exists():
                req = existing.first()
            else:
                req = Requisition(title=rd["title"], client=rd["client"])

            req.sector = rd["sector"]
            req.level = rd["level"]
            req.engagement = rd["engagement"]
            req.budget_min = rd["budget_min"]
            req.budget_max = rd["budget_max"]
            req.location = rd["location"]
            req.timezone = rd["timezone"]
            req.skills = rd["skills"]
            req.description = rd["description"]
            req.bounty_enabled = rd["bounty_enabled"]
            req.bounty_type = rd["bounty_type"]
            req.status = RequisitionStatus.OPEN
            req.visibility = RequisitionVisibility.PUBLISHED_JOB
            req.owner = recruiter_user
            req.headcount = 1
            req.save()
            created_reqs.append(req)

        self.stdout.write(self.style.SUCCESS(f"  [OK] Requisitions: {len(created_reqs)} published requisitions verified (3 Tech, 3 Healthcare)."))

        # --------------------------------------------------------------------
        # 5. Two Live Connected Applications (Connecting Candidate -> Job -> Recruiter)
        # --------------------------------------------------------------------
        # Application 1: Sarah Connor (Tech) -> Lead Cloud & DevOps Sprint Specialist
        req_tech_1 = created_reqs[0]
        app_1, a1_created = Application.objects.update_or_create(
            candidate=cand_tech,
            requisition=req_tech_1,
            defaults={
                "stage": ApplicationStage.TECHNICAL_VETTING,
                "sub_stage": "Assessment Dispatched",
                "source": ApplicationSource.REVERSE,
                "owner": recruiter_user,
            }
        )

        PitchAuthorization.objects.update_or_create(
            candidate=cand_tech,
            requisition=req_tech_1,
            defaults={
                "status": PitchAuthorizationStatus.AUTHORIZED,
                "decided_at": timezone.now(),
                "snapshot_hash": "sha256_verified_bootstrap_snapshot_tech_01",
            }
        )

        import datetime
        vetting_deadline = datetime.datetime(2026, 10, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)

        ApplicationVetting.objects.update_or_create(
            application=app_1,
            template=tpl_tech,
            defaults={
                "primary_validator": tech_val_user,
                "assigned_by": recruiter_user,
                "status": ApplicationVetting.Status.IN_PROGRESS,
                "deadline": vetting_deadline,
                "recruiter_notes": "Technical vetting assessment dispatched by recruiter. Target Due Date: 2026-10-31.",
                "pass_threshold": 70,
            }
        )

        if not ApplicationEvent.objects.filter(application=app_1, to_stage=ApplicationStage.TECHNICAL_VETTING).exists():
            ApplicationEvent.objects.create(
                application=app_1,
                from_stage=ApplicationStage.MARKET_MAPPING,
                to_stage=ApplicationStage.TECHNICAL_VETTING,
                sub_stage="Assessment Dispatched",
                actor=recruiter_user,
                note=f"Candidate advanced to Technical Vetting stage for {req_tech_1.title}. Assigned to Dr. Marcus Vance. Target Due Date: 2026-10-31.",
            )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Application 1: {cand_tech.full_name} -> {req_tech_1.title} (Stage: Technical Vetting, Assessment Dispatched)"))

        # Application 2: Sarah Ahmed (Healthcare) -> Intensive Care Unit (ICU) Registered Nurse
        req_health_1 = created_reqs[3]
        app_2, a2_created = Application.objects.update_or_create(
            candidate=cand_health,
            requisition=req_health_1,
            defaults={
                "stage": ApplicationStage.TECHNICAL_VETTING,
                "sub_stage": "Scorecard Evaluation",
                "source": ApplicationSource.SOURCED,
                "owner": recruiter_user,
            }
        )

        PitchAuthorization.objects.update_or_create(
            candidate=cand_health,
            requisition=req_health_1,
            defaults={
                "status": PitchAuthorizationStatus.AUTHORIZED,
                "decided_at": timezone.now(),
                "snapshot_hash": "sha256_verified_bootstrap_snapshot_health_02",
            }
        )

        ApplicationVetting.objects.update_or_create(
            application=app_2,
            template=tpl_health,
            defaults={
                "primary_validator": cred_off_user,
                "assigned_by": recruiter_user,
                "status": ApplicationVetting.Status.IN_PROGRESS,
            }
        )

        if not ApplicationEvent.objects.filter(application=app_2, to_stage=ApplicationStage.TECHNICAL_VETTING).exists():
            ApplicationEvent.objects.create(
                application=app_2,
                from_stage=ApplicationStage.MARKET_MAPPING,
                to_stage=ApplicationStage.TECHNICAL_VETTING,
                sub_stage="Scorecard Evaluation",
                actor=recruiter_user,
                note=f"Candidate advanced to Vetting stage for {req_health_1.title}. Assigned to Credential Officer.",
            )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Application 2: {cand_health.full_name} -> {req_health_1.title} (Stage: Technical Vetting, Scorecard In Progress)"))

        self.stdout.write(self.style.SUCCESS("=== [3/5] ATS Clients, Candidates, Jobs & Pipelines Completed Successfully ===\n"))
