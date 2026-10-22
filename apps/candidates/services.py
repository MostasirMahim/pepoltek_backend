"""
candidates/services.py
Business logic, mutations, transactions, and audit records for candidate domain.
Views call these services; services own transaction.atomic() and audit logs.
"""
import hashlib
from django.db import transaction
from django.utils import timezone
from .models import (
    Candidate,
    CandidateSkill,
    Document,
    DocumentType,
    ScanStatus,
    SkillTaxonomy,
)
from apps.vetting.models import Credential, CredentialStatus
from apps.audit.services import record as record_audit
from apps.audit.models import AuditLog


def update_candidate_profile(
    *,
    candidate: Candidate,
    data: dict,
    user,
    request=None,
) -> Candidate:
    """
    Update candidate profile details, recalculate telemetry, and write audit event.
    """
    before_state = {
        'full_name': candidate.full_name,
        'sector': candidate.sector,
        'domain': candidate.domain,
        'level': candidate.level,
        'location': candidate.location,
        'desired_hourly_rate': candidate.desired_hourly_rate,
        'open_to_work': candidate.open_to_work,
    }

    updatable_fields = [
        'full_name',
        'phone',
        'sector',
        'domain',
        'level',
        'location',
        'timezone',
        'work_auth',
        'engagement_prefs',
        'desired_hourly_rate',
        'portfolio_url',
        'github_url',
        'linkedin_url',
        'bio',
        'open_to_work',
        'availability_date',
    ]

    with transaction.atomic():
        for field in updatable_fields:
            if field in data:
                setattr(candidate, field, data[field])

        # Handle skills cache if provided
        if 'skills' in data and isinstance(data['skills'], list):
            candidate.skills_cache = [s.strip() for s in data['skills'] if str(s).strip()]

        candidate.save()

        # Write audit event
        record_audit(
            action=AuditLog.Action.UPDATE,
            entity='Candidate',
            entity_id=str(candidate.id),
            actor=user,
            before=before_state,
            after={
                'full_name': candidate.full_name,
                'sector': candidate.sector,
                'domain': candidate.domain,
                'level': candidate.level,
                'location': candidate.location,
                'desired_hourly_rate': candidate.desired_hourly_rate,
                'open_to_work': candidate.open_to_work,
            },
            request=request,
        )

    return candidate


def create_candidate_credential(
    *,
    candidate: Candidate,
    data: dict,
    user,
    request=None,
) -> Credential:
    """
    Create a new healthcare professional license or certification credential (SRS CAN-04, VET-04).
    """
    with transaction.atomic():
        credential = Credential.objects.create(
            candidate=candidate,
            kind=data.get('kind', Credential.Kind.LICENSE),
            name=data['name'].strip(),
            license_number=data.get('license_number', '').strip(),
            jurisdiction=data.get('jurisdiction', '').strip(),
            issued_on=data.get('issued_on') or None,
            expires_on=data.get('expires_on') or None,
            status=CredentialStatus.UNVERIFIED,
        )

        record_audit(
            action=AuditLog.Action.CREATE,
            entity='Credential',
            entity_id=str(credential.id),
            actor=user,
            after={
                'name': credential.name,
                'kind': credential.kind,
                'jurisdiction': credential.jurisdiction,
                'status': credential.status,
            },
            request=request,
        )

    return credential


def delete_candidate_credential(
    *,
    candidate: Candidate,
    credential_id,
    user,
    request=None,
) -> bool:
    """
    Delete a candidate credential.
    """
    credential = Credential.objects.filter(candidate=candidate, id=credential_id).first()
    if not credential:
        return False

    with transaction.atomic():
        cred_name = credential.name
        credential.delete()

        record_audit(
            action=AuditLog.Action.DELETE,
            entity='Credential',
            entity_id=str(credential_id),
            actor=user,
            before={'name': cred_name},
            request=request,
        )

    return True


def create_candidate_document(
    *,
    candidate: Candidate,
    file_obj,
    doc_type: str = DocumentType.RESUME,
    user,
    request=None,
) -> Document:
    """
    Process and record a candidate file upload (SRS CAN-09, PAR-01).
    """
    content = file_obj.read()
    file_hash = hashlib.sha256(content).hexdigest()
    storage_key = f'resumes/{candidate.id}/{file_obj.name}'

    with transaction.atomic():
        doc = Document.objects.create(
            candidate=candidate,
            doc_type=doc_type,
            storage_key=storage_key,
            original_filename=file_obj.name,
            mime_type=file_obj.content_type or 'application/octet-stream',
            size_bytes=file_obj.size,
            sha256=file_hash,
            scan_status=ScanStatus.CLEAN,
        )

        record_audit(
            action=AuditLog.Action.UPLOAD,
            entity='Document',
            entity_id=str(doc.id),
            actor=user,
            after={
                'filename': doc.original_filename,
                'doc_type': doc.doc_type,
                'size': doc.size_bytes,
            },
            request=request,
        )

    return doc


def delete_candidate_document(
    *,
    candidate: Candidate,
    document_id,
    user,
    request=None,
) -> bool:
    """
    Delete a candidate document.
    """
    doc = Document.objects.filter(candidate=candidate, id=document_id).first()
    if not doc:
        return False

    with transaction.atomic():
        filename = doc.original_filename
        doc.delete()

        record_audit(
            action=AuditLog.Action.DELETE,
            entity='Document',
            entity_id=str(document_id),
            actor=user,
            before={'filename': filename},
            request=request,
        )

    return True


def toggle_open_to_work(
    *,
    candidate: Candidate,
    open_to_work: bool,
    user,
    request=None,
) -> Candidate:
    """
    Toggle candidate open to work and pitch authorization status.
    """
    with transaction.atomic():
        candidate.open_to_work = bool(open_to_work)
        candidate.save(update_fields=['open_to_work', 'updated_at'])

        action_type = AuditLog.Action.PITCH_AUTHORIZED if open_to_work else AuditLog.Action.PITCH_REVOKED
        record_audit(
            action=action_type,
            entity='Candidate',
            entity_id=str(candidate.id),
            actor=user,
            after={'open_to_work': candidate.open_to_work},
            request=request,
        )

    return candidate


def export_candidate_data(
    *,
    candidate: Candidate,
    user,
    request=None,
) -> dict:
    """
    Compile complete GDPR export payload of candidate data (SRS CAN-09).
    """
    record_audit(
        action=AuditLog.Action.DATA_EXPORT,
        entity='Candidate',
        entity_id=str(candidate.id),
        actor=user,
        request=request,
    )

    credentials = [
        {
            'name': c.name,
            'kind': c.kind,
            'jurisdiction': c.jurisdiction,
            'status': c.status,
            'expires_on': str(c.expires_on) if c.expires_on else None,
        }
        for c in candidate.credentials.all()
    ]

    documents = [
        {
            'filename': d.original_filename,
            'doc_type': d.doc_type,
            'size_bytes': d.size_bytes,
            'uploaded_at': d.created_at.isoformat(),
        }
        for d in candidate.documents.all()
    ]

    return {
        'profile': {
            'id': str(candidate.id),
            'email': candidate.user.email,
            'full_name': candidate.full_name,
            'phone': candidate.phone,
            'sector': candidate.sector,
            'domain': candidate.domain,
            'level': candidate.level,
            'location': candidate.location,
            'desired_hourly_rate': candidate.desired_hourly_rate,
            'work_auth': candidate.work_auth,
            'skills': candidate.skills_cache,
            'bio': candidate.bio,
            'created_at': candidate.created_at.isoformat(),
        },
        'credentials': credentials,
        'documents': documents,
        'exported_at': timezone.now().isoformat(),
    }


def request_candidate_deletion(
    *,
    candidate: Candidate,
    reason: str,
    user,
    request=None,
) -> dict:
    """
    Submit account deletion request under GDPR right to erasure (SRS CAN-09).
    """
    with transaction.atomic():
        candidate.deletion_requested_at = timezone.now()
        candidate.deletion_reason = reason.strip()
        candidate.open_to_work = False
        candidate.save(update_fields=['deletion_requested_at', 'deletion_reason', 'open_to_work', 'updated_at'])

        record_audit(
            action=AuditLog.Action.DELETE_REQUEST,
            entity='Candidate',
            entity_id=str(candidate.id),
            actor=user,
            extra={'reason': reason},
            request=request,
        )

    return {
        'candidate_id': str(candidate.id),
        'deletion_requested_at': candidate.deletion_requested_at.isoformat(),
        'status': 'pending_processing',
        'message': 'Account deletion request recorded. Our compliance officer will process your data removal within 30 days.',
    }
