# Story 38.4: Backend — asyncio.run → async_to_sync (Celery polling)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur backend,
I want remplacer les appels `asyncio.run()` par `async_to_sync()` (asgiref) dans `executions/tasks/polling.py`,
so that les tâches Celery de polling ne créent pas de conflits d'event loop (RuntimeError: This event loop is already running) et suivent le pattern standard du projet.

## Acceptance Criteria

1. **Les deux appels `asyncio.run()` sont remplacés par `async_to_sync()`** — lignes 313 et 320 de `polling.py` utilisent `async_to_sync` au lieu de `asyncio.run`.
2. **L'import `asyncio` est supprimé** — l'import `import asyncio` (ligne 286) n'est plus nécessaire et doit être retiré.
3. **Le pattern est cohérent avec le reste du fichier** — `_broadcast_execution_update()` (ligne 116) utilise déjà `async_to_sync` via `from asgiref.sync import async_to_sync` ; le même import doit être utilisé dans `poll_platform_job_status()`.
4. **Les tests de polling existants passent** — aucune régression dans `executions/tests/test_polling_max_retries.py`.
5. **Pas de régression fonctionnelle** — le comportement du polling (get_status, get_job_logs, re-scheduling, retry, broadcast) reste identique.

## Tasks / Subtasks

- [x] Task 1 — Remplacer `asyncio.run()` par `async_to_sync()` (AC: #1, #2, #3)
  - [x] 1.1 Dans `poll_platform_job_status()` (ligne 286), remplacer `import asyncio` par `from asgiref.sync import async_to_sync`
  - [x] 1.2 Ligne 313 : remplacer `asyncio.run(adapter.get_status(...))` par `async_to_sync(adapter.get_status)(platform_job_id=..., correlation_id=..., **(poll_kwargs or {}))`
  - [x] 1.3 Ligne 320 : remplacer `asyncio.run(adapter.get_job_logs(...))` par `async_to_sync(adapter.get_job_logs)(platform_job_id=..., correlation_id=..., **(poll_kwargs or {}))`
- [x] Task 2 — Vérification et tests (AC: #4, #5)
  - [x] 2.1 Lancer les tests polling : `.venv/bin/python -m pytest executions/tests/test_polling_max_retries.py -v`
  - [x] 2.2 Vérifier que tous les tests passent (0 échec, 0 régression)

## Dev Notes

### Analyse du problème (NEW-BE-4)

**Fichier :** `idp-portal/django_backend/executions/tasks/polling.py` (lignes 286, 313, 320)

La fonction `poll_platform_job_status()` (tâche Celery `@shared_task`) utilise `asyncio.run()` pour appeler les méthodes async des adapters de plateforme :

```python
# Ligne 286
import asyncio

# Ligne 313
status_data = asyncio.run(
    adapter.get_status(
        platform_job_id=platform_job_id,
        correlation_id=correlation_id,
        **(poll_kwargs or {}),
    )
)

# Ligne 320
logs_data = asyncio.run(
    adapter.get_job_logs(
        platform_job_id=platform_job_id,
        correlation_id=correlation_id,
        **(poll_kwargs or {}),
    )
)
```

**Problème :** `asyncio.run()` crée un nouvel event loop et le ferme à chaque appel. Dans un worker Celery (qui peut tourner en mode gevent ou eventlet), cela peut provoquer :
- `RuntimeError: This event loop is already running` si un event loop existe déjà
- Incompatibilité avec certains backends Celery async

**Fix :** Utiliser `async_to_sync()` d'asgiref, qui gère correctement les contextes d'event loop existants. Ce pattern est **déjà utilisé dans le même fichier** (ligne 116, `_broadcast_execution_update`) et dans 5 autres fichiers du backend.

### Pattern cible (déjà utilisé dans le projet)

```python
from asgiref.sync import async_to_sync  # noqa: PLC0415

status_data = async_to_sync(adapter.get_status)(
    platform_job_id=platform_job_id,
    correlation_id=correlation_id,
    **(poll_kwargs or {}),
)
```

**Attention à la syntaxe** : `async_to_sync(coroutine_func)(args)` — deux jeux de parenthèses. `async_to_sync` retourne un callable synchrone, qu'on appelle ensuite avec les arguments.

### Ce qu'il ne faut PAS faire

- **Ne PAS modifier** `_broadcast_execution_update()` — elle utilise déjà `async_to_sync` correctement
- **Ne PAS modifier** les shims backward-compat (lignes 431-564) — ils délèguent à `poll_platform_job_status`
- **Ne PAS ajouter** de changements cosmétiques, refactoring ou commentaires supplémentaires
- **Ne PAS modifier** la logique de retry, broadcast ou update — seul l'appel aux méthodes async change
- **Ne PAS toucher** aux tests — ils mockent les adapters et ne sont pas affectés par le changement sync/async

### Intelligence story précédente (38.3)

- Story 38.3 (NEW-FE-1 frontend) terminée avec succès — correction minimale, 0 régression
- Commit récent : `adb8f83 fix(frontend): remove duplicate key prop on nested TopNav button element (NEW-FE-1)`
- Story 38.1 (backend quick wins) aussi terminée — commit `3195fd7 fix(backend): quick wins N+1, double update, TODO obsolète, log execution_id`
- Pattern tests backend confirmé : pytest + `test_settings`, fichiers dans `tests/` sous chaque app

### Commits récents pertinents

```
adb8f83 fix(frontend): remove duplicate key prop on nested TopNav button element (NEW-FE-1)
0f21a08 refactor(frontend): consolidate duplicate status config into shared execution-status module (SOLID-FE-10)
3195fd7 fix(backend): quick wins N+1, double update, TODO obsolète, log execution_id
```

### Project Structure Notes

- Fichier cible : `idp-portal/django_backend/executions/tasks/polling.py`
- Tests : `idp-portal/django_backend/executions/tests/test_polling_max_retries.py`
- Python venv : `.venv/bin/python`
- Test runner : `.venv/bin/python -m pytest` (depuis `django_backend/`)
- Test settings : `idp_backend.test_settings` (via pytest.ini)
- Dépendance : `asgiref` (déjà installé — requis par Django)

### Fichiers du projet utilisant async_to_sync (référence)

- `executions/tasks/polling.py:116` — `_broadcast_execution_update()` (même fichier)
- `executions/views/execution_views.py:579`
- `executions/views/github_webhooks.py:249`
- `executions/views/terraform_webhooks.py:256`
- `executions/workflow_step_executor.py:398`
- `integrations/views.py:8`

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §17 Audit #3 — NEW-BE-4 asyncio.run dans polling.py]
- [Source: _bmad-output/planning-artifacts/epic-38-codebase-review-audit-3-corrections.md — Story 38.4]
- [Source: idp-portal/django_backend/executions/tasks/polling.py — lignes 286, 313, 320]
- [Source: idp-portal/django_backend/executions/tests/test_polling_max_retries.py — tests polling]
- [Source: _bmad-output/implementation-artifacts/38-3-frontend-nested-key-props-topnav.md — story précédente]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Aucun problème rencontré.

### Completion Notes List

- ✅ Remplacé `import asyncio` par `from asgiref.sync import async_to_sync` dans `poll_platform_job_status()` (ligne 286)
- ✅ Remplacé `asyncio.run(adapter.get_status(...))` par `async_to_sync(adapter.get_status)(...)` (ligne 313)
- ✅ Remplacé `asyncio.run(adapter.get_job_logs(...))` par `async_to_sync(adapter.get_job_logs)(...)` (ligne 318-322)
- ✅ Pattern cohérent avec `_broadcast_execution_update()` (ligne 116) qui utilise déjà `async_to_sync`
- ✅ 22/22 tests polling passent sans régression
- ✅ Aucune modification hors du scope (pas de refactoring, pas de changement cosmétique)

### File List

- `idp-portal/django_backend/executions/tasks/polling.py` — modifié (asyncio.run → async_to_sync)
- `idp-portal/django_backend/executions/tests/test_polling_max_retries.py` — modifié (docstring CELERY-3 mise à jour, review M1)

## Change Log

| Date | Changement | Auteur |
|------|-----------|--------|
| 2026-02-23 | Implémentation : remplacement asyncio.run → async_to_sync dans poll_platform_job_status(), 22/22 tests passent | Claude Opus 4.6 |
| 2026-02-23 | Code review : 0H 1M 2L trouvés. M1 fixé (docstring test CELERY-3 obsolète), L1 fixé (numéro de ligne completion notes), L2 noté (import dupliqué — pattern existant, pas de fix). Status → done | Claude Opus 4.6 |
