"""
Celery application configuration for IDP Portal.
Story 20.3: Asynchronous retry with Celery.
Story 25.3: Celery Beat schedule for evaluate_waiting_gates.
Story 42.1: Celery Beat schedule for process_pending_scheduled_executions.
Story 51.3: Celery Beat schedule for health_check_all_integrations.
Story 78.5: Celery Beat schedule for process_runnable_steps (WorkQueue consumer).
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
        try:
            _gate_schedule = crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        except Exception as exc:
            logger.warning(
                "celery_beat_invalid_crontab_fallback_interval: crontab=%r error=%s fallback_interval=%s",
                _gate_crontab,
                exc,
                60.0,
            )
            _gate_schedule = 60.0
    else:
        logger.warning(
            "celery_beat_invalid_crontab_fallback_interval: crontab=%r fallback_interval=%s",
            _gate_crontab,
            60.0,
        )
        _gate_schedule = 60.0
else:
    try:
        _gate_schedule = float(os.getenv('CELERY_BEAT_EVALUATE_GATES_INTERVAL', '60.0'))
    except ValueError as exc:
        logger.warning(
            "celery_beat_invalid_interval: value=%r error=%s fallback=60.0",
            os.getenv('CELERY_BEAT_EVALUATE_GATES_INTERVAL'),
            exc,
        )
        _gate_schedule = 60.0

app.conf.beat_schedule = {
    'evaluate-waiting-gates': {
        'task': 'executions.tasks.evaluate_waiting_gates',
        'schedule': _gate_schedule,
    },
}

# Story 42.1: Celery Beat — process pending scheduled executions
# Environment variables:
#   CELERY_BEAT_PROCESS_SCHEDULED_EXECUTIONS_INTERVAL: seconds (default: 60.0)
#   CELERY_BEAT_PROCESS_SCHEDULED_EXECUTIONS_CRONTAB: crontab expression overrides interval
_sched_crontab = os.getenv('CELERY_BEAT_PROCESS_SCHEDULED_EXECUTIONS_CRONTAB')
if _sched_crontab:
    parts = _sched_crontab.split()
    if len(parts) == 5:
        try:
            _sched_schedule = crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        except Exception as exc:
            logger.warning(
                "celery_beat_invalid_sched_crontab_fallback_interval: crontab=%r error=%s fallback_interval=%s",
                _sched_crontab,
                exc,
                60.0,
            )
            _sched_schedule = 60.0
    else:
        logger.warning(
            "celery_beat_invalid_sched_crontab_fallback_interval: crontab=%r fallback_interval=%s",
            _sched_crontab,
            60.0,
        )
        _sched_schedule = 60.0
else:
    try:
        _sched_schedule = float(os.getenv('CELERY_BEAT_PROCESS_SCHEDULED_EXECUTIONS_INTERVAL', '60.0'))
    except ValueError as exc:
        logger.warning(
            "celery_beat_invalid_sched_interval: value=%r error=%s fallback=60.0",
            os.getenv('CELERY_BEAT_PROCESS_SCHEDULED_EXECUTIONS_INTERVAL'),
            exc,
        )
        _sched_schedule = 60.0

app.conf.beat_schedule['process-pending-scheduled-executions'] = {
    'task': 'executions.tasks.process_pending_scheduled_executions',
    'schedule': _sched_schedule,
}

# Story 51.3: Celery Beat — periodic health check of all integrations
# Environment variables:
#   CELERY_BEAT_HEALTH_CHECK_INTERVAL: seconds (default: 3600.0)
#   CELERY_BEAT_HEALTH_CHECK_CRONTAB: crontab expression overrides interval (e.g., "0 * * * *")
_health_check_crontab = os.getenv('CELERY_BEAT_HEALTH_CHECK_CRONTAB')
if _health_check_crontab:
    parts = _health_check_crontab.split()
    if len(parts) == 5:
        try:
            _health_check_schedule = crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        except Exception as exc:
            logger.warning(
                "celery_beat_invalid_health_check_crontab_fallback_interval: crontab=%r error=%s fallback_interval=%s",
                _health_check_crontab,
                exc,
                3600.0,
            )
            _health_check_schedule = 3600.0
    else:
        logger.warning(
            "celery_beat_invalid_health_check_crontab_fallback_interval: crontab=%r fallback_interval=%s",
            _health_check_crontab,
            3600.0,
        )
        _health_check_schedule = 3600.0
else:
    try:
        _health_check_schedule = float(os.getenv('CELERY_BEAT_HEALTH_CHECK_INTERVAL', '3600.0'))
    except ValueError as exc:
        logger.warning(
            "celery_beat_invalid_health_check_interval: value=%r error=%s fallback=3600.0",
            os.getenv('CELERY_BEAT_HEALTH_CHECK_INTERVAL'),
            exc,
        )
        _health_check_schedule = 3600.0

app.conf.beat_schedule['health-check-all-integrations'] = {
    'task': 'integrations.tasks.health_check_all_integrations',
    'schedule': _health_check_schedule,
}

# Purge old platform logs from ExecutionStep output (DB log retention)
# Environment variables:
#   CELERY_BEAT_PURGE_LOGS_CRONTAB: crontab expression (default: "0 3 * * *" = daily at 03:00)
#   CELERY_BEAT_PURGE_LOGS_INTERVAL: seconds, fallback if no crontab set
_purge_logs_crontab = os.getenv('CELERY_BEAT_PURGE_LOGS_CRONTAB')
_purge_logs_interval = os.getenv('CELERY_BEAT_PURGE_LOGS_INTERVAL')
if _purge_logs_crontab:
    parts = _purge_logs_crontab.split()
    if len(parts) == 5:
        try:
            _purge_logs_schedule = crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        except Exception as exc:
            logger.warning(
                "celery_beat_invalid_purge_logs_crontab: crontab=%r error=%s fallback=crontab(hour=3)",
                _purge_logs_crontab,
                exc,
            )
            _purge_logs_schedule = crontab(hour=3, minute=0)
    else:
        logger.warning(
            "celery_beat_invalid_purge_logs_crontab: crontab=%r fallback=crontab(hour=3)",
            _purge_logs_crontab,
        )
        _purge_logs_schedule = crontab(hour=3, minute=0)
elif _purge_logs_interval:
    try:
        _purge_logs_schedule = float(_purge_logs_interval)
    except ValueError as exc:
        logger.warning(
            "celery_beat_invalid_purge_logs_interval: value=%r error=%s fallback=crontab(hour=3)",
            _purge_logs_interval,
            exc,
        )
        _purge_logs_schedule = crontab(hour=3, minute=0)
else:
    _purge_logs_schedule = crontab(hour=3, minute=0)

# Vault secrets cache warmup — keeps the per-worker TTL cache primed so that
# execution requests hit the cache instead of calling Vault.
# Default interval = VAULT_CACHE_TTL (or 300s) to refresh just before expiry.
# Environment variables:
#   CELERY_BEAT_VAULT_WARMUP_INTERVAL: seconds (default: VAULT_CACHE_TTL or 300)
#   VAULT_CACHE_WARMUP: "true"/"false" — enable/disable warmup (default: true)
try:
    _vault_warmup_schedule = float(
        os.getenv('CELERY_BEAT_VAULT_WARMUP_INTERVAL', os.getenv('VAULT_CACHE_TTL', '300'))
    )
except ValueError:
    _vault_warmup_schedule = 300.0

app.conf.beat_schedule['warmup-vault-secrets-cache'] = {
    'task': 'integrations.tasks.warmup_vault_secrets_cache',
    'schedule': _vault_warmup_schedule,
}

app.conf.beat_schedule['purge-old-platform-logs'] = {
    'task': 'executions.tasks.purge_old_platform_logs',
    'schedule': _purge_logs_schedule,
}

# Purge old workflow events (UI sync catch-up records)
# Default: daily at 04:00, retention: 7 days (WORKFLOW_EVENT_RETENTION_DAYS)
# Environment variables:
#   CELERY_BEAT_PURGE_WORKFLOW_EVENTS_CRONTAB: crontab expression (default: "0 4 * * *")
_purge_events_crontab = os.getenv('CELERY_BEAT_PURGE_WORKFLOW_EVENTS_CRONTAB')
if _purge_events_crontab:
    parts = _purge_events_crontab.split()
    if len(parts) == 5:
        try:
            _purge_events_schedule = crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        except Exception as exc:
            logger.warning(
                "celery_beat_invalid_purge_events_crontab: crontab=%r error=%s fallback=crontab(hour=4)",
                _purge_events_crontab,
                exc,
            )
            _purge_events_schedule = crontab(hour=4, minute=0)
    else:
        logger.warning(
            "celery_beat_invalid_purge_events_crontab: crontab=%r fallback=crontab(hour=4)",
            _purge_events_crontab,
        )
        _purge_events_schedule = crontab(hour=4, minute=0)
else:
    _purge_events_schedule = crontab(hour=4, minute=0)

app.conf.beat_schedule['purge-old-workflow-events'] = {
    'task': 'executions.tasks.purge_old_workflow_events',
    'schedule': _purge_events_schedule,
}

# Crash recovery: reconcile stale RUNNING executions (orphaned after backend crash).
# Runs periodically as a safety net in addition to the AppConfig.ready() startup trigger.
# Default interval = 300s (5 minutes). Set to 0 to disable periodic reconciliation
# (startup-only mode). Env var: CELERY_BEAT_RECONCILE_INTERVAL (seconds, default: 300).
try:
    _reconcile_schedule = float(os.getenv('CELERY_BEAT_RECONCILE_INTERVAL', '300.0'))
except ValueError as exc:
    logger.warning(
        "celery_beat_invalid_reconcile_interval: value=%r error=%s fallback=300.0",
        os.getenv('CELERY_BEAT_RECONCILE_INTERVAL'),
        exc,
    )
    _reconcile_schedule = 300.0

if _reconcile_schedule > 0:
    app.conf.beat_schedule['reconcile-stale-executions'] = {
        'task': 'executions.tasks.reconcile_stale_executions',
        'schedule': _reconcile_schedule,
    }

# Story 78.7: Outbox dispatcher — process pending outbox entries for reliable side-effect delivery.
# Default interval = 10s. Set CELERY_BEAT_OUTBOX_INTERVAL env var to override (seconds).
try:
    _outbox_schedule = float(os.getenv('CELERY_BEAT_OUTBOX_INTERVAL', '10.0'))
except ValueError as exc:
    logger.warning(
        "celery_beat_invalid_outbox_interval: value=%r error=%s fallback=10.0",
        os.getenv('CELERY_BEAT_OUTBOX_INTERVAL'),
        exc,
    )
    _outbox_schedule = 10.0

if _outbox_schedule > 0:
    app.conf.beat_schedule['process-outbox-entries'] = {
        'task': 'executions.tasks.process_outbox_entries',
        'schedule': _outbox_schedule,
    }

# Story 86.9: Splunk batch durability — periodic safety flush for Celery workers
# Default interval = 30s. Set CELERY_BEAT_SPLUNK_FLUSH_INTERVAL env var to override (seconds).
try:
    _splunk_flush_schedule = float(os.getenv('CELERY_BEAT_SPLUNK_FLUSH_INTERVAL', '30.0'))
except ValueError as exc:
    logger.warning(
        "celery_beat_invalid_splunk_flush_interval: value=%r error=%s fallback=30.0",
        os.getenv('CELERY_BEAT_SPLUNK_FLUSH_INTERVAL'),
        exc,
    )
    _splunk_flush_schedule = 30.0

if _splunk_flush_schedule > 0:
    app.conf.beat_schedule['flush-splunk-logging-handler'] = {
        'task': 'core.tasks.flush_splunk_logging_handler',
        'schedule': _splunk_flush_schedule,
    }

# Story 78.5: WorkQueue consumer — claim and execute PENDING runnable steps (gates, platform steps).
# Default interval = 5s for low-latency gate processing. Override with CELERY_BEAT_RUNNABLE_STEPS_INTERVAL.
try:
    _runnable_steps_schedule = float(os.getenv('CELERY_BEAT_RUNNABLE_STEPS_INTERVAL', '5.0'))
except ValueError as exc:
    logger.warning(
        "celery_beat_invalid_runnable_steps_interval: value=%r error=%s fallback=5.0",
        os.getenv('CELERY_BEAT_RUNNABLE_STEPS_INTERVAL'),
        exc,
    )
    _runnable_steps_schedule = 5.0

if _runnable_steps_schedule > 0:
    app.conf.beat_schedule['process-runnable-steps'] = {
        'task': 'executions.tasks.process_runnable_steps',
        'schedule': _runnable_steps_schedule,
    }
