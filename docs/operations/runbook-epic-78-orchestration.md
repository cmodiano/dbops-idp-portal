# Runbook — Epic 78 : Orchestration Temporal-like

**Version** : 1.0 — Story 78.16
**Périmètre** : Worker d'orchestration, Outbox, Commandes workflow, Event store
**Logs ingérés dans** : Splunk (`SPLUNK_INDEX=idp_portal_prod`)

---

## Vue d'ensemble des métriques clés

| Champ structlog | Source | Seuil d'alerte |
|---|---|---|
| `runnable_queue_depth` | `process_runnable_steps_metrics` | > 100 |
| `runnable_expired_leases` | `process_runnable_steps_metrics`, `reconcile_stale_executions_metrics` | > 10 |
| `command_backlog` | `reconcile_stale_executions_metrics` | > 50 |
| `outbox_pending` | `process_outbox_entries_metrics` | > 200 |
| `event_append_failure=True` | `workflow_event_emit_failed` | > 0 |
| `event_append_failure_best_effort=True` | `workflow_event_emit_failed` | > 5 |

---

## Scénarios d'incident

---

### Scénario 1 : Lease Expiry Storm

**Symptômes**

- Log key : `runnable_expired_leases` élevé (> 10) dans `process_runnable_steps_metrics` ou `reconcile_stale_executions_metrics`
- Requête Splunk : `index=idp_portal_prod event="process_runnable_steps_metrics" runnable_expired_leases>10`

**Causes probables**

1. Worker Celery crashé ou tué pendant un lease actif (SIGKILL, OOM)
2. `RUNNABLE_STEP_LEASE_SECONDS` trop court par rapport au temps d'exécution des steps
3. Batch size trop élevé — le worker prend trop de steps en même temps et dépasse le time_limit
4. Surcharge CPU/mémoire sur les workers → steps non traités avant expiration du lease

**Diagnostic**

```python
# Django shell — vérifier les leases expirés
from executions.observability import get_runnable_queue_depth
print(get_runnable_queue_depth())
# {'pending': X, 'running': Y, 'expired_leases': Z}

# Voir les steps avec leases expirés
from django.utils import timezone
from executions.models import RunnableStep
expired = RunnableStep.objects.filter(
    claimed_until__isnull=False,
    claimed_until__lte=timezone.now(),
)
print(f"Leases expirés : {expired.count()}")
for r in expired[:5]:
    print(f"  step_id={r.execution_step_id}, claimed_by={r.claimed_by}, until={r.claimed_until}")
```

```sql
-- Oracle : leases expirés
SELECT COUNT(*), CLAIMED_BY
FROM RUNNABLE_STEPS
WHERE CLAIMED_UNTIL IS NOT NULL AND CLAIMED_UNTIL <= SYSDATE
GROUP BY CLAIMED_BY;
```

**Remédiation**

1. Vérifier la santé des workers Celery : `celery inspect active`
2. Redémarrer les workers si crashés : `systemctl restart celery-worker`
3. Le réconciliateur `reconcile_stale_executions` appelle `WorkQueue.reclaim_expired()` automatiquement — attendre 1 cycle (par défaut toutes les 5 min) ou le déclencher manuellement :

```python
from executions.tasks.reconcile import reconcile_stale_executions
reconcile_stale_executions.apply_async()
```

4. Si le problème est structurel (lease trop court), augmenter `RUNNABLE_STEP_LEASE_SECONDS` dans les settings ou réduire le `batch_size` de `process_runnable_steps`.

---

### Scénario 2 : Command Backlog Growth

**Symptômes**

- Log key : `command_backlog` croissant dans `reconcile_stale_executions_metrics`
- Requête Splunk : `index=idp_portal_prod event="reconcile_stale_executions_metrics" command_backlog>50`
- Les approbations ou annulations d'exécution semblent sans effet dans l'UI

**Causes probables**

1. `reconcile_stale_executions` Celery Beat non démarré ou en erreur
2. `WorkflowCommandService.process_pending_commands()` en exception répétée (voir `reconcile_commands_redrive_failed`)
3. Deadlock Oracle sur la table `WORKFLOW_COMMANDS` (SELECT FOR UPDATE SKIP LOCKED)
4. Exécutions en état terminal bloquant le traitement des commandes associées

**Diagnostic**

```python
# Django shell — état du backlog
from executions.observability import get_command_backlog
print(f"Commandes PENDING : {get_command_backlog()}")

# Détail des commandes stuck
from executions.models import WorkflowCommand, WorkflowCommandStatus
pending = WorkflowCommand.objects.filter(status=WorkflowCommandStatus.PENDING).order_by('created_at')
print(f"Total PENDING : {pending.count()}")
for cmd in pending[:5]:
    print(f"  id={cmd.id}, type={cmd.command_type}, execution_id={cmd.execution_id}, created={cmd.created_at}")
```

```sql
-- Oracle : commandes stuck depuis plus de 10 min
SELECT ID, COMMAND_TYPE, EXECUTION_ID, STATUS, CREATED_AT
FROM WORKFLOW_COMMANDS
WHERE STATUS = 'pending'
  AND CREATED_AT < SYSDATE - INTERVAL '10' MINUTE
ORDER BY CREATED_AT;
```

**Remédiation**

1. Vérifier que `reconcile_stale_executions` tourne dans Celery Beat : `celery inspect scheduled`
2. Vérifier les erreurs récentes : Splunk `index=idp_portal_prod event="reconcile_commands_redrive_failed"`
3. Si le Celery Beat est arrêté, le relancer : `systemctl restart celery-beat`
4. En dernier recours, traiter manuellement les commandes :

```python
from executions.services.workflow_commands import WorkflowCommandService
count = WorkflowCommandService.process_pending_commands()
print(f"Commandes traitées : {count}")
```

---

### Scénario 3 : Outbox Stuck Events

**Symptômes**

- Log key : `outbox_pending` stable ou croissant dans `process_outbox_entries_metrics`
- Requête Splunk : `index=idp_portal_prod event="process_outbox_entries_metrics" outbox_pending>200`
- Notifications ou broadcasts WebSocket non reçus par les utilisateurs

**Causes probables**

1. `process_outbox_entries` Celery Beat non démarré ou en erreur
2. `max_attempts` atteint sur plusieurs entrées (voir `outbox_dispatch_failed`)
3. Service externe indisponible (NotificationService, WebSocket broker)
4. Entrées en statut FAILED bloquant la vue `outbox_pending` (count uniquement les PENDING)

**Diagnostic**

```python
# Django shell — état de l'outbox
from executions.observability import get_outbox_pending
print(f"Outbox PENDING : {get_outbox_pending()}")

# Entrées FAILED récentes
from executions.models import ExecutionOutbox, OutboxEntryStatus
failed = ExecutionOutbox.objects.filter(status=OutboxEntryStatus.FAILED).order_by('-id')
print(f"Total FAILED : {failed.count()}")
for e in failed[:5]:
    print(f"  id={e.id}, event_type={e.event_type}, attempts={e.attempt_no}/{e.max_attempts}, last_error={e.last_error[:100] if e.last_error else 'N/A'}")

# PENDING avec attempts proches du max
from django.db.models import F
at_risk = ExecutionOutbox.objects.filter(
    status=OutboxEntryStatus.PENDING,
    attempt_no__gte=F('max_attempts') - 1,
)
print(f"PENDING proches du max_attempts : {at_risk.count()}")
```

```sql
-- Oracle : outbox pending et failed depuis plus de 5 min
SELECT STATUS, COUNT(*), MIN(CREATED_AT) as oldest
FROM EXECUTION_OUTBOX
WHERE STATUS IN ('pending', 'failed')
  AND CREATED_AT < SYSDATE - INTERVAL '5' MINUTE
GROUP BY STATUS;
```

**Remédiation**

1. Vérifier que `process_outbox_entries` tourne dans Celery Beat
2. Vérifier `outbox_dispatch_failed` dans Splunk pour identifier le type d'erreur
3. Si service externe indisponible, les retry automatiques reprendront au retour du service
4. Pour réinitialiser des entrées FAILED en PENDING (retry forcé) :

```python
from django.db.models import F
from executions.models import ExecutionOutbox, OutboxEntryStatus
# Réinitialiser les FAILED avec attempt_no < max_attempts
reset_count = ExecutionOutbox.objects.filter(
    status=OutboxEntryStatus.FAILED,
    attempt_no__lt=F('max_attempts'),
).update(status=OutboxEntryStatus.PENDING, last_error=None)
print(f"Entrées réinitialisées : {reset_count}")
```

5. Déclencher manuellement le dispatcher :

```python
from executions.tasks.outbox_dispatcher import process_outbox_entries
result = process_outbox_entries.apply_async()
print(result.get())
```

---

### Scénario 4 : Sequence Allocation Failures (Event Store)

**Symptômes**

- Log key : `event_append_failure=True` dans `workflow_event_emit_failed`
- Requête Splunk : `index=idp_portal_prod event="workflow_event_emit_failed" event_append_failure=True`
- Les exécutions restent bloquées en RUNNING (les transitions de statut ne progressent pas)
- Erreurs 500 ou timeouts côté API lors des transitions d'approbation/rejet

**Causes probables**

1. Contention Oracle élevée sur `WORKFLOW_EVENT_COUNTER` (table utilisée pour l'allocation atomique de `sequence_num`)
2. Deadlock entre deux émetteurs concurrents sur la même `execution_id`
3. Saturation des connexions Oracle (`ORA-04031`, `ORA-00018`)
4. Transaction trop longue tenant un verrou sur `WORKFLOW_EVENT_COUNTER` (SELECT FOR UPDATE)

**Diagnostic**

```python
# Django shell — vérifier l'event store
from executions.models import WorkflowEventCounter, WorkflowEvent

# Dernière séquence pour une exécution spécifique
counter = WorkflowEventCounter.objects.filter(execution_id=<EXEC_ID>).first()
if counter:
    print(f"Dernière séquence : {counter.last_sequence_num}")
    events = WorkflowEvent.objects.filter(execution_id=<EXEC_ID>).order_by('-sequence_num')[:5]
    for ev in events:
        print(f"  seq={ev.sequence_num}, type={ev.event_type}, created={ev.created_at}")
```

```sql
-- Oracle : sessions bloquées sur WORKFLOW_EVENT_COUNTER
SELECT s.SID, s.SERIAL#, s.STATUS, s.SQL_ID, s.BLOCKING_SESSION, s.WAIT_CLASS, s.EVENT
FROM V$SESSION s
WHERE s.WAIT_CLASS NOT IN ('Idle')
  AND UPPER(s.EVENT) LIKE '%WORKFLOW_EVENT_COUNTER%';

-- Verrous actifs sur la table
SELECT * FROM V$LOCK
WHERE TYPE = 'TM'
  AND ID1 = (SELECT OBJECT_ID FROM DBA_OBJECTS WHERE OBJECT_NAME = 'WORKFLOW_EVENT_COUNTER');
```

**Remédiation**

1. **Court terme** : Les émetteurs critiques re-lèvent l'exception → les transactions sont rollbackées et les steps passeront en FAILED. Le réconciliateur les reprendra.
2. Vérifier les sessions Oracle bloquées et les killer si nécessaire via DBA Oracle.
3. Vérifier que le retry backoff est actif (le service émet via transaction.atomic() avec IntegrityError catch).
4. **Long terme** : Si la contention est structurelle (> 50 émissions/s sur une seule execution_id), envisager de partitionner la table `WORKFLOW_EVENT_COUNTER` ou d'augmenter les connexions Oracle disponibles.
5. Alerter l'équipe DBA si `event_append_failure=True` apparaît plus de 5 fois en 5 minutes.

---

## Commandes de diagnostic rapide

```python
# Vue d'ensemble santé orchestration
from executions.observability import (
    get_runnable_queue_depth,
    get_command_backlog,
    get_outbox_pending,
)

depth = get_runnable_queue_depth()
print(f"Queue depth     : pending={depth['pending']}, running={depth['running']}, expired={depth['expired_leases']}")
print(f"Command backlog : {get_command_backlog()}")
print(f"Outbox pending  : {get_outbox_pending()}")
```

---

## Références

- Architecture : `docs/backend/epic-78-temporal-like-orchestration-without-temporal.md`
- Code worker : `idp-portal/django_backend/executions/tasks/orchestration_worker.py`
- Code outbox : `idp-portal/django_backend/executions/tasks/outbox_dispatcher.py`
- Code réconciliateur : `idp-portal/django_backend/executions/tasks/reconcile.py`
- Code event service : `idp-portal/django_backend/executions/services/workflow_events.py`
- Module métriques : `idp-portal/django_backend/executions/observability.py`
