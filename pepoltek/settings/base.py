"""
Django settings - base (shared across all environments).
Split: base → dev / staging / prod imports and override.
"""
from pathlib import Path
from datetime import timedelta
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_env_file = BASE_DIR / env('ENV_FILE', default='.env')
if not _env_file.exists() and (BASE_DIR / '.env.production').exists():
    _env_file = BASE_DIR / '.env.production'
if _env_file.exists():
    environ.Env.read_env(_env_file, overwrite=False)

# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

AUTH_USER_MODEL = 'accounts.User'

# ─── Installed Apps ───────────────────────────────────────────────────────────
DJANGO_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'corsheaders',
    'django_filters',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.linkedin_oauth2',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'auditlog',
    'axes',
    'django_celery_beat',
    'django_celery_results',
    'storages',
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail',
    'modelcluster',
    'taggit',
]

LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.audit',
    'apps.config_center',
    'apps.cms',
    'apps.leads',
    'apps.candidates',
    'apps.resumes',
    'apps.ats',
    'apps.vetting',
    'apps.matching',
    'apps.referrals',
    'apps.academy',
    'apps.notifications',
    'apps.ai_service',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

SITE_ID = 1

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'apps.audit.middleware.RequestContextMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'pepoltek.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pepoltek.wsgi.application'

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    'default': env.db('DATABASE_URL'),
}
if 'postgresql' in DATABASES['default'].get('ENGINE', ''):
    DATABASES['default']['OPTIONS'] = {
        'connect_timeout': 10,
    }

# ─── Password Hashing ─────────────────────────────────────────────────────────
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 4}},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─── Static & Media ───────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Cache (Redis) ────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True

# Queue routing - separate slow AI from fast notify
CELERY_TASK_ROUTES = {
    'apps.resumes.tasks.*': {'queue': 'files'},
    'apps.matching.tasks.*': {'queue': 'ai'},
    'apps.notifications.tasks.*': {'queue': 'notify'},
    'apps.leads.tasks.*': {'queue': 'notify'},
    'apps.ai_service.tasks.*': {'queue': 'ai'},
}

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.accounts.authentication.CookieJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'login': '10/min',
        'leads': '5/hour',
        'calculator': '60/min',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ─── SimpleJWT ────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_REFRESH': 'refresh_token',
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_SECURE': env.bool('AUTH_COOKIE_SECURE', default=env.bool('SECURE_SSL_REDIRECT', default=False)),
    'AUTH_COOKIE_SAMESITE': 'Lax',
}

# ─── drf-spectacular ─────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'Pepoltek API',
    'DESCRIPTION': 'Workforce platform API - AI-assisted recruitment, candidate matching, and referral network.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['apps.accounts.permissions.IsStaff'],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/v1/',
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'authorization', 'content-type', 'x-csrftoken', 'x-requested-with', 'idempotency-key',
]

CSRF_COOKIE_HTTPONLY = False  # Frontend must read CSRF token
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000']))

# ─── Allauth ─────────────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'

# ─── Axes (brute-force protection) ───────────────────────────────────────────
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']

# ─── Field Encryption ─────────────────────────────────────────────────────────
_raw_encryption_key = env('FIELD_ENCRYPTION_KEY', default='RV_NauDPp_PmhYT7ro6P6E18eNL8Jt4ze48yg9HrpsY=')
try:
    from cryptography.fernet import Fernet
    Fernet(_raw_encryption_key)
    FIELD_ENCRYPTION_KEY = _raw_encryption_key
except Exception:
    FIELD_ENCRYPTION_KEY = 'RV_NauDPp_PmhYT7ro6P6E18eNL8Jt4ze48yg9HrpsY='

# ─── File Storage ─────────────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='pepoltek-media')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='us-east-1')
AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL', default=None)
AWS_DEFAULT_ACL = 'private'
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 300  # 5-minute pre-signed URL expiry

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_USER', default=env('EMAIL_HOST_USER', default=''))
EMAIL_HOST_PASSWORD = env('EMAIL_PASS', default=env('EMAIL_HOST_PASSWORD', default=''))
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=f"Pepoltek Platform <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else 'noreply@pepoltek.com')
SERVER_EMAIL = EMAIL_HOST_USER or 'errors@pepoltek.com'

# ─── Google OAuth Configuration ───────────────────────────────────────────────
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_CALLBACK_URL = env('GOOGLE_CALLBACK_URL', default='http://localhost:8000/api/v1/auth/google/callback')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': GOOGLE_CLIENT_ID,
            'secret': GOOGLE_CLIENT_SECRET,
            'key': '',
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'VERIFIED_EMAIL': True,
    }
}

# ─── Wagtail ─────────────────────────────────────────────────────────────────
WAGTAIL_SITE_NAME = 'Pepoltek'
WAGTAILAPI_LIMIT_MAX = 100
WAGTAIL_FRONTEND_LOGIN_URL = '/careers/login/'
WAGTAILIMAGES_IMAGE_MODEL = 'cms.CustomImage'
WAGTAILADMIN_BASE_URL = 'http://localhost:8000'

# ─── Frontend ─────────────────────────────────────────────────────────────────
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')
ISR_REVALIDATE_SECRET = env('ISR_REVALIDATE_SECRET', default='')

# ─── AI Providers & Failover Ranking ──────────────────────────────────────────
AI_PROVIDER = env('AI_PROVIDER', default='auto')
AI_PROVIDER_PRIORITY = env('AI_PROVIDER_PRIORITY', default='gemini,groq,deepseek,qwen,openai,anthropic,ollama,local_nlp')
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GROQ_API_KEY = env('GROQ_API_KEY', default='')
DEEPSEEK_API_KEY = env('DEEPSEEK_API_KEY', default='')
QWEN_API_KEY = env('QWEN_API_KEY', default='')
OPENAI_API_KEY = env('OPENAI_API_KEY', default='')
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='')
OLLAMA_BASE_URL = env('OLLAMA_BASE_URL', default='http://localhost:11434/v1')
AI_PARSE_CONFIDENCE_THRESHOLD = 0.6
AI_REQUEST_TIMEOUT = 30


# ─── Logging ─────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'logging.Formatter',
            'fmt': '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        },
        'simple': {'format': '[%(levelname)s] %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'apps': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
