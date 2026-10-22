from rest_framework import serializers
from .models import Requisition, Application, ApplicationStage, ApplicationSource, Submission, DeliveryChannel


def get_default_responsibilities(obj):
    if obj.discovery and isinstance(obj.discovery, dict) and obj.discovery.get('responsibilities'):
        return obj.discovery['responsibilities']
    
    skills_text = ", ".join(obj.skills[:3]) if obj.skills else "core technologies"
    is_health = 'health' in (obj.sector or '').lower()
    if is_health:
        return [
            "Deliver patient-centered clinical care or medical informatics oversight aligned with institutional protocols.",
            "Maintain meticulous HIPAA-compliant clinical documentation, electronic health records (EHR), and patient charts.",
            "Collaborate cross-functionally with clinical staff, attending physicians, and administrative leadership.",
            "Participate in daily multidisciplinary huddles, quality assurance audits, and incident reviews."
        ]
    return [
        f"Architect, develop, and maintain high-throughput production services and APIs utilizing {skills_text}.",
        "Collaborate with engineering leads and product stakeholders in rapid 7-day sprint execution cycles.",
        "Implement comprehensive automated test suites including unit, integration, and performance benchmarks.",
        "Champion system resilience, database performance optimization, and zero-downtime CI/CD deployment pipelines."
    ]


def get_default_requirements(obj):
    if obj.discovery and isinstance(obj.discovery, dict) and obj.discovery.get('requirements'):
        return obj.discovery['requirements']
    
    level = obj.level or "Senior"
    is_health = 'health' in (obj.sector or '').lower()
    skills_text = ", ".join(obj.skills[:4]) if obj.skills else "domain standards"
    if is_health:
        return [
            f"Active professional state licensure or healthcare informatics accreditation for {level} level practice.",
            "Proven clinical or medical operations experience within acute care, hospital, or outpatient environments.",
            "Demonstrated competency in HIPAA Title II compliance, medical terminology, and EHR platforms.",
            "Exceptional interpersonal communication, patient advocacy, and emergency response capabilities."
        ]
    years = "5+ years" if any(w in level.lower() for w in ["lead", "architect", "principal", "senior"]) else "3+ years"
    return [
        f"{years} of verified engineering experience designing and operating production software at scale.",
        f"Deep hands-on proficiency in modern distributed systems, cloud computing, and {skills_text}.",
        "Solid theoretical and practical command of relational database design, indexing, and cache architectures.",
        "Track record of writing clean, self-documenting code with proactive security and telemetry instrumentation."
    ]


def get_default_nice_to_haves(obj):
    if obj.discovery and isinstance(obj.discovery, dict) and obj.discovery.get('nice_to_haves'):
        return obj.discovery['nice_to_haves']
    
    is_health = 'health' in (obj.sector or '').lower()
    if is_health:
        return [
            "Familiarity with Epic, Cerner, FHIR, HL7 interoperability standards, or clinical data analytics.",
            "Experience working with telemetry monitoring systems or clinical trial research protocols."
        ]
    return [
        "Experience operating in regulated SOC 2 or HIPAA environments with encrypted data handling.",
        "Familiarity with container orchestration (Kubernetes, Docker) and infrastructure-as-code (Terraform).",
        "Active contributions to open-source software, RFC proposals, or developer communities."
    ]


def get_default_benefits(obj):
    if obj.discovery and isinstance(obj.discovery, dict) and obj.discovery.get('benefits'):
        return obj.discovery['benefits']
    
    b_min = obj.budget_min or 85
    b_max = obj.budget_max or 135
    bounty_part = f"Eligible for referral reward program (up to ${int(obj.bounty_amount):,} bounty)." if (obj.bounty_enabled and obj.bounty_amount) else "Guaranteed direct client engagement with transparent bi-weekly compensation."
    return [
        f"Competitive hourly rate (${b_min} - ${b_max}/hr) backed by verified client escrow.",
        "100% remote work flexibility with guaranteed 4 to 8 hours live timezone overlap.",
        "Rapid 7-day deployment SLA from application to client kickoff.",
        "Proctor-free assessment: evaluate practical architecture skills rather than algorithmic puzzles.",
        bounty_part
    ]


def get_default_interview_process(obj):
    if obj.discovery and isinstance(obj.discovery, dict) and obj.discovery.get('interview_process'):
        return obj.discovery['interview_process']
    
    return [
        {"step": "1", "title": "Application & Profile Intake", "duration": "Day 1", "desc": "Submit CV and verified telemetry for automated ATS score benchmark."},
        {"step": "2", "title": "Technical Competency Check", "duration": "Day 2-3", "desc": "Practical systems and architecture vetting with senior engineers."},
        {"step": "3", "title": "Client Panel Alignment", "duration": "Day 4-5", "desc": "Live conversational walkthrough with the hiring engineering manager."},
        {"step": "4", "title": "Sprint Offer & Workspace Deploy", "duration": "Day 6-7", "desc": "Compliance signoff, contract finalization, and sprint onboarding."}
    ]


class PublicRequisitionSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    bounty_amount = serializers.DecimalField(max_digits=8, decimal_places=2, coerce_to_string=False, required=False)
    bounty_type_name = serializers.SerializerMethodField()
    responsibilities = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()
    nice_to_haves = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()
    interview_process = serializers.SerializerMethodField()

    class Meta:
        model = Requisition
        fields = [
            'id',
            'client_name',
            'title',
            'sector',
            'level',
            'headcount',
            'skills',
            'budget_min',
            'budget_max',
            'location',
            'engagement',
            'visibility',
            'bounty_enabled',
            'bounty_amount',
            'bounty_type_name',
            'status',
            'priority',
            'description',
            'responsibilities',
            'requirements',
            'nice_to_haves',
            'benefits',
            'interview_process',
            'created_at',
        ]

    def get_bounty_type_name(self, obj):
        if obj.bounty_type:
            return obj.bounty_type.name
        return None

    def get_responsibilities(self, obj):
        return get_default_responsibilities(obj)

    def get_requirements(self, obj):
        return get_default_requirements(obj)

    def get_nice_to_haves(self, obj):
        return get_default_nice_to_haves(obj)

    def get_benefits(self, obj):
        return get_default_benefits(obj)

    def get_interview_process(self, obj):
        return get_default_interview_process(obj)


class JobApplyInputSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    portfolio_url = serializers.URLField(required=False, allow_blank=True)


class RecruiterRequisitionSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    candidates_count = serializers.SerializerMethodField()
    bounty_type_name = serializers.SerializerMethodField()
    bounty_type_amount = serializers.SerializerMethodField()
    responsibilities = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()
    nice_to_haves = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()
    interview_process = serializers.SerializerMethodField()

    class Meta:
        model = Requisition
        fields = [
            'id',
            'client',
            'client_name',
            'title',
            'sector',
            'level',
            'headcount',
            'skills',
            'must_haves',
            'engagement',
            'visa_requirements',
            'timezone',
            'location',
            'budget_min',
            'budget_max',
            'visibility',
            'bounty_enabled',
            'bounty_type',
            'bounty_type_name',
            'bounty_type_amount',
            'bounty_amount',
            'status',
            'priority',
            'discovery',
            'description',
            'responsibilities',
            'requirements',
            'nice_to_haves',
            'benefits',
            'interview_process',
            'candidates_count',
            'created_at',
            'updated_at',
        ]

    def get_candidates_count(self, obj):
        return obj.applications.count()

    def get_bounty_type_name(self, obj):
        return obj.bounty_type.name if obj.bounty_type else None

    def get_bounty_type_amount(self, obj):
        return float(obj.bounty_type.amount) if obj.bounty_type else None

    def get_responsibilities(self, obj):
        return get_default_responsibilities(obj)

    def get_requirements(self, obj):
        return get_default_requirements(obj)

    def get_nice_to_haves(self, obj):
        return get_default_nice_to_haves(obj)

    def get_benefits(self, obj):
        return get_default_benefits(obj)

    def get_interview_process(self, obj):
        return get_default_interview_process(obj)


class RecruiterRequisitionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(required=True)
    sector = serializers.CharField(required=False, default='Technology & SDLC')
    client_name = serializers.CharField(required=False, default='Enterprise Workspace Partner')
    level = serializers.CharField(required=False, default='Senior')
    headcount = serializers.IntegerField(required=False, default=1)
    skills = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    engagement = serializers.CharField(required=False, default='Full-Time Requisition (W2/C2C)')
    location = serializers.CharField(required=False, default='100% Remote (US/EU)')
    budget_min = serializers.IntegerField(required=False, default=85)
    budget_max = serializers.IntegerField(required=False, default=125)
    visibility = serializers.CharField(required=False, default='published_job')
    # Bounty fields: use bounty_type_id (structured catalog) instead of flat bounty_amount
    bounty_enabled = serializers.BooleanField(required=False, default=False)
    bounty_type_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    bounty_amount = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True, default=None)
    priority = serializers.IntegerField(required=False, default=3)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    status = serializers.CharField(required=False, default='open')
    discovery = serializers.JSONField(required=False, default=dict)
    responsibilities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    requirements = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    nice_to_haves = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    benefits = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class RecruiterApplicationSerializer(serializers.ModelSerializer):
    candidate_id = serializers.CharField(source='candidate.id', read_only=True)
    candidate_name = serializers.CharField(source='candidate.full_name', read_only=True)
    candidate_email = serializers.CharField(source='candidate.user.email', read_only=True)
    requisition_title = serializers.CharField(source='requisition.title', read_only=True)
    client_name = serializers.CharField(source='requisition.client.name', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id',
            'candidate_id',
            'candidate_name',
            'candidate_email',
            'requisition',
            'requisition_title',
            'client_name',
            'stage',
            'sub_stage',
            'source',
            'created_at',
            'updated_at',
        ]


class SubmissionSerializer(serializers.ModelSerializer):
    requisition_title = serializers.CharField(source='requisition.title', read_only=True)
    client_name = serializers.CharField(source='requisition.client.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    candidates_count = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id',
            'requisition',
            'requisition_title',
            'client_name',
            'created_by',
            'created_by_name',
            'channel',
            'sent_at',
            'export_document_key',
            'items',
            'candidates_count',
            'created_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.email
        return 'System Recruiter'

    def get_candidates_count(self, obj):
        return len(obj.items) if isinstance(obj.items, list) else 0


class SubmissionCreateSerializer(serializers.Serializer):
    requisition_id = serializers.UUIDField(required=False, allow_null=True)
    channel = serializers.ChoiceField(choices=DeliveryChannel.choices, default=DeliveryChannel.EMAIL)
    pitch_notes = serializers.CharField(required=False, allow_blank=True, default='')
    client_name = serializers.CharField(required=False, allow_blank=True, default='Enterprise Client Partner')
    items = serializers.ListField(child=serializers.DictField(), required=True)


