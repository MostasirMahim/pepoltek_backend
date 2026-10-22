"""
apps/cms/management/commands/seed_cms_content.py
Seeds full live content blocks for all SiteContent keys including the complete
homepage master structure with all 9 visual sections mapped directly from the frontend.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.cms.models import SiteContent
from apps.cms.services import publish_content

User = get_user_model()

# ============================================================================
# Complete High-Fidelity Homepage Data (All 9 Sections)
# ============================================================================
HOMEPAGE_DATA = {
    "hero": {
        "eyebrow": "Enterprise RPO & Strategic HR Solutions",
        "typedHeadline": "Hire Faster",
        "headlineSuffix": "than your competition",
        "description": "Pepoltek is an enterprise Recruitment Process Outsourcing (RPO) and strategic HR partner. We combine AI-driven candidate screening, automated technical assessments, and dedicated HR operations teams to deliver pre-vetted IT and compliance-ready healthcare talent within 2 to 7 days.",
        "descriptionMobile": "Enterprise RPO deploying pre-screened IT engineers and compliance-ready healthcare specialists in 2 to 7 days with guaranteed global timezone overlap.",
        "pills": [
            "Enterprise RPO",
            "AI-Powered HRMS",
            "Healthcare Compliance",
            "Tech & SDLC Staffing",
        ],
        "primaryCta": {
            "label": "Explore RPO Solutions",
            "href": "#specialist-tracks",
        },
        "secondaryCta": {
            "label": "View Pre-Screened Talent",
            "href": "#calculator-section",
        },
        "cards": [
            {
                "id": "tech-sdlc",
                "title": "Tech & SDLC Teams",
                "subtitle": "Full-Stack Dev",
            },
            {
                "id": "healthcare-it",
                "title": "Healthcare IT",
                "subtitle": "EMR & HIPAA",
            },
            {
                "id": "ai-hrms",
                "title": "AI HRMS Portal",
                "subtitle": "Global Workforce",
            },
        ],
    },
    "specialist_tracks": {
        "eyebrow": "Specialist-Led RPO & AI-Driven Talent Acquisition",
        "title": "Enterprise RPO Powered by AI Interviewing and Domain Specialists",
        "subtitle": "Move beyond generalist recruiters. Pepoltek pairs AI-driven video interviewing and automated skill evaluation with dedicated teams of software engineers, medical specialists, and HR strategists to hand-vet every candidate.",
        "stats": [
            {
                "label": "Specialists Deployed",
                "value": "500+",
                "description": "High-impact placements across IT and clinical domains",
            },
            {
                "label": "First-Year Retention",
                "value": "92%",
                "description": "Consistently exceeds the staffing industry benchmark",
            },
            {
                "label": "Shortlist SLA",
                "value": "72h",
                "description": "First calibrated candidate presentation delivered fast",
            },
        ],
        "regions": [
            {"id": "usa", "country": "USA", "label": "N. America", "tz": "EST (UTC-5)"},
            {"id": "eu", "country": "Europe", "label": "Europe", "tz": "CET (UTC+1)"},
            {"id": "gcc", "country": "GCC", "label": "GCC", "tz": "GST (UTC+4)"},
            {"id": "apac", "country": "APAC", "label": "APAC", "tz": "JST (UTC+9)"},
        ],
    },
    "sprint_matrix": {
        "eyebrow": "5-Stage Agile Sourcing Protocol",
        "title": "Sprint Execution Matrix: Precision Hiring from Day 1 to Day 7",
        "subtitle": "Deterministic hiring milestones designed to de-risk technical and clinical hiring through verified checkpoints.",
        "steps": [
            {
                "num": "01",
                "days": "Day 1",
                "title": "Discovery & Alignment",
                "sub": "Technical stack mapping and role scoping",
                "sla": "< 12h Turnaround",
                "deliverables": ["Role Taxonomy Spec", "Search Strategy", "Profile Matrix"],
            },
            {
                "num": "02",
                "days": "Day 2",
                "title": "Talent Mapping & Sourcing",
                "sub": "AI sourcing across 500k+ global talent pool",
                "sla": "24h Sourcing Sprint",
                "deliverables": ["Calibrated Longlist", "Semantic Relevance Scoring", "Timezone Matching"],
            },
            {
                "num": "03",
                "days": "Day 3",
                "title": "Deep Technical & Clinical Vetting",
                "sub": "Senior architect coding reviews and primary license audits",
                "sla": "48h Assessment SLA",
                "deliverables": ["Code Architecture Evaluation", "Primary Source Verification", "Behavioral Calibration"],
            },
            {
                "num": "04",
                "days": "Day 4-5",
                "title": "Synchronous Client Panels",
                "sub": "Pre-briefed candidates in structured interview loops",
                "sla": "Zero-Latency Scheduling",
                "deliverables": ["Interview Scorecards", "Candidate Dossiers", "Compensation Pre-alignment"],
            },
            {
                "num": "05",
                "days": "Day 6-7",
                "title": "Offer, Clearance & Onboarding",
                "sub": "Contract execution, background checks, and Day-1 readiness",
                "sla": "Guaranteed Day-1 Start",
                "deliverables": ["Compliant W2/C2C Contracts", "Hardware & Access Provisioning", "90-Day Retention Guarantee"],
            },
        ],
    },
    "hiring_velocity": {
        "eyebrow": "Flexible Global RPO & Staffing Calculator",
        "title": "Deploy Locally, Source Globally: 24/7 Timezone Coverage & RPO Cost Engine",
        "subtitle": "Guaranteed daily operational overlap across global hubs. Configure your custom squad across stacks, seniority tiers, and regions to compare real-time savings against traditional recruiting agencies.",
        "defaultSquadSize": 5,
        "defaultLocation": "nearshore",
        "disclaimer": "Calculated estimates reflect median market compensation, benefits, compliance overhead, and Pepoltek guaranteed performance margins.",
    },
    "commercial_terms": {
        "eyebrow": "Commercial Engagement Terms",
        "title": "Flexible Commercial Models & Risk-Free Guarantees",
        "subtitle": "Terms engineered to de-risk every hire. Three transparent engagement models with backed replacement and trial guarantees.",
        "models": [
            {
                "tag": "01",
                "name": "Direct Hire Placement",
                "category": "Executive & Specialist",
                "desc": "Contingency & retained hiring for senior engineering, product, and clinical leaders.",
                "metric": "12%",
                "metricLabel": "Entry Rate",
                "rateTerms": "Standard 15% to 20% first-year compensation",
                "guarantee": "90-Day Candidate Replacement Guarantee",
                "bullets": [
                    "Rigorous technical code audits and credentialing",
                    "Executive panel interview orchestration",
                    "Offer negotiation and compensation benchmarking",
                ],
            },
            {
                "tag": "02",
                "name": "Staff Augmentation",
                "category": "Turnkey Dedicated Squads",
                "desc": "Dedicated engineering and healthcare teams embedded in your sprint workflow.",
                "metric": "2 wk",
                "metricLabel": "Trial Period",
                "rateTerms": "Transparent monthly or hourly sprint billing",
                "guarantee": "2-Week Risk-Free Trial ($0 if benchmarks fail)",
                "featured": True,
                "bullets": [
                    "Pre-vetted engineering and clinical specialists",
                    "Guaranteed 4 to 6 hour daily operational overlap",
                    "Immediate sprint deployment in 2 to 7 days",
                ],
            },
            {
                "tag": "03",
                "name": "Employer of Record (EOR)",
                "category": "Global Payroll & Compliance",
                "desc": "Hire across 15+ countries with complete payroll, tax, and labor compliance.",
                "metric": "15+",
                "metricLabel": "Countries",
                "rateTerms": "Localized payroll, benefits, and tax withholding",
                "guarantee": "100% Statutory Compliance Ownership",
                "bullets": [
                    "Localized employment contracts and IP protection",
                    "Automated multi-currency salary disbursement",
                    "Statutory health, pension, and local benefits",
                ],
            },
        ],
    },
    "ai_hrms_portal": {
        "eyebrow": "Proprietary HR Technology",
        "title": "Ask for the shortlist in plain language.",
        "subtitle": "Our AI-HRMS portal translates natural language queries into instant, verified talent pipelines with match score, work authorization, timezone overlap, and hard-coded engineering audits.",
        "features": [
            {
                "id": 0,
                "title": "Natural Language Query",
                "body": "Query in plain English to get ranked matches with match score, work authorization, timezone overlap, and engagement model.",
            },
            {
                "id": 1,
                "title": "System Design Audit Logs",
                "body": "Every ranking ships with code quality, test coverage, and Redis and Kafka memory safety validation you can inspect.",
            },
            {
                "id": 2,
                "title": "Video Scorecards",
                "body": "HEXACO, OCEAN, and BEI signals paired with a 90 second technical explainer clip for every finalist.",
            },
        ],
    },
    "product_solutions": {
        "eyebrow": "Verified Technical Footprint · Pepoltek Limited",
        "title": "Systems Built, Deployed & Scaled",
        "subtitle": "We do not just recruit talent; our in-house engineering team designs, builds, and maintains enterprise-grade platforms. This deep technical foundation guarantees authentic vetting for your open roles.",
        "featuredBadge": "In-House Engineering Excellence",
    },
    "talent_ecosystem": {
        "eyebrow": "The Global Talent Ecosystem",
        "title": "The Global Talent Ecosystem",
        "subtitle": "Upload your resume, leverage AI to build an ATS-ready profile, and let enterprise opportunities find you.",
        "stages": [
            {
                "n": "01",
                "badge": "RESUME INTAKE",
                "rightBadge": "✦ INSTANT",
                "title": "Smart Resume Intake",
                "description": "Upload your resume and let our AI parser extract skills, experience, and certifications into a standardized ATS profile.",
                "route": "/careers/upload-cv",
            },
            {
                "n": "02",
                "badge": "REVERSE SEARCH",
                "rightBadge": "✦ MATCH",
                "title": "AI-Powered Reverse Search",
                "description": "Get discovered by verified enterprise employers seeking your exact tech stack and clinical domain expertise.",
                "route": "/careers/reverse-search",
            },
            {
                "n": "03",
                "badge": "TALENT ACADEMY",
                "rightBadge": "✦ CERTIFY",
                "title": "Pepoltek Talent Academy",
                "description": "Build your skills with expert-led learning paths and get vetted through real-world assessments to earn enterprise-ready credentials.",
                "route": "/talent/academy",
            },
            {
                "n": "04",
                "badge": "REFERRAL BOUNTY",
                "rightBadge": "✦ EARN",
                "title": "Referral Bounty Network",
                "description": "Refer top talent and get rewarded. Track your referrals, confirm payouts, and grow your earnings with our transparent bounty system.",
                "route": "/talent/bounty",
            },
        ],
    },
    "cta_banner": {
        "badge": "Zero Risk Hiring",
        "title": "Submit your requisition. We deploy a verified shortlist in 48 hours.",
        "description": "Enterprise delivery teams and pre-screened specialists ready for immediate integration. Backed by guaranteed daily timezone overlap and zero billing until trial benchmarks pass.",
        "pills": [
            "14-day risk-free trial on staff augmentation",
            "90-day placement replacement guarantee",
            "Zero generalist recruiters",
        ],
        "primaryCta": {
            "label": "Start 14-Day Risk-Free Trial",
            "href": "/contact",
        },
        "secondaryCta": {
            "label": "Schedule RPO Consultation",
            "href": "/contact",
        },
    },
}

# Standalone blocks for other pages
OTHER_SEEDS = {
    SiteContent.Key.SERVICES_LIST: {
        "header": {
            "eyebrow": "Commercial Solutions Suite",
            "title": "Workforce Solutions Tailored",
            "highlightedText": "for Speed and Precision",
            "description": "From flexible contractor bandwidth to fully autonomous engineering squads and clinical rotas, Pepoltek provides transparent commercial models backed by performance guarantees.",
            "stats": [
                {"value": "2 to 7 Days", "label": "Sprint Shortlist Velocity"},
                {"value": "2 Weeks", "label": "Risk-Free Trial Period"},
                {"value": "15+ Countries", "label": "Global EOR & Payroll Hubs"},
            ],
            "specs": [
                "W2 & C2C Compliant",
                "4 to 8 Hrs Live Overlap",
                "90-Day Placement Guarantee",
                "HIPAA Title II Certified",
            ],
            "primaryCta": {"label": "Request Workforce Quote", "href": "/contact"},
            "secondaryCta": {"label": "Launch Velocity Calculator", "href": "#calculator-section"},
        },
        "services": [
            {
                "id": "staff-augmentation",
                "title": "IT Staff Augmentation",
                "badge": "Elastic Bandwidth",
                "iconName": "Zap",
                "desc": "Seamlessly embed senior software engineers into your sprint cycles. Billed hourly or monthly with complete flexibility.",
                "guarantee": "2-week risk-free trial + 10% rate discount on 6-month squad commitments.",
                "features": [
                    "W2 Contract and Corp-to-Corp (C2C) compliant structures",
                    "Overlapping workdays (4 to 8 hours live synchronous collaboration)",
                    "Senior developers across Frontend, Backend, Cloud, and AI",
                    "Immediate deployment in 2 to 7 business days",
                ],
            },
            {
                "id": "offshore-teams",
                "title": "Dedicated Engineering Teams",
                "badge": "Turnkey Squads",
                "iconName": "Cpu",
                "desc": "Autonomous, cross-functional software teams managed by in-house architects and agile project managers.",
                "guarantee": "SLA-governed sprint velocity and weekly delivery burn-down charts.",
                "features": [
                    "Tripartite team composition (Lead Architect, Engineers, QA & DevOps)",
                    "Daily live standup attendance and synchronized sprint cadence",
                    "Hard-coded repository reviews and microservices architecture",
                    "Zero management overhead for enterprise clients",
                ],
            },
            {
                "id": "eor-services",
                "title": "Employer of Record (EOR)",
                "badge": "Global Compliance",
                "iconName": "Globe",
                "desc": "Hire international talent anywhere without incorporating local entities. We handle global payroll, taxes, and legal labor laws.",
                "guarantee": "Compliant payroll distribution across 15+ countries.",
                "features": [
                    "Local labor law compliance and employment contracts",
                    "Statutory benefits administration and IP protection clauses",
                    "Single consolidated monthly invoicing in USD, GBP, or EUR",
                    "Zero risk of contractor misclassification",
                ],
            },
            {
                "id": "direct-hire",
                "title": "Direct Hire & Executive Search",
                "badge": "Permanent Placement",
                "iconName": "Users",
                "desc": "Contingent and retained search for full-time staff, specialized engineering leads, and C-level technology executives.",
                "guarantee": "90-day replacement guarantee + competitive market-entry rates.",
                "features": [
                    "Transparent fee structure (15% to 20% first-year compensation)",
                    "Introductory 12% placement rate on initial three hires",
                    "Rigorous behavioral vetting (HEXACO and BEI scorecards)",
                    "Full background checks and credential verification",
                ],
            },
            {
                "id": "healthcare-staffing",
                "title": "Healthcare & Clinical Staffing",
                "badge": "HIPAA Compliant",
                "iconName": "Stethoscope",
                "desc": "Vetted healthcare professionals and health-tech engineers ready for hospital rotas, clinics, and digital health platforms.",
                "guarantee": "Clinical credentialing audits with continuous license verification.",
                "features": [
                    "Physicians and Registered Nurses (ICU, Emergency, Outpatient)",
                    "EMR / EHR implementation specialists (Epic, Cerner, FHIR)",
                    "HIPAA-aware remote hiring and compliance frameworks",
                    "DBS, GMC, and state medical board credentialing checks",
                ],
            },
            {
                "id": "workforce-readiness",
                "title": "Workforce Readiness & Academy",
                "badge": "Talent Upskilling",
                "iconName": "Award",
                "desc": "Targeted pre-deployment training for candidates to eliminate skill gaps and ensure instant productivity on day one.",
                "guarantee": "Verified competency badges and enterprise communication alignment.",
                "features": [
                    "US Enterprise Readiness and daily standup etiquette",
                    "HIPAA and PCI DSS data security bootcamps",
                    "Distributed Systems and modern RAG AI architectures",
                    "Tailored client onboarding modules available on request",
                ],
            },
        ],
    },
    SiteContent.Key.CASE_STUDIES: {
        "header": {
            "eyebrow": "Verified Production Deployments",
            "title": "Technical Case Studies &",
            "highlightedText": "Architecture Blueprints",
            "description": "Inspect microservices blueprints, data schemas, and hard-coded audit benchmarks across enterprise FinTech, Health-Tech, and BioTech deployments.",
            "stats": [
                {"value": "100%", "label": "Code Audit Transparency"},
                {"value": "< 45ms", "label": "Vector Matching SLA"},
                {"value": "92%", "label": "First-Year Retention Rate"},
            ],
            "specs": [
                "Zero Fluff Architecture",
                "Live Telemetry Validation",
                "Multi-Tenant Microservices",
                "HIPAA & PCI-DSS Verified",
            ],
            "primaryCta": {"label": "Schedule Technical Briefing", "href": "/contact"},
            "secondaryCta": {"label": "Explore Services", "href": "/services"},
        },
        "studies": [
            {
                "slug": "fintech-cloud-platform-acceleration",
                "title": "Scaling Cloud Platform Engineering for Tier-1 FinTech",
                "category": "Enterprise Web Apps",
                "sector": "tech",
                "sectorLabel": "Technology and Cloud",
                "client": "Global NeoBank Enterprise",
                "timeline": "3 Months",
                "summary": "Reduced time-to-hire from 48 days to 11 days while placing 14 high-throughput Python and Kubernetes engineers with zero post-onboarding attrition.",
                "challenge": "The client faced severe sprint bottlenecks launching cross-border payment rails due to a shortage of vetted distributed systems engineers with PCI-DSS compliance backgrounds.",
                "solution": "Pepoltek deployed our AI semantic matching pipeline combined with peer-level architectural vetting to shortlist candidates within 72 hours, orchestrating synchronous technical panel assessments.",
                "techStack": ["Next.js", "Python / Django", "PostgreSQL", "Redis", "Docker", "Kubernetes"],
                "metrics": [
                    {"label": "Time to Hire", "value": "11 Days"},
                    {"label": "Engineers Placed", "value": "14 Senior Devs"},
                    {"label": "Retention Rate", "value": "100% Zero Churn"},
                ],
            },
            {
                "slug": "regional-health-system-icu-nursing",
                "title": "Emergency Staffing and Primary Credentialing for Acute Care Network",
                "category": "Health-Tech & EMR",
                "sector": "healthcare",
                "sectorLabel": "Healthcare and Clinical",
                "client": "Multi-State Regional Hospital Network",
                "timeline": "6 Weeks",
                "summary": "Mobilized 28 ICU and telemetry travel nurses with 100% credential compliance pass rate on day 1, averting unit closures across 3 regional facilities.",
                "challenge": "Seasonal patient surges and unexpected nursing vacancies left 4 acute care facilities dangerously below required staff-to-patient ratios, threatening patient safety.",
                "solution": "Pepoltek healthcare credentialing team executed automated primary source license verifications, immunization reviews, and drug screening within a 5-day cycle.",
                "techStack": ["Epic Systems", "Cerner EMR", "FHIR API", "HIPAA Vault"],
                "metrics": [
                    {"label": "Clinical Staff Deployed", "value": "28 Nurses"},
                    {"label": "Turnaround Time", "value": "5 Days"},
                    {"label": "Compliance Rate", "value": "100% Audited"},
                ],
            },
            {
                "slug": "ai-biotech-nlp-data-pipeline",
                "title": "BioTech Genomic NLP Model Training Pipeline Staffing",
                "category": "SaaS",
                "sector": "tech",
                "sectorLabel": "Technology and Cloud",
                "client": "Next-Gen Oncology BioTech",
                "timeline": "2 Months",
                "summary": "Supplied 6 specialized PyTorch and Bioinformatics machine learning researchers to accelerate oncology publication timelines by 4 months.",
                "challenge": "Candidate pool for researchers possessing both deep biomedical context and advanced transformer model training capabilities was virtually non-existent through standard job boards.",
                "solution": "Pepoltek leveraged our reverse search algorithms and academic talent networks to engage passive PhD-level research engineers.",
                "techStack": ["PyTorch", "Hugging Face", "CUDA", "AWS SageMaker", "Python"],
                "metrics": [
                    {"label": "PhD Researchers Placed", "value": "6 Specialists"},
                    {"label": "Timeline Accelerated", "value": "4 Months"},
                    {"label": "Pipeline Throughput", "value": "10x Data Velocity"},
                ],
            },
        ],
    },
    SiteContent.Key.HEALTHCARE_PAGE: {
        "header": {
            "eyebrow": "Regulated Clinical & Med-Tech Practice",
            "title": "Healthcare Workforce &",
            "highlightedText": "Compliance Ready",
            "description": "Pre-vetted clinical medical staffing, non-clinical healthcare administration, and health-tech interoperability engineering governed by 100% HIPAA compliance frameworks.",
            "stats": [
                {"value": "100%", "label": "HIPAA & BAA Compliance"},
                {"value": "48h", "label": "Clinical Credential SLA"},
                {"value": "10k+", "label": "Verified Specialists"},
            ],
            "specs": [
                "GMC & State Board Verified",
                "DBS Enhanced Cleared",
                "FHIR & HL7 Interoperability",
                "Epic & Cerner Specialists",
            ],
            "primaryCta": {"label": "Deploy Clinical Talent", "href": "/contact"},
            "secondaryCta": {"label": "Inspect Compliance Vault", "href": "/case-studies"},
        },
        "services": [
            {
                "id": "clinical-staffing",
                "title": "Clinical Medical Staffing",
                "badge": "Clinical Practice",
                "iconName": "Stethoscope",
                "desc": "Licensed physicians, registered nurses, and specialist clinicians for emergency, outpatient, and ICU wards.",
                "guarantee": "100% primary source license verification prior to start date.",
                "features": [
                    "Physicians (Attending, Hospitalists, Emergency Medicine)",
                    "Registered Nurses (ICU, Telemetry, ER, Travel Nursing)",
                    "Allied Health Professionals (Radiology, Lab Techs, Physical Therapy)",
                    "Continuous automated primary source license monitoring",
                ],
            },
            {
                "id": "non-clinical-operations",
                "title": "Non-Clinical Healthcare Operations",
                "badge": "Healthcare Ops",
                "iconName": "Users",
                "desc": "Healthcare administrators, EMR directors, and medical coding professionals optimizing revenue cycles.",
                "guarantee": "HIPAA Title II trained and compliance certified staff.",
                "features": [
                    "Medical billing, coding, and denial management specialists",
                    "Health system administrators and practice managers",
                    "Patient intake and telehealth customer experience teams",
                    "Compliance and credentialing audit coordinators",
                ],
            },
            {
                "id": "health-tech-engineering",
                "title": "Health-Tech & EMR Engineering",
                "badge": "Health IT",
                "iconName": "Cpu",
                "desc": "Specialized software engineers and systems architects building, migrating, and maintaining clinical data pipelines.",
                "guarantee": "FHIR and HL7 interoperability standards guaranteed.",
                "features": [
                    "Certified Epic and Cerner interface integration engineers",
                    "FHIR / HL7 v2/v3 data pipelines and telemetry gateways",
                    "Cloud HIPAA-compliant data lakes on AWS HealthLake and GCP",
                    "Medical device and IoT telemetry integration specialists",
                ],
            },
            {
                "id": "hipaa-governance",
                "title": "HIPAA & PCI DSS Governance Vault",
                "badge": "Audited Security",
                "iconName": "ShieldCheck",
                "desc": "Institutional security frameworks, Business Associate Agreements (BAAs), and end-to-end encrypted remote setups.",
                "guarantee": "Zero compliance breach guarantee backed by contractual indemnification.",
                "features": [
                    "Signed Business Associate Agreements (BAAs) on all engagements",
                    "Zero-trust hardware provisioning and mobile device management",
                    "SOC 2 Type II and HIPAA Title II verified audit trails",
                    "Real-time session logging and data loss prevention (DLP)",
                ],
            },
        ],
    },
    SiteContent.Key.ABOUT_PAGE: {
        "mission": "Empowering enterprise technology and healthcare leaders with precision talent deployment, backed by algorithmic matching, human peer vetting, and institutional compliance standards.",
        "pillars": [
            {
                "role": "Algorithmic Precision Sourcing",
                "focus": "Semantic Matching and Multi-Factor Ranking",
                "desc": "Proprietary embeddings compare technical taxonomy, team dynamics, and past project scale to find candidate fit beyond standard keyword filters.",
                "badge": "AI Engine",
            },
            {
                "role": "Rigorous Peer-Led Vetting",
                "focus": "System Design and Live Coding Diagnostics",
                "desc": "Candidates are vetted by staff architects and clinicians who actively work in their respective domains, ensuring zero resume inflation.",
                "badge": "Top 3% Standard",
            },
            {
                "role": "Institutional Compliance",
                "focus": "W2, C2C, and Healthcare Credential Verification",
                "desc": "Automated license verification, drug screening, background checks, and payroll management with complete audit tracking.",
                "badge": "Audit-Ready",
            },
            {
                "role": "Rapid Sprint Deployment",
                "focus": "72-Hour Calibrated Shortlists",
                "desc": "Pre-vetted talent specialists ready to onboard immediately without the standard 60-day agency delays.",
                "badge": "Velocity SLA",
            },
        ],
    },
    SiteContent.Key.SITE_NAVIGATION: {
        "links": [
            {"label": "Services", "href": "/services"},
            {"label": "Case Studies", "href": "/case-studies"},
            {"label": "Career", "href": "/career"},
            {"label": "Velocity Calculator", "href": "/calculator"},
            {"label": "Hire Talent", "href": "/hire"},
            {"label": "About", "href": "/about"},
        ],
    },
    SiteContent.Key.CONTACT_INFO: {
        "email": "contact@pepoltek.com",
        "phone": "+1 (800) 555-0199",
        "address": "Pepoltek Global Headquarters, 100 Innovation Way, Suite 400, New York, NY 10001",
        "hours": "Monday to Friday: 8:00 AM to 7:00 PM EST",
    },
    SiteContent.Key.FOOTER_CONTENT: {
        "copyright": "2026 Pepoltek Inc. All rights reserved. Precision Workforce Solutions.",
        "columns": [
            {"heading": "Solutions"},
            {"heading": "Candidates"},
            {"heading": "Company"},
            {"heading": "Legal and Compliance"},
        ],
    },
    SiteContent.Key.CTA_BANNERS: {
        "banners": [
            {
                "id": "homepage-bottom",
                "heading": "Ready to Accelerate Your Hiring Velocity?",
                "body": "Speak directly with our technical staffing directors and receive a calibrated shortlist of vetted specialists within 72 hours.",
                "primaryLabel": "Schedule Discovery Call",
                "primaryHref": "/hire",
            },
            {
                "id": "career-cta",
                "heading": "Join the Pepoltek Elite Talent Network",
                "body": "Get matched with high-impact engineering squads, clinical units, and enterprise contracts with transparent rates.",
                "primaryLabel": "Submit Your Resume",
                "primaryHref": "/careers/upload-cv",
            },
        ],
    },
}


class Command(BaseCommand):
    help = "Seeds initial live content blocks for all SiteContent keys including the full Homepage master."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing published blocks with defaults.",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)
        author = User.objects.filter(is_superuser=True).first() or User.objects.first()

        created_count = 0
        skipped_count = 0

        # 1. Seed HOMEPAGE master data
        homepage_existing = SiteContent.objects.filter(key=SiteContent.Key.HOMEPAGE, is_published=True).first()
        if homepage_existing and not force:
            self.stdout.write(f"  [SKIP] {SiteContent.Key.HOMEPAGE} already has published v{homepage_existing.version}")
            skipped_count += 1
        else:
            block = publish_content(
                key=SiteContent.Key.HOMEPAGE,
                data=HOMEPAGE_DATA,
                author=author,
                notes="Initial homepage master seed with all 9 visual sections mapped",
            )
            self.stdout.write(self.style.SUCCESS(f"  [LIVE] {SiteContent.Key.HOMEPAGE} published as v{block.version}"))
            created_count += 1

        # 2. Seed Hero & Stats backwards compatibility
        hero_existing = SiteContent.objects.filter(key=SiteContent.Key.HOMEPAGE_HERO, is_published=True).first()
        if not hero_existing or force:
            publish_content(
                key=SiteContent.Key.HOMEPAGE_HERO,
                data=HOMEPAGE_DATA["hero"],
                author=author,
                notes="Seed homepage_hero from master",
            )
            created_count += 1

        # 3. Seed other site content
        for key, data in OTHER_SEEDS.items():
            existing = SiteContent.objects.filter(key=key, is_published=True).first()
            if existing and not force:
                self.stdout.write(f"  [SKIP] {key} already has published v{existing.version}")
                skipped_count += 1
                continue

            block = publish_content(
                key=key,
                data=data,
                author=author,
                notes="Initial content seed",
            )
            self.stdout.write(self.style.SUCCESS(f"  [LIVE] {key} published as v{block.version}"))
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Seeded {created_count} blocks ({skipped_count} skipped)."
            )
        )
