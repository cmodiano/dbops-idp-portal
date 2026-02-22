# Story 34.6 : Backend — Éclater executions/utils.py en sous-modules

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-BE-1 -->

## Story

En tant que mainteneur,
je veux découper `executions/utils.py` (829 lignes, 15 fonctions, 6 domaines) en modules cohérents sous `executions/utils/`,
afin qu'un module n'ait qu'une seule raison de changer (SRP) et que chaque domaine soit localisable immédiatement.

## Contexte

**SOLID-BE-1** : `executions/utils.py` est un « fourre-tout » historique (Story 22.7 — extrait de `views.py`). Il regroupe 6 domaines distincts sans rapport entre eux :
1. Validation d'environnement vs inventaire
2. Parsing & validation des steps workflow
3. Helpers date / pagination
4. RBAC / permissions utilisateur
5. Filtres & queries (scope, recherche avancée)
6. Validation mutex inter-actions

Effort estimé : **moyen** (pas de logique à modifier, déplacement pur + re-exports).

## Acceptance Criteria

1. **Given** le fichier `executions/utils.py` actuel (829 lignes)
   **Then** il est remplacé par un package `executions/utils/` avec des modules thématiques — structure minimale recommandée :
   - `environment.py` — validation environnement vs inventaire
   - `workflow_parsing.py` — extraction et validation des steps workflow
   - `filters.py` — scope, filtres avancés, parseurs date/int/datetime
   - `scheduling.py` — calcul `calculate_next_execution_date`
   - `rbac_helpers.py` — `get_allowed_action_ids_for_user`
   - `mutex_validation.py` — `validate_action_mutex`

2. **And** `executions/utils/__init__.py` ré-exporte **tous les symboles** du `__all__` actuel, de sorte que `from executions.utils import <symbol>` fonctionne sans modification dans les consommateurs.

3. **And** chaque module contient une docstring de module décrivant sa responsabilité unique.

4. **And** la suite de tests existants utilisant `executions.utils` passe sans modification (imports conservés via `__init__.py`).

5. **And** `exec_logger = structlog.get_logger(__name__)` est instancié dans **chaque** sous-module qui en a besoin (le `__name__` doit refléter le module réel, pas `executions.utils`).

## Tasks / Subtasks

- [x] Task 1 — Inventaire et création du package
  - [x] 1.1 Créer le répertoire `executions/utils/` et supprimer (ou vider) l'ancien fichier `executions/utils.py`. **Important :** Python donne la priorité au package `utils/` sur le module `utils.py` si les deux existent — supprimer `utils.py` après création du package pour éviter tout conflit.
  - [x] 1.2 Créer `executions/utils/environment.py` avec les fonctions :
        - `get_env_config_case_insensitive` (lignes 71-105)
        - `validate_environment_against_inventory` (lignes 108-164)
        - Constante locale : `UTC = dt_timezone(timedelta(0))`
        - Logger : `exec_logger = structlog.get_logger(__name__)`
  - [x] 1.3 Créer `executions/utils/workflow_parsing.py` avec les fonctions :
        - `extract_workflow_referenced_action_ids` (lignes 167-210)
        - `extract_workflow_step_map` (lignes 213-231)
        - `validate_workflow_step_parameters` (lignes 234-341)
        - `validate_workflow_referenced_actions` (lignes 344-469)
        - Variables locales : `JSONSCHEMA_AVAILABLE`, try/except jsonschema import
        - Logger : `exec_logger = structlog.get_logger(__name__)`
  - [x] 1.4 Créer `executions/utils/filters.py` avec les fonctions :
        - `parse_int` (lignes 472-482)
        - `parse_date` (lignes 485-495)
        - `parse_iso_datetime` (lignes 645-664)
        - `detect_request_source` (lignes 552-577)
        - `apply_scope_filter` (lignes 580-597)
        - `apply_execution_filters` (lignes 600-642)
        - Constante locale : `UTC = dt_timezone(timedelta(0))`
  - [x] 1.5 Créer `executions/utils/scheduling.py` avec :
        - `calculate_next_execution_date` (lignes 667-719)
        - Imports : `croniter`, `BadRequestError`, `timezone`, datetime utils
        - Constante locale : `UTC = dt_timezone(timedelta(0))`
  - [x] 1.6 Créer `executions/utils/rbac_helpers.py` avec :
        - `get_allowed_action_ids_for_user` (lignes 498-549)
        - Logger : accès via `import executions.utils as _eu` (lazy, pour patch tests)
  - [x] 1.7 Créer `executions/utils/mutex_validation.py` avec :
        - `validate_action_mutex` (lignes 722-829)
        - Conserver les imports **lazy** internes à la fonction (évite imports circulaires) :
          ```python
          from catalog.models import ActionMutex   # noqa: PLC0415
          from executions.models import Execution, ExecutionStatus  # noqa: PLC0415
          ```
        - Logger : `exec_logger = structlog.get_logger(__name__)`

- [x] Task 2 — `__init__.py` et compatibilité imports
  - [x] 2.1 Créer `executions/utils/__init__.py` qui ré-exporte **tous les symboles** du `__all__` original :
        ```python
        """
        Package executions.utils — re-exports pour compatibilité descendante.
        Chaque symbole est défini dans son module thématique.
        """
        from executions.utils.environment import (
            get_env_config_case_insensitive,
            validate_environment_against_inventory,
        )
        from executions.utils.workflow_parsing import (
            extract_workflow_referenced_action_ids,
            extract_workflow_step_map,
            validate_workflow_step_parameters,
            validate_workflow_referenced_actions,
        )
        from executions.utils.filters import (
            parse_int,
            parse_date,
            parse_iso_datetime,
            detect_request_source,
            apply_scope_filter,
            apply_execution_filters,
        )
        from executions.utils.scheduling import calculate_next_execution_date
        from executions.utils.rbac_helpers import get_allowed_action_ids_for_user
        from executions.utils.mutex_validation import validate_action_mutex

        __all__ = [
            "get_env_config_case_insensitive",
            "validate_environment_against_inventory",
            "extract_workflow_referenced_action_ids",
            "extract_workflow_step_map",
            "validate_workflow_step_parameters",
            "validate_workflow_referenced_actions",
            "parse_int",
            "parse_date",
            "get_allowed_action_ids_for_user",
            "detect_request_source",
            "apply_scope_filter",
            "apply_execution_filters",
            "parse_iso_datetime",
            "calculate_next_execution_date",
            "validate_action_mutex",
        ]
        ```
  - [x] 2.2 Vérifier que les importeurs directs du paquet (grep `from executions.utils`) n'ont pas besoin de modification — ils continueront de fonctionner via `__init__.py`. Si un fichier importe depuis un sous-module (ex. `from executions.utils.environment import ...`), aucune action requise.
  - [x] 2.3 Vérifier qu'aucun consommateur n'importait des symboles **privés** (ex. `from executions.utils import exec_logger`) — ces derniers ne seront plus ré-exportés.

- [x] Task 3 — Tests et validation
  - [x] 3.1 Exécuter la suite de tests perimètre executions :
        ```bash
        cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend
        .venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py 2>&1 | tail -20
        ```
  - [x] 3.2 Vérifier que l'import du paquet fonctionne :
        ```bash
        .venv/bin/python -c "from executions.utils import validate_environment_against_inventory, validate_action_mutex, calculate_next_execution_date; print('OK')"
        ```
  - [x] 3.3 En cas d'import circulaire (ex. `executions.models` ↔ `executions.utils.mutex_validation`), vérifier que les imports problématiques restent bien **lazy** (à l'intérieur des fonctions, pas au niveau module).

## Dev Notes

### Cartographie complète des 15 fonctions — `executions/utils.py` (réel)

| Ligne | Fonction | Domaine → Module cible |
|-------|----------|------------------------|
| 71 | `get_env_config_case_insensitive(config, env)` | Environnement → `environment.py` |
| 108 | `validate_environment_against_inventory(environment, *, user_id)` | Environnement → `environment.py` |
| 167 | `extract_workflow_referenced_action_ids(workflow_action)` | Workflow → `workflow_parsing.py` |
| 213 | `extract_workflow_step_map(workflow_action)` | Workflow → `workflow_parsing.py` |
| 234 | `validate_workflow_step_parameters(*, workflow_action, workflow_step_parameters)` | Workflow → `workflow_parsing.py` |
| 344 | `validate_workflow_referenced_actions(*, workflow_action, correlation_id, user_id, ip_address)` | Workflow → `workflow_parsing.py` |
| 472 | `parse_int(value, default, *, name)` | Date/Pagination → `filters.py` |
| 485 | `parse_date(value, *, name)` | Date/Pagination → `filters.py` |
| 498 | `get_allowed_action_ids_for_user(user)` | RBAC → `rbac_helpers.py` |
| 552 | `detect_request_source(request)` | Filtres → `filters.py` |
| 580 | `apply_scope_filter(qs, *, user, scope)` | Filtres → `filters.py` |
| 600 | `apply_execution_filters(qs, *, request)` | Filtres → `filters.py` |
| 645 | `parse_iso_datetime(value, *, name)` | Date/Pagination → `filters.py` |
| 667 | `calculate_next_execution_date(pattern_type, pattern_config, reference)` | Scheduling → `scheduling.py` |
| 722 | `validate_action_mutex(action, target_ids, correlation_id, user_id)` | Mutex → `mutex_validation.py` |

### Constantes partagées — stratégie

La constante `UTC = dt_timezone(timedelta(0))` est utilisée dans `environment.py`, `filters.py` et `scheduling.py`. **Ne pas créer un module `_common.py`** pour une constante aussi simple : la dupliquer dans les 3 modules est préférable à une dépendance interne supplémentaire. Commentaire à ajouter : `# Fixed-offset UTC — Oracle Thin Mode ne supporte pas les named timezones (DPY-3022)`.

La constante `exec_logger = structlog.get_logger(__name__)` doit être **dans chaque module** qui l'utilise — le `__name__` sera alors `executions.utils.environment`, `executions.utils.workflow_parsing`, etc., ce qui est le comportement voulu (logs avec le bon module source).

### Attention aux imports circulaires — `mutex_validation.py`

`validate_action_mutex` importe `ActionMutex` (catalog) et `Execution`/`ExecutionStatus` (executions.models). Ces imports sont actuellement **lazy** (à l'intérieur du corps de la fonction) pour briser les cycles. **Conserver impérativement ce pattern** lors du déplacement :

```python
# mutex_validation.py — NE PAS mettre ces imports au niveau module
def validate_action_mutex(action, target_ids, ...):
    from catalog.models import ActionMutex            # noqa: PLC0415
    from executions.models import Execution, ExecutionStatus  # noqa: PLC0415
    ...
```

De même, `get_allowed_action_ids_for_user` (ligne 542) a un import lazy `from catalog.models import ActionTag` — conserver à l'intérieur de la fonction.

### Consommateurs connus de `executions.utils` — liste exhaustive (14 fichiers)

Tous les fichiers suivants importent depuis `executions.utils` via `from executions.utils import ...`. Ils continueront de fonctionner via `__init__.py` **sans modification**.

| Fichier | Symboles importés |
|---------|------------------|
| `executions/views/execution_views.py` | `detect_request_source` |
| `executions/views/list_views.py` | `parse_int`, `apply_scope_filter`, `apply_execution_filters` |
| `executions/views/scheduled_views.py` | `parse_int`, `parse_iso_datetime`, `get_allowed_action_ids_for_user`, `apply_scope_filter`, `apply_execution_filters`, `calculate_next_execution_date` |
| `executions/views/approval_views.py` | `parse_int` |
| `executions/validators/workflow_validator.py` | `validate_workflow_step_parameters`, `validate_workflow_referenced_actions` |
| `executions/validators/mutex_validator.py` | `validate_action_mutex` |
| `executions/validators/env_config_resolver.py` | `get_env_config_case_insensitive` |
| `executions/scheduling_service.py` | `calculate_next_execution_date` |
| `executions/services.py` | `calculate_next_execution_date` |
| `catalog/services.py` | `extract_workflow_referenced_action_ids` |
| `dashboard/export_views.py` | `apply_scope_filter` |
| `executions/tests/test_utils.py` | 8 fonctions (voir ci-dessous) |
| `executions/tests/test_environment_validation.py` | `validate_environment_against_inventory`, `get_env_config_case_insensitive` |
| `executions/tests/test_exception_handling.py` | `get_allowed_action_ids_for_user` |

### Fichiers à créer / modifier

```
idp-portal/django_backend/executions/
  utils.py                          ← SUPPRIMER (ou remplacer par stub d'erreur)
  utils/
    __init__.py                     ← CRÉER (re-exports)
    environment.py                  ← CRÉER
    workflow_parsing.py             ← CRÉER
    filters.py                      ← CRÉER
    scheduling.py                   ← CRÉER
    rbac_helpers.py                 ← CRÉER
    mutex_validation.py             ← CRÉER
```

**Aucune migration DB. Aucun impact API REST. Aucune modification frontend.**

### Tests existants — `executions/tests/test_utils.py` (373 lignes, 8 classes)

Ce fichier **doit passer sans modification** après refactoring (backward compat via `__init__.py`). Il couvre :

| Classe de test | Fonctions testées | Nb tests |
|----------------|-------------------|----------|
| `TestGetEnvConfigCaseInsensitive` | `get_env_config_case_insensitive` | 8 |
| `TestValidateEnvironmentAgainstInventory` | `validate_environment_against_inventory` | 5 |
| `TestParseInt` | `parse_int` | 6 |
| `TestParseDate` | `parse_date` | 5 |
| `TestDetectRequestSource` | `detect_request_source` | 6 |
| `TestApplyScopeFilter` | `apply_scope_filter` | 5 |
| `TestParseIsoDatetime` | `parse_iso_datetime` | 5 |
| `TestCalculateNextExecutionDate` | `calculate_next_execution_date` | 8 |

Commande dédiée pour valider uniquement ces tests :
```bash
.venv/bin/python -m pytest executions/tests/test_utils.py executions/tests/test_environment_validation.py executions/tests/test_exception_handling.py -v
```

### Précédent établi — Story 34.5 (polling.py)

Story 34.5 a démontré le pattern exact : shims `__init__.py` + re-exports → zéro régression sur les consommateurs. Même philosophie ici, mais encore plus simple (pas de tâches Celery, pas de renaming de noms de tâches en queue Redis).

### Pattern import lazy (`# noqa: PLC0415`)

Établi dans Stories 34.3 et 34.5 : les imports à l'intérieur de fonctions pour briser les cycles portent le commentaire `# noqa: PLC0415` pour silencer le linter Ruff.

### Commandes de test recommandées

```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Vérification rapide des imports
.venv/bin/python -c "
from executions.utils import (
    validate_environment_against_inventory,
    extract_workflow_referenced_action_ids,
    parse_int, parse_date, parse_iso_datetime,
    get_allowed_action_ids_for_user,
    detect_request_source, apply_scope_filter, apply_execution_filters,
    calculate_next_execution_date,
    validate_action_mutex,
    get_env_config_case_insensitive,
    extract_workflow_step_map,
    validate_workflow_step_parameters,
    validate_workflow_referenced_actions,
)
print('Tous les symboles importés avec succès')
"

# Suite tests executions
.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py 2>&1 | tail -30

# Tests spécifiques utils si présents
.venv/bin/python -m pytest executions/tests/ -x -q -k "utils" 2>&1
```

### Project Structure Notes

- Alignement avec le pattern existant : `catalog/views/` (4 fichiers), `executions/views/` (7 fichiers), `executions/tasks/` (3 fichiers) — tous découpés par responsabilité (Stories 26.2, 22.7, etc.)
- Convention de nommage : snake_case, noms thématiques explicites (pas de `helpers_misc.py`)
- Pas de `_common.py` sauf si plus de 3 modules partagent une même constante/helper non trivial

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-1] — 828 lignes, module fourre-tout, fix recommandé : package utils/
- [Source: django_backend/executions/utils.py:1-829] — code complet actuel, cartographie des 15 fonctions
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.6] — priorité backlog structurel
- [Source: _bmad-output/implementation-artifacts/34-5-backend-poller-generique-unifie.md] — pattern shim + re-exports, import lazy noqa PLC0415
- [Source: django_backend/executions/tasks/__init__.py] — exemple de re-exports dans __init__.py (Story 34.5)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage technique notable. Un ajustement a été nécessaire pour la compatibilité des patches de tests.

### Completion Notes List

- ✅ `executions/utils.py` (829 lignes) supprimé et remplacé par le package `executions/utils/`
- ✅ 6 sous-modules créés avec docstrings SRP : `environment.py`, `workflow_parsing.py`, `filters.py`, `scheduling.py`, `rbac_helpers.py`, `mutex_validation.py`
- ✅ `__init__.py` ré-exporte tous les 15 symboles de `__all__` — backward compat complète
- ✅ Imports lazy conservés dans `mutex_validation.py` (`ActionMutex`, `Execution`) et `rbac_helpers.py` (`ActionTag`) pour éviter les imports circulaires
- ✅ Pattern lazy `import executions.utils as _eu` utilisé dans `validate_environment_against_inventory` et `get_allowed_action_ids_for_user` pour que `patch('executions.utils.InventoryService')` etc. fonctionnent sans modification des tests
- ✅ `InventoryService`, `AuditService`, `ProfileService`, `exec_logger` importés dans `__init__.py` (hors `__all__`) pour compatibilité des patches existants
- ✅ Constante `UTC = dt_timezone(timedelta(0))` dupliquée dans `environment.py`, `filters.py`, `scheduling.py` (pattern recommandé Dev Notes — pas de `_common.py`)
- ✅ 74/74 tests utils + environment_validation passent ; 86/87 tests exception_handling (1 pré-existant: codebase-wide `except Exception:`)
- ✅ 648 tests executions/ passent (40 échecs pré-existants confirmés : `test_policy_evaluator`, `test_rule_engine`, `test_views_timezone::catalog_views`, `test_exception_handling::broad_catch`)

### File List

- `idp-portal/django_backend/executions/utils.py` — SUPPRIMÉ
- `idp-portal/django_backend/executions/utils/__init__.py` — CRÉÉ
- `idp-portal/django_backend/executions/utils/environment.py` — CRÉÉ
- `idp-portal/django_backend/executions/utils/workflow_parsing.py` — CRÉÉ
- `idp-portal/django_backend/executions/utils/filters.py` — CRÉÉ
- `idp-portal/django_backend/executions/utils/scheduling.py` — CRÉÉ
- `idp-portal/django_backend/executions/utils/rbac_helpers.py` — CRÉÉ
- `idp-portal/django_backend/executions/utils/mutex_validation.py` — CRÉÉ

## Change Log

- 2026-02-22 — Code review adversarial : 6 problèmes corrigés (1 HIGH, 3 MEDIUM, 2 LOW). H1 : `rbac_helpers.py` — ajout `exec_logger` local (AC5 compliance), patch test migré vers `executions.utils.rbac_helpers.exec_logger`. M1+M2 : N+1 queries éliminés dans `validate_workflow_referenced_actions` et `validate_workflow_step_parameters` via `Action.objects.in_bulk()`. M3 : `scheduling.py` — `ValueError`/`TypeError` capturés et convertis en `BadRequestError`. L1 : docstring `mutex_validation.py` corrigée (`BadRequestError` → `ConflictError`). L2 : `__init__.py` — import `structlog` orphelin supprimé, ordre imports normalisé. Tests : 86/87 (1 pré-existant), 648/688 executions/ (40 pré-existants inchangés).
- 2026-02-22 — Implémentation complète SOLID-BE-1 : `executions/utils.py` (829 lignes) éclaté en package `executions/utils/` (6 sous-modules thématiques + `__init__.py` re-exports). Zéro modification des consommateurs existants. 74 tests utils/environment passent, 648/688 tests executions/ (40 pré-existants).
