"""
Celery application configuration for IDP Portal.
Story 20.3: Asynchronous retry with Celery.
"""

import os
from celery import Celery  # type: ignore[import-untyped]

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idp_backend.settings')

app = Celery('idp_backend')

# Load config from Django settings with CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()
