"""
cms/services.py
Business logic for SiteContent versioned content store.
All write operations live here; views remain thin.
"""
import logging
from django.db import transaction
from .models import SiteContent

logger = logging.getLogger(__name__)


def get_published_content(key: str) -> dict:
    """
    Return the data dict of the currently published SiteContent block.
    Returns None if no published version exists yet.
    """
    try:
        block = SiteContent.objects.get(key=key, is_published=True)
        return {
            'key': block.key,
            'version': block.version,
            'data': block.data,
            'notes': block.notes,
            'updated_at': block.updated_at.isoformat(),
            'author': (block.author.full_name or block.author.email) if block.author else None,
        }
    except SiteContent.DoesNotExist:
        return None


def list_content_history(key: str, limit: int = 20) -> list:
    """Return all versions for a key, newest first."""
    qs = SiteContent.objects.filter(key=key).select_related('author').order_by('-version')[:limit]
    return [
        {
            'version': b.version,
            'is_published': b.is_published,
            'notes': b.notes,
            'created_at': b.created_at.isoformat(),
            'author': (b.author.full_name or b.author.email) if b.author else None,
        }
        for b in qs
    ]


@transaction.atomic
def publish_content(key: str, data: dict, author, notes: str = '') -> SiteContent:
    """
    Save a new version and publish it. Unpublishes previous active version.
    Old versions are never deleted -- full history is always preserved.
    """
    # Deactivate current published version
    SiteContent.objects.filter(key=key, is_published=True).update(is_published=False)

    # Next version number
    last = SiteContent.objects.filter(key=key).order_by('-version').first()
    next_version = (last.version + 1) if last else 1

    block = SiteContent.objects.create(
        key=key,
        version=next_version,
        data=data,
        notes=notes,
        is_published=True,
        author=author,
    )
    logger.info(
        'SiteContent published: key=%s version=%s author=%s',
        key, next_version, getattr(author, 'email', str(author))
    )
    return block


@transaction.atomic
def save_draft(key: str, data: dict, author, notes: str = '') -> SiteContent:
    """
    Save a new draft version without publishing it.
    The existing published version stays active.
    """
    last = SiteContent.objects.filter(key=key).order_by('-version').first()
    next_version = (last.version + 1) if last else 1

    block = SiteContent.objects.create(
        key=key,
        version=next_version,
        data=data,
        notes=notes,
        is_published=False,
        author=author,
    )
    logger.info(
        'SiteContent draft saved: key=%s version=%s author=%s',
        key, next_version, getattr(author, 'email', str(author))
    )
    return block


@transaction.atomic
def rollback_content(key: str, target_version: int, author) -> SiteContent:
    """
    Re-publish a historical version by creating a new version entry
    with the same data. Does NOT delete any rows.
    """
    target = SiteContent.objects.get(key=key, version=target_version)
    return publish_content(
        key=key,
        data=target.data,
        author=author,
        notes=f'Rollback to v{target_version}',
    )


# ---------------------------------------------------------------------------
# Case Studies helpers (backed by SiteContent key=CASE_STUDIES)
# ---------------------------------------------------------------------------

def get_case_studies(sector: str = 'all') -> list:
    """Return published case studies, optionally filtered by sector."""
    content = get_published_content(SiteContent.Key.CASE_STUDIES)
    studies = content['data'].get('studies', []) if content else _get_default_case_studies()
    if sector and sector != 'all':
        studies = [s for s in studies if s.get('sector') == sector]
    return studies


def get_case_study_by_slug(slug: str) -> dict | None:
    """Return a single case study by slug."""
    studies = get_case_studies()
    return next((s for s in studies if s.get('slug') == slug), None)


def _get_default_case_studies() -> list:
    """Bootstrap defaults used until admin publishes real content."""
    return [
        {
            'slug': 'fintech-cloud-platform-acceleration',
            'title': 'Scaling Cloud Platform Engineering for Tier-1 FinTech',
            'sector': 'tech',
            'sectorLabel': 'Technology & Cloud',
            'client': 'Global NeoBank Enterprise',
            'timeline': '3 Months',
            'summary': 'Reduced time-to-hire from 48 days to 11 days while placing 14 high-throughput Python and Kubernetes engineers with zero post-onboarding attrition.',
            'challenge': 'The client was facing severe sprint bottlenecks launching their cross-border payment rails due to a shortage of vetted distributed systems engineers with PCI-DSS compliance backgrounds.',
            'solution': 'Pepoltek deployed our AI semantic matching pipeline combined with peer-level architectural vetting to shortlist candidates within 72 hours, orchestrating synchronous technical panel assessments.',
            'metrics': [
                {'label': 'Time-to-Hire', 'value': '11 Days', 'baseline': '48 Days Previously'},
                {'label': 'Engineers Placed', 'value': '14 Specialists', 'baseline': '100% Offer Acceptance'},
                {'label': 'First-Year Retention', 'value': '100%', 'baseline': 'Top Decile'},
                {'label': 'Cost Savings', 'value': '32%', 'baseline': 'vs Traditional Headhunters'},
            ],
            'quote': {
                'text': 'Pepoltek is the only staffing partner that actually understands modern distributed architectures. Every single candidate they sent over could code on day one.',
                'author': 'Marcus Vance',
                'title': 'VP of Engineering, Global Payments',
            },
        },
        {
            'slug': 'regional-health-system-icu-nursing',
            'title': 'Emergency Staffing & Primary Credentialing for Acute Care Network',
            'sector': 'healthcare',
            'sectorLabel': 'Healthcare & Clinical',
            'client': 'Multi-State Regional Hospital Network',
            'timeline': '6 Weeks',
            'summary': 'Mobilized 28 ICU and telemetry travel nurses with 100% credential compliance pass rate on day 1, averting unit closures across 3 regional facilities.',
            'challenge': 'Seasonal patient surges and unexpected nursing vacancies left 4 acute care facilities dangerously below required staff-to-patient ratios, threatening patient safety and facility accreditation.',
            'solution': 'Pepoltek healthcare credentialing team executed automated primary source license verifications, immunization reviews, and drug screening within a 5-day cycle.',
            'metrics': [
                {'label': 'Deployment Speed', 'value': '5 Days', 'baseline': '30-Day Industry Avg'},
                {'label': 'Nurses Mobilized', 'value': '28 Clinicians', 'baseline': 'Zero Shift Cancellations'},
                {'label': 'Day-1 Credential Pass', 'value': '100%', 'baseline': 'Zero Deficiencies'},
                {'label': 'Overtime Reductions', 'value': '41%', 'baseline': 'Substantial Facility Savings'},
            ],
            'quote': {
                'text': 'The clinical credentialing rigor was impeccable. Pepoltek delivered ready-to-work ICU nurses with verified certifications before our deadline.',
                'author': 'Dr. Evelyn Reed',
                'title': 'Chief Nursing Officer, MetroHealth Alliance',
            },
        },
        {
            'slug': 'ai-biotech-nlp-data-pipeline',
            'title': 'BioTech Genomic NLP Model Training Pipeline Staffing',
            'sector': 'tech',
            'sectorLabel': 'Technology & Cloud',
            'client': 'Next-Gen Oncology BioTech',
            'timeline': '2 Months',
            'summary': 'Supplied 6 specialized PyTorch and Bioinformatics machine learning researchers to accelerate oncology publication timelines by 4 months.',
            'challenge': 'Candidate pool for researchers possessing both deep biomedical context and advanced transformer model training capabilities was virtually non-existent through standard job boards.',
            'solution': 'Pepoltek leveraged our reverse search algorithms and academic talent networks to engage passive PhD-level research engineers.',
            'metrics': [
                {'label': 'Sourcing Cycle', 'value': '9 Days', 'baseline': '90+ Days Industry'},
                {'label': 'Researchers Integrated', 'value': '6 PhD Specialists', 'baseline': 'Complete Project Team'},
                {'label': 'Delivery Acceleration', 'value': '4 Months', 'baseline': 'Ahead of Schedule'},
                {'label': 'IP Clearance', 'value': '100%', 'baseline': 'Complete NDA & Work-for-Hire'},
            ],
            'quote': {
                'text': 'Finding AI talent with biology expertise is needle-in-a-haystack work. Pepoltek delivered exactly the caliber of research talent we needed.',
                'author': 'Siddharth Nair',
                'title': 'Head of AI Research, Cellomics',
            },
        },
    ]
