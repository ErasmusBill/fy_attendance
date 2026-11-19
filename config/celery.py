import os
from celery import Celery

# Set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('fy_attendacne')

# Read config from Django settings, with CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks.py in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Celery Debug Task: {self.request!r}')
