"""
Django settings for poker_project - Railway deployment.
"""

import os
import dj_database_url
from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', '3e6151b75f6d1c8609785dad05adabf81119f43b066c29fc879a03bd5550df3d')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Railway provides the domain automatically
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    'gillsgamestudio.com',
    '.railway.app',  # Allow all Railway subdomains
]

# Add Railway-provided domain if available
if 'RAILWAY_STATIC_URL' in os.environ:
    railway_domain = os.environ['RAILWAY_STATIC_URL'].replace('https://', '').replace('http://', '')
    if railway_domain and railway_domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(railway_domain)

# Database configuration for Railway (PostgreSQL)
if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Fallback to SQLite if DATABASE_URL not available
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Redis configuration for WebSocket channels
if 'REDIS_URL' in os.environ:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [os.environ.get('REDIS_URL')],
            },
        },
    }
else:
    # Fallback to in-memory channel layer
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# CORS settings for production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    'https://gillsgamestudio.com',
]

# Helper function to ensure URL has proper scheme
def ensure_url_scheme(url):
    """Ensure URL has a proper scheme (https:// or http://)"""
    if not url:
        return None
    if not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url

# Add Railway domains to CORS allowed origins with proper scheme
if 'RAILWAY_STATIC_URL' in os.environ:
    railway_url = ensure_url_scheme(os.environ['RAILWAY_STATIC_URL'])
    if railway_url and railway_url not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(railway_url)

# Also allow common frontend domains with proper scheme
frontend_url = os.environ.get('FRONTEND_URL')
if frontend_url:
    frontend_url = ensure_url_scheme(frontend_url)
    if frontend_url and frontend_url not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(frontend_url)

# Security settings for production
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Static files configuration for Railway
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Ensure static files are collected
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

print("DEBUG: Railway settings loaded successfully!")
print(f"DEBUG: Database URL configured: {'Yes' if 'DATABASE_URL' in os.environ else 'No (using SQLite fallback)'}")
print(f"DEBUG: Redis URL configured: {'Yes' if 'REDIS_URL' in os.environ else 'No (using in-memory fallback)'}")
print(f"DEBUG: Allowed hosts: {ALLOWED_HOSTS}")
print(f"DEBUG: CORS allowed origins: {CORS_ALLOWED_ORIGINS}")
print(f"DEBUG: Debug mode: {DEBUG}")