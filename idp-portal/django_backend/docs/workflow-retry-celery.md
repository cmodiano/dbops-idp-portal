# Workflow Retry avec Celery — Architecture et Configuration

> Story 20.3 — Migration du retry bloquant (`time.sleep()`) vers Celery `apply_async(countdown=...)`.

## Architecture

### Décision (ADR)

**Choix retenu : Celery + Redis**

| Critère | Celery | Huey | ARQ |
|---------|--------|------|-----|
| Maturité écosystème Django | ★★★★★ | ★★★ | ★★ |
| Support HA / monitoring | Flower, events | Limité | Minimal |
| Features avancées (chord, chain) | Oui | Non | Non |
| Compatible VM (sans Docker) | Oui | Oui | Oui |
| Redis déjà dans l'architecture | ✓ (feature flags 17.12) | ✓ | ✓ |

**Raisons :**
- Standard enterprise, largement adopté
- Redis déjà présent pour les feature flags (Story 17.12)
- Support monitoring production (Flower)
- Compatible avec le déploiement VM existant

### Diagramme de séquence

```
Échec étape workflow (tentative 1 - synchrone)
    │
    ├─ Succès → Retourner résultat ✓
    │
    ├─ Erreur permanente (validation, 4xx) → Arrêt immédiat ✗
    │
    └─ Erreur temporaire (timeout, 5xx) → Planifier retry Celery
         │
         │  retry_workflow_step.apply_async(
         │      args=[execution_id, step, 2],
         │      countdown=interval_seconds  # délai avant tentative 2
         │  )
         │
         └─ Worker Celery exécute après countdown
              │
              ├─ Vérifier annulation (is_cancelled)
              ├─ Exécuter l'étape
              ├─ Si succès → Audit + fin
              ├─ Si erreur permanente → Audit + arrêt
              ├─ Si erreur temporaire et attempt < max → Planifier attempt+1
              └─ Si attempt == max → Audit EXHAUSTED + arrêt
```

### Formule de backoff

Le délai est calculé **avant** la tentative N+1 :

```
delay = interval_seconds × backoff_multiplier^(attempt - 1)
```

**Exemple concret** avec `interval_seconds=30`, `backoff_multiplier=1.5`, `max_attempts=5` :

| Tentative | Calcul | Délai (countdown) | Timing cumulé |
|-----------|--------|--------------------|---------------|
| 1 | Immédiate (synchrone) | 0s | 0s |
| 2 | 30 × 1.5^0 | 30s | 30s |
| 3 | 30 × 1.5^1 | 45s | 75s |
| 4 | 30 × 1.5^2 | 67.5s | 142.5s |
| 5 | 30 × 1.5^3 | 101.25s | 243.75s |

**Important :** Le `countdown` est le délai **avant** l'exécution de la tentative suivante, géré par Celery (pas de `time.sleep()`).

## Comportement du Workflow Après Retry Planifié

**Question critique :** Que se passe-t-il quand `_execute_step_with_retry()` planifie un retry Celery et retourne immédiatement ?

**Réponse :**

1. **Première tentative échoue (synchrone)** → `_execute_step_with_retry()` retourne `StepResult(outcome=ERROR, error_details={'retry_scheduled': True})`

2. **Le workflow principal reçoit ce StepResult** :
   - Le WorkflowRuntime détecte `outcome=ERROR`
   - **Le workflow suit immédiatement `on_error_step_id`** (branche d'erreur)
   - Le workflow **ne bloque PAS** en attendant le résultat du retry asynchrone

3. **En arrière-plan** :
   - Celery exécute la tâche `retry_workflow_step()` après `countdown` secondes
   - Si succès → Audit trail enregistre `EXECUTION_STEP_RETRY_SUCCESS`
   - Si échec → Planifie tentative suivante ou enregistre `RETRY_EXHAUSTED`

4. **Réconciliation** :
   - Le résultat du retry asynchrone est **découplé** du workflow principal
   - L'audit trail permet de tracer le succès/échec final du retry
   - **Limitation actuelle :** Le workflow ne peut pas "revenir en arrière" si le retry réussit après avoir suivi `on_error_step_id`

**Exemple concret :**

```
Workflow: [Step A (retry enabled)] → on_success: [Step B], on_error: [Step C]

Timing:
t=0s   : Step A tentative 1 → ÉCHEC temporaire
t=0s   : Celery planifie retry tentative 2 (countdown=30s)
t=0s   : Workflow suit on_error_step_id → Step C s'exécute
t=30s  : Celery exécute Step A tentative 2 → SUCCÈS (mais Step C déjà exécuté)
```

**Recommandations pour la production :**
- Configurer `on_error_step_id` vers une étape de "cleanup" ou "notification"
- Ne PAS utiliser `on_error_step_id` pour rollback critique si retry activé
- Monitorer l'audit trail pour détecter les retries réussis après erreur workflow

## Configuration

### Django settings

```python
# idp_backend/settings.py

# Celery Configuration (Story 20.3)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_ALWAYS_EAGER = False  # True pour tests synchrones

# Cache Redis pour annulation (optionnel, production >100 workflows actifs)
WORKFLOW_RETRY_USE_CANCELLATION_CACHE = False  # True en production à fort volume
```

### Variables d'environnement

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | URL du broker Redis |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | URL du result backend |
| `CELERY_TASK_ALWAYS_EAGER` | `False` | Exécution synchrone (tests) |
| `WORKFLOW_RETRY_USE_CANCELLATION_CACHE` | `False` | Cache Redis pour annulation |

## Déploiement

### Prérequis

- Redis server ≥ 7.x sur `localhost:6379` (ou URL configurée)
- Python packages : `celery[redis]>=5.4.0`, `redis>=5.0.0`

### Développement

```bash
# Terminal 1 : Backend Django
cd idp-portal/django_backend
.venv/bin/python manage.py runserver

# Terminal 2 : Worker Celery
cd idp-portal/django_backend
.venv/bin/celery -A idp_backend worker -l info
```

### Production (systemd)

```ini
# /etc/systemd/system/idp-celery-worker.service
[Unit]
Description=IDP Portal Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=idp
Group=idp
WorkingDirectory=/opt/idp-portal/django_backend
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
Environment="CELERY_RESULT_BACKEND=redis://localhost:6379/0"
Environment="DJANGO_SETTINGS_MODULE=idp_backend.settings"
ExecStart=/opt/idp-portal/.venv/bin/celery -A idp_backend worker -l info
StandardOutput=journal
StandardError=journal
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Commandes systemd :**
```bash
# Activer et démarrer le service
sudo systemctl enable idp-celery-worker
sudo systemctl start idp-celery-worker

# Vérifier le statut
sudo systemctl status idp-celery-worker

# Voir les logs
sudo journalctl -u idp-celery-worker -f
```

## Cache Redis pour annulation (AC5)

Quand `WORKFLOW_RETRY_USE_CANCELLATION_CACHE = True` :
- Le statut d'annulation est mis en cache Redis (TTL 60s)
- Réduit les requêtes `refresh_from_db()` en production à fort volume
- Fallback automatique vers DB si Redis est indisponible

**Quand l'activer :** Production avec >100 workflows actifs avec retry simultanés.

## Tests

### Configuration

- Tests normaux : `CELERY_TASK_ALWAYS_EAGER = True` (exécution synchrone, pas de broker)
- Tests avec délais réels : `CELERY_TASK_ALWAYS_EAGER = False`, marqués `@pytest.mark.slow`

### Fichiers de tests

| Fichier | Description |
|---------|-------------|
| `test_workflow_runtime_retry.py` | Tests unitaires retry (23 tests) |
| `test_celery_retry_tasks.py` | Tests unitaires tâche Celery (8 tests) |
| `test_cancellation_cache.py` | Tests cache annulation (7 tests) |
| `test_workflow_runtime_retry_integration.py` | Tests intégration workflow+retry (4 tests) |
