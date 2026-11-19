"""
Settings package initialization.
Dynamically loads environment settings (development or production)
based on the DJANGO_ENV or ENVIRONMENT environment variable.
Defaults to development.
"""

import os

env = os.getenv('DJANGO_ENV', os.getenv('ENVIRONMENT', 'development')).lower()

if env in ('prod', 'production'):
    from .production import *
else:
    from .development import *
