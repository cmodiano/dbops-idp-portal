# Story 26.16 : Enforcer mypy sur tout le codebase + hook pre-commit

Status: done

## Story

En tant que **développeur**,
je veux **appliquer le typage mypy sur l'intégralité du backend Django et configurer un hook pre-commit qui bloque les commits en cas d'erreur**,
afin de **garantir la qualité des types, détecter les erreurs tôt et éviter les régressions**.

## Acceptance Criteria

### AC1 - Baseline mypy réduit à 0
- **Given** la baseline mypy actuelle est de 29 erreurs (après Story 22.19)
- **When** les corrections de type sont appliquées
- **Then** 0 erreur mypy (baseline supprimée ou à 0)
- **And** les ~80 erreurs actuelles (régression depuis 22.19 : 29 → 80) sont corrigées
- **And** le fichier `.mypy-baseline-count` contient 0 ou est supprimé

### AC2 - Mode strict activé sur modules principaux
- **Given** les modules `core/`, `idp_auth/`, `executions/`, `catalog/`, `inventory/` sont les modules principaux
- **When** la configuration mypy est mise à jour
- **Then** `disallow_untyped_defs = true` est activé sur ces modules dans pyproject.toml
- **And** mypy ne génère aucune erreur sur ces modules

### AC3 - Hook pre-commit bloquant configuré
- **Given** le fichier `.pre-commit-config.yaml` existe déjà avec mypy
- **When** un développeur fait un commit avec des erreurs mypy
- **Then** le hook pre-commit bloque le commit et affiche les erreurs
- **And** le hook est documenté dans README.md (installation `pre-commit install`)

### AC4 - CI mypy en mode bloquant
- **Given** le job CI typecheck-backend existe ou doit être créé
- **When** la CI exécute mypy
- **Then** mypy s'exécute en mode bloquant (sans `continue-on-error`)
- **And** le job échoue si des erreurs mypy sont détectées
- **And** le script `check_mypy_baseline.sh` est adapté pour mode strict (pas de tolérance)

### AC5 - Mécanisme baseline obsolète
- **Given** le mécanisme baseline a été utilisé en Phase 1 et 2
- **When** la baseline atteint 0
- **Then** le fichier `.mypy-baseline-count` est supprimé ou contient 0
- **And** les scripts `generate_mypy_baseline.sh` et `check_mypy_baseline.sh` sont supprimés ou adaptés pour mode strict
- **And** la CI n'utilise plus de tolérance baseline

### AC6 - Documentation mise à jour
- **Given** les documents `docs/mypy-improvement-roadmap.md` et `docs/mypy-developer-guide.md` existent
- **When** la Phase 4 est complétée
- **Then** `docs/mypy-improvement-roadmap.md` est mis à jour avec statut Phase 4 complété (date 2026-02-13)
- **And** `docs/mypy-developer-guide.md` reflète le mode strict activé

### AC7 - Aucune régression des tests
- **Given** tous les tests pytest passent actuellement
- **When** les corrections mypy sont appliquées
- **Then** 100% des tests backend passent sans régression
- **And** aucune nouvelle erreur mypy n'est introduite

## Tasks / Subtasks

### Task 1: Analyser et corriger les ~80 erreurs mypy actuelles (AC: #1, #2)

- [x] Subtask 1.1: Générer rapport mypy détaillé et classifier les erreurs
  - Exécuter `source .venv/bin/activate && mypy . --no-error-summary > mypy-full-report.txt`
  - Classifier par type d'erreur : no-any-return, override, misc, arg-type, assignment, unreachable
  - Classifier par module : core/, reference/, profiles/, inventory/, executions/, catalog/

- [x] Subtask 1.2: Corriger erreurs dans core/environment.py (1 erreur)
  - `core/environment.py:132: error: Returning Any from function declared to return "dict[Any, Any] | None"`
  - Ajouter cast explicite ou typer précisément le retour

- [x] Subtask 1.3: Corriger erreurs dans idp_backend/celery.py (2 erreurs)
  - `idp_backend/celery.py:44: error: Unexpected keyword argument "crontab" for "warning"` (x2)
  - Corriger appel au logger structlog

- [x] Subtask 1.4: Corriger erreurs dans reference/models.py (6 erreurs)
  - Erreurs `override` : signatures des méthodes `ordered()` incompatibles avec QuerySet
  - Erreurs `misc` : `Unsupported dynamic base class "models.Manager.from_queryset"`
  - Utiliser `# type: ignore[misc]` ciblé pour `from_queryset` (limitation django-stubs)
  - Corriger signatures `ordered()` pour correspondre à QuerySet

- [x] Subtask 1.5: Corriger erreurs dans profiles/models.py (1 erreur)
  - `profiles/models.py:300: error: Returning Any from function declared to return "dict[str, list[str]] | None"`
  - Ajouter cast explicite ou typer le retour

- [x] Subtask 1.6: Corriger erreurs dans inventory/ (14 erreurs)
  - `inventory/rbac_filter.py` : arg-type (2 erreurs) — vérifier None vs str
  - `inventory/source_resolver.py` : no-any-return (2 erreurs) — typer retours Integration
  - `inventory/serializers.py` : assignment (3 erreurs) — incompatibilité types Serializer
  - `inventory/mapper.py` : no-any-return (3 erreurs) — typer retours str
  - `inventory/query_executor.py` : attr-defined + assignment (3 erreurs) — import connection, type int vs str

- [x] Subtask 1.7: Corriger erreurs dans executions/ (9 erreurs)
  - `executions/gate_context.py` : unreachable (1 erreur) — supprimer code mort
  - `executions/models.py` : no-any-return (1 erreur) — typer retour dict
  - `executions/simulation_service.py` : misc + operator + attr-defined (6 erreurs) — typer objets correctement

- [x] Subtask 1.8: Corriger erreurs dans catalog/models.py (1 erreur)
  - `catalog/models.py:120: error: Unsupported dynamic base class "models.Manager.from_queryset"`
  - Utiliser `# type: ignore[misc]` ciblé (limitation django-stubs)

- [x] Subtask 1.9: Vérifier baseline à 0
  - Exécuter `mypy . --no-error-summary 2>&1 | grep ": error:" | wc -l`
  - Vérifier count = 0
  - Mettre à jour `.mypy-baseline-count` à 0 ou supprimer le fichier

### Task 2: Activer mode strict sur modules principaux (AC: #2)

- [x] Subtask 2.1: Ajouter overrides pyproject.toml pour modules principaux
  ```toml
  [[tool.mypy.overrides]]
  module = [
    "core.*",
    "idp_auth.*",
    "executions.*",
    "catalog.*",
    "inventory.*",
    "profiles.*",
    "reference.*",
  ]
  disallow_untyped_defs = true
  ```

- [x] Subtask 2.2: Valider que mypy passe avec les nouveaux overrides
  - Exécuter `mypy .` et vérifier 0 erreur
  - Si des erreurs apparaissent, les corriger ou ajuster les overrides

### Task 3: Rendre le hook pre-commit bloquant (AC: #3)

- [x] Subtask 3.1: Vérifier configuration actuelle `.pre-commit-config.yaml`
  - Le hook mypy existe déjà (Story 17.9)
  - Vérifier que `args: [--config-file=pyproject.toml, --no-error-summary]` est présent
  - Aucun changement nécessaire si déjà bloquant

- [x] Subtask 3.2: Documenter installation du hook dans README.md
  - Ajouter section "Pre-commit hooks" dans `idp-portal/django_backend/README.md`
  ```markdown
  ## Pre-commit hooks

  Le projet utilise pre-commit pour valider la qualité du code avant chaque commit.

  ### Installation (une seule fois)

  ```bash
  cd idp-portal/django_backend
  pre-commit install
  ```

  ### Hooks configurés
  - **mypy** : vérification de type statique (bloquant)

  ### Exécuter manuellement

  ```bash
  pre-commit run --all-files
  ```

  ### Bypasser (déconseillé)

  ```bash
  git commit --no-verify
  ```
  ```

- [x] Subtask 3.3: Tester le hook pre-commit
  - Créer une modification avec une erreur mypy volontaire
  - Tenter un commit
  - Vérifier que le commit est bloqué avec message d'erreur mypy
  - Corriger l'erreur et vérifier que le commit passe

### Task 4: Configurer CI mypy en mode bloquant (AC: #4)

- [x] Subtask 4.1: Créer ou mettre à jour le job CI typecheck-backend
  - Vérifier si un workflow `.github/workflows/` existe avec mypy
  - Si non, créer `.github/workflows/typecheck.yml` :
  ```yaml
  name: Type Check Backend

  on:
    push:
      branches: [main, develop]
    pull_request:
      branches: [main, develop]

  jobs:
    typecheck-backend:
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: idp-portal/django_backend
      steps:
        - uses: actions/checkout@v4

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: '3.12'

        - name: Install dependencies
          run: |
            python -m pip install --upgrade pip
            pip install -r requirements-dev.lock

        - name: Run mypy type check
          run: |
            mypy . --no-error-summary
  ```

- [x] Subtask 4.2: Adapter script check_mypy_baseline.sh pour mode strict
  - **Option A** : Supprimer le script (plus nécessaire)
  - **Option B** : Adapter pour vérifier que baseline = 0 et bloquer si > 0
  - Recommandation : supprimer `scripts/check_mypy_baseline.sh` et `scripts/generate_mypy_baseline.sh`

- [x] Subtask 4.3: Valider CI en mode bloquant
  - Pousser une branche de test avec le workflow CI
  - Vérifier que le job typecheck-backend passe avec 0 erreur
  - Introduire volontairement une erreur mypy et vérifier que CI échoue

### Task 5: Nettoyer mécanisme baseline obsolète (AC: #5)

- [x] Subtask 5.1: Supprimer ou mettre à jour .mypy-baseline-count
  - **Option A** : Supprimer le fichier `.mypy-baseline-count`
  - **Option B** : Mettre à jour à 0 et conserver pour historique
  - Recommandation : supprimer le fichier (plus nécessaire)

- [x] Subtask 5.2: Supprimer scripts baseline
  - Supprimer `scripts/check_mypy_baseline.sh`
  - Supprimer `scripts/generate_mypy_baseline.sh`
  - Mettre à jour documentation qui référence ces scripts

- [x] Subtask 5.3: Mettre à jour CI pour ne plus utiliser check_mypy_baseline.sh
  - Si un workflow CI référence `scripts/check_mypy_baseline.sh`, le mettre à jour
  - Remplacer par `mypy . --no-error-summary` direct

### Task 6: Mettre à jour documentation (AC: #6)

- [x] Subtask 6.1: Mettre à jour docs/mypy-improvement-roadmap.md
  - Marquer Phase 4 comme complétée
  - Ajouter date de complétion : 2026-02-13
  - Documenter résultat : baseline 29 → 0, mode strict activé

- [x] Subtask 6.2: Mettre à jour docs/mypy-developer-guide.md
  - Supprimer section baseline (obsolète)
  - Mettre à jour commandes :
    - Remplacer `scripts/check_mypy_baseline.sh` par `mypy .`
    - Supprimer référence à `scripts/generate_mypy_baseline.sh`
  - Ajouter note : "Mode strict activé — toute erreur mypy bloque le commit et la CI"

- [x] Subtask 6.3: Mettre à jour README.md principal
  - Ajouter badge CI typecheck si applicable
  - Documenter pre-commit hook mypy

### Task 7: Tests et validation finale (AC: #7)

- [x] Subtask 7.1: Exécuter tous les tests pytest
  - `pytest` dans django_backend/
  - Vérifier 100% pass rate (aucune régression)

- [x] Subtask 7.2: Exécuter mypy en mode strict
  - `mypy .`
  - Vérifier 0 erreur

- [x] Subtask 7.3: Tester pre-commit hook
  - Créer commit avec erreur mypy → bloqué
  - Créer commit sans erreur → passe

- [x] Subtask 7.4: Tester CI
  - Pousser branche → CI passe
  - Pousser branche avec erreur mypy → CI échoue

## Dev Notes

### Contexte Projet

**Projet** : IDP Portal — Portail interne d'automatisation DB (Django 5.2 + DRF 3.16 backend, React + Ant Design frontend)

**Working directory** : `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend`

**Python environment** : `.venv/bin/python` (Python 3.12)

### Historique mypy

Cette story complète les **Phases 1 et 2** du roadmap mypy :

1. **Story 17.9 (Phase 1)** : Configuration mypy baseline (89 erreurs), pre-commit hook, CI bloquant sur nouvelles erreurs
2. **Story 22.19 (Phase 2)** : Réduction baseline 89 → 29 erreurs (-67%)
3. **Story 26.16 (Phase 4)** : Baseline 0, mode strict complet

**État actuel** : 80 erreurs mypy (régression depuis Phase 2, probablement due aux stories 26.1-26.15)

**Objectif** : 0 erreur, mode strict, hook pre-commit bloquant, CI bloquant

### Types d'erreurs à corriger

Analyse du rapport mypy actuel (80 erreurs) :

| Type d'erreur | Count | Exemple |
|---------------|-------|---------|
| `no-any-return` | ~10 | Fonction retourne Any au lieu d'un type précis |
| `override` | ~3 | Signature méthode incompatible avec parent (QuerySet) |
| `misc` | ~8 | `Unsupported dynamic base class` (Manager.from_queryset) |
| `arg-type` | ~4 | Argument de mauvais type (None vs str) |
| `assignment` | ~5 | Type incompatible dans assignation |
| `unreachable` | ~1 | Code mort (supprimer) |
| `call-arg` | ~2 | Argument inattendu (logger structlog) |
| `attr-defined` | ~3 | Attribut inexistant ou import manquant |
| `operator` | ~1 | Opération sur None |

### Patterns de correction

**Pattern 1 : no-any-return**
```python
# AVANT (erreur mypy)
def get_config() -> dict[Any, Any] | None:
    return some_dynamic_call()  # error: Returning Any

# APRÈS (corrigé)
def get_config() -> dict[Any, Any] | None:
    result = some_dynamic_call()
    return cast(dict[Any, Any] | None, result)
```

**Pattern 2 : override (QuerySet.ordered)**
```python
# AVANT (erreur mypy)
class EngineQuerySet(models.QuerySet):
    def ordered(self):
        return self.order_by("name")

# APRÈS (corrigé)
class EngineQuerySet(models.QuerySet["Engine"]):
    def ordered(self) -> "QuerySet[Engine]":
        return self.order_by("name")
```

**Pattern 3 : misc (Manager.from_queryset)**
```python
# AVANT (erreur mypy)
class EngineManager(models.Manager.from_queryset(EngineQuerySet)):
    pass

# APRÈS (corrigé — limitation django-stubs)
class EngineManager(models.Manager.from_queryset(EngineQuerySet)):  # type: ignore[misc]
    pass
```

**Pattern 4 : arg-type (None vs str)**
```python
# AVANT (erreur mypy)
def process(entity_type: str | None):
    apply_filter(entity_type)  # error: arg-type (attend str)

# APRÈS (corrigé)
def process(entity_type: str | None):
    if entity_type is not None:
        apply_filter(entity_type)
```

### Fichiers principaux à modifier

| Fichier | Erreurs | Action |
|---------|---------|--------|
| `core/environment.py` | 1 | Cast no-any-return |
| `idp_backend/celery.py` | 2 | Corriger appel logger |
| `reference/models.py` | 6 | Override + type: ignore[misc] |
| `profiles/models.py` | 1 | Cast no-any-return |
| `inventory/rbac_filter.py` | 2 | Check None avant appel |
| `inventory/source_resolver.py` | 2 | Typer retours Integration |
| `inventory/serializers.py` | 3 | Corriger types Serializer |
| `inventory/mapper.py` | 3 | Typer retours str |
| `inventory/query_executor.py` | 3 | Import + types |
| `executions/gate_context.py` | 1 | Supprimer code mort |
| `executions/models.py` | 1 | Cast no-any-return |
| `executions/simulation_service.py` | 6 | Typer objets |
| `catalog/models.py` | 1 | type: ignore[misc] |

**Total** : ~13 fichiers à corriger

### Configuration mypy actuelle (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.12"
plugins = ["mypy_django_plugin.main", "mypy_drf_plugin.main"]
namespace_packages = true
explicit_package_bases = true

# Phase 1: Permissive global settings
disallow_untyped_defs = false  # À activer en Phase 4
disallow_any_generics = false
disallow_subclassing_any = false
disallow_untyped_calls = false
disallow_untyped_decorators = false
disallow_incomplete_defs = false

# Enabled checks
check_untyped_defs = true
no_implicit_reexport = true
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

# Exclusions
exclude = [
    "migrations/",
    "tests/",
    ".venv/",
    "venv/",
    "build/",
    "dist/",
    "__pycache__/",
    ".*/tests\\.py$",
    "test_settings\\.py$",
]

[tool.django-stubs]
django_settings_module = "idp_backend.settings"
strict_settings = false  # Phase 4: activer strict_settings = true

# Per-module overrides
[[tool.mypy.overrides]]
module = "admin_analytics.*"
disallow_untyped_defs = true

# Phase 4: Ajouter overrides pour modules principaux
# [[tool.mypy.overrides]]
# module = [
#   "core.*",
#   "idp_auth.*",
#   "executions.*",
#   "catalog.*",
#   "inventory.*",
#   "profiles.*",
#   "reference.*",
# ]
# disallow_untyped_defs = true
```

### Contraintes et décisions architecturales

**Contrainte 1** : Ne pas casser les tests existants
- Tous les tests pytest doivent passer après corrections
- Aucune régression fonctionnelle

**Contrainte 2** : Utiliser django-stubs et djangorestframework-stubs
- Versions : django-stubs==5.2.9, djangorestframework-stubs==3.16.8
- Limitation connue : `Manager.from_queryset` génère erreur `misc` — utiliser `# type: ignore[misc]`

**Contrainte 3** : Pre-commit hook déjà configuré
- `.pre-commit-config.yaml` existe avec mypy (Story 17.9)
- Aucune modification nécessaire si déjà bloquant

**Décision 1** : Supprimer mécanisme baseline
- `.mypy-baseline-count` supprimé
- `scripts/check_mypy_baseline.sh` supprimé
- `scripts/generate_mypy_baseline.sh` supprimé
- CI appelle directement `mypy .`

**Décision 2** : Mode strict progressif
- Activer `disallow_untyped_defs = true` uniquement sur modules principaux
- Conserver permissif sur modules secondaires (si nécessaire)

### Tests à exécuter

1. **mypy** : `mypy . --no-error-summary` → 0 erreur
2. **pytest** : `pytest` → 100% pass rate
3. **pre-commit** : `pre-commit run --all-files` → passe
4. **CI** : pousser branche → job typecheck-backend passe

### Références

**Documents** :
- [Source: docs/mypy-improvement-roadmap.md] — Roadmap Phase 4
- [Source: docs/mypy-developer-guide.md] — Guide développeur
- [Source: planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md#Story 26.16] — Acceptance Criteria

**Stories précédentes** :
- [Source: implementation-artifacts/17-9-mypy-bloquant-progressivement.md] — Phase 1 (baseline 89)
- [Source: implementation-artifacts/22-19-rendre-mypy-bloquant-progressivement.md] — Phase 2 (baseline 29)

**Commits récents pertinents** :
- `3bacc34` — refactor(26-15): fix deprecation warnings and linter issues
- `ff2bd4d` — test(26-14): fix all failing backend tests
- `c1fd32d` — test(26-13): fix all failing frontend tests

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6) + Claude Sonnet (parallel sub-agents)

### Debug Log References

N/A

### Completion Notes List

- **Task 1** : 80 erreurs mypy corrigées → 0 erreur. Types de corrections : no-any-return (cast), override (type: ignore[override]), misc (Manager.from_queryset ignore), arg-type (None guards), assignment (serializer ignores), unreachable (isinstance guards), call-arg (structlog kwargs), attr-defined (imports), operator (None checks). 5 agents parallèles utilisés pour batch fixes.
- **Task 2** : Mode strict activé (`disallow_untyped_defs = true`) sur 7 modules (core, idp_auth, executions, catalog, inventory, profiles, reference). 373 nouvelles erreurs no-untyped-def corrigées par ajout d'annotations de type sur ~373 fonctions dans 52 fichiers. 4 agents parallèles utilisés.
- **Task 3** : Pre-commit hook déjà bloquant (mirrors-mypy v1.10.0). README.md mis à jour avec documentation installation/usage/bypass.
- **Task 4** : CI workflows (ci.yml, deploy.yml, django-tests.yml) mis à jour en mode strict bloquant direct (`mypy . --no-error-summary`). Suppression des références baseline.
- **Task 5** : Mécanisme baseline supprimé — `.mypy-baseline-count`, `scripts/check_mypy_baseline.sh`, `scripts/generate_mypy_baseline.sh` supprimés.
- **Task 6** : Documentation mise à jour — `docs/mypy-improvement-roadmap.md` (Phase 4 complétée), `docs/mypy-developer-guide.md` (mode strict documenté), `docs/mypy-baseline-workflow.md` supprimé.
- **Task 7** : Validation finale — 0 erreur mypy, 2249 tests backend passent, 0 régression.

### Change Log

- 2026-02-13: Story 26.16 complétée — 0 erreur mypy, mode strict, CI/pre-commit bloquants, baseline supprimée

### File List

**Fichiers créés** :
- `_bmad-output/implementation-artifacts/26-16-enforcer-mypy-codebase-pre-commit-hook.md` — Story file

**Fichiers modifiés (configuration)** :
- `pyproject.toml` — Phase 4 strict overrides activés sur 7 modules
- `.github/workflows/ci.yml` — CI mypy strict bloquant direct
- `.github/workflows/deploy.yml` — CI mypy strict bloquant direct
- `.github/workflows/django-tests.yml` — Supprimé continue-on-error mypy
- `README.md` — Section Type Checking et Pre-commit hooks mise à jour

**Fichiers modifiés (type annotations, 52+ fichiers)** :
- `core/models.py`, `core/middleware.py`, `core/feature_flags.py`, `core/exceptions.py`, `core/services.py`, `core/fields.py`, `core/throttling.py`, `core/permissions.py`, `core/consumers.py`, `core/startup_checks.py`, `core/feature_flag_views.py`, `core/views.py`, `core/schema.py`, `core/apps.py`, `core/environment.py`
- `catalog/views.py`, `catalog/services.py`, `catalog/serializers.py`, `catalog/models.py`
- `executions/models.py`, `executions/services.py`, `executions/tasks.py`, `executions/consumers.py`, `executions/gate_context.py`, `executions/gate_evaluator.py`, `executions/simulation_service.py`, `executions/utils.py`, `executions/builders/response_builder.py`, `executions/validators/*.py`, `executions/views/action_views.py`, `executions/views/execution_views.py`, `executions/views/scheduled_views.py`, `executions/views/workflow_views.py`, `executions/views/utils.py`
- `profiles/models.py`, `profiles/services.py`, `profiles/views.py`, `profiles/serializers.py`, `profiles/services_export_import.py`
- `idp_auth/views.py`, `idp_auth/services.py`, `idp_auth/models.py`, `idp_auth/middleware.py`, `idp_auth/authentication.py`, `idp_auth/jwt_utils.py`
- `reference/models.py`, `reference/views.py`, `reference/serializers.py`
- `inventory/views.py`, `inventory/query_executor.py`, `inventory/services.py`
- `admin_analytics/views.py`

**Fichiers modifiés (documentation)** :
- `docs/mypy-improvement-roadmap.md` — Phase 4 complétée
- `docs/mypy-developer-guide.md` — Mode strict documenté

**Fichiers supprimés** :
- `.mypy-baseline-count`
- `scripts/check_mypy_baseline.sh`
- `scripts/generate_mypy_baseline.sh`
- `docs/mypy-baseline-workflow.md`

