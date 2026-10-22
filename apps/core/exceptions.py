"""
core/exceptions.py
Uniform error envelope for all API responses.
Format: { "error": { "code": str, "message": str, "fields": {...} } }
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Transforms all DRF exceptions into a uniform error envelope.
    Non-DRF exceptions bubble up to Sentry via standard Django error handling.
    """
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception - log and return 500
        logger.exception('Unhandled exception in %s', context.get('view'))
        return Response(
            {'error': {'code': 'INTERNAL_ERROR', 'message': 'An unexpected error occurred.'}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Map DRF response to our envelope
    error_code = _status_to_code(response.status_code)
    message = _extract_message(response.data)
    fields = _extract_fields(response.data)

    payload = {'error': {'code': error_code, 'message': message}}
    if fields:
        payload['error']['fields'] = fields

    response.data = payload
    return response


def _status_to_code(http_status: int) -> str:
    mapping = {
        400: 'VALIDATION_FAILED',
        401: 'AUTHENTICATION_REQUIRED',
        403: 'PERMISSION_DENIED',
        404: 'NOT_FOUND',
        405: 'METHOD_NOT_ALLOWED',
        409: 'CONFLICT',
        422: 'UNPROCESSABLE',
        429: 'RATE_LIMITED',
        500: 'INTERNAL_ERROR',
    }
    return mapping.get(http_status, f'HTTP_{http_status}')


def _extract_message(data) -> str:
    if isinstance(data, dict):
        for key in ('detail', 'message', 'non_field_errors'):
            if key in data:
                val = data[key]
                return str(val[0]) if isinstance(val, list) else str(val)
        # Extract the first specific field error message
        for key, val in data.items():
            if key not in ('detail', 'message', 'non_field_errors', 'code'):
                field_label = key.replace('_', ' ').capitalize()
                if isinstance(val, list) and val:
                    return f"{field_label}: {val[0]}"
                elif isinstance(val, str):
                    return f"{field_label}: {val}"
        return 'Invalid request.'
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)


def _extract_fields(data) -> dict | None:
    if not isinstance(data, dict):
        return None
    skip = {'detail', 'message', 'non_field_errors', 'code'}
    fields = {k: ([str(v) for v in val] if isinstance(val, list) else [str(val)])
              for k, val in data.items() if k not in skip}
    return fields or None
