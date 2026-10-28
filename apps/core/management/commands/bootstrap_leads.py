"""
apps/core/management/commands/bootstrap_leads.py

Bootstrap Script 4 of 5: Commercial employer leads, activity audit logs, and inbound inquiries.
Strict House Style Rule: Zero em dashes in all strings, documentation, and output.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import User
from apps.leads.models import (
    Lead,
    LeadActivityLog,
    ContactInquiry,
    LeadSource,
    LeadStatus,
    SectorChoice,
    EngagementModelChoice,
    TimelineChoice,
    ContactCategory,
    ContactStatus,
)


class Command(BaseCommand):
    help = "Bootstrap Leads: Seeds realistic commercial employer leads, audit logs, and contact inquiries."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== [4/5] Bootstrapping Employer Leads & Contact Inquiries ==="))

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
        recruiter_user = User.objects.filter(email__icontains="recruiter").first() or admin_user
        analyst_user = User.objects.filter(email__icontains="analyst").first() or admin_user
        validator_user = User.objects.filter(email__icontains="validator").first() or admin_user

        # -------------------------------------------------------------------------
        # 1. Commercial Employer Leads
        # -------------------------------------------------------------------------
        leads_data = [
            {
                "company": "Apex Financial Cloud Systems",
                "contact_name": "Evelyn Vance",
                "work_email": "evelyn.vance@apexfinancial.com",
                "phone": "+1-415-555-0192",
                "sector": SectorChoice.TECHNOLOGY,
                "source": LeadSource.HIRE_FORM,
                "status": LeadStatus.NEW,
                "roles_needed": "3x Senior Distributed Go and Rust Infrastructure Engineers with gRPC and Raft consensus experience.",
                "headcount": 3,
                "engagement_model": "dedicated_pod",
                "timeline": TimelineChoice.IMMEDIATE,
                "estimated_budget": "$130 to $160/hr",
                "notes": "Migrating legacy settlement infrastructure to a distributed event-driven mesh. Target deployment within 7 days.",
                "booking_data": {"selected_slot": "Tomorrow, 2:30 PM EST", "timezone": "EST (UTC-5)"},
                "owner": recruiter_user,
            },
            {
                "company": "St. Marys Regional Health Network",
                "contact_name": "Dr. Alistair Finch",
                "work_email": "a.finch@stmarys-health.org",
                "phone": "+1-617-555-0321",
                "sector": SectorChoice.HEALTHCARE,
                "source": LeadSource.CALCULATOR,
                "status": LeadStatus.DISCOVERY_BOOKED,
                "roles_needed": "4x Intensive Care Unit (ICU) Registered Nurses and 1x Certified Nurse Midwife (CNM) for hospital wing expansion.",
                "headcount": 5,
                "engagement_model": "staff_aug",
                "timeline": TimelineChoice.TWO_WEEKS,
                "estimated_budget": "$90 to $115/hr",
                "notes": "Clinical credentials and compact state licensure verification required prior to deployment.",
                "booking_data": {"selected_slot": "Thursday, 10:00 AM EST", "timezone": "EST (UTC-5)"},
                "owner": analyst_user,
            },
            {
                "company": "QuantumEdge Telemetry Labs",
                "contact_name": "Marcus Brody",
                "work_email": "m.brody@quantumedge.io",
                "phone": "+1-206-555-0784",
                "sector": SectorChoice.TECHNOLOGY,
                "source": LeadSource.HIRE_FORM,
                "status": LeadStatus.QUALIFIED,
                "roles_needed": "2x Staff Full Stack Architecture Specialists (React 19, TypeScript strict, Next.js App Router, Python FastAPI).",
                "headcount": 2,
                "engagement_model": "dedicated_pod",
                "timeline": TimelineChoice.IMMEDIATE,
                "estimated_budget": "$125 to $150/hr",
                "notes": "Discovery consultation completed. Client approved technical evaluation rubric. Pre-vetted shortlist builder scheduled.",
                "booking_data": {"selected_slot": "Completed Yesterday", "timezone": "PST (UTC-8)"},
                "owner": admin_user,
            },
            {
                "company": "Vanguard BioTech Genomics",
                "contact_name": "David K. Sterling",
                "work_email": "d.sterling@vanguard-biotech.com",
                "phone": "+1-617-555-0455",
                "sector": SectorChoice.BOTH,
                "source": LeadSource.CONTACT_FORM,
                "status": LeadStatus.DISCOVERY_RUNNING,
                "roles_needed": "2x Bioinformatics Cloud Engineers (AWS Genomics, Nextflow, Kubernetes) and 1x Healthcare Compliance Data Officer.",
                "headcount": 3,
                "engagement_model": "staff_aug",
                "timeline": TimelineChoice.ONE_MONTH,
                "estimated_budget": "$140 to $175/hr",
                "notes": "Discovery sprint in progress. Reviewing HIPAA data residency architecture and candidate clearance requirements.",
                "booking_data": {"selected_slot": "Today, 4:00 PM EST", "timezone": "EST (UTC-5)"},
                "owner": validator_user,
            },
            {
                "company": "Aura Health AI Diagnostics",
                "contact_name": "Samantha Reed",
                "work_email": "samantha.reed@aurahealth.ai",
                "phone": "+1-415-555-0633",
                "sector": SectorChoice.BOTH,
                "source": LeadSource.REFERRAL,
                "status": LeadStatus.CONTACTED,
                "roles_needed": "1x Lead Computer Vision and PyTorch ML Engineer for medical imaging segmentation.",
                "headcount": 1,
                "engagement_model": "direct_hire",
                "timeline": TimelineChoice.TWO_WEEKS,
                "estimated_budget": "$170,000 to $210,000 / yr",
                "notes": "Referred via executive partner. Initial recruiter screening call conducted. Candidate shortlist pending.",
                "booking_data": {"selected_slot": "Friday, 1:00 PM EST", "timezone": "EST (UTC-5)"},
                "owner": recruiter_user,
            },
            {
                "company": "FinTech Velocity Inc.",
                "contact_name": "Hiroshi Tanaka",
                "work_email": "h.tanaka@fintechvelocity.com",
                "phone": "+1-212-555-0811",
                "sector": SectorChoice.TECHNOLOGY,
                "source": LeadSource.CALCULATOR,
                "status": LeadStatus.CONVERTED,
                "roles_needed": "2x Senior DevOps Cloud Infrastructure Specialists (Terraform, AWS, SOC2 compliance).",
                "headcount": 2,
                "engagement_model": "staff_aug",
                "timeline": TimelineChoice.IMMEDIATE,
                "estimated_budget": "$110 to $135/hr",
                "notes": "Successfully converted to ATS Client entity. Active requisitions deployed in ATS workspace.",
                "booking_data": {"selected_slot": "Onboarded and Converted", "timezone": "EST (UTC-5)"},
                "owner": admin_user,
            },
        ]

        created_leads = 0
        for item in leads_data:
            lead, created = Lead.objects.update_or_create(
                company=item["company"],
                defaults=item
            )
            if created:
                created_leads += 1
                LeadActivityLog.objects.create(
                    lead=lead,
                    actor=admin_user,
                    action="lead_created",
                    to_status=lead.status,
                    note=f"Commercial inbound inquiry received for {lead.company}. Requirements: {lead.roles_needed[:120]}."
                )

        self.stdout.write(self.style.SUCCESS(f"  [OK] Commercial Leads: Seeded {len(leads_data)} records ({created_leads} created)"))

        # -------------------------------------------------------------------------
        # 2. Inbound Contact Inquiries
        # -------------------------------------------------------------------------
        contacts_data = [
            {
                "name": "Charlotte Dubois",
                "email": "c.dubois@globalequity.org",
                "phone": "+1-650-555-9281",
                "category": ContactCategory.PARTNERSHIP,
                "subject": "Strategic RPO Partnership Exploration with Global Healthcare Consortium",
                "message": "We are representing a consortium of private hospitals in North America and Western Europe looking to establish a standardized talent delivery partnership under Pepoltek 7-day deployment SLAs. Would appreciate connecting with your partnership directors.",
                "status": ContactStatus.IN_PROGRESS,
                "responder": admin_user,
                "response_notes": "Initial briefing deck sent. Scheduling formal enterprise partnership discussion.",
            },
            {
                "name": "Elena Rostova",
                "email": "elena.rostova@vanguardventures.com",
                "phone": "+1-415-555-0914",
                "category": ContactCategory.TALENT_SUPPORT,
                "subject": "Inquiry regarding dedicated Go and Rust engineering squads for portfolio companies",
                "message": "Our portfolio includes three fast-growing B2B infrastructure startups scaling their distributed systems engineering teams. We would like to understand your pricing and escrow terms for dedicated squads.",
                "status": ContactStatus.NEW,
                "responder": None,
                "response_notes": "",
            },
            {
                "name": "Nathaniel Cross",
                "email": "ncross@techreviewdaily.com",
                "phone": "+1-212-555-0199",
                "category": ContactCategory.PRESS_MEDIA,
                "subject": "Interview request on 7-Day Technical Vetting and Benchmark SLAs in 2026",
                "message": "We are publishing a feature on verified talent delivery models and RPO platforms. We would love to feature Pepoltek leadership regarding your 70-point benchmark threshold and escrow shortlist builder.",
                "status": ContactStatus.RESPONDED,
                "responder": admin_user,
                "response_notes": "Interview scheduled for next Tuesday with communications team.",
                "responded_at": timezone.now() - timedelta(days=1),
            },
            {
                "name": "Kavita Sharma",
                "email": "kavita.sharma@medtech-innovations.io",
                "phone": "+44-20-7946-0912",
                "category": ContactCategory.FEEDBACK,
                "subject": "Candidate credential upload and verification workflow feedback",
                "message": "The automated document parser accurately extracted all clinical board certifications and state license numbers without manual corrections. Excellent user experience on the intake wizard.",
                "status": ContactStatus.CLOSED,
                "responder": recruiter_user,
                "response_notes": "Acknowledged feedback and logged to UX enhancement register.",
                "responded_at": timezone.now() - timedelta(days=2),
            },
            {
                "name": "Dr. Henrik Lindqvist",
                "email": "henrik.lindqvist@nordichealthcare.se",
                "phone": "+46-8-555-0123",
                "category": ContactCategory.GENERAL,
                "subject": "General inquiry on EU and UK EOR compliance capabilities for clinical researchers",
                "message": "We are seeking guidance on cross-border healthcare researcher staffing and whether Pepoltek provides Employer of Record (EOR) indemnification for European cross-border projects.",
                "status": ContactStatus.NEW,
                "responder": None,
                "response_notes": "",
            },
        ]

        created_contacts = 0
        for c in contacts_data:
            contact, created = ContactInquiry.objects.update_or_create(
                email=c["email"],
                subject=c["subject"],
                defaults=c
            )
            if created:
                created_contacts += 1

        self.stdout.write(self.style.SUCCESS(f"  [OK] Contact Inquiries: Seeded {len(contacts_data)} records ({created_contacts} created)"))
        self.stdout.write(self.style.SUCCESS("All commercial employer leads and inbound contact inquiries seeded successfully.\n"))
