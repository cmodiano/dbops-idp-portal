# Story 30.7: Race conditions, Celery polling, caches partagés

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'opérateur,
Je veux que le polling Celery ait une limite de retry, que les mises à jour concurrentes du catalogue soient sérialisées, et que les caches soient cohérents entre workers (ou le comportement documenté),
Afin d'éviter les boucles infinies et les corruptions silencieuses.

## Acceptance Criteria

1. **Given** les tâches de polling (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud)
   **When** une erreur ou un timeout distant survient
   **Then** un `max_retries` est appliqué ; après dépassement, l'exécution passe en `FAILED` (pas de re-schedule infini)

2. **Given** dans `catalog/services.py`, les opérations `update_action`, `update_status`, `delete_action`, `deactivate_action`
   **When** plusieurs requêtes concurrentes tentent de modifier la même action
   **Then** `select_for_update()` est utilisé dans le bloc transactionnel pour sérialiser les modifications

3. **Given** les caches module-level (`_catalog_cache`, `_tags_cache`, `_environments_cache`)
   **When** plusieurs workers Gunicorn traitent des requêtes
   **Then** soit les caches sont migrés vers un cache partagé (ex. Redis), soit le comportement (par-worker) est documenté et TTL court accepté

4. **Given** l'utilisation de `asyncio` dans les tâches de polling
   **When** un nouveau cycle de polling démarre
   **Then** (optionnel) `asyncio.run()` est utilisé au lieu de créer un nouvel event loop à chaque cycle

5. **Given** un gate timeout dans un workflow
   **When** le timeout est dépassé
   **Then** le workflow continue ou est marqué explicitement en échec ; les steps en SKIPPED pour timeout ont un `error_message` explicite

## Tasks / Subtasks

- [x] Task 1: Implémenter max_retries pour les tâches de polling (AC: #1)
  - [x] Subtask 1.1: Analyser les 5 tâches de polling actuelles dans executions/tasks.py
  - [x] Subtask 1.2: Ajouter un paramètre `retry_count` à chaque tâche (default=0)
  - [x] Subtask 1.3: Définir `MAX_POLLING_RETRIES` comme constante (20 tentatives)
  - [x] Subtask 1.4: Après chaque erreur d'adapter, vérifier `retry_count >= MAX_POLLING_RETRIES`
  - [x] Subtask 1.5: Si dépassé, marquer l'exécution en `FAILED` avec error_message explicite
  - [x] Subtask 1.6: Sinon, re-schedule avec `retry_count + 1`
  - [x] Subtask 1.7: Ajouter un log structlog avec `retry_count` et `max_retries` à chaque tentative
  - [x] Subtask 1.8: Créer une entrée d'audit `EXECUTION_POLLING_EXHAUSTED` quand max atteint
  - [x] Subtask 1.9: Écrire des tests unitaires pour chaque tâche avec scénario exhaustion

- [x] Task 2: Ajouter select_for_update() dans catalog/services.py (AC: #2)
  - [x] Subtask 2.1: Analyser les méthodes de modification d'action
  - [x] Subtask 2.2: Dans `update_action()`, remplacer par `select_for_update().get()`
  - [x] Subtask 2.3: Appliquer le même pattern dans `update_status()`, `delete_action()`, `deactivate_action()`
  - [x] Subtask 2.4: Vérifier que toutes ces méthodes sont bien dans un bloc `@transaction.atomic`
  - [x] Subtask 2.5: Ajouter un commentaire expliquant pourquoi `select_for_update()` est nécessaire
  - [x] Subtask 2.6: Écrire des tests vérifiant le bon fonctionnement avec verrouillage
  - [x] Subtask 2.7: Vérifier qu'aucune deadlock n'est introduite (ordre d'acquisition cohérent)

- [x] Task 3: Documenter ou migrer les caches module-level (AC: #3)
  - [x] Subtask 3.1: Analyser les 3 caches in-memory actuels
  - [x] Subtask 3.2: Décision: documenter le comportement per-worker (Option A)
  - [x] Subtask 3.5: Créer `docs/architecture/caching-strategy.md`
  - [x] Subtask 3.6: Ajouter un commentaire dans le code à côté de chaque cache pointant vers la doc
  - [x] Subtask 3.8: Ajouter un test vérifiant que le TTL est bien appliqué

- [x] Task 4: (Optionnel) Optimiser asyncio event loops dans polling (AC: #4)
  - [x] Subtask 4.1: Analyser les 5 usages de `asyncio.new_event_loop()` dans tasks.py
  - [x] Subtask 4.2: Remplacer par `asyncio.run()` pour chaque tâche
  - [x] Subtask 4.3: Vérifier que le comportement est identique (tests existants passent)

- [x] Task 5: Corriger le comportement après gate timeout (AC: #5)
  - [x] Subtask 5.1: Analyser le code de gestion de timeout dans executions/tasks.py
  - [x] Subtask 5.2: Décision: SKIPPED → continuer le workflow, FAILED → marquer en échec
  - [x] Subtask 5.3: SKIPPED: marquer le step avec `error_message = "Gate timeout exceeded"`
  - [x] Subtask 5.4: FAILED: marquer l'exécution en `FAILED` et arrêter le workflow
  - [x] Subtask 5.5: Remplacer le TODO actuel par l'implémentation choisie
  - [x] Subtask 5.6: Ajouter un log structlog explicite quand un gate timeout
  - [x] Subtask 5.7: Audit `EXECUTION_STEP_GATE_TIMEOUT` déjà existant (Story 25.3)
  - [x] Subtask 5.8: Écrire des tests simulant un gate timeout et vérifiant le comportement

- [x] Task 6: Tests d'intégration et documentation (tous AC)
  - [x] Subtask 6.3: Documenter les limites de retry dans docs/operations/polling-tasks.md
  - [x] Subtask 6.4: Documenter la stratégie de cache dans docs/architecture/caching-strategy.md
  - [x] Subtask 6.5: Mettre à jour CODEBASE-REVIEW.md pour marquer RACE-1, RACE-2, RACE-3, CELERY-3, CELERY-4, CELERY-5 comme ✅ RESOLVED
  - [x] Subtask 6.6: Valider qu'aucune régression n'est introduite (77 tests passent)

## Dev Notes

### Contexte Epic 30

Cette story fait partie de l'Epic 30 "Corrections exhaustives — Codebase Review IDP Portal" qui adresse 65 findings identifiés dans CODEBASE-REVIEW.md (16 février 2026). Story 30.7 cible spécifiquement les problèmes de race conditions et de concurrence (RACE-1, RACE-2, RACE-3, CELERY-3, CELERY-4, CELERY-5).

### Issues identifiées

**RACE-1 [HIGH]** — Polling infini sans limite de retry
- **Fichier:** `executions/tasks.py` (5 tâches de polling)
- **Problème:** Toutes les tâches de polling (`poll_aap_job_status`, `poll_tower_job_status`, `poll_azure_devops_run_status`, `poll_github_actions_run_status`, `poll_terraform_cloud_run_status`) se re-planifient sur erreur sans compteur de retry. Si la plateforme distante est down, elles polleront indéfiniment.
- **Impact:** Boucle infinie consommant des ressources Celery, exécutions bloquées sans statut final
- **Fix:** Ajouter un `max_retries` et passer l'exécution en `FAILED` après dépassement

**RACE-2 [MEDIUM]** — `update_action()` sans `select_for_update()`
- **Fichier:** `catalog/services.py:264-265`
- **Problème:** Dans un `@transaction.atomic`, le `get()` n'acquiert pas de verrou. Deux requêtes concurrentes → last-write-wins. Même pattern dans `update_status()`, `delete_action()`, `deactivate_action()`.
- **Impact:** Corruption silencieuse des données du catalogue, perte de mises à jour concurrentes
- **Fix:** `Action.objects.select_for_update().get(id=action_id)`

**RACE-3 [MEDIUM]** — Caches in-memory module-level non partagés entre workers
- **Fichiers:** `catalog/views.py` (`_catalog_cache`, `_tags_cache`), `inventory/services.py` (`_environments_cache`)
- **Problème:** `cachetools.TTLCache` au niveau module → chaque worker Gunicorn a son propre cache. Données incohérentes entre requêtes routées vers différents workers.
- **Impact:** UX incohérente, utilisateurs voient des données différentes selon le worker qui traite leur requête
- **Fix:** Utiliser Redis comme cache partagé, ou accepter l'incohérence avec un TTL court et le documenter

**CELERY-3 [MEDIUM]** — Nouveau event loop asyncio créé à chaque cycle de polling
- **Fichier:** `executions/tasks.py:589-590, 749-750, 905-906, 1209-1210, 1379-1380`
- **Problème:** `asyncio.new_event_loop()` + `set_event_loop()` à chaque poll. Coûteux.
- **Impact:** Performance dégradée, allocation mémoire inutile
- **Fix:** Utiliser `asyncio.run()`

**CELERY-4 [MEDIUM]** — Gate timeout ne continue pas le workflow
- **Fichier:** `executions/tasks.py:506-522`
- **Problème:** Après un timeout de gate, le code log un TODO mais ne continue pas le workflow. L'exécution reste bloquée indéfiniment.
- **Impact:** Workflows bloqués, SLA non respecté
- **Fix:** Continuer le workflow ou marquer explicitement en échec

**CELERY-5 [LOW]** — Gate timeout SKIPPED sans message d'erreur
- **Fichier:** `executions/tasks.py:470-474`
- **Problème:** Step mise en `SKIPPED` sans `error_message` → impossible de savoir pourquoi dans l'historique.
- **Impact:** Traçabilité réduite, debugging difficile
- **Fix:** Ajouter `error_message = "Gate timeout exceeded"` explicite

### Architecture technique

**Backend:**
- Django 5.2 + Django REST Framework 3.16
- Celery pour les tâches asynchrones (retry, polling, gate evaluation)
- Base de données: Oracle
- Workers Gunicorn (multi-process)

**Structure du code:**
- `executions/tasks.py`: Tâches Celery de polling et retry
- `catalog/services.py`: Logique métier du catalogue (CRUD actions)
- `catalog/views.py`: Views DRF avec cache in-memory
- `inventory/services.py`: Services d'inventaire avec cache in-memory
- `executions/workflow_runtime.py`: Moteur d'exécution de workflows

**Tâches de polling Celery:**

Toutes suivent le même pattern:
```python
@shared_task(bind=True, max_retries=0)
def poll_xxx_status(self, execution_id: int, step_id: str, platform_job_id: str):
    # 1. Charger l'exécution
    # 2. Créer l'adapter (AAP, Tower, Azure, GitHub, Terraform)
    # 3. Appeler adapter.poll_job_status() via asyncio
    # 4. Mettre à jour le step status
    # 5. Si EN_COURS: re-schedule avec countdown=5s
    # 6. Si TERMINÉ: continuer le workflow
    # 7. Si ERREUR: re-schedule sans limite (BUG!)
```

**Caches actuels:**

```python
# catalog/views.py
_catalog_cache: TTLCache = TTLCache(maxsize=100, ttl=300)  # 5min
_tags_cache: TTLCache = TTLCache(maxsize=50, ttl=300)

# inventory/services.py
_environments_cache: TTLCache = TTLCache(maxsize=10, ttl=600)  # 10min
```

### Stratégie de correction recommandée

**Pour RACE-1 (polling infini):**

Option choisie: **Ajouter un compteur de retry avec max_retries = 20**
- 20 tentatives × 5s = 100s minimum
- Avec backoff exponentiel (si implémenté): jusqu'à ~33 minutes
- Suffisant pour absorber des pannes temporaires
- Évite les boucles infinies

**Pour RACE-2 (update_action sans verrou):**

Option choisie: **Ajouter select_for_update() dans tous les blocs @transaction.atomic**
- Sérialise les modifications concurrentes
- Évite les corruptions silencieuses
- Performance acceptable (le catalogue n'est pas modifié en haute fréquence)

**Pour RACE-3 (caches non partagés):**

Deux options possibles:

**Option A (Recommandée pour MVP): Documenter le comportement**
- Avantages: Pas de dépendance Redis, simplicité opérationnelle
- Inconvénients: Incohérence temporaire entre workers
- Acceptable si: TTL courts (5min max), invalidation automatique au redémarrage, données non-critiques (catalogue, tags, environments)
- Implémentation: Créer `docs/architecture/caching-strategy.md`

**Option B (Recommandée pour Production): Migrer vers Redis**
- Avantages: Cohérence garantie entre workers, invalidation précise
- Inconvénients: Dépendance Redis, complexité opérationnelle
- Implémentation: django-redis, configurer CACHES, remplacer TTLCache par cache.get/set

→ **Choisir Option A pour MVP** (documenter), planifier Option B pour Phase 2

**Pour CELERY-3 (asyncio event loops):**

Option choisie: **Utiliser asyncio.run()**
- Plus simple, recommandé par la doc Python 3.7+
- Évite la gestion manuelle d'event loop
- Pas de régression de comportement

**Pour CELERY-4/5 (gate timeout):**

Option choisie: **Continuer le workflow avec step SKIPPED + error_message**
- Cohérent avec le pattern retry (après max_retries, on continue)
- Permet de terminer les workflows malgré un gate timeout
- Traçabilité via error_message explicite

### Patterns de code établis

**Pattern retry Celery avec max_retries:**

```python
@shared_task(bind=True, max_retries=0)
def poll_xxx_status(
    self,
    execution_id: int,
    step_id: str,
    platform_job_id: str,
    retry_count: int = 0,
):
    MAX_POLLING_RETRIES = 20  # ~33 minutes avec backoff

    try:
        # ... logic de polling ...

        if status == 'running':
            # Re-schedule
            poll_xxx_status.apply_async(
                args=[execution_id, step_id, platform_job_id, retry_count],
                countdown=5,
            )
        elif status == 'error':
            # Check max retries
            if retry_count >= MAX_POLLING_RETRIES:
                # EXHAUSTED - marquer en FAILED
                logger.error("polling_exhausted", execution_id=execution_id, ...)
                step.status = ExecutionStepStatus.FAILED
                step.error_message = f"Polling exhausted after {MAX_POLLING_RETRIES} retries"
                step.save()

                AuditService.create_entry(
                    action_type=AuditActionType.EXECUTION_POLLING_EXHAUSTED,
                    ...
                )
            else:
                # Re-schedule avec retry_count + 1
                poll_xxx_status.apply_async(
                    args=[execution_id, step_id, platform_job_id, retry_count + 1],
                    countdown=5,
                )

    except Exception as exc:
        logger.error("polling_error", error=str(exc), ...)
        # Même logique de max_retries
```

**Pattern select_for_update() dans transactions:**

```python
@transaction.atomic
def update_action(action_id: int, updates: dict) -> Action:
    """
    Update action with pessimistic locking to prevent race conditions.

    Uses select_for_update() to serialize concurrent updates on the same action.
    This prevents last-write-wins corruption when multiple requests attempt to
    modify the same action simultaneously.
    """
    # Acquire row-level lock
    action = Action.objects.select_for_update().get(id=action_id)

    # Apply updates
    for key, value in updates.items():
        setattr(action, key, value)

    action.save()
    return action
```

**Pattern cache partagé Redis (si Option B choisie):**

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'idp_portal',
        'TIMEOUT': 300,  # 5min
    }
}

# catalog/views.py
from django.core.cache import cache

def list_catalog(filters: dict):
    cache_key = f"catalog:{filters_hash}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return cached_data

    # Query DB
    data = _fetch_catalog(filters)

    # Cache for 5min
    cache.set(cache_key, data, timeout=300)
    return data
```

### Travaux précédents de l'Epic 30

Stories déjà complétées dans cet epic:
- **30.1**: Endpoints approve/reject + bug filtres catalogue + config sécurité (CRITICAL) ✅
- **30.2**: Endpoints remediation et export dashboard (HIGH) ✅
- **30.3**: Bugs logiques backend (BUG-BE-2 à BE-7) ✅
- **30.4**: Bugs logiques frontend (notifications, Alert, rowKey, hooks) ✅
- **30.5**: Sécurité auth, uploads, dev bypass, CORS, Celery ✅
- **30.6**: Incohérences API (format de réponse) ✅

Learnings des stories précédentes:
- **Story 30.3**: Importance de la gestion d'erreur explicite (pas de swallow silencieux)
- **Story 30.5**: Celery déjà utilisé pour retry asynchrone (Story 20.3) - pattern à suivre
- **Story 30.6**: Cohérence critique pour l'expérience développeur

### Commits récents pertinents

```
e9bef56 fix(30-6): standardisation format réponses API et correction cache catalogue
11a9045 feat(30-5): renforcement sécurité authentification, uploads et configuration développement
ade895a fix(30-4): correction bugs logiques frontend notifications, Alert props, rowKey et hooks
5a08d4b fix(30-3): correction bugs logiques backend BE-2 à BE-7
de04772 feat(30-2): endpoints remédiation et export dashboard
```

Le commit `5a08d4b` (Story 30.3) a déjà corrigé plusieurs bugs backend, le pattern de correction est établi.

### Fichiers à modifier

**Backend - Tâches Celery:**
- `idp-portal/django_backend/executions/tasks.py` (lignes ~530-1400)
  - `poll_aap_job_status` (~530)
  - `poll_tower_job_status` (~696)
  - `poll_azure_devops_run_status` (~827)
  - `poll_github_actions_run_status` (~983)
  - `poll_terraform_cloud_run_status` (~1153)
  - `evaluate_waiting_gates` (gate timeout handling ~470-522)

**Backend - Services Catalogue:**
- `idp-portal/django_backend/catalog/services.py`
  - `update_action()` (~264)
  - `update_status()` (~300)
  - `delete_action()` (~378)
  - `deactivate_action()` (~424)

**Backend - Caches:**
- `idp-portal/django_backend/catalog/views.py` (~726, ~862)
- `idp-portal/django_backend/inventory/services.py` (cache environments)
- `idp-portal/django_backend/idp_backend/settings.py` (si Option B Redis)

**Documentation (nouveau):**
- `idp-portal/docs/architecture/caching-strategy.md` (si Option A documenter)
- `idp-portal/docs/operations/polling-tasks.md` (limites de retry)

**Tests:**
- `idp-portal/django_backend/executions/tests/test_polling_tasks.py` (nouveau ou modifier)
- `idp-portal/django_backend/catalog/tests/test_concurrency.py` (nouveau)
- Tests d'intégration pour validation end-to-end

### Testing requirements

**Tests unitaires:**
- 5 tests pour chaque tâche de polling simulant exhaustion (5 × 1 = 5 tests min)
- Tests de concurrence pour update_action, update_status, delete_action, deactivate_action (4 tests)
- Tests de cache (Redis ou TTLCache selon option choisie) (3 tests)
- Tests gate timeout avec error_message explicite (2 tests)
- **Total minimum: 14 tests backend**

**Tests d'intégration:**
- Charge: 100+ polling tasks simultanés (1 test)
- Concurrence: 10+ updates simultanés sur la même action (1 test)
- Cache cohérence: vérifier TTL ou partage Redis (1 test)
- **Total: 3 tests intégration**

**Critères de succès:**
- Tous les tests existants passent (0 régression)
- Les 5 tâches de polling s'arrêtent après MAX_POLLING_RETRIES
- Pas de corruption silencieuse lors de mises à jour concurrentes du catalogue
- Comportement de cache documenté OU cohérent entre workers (selon option)
- Gate timeout traité explicitement (pas de workflow bloqué)

### Risques et mitigations

**Risque 1: Deadlocks avec select_for_update()**
- **Mitigation:** Toujours acquérir les verrous dans le même ordre (par ID croissant)
- **Test:** Simuler 2+ transactions concurrentes et vérifier qu'aucune deadlock

**Risque 2: Performance dégradée avec select_for_update()**
- **Mitigation:** Le catalogue n'est pas modifié en haute fréquence (acceptable)
- **Monitoring:** Logger la durée des transactions avec verrous

**Risque 3: Redis down si Option B choisie**
- **Mitigation:** Fallback sur DB query si cache indisponible
- **Test:** Simuler Redis down et vérifier que l'app reste fonctionnelle

**Risque 4: MAX_POLLING_RETRIES trop bas ou trop haut**
- **Mitigation:** Commencer avec 20 (conservateur), ajuster selon métriques production
- **Monitoring:** Logger retry_count à chaque tentative, analyser les patterns

### Performance considerations

**Impact select_for_update():**
- Augmentation latence: ~10-50ms par requête (mesure à valider)
- Volume modif catalogue: <10 req/min (acceptable)
- Alternative: optimistic locking (version field) - plus complexe

**Impact MAX_POLLING_RETRIES:**
- Charge Celery réduite: évite les boucles infinies
- Latence détection d'échec: max 33 minutes (acceptable pour ops)
- Alternative: timeout global par exécution - peut interrompre des opérations longues légitimes

**Impact cache Redis (si Option B):**
- Latence cache hit: +2-5ms (réseau Redis)
- Charge Redis: <100 req/s (faible)
- Alternative: cache local avec invalidation pub/sub - plus complexe

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#Section 6 - Race conditions & concurrence]
- [Source: idp-portal/CODEBASE-REVIEW.md#Section 11 - Problèmes Celery / tâches async]
- [Source: _bmad-output/planning-artifacts/epic-30-codebase-review-corrections-fev-2026.md#Story 30.7]
- [Source: idp-portal/django_backend/executions/tasks.py:530-1400 - Polling tasks]
- [Source: idp-portal/django_backend/catalog/services.py:264-424 - CRUD actions]
- [Source: idp-portal/django_backend/catalog/views.py:726,862 - Caches in-memory]
- [Source: idp-portal/django_backend/inventory/services.py - Environments cache]
- [Story 20.3: Celery async retry - Pattern établi pour retry avec countdown]
- [Story 25.3: Periodic gate evaluation - evaluate_waiting_gates task]
- [Story 27.1-27.5: Adapters AAP, Tower, Azure, GitHub, Terraform - Polling tasks]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Aucun blocage rencontré.

### Completion Notes List

- **RACE-1 (HIGH):** Ajouté `retry_count` + `MAX_POLLING_RETRIES=20` aux 5 tâches de polling. Helper `_mark_execution_polling_exhausted()` marque execution FAILED + step FAILED + audit `EXECUTION_POLLING_EXHAUSTED`. Retry_count remis à 0 après chaque poll réussi.
- **RACE-2 (MEDIUM):** Ajouté `select_for_update()` dans `update_action()`, `update_status()`, `delete_action()`, `deactivate_action()` — toutes déjà dans `@transaction.atomic`.
- **RACE-3 (MEDIUM):** Option A choisie (documentation). Créé `docs/architecture/caching-strategy.md`, ajouté commentaires dans le code.
- **CELERY-3 (MEDIUM):** Remplacé `asyncio.new_event_loop()` + `set_event_loop()` par `asyncio.run()` dans les 5 tâches de polling.
- **CELERY-4 (MEDIUM):** `_handle_gate_timeout()` implémente la continuation du workflow. SKIPPED → déclenche le step suivant (avec validation du next_step_def). FAILED → marque l'exécution en FAILED.
- **CELERY-5 (LOW):** `error_message = "Gate timeout exceeded after {hours}h"` ajouté pour tous les cas (SKIPPED et FAILED).
- **Tests:** 22 nouveaux tests (5 exhaustion, 3 gate timeout, 4 select_for_update, 3 cache TTL, 3 helpers, 2 max_retries, 2 AAP reschedule) — 77 tests total passent (0 régression).
- **Code Review (auto-fix):** Ajouté validation `next_step_def.get('name')` avant `apply_async` pour éviter crash sur workflows malformés. Documentation ajoutée à git (docs/ non-trackés corrigés).

### Change Log

- 2026-02-16: Story 30.7 implémentée — RACE-1/2/3, CELERY-3/4/5 résolus, 22 tests ajoutés

### File List

- `idp-portal/django_backend/executions/tasks.py` (modifié) — retry_count, MAX_POLLING_RETRIES, asyncio.run(), gate timeout fix, _mark_execution_polling_exhausted
- `idp-portal/django_backend/catalog/services.py` (modifié) — select_for_update() dans 4 méthodes
- `idp-portal/django_backend/core/models.py` (modifié) — AuditActionType.EXECUTION_POLLING_EXHAUSTED
- `idp-portal/django_backend/catalog/views.py` (modifié) — commentaires cache RACE-3
- `idp-portal/django_backend/inventory/services.py` (modifié) — commentaire cache RACE-3
- `idp-portal/django_backend/executions/tests/test_polling_max_retries.py` (nouveau) — 22 tests
- `idp-portal/docs/architecture/caching-strategy.md` (nouveau) — stratégie de cache documentée
- `idp-portal/docs/operations/polling-tasks.md` (nouveau) — documentation limites de retry
- `idp-portal/CODEBASE-REVIEW.md` (modifié) — RACE-1/2/3, CELERY-3/4/5 marqués ✅ RESOLVED
