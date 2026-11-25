"""
Django settings for SellBundle project.

Configured for Ghana Mobile Data Bundle Reselling Platform.
Uses decouple for environment-based configuration (.env).
"""

from pathlib import Path
from decouple import config, Csv

# Build paths inside the project: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------------------
# CORE SECURITY SETTINGS
# ------------------------------------------------------------------------------
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-sellbundle-local-dev-key-change-in-production'
)

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = ["*"] 

# config(
#     'ALLOWED_HOSTS',
#     default='localhost,127.0.0.1,testserver',
#     cast=Csv()
# )

# ------------------------------------------------------------------------------
# APPLICATION DEFINITION
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.bundles',
    'apps.orders',
    'apps.payments',
    'apps.dashboard',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ------------------------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Needs to be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sellbundle.urls'

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

WSGI_APPLICATION = 'sellbundle.wsgi.application'
ASGI_APPLICATION = 'sellbundle.asgi.application'

# ------------------------------------------------------------------------------
# DATABASE CONFIGURATION (PostgreSQL / Railway / SQLite fallback)
# ------------------------------------------------------------------------------
DATABASE_URL = config('DATABASE_URL', default='').strip()
USE_POSTGRESQL = config('USE_POSTGRESQL', default=False, cast=bool)

if DATABASE_URL:
    # Production / Railway automated connection URL
    from urllib.parse import urlparse, unquote, parse_qs
    _url = urlparse(DATABASE_URL)
    _qs = parse_qs(_url.query)
    _options = {}
    if 'sslmode' in _qs:
        _options['sslmode'] = _qs['sslmode'][0]

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _url.path.lstrip('/'),
            'USER': unquote(_url.username or ''),
            'PASSWORD': unquote(_url.password or ''),
            'HOST': _url.hostname or '',
            'PORT': str(_url.port or 5432),
            'CONN_MAX_AGE': 600,
            'OPTIONS': _options,
        }
    }
elif USE_POSTGRESQL:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default=''),
            'USER': config('DB_USER', default=''),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default=''),
            'PORT': config('DB_PORT', default=''),
            'CONN_MAX_AGE': 600,
        }
    }
else:
    # Instant local development fallback
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ------------------------------------------------------------------------------
# DJANGO REST FRAMEWORK CONFIGURATION
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/minute',
        'user': '1000/minute',
        'orders': '10/minute',
        'payments': '20/minute',
    },
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%SZ',
}

# ------------------------------------------------------------------------------
# CORS (CROSS-ORIGIN RESOURCE SHARING)
# ------------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000',
    cast=Csv()
)
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173,https://*.railway.app,https://*.up.railway.app',
    cast=Csv()
)

# Trust reverse proxy SSL termination in production (Railway, Render, AWS, Heroku, Nginx)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ------------------------------------------------------------------------------
# PASSWORD VALIDATION
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------------------------------------------------------------------
# INTERNATIONALIZATION & TIMEZONE (Ghana: Africa/Accra)
# ------------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Accra'
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------------------
# STATIC & MEDIA FILES
# ------------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------------------------
# CELERY & REDIS CONFIGURATION
# ------------------------------------------------------------------------------
_default_redis = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=_default_redis)
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=_default_redis)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 120  # 2 minutes max per task
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=True, cast=bool)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'socket_timeout': 2.0,
    'socket_connect_timeout': 2.0,
}

# ------------------------------------------------------------------------------
# PAYSTACK INTEGRATION SETTINGS
# ------------------------------------------------------------------------------
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_WEBHOOK_SECRET = config('PAYSTACK_WEBHOOK_SECRET', default='')
PAYSTACK_BASE_URL = 'https://api.paystack.co'

# ------------------------------------------------------------------------------
# VENDOR / AGGREGATOR API SETTINGS
# ------------------------------------------------------------------------------
VENDOR_BASE_URL = config('VENDOR_BASE_URL', default='')
VENDOR_API_KEY = config('VENDOR_API_KEY', default='')
VENDOR_API_SECRET = config('VENDOR_API_SECRET', default='')

# ------------------------------------------------------------------------------
# GHANA SMS GATEWAY CONFIGURATION (Arkesel / mNotify / Hubtel)
# ------------------------------------------------------------------------------
SMS_ENABLED = config('SMS_ENABLED', default=True, cast=bool)
SMS_PROVIDER = config('SMS_PROVIDER', default='arkesel').lower()
SMS_SENDER_ID = config('SMS_SENDER_ID', default='SellBundle')
ARKESEL_API_KEY = config('ARKESEL_API_KEY', default='')
MNOTIFY_API_KEY = config('MNOTIFY_API_KEY', default='')
HUBTEL_CLIENT_ID = config('HUBTEL_CLIENT_ID', default='')
HUBTEL_CLIENT_SECRET = config('HUBTEL_CLIENT_SECRET', default='')

# ------------------------------------------------------------------------------
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ------------------------------------------------------------------------------
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Check every 10 minutes for stuck orders and re-queue delivery
    'check-stuck-orders-every-10-minutes': {
        'task': 'apps.orders.tasks.check_stuck_orders',
        'schedule': crontab(minute='*/10'),
    },
}

