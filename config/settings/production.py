"""
Production settings for config project.
Inherits from base settings and overrides for production deployment.
"""

from .base import *

# In production, DEBUG must always be False unless explicitly overridden
DEBUG = env.bool('DEBUG', default=False)

# In production, ALLOWED_HOSTS must be explicitly defined
ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS', 
    default=['localhost', '127.0.0.1', '.ngrok-free.dev', '.ngrok-free.app', '.ngrok.io', 'unshackle-reggae-distort.ngrok-free.dev']
)

# Production Database
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

# Static files with WhiteNoise compression & caching
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# CSRF Trusted Origins (preserves base defaults and allows env additions)
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=CSRF_TRUSTED_ORIGINS)

# Email backend for production
EMAIL_BACKEND = env.str(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend'
)

# Security settings
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
SECURE_BROWSER_XSS_FILTER = env.bool('SECURE_BROWSER_XSS_FILTER', default=True)
SECURE_CONTENT_TYPE_NOSNIFF = env.bool('SECURE_CONTENT_TYPE_NOSNIFF', default=True)
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=True)
X_FRAME_OPTIONS = 'DENY'
