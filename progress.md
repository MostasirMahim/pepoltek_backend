# Pepoltek Backend Implementation Progress

> **Tracking Reference:** Technical SRS v2.1 (`technical_srs_v1.md`)  
> **Backend Architecture:** Django 5 + DRF Modular Monolith (Clean Architecture)  
> **House Style Rule:** No em dashes anywhere in copy, documentation, or code.  
> **Status:** Active Execution  

---

## Completed Milestones and Task Breakdown

### 1. Environment Scaffolding and Virtual Environment
- **Task:** Created dedicated Python 3.12 virtual environment `.venv` under `pepoltek_backend/`.
- **Status:** Completed.
- **Details:**
  - Initialized isolated virtual environment via `python -m venv .venv`.
  - Upgraded `pip` to version 26.2.1.
  - Configured `requirements/base.txt` with Django 5.0.6, DRF 3.15.2, SimpleJWT 5.4.0, Wagtail 6.3.1, Celery 5.4.0, pgvector, argon2-cffi, and allauth.
  - Adjusted `django-filter` to `24.3` to maintain strict compatibility with Wagtail 6.3.1.
  - Added Windows-safe handling for `python-magic-bin==0.4.14; sys_platform == 'win32'`.
  - Configured `.env` and `.env.example` with local defaults for development.

### 2. Django Project Core Structure and Configuration
- **Task:** Scaffolded Django 5 core project files and environment-split settings.
- **Status:** Completed.
- **Details:**
  - `pepoltek_backend/manage.py`: Configured default entry point targeting `pepoltek.settings.dev`.
  - `pepoltek_backend/pepoltek/settings/base.py`: Centralized configuration, custom user model (`accounts.User`), Argon2 password hasher, Django Unfold admin, Wagtail CMS, REST Framework configuration with `drf-spectacular`, and Redis cache.
  - `pepoltek_backend/pepoltek/settings/dev.py`: Development overrides (Debug enabled, CORS permissive, debug toolbar, local storage, Mailpit SMTP).
  - `pepoltek_backend/pepoltek/settings/staging.py` & `prod.py`: Production-ready settings with strict security headers, Sentry, and cloud storage.
  - `pepoltek_backend/pepoltek/celery.py`: Celery application configured with 4 dedicated queues:
    - `ai`: Parsing, extraction, embedding generation.
    - `files`: File validation, ClamAV antivirus scanning, cloud exports.
    - `notify`: Async emails, in-app notifications, webhooks.
    - `default`: Core business operations and scheduled maintenance.
  - `pepoltek_backend/pepoltek/api_router.py`: Unified API v1 router mounting all modular domain apps.
  - `pepoltek_backend/pepoltek/urls.py`: Root routing for admin, API v1, Wagtail CMS, and OpenAPI 3.1 schema.

### 3. Core Foundation App (`apps/core/`)
- **Task:** Created shared base models, utilities, exceptions, and response formatters.
- **Status:** Completed.
- **Details:**
  - `apps/core/models.py`: Abstract `BaseModel` featuring UUIDv7 primary keys, standard UTC timestamps (`created_at`, `updated_at`), soft-deletion support (`archived_at` and `ActiveManager`), and `SafeEncryptionField` for PII.
  - `apps/core/pagination.py`: Standardized envelope pagination (`{ data: [...], meta: { page, page_size, total, total_pages } }`).
  - `apps/core/exceptions.py`: Uniform exception handler returning structured error payloads (`{ error: { code, message, fields } }`).
  - `apps/core/views.py`: System health check endpoint (`/api/v1/health/`).

### 4. Accounts and Authentication Domain (`apps/accounts/`)
- **Task:** Custom User model, Multi-Persona RBAC, and secure JWT authentication.
- **Status:** Completed.
- **Details:**
  - `apps/accounts/models.py`:
    - `User`: Custom user with email as username, Argon2 hashing, unique referral code generated on creation, attribution linkage, MFA toggle, and account status.
    - `UserRole`: Multi-persona support allowing users to hold multiple roles simultaneously (`VISITOR`, `CANDIDATE`, `REFERRER`, `LEARNER`, `RECRUITER`, `BA`, `VALIDATOR`, `CREDENTIAL_OFFICER`, `ADMIN`, `SUPER_ADMIN`) with optional client scope.
    - `ConsentRecord`: Append-only compliance log capturing user consent for Terms and Privacy with version, IP address, and user agent.
  - `apps/accounts/services.py`: Business logic for registration with referral code attribution, credential verification, and secure httpOnly cookie tokens (strictly preventing JWT tokens in `localStorage`).
  - `apps/accounts/permissions.py`: Role-based access control permission classes (`IsCandidate`, `IsRecruiter`, `IsAdmin`, `IsCredentialOfficer`, `HasAnyRole`).
  - `apps/accounts/views.py`: Secure auth endpoints (`/register`, `/login`, `/logout`, `/me`, `/refresh`).

### 5. Audit Logging App (`apps/audit/`)
- **Task:** Structured immutable audit trail for compliance and security.
- **Status:** Completed.
- **Details:**
  - `apps/audit/models.py`: `AuditLog` table capturing `actor_id`, `action`, `entity`, `entity_id`, before/after JSON diffs, IP address, user agent, and timestamp.
  - `apps/audit/middleware.py`: `RequestContextMiddleware` capturing thread-local request metadata (IP, user agent, actor) for automated audit attribution.
  - `apps/audit/services.py`: Dedicated service method `record_audit_event()` for transactional audit writes.

### 6. Leads and Sales App (`apps/leads/`)
- **Task:** Client inquiry intake and cost-calculator lead capture.
- **Status:** Completed.
- **Details:**
  - `apps/leads/models.py`: `Lead` model tracking contact details (encrypted phone/email), company, hiring needs, estimated savings from calculator, status pipeline (`NEW`, `CONTACTED`, `QUALIFIED`, `CONVERTED`, `NURTURING`, `LOST`), and source tracking.

### 7. Candidates App (`apps/candidates/`)
- **Task:** Full candidate profile domain with readiness indexing and anonymized pitch views.
- **Status:** Completed.
- **Details:**
  - `apps/candidates/models.py`: Candidate profiles, skills taxonomy (`Skill`, `CandidateSkill`), work experience, education, healthcare certifications, and anonymized profile view generation for secure client presentation without exposing raw PII.

### 8. Resumes and Ingestion Pipeline (`apps/resumes/`)
- **Task:** Resume document upload, ClamAV antivirus scanning, text extraction, and AI structured parsing.
- **Status:** Completed.
- **Details:**
  - `apps/resumes/models.py`: `ResumeDocument` tracking uploaded files, SHA-256 checksums, and parsing state machine (`QUEUED` -> `SCANNING` -> `EXTRACTING` -> `PARSING` -> `DONE` / `FAILED` / `QUARANTINED`).
  - `apps/resumes/tasks.py`: Celery async pipeline with tasks routed across `files` and `ai` queues, executing antivirus validation, text extraction, and LLM-assisted resume parsing.

### 9. Internal ATS Workspace (`apps/ats/`)
- **Task:** Internal recruitment workspace for Pepoltek recruiters.
- **Status:** Completed.
- **Details:**
  - `apps/ats/models.py`: Internal `Client` management (no client logins in MVP per D-01), `Requisition` (job orders with salary range and requirements), `Application` (5-stage recruitment pipeline: Discovery, Market Mapping, Technical Vetting, Client Interview, Closed), `Submission`, and `Placement`.

### 10. Vetting and Healthcare Credentials (`apps/vetting/`)
- **Task:** Technical assessments and healthcare license verification.
- **Status:** Completed.
- **Details:**
  - `apps/vetting/models.py`: `Assessment` (rubric-scored technical vetting), `Credential` (primary source verification for medical/nursing licenses with issue and expiry tracking).

### 11. Matching Engine (`apps/matching/`)
- **Task:** Candidate-to-job matching scores and pitch authorization.
- **Status:** Completed.
- **Details:**
  - `apps/matching/models.py`: `MatchScore` with vector similarity, structured skill overlap, and weighted scoring breakdown; `PitchAuthorization` logging recruiter-to-candidate pitch approvals.

### 12. Refer and Earn Network (`apps/referrals/`)
- **Task:** Referral tracking and double-entry immutable payout ledger.
- **Status:** Completed.
- **Details:**
  - `apps/referrals/models.py`: `ReferralAttribution` tracking referrer to candidate or client relationships; `ReferralLedgerEntry` maintaining an immutable double-entry financial ledger for pending, approved, and paid referral rewards.

### 13. Notifications App (`apps/notifications/`)
- **Task:** Multi-channel notifications and async email queue.
- **Status:** Completed.
- **Details:**
  - `apps/notifications/models.py`: In-app notification center and user email notification preferences.
  - `apps/notifications/tasks.py`: Asynchronous email delivery via Celery `notify` queue using Django Anymail.

### 14. Talent Academy (`apps/academy/`)
- **Task:** Upskilling courses, modules, and readiness badges.
- **Status:** Completed.
- **Details:**
  - `apps/academy/models.py`: `Course`, `Module`, `Enrollment`, and `Badge` models linked to candidate readiness index.

### 15. AI Service Adapter (`apps/ai_service/`)
- **Task:** Provider-agnostic AI layer with security and PII safeguards.
- **Status:** Completed.
- **Details:**
  - `apps/ai_service/services.py`: Provider adapter wrapping OpenAI and Anthropic with automatic fallback, strict schema validation, PII redaction, and temperature controls.

### 16. Database Migrations Execution and Schema Validation
- **Task:** Generated and verified all app migrations.
- **Status:** Completed.
- **Details:**
  - Initialized `migrations/__init__.py` across all 15 local apps.
  - Successfully generated initial migrations for: `accounts`, `audit`, `candidates`, `config_center`, `notifications`, `resumes`, `vetting`, `ats`, `leads`, `matching`, `referrals`, `cms`, and `academy`.
  - Applied all database migrations cleanly with zero schema or dependency errors.

### 17. Automated Testing Suite and Code Quality Validation
- **Task:** Unit tests, lint verification, and security checks.
- **Status:** Completed.
- **Details:**
  - `apps/core/tests/test_health.py`: Verified `/api/v1/health/` uptime and version inspection endpoint.
  - `apps/accounts/tests/test_auth.py`: Tested user registration, Argon2 password hashing, automated referral code creation, secure httpOnly JWT cookies (`access_token`, `refresh_token`), credential login, and multi-role RBAC authorization.
  - Pytest suite executed: 4 passed with 100% pass rate.
  - Ruff linter executed: all checks passed with zero lint errors.

### 18. Domain Integration Tests and Lifecycle Validation
- **Task:** End-to-end tests for all core business entities and workflows.
- **Status:** Completed.
- **Details:**
  - `apps/core/tests/test_domain_flows.py`:
    - `BaseModel`: Verified UUIDv7 primary keys, UTC timestamps, soft-deletion via `archive()`, and default manager exclusion.
    - `Candidate` & `SkillTaxonomy`: Verified encrypted PII fields and skill proficiency linkage.
    - `ATS Pipeline`: Verified `Client`, `Requisition`, and `Application` 5-stage progression (Discovery -> Technical Vetting -> Client Interview).
    - `Lead Capture`: Verified cost-calculator snapshot storage and attribution.
    - `ConfigCenter`: Verified versioned publishing (`v1` -> `v2`), history preservation, and active version query.
    - `Referrals & Ledger`: Verified referral attribution and double-entry immutable financial ledger.

### 19. Frontend Architecture Upgrade and Canonical SRS Route Alignment
- **Task:** Upgraded Next.js App Router architecture and route hierarchy according to Technical SRS v2.1 while preserving all existing styling, components, and dashboard interfaces.
- **Status:** Completed and Verified.
- **Details:**
  - **Route Groups Reorganization:**
    - Segregated application into three canonical route groups: `src/app/(public)`, `src/app/(candidate)`, and `src/app/(workspace)`.
  - **Canonical Public Routes Implemented:**
    - `/` (Homepage): Preserved all existing hero, metrics, and solution components.
    - `/about` (`src/app/(public)/about/page.jsx`): Comprehensive 6-stage talent delivery engine overview, peer technical vetting, verified credentialing, and company metrics. Added permanent 301 redirect from legacy `/about-us`.
    - `/hire` (`src/app/(public)/hire/page.jsx`): Dual-track intake for tech and healthcare, headcount selector, engagement model picker, and instant 20-minute discovery consultation booking integration (SRS M3, LEAD-01, LEAD-02).
    - `/calculator` (`src/app/(public)/calculator/page.jsx`): Interactive Hiring Velocity and Cost Savings Calculator with debounced inputs and estimate disclaimers.
    - `/case-studies` and `/case-studies/[slug]` (`src/app/(public)/case-studies/`): Sector-filterable case studies with verified proof metrics, client quotes, and enterprise requisition CTAs (SRS M1, WEB-07).
    - `/technology/[slug]` (`src/app/(public)/technology/[slug]/`): Dedicated track practice pages covering Cloud & DevOps, Full-Stack Python, AI/ML Engineering, Cybersecurity, and Data Engineering.
    - `/healthcare/[slug]` (`src/app/(public)/healthcare/[slug]/`): Dedicated clinical practice pages covering Travel Nursing, Critical Care Specialists, Allied Health, Health Informatics, and Physician Locums.
    - `/ecosystem/refer-and-earn` (`src/app/(public)/ecosystem/refer-and-earn/page.jsx`): Referral program hub with personal link generator, live bounty ledger, and transparent pipeline tracker (SRS M9).
    - `/ecosystem/academy` (`src/app/(public)/ecosystem/academy/page.jsx`): Talent academy certification tracks and role readiness index boosters (SRS M10).
    - `/r/[code]` (`src/app/(public)/r/[code]/page.jsx`): Referral landing page that automatically configures a 90-day attribution cookie and fast-tracks candidate intake.
    - `/services` and `/services/[slug]` (`src/app/(public)/services/[slug]/`): Prerendered dynamic services engine with full process flow and inquiry booking.
  - **Canonical Candidate Routes Implemented:**
    - `/careers/dashboard` (`src/app/(candidate)/careers/dashboard/page.jsx`): Candidate ecosystem portal with profile readiness score, application pipeline tracker, and anonymous pitch authorization toggles (SRS M4).
    - `/careers/upload-cv` (`src/app/(candidate)/careers/upload-cv/page.jsx`): Multi-step resume intake engine with permanent redirect from legacy `/career/upload_cv/`.
    - `/careers/jobs`, `/careers/jobs/[id]`, and `/careers/jobs/[id]/apply`: Full job board, job details, and direct application workflows with backwards-compatible `/career/jobs` support.
    - `/careers/reverse-search` (`src/app/(candidate)/careers/reverse-search/page.jsx`): Reverse job search allowing candidates to specify target compensation and scan confidential employer requisitions (SRS M8).
  - **Workspace ATS Routing and Aliasing:**
    - Configured Next.js rewrites in `next.config.mjs` mapping `/workspace/*` directly to `/dashboard/*` so internal ATS recruiter workflows function under both URLs seamlessly.
  - **API Client and Cookie Security:**
    - Created `src/lib/api.js` configured with `credentials: "include"`, automatic Django CSRF token handling, and typed domain helpers (`authApi`, `leadsApi`, `candidatesApi`, `resumesApi`, `jobsApi`, `matchingApi`, `referralsApi`, `academyApi`).
  - **Middleware Upgrades:**
    - Updated `src/middleware.js` to guard `/dashboard/:path*` and `/workspace/:path*`, querying the Django backend `/api/v1/auth/me` endpoint using secure httpOnly cookies.
  - **Code Quality and Build Verification:**
    - Stripped all em dashes across the frontend codebase to strictly maintain the House Style Rule.
    - Resolved React hook order violation in `EditContactForm.js`.
    - Executed `npm run lint`: **Passed cleanly with 0 errors**.
    - Executed `npm run build`: **Generated 88/88 static and dynamic routes cleanly with zero compilation errors**.

### 20. Model-Aligned Dynamic UI Integration and Zero Backend Model Mutations
- **Task:** Upgraded all frontend interfaces to be dynamic using Server Actions and Zustand state while keeping backend models 100% frozen and aligning UI static choices to match model definitions within identical designs.
- **Status:** Completed and Verified.
- **Details:**
  - **Zero Backend Model Mutation Invariant:**
    - Zero modifications, alterations, or migrations to Django models (`apps/*/models.py`). All models remain strictly frozen.
  - **Backend API Layer Additions (Zero Model Schema Changes):**
    - `apps/leads/`: Serializers and views (`LeadCreateView`, `LeadBookingView`) mapping directly to `Lead` model fields (`contact_name`, `work_email`, `sector`, `headcount`, `engagement_model`, `booking_data`).
    - `apps/config_center/`: `CalculatorConfigView` and `CalculatorEstimateView` providing ruleset versioning and instant cost savings modeling.
    - `apps/ats/`: `PublicJobsListView`, `PublicJobDetailView`, and `PublicJobApplyView` servicing public requisitions, filters, and candidate applications.
    - `apps/candidates/`: `CandidateMeView`, `CandidateApplicationsView`, `CandidatePitchToggleView`, and `CandidateIntakeView` with `CandidateIntakeSerializer` for multipart CV ingestion.
    - `apps/matching/`: `ReverseSearchView` and `PitchSubmissionView` supporting confidential candidate reverse requisition scanning.
    - `apps/referrals/`: `ReferralSummaryView` and `ReferralTrackView` returning transparent bounty stats and attribution.
    - `apps/academy/`: `AcademyCoursesListView` and `AcademyEnrollView` powering talent readiness track enrollment.
    - `apps/cms/`: `CaseStudiesListView` and `CaseStudyDetailView` delivering verified proof studies.
  - **Next.js Server Actions Layer (`src/actions/`):**
    - Built type-safe, error-handled Server Actions: `leads.js`, `calculator.js`, `jobs.js`, `candidate.js`, `reverseSearch.js`, `referrals.js`, `academy.js`, and `caseStudies.js`.
  - **Zustand Reactive State Stores (`src/stores/`):**
    - Implemented clean client state stores: `hireFormStore.js`, `calculatorStore.js`, `jobFilterStore.js`, `candidateDashboardStore.js`, and `reverseSearchStore.js`.
  - **Model-Aligned UI Static Content & Choices (Identical Design):**
    - `UploadCvForm.jsx` (`/careers/upload-cv`): Upgraded to Server Actions via `submitCandidateIntake`, with dropdown choices mapped to `SectorChoice` (`technology`, `healthcare`), `ExperienceLevel` (`junior`, `mid`, `senior`, `lead`, `director`, `c_level`), `WorkAuth` (`us_citizen`, `green_card`, `h1b`, `opt`, `international_remote`), and `EngagementType` (`direct_hire`, `w2`, `c2c`, `1099`) while preserving 100% of the UI design, CSS styling, and step flow.
    - `HireFormClient.jsx` (`/hire`): Aligned sector to `technology`/`healthcare` and engagement models to `staff_aug`, `direct_hire`, `eor`, and `executive`.
    - `JobListClient.jsx` (`/careers/jobs`): Aligned sector filter tab values directly to `technology` and `healthcare`.
    - `CalculatorClient.jsx` (`/calculator`): Aligned practice tracks to `technology` and `healthcare`.
    - `ReverseSearchClient.jsx` (`/careers/reverse-search`): Aligned sector criteria to model choices.
  - **Verification:**
    - Pytest suite: **10/10 passed in 7.11s**.
    - Next.js lint: **Passed with 0 errors**.
    - Next.js build: **88/88 static and dynamic routes compiled cleanly**.
    - House style rule: **Zero em dashes across frontend and backend**.

