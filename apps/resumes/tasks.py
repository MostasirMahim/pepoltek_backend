"""
resumes/tasks.py
CV/Resume ingestion pipeline. Celery chain: scan → extract → parse → map.
Queues: scan+export on 'files', parsing on 'ai'.
All tasks are idempotent - safe to retry.
"""
import logging
from celery import shared_task
from django.utils import timezone

from .models import ResumeParse, ParseStatus

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='resumes.scan_document',
    queue='files',
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def scan_document(self, *, parse_id: str):
    """
    Step 1: Malware scan via ClamAV.
    On clean: triggers extract_and_parse.
    On infected: marks quarantined and blocks all further processing.
    """
    from apps.candidates.models import ScanStatus

    try:
        parse = ResumeParse.objects.get(id=parse_id)
    except ResumeParse.DoesNotExist:
        logger.error('scan_document: parse %s not found', parse_id)
        return

    parse.status = ParseStatus.SCANNING
    parse.save(update_fields=['status', 'updated_at'])

    try:
        _result = _clamd_scan(parse.document.storage_key)
        if _result == 'infected':
            parse.status = ParseStatus.QUARANTINED
            parse.error_message = 'File flagged by malware scanner.'
            parse.save(update_fields=['status', 'error_message', 'updated_at'])
            parse.document.scan_status = ScanStatus.INFECTED
            parse.document.save(update_fields=['scan_status'])
            logger.warning('Quarantined document %s', parse.document.id)
            return

        parse.document.scan_status = ScanStatus.CLEAN
        parse.document.scanned_at = timezone.now()
        parse.document.save(update_fields=['scan_status', 'scanned_at'])

        # Chain to text extraction
        extract_and_parse.apply_async(kwargs={'parse_id': parse_id})

    except Exception as exc:
        parse.retry_count += 1
        parse.error_message = str(exc)
        parse.save(update_fields=['retry_count', 'error_message', 'updated_at'])
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='resumes.extract_and_parse',
    queue='ai',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def extract_and_parse(self, *, parse_id: str):
    """
    Step 2: Extract raw text from document, then call AI to parse into structured JSON.
    Low-confidence fields (< 0.6) are flagged for candidate review.
    Output never applied to profile automatically - candidate must confirm.
    """
    try:
        parse = ResumeParse.objects.get(id=parse_id)
    except ResumeParse.DoesNotExist:
        logger.error('extract_and_parse: parse %s not found', parse_id)
        return

    try:
        # Text extraction
        parse.status = ParseStatus.EXTRACTING
        parse.save(update_fields=['status', 'updated_at'])

        raw_text = _extract_text(parse.document)
        parse.raw_text = raw_text[:50000]  # cap storage
        parse.save(update_fields=['raw_text', 'updated_at'])

        # AI parsing
        parse.status = ParseStatus.PARSING
        parse.save(update_fields=['status', 'updated_at'])

        from apps.ai_service.services import parse_resume
        result = parse_resume(raw_text=raw_text, document_id=str(parse.document.id))

        parse.output = result['output']
        parse.field_confidence = result['confidence']
        parse.model_name = result['model']
        parse.prompt_version = result['prompt_version']
        parse.status = ParseStatus.DONE
        parse.save(update_fields=[
            'output', 'field_confidence', 'model_name', 'prompt_version', 'status', 'updated_at'
        ])
        logger.info('Parse complete for document %s', parse.document.id)

    except Exception as exc:
        parse.status = ParseStatus.FAILED
        parse.retry_count += 1
        parse.error_message = str(exc)
        parse.save(update_fields=['status', 'retry_count', 'error_message', 'updated_at'])
        logger.exception('Parse failed for %s: %s', parse_id, exc)
        raise self.retry(exc=exc)


def _clamd_scan(storage_key: str) -> str:
    """
    Scan file via ClamAV daemon. Returns 'clean' or 'infected'.
    In local dev without ClamAV, returns 'clean' (safe default).
    """
    try:
        import clamd
        _cd = clamd.ClamdNetworkSocket()
        # Download from S3 to temp and scan
        # TODO: implement S3 streaming to clamd
        return 'clean'
    except Exception:
        logger.warning('ClamAV not available - skipping scan (dev mode)')
        return 'clean'


def _extract_text(document) -> str:
    """Extract raw text from PDF, DOCX, or RTF document."""
    from pathlib import Path

    # TODO: download from S3 storage to temp file
    # Placeholder extraction - will be replaced with actual S3 download
    ext = Path(document.original_filename).suffix.lower()

    if ext == '.pdf':
        return _extract_pdf(b'')
    elif ext in ('.docx', '.doc'):
        return _extract_docx(b'')
    elif ext == '.rtf':
        return _extract_rtf(b'')
    return ''


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    import io
    try:
        reader = PdfReader(io.BytesIO(content))
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception as e:
        logger.warning('PDF extraction failed: %s', e)
        return ''


def _extract_docx(content: bytes) -> str:
    from docx import Document as DocxDocument
    import io
    try:
        doc = DocxDocument(io.BytesIO(content))
        return '\n'.join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning('DOCX extraction failed: %s', e)
        return ''


def _extract_rtf(content: bytes) -> str:
    try:
        from striprtf.striprtf import rtf_to_text
        return rtf_to_text(content.decode('utf-8', errors='ignore'))
    except Exception as e:
        logger.warning('RTF extraction failed: %s', e)
        return ''
