import sys
from .base import *  # noqa

DEBUG = True

# Disable security headers in dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Allow all CORS in dev
CORS_ALLOW_ALL_ORIGINS = True

# Django Debug Toolbar
INSTALLED_APPS += ['debug_toolbar', 'silk']  # noqa
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware', 'silk.middleware.SilkyMiddleware'] + MIDDLEWARE  # noqa
INTERNAL_IPS = ['127.0.0.1', 'localhost']
TESTING = 'pytest' in sys.modules or 'test' in sys.argv
DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': lambda r: DEBUG and not TESTING}

USE_SQLITE = env.bool('USE_SQLITE', default=True)  # Set USE_SQLITE=False in .env when local PostgreSQL is configured

if USE_SQLITE or TESTING:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / ('test_db.sqlite3' if TESTING else 'dev_db.sqlite3'),  # noqa
        }
    }


# Local file storage (override to use local FS in dev if MinIO not running)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Email backend configuration (defaults to Gmail SMTP if EMAIL_HOST_USER provided, otherwise Mailpit)
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
else:
    EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST = env('EMAIL_HOST', default='localhost')
    EMAIL_PORT = env.int('EMAIL_PORT', default=1025)

# Development throttle rates (relaxed for local development & automated test suites)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '100000/day',
    'user': '100000/day',
    'login': '1000/min',
    'leads': '1000/hour',
    'calculator': '1000/min',
}


