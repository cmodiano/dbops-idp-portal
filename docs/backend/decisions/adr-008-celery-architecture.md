# ADR-008 : Architecture Celery — Tâches Asynchrones

**Date :** 2025-01-15
**Statut :** Accepté
**Décideurs :** Équipe IDP Portal

## Contexte

Le portail IDP doit exécuter des opérations longues sans bloquer les workers web Django :
polling du statut des jobs sur les plateformes externes (AAP, Terraform, GitHub Actions),
exécution des workflows conteneurs, health checks des intégrations, et tâches planifiées
(Beat). Ces opérations peuvent durer de quelques secondes à plusieurs minutes.

Un mécanisme de traitement asynchrone fiable et observable était nécessaire, avec la
capacité de router les tâches selon la plateforme cible.

## Décision

**Celery 5.x avec Redis comme broker et backend de résultats.**

### Configuration principale (`settings.py` lignes 695-745)

```python
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True
```

### Sérialisation JSON (Story 20.3)

Seul le format JSON est accepté (`CELERY_ACCEPT_CONTENT = ['json']`). La sérialisation
`pickle` est explicitement exclue pour des raisons de sécurité (exécution de code arbitraire
lors de la désérialisation de messages malveillants).

### Routing dynamique (Story 47.4)

`CELERY_TASK_ROUTES` est construit dynamiquement depuis l'`AdapterRegistry`
(`adapters/registry.py`). Ajouter une nouvelle plateforme dans `adapters/__init__.py`
est suffisant — aucune modification de `settings.py` n'est requise. La résolution de
queue utilise `adapter_registry.get_queue(platform_type)` au runtime.

Les tâches système (Beat, gates, résumé workflow) sont acheminées sur la queue `default`.

### Time limits centralisés (Story 71.8)

Un dictionnaire `CELERY_TASK_TIME_LIMITS` centralise les limites de temps pour chaque
tâche :

```python
CELERY_TASK_TIME_LIMITS = {
    "trigger_platform_job":      {"soft": 600, "hard": 630},   # 10min
    "poll_platform_job_status":  {"soft": 300, "hard": 330},   # 5min
    "evaluate_waiting_gates":    {"soft": 300, "hard": 330},   # 5min
    # ... (11 tâches couvertes)
}
```

**Mécanisme d'application** : chaque module de tâche lit ses limites depuis Django
`settings` à l'import du module, puis les injecte dans le décorateur `@app.task` :

```python
# executions/tasks/gates.py
_GATES_LIMITS = settings.CELERY_TASK_TIME_LIMITS["evaluate_waiting_gates"]

@app.task(
    soft_time_limit=_GATES_LIMITS["soft"],
    time_limit=_GATES_LIMITS["hard"],
)
def evaluate_waiting_gates(...): ...
```

- `soft_time_limit` : lève `SoftTimeLimitExceeded` pour permettre un cleanup gracieux
  (fermeture de connexions, logging final).
- `time_limit` (hard) : kill forcé après `soft + 30s` de marge.
- Les tâches implémentent `except SoftTimeLimitExceeded` pour le cleanup.

### Mode test synchrone

`CELERY_TASK_ALWAYS_EAGER = True` (variable d'environnement en CI) exécute les tâches
de manière synchrone dans le même thread, sans broker. `CELERY_TASK_EAGER_PROPAGATES = True`
propage les exceptions pour que les tests détectent les erreurs.

### Queues

- `default` : toutes les tâches actuellement (routing extensible via `apply_async(queue=...)`)
- Queues spécifiques par plateforme (`aap`, `github`, `terraform`, etc.) réservées pour
  l'isolation des workers par plateforme (extensibilité future)

## Conséquences

### Positives
- Tâches longues n'impactent pas les workers web Django
- Redis déjà déployé pour les Django Channels — mutualisation de l'infrastructure
- Routing dynamique : zéro modification `settings.py` pour ajouter une plateforme
- Time limits centralisés en un seul endroit (`CELERY_TASK_TIME_LIMITS`)
- Mode eager simplifie les tests (pas de broker requis en CI)

### Négatives
- Dépendance Redis (point de défaillance supplémentaire)
- Celery Beat nécessite un scheduler séparé (déployé comme service distinct)
- Les résultats des tâches sont stockés dans Redis (TTL à configurer)

### Neutres
- Un seul worker Celery couvre actuellement toutes les queues
- La configuration `CELERY_TASK_ROUTES` est construite à l'import de `settings.py`
  (import d'`adapters` déclenché explicitement, nettoyé du namespace ensuite)

## Alternatives Considérées

### Alternative 1 : Django-Q / Huey

- **Description :** Files d'attente légères intégrées à Django, sans broker externe requis
- **Raison du rejet :** Moins matures, moins documentés, écosystème restreint. Pas de support
  natif pour les tasks planifiées complexes (Beat equivalent), moins de visibilité sur l'état
  des tâches.

### Alternative 2 : ARQ (Async Redis Queue)

- **Description :** File d'attente asynchrone basée sur asyncio et Redis
- **Raison du rejet :** Nécessite une migration vers asyncio de la couche métier. La base de
  code est synchrone Django — migration trop coûteuse sans bénéfice immédiat.

### Alternative 3 : RQ (Redis Queue) + Django-RQ

- **Description :** File d'attente Redis sans dépendance Celery, avec intégration Django
  via `django-rq`. API plus simple pour les cas basiques.
- **Raison du rejet :** Pas de scheduler intégré équivalent à Celery Beat (requis pour
  Epic 42 — health checks périodiques, purge), pas de primitives `group`/`chord`, monitoring
  Flower non disponible. La maturité et l'écosystème Celery justifient le choix.

## Références

- `idp_backend/settings.py:695-745` — Configuration Celery complète
- `adapters/registry.py` — `AdapterRegistry` pour le routing dynamique
- `executions/tasks/__init__.py` — Décorateurs `@app.task` avec time limits
- `executions/tasks/polling.py` — Handlers `SoftTimeLimitExceeded`
- Story 20.3 — Introduction Celery asynchrone
- Story 47.4 — Routing dynamique via AdapterRegistry
- Story 71.8 — Centralisation `CELERY_TASK_TIME_LIMITS`
- Epic 42 — Celery Beat : tâches planifiées
