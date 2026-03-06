"""
Production settings for Django Auth Service
Implements comprehensive security features
"""
import os
from datetime import timedelta
from pathlib import Path
import secrets
from urllib.parse import urlparse
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
except Exception:
    sentry_sdk = None
    DjangoIntegration = None

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# Generate a secure random key if not provided
def get_secret_key():
    key = os.environ.get('DJANGO_SECRET_KEY')
    if not key:
        # Generate a new secure key - but this will change on every restart!
        # In production, always provide DJANGO_SECRET_KEY
        print("WARNING: Using auto-generated secret key. Set DJANGO_SECRET_KEY in production!")
        key = secrets.token_urlsafe(50)
    return key

SECRET_KEY = get_secret_key()

# DEBUG should always be False in production
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

# ALLOWED_HOSTS - Configure your domain here
ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS', 
    'localhost,127.0.0.1'
).split(',')

# ============================================================================
# APPLICATION REGISTRATION
# ============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'auth_service',
]

# ============================================================================
# MIDDLEWARE - Security Layers
# ============================================================================

MIDDLEWARE = [
    # Security headers (must be first)
    'corsheaders.middleware.CorsMiddleware',
    
    # Django Security Middleware
    'django.middleware.security.SecurityMiddleware',
    
    # Session management
    'django.contrib.sessions.middleware.SessionMiddleware',
    
    # CSRF protection
    'django.middleware.csrf.CsrfViewMiddleware',
    
    # Authentication
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # Messages
    'django.contrib.messages.middleware.MessageMiddleware',
    
    # Clickjacking protection
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'auth_service.auth_service.urls'
AUTH_USER_MODEL = 'auth_service.User'

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
            # Enable template caching in production
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
            ] if not DEBUG else None,
        },
    },
]

WSGI_APPLICATION = 'auth_service.auth_service.wsgi.application'

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    db_engine = 'django.db.backends.postgresql'
    if parsed.scheme.startswith('postgres'):
        db_name = parsed.path.lstrip('/')
        db_user = parsed.username
        db_password = parsed.password
        db_host = parsed.hostname
        db_port = parsed.port or 5432
    else:
        # Fallback for unknown schemes
        db_name = DATABASE_URL
        db_user = ''
        db_password = ''
        db_host = ''
        db_port = ''

    DATABASES = {
        'default': {
            'ENGINE': db_engine,
            'NAME': db_name,
            'USER': db_user,
            'PASSWORD': db_password,
            'HOST': db_host,
            'PORT': db_port,
            'OPTIONS': {
                'sslmode': 'require',
                'sslrootcert': os.environ.get('SSL_ROOT_CERT', ''),
            } if os.environ.get('DATABASE_SSL', 'true').lower() == 'true' else {},
            'CONN_MAX_AGE': 60,  # Connection pooling
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ============================================================================
# INTERNATIONALIZATION
# ============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================================
# CORS (Cross-Origin Resource Sharing) CONFIGURATION
# ============================================================================

# In production, specify exact origins instead of allowing all
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost,http://localhost:80,http://localhost:3000,http://127.0.0.1'
).split(',')

CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'False').lower() == 'true'

# Allow credentials (cookies, authorization headers)
CORS_ALLOW_CREDENTIALS = True

# Allow only specific methods
CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS',
]

# Allow only specific headers
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ============================================================================
# REST FRAMEWORK CONFIGURATION
# ============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Throttling for API protection
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'login': '10/minute',
    }
}

# ============================================================================
# JWT (JSON Web Token) CONFIGURATION
# ============================================================================

SIMPLE_JWT = {
    # Token lifetime
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # Short access token
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),     # Refresh token valid for 1 day
    
    # Security settings
    'ROTATE_REFRESH_TOKENS': True,           # Issue new refresh token on use
    'BLACKLIST_AFTER_ROTATION': True,         # Add old refresh tokens to blacklist
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    
    # Token verification
    'VERIFY_ISS': False,
    'VERIFY_AUD': False,
    
    # Authentication header
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    
    # User authentication
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    # Token types
    'TOKEN_TYPE_CLAIM': 'token_type',
    
    # Sliding JWT
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=30),
}

# ============================================================================
# SECURITY SETTINGS FOR PRODUCTION
# ============================================================================

if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Content Security Policy
    SECURE_CONTENT_TYPE_NOSNIFF = True
    
    # Browser XSS Protection
    SECURE_BROWSER_XSS_FILTER = True
    
    # Referrer Policy
    REFERRER_POLICY = 'strict-origin-when-cross-origin'
    
    # Permissions Policy
    PERMISSIONS_POLICY = {
        'geolocation': '()',
        'microphone': '()',
        'camera': '()'
    }

# ============================================================================
# SESSION SECURITY
# ============================================================================

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ============================================================================
# CSRF SETTINGS
# ============================================================================

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# ============================================================================
# LOGGING - Security Event Logging
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.auth': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    if not sentry_sdk or not DjangoIntegration:
        print("WARNING: Sentry DSN set but sentry-sdk is not installed.")
    else:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            send_default_pii=False,
        )
