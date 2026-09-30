import os
from pathlib import Path
import urllib.parse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'unsafe-dev-secret-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'channels',
    
    # Local Apps
    'apps.tenants',
    'apps.users',
    'apps.conversations',
    'apps.messages.apps.MessagesConfig',
    'apps.exports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
AUTH_USER_MODEL = 'users.User'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
db_url = os.environ.get('DATABASE_URL', 'postgres://postgres:postgres@localhost:5432/postgres')
parsed_db = urllib.parse.urlparse(db_url)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parsed_db.path[1:],
        'USER': parsed_db.username,
        'PASSWORD': parsed_db.password,
        'HOST': parsed_db.hostname,
        'PORT': parsed_db.port,
    }
}

# Cache & Channels
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': redis_url,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [redis_url],
        },
    },
}

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # Cognito Access JWT (Authorization: Bearer …)
        'apps.users.authentication.CognitoJWTAuthentication',
        # Legacy DRF Token — remove after Phase 4/5 cutover
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')

# Cognito / MiniStack (see docs/MINISTACK_COGNITO_PLAN.md)
# AWS_ENDPOINT_URL points at MiniStack locally (http://ministack:4566); leave unset for real AWS.
AWS_ENDPOINT_URL = os.environ.get('AWS_ENDPOINT_URL', '').strip() or None
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
COGNITO_POOL_NAME = os.environ.get('COGNITO_POOL_NAME', 'messaging-app')
COGNITO_CLIENT_NAME = os.environ.get('COGNITO_CLIENT_NAME', 'messaging-web')
# Prefer env; apps.users.cognito falls back to cognito_state.json written by bootstrap_cognito
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '').strip()
COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID', '').strip()
# MiniStack stub JWTs may not verify with real JWKS — set COGNITO_VERIFY_JWT=False locally if needed.
# Default: verify when talking to real AWS; skip signature verify when using MiniStack endpoint.
_verify_jwt_env = os.environ.get('COGNITO_VERIFY_JWT', '').strip().lower()
if _verify_jwt_env in ('1', 'true', 'yes'):
    COGNITO_VERIFY_JWT = True
elif _verify_jwt_env in ('0', 'false', 'no'):
    COGNITO_VERIFY_JWT = False
else:
    COGNITO_VERIFY_JWT = AWS_ENDPOINT_URL is None

# S3 Export Storage (see docs/S3_INTEGRATION_PLAN.md)
EXPORT_S3_BUCKET = os.environ.get('EXPORT_S3_BUCKET', 'messaging-exports')

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
