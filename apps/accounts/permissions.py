"""
accounts/permissions.py
Role-based DRF permission classes.
All checks are server-side. Frontend middleware is convenience only.
"""
from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    """Base class: subclass and set `required_role`."""
    required_role = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        return request.user.has_role(self.required_role)


class IsCandidate(HasRole):
    required_role = 'CANDIDATE'


class IsReferrer(HasRole):
    required_role = 'REFERRER'


class IsLearner(HasRole):
    required_role = 'LEARNER'


class IsRecruiter(HasRole):
    required_role = 'RECRUITER'


class IsBusinessAnalyst(HasRole):
    required_role = 'BUSINESS_ANALYST'


class IsTechValidator(HasRole):
    required_role = 'TECH_VALIDATOR'


class IsCredentialOfficer(HasRole):
    required_role = 'CREDENTIAL_OFFICER'


class IsAdmin(HasRole):
    required_role = 'ADMIN'


class IsSuperAdmin(HasRole):
    required_role = 'SUPER_ADMIN'


class IsAdminOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        return request.user.has_role('ADMIN') or request.user.has_role('SUPER_ADMIN')


class IsStaffMember(BasePermission):
    """Any internal Pepoltek staff role."""
    STAFF_ROLES = {
        'RECRUITER',
        'BUSINESS_ANALYST',
        'TECH_VALIDATOR',
        'CREDENTIAL_OFFICER',
        'ADMIN',
        'SUPER_ADMIN',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False) or getattr(request.user, 'is_staff', False):
            return True
        return bool(self.STAFF_ROLES & set(request.user.get_roles()))


class IsStaff(IsStaffMember):
    """Alias for IsStaffMember used in Swagger and admin views."""
    pass


class IsOwner(BasePermission):
    """Object-level: user can only access their own record."""
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, 'user', None) or getattr(obj, 'user_id', None)
        if owner is None:
            return False
        owner_id = owner.pk if hasattr(owner, 'pk') else owner
        return str(request.user.pk) == str(owner_id)


# Complete System Role and Permissions Catalogue (aligned with Technical SRS Section 4)
ROLE_CAPABILITIES = {
    'CANDIDATE': {
        'code': 'CANDIDATE',
        'name': 'Candidate',
        'category': 'Talent Network',
        'scope': 'Candidate Dashboard (/candidate/*), Applications & CV',
        'description': 'Verified candidate profile, confidential reverse job matching, and sprint squad placement.',
        'permissions': [
            'Own profile: Read & Update',
            'Anonymous pitch authorization: Toggle',
            'Job board & gigs: Browse & Apply',
            'Assessments: View own scorecards',
        ],
    },
    'REFERRER': {
        'code': 'REFERRER',
        'name': 'Referrer',
        'category': 'Ecosystem Community',
        'scope': 'Referral Dashboard (/candidate/referrals), Bounty Ledger',
        'description': 'Talent scout and ecosystem referrer with double-entry bounty ledger access.',
        'permissions': [
            'Referral link attribution: Read',
            'Candidate submissions: Submit',
            'Bounty ledger: View earned & pending rewards',
        ],
    },
    'LEARNER': {
        'code': 'LEARNER',
        'name': 'Learner',
        'category': 'Talent Academy',
        'scope': 'Academy Dashboard (/candidate/academy), Course Modules',
        'description': 'Academy student with course enrollment, progress tracking, and readiness credentials.',
        'permissions': [
            'Academy courses: Browse & Enroll',
            'Course progress & modules: Read & Complete',
            'Readiness index badges: Earn',
        ],
    },
    'RECRUITER': {
        'code': 'RECRUITER',
        'name': 'Recruiter',
        'category': 'Internal Staff',
        'scope': 'Recruiter Workspace (/recruiter/*), ATS APIs (/api/v1/ats/*)',
        'description': 'Full ATS access, candidate sourcing, pipeline stage management, and technical interview scheduling.',
        'permissions': [
            'Requisitions: Create, Read & Update',
            'Candidate pool: Read & Search',
            '5-Stage ATS Pipeline: Move & Manage',
            'Technical interviews: Schedule & Confirm',
            'Requisition staffing & allocation: Manage',
        ],
    },
    'BUSINESS_ANALYST': {
        'code': 'BUSINESS_ANALYST',
        'name': 'Business Analyst',
        'category': 'Internal Staff',
        'scope': 'Staff Workspace (/recruiter/*), Leads APIs (/api/v1/leads/*)',
        'description': 'Client discovery documentation, requisition specification drafting, and candidate pool review.',
        'permissions': [
            'Client discovery records: Create & Update',
            'Requisition specifications: Draft & Read',
            'Candidate pool: Read assigned',
            'Hiring velocity telemetry: Read',
        ],
    },
    'TECH_VALIDATOR': {
        'code': 'TECH_VALIDATOR',
        'name': 'Technical Validator',
        'category': 'Internal Staff',
        'scope': 'Staff Workspace (/recruiter/*), Vetting APIs (/api/v1/vetting/*)',
        'description': 'Technical code evaluation, system design grading, repository reviews, and candidate vetting scorecards.',
        'permissions': [
            'Technical assessments: Create, Grade & Update',
            'Candidate vetting scorecards: Score (0-100)',
            'Assigned candidates: Read & Review',
            'Subscore grading: Code, System, Tests, Behavioral',
        ],
    },
    'CREDENTIAL_OFFICER': {
        'code': 'CREDENTIAL_OFFICER',
        'name': 'Credential Officer',
        'category': 'Internal Staff',
        'scope': 'Staff Workspace (/recruiter/*), Vetting APIs (/api/v1/vetting/*)',
        'description': 'Healthcare license verification, clinical certification auditing, and daily expiry job management.',
        'permissions': [
            'Healthcare licenses: Verify, Approve & Reject',
            'Clinical certifications: Audit & Track',
            'License expiration scans: Audit log read',
            'Assigned clinical talent: Read',
        ],
    },
    'ADMIN': {
        'code': 'ADMIN',
        'name': 'Platform Administrator',
        'category': 'Platform Governance',
        'scope': 'Admin Portal (/admin/*), Config Center (/api/v1/config/*)',
        'description': 'User directory governance, staff invitation dispatch, hiring calculator rules, and system configuration.',
        'permissions': [
            'User directory: Read, Update roles & Suspend',
            'Staff invitations: Provision & Email dispatch',
            'Config Center & Calculator: Read & Update',
            'Platform telemetry & uptime: Read',
            'Audit log: Read',
        ],
    },
    'SUPER_ADMIN': {
        'code': 'SUPER_ADMIN',
        'name': 'Super Administrator',
        'category': 'Executive Governance',
        'scope': 'Global Platform Access (/admin/*, Django Admin, All APIs)',
        'description': 'Unrestricted platform authority, global RBAC assignment, security policies, and data export or deletion.',
        'permissions': [
            'All platform resources: Full CRUD & Approve',
            'Global RBAC & Role assignment: Unrestricted',
            'Escrow vault & Bounties: Approve payouts',
            'Security & audit logs: Full access',
            'Candidate PII: Unmasked inspection',
        ],
    },
}

ALL_SYSTEM_PERMISSIONS = [
    {
        'domain': 'Recruitment ATS & Pipeline',
        'permissions': [
            {'code': 'ats:requisitions:read', 'label': 'View open and archived requisitions'},
            {'code': 'ats:requisitions:write', 'label': 'Create and edit enterprise requisitions'},
            {'code': 'ats:pipeline:manage', 'label': 'Manage 5-stage ATS pipeline transitions'},
            {'code': 'ats:interviews:schedule', 'label': 'Schedule interviews and dispatch candidate invites'},
            {'code': 'ats:requisitions:allocate', 'label': 'Allocate candidates to active requisitions'},
            {'code': 'ats:pods:manage', 'label': 'Allocate candidates to active requisitions (legacy alias)'},
        ],
    },
    {
        'domain': 'Candidate Vetting & Compliance',
        'permissions': [
            {'code': 'vetting:scorecards:create', 'label': 'Create and evaluate technical scorecards'},
            {'code': 'vetting:scores:override', 'label': 'Override vetting benchmark scores'},
            {'code': 'vetting:licenses:verify', 'label': 'Verify healthcare clinical licenses'},
            {'code': 'vetting:compliance:audit', 'label': 'Audit Right to Work sharecodes and compliance'},
            {'code': 'vetting:pii:unmask', 'label': 'Unmasked candidate contact and PII inspection'},
        ],
    },
    {
        'domain': 'Enterprise Discovery & Leads',
        'permissions': [
            {'code': 'leads:discovery:create', 'label': 'Author client discovery briefs and squad sizing'},
            {'code': 'leads:specs:draft', 'label': 'Draft requisition specifications'},
            {'code': 'leads:view:all', 'label': 'Inspect inbound client leads and consultations'},
        ],
    },
    {
        'domain': 'Referrals & Ecosystem Ledger',
        'permissions': [
            {'code': 'referrals:ledger:read', 'label': 'Inspect double-entry bounty ledger'},
            {'code': 'referrals:payout:approve', 'label': 'Authorize bounty payouts and escrow disbursements'},
        ],
    },
    {
        'domain': 'Talent Academy & Credentials',
        'permissions': [
            {'code': 'academy:courses:manage', 'label': 'Create and publish academy curriculum'},
            {'code': 'academy:badges:issue', 'label': 'Issue readiness credentials and skills badges'},
        ],
    },
    {
        'domain': 'Platform Governance & RBAC',
        'permissions': [
            {'code': 'admin:users:read', 'label': 'Access user directory and dossier inspect'},
            {'code': 'admin:users:manage_roles', 'label': 'Assign, update, and revoke user roles'},
            {'code': 'admin:users:suspend', 'label': 'Suspend and reactivate platform accounts'},
            {'code': 'admin:roles:manage', 'label': 'Create, edit, and configure role groups'},
            {'code': 'admin:config:write', 'label': 'Update hiring calculator rules and parameters'},
            {'code': 'admin:audit:read', 'label': 'Inspect immutable system audit logs and telemetry'},
        ],
    },
]
