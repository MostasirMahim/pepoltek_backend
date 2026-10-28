from .base import *  # noqa

_env = environ.Env()

DEBUG = _env.bool('DEBUG', default=False)

# SSL & Security: default to False on HTTP / bare-IP deployments, True when SSL is active
SECURE_SSL_REDIRECT = _env.bool('SECURE_SSL_REDIRECT', default=False)
SESSION_COOKIE_SECURE = _env.bool('SESSION_COOKIE_SECURE', default=SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = _env.bool('CSRF_COOKIE_SECURE', default=SECURE_SSL_REDIRECT)

if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = _env.int('SECURE_HSTS_SECONDS', default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
    SECURE_HSTS_PRELOAD = _env.bool('SECURE_HSTS_PRELOAD', default=True)
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# File Storage: Gracefully fallback to FileSystemStorage if S3 is not enabled
USE_S3 = _env.bool('USE_S3', default=False)
if USE_S3:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
else:
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Sentry (only init if DSN provided and library installed)
_sentry_dsn = _env('SENTRY_DSN', default='')
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
    except ImportError:
        pass
