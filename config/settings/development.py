"""
Development settings for config project.
Inherits from base settings and overrides for local development.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', '*'])

# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

# Email backend for development (outputs emails to console)
EMAIL_BACKEND = env.str(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)

# In development, execute Celery tasks immediately in-process by default
# so Mnotify SMS messages are dispatched instantly without requiring a separate
# 'celery worker' process running in a second terminal.
# (To test asynchronous background worker queues, set CELERY_TASK_ALWAYS_EAGER=False in .env)
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_TASK_ALWAYS_EAGER', default=True)
CELERY_TASK_EAGER_PROPAGATES = True
