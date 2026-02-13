"""
Celery application configuration for IDP Portal.
Story 20.3: Asynchronous retry with Celery.
Story 25.3: Celery Beat schedule for evaluate_waiting_gates.
"""

import os
import logging
from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idp_backend.settings')

app = Celery('idp_backend')

# Load config from Django settings with CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Story 25.3: Celery Beat schedule — periodic evaluation of WAITING gate conditions
# Story 25.3 code review fix MEDIUM-2: Support crontab for prod flexibility
# Environment variables:
#   CELERY_BEAT_EVALUATE_GATES_INTERVAL: seconds (default: 60.0) for simple interval
#   CELERY_BEAT_EVALUATE_GATES_CRONTAB: crontab expression (e.g., "*/5 * * * *") overrides interval
_gate_crontab = os.getenv('CELERY_BEAT_EVALUATE_GATES_CRONTAB')
if _gate_crontab:
    # Crontab format: minute hour day-of-month month day-of-week
    # Example: "*/5 * * * *" = every 5 minutes
    parts = _gate_crontab.split()
    if len(parts) == 5:
        _gate_schedule = crontab(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month_of_year=parts[3],
            day_of_week=parts[4],
        )
    else:
        logger.warning(
            "celery_beat_invalid_crontab_fallback_interval",
            crontab=_gate_crontab,
            fallback_interval=60.0,
        )
        _gate_schedule = 60.0
else:
    _gate_schedule = float(os.getenv('CELERY_BEAT_EVALUATE_GATES_INTERVAL', '60.0'))

app.conf.beat_schedule = {
    'evaluate-waiting-gates': {
        'task': 'executions.tasks.evaluate_waiting_gates',
        'schedule': _gate_schedule,
    },
}
