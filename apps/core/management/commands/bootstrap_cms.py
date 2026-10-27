"""
apps/core/management/commands/bootstrap_cms.py

Bootstrap Script 4 of 4: Seeds master dynamic site navigation, full homepage, and CMS collections.
Strict House Style Rule: Zero em dashes in all strings and output.
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.cms.models import SiteContent
from apps.cms.services import publish_content
from apps.cms.management.commands.seed_cms_content import HOMEPAGE_DATA, OTHER_SEEDS


MASTER_NAVIGATION_DATA = {
    "sections": [
        {
            "id": "services-solutions",
            "label": "Services & Solutions",
            "href": "/services",
            "eyebrow": "01 · Regulated Delivery Models",
            "layout": "dual",
            "serial": 1,
            "items": [
                {
                    "id": "staff-aug",
                    "title": "IT Staff Augmentation",
                    "desc": "W2 & C2C senior engineering bandwidth with 2-week risk-free trial.",
                    "href": "/services",
                    "badge": "Elastic",
                    "icon": "Code",
                    "serial": 1,
                },
                {
                    "id": "engineering-teams",
                    "title": "Multi-Seat Engineering Teams",
                    "desc": "Autonomous cross-functional delivery teams managed by in-house leads.",
                    "href": "/services",
                    "badge": "Turnkey",
                    "icon": "Users",
                    "serial": 2,
                },
                {
                    "id": "eor-services",
                    "title": "Employer of Record (EOR)",
                    "desc": "Global compliant payroll, taxation, and labor governance across 15+ countries.",
                    "href": "/services",
                    "badge": "15+ Countries",
                    "icon": "Globe",
                    "serial": 3,
                },
                {
                    "id": "direct-hire",
                    "title": "Direct Hire & Search",
                    "desc": "Contingent and retained executive recruitment with a 90-day replacement guarantee.",
                    "href": "/services",
                    "badge": "Permanent",
                    "icon": "Briefcase",
                    "serial": 4,
                },
                {
                    "id": "academy-readiness",
                    "title": "Training & Academy Readiness",
                    "desc": "Pre-deployment skill bootcamps, architectural vetting, and compliance readiness.",
                    "href": "/ecosystem/academy",
                    "badge": "Academy",
                    "icon": "Sparkles",
                    "serial": 5,
                },
                {
                    "id": "case-studies-item",
                    "title": "Technical Case Studies",
                    "desc": "Inspect microservices blueprints, data schemas, and hard-coded audit benchmarks.",
                    "href": "/case-studies",
                    "badge": "Proof",
                    "icon": "ShieldCheck",
                    "serial": 6,
                },
            ],
            "spotlight": {
                "headline": "7-Day Sprint Deployment",
                "sub": "From technical brief to fully productive specialist in 7 days flat.",
                "cta": "Explore Solutions",
                "href": "/services",
            },
        },
        {
            "id": "healthcare-compliance",
            "label": "Healthcare & Compliance",
            "href": "/healthcare",
            "eyebrow": "02 · Regulated Clinical & Med-Tech",
            "layout": "dual",
            "serial": 2,
            "items": [
                {
                    "id": "clinical-staffing",
                    "title": "Clinical Medical Staffing",
                    "desc": "Licensed physicians, registered nurses for emergency, outpatient, and ICU.",
                    "href": "/healthcare",
                    "badge": "Clinical",
                    "icon": "Activity",
                    "serial": 1,
                },
                {
                    "id": "non-clinical-staffing",
                    "title": "Non-Clinical Healthcare Staffing",
                    "desc": "Healthcare administrators, EMR and EHR directors, medical billing and coding.",
                    "href": "/healthcare",
                    "badge": "Operations",
                    "icon": "Building2",
                    "serial": 2,
                },
                {
                    "id": "healthtech-engineering",
                    "title": "Health-Tech Engineering",
                    "desc": "Interoperability engineers specializing in Epic, Cerner, FHIR, and HL7 protocols.",
                    "href": "/case-studies",
                    "badge": "Integration",
                    "icon": "Zap",
                    "serial": 3,
                },
                {
                    "id": "hipaa-governance",
                    "title": "HIPAA & PCI DSS Frameworks",
                    "desc": "Institutional data handling, encrypted remote setups, and signed BAA agreements.",
                    "href": "/healthcare",
                    "badge": "Audited",
                    "icon": "ShieldCheck",
                    "serial": 4,
                },
            ],
            "spotlight": {
                "headline": "100% HIPAA-Compliant Delivery",
                "sub": "Pre-vetted clinical personnel and health-tech squads ready for hospital networks.",
                "cta": "Explore Healthcare Practice",
                "href": "/healthcare",
            },
        },
        {
            "id": "talent-careers",
            "label": "Careers & Talent",
            "href": "/career",
            "eyebrow": "03 · Global Talent Ecosystem",
            "layout": "single",
            "serial": 3,
            "items": [
                {
                    "id": "public-jobs",
                    "title": "Active Jobs & Sprints",
                    "desc": "Explore verified client requisitions, remote gigs, and bounties.",
                    "href": "/jobs",
                    "badge": "Live",
                    "icon": "Briefcase",
                    "serial": 1,
                },
                {
                    "id": "upload-cv",
                    "title": "Join Talent Network (Upload CV)",
                    "desc": "Fast-track candidate intake with AI CV parsing and skill benchmarking.",
                    "href": "/career/upload_cv",
                    "badge": "Intake",
                    "icon": "UploadCloud",
                    "serial": 2,
                },
                {
                    "id": "reverse-search",
                    "title": "AI Reverse Job Search",
                    "desc": "Candidate-controlled matching with anonymized dossiers and 1-Click Pitch.",
                    "href": "/candidate/reverse-search",
                    "badge": "Escrow",
                    "icon": "Compass",
                    "serial": 3,
                },
                {
                    "id": "refer-earn",
                    "title": "Refer & Earn Network",
                    "desc": "Earn up to $2,000 per verified candidate placement via double-entry escrow.",
                    "href": "/referrals",
                    "badge": "Bounties",
                    "icon": "DollarSign",
                    "serial": 4,
                },
            ],
        },
    ],
    "quickLinks": [
        {"label": "Hiring Calculator", "href": "/#calculator-section"},
        {"label": "Case Studies", "href": "/case-studies"},
        {"label": "About Pepoltek", "href": "/about"},
        {"label": "Contact & Consultation", "href": "/contact"},
    ],
    "footerLinks": [
        {"label": "Terms of Service", "href": "/terms"},
        {"label": "Privacy Policy", "href": "/privacy"},
        {"label": "Escrow Guarantees", "href": "/compliance"},
        {"label": "Security Standards", "href": "/security"},
    ],
}


class Command(BaseCommand):
    help = "Bootstrap CMS: Seeds master site navigation, 9-section homepage, and all public content collections."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== [4/4] Bootstrapping Headless CMS & Public Content ==="))

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR("  [FAIL] No admin user found. Run bootstrap_auth first."))
            return

        # 1. Master Site Navigation
        nav_block = publish_content(
            key="site_navigation",
            data=MASTER_NAVIGATION_DATA,
            author=admin_user,
            notes="Bootstrap seed of master site navigation tree",
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Site Navigation: Published as version {nav_block.version}."))

        # 2. Master Homepage (All 9 Visual Sections)
        home_block = publish_content(
            key=SiteContent.Key.HOMEPAGE,
            data=HOMEPAGE_DATA,
            author=admin_user,
            notes="Bootstrap seed of 9-section high-fidelity homepage structure",
        )
        # Backward-compat hero block
        publish_content(
            key=SiteContent.Key.HOMEPAGE_HERO,
            data=HOMEPAGE_DATA["hero"],
            author=admin_user,
            notes="Bootstrap seed of homepage hero block",
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Master Homepage: Published 9-section layout as version {home_block.version}."))

        # 3. Services Collection (Dual publish for services_list and services routes)
        services_data = OTHER_SEEDS[SiteContent.Key.SERVICES_LIST]
        s_block = publish_content(
            key=SiteContent.Key.SERVICES_LIST,
            data=services_data,
            author=admin_user,
            notes="Bootstrap seed of services and delivery models collection",
        )
        publish_content(
            key="services",
            data=services_data,
            author=admin_user,
            notes="Bootstrap alias for /services API",
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Services Collection: Published as version {s_block.version}."))

        # 4. Case Studies Collection
        case_data = OTHER_SEEDS[SiteContent.Key.CASE_STUDIES]
        c_block = publish_content(
            key=SiteContent.Key.CASE_STUDIES,
            data=case_data,
            author=admin_user,
            notes="Bootstrap seed of technical case studies collection",
        )
        publish_content(
            key="case-studies",
            data=case_data,
            author=admin_user,
            notes="Bootstrap alias for /case-studies API",
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Case Studies Collection: Published as version {c_block.version}."))

        # 5. Healthcare Collection
        health_data = OTHER_SEEDS[SiteContent.Key.HEALTHCARE_PAGE]
        h_block = publish_content(
            key=SiteContent.Key.HEALTHCARE_PAGE,
            data=health_data,
            author=admin_user,
            notes="Bootstrap seed of healthcare and clinical staffing collection",
        )
        publish_content(
            key="healthcare",
            data=health_data,
            author=admin_user,
            notes="Bootstrap alias for /healthcare API",
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] Healthcare Collection: Published as version {h_block.version}."))

        # 6. About, Contact, Footer, and CTA Banners
        for extra_key, label in [
            (SiteContent.Key.ABOUT_PAGE, "About Page"),
            (SiteContent.Key.CONTACT_INFO, "Contact Information"),
            (SiteContent.Key.FOOTER_CONTENT, "Footer Content"),
            (SiteContent.Key.CTA_BANNERS, "CTA Banners"),
        ]:
            if extra_key in OTHER_SEEDS:
                b = publish_content(
                    key=extra_key,
                    data=OTHER_SEEDS[extra_key],
                    author=admin_user,
                    notes=f"Bootstrap seed of {label}",
                )
                self.stdout.write(self.style.SUCCESS(f"  [OK] {label}: Published as version {b.version}."))

        self.stdout.write(self.style.SUCCESS("=== [4/4] Headless CMS & Public Content Completed Successfully ===\n"))
