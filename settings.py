"""
Django settings for MapleTrade project.
Complete settings.py with Technical Indicators configuration.
Updated to use existing User model from users app.
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-secret-key-here-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_redis',
    
    # Local apps (keep existing order)
    'users',      # Your existing users app
    'analytics',  # Analytics app for technical indicators
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mapletrade.urls'  # Adjust to your project name

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

WSGI_APPLICATION = 'mapletrade.wsgi.application'  # Adjust to your project name

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='mapletrade_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'MAX_CONNS': 20,
        }
    }
}

# Use your existing custom User model (keep this as is)
# AUTH_USER_MODEL = 'users.User'  # This should already be set in your existing settings

# Cache Configuration for Technical Indicators
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'mapletrade',
        'VERSION': 1,
        'TIMEOUT': 3600,  # 1 hour default
    },
    # Separate cache for technical indicators (optimized for high-RAM environment)
    'technical_indicators': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_TECHNICAL_URL', default='redis://127.0.0.1:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 200,  # Higher for technical calculations
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'tech_indicators',
        'VERSION': 1,
        'TIMEOUT': 3600,  # 1 hour for technical indicators
    },
    # Cache for market data
    'market_data': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_MARKET_URL', default='redis://127.0.0.1:6379/3'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'market_data',
        'VERSION': 1,
        'TIMEOUT': 3600,  # 1 hour for market data
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React development server
    "http://127.0.0.1:3000",
]

CORS_ALLOW_CREDENTIALS = True

# Technical Indicators Configuration
TECHNICAL_INDICATORS_CONFIG = {
    # Cache TTL settings (in seconds)
    'CACHE_TTL': {
        'SMA': 3600,           # 1 hour
        'EMA': 3600,           # 1 hour
        'RSI': 3600,           # 1 hour
        'MACD': 3600,          # 1 hour
        'BOLLINGER': 3600,     # 1 hour
        'BATCH': 7200,         # 2 hours for batch calculations
    },
    
    # Memory optimization for high-RAM environment (192GB)
    'MEMORY_OPTIMIZATION': {
        'MAX_DATAPOINTS_IN_MEMORY': 10000,    # Maximum data points to keep in memory
        'BATCH_SIZE': 100,                     # Batch size for bulk operations
        'PREFETCH_INDICATORS': True,           # Pre-calculate common indicators
        'USE_VECTORIZATION': True,             # Use numpy vectorization
    },
    
    # Default periods for indicators
    'DEFAULT_PERIODS': {
        'SMA': [20, 50, 200],
        'EMA': [12, 26, 50],
        'RSI': [14],
        'MACD': {'fast': 12, 'slow': 26, 'signal': 9},
        'BOLLINGER': {'period': 20, 'std_dev': 2.0},
    },
    
    # Signal thresholds
    'SIGNAL_THRESHOLDS': {
        'RSI_OVERBOUGHT': 70,
        'RSI_OVERSOLD': 30,
        'SMA_DEVIATION': 0.02,  # 2% deviation for signal generation
        'BOLLINGER_EXTREME': 80,  # 80% position for extreme signals
    }
}

# Cache TTL for different data types
TECHNICAL_INDICATORS_CACHE_TTL = 3600  # 1 hour
MARKET_DATA_CACHE_TTL = 3600           # 1 hour
ANALYSIS_RESULTS_CACHE_TTL = 14400     # 4 hours
SECTOR_MAPPINGS_CACHE_TTL = 86400      # 24 hours

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Logging configuration for technical indicators
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'technical_indicators.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'analytics.technical_indicators': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'analytics.cache': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'analytics.services': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Session configuration (use Redis for sessions)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Memory settings for pandas/numpy operations (optimized for 192GB RAM)
os.environ['NUMEXPR_MAX_THREADS'] = '16'  # Optimize for high-RAM environment
os.environ['OMP_NUM_THREADS'] = '16'      # OpenMP threads for numpy

# Database optimization for technical indicators
if 'OPTIONS' not in DATABASES['default']:
    DATABASES['default']['OPTIONS'] = {}

DATABASES['default']['OPTIONS'].update({
    'MAX_CONNS': 20,
})

# Celery configuration for background technical analysis (if using Celery)
CELERY_TASK_ROUTES = {
    'analytics.tasks.calculate_technical_indicators': {'queue': 'technical_analysis'},
    'analytics.tasks.update_market_data': {'queue': 'market_data'},
}

# Performance monitoring settings
TECHNICAL_INDICATORS_MONITORING = {
    'ENABLE_PERFORMANCE_LOGGING': True,
    'LOG_SLOW_CALCULATIONS': True,
    'SLOW_CALCULATION_THRESHOLD': 5.0,  # seconds
    'ENABLE_CACHE_STATS': True,
}

# Production settings
if not DEBUG:
    # Production cache settings
    CACHES['default']['TIMEOUT'] = 7200  # 2 hours in production
    CACHES['technical_indicators']['TIMEOUT'] = 7200
    
    # Enable cache key versioning for safe deployments
    CACHE_MIDDLEWARE_KEY_PREFIX = 'mapletrade_prod'
    
    # Memory optimization for production
    TECHNICAL_INDICATORS_CONFIG['MEMORY_OPTIMIZATION']['MAX_DATAPOINTS_IN_MEMORY'] = 5000
    
    # Security settings for production
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Force HTTPS in production
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True