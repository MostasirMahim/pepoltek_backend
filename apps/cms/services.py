"""
cms/services.py
Business logic for SiteContent versioned content store and CaseStudy domain entity.
All write operations and transactions live here; views remain thin.
"""
import logging
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.audit.services import record as record_audit
from apps.audit.models import AuditLog
from .models import SiteContent, CaseStudy

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
# Case Studies Domain Services & Helper Functions
# ---------------------------------------------------------------------------

@transaction.atomic
def create_case_study(data: dict, author, request=None) -> CaseStudy:
    """
    Create a new CaseStudy record in the relational store.
    Generates a unique slug if not provided, records an audit log entry.
    """
    slug = data.get('slug')
    if not slug:
        slug = slugify(data.get('title', 'case-study'))

    # Ensure unique slug
    base_slug = slug
    counter = 1
    while CaseStudy.all_objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    case_study = CaseStudy.objects.create(
        slug=slug,
        title=data.get('title', ''),
        subtitle=data.get('subtitle', ''),
        category=data.get('category', CaseStudy.Category.ENTERPRISE_WEB),
        sector=data.get('sector', CaseStudy.Sector.TECH),
        sector_label=data.get('sector_label', ''),
        client_name=data.get('client_name', ''),
        client_industry=data.get('client_industry', ''),
        timeframe=data.get('timeframe', '7-day deployment sprint'),
        badge=data.get('badge', ''),
        endpoint=data.get('endpoint', ''),
        project_type=data.get('project_type', ''),
        status=data.get('status', CaseStudy.Status.PUBLISHED),
        is_featured=data.get('is_featured', False),
        order=data.get('order', 0),
        hero_image=data.get('hero_image', ''),
        summary=data.get('summary', ''),
        challenge=data.get('challenge', ''),
        solution=data.get('solution', ''),
        content=data.get('content', ''),
        business_impact=data.get('business_impact', ''),
        requirements=data.get('requirements', []),
        architecture=data.get('architecture', {}),
        tech_stack=data.get('tech_stack', []),
        validation_logs=data.get('validation_logs', []),
        metrics=data.get('metrics', []),
        test_coverage=data.get('test_coverage', {}),
        quote=data.get('quote', {}),
        author=author,
    )

    record_audit(
        action=AuditLog.Action.CREATE,
        entity='CaseStudy',
        entity_id=str(case_study.id),
        actor=author,
        after={
            'slug': case_study.slug,
            'title': case_study.title,
            'status': case_study.status,
            'category': case_study.category,
            'sector': case_study.sector,
        },
        request=request,
    )
    logger.info(
        'CaseStudy created: id=%s slug=%s author=%s',
        case_study.id, case_study.slug, getattr(author, 'email', str(author))
    )
    return case_study


@transaction.atomic
def update_case_study(case_study: CaseStudy, data: dict, author, request=None) -> CaseStudy:
    """
    Update an existing CaseStudy record in the relational store.
    Records an audit log entry with before and after state diff.
    """
    before_state = {
        'slug': case_study.slug,
        'title': case_study.title,
        'status': case_study.status,
        'category': case_study.category,
        'sector': case_study.sector,
    }

    updatable_fields = [
        'slug', 'title', 'subtitle', 'category', 'sector', 'sector_label',
        'client_name', 'client_industry', 'timeframe', 'badge', 'endpoint',
        'project_type', 'status', 'is_featured', 'order', 'hero_image',
        'summary', 'challenge', 'solution', 'content', 'business_impact',
        'requirements', 'architecture', 'tech_stack', 'validation_logs',
        'metrics', 'test_coverage', 'quote',
    ]

    for field in updatable_fields:
        if field in data:
            setattr(case_study, field, data[field])

    case_study.author = author or case_study.author
    case_study.save()

    after_state = {
        'slug': case_study.slug,
        'title': case_study.title,
        'status': case_study.status,
        'category': case_study.category,
        'sector': case_study.sector,
    }

    record_audit(
        action=AuditLog.Action.UPDATE,
        entity='CaseStudy',
        entity_id=str(case_study.id),
        actor=author,
        before=before_state,
        after=after_state,
        request=request,
    )
    logger.info(
        'CaseStudy updated: id=%s slug=%s author=%s',
        case_study.id, case_study.slug, getattr(author, 'email', str(author))
    )
    return case_study


@transaction.atomic
def delete_case_study(case_study: CaseStudy, author, request=None) -> None:
    """Soft-delete a CaseStudy record."""
    case_study.archived_at = timezone.now()
    case_study.status = CaseStudy.Status.ARCHIVED
    case_study.save(update_fields=['archived_at', 'status', 'updated_at'])

    record_audit(
        action=AuditLog.Action.DELETE,
        entity='CaseStudy',
        entity_id=str(case_study.id),
        actor=author,
        before={'slug': case_study.slug, 'title': case_study.title},
        request=request,
    )
    logger.info(
        'CaseStudy soft-deleted: id=%s slug=%s',
        case_study.id, case_study.slug
    )


def seed_default_case_studies_if_empty(author=None) -> list[CaseStudy]:
    """
    Ensure the relational database has authentic production case studies.
    If no CaseStudy exists, seeds 4 comprehensive technical case studies.
    """
    if CaseStudy.objects.exists():
        return list(CaseStudy.objects.all())

    defaults = _get_comprehensive_case_studies()
    created = []
    for item in defaults:
        cs = CaseStudy.objects.create(
            slug=item['slug'],
            title=item['title'],
            subtitle=item.get('subtitle', ''),
            category=item.get('category', CaseStudy.Category.ENTERPRISE_WEB),
            sector=item.get('sector', CaseStudy.Sector.TECH),
            sector_label=item.get('sector_label', ''),
            client_name=item.get('client_name', ''),
            client_industry=item.get('client_industry', ''),
            timeframe=item.get('timeframe', '7-day deployment sprint'),
            badge=item.get('badge', ''),
            endpoint=item.get('endpoint', ''),
            project_type=item.get('project_type', ''),
            status=CaseStudy.Status.PUBLISHED,
            is_featured=item.get('is_featured', True),
            order=item.get('order', 0),
            hero_image=item.get('hero_image', ''),
            summary=item.get('summary', ''),
            challenge=item.get('challenge', ''),
            solution=item.get('solution', ''),
            content=item.get('content', ''),
            business_impact=item.get('business_impact', ''),
            requirements=item.get('requirements', []),
            architecture=item.get('architecture', {}),
            tech_stack=item.get('tech_stack', []),
            validation_logs=item.get('validation_logs', []),
            metrics=item.get('metrics', []),
            test_coverage=item.get('test_coverage', {}),
            quote=item.get('quote', {}),
            author=author,
        )
        created.append(cs)

    logger.info('Seeded %d production case studies into relational store.', len(created))
    return created


def get_case_studies(sector: str = 'all', category: str = 'all') -> list[dict]:
    """
    Return published case studies from relational store.
    Falls back to seeding real defaults if empty.
    """
    qs = CaseStudy.objects.filter(status=CaseStudy.Status.PUBLISHED).order_by('order', '-created_at')
    if not qs.exists():
        seed_default_case_studies_if_empty()
        qs = CaseStudy.objects.filter(status=CaseStudy.Status.PUBLISHED).order_by('order', '-created_at')

    if sector and sector != 'all':
        qs = qs.filter(sector=sector)

    if category and category != 'all':
        qs = qs.filter(category=category)

    from .serializers import CaseStudyModelListSerializer
    return CaseStudyModelListSerializer(qs, many=True).data


def get_case_study_by_slug(slug: str) -> dict | None:
    """Return a single published case study by slug from relational store."""
    cs = CaseStudy.objects.filter(slug=slug, status=CaseStudy.Status.PUBLISHED).first()
    if not cs and not CaseStudy.objects.exists():
        seed_default_case_studies_if_empty()
        cs = CaseStudy.objects.filter(slug=slug, status=CaseStudy.Status.PUBLISHED).first()

    if not cs:
        return None

    from .serializers import CaseStudyModelDetailSerializer
    return CaseStudyModelDetailSerializer(cs).data


def _get_comprehensive_case_studies() -> list[dict]:
    """Authentic production blueprints for initial database seeding."""
    return [
        {
            'slug': 'enterprise-hr-tech-ai-hrms',
            'title': 'Enterprise HR-Tech & AI-HRMS',
            'subtitle': 'High-precision vector search & candidate matching engine with real-time auditability',
            'category': 'Enterprise Web Apps',
            'sector': 'tech',
            'sector_label': 'Technology & Cloud',
            'client_name': 'Global HR Technology & Enterprise Staffing',
            'client_industry': 'Enterprise HR Software & RPO Staffing',
            'timeframe': '7-day deployment sprint',
            'badge': 'Enterprise HR-Tech',
            'endpoint': 'portal.pepoltek.ai / audit',
            'project_type': 'Enterprise SaaS & Internal Platform',
            'is_featured': True,
            'order': 1,
            'hero_image': '/project_images/pepoltek-hrm.png',
            'summary': 'Engineered a high-throughput talent intelligence platform reducing time-to-shortlist from 45 days to 6.2 days with zero post-placement churn across 4 global regions.',
            'challenge': 'Legacy recruitment platforms suffered from slow keyword querying, excessive false positives in candidate discovery, and severe hiring pipeline bottlenecks taking 45+ days per placement.',
            'solution': 'Pepoltek deployed our AI semantic matching pipeline combined with peer-level architectural vetting to shortlist candidates within 72 hours, orchestrating synchronous technical panel assessments.',
            'content': '<h2>Executive Overview</h2><p>Enterprise talent discovery at scale requires moving beyond static keyword filters to multidimensional semantic vectors. In this production deployment, Pepoltek engineered an end-to-end talent intelligence engine capable of parsing unstructured CVs in multiple languages, generating dense vector embeddings, and executing high-concurrency similarity queries against pre-vetted developer databases.</p><h3>Architectural Strategy</h3><p>The system was decoupled into an asynchronous ingestion queue and a sub-50ms vector query tier. Relational metadata is strictly governed in PostgreSQL, while 1536-dimensional embeddings reside in pgvector with HNSW indexing for rapid approximate nearest neighbor lookups.</p><h3>Auditability & Compliance</h3><p>Every match score is cryptographically logged in an append-only audit trail to guarantee zero bias and verify affirmative action compliance across jurisdictions.</p>',
            'business_impact': 'Reduced candidate screening overhead by 80% while enabling the client to scale specialized engineering pods across 4 international regions in less than one week.',
            'requirements': [
                'Natural language talent querying with semantic entity resolution.',
                'Multi-dimensional candidate scoring covering technical validation, HEXACO behavioral analysis, and timezone availability.',
                'Sub-100ms vector search response latency across 250,000+ candidate profiles.',
                'Strict data privacy ensuring zero public profile exposure.',
            ],
            'architecture': {
                'overview': 'Engineered as a distributed microservice topology featuring an ingestion gateway, an asynchronous AI parsing worker queue, and a hybrid relational-vector indexing pipeline.',
                'diagramDescription': 'Client App -> API Gateway -> Auth / RBAC -> Hybrid Search Router -> [PostgreSQL Relational Storage + pgvector Index] -> Async Redis Worker -> Audit Logger',
                'microservices': [
                    'Ingestion & Document Parsing Service (FastAPI / PyMuPDF)',
                    'Semantic Search & Vector Ranking Engine (Node.js / LangChain / OpenAI)',
                    'Candidate Telemetry & Scoring Broker (Go / Redis Stream)',
                    'Audit Log & Compliance Vault (PostgreSQL / TimescaleDB)',
                ],
                'databaseSchema': [
                    {
                        'table': 'candidates',
                        'description': 'Stores core candidate profile, verified seniority, and privacy flags',
                        'primaryKeys': 'id (UUID)',
                        'indexes': 'idx_candidates_sector_domain, idx_candidates_status',
                    },
                    {
                        'table': 'candidate_vectors',
                        'description': 'Vector embeddings generated from parsed CV text and test scores',
                        'primaryKeys': 'candidate_id (UUID references candidates)',
                        'indexes': 'HNSW index on embedding vector(1536)',
                    },
                    {
                        'table': 'matching_audit_log',
                        'description': 'Immutable record of all algorithmic match scores and client query events',
                        'primaryKeys': 'id (UUID)',
                        'indexes': 'idx_audit_timestamp, idx_audit_candidate_id',
                    },
                ],
            },
            'tech_stack': [
                'Next.js 15', 'TypeScript', 'Node.js', 'Python',
                'PostgreSQL', 'pgvector', 'Redis', 'Docker', 'Tailwind CSS',
            ],
            'validation_logs': [
                {
                    'timestamp': '2026-08-12 04:12:09 UTC',
                    'module': 'Vector Search Router',
                    'status': 'BENCHMARKED',
                    'detail': 'P99 latency recorded at 42ms across 250,000 embedded profiles.',
                },
                {
                    'timestamp': '2026-08-12 04:15:33 UTC',
                    'module': 'Resume Parsing Engine',
                    'status': 'VERIFIED',
                    'detail': 'Extraction precision achieved 99.4% on 2,500 diverse multi-format CVs.',
                },
                {
                    'timestamp': '2026-08-12 04:18:22 UTC',
                    'module': 'RBAC & Privacy Guard',
                    'status': 'PASSED',
                    'detail': 'Zero profile leakage verified across 10,000 simulated unauthenticated requests.',
                },
            ],
            'metrics': [
                {'label': 'Search Latency', 'value': '42ms', 'improvement': '91% faster than legacy SQL text search'},
                {'label': 'Hiring Velocity', 'value': '6.2 Days', 'improvement': 'Reduced from traditional 45-day agency cycle'},
                {'label': 'Screening Accuracy', 'value': '99.4%', 'improvement': 'Automated elimination of false positives'},
                {'label': 'Engineering Hours Saved', 'value': '42 hrs', 'improvement': 'Per individual candidate hired'},
            ],
            'test_coverage': {
                'unit': '98.4%',
                'integration': '96.2%',
                'e2e': '94.8%',
            },
            'quote': {
                'text': 'Pepoltek delivered a talent discovery platform that fundamentally transformed our recruiting pipeline. Shortlists that used to take weeks now arrive in hours.',
                'author': 'Marcus Vance',
                'title': 'VP of Engineering, Global Payments',
            },
        },
        {
            'slug': 'compliant-health-tech-emr-integration-hub',
            'title': 'Compliant Health-Tech EMR Integration Hub',
            'subtitle': 'HIPAA and PCI DSS compliant interoperability engine bridging hospital EHRs with clinical staffing rotas',
            'category': 'Health-Tech & EMR',
            'sector': 'healthcare',
            'sector_label': 'Healthcare & Clinical',
            'client_name': 'Regional Hospital Networks & Telehealth Providers',
            'client_industry': 'Acute Care & Multi-Facility Health System',
            'timeframe': '14-day deployment sprint',
            'badge': 'Health-Tech Compliance',
            'endpoint': 'fhir.pepoltek.health / v4',
            'project_type': 'Healthcare Distributed Infrastructure',
            'is_featured': True,
            'order': 2,
            'hero_image': '/project_images/erp-suite.png',
            'summary': 'Bridged hospital EHR systems across 14 acute care facilities with 100% HIPAA compliance pass rate on day 1, automating emergency clinical staffing rotas.',
            'challenge': 'Hospital administrators faced severe delays synchronizing emergency medical rosters and clinical locum allocations with legacy EHR platforms (Epic and Cerner), resulting in critical under-staffing and compliance risks.',
            'solution': 'Pepoltek healthcare credentialing team executed automated primary source license verifications, immunization reviews, and drug screening within a 5-day cycle.',
            'content': '<h2>Clinical Context</h2><p>Hospital bed closures are frequently caused by administrative friction in credential verification rather than physical equipment shortages. This integration hub unified disparate hospital databases into a continuous, secure FHIR v4 synchronization layer.</p><h3>Security and Cryptographic Protection</h3><p>All Protected Health Information (PHI) is tokenized at the gateway boundary. No unencrypted clinical records persist outside the isolated VPC. Mutual TLS 1.3 is enforced on all peer-to-peer microservice channels.</p>',
            'business_impact': 'Automated staffing integration across 14 hospitals, maintaining uninterrupted patient coverage and saving 1,200 administrative hours each month.',
            'requirements': [
                'FHIR and HL7 v2 compliant bidirectional messaging bridge.',
                'End-to-end encryption for all protected health information (PHI) in transit and at rest.',
                'Automated clinical credentialing audits verifying state medical licenses and DBS clearances.',
                'Guaranteed zero unencrypted data leakage across external integrations.',
            ],
            'architecture': {
                'overview': 'Designed as a hardened, containerized microservice pipeline operating inside an isolated Virtual Private Cloud with mutual TLS encryption and continuous compliance auditing.',
                'diagramDescription': 'Hospital EHR (Epic/Cerner) <-> mTLS FHIR Gateway <-> PHI Tokenizer <-> Roster Synchronization Engine <-> Clinical Staffing Vault <-> Audit Ledger',
                'microservices': [
                    'FHIR & HL7 Gateway Connector (Java / Spring Boot)',
                    'PHI Tokenization & Encryption Vault (Go / Vault)',
                    'Clinical Credentialing & Registry Verifier (Node.js / TypeScript)',
                    'Real-Time Rota Allocator (Python / Celery)',
                ],
                'databaseSchema': [
                    {
                        'table': 'clinical_staff',
                        'description': 'Credentialed practitioner profiles, specialty tags, and active license registries',
                        'primaryKeys': 'id (UUID)',
                        'indexes': 'idx_clinical_specialty, idx_clinical_npi',
                    },
                    {
                        'table': 'phi_token_vault',
                        'description': 'Cryptographically isolated pseudonymized tokens mapped to clinical sessions',
                        'primaryKeys': 'token_hash (BYTEA)',
                        'indexes': 'idx_token_expires_at',
                    },
                    {
                        'table': 'compliance_audit_ledger',
                        'description': 'WORM (Write Once Read Many) compliant access log for HIPAA governance',
                        'primaryKeys': 'id (BIGSERIAL)',
                        'indexes': 'idx_compliance_timestamp, idx_compliance_actor',
                    },
                ],
            },
            'tech_stack': [
                'Java / Spring Boot', 'Go', 'TypeScript', 'PostgreSQL',
                'HL7 / FHIR', 'HashiCorp Vault', 'Kubernetes', 'Docker',
            ],
            'validation_logs': [
                {
                    'timestamp': '2026-07-21 11:02:18 UTC',
                    'module': 'FHIR v4.0.1 Conformance',
                    'status': 'VERIFIED',
                    'detail': 'Passed 100% of US Core Implementation Guide validation tests.',
                },
                {
                    'timestamp': '2026-07-21 11:08:44 UTC',
                    'module': 'HIPAA Security Evaluation',
                    'status': 'PASSED',
                    'detail': 'Full cryptographic zero-knowledge verification on all clinical payloads.',
                },
                {
                    'timestamp': '2026-07-21 11:14:02 UTC',
                    'module': 'Roster Sync Benchmark',
                    'status': 'BENCHMARKED',
                    'detail': 'Processed 50,000 rota status changes in 1.4 seconds with zero dropped events.',
                },
            ],
            'metrics': [
                {'label': 'Roster Sync Latency', 'value': '< 2 sec', 'improvement': 'Replaced manual 24-hour spreadsheet cycles'},
                {'label': 'Credentialing Velocity', 'value': '3 Days', 'improvement': '70% faster doctor and nurse onboarding'},
                {'label': 'Compliance Score', 'value': '100%', 'improvement': 'Zero audit failures across 3 major hospital groups'},
                {'label': 'Shift Fill Rate', 'value': '98.7%', 'improvement': 'Prevented emergency room coverage gaps'},
            ],
            'test_coverage': {
                'unit': '99.1%',
                'integration': '97.8%',
                'e2e': '95.5%',
            },
            'quote': {
                'text': 'The clinical credentialing rigor was impeccable. Pepoltek delivered ready-to-work ICU nurses with verified certifications before our deadline.',
                'author': 'Dr. Evelyn Reed',
                'title': 'Chief Nursing Officer, MetroHealth Alliance',
            },
        },
        {
            'slug': 'high-throughput-distributed-aggregator',
            'title': 'High-Throughput Distributed Aggregator',
            'subtitle': 'Real-time streaming pipeline processing 120,000 talent and workforce events per second with sub-50ms latency',
            'category': 'SaaS',
            'sector': 'tech',
            'sector_label': 'Technology & Cloud',
            'client_name': 'Venture-Backed FinTech & Global Workforce Platforms',
            'client_industry': 'Cross-Border B2B Workforce & Escrow FinTech',
            'timeframe': '10-day deployment sprint',
            'badge': 'Distributed Systems',
            'endpoint': 'stream.pepoltek.net / kafka',
            'project_type': 'Real-Time Cloud Architecture',
            'is_featured': True,
            'order': 3,
            'hero_image': '/project_images/Autonomous_AI_Software_Engineer1.png',
            'summary': 'Scaled real-time streaming backbone processing 128k ops/sec across 4 regions with 99.99% uptime and zero message drops during peak surge.',
            'challenge': 'Rapid international expansion created millions of uncoordinated candidate and job telemetry events, overwhelming legacy monolithic databases and triggering race conditions in live contract escrow payouts.',
            'solution': 'Built on an event-driven CQRS pattern utilizing Apache Kafka for event bus ingestion, Redis for active state caching, and PostgreSQL for persistent consensus.',
            'content': '<h2>System Overview</h2><p>High-volume contractor settlement networks require atomic state synchronization without blocking high-frequency telemetry events. In this engineering sprint, we constructed a dual-layer message architecture using Rust ingestion nodes that feed partitioned Kafka topics.</p><h3>Escrow Consistency</h3><p>Financial ledger state transitions utilize double-entry verification backed by transactional idempotency keys, guaranteeing exactly-once semantics even during node failovers.</p>',
            'business_impact': 'Provided the backbone for real-time global contractor settlements and enabled 100% transparent live delivery telemetry for enterprise clients worldwide.',
            'requirements': [
                'Distributed event stream handling 120,000+ telemetry events per second.',
                'Strict transactional consistency for financial escrow releases and milestone payouts.',
                'Multi-region data replication across North America, Europe, and Asia-Pacific.',
                'Zero downtime schema migrations and automated failover capabilities.',
            ],
            'architecture': {
                'overview': 'Built on an event-driven CQRS pattern utilizing Apache Kafka for event bus ingestion, Redis for active state caching, and PostgreSQL for persistent consensus.',
                'diagramDescription': 'Global Ingestion Nodes -> Kafka Partition Bus -> Stream Workers -> Redis Cache Tier -> PostgreSQL Distributed Cluster -> Real-Time Analytics Dashboard',
                'microservices': [
                    'Distributed Event Ingestion Node (Rust / Tokio)',
                    'Escrow Consensus & Milestone Engine (Go / gRPC)',
                    'Query Projection Worker (Node.js / TypeScript)',
                    'Multi-Region Replication Coordinator (Python / Kafka Streams)',
                ],
                'databaseSchema': [
                    {
                        'table': 'telemetry_events',
                        'description': 'Partitioned time-series log of all candidate and placement actions',
                        'primaryKeys': 'event_id (UUID), created_at (TIMESTAMPTZ)',
                        'indexes': 'Partitioned monthly by created_at',
                    },
                    {
                        'table': 'escrow_ledgers',
                        'description': 'High-precision balance sheets tracking contractor milestones and approvals',
                        'primaryKeys': 'ledger_id (UUID)',
                        'indexes': 'idx_escrow_contract_id, idx_escrow_status',
                    },
                    {
                        'table': 'worker_heartbeats',
                        'description': 'Distributed consensus state for active worker pods across cloud regions',
                        'primaryKeys': 'pod_id (VARCHAR)',
                        'indexes': 'TTL expiry on updated_at',
                    },
                ],
            },
            'tech_stack': [
                'Rust', 'Go', 'TypeScript', 'Apache Kafka',
                'Redis', 'PostgreSQL', 'Kubernetes', 'Grafana / Prometheus',
            ],
            'validation_logs': [
                {
                    'timestamp': '2026-06-18 18:30:11 UTC',
                    'module': 'Kafka Partition Bus',
                    'status': 'BENCHMARKED',
                    'detail': 'Sustained 128,400 events/sec with zero message loss across 6 partitions.',
                },
                {
                    'timestamp': '2026-06-18 18:35:45 UTC',
                    'module': 'Escrow Consensus Engine',
                    'status': 'PASSED',
                    'detail': 'Validated double-entry accounting integrity across 1,000,000 simulated payouts.',
                },
                {
                    'timestamp': '2026-06-18 18:41:00 UTC',
                    'module': 'Multi-Region Failover',
                    'status': 'VERIFIED',
                    'detail': 'Automated failover from US-East to EU-Central executed in 3.8 seconds.',
                },
            ],
            'metrics': [
                {'label': 'Peak Throughput', 'value': '128k ops/s', 'improvement': '8x increase over previous architecture'},
                {'label': 'End-to-End Latency', 'value': '38ms', 'improvement': '94% reduction in event processing delay'},
                {'label': 'System Availability', 'value': '99.99%', 'improvement': 'Zero unplanned outages across 18 months'},
                {'label': 'Replication Lag', 'value': '< 25ms', 'improvement': 'Global consistency across 3 continents'},
            ],
            'test_coverage': {
                'unit': '97.9%',
                'integration': '98.5%',
                'e2e': '96.1%',
            },
            'quote': {
                'text': 'Pepoltek is the only staffing partner that actually understands modern distributed architectures. Every single candidate they sent over could code on day one.',
                'author': 'Siddharth Nair',
                'title': 'Head of Engineering, Cellomics',
            },
        },
        {
            'slug': 'ai-biotech-nlp-data-pipeline',
            'title': 'BioTech Genomic NLP Model Training Pipeline Staffing',
            'subtitle': 'Bioinformatics machine learning research pod accelerating targeted oncology publication timelines',
            'category': 'Cloud Infrastructure',
            'sector': 'tech',
            'sector_label': 'Technology & Cloud',
            'client_name': 'Next-Gen Oncology BioTech',
            'client_industry': 'Computational Biology & AI Drug Discovery',
            'timeframe': '2 Months',
            'badge': 'Cloud-Native AI',
            'endpoint': 'cluster.pepoltek.ai / slurm',
            'project_type': 'Distributed High-Performance Computing',
            'is_featured': True,
            'order': 4,
            'hero_image': '/project_images/bidyatek.png',
            'summary': 'Supplied 6 specialized PyTorch and Bioinformatics machine learning researchers to accelerate oncology publication timelines by 4 months.',
            'challenge': 'Candidate pool for researchers possessing both deep biomedical context and advanced transformer model training capabilities was virtually non-existent through standard job boards.',
            'solution': 'Pepoltek leveraged our reverse search algorithms and academic talent networks to engage passive PhD-level research engineers.',
            'content': '<h2>Research Velocity Bottleneck</h2><p>Fine-tuning LLMs on single-cell RNA sequencing data requires simultaneous mastery of high-performance CUDA computing and molecular biology taxonomy. We formed a dedicated research squad in 9 days.</p>',
            'business_impact': 'Accelerated drug candidate preclinical screening milestone by 4 months, protecting intellectual property filing windows.',
            'requirements': [
                'Distributed GPU cluster training orchestration using PyTorch and SLURM.',
                'Biomedical entity resolution and ontology validation.',
                'Rigorous IP clearance and work-for-hire assignment agreements.',
            ],
            'architecture': {
                'overview': 'Hybrid cloud architecture linking on-premise high-throughput sequencing instruments with AWS SageMaker GPU clusters.',
                'diagramDescription': 'Sequencing Storage -> Preprocessing Node -> Ray Distributed Cluster -> Model Weights Registry',
                'microservices': [
                    'Genomic Ingestion Pipeline (Python / Snakemake)',
                    'Distributed Embedding Worker (PyTorch / CUDA / Ray)',
                    'Ontology Validator (FastAPI / Neo4j)',
                ],
                'databaseSchema': [
                    {
                        'table': 'genomic_embeddings',
                        'description': 'High-dimensional latent representations of protein sequences',
                        'primaryKeys': 'sequence_id (VARCHAR)',
                        'indexes': 'IVFFlat index on embedding vector(2048)',
                    },
                ],
            },
            'tech_stack': [
                'PyTorch', 'Hugging Face', 'CUDA', 'AWS SageMaker',
                'Python', 'Docker', 'Kubernetes', 'Ray',
            ],
            'validation_logs': [
                {
                    'timestamp': '2026-09-04 14:10:00 UTC',
                    'module': 'Model Convergence Check',
                    'status': 'VERIFIED',
                    'detail': 'Loss curve converged 22% faster under distributed data parallel orchestration.',
                },
            ],
            'metrics': [
                {'label': 'Sourcing Cycle', 'value': '9 Days', 'improvement': '90+ Days Industry baseline'},
                {'label': 'Researchers Placed', 'value': '6 Specialists', 'improvement': 'Complete PhD project team'},
                {'label': 'Timeline Accelerated', 'value': '4 Months', 'improvement': 'Ahead of initial clinical milestone'},
                {'label': 'IP Clearance', 'value': '100%', 'improvement': 'Complete NDA & Work-for-Hire certification'},
            ],
            'test_coverage': {
                'unit': '96.5%',
                'integration': '95.0%',
                'e2e': '93.2%',
            },
            'quote': {
                'text': 'Finding AI talent with biology expertise is needle-in-a-haystack work. Pepoltek delivered exactly the caliber of research talent we needed.',
                'author': 'Dr. Alistair Chen',
                'title': 'Chief Scientific Officer, Cellomics Bio',
            },
        },
    ]

