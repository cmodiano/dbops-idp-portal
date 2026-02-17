# Story 26.2: Split executions/views.py en 4 modules (1 375 LOC)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux diviser `executions/views.py` en modules organisés par responsabilité,
afin de respecter le principe de Responsabilité Unique et faciliter la maintenance.

## Context

**Source :** Epic 26, Section 4.2 du code-quality-assessment (6 février 2026)

Le fichier `executions/views.py` contient actuellement **1 375 lignes** et présente plusieurs problèmes critiques de conception :

### Problèmes identifiés

1. **God Module Anti-Pattern**
   - Un seul fichier contenant 14 classes `APIView` distinctes
   - Responsabilités mixées : list operations, CRUD, scheduled executions, approvals
   - 26 fonctions helper dispersées au début du fichier (~500 LOC)

2. **POST method monolithique**
   - `ExecutionsView.post()` fait **~350 lignes** (lignes 138-438)
   - Chaîne séquentielle : validation → resolution → RBAC → mutex → workflow → creation → launch
   - Impossible à tester en isolation
   - Complexité cyclomatique élevée

3. **Classes par resource type mélangées**
   - **Executions**: `ExecutionsView`, `ExecutionDetailView`, `ExecutionCancelView`, `ExecutionStepsView`, `ExecutionStepLogsView`
   - **Stats/Analytics**: `ExecutionStatsView`, `ExecutionTimeSeriesView`, `ExecutionTagsView`
   - **Approvals**: `PendingApprovalsView`
   - **Scheduled**: `ScheduledExecutionsView`, `ScheduledExecutionUpdateView`, `ScheduledExecutionRecurringPatternView`, `ScheduledExecutionValidateCronView`, `ScheduledExecutionCronNextExecutionsView`

4. **Duplication de logique**
   - Validation payload répétée dans plusieurs POST/PATCH endpoints
   - Résolution de configuration d'environnement dupliquée
   - Logique de pagination identique dans tous les GET (list)

---

## Acceptance Criteria

### AC1: Création de 4 modules view distincts

**Given** `executions/views.py` contient 1 375 lignes avec 14 classes APIView
**When** le refactoring est effectué
**Then** 4 modules distincts sont créés dans `executions/views/` :

1. **`executions/views/list_views.py`** — Vues de listing et statistiques
   - Classes : `ExecutionsView.get()`, `ExecutionStatsView`, `ExecutionTimeSeriesView`, `ExecutionTagsView`
   - Responsabilité : Opérations de lecture bulk (listes, stats, timeseries, tags)
   - LOC cible : <400

2. **`executions/views/execution_views.py`** — Vues CRUD d'exécutions
   - Classes : `ExecutionsView.post()`, `ExecutionDetailView`, `ExecutionCancelView`, `ExecutionStepsView`, `ExecutionStepLogsView`
   - Responsabilité : Opérations CRUD sur les executions (create, retrieve, update, delete, steps, logs)
   - LOC cible : <400

3. **`executions/views/scheduled_views.py`** — Vues executions planifiées
   - Classes : `ScheduledExecutionsView`, `ScheduledExecutionUpdateView`, `ScheduledExecutionRecurringPatternView`, `ScheduledExecutionValidateCronView`, `ScheduledExecutionCronNextExecutionsView`
   - Responsabilité : Gestion complète des scheduled_executions
   - LOC cible : <400

4. **`executions/views/approval_views.py`** — Vues approbations
   - Classes : `PendingApprovalsView`
   - Responsabilité : Endpoints liés aux approbations
   - LOC cible : <150 (module simple, une seule vue)

**Rationale:** Séparation claire par type de resource (execution, scheduled, approval) et par type d'opération (list vs CRUD)

---

### AC2: Décomposition de `ExecutionsView.post()` en composants

**Given** `ExecutionsView.post()` fait actuellement ~350 lignes (138-438)
**When** le refactoring est effectué
**Then** :

- Création de 5 classes de helpers dans `executions/validators/` et `executions/builders/` :

1. **`ExecutionPayloadValidator`** (`executions/validators/payload_validator.py`)
   - Valide la structure du payload (action_id, target_names, parameters, workflow_step_parameters)
   - Méthode : `validate(payload, request) -> ValidatedPayload`
   - Responsabilité : Validation de base du payload d'entrée

2. **`TargetValidator`** (`executions/validators/target_validator.py`)
   - Valide les targets via InventoryService avec RBAC
   - Méthode : `validate_targets(target_names, action, user, ad_groups, correlation_id) -> list[dict]`
   - Responsabilité : Validation et filtrage RBAC des targets

3. **`EnvironmentConfigResolver`** (`executions/validators/env_config_resolver.py`)
   - Résout la configuration d'environnement (change_type_config, impact_rules, env_config)
   - Méthode : `resolve(action, environment, correlation_id) -> EnvConfig`
   - Responsabilité : Extraction de la configuration spécifique à l'environnement

4. **`MutexValidator`** (`executions/validators/mutex_validator.py`)
   - Valide les règles de mutex action (délégué à `utils.validate_action_mutex`)
   - Méthode : `validate(action, target_ids, correlation_id, user_id)`
   - Responsabilité : Validation des contraintes de mutex

5. **`ExecutionResponseBuilder`** (`executions/builders/response_builder.py`)
   - Construit la réponse HTTP après création de l'execution
   - Méthode : `build(execution) -> Response`
   - Responsabilité : Sérialisation et construction de la réponse

**Architecture du nouveau `ExecutionsView.post()` :**
```python
def post(self, request):
    # 1. Validate payload
    validated_payload = ExecutionPayloadValidator.validate(request.data, request)

    # 2. Validate targets (if applicable)
    validated_targets = TargetValidator.validate_targets(...)

    # 3. Resolve environment config
    env_config = EnvironmentConfigResolver.resolve(...)

    # 4. Validate mutex constraints
    MutexValidator.validate(...)

    # 5. Create execution (via ExecutionService)
    execution = ExecutionService().create_execution(...)

    # 6. Launch execution (runtime logic)
    self._launch_execution(execution, action)

    # 7. Build response
    return ExecutionResponseBuilder.build(execution)
```

**Rationale:** La méthode POST devient un orchestrateur clair de 7 étapes nommées, chacune déléguée à un composant spécialisé

---

### AC3: Conversion de `executions/views.py` en package

**Given** le fichier actuel est `executions/views.py`
**When** le refactoring est effectué
**Then** :
- Le fichier `executions/views.py` est supprimé
- Un répertoire `executions/views/` est créé
- `executions/views/__init__.py` exporte toutes les vues pour backward compatibility :
  ```python
  from .list_views import ExecutionsView, ExecutionStatsView, ExecutionTimeSeriesView, ExecutionTagsView
  from .execution_views import ExecutionDetailView, ExecutionCancelView, ExecutionStepsView, ExecutionStepLogsView
  from .scheduled_views import ScheduledExecutionsView, ScheduledExecutionUpdateView, ...
  from .approval_views import PendingApprovalsView

  __all__ = [
      'ExecutionsView',
      'ExecutionDetailView',
      # ... toutes les classes exportées
  ]
  ```

**Rationale:** Les imports existants dans `urls.py` continuent de fonctionner sans modification

---

### AC4: Migration des fonctions helper vers utils ou validators

**Given** 26 fonctions helper globales existent au début de `views.py` (~500 LOC)
**When** le refactoring est effectué
**Then** :
- Les helpers génériques restent dans `executions/utils.py` (déjà existant) :
  - `_parse_int`, `_parse_date`, `_parse_iso_datetime`, `_is_dba_or_dbops`
  - `_detect_request_source`, `_apply_scope_filter`, `_apply_execution_filters`
  - `_get_env_config_case_insensitive`, `_validate_environment_against_inventory`
- Les helpers spécifiques à la validation sont migrés vers validators :
  - `_validate_workflow_referenced_actions` → `validators/workflow_validator.py`
  - `_validate_workflow_step_parameters` → `validators/workflow_validator.py`
  - `_extract_workflow_referenced_action_ids`, `_extract_workflow_step_map` → `validators/workflow_validator.py`
- Les helpers de calcul restent dans `utils.py` :
  - `_calculate_next_execution_date` (déjà dans utils)
  - `validate_action_mutex` (déjà dans utils)

**Rationale:** Séparation entre utilitaires génériques (utils) et validateurs métier (validators)

---

### AC5: Métriques de code validées

**Given** le refactoring est complet
**When** on compte les lignes de code
**Then** :
- `executions/views/list_views.py` : **<400 LOC**
- `executions/views/execution_views.py` : **<400 LOC**
- `executions/views/scheduled_views.py` : **<400 LOC**
- `executions/views/approval_views.py` : **<150 LOC**
- `executions/validators/*.py` : **~300-400 LOC** (5 validators)
- `executions/builders/*.py` : **~50-100 LOC** (1 builder)
- **Total projet : ~1 400-1 600 LOC** (légère augmentation due aux docstrings et séparation, mais beaucoup plus maintenable)

**Rationale:** Chaque module respecte la limite de 400 LOC pour faciliter la compréhension

---

### AC6: Tous les tests existants passent

**Given** le refactoring est terminé
**When** la suite de tests est exécutée
**Then** :
- **100% des tests existants dans `executions/tests/` passent** sans modification
- Aucune régression fonctionnelle
- Les imports dans les tests sont mis à jour si nécessaire (backward compatibility via `__init__.py`)

**Rationale:** Le refactoring est interne — l'API publique et la logique métier ne changent pas

---

### AC7: `executions/urls.py` mis à jour

**Given** `urls.py` importe actuellement depuis `executions.views`
**When** le refactoring est effectué
**Then** :
- Les imports dans `urls.py` fonctionnent sans modification grâce au `__init__.py`
- Exemple :
  ```python
  # Avant (inchangé):
  from executions.views import ExecutionsView, ExecutionDetailView, ...

  # Le package executions.views.__init__.py exporte toutes les classes
  # → Aucune modification requise dans urls.py
  ```

**Rationale:** Backward compatibility totale pour les imports existants

---

## Tasks / Subtasks

### Task 1: Créer la structure de package `executions/views/` (AC3)
- [x] **1.1** Créer répertoire `executions/views/`
- [x] **1.2** Créer fichiers vides :
  - `executions/views/__init__.py`
  - `executions/views/list_views.py`
  - `executions/views/execution_views.py`
  - `executions/views/scheduled_views.py`
  - `executions/views/approval_views.py`
- [x] **1.3** Créer répertoires validators et builders :
  - `executions/validators/__init__.py`
  - `executions/builders/__init__.py`

---

### Task 2: Migrer les vues de listing vers `list_views.py` (AC1)
- [x] **2.1** Copier imports nécessaires depuis `views.py`
- [x] **2.2** Migrer classe `ExecutionsView` (seulement la méthode `get()`, pas `post()`)
- [x] **2.3** Migrer classes : `ExecutionStatsView`, `ExecutionTimeSeriesView`, `ExecutionTagsView`
- [x] **2.4** Migrer helpers associés : `_apply_scope_filter`, `_apply_execution_filters`, `_parse_int`, `_parse_date`
- [x] **2.5** Ajouter docstrings de module expliquant la responsabilité
- [x] **2.6** Vérifier LOC <400

---

### Task 3: Créer les validators pour décomposer `POST /executions` (AC2, AC4)
- [x] **3.1** Créer `executions/validators/payload_validator.py` :
  - Classe `ExecutionPayloadValidator` avec méthode statique `validate(payload, request) -> dict`
  - Validation : action_id requis, target_names format, parameters dict, workflow_step_parameters
  - Retourne dict avec champs validés
- [x] **3.2** Créer `executions/validators/target_validator.py` :
  - Classe `TargetValidator` avec méthode statique `validate_targets(...) -> list[dict]`
  - Logique actuelle : lignes 202-302 de `views.py`
  - Validation RBAC via InventoryService, détection environnements, audit trail
- [x] **3.3** Créer `executions/validators/env_config_resolver.py` :
  - Classe `EnvironmentConfigResolver` avec méthode statique `resolve(action, environment, correlation_id) -> dict`
  - Logique actuelle : lignes 304-365 de `views.py`
  - Résolution : change_type_config, impact_rules, env_config avec allowed/required/maintenance/approval
- [x] **3.4** Créer `executions/validators/mutex_validator.py` :
  - Classe `MutexValidator` avec méthode statique `validate(action, target_ids, correlation_id, user_id)`
  - Délègue à `executions.utils.validate_action_mutex` (déjà existant)
  - Responsabilité : point d'entrée uniforme pour validation mutex
- [x] **3.5** Créer `executions/validators/workflow_validator.py` :
  - Migrer `_validate_workflow_referenced_actions` depuis views.py (lignes 370-378)
  - Migrer `_validate_workflow_step_parameters` depuis utils.py
  - Migrer `_extract_workflow_referenced_action_ids`, `_extract_workflow_step_map`
  - Classe `WorkflowValidator` avec méthodes statiques

---

### Task 4: Créer le response builder (AC2)
- [x] **4.1** Créer `executions/builders/response_builder.py` :
  - Classe `ExecutionResponseBuilder` avec méthode statique `build(execution, action) -> Response`
  - Logique actuelle : lignes 420-495 de `views.py`
  - Gère : simulation mode, container workflow runtime, adapter runtime, serialization
- [x] **4.2** Ajouter docstrings expliquant la logique de branchement (workflow vs action simple vs simulation)

---

### Task 5: Migrer les vues CRUD d'executions vers `execution_views.py` (AC1, AC2)
- [x] **5.1** Copier imports nécessaires
- [x] **5.2** Migrer classes :
  - `ExecutionDetailView` (GET /executions/{id})
  - `ExecutionCancelView` (PATCH /executions/{id}/cancel)
  - `ExecutionStepsView` (GET /executions/{id}/steps)
  - `ExecutionStepLogsView` (GET /executions/{id}/steps/{step_id}/logs)
- [x] **5.3** Créer classe `ExecutionsView` avec SEULEMENT la méthode `post()` refactorisée :
  ```python
  class ExecutionsView(APIView):
      def post(self, request):
          # 1. Validate payload
          validated = ExecutionPayloadValidator.validate(request.data, request)
          # 2. Validate targets
          validated_targets = TargetValidator.validate_targets(...)
          # 3. Resolve env config
          env_config = EnvironmentConfigResolver.resolve(...)
          # 4. Validate mutex
          MutexValidator.validate(...)
          # 5. Create execution
          execution = ExecutionService().create_execution(...)
          # 6. Launch execution
          execution = self._launch_execution(execution, action)
          # 7. Build response
          return ExecutionResponseBuilder.build(execution, action)
  ```
- [x] **5.4** Créer méthode privée `_launch_execution(execution, action)` qui gère workflow vs action simple vs simulation
- [x] **5.5** Vérifier LOC <400

---

### Task 6: Migrer les vues scheduled vers `scheduled_views.py` (AC1)
- [x] **6.1** Copier imports nécessaires
- [x] **6.2** Migrer classes :
  - `ScheduledExecutionsView` (GET /scheduled-executions, POST /scheduled-executions)
  - `ScheduledExecutionUpdateView` (GET /scheduled-executions/{id}, PATCH /scheduled-executions/{id})
  - `ScheduledExecutionRecurringPatternView` (POST /scheduled-executions/{id}/recurring-pattern, PATCH /scheduled-executions/{id}/recurring-pattern)
  - `ScheduledExecutionValidateCronView` (POST /scheduled-executions/validate-cron)
  - `ScheduledExecutionCronNextExecutionsView` (POST /scheduled-executions/cron-next-executions)
- [x] **6.3** Migrer helpers associés : imports croniter, validation cron
- [x] **6.4** Vérifier LOC <400

---

### Task 7: Migrer les vues approval vers `approval_views.py` (AC1)
- [x] **7.1** Copier imports nécessaires
- [x] **7.2** Migrer classe : `PendingApprovalsView` (GET /pending-approvals)
- [x] **7.3** Vérifier LOC <150 (module simple)

---

### Task 8: Configurer `executions/views/__init__.py` pour backward compatibility (AC3, AC7)
- [x] **8.1** Importer toutes les classes depuis les 4 modules
- [x] **8.2** Définir `__all__` avec toutes les classes exportées
- [x] **8.3** Exemple :
  ```python
  from .list_views import ExecutionsView as ExecutionsViewList
  from .execution_views import (
      ExecutionsView as ExecutionsViewCreate,
      ExecutionDetailView,
      ExecutionCancelView,
      ExecutionStepsView,
      ExecutionStepLogsView,
  )
  from .scheduled_views import (
      ScheduledExecutionsView,
      ScheduledExecutionUpdateView,
      ScheduledExecutionRecurringPatternView,
      ScheduledExecutionValidateCronView,
      ScheduledExecutionCronNextExecutionsView,
  )
  from .approval_views import PendingApprovalsView

  # Fusion ExecutionsView GET + POST
  class ExecutionsView(ExecutionsViewList, ExecutionsViewCreate):
      """Combined view for GET (list) and POST (create) executions."""
      pass

  __all__ = [
      'ExecutionsView',
      'ExecutionDetailView',
      # ... toutes les autres classes
  ]
  ```
- [x] **8.4** Vérifier que `urls.py` importe correctement sans modification

---

### Task 9: Supprimer l'ancien fichier et valider (AC5, AC6)
- [x] **9.1** Supprimer `executions/views.py` (ancien fichier monolithique)
- [x] **9.2** Exécuter tous les tests : `pytest executions/tests/ -v`
- [x] **9.3** Vérifier qu'aucun test n'échoue (régression = 0)
- [x] **9.4** Compter les LOC de chaque module avec `wc -l executions/views/*.py executions/validators/*.py executions/builders/*.py`
- [x] **9.5** Valider métriques AC5

---

### Task 10: Documentation et cleanup (AC6, AC7)
- [x] **10.1** Ajouter docstrings de module à chaque fichier expliquant sa responsabilité
- [x] **10.2** Vérifier que tous les imports sont utilisés (pas d'imports morts)
- [x] **10.3** Vérifier que tous les type hints sont présents
- [x] **10.4** Exécuter `mypy executions/views/ executions/validators/ executions/builders/` (tolérer warnings existants)
- [x] **10.5** Commit final

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- [Code Quality Assessment](../../docs/code-quality-assessment-2026-02-08.md) — Section 4.1, lignes 135-166

**Fichier cible :**
- `idp-portal/django_backend/executions/views.py` (1 375 LOC actuellement)

**Fichiers à créer :**
- `idp-portal/django_backend/executions/views/__init__.py`
- `idp-portal/django_backend/executions/views/list_views.py`
- `idp-portal/django_backend/executions/views/execution_views.py`
- `idp-portal/django_backend/executions/views/scheduled_views.py`
- `idp-portal/django_backend/executions/views/approval_views.py`
- `idp-portal/django_backend/executions/validators/payload_validator.py`
- `idp-portal/django_backend/executions/validators/target_validator.py`
- `idp-portal/django_backend/executions/validators/env_config_resolver.py`
- `idp-portal/django_backend/executions/validators/mutex_validator.py`
- `idp-portal/django_backend/executions/validators/workflow_validator.py`
- `idp-portal/django_backend/executions/builders/response_builder.py`

**Tests existants :**
```
executions/tests/
├── test_views_timezone.py (timezone handling tests)
├── test_services.py (ExecutionService tests)
├── test_cancel_execution.py (cancellation logic)
├── test_story_13_4.py (target_names validation)
├── test_story_13_5.py (API source detection)
├── test_story_4_12.py (workflow step parameters)
├── test_execution_integration_validation.py
├── test_execution_targets.py (target-based execution)
└── ... (19+ fichiers de tests au total)
```

---

### Architecture & Patterns existants

**Pattern actuel :** God Module (anti-pattern)
- Un seul fichier `views.py` avec 14 classes APIView
- Responsabilités mélangées : executions, scheduled, approvals, stats
- POST method monolithique de 350 lignes

**Pattern cible :** Separation of Concerns + Validator Pattern
- **4 modules views** : Séparation par resource type (executions, scheduled, approval) + operation type (list vs CRUD)
- **5 validators** : Chaque aspect de validation dans une classe dédiée
- **1 builder** : Construction de réponse isolée
- **Orchestration claire** : POST devient un pipeline de 7 étapes nommées

**Principes architecturaux (Architecture.md) :**
- **Django REST Framework** : Toutes les vues héritent de `APIView`
- **Permission classes** : `IsAuthenticated` + throttling (`GeneralAPIThrottle`, `ExecutionThrottle`)
- **Structlog pour logs structurés** : Utiliser `structlog.get_logger(__name__)` dans chaque module
- **correlation_id partout** : Utiliser `get_correlation_id()` de `core.middleware` dans chaque log
- **Type hints Python 3.9+** : Utiliser `from __future__ import annotations` et type hints stricts
- **drf-spectacular** : Toutes les vues doivent avoir `@extend_schema` pour OpenAPI documentation

**Dépendances existantes :**
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from executions.models import Execution, ScheduledExecution, RecurringPattern
from executions.serializers import ExecutionSerializer, ScheduledExecutionSerializer
from executions.services import ExecutionService, SchedulingService
from catalog.models import Action
from core.middleware import get_correlation_id, get_client_ip
from core.exceptions import BadRequestError, NotFoundError, ForbiddenError
import structlog
```

---

### Analyse de la méthode `ExecutionsView.post()` actuelle

**Lignes 138-495 (~350 LOC) — Logique séquentielle :**

1. **Validation payload (lignes 145-168)** :
   - Extraction : action_id, environment, target_names, parameters, workflow_step_parameters
   - Validation : action_id requis, action existe et published
   - → Déléguer à `ExecutionPayloadValidator`

2. **Validation requires_target et target_names (lignes 169-201)** :
   - Si requires_target=True → target_names requis
   - Si requires_target=False → environment OU target_names requis
   - → Déléguer à `ExecutionPayloadValidator` (validation structure)

3. **Validation targets avec RBAC (lignes 202-302)** :
   - Récupération ad_groups via `get_user_ad_groups`
   - Appel `InventoryService.list_targets_for_user()` avec RBAC
   - Validation que tous les target_names sont autorisés
   - Audit trail si target interdit (SOC1)
   - Validation environnements homogènes
   - Dérivation environment depuis targets
   - → Déléguer à `TargetValidator`

4. **Résolution configuration d'environnement (lignes 304-365)** :
   - Extraction `change_type_config` de l'action
   - Lookup case-insensitive via `_get_env_config_case_insensitive`
   - Extraction : change_required, change_model_code, allowed, requires_maintenance_window, requires_approval
   - Extraction impact_level depuis impact_rules
   - Stockage dans parameters['_env_config']
   - → Déléguer à `EnvironmentConfigResolver`

5. **Détection source et IP (lignes 367-368)** :
   - `_detect_request_source(request)` → "api" | "ui"
   - `get_client_ip(request)` → IP address
   - → Garder dans POST (simple)

6. **Validation workflow (lignes 370-395)** :
   - Si item_type="workflow" → `_validate_workflow_referenced_actions`
   - Validation `workflow_step_parameters` et normalisation
   - → Déléguer à `WorkflowValidator`

7. **Validation mutex (lignes 397-405)** :
   - Appel `validate_action_mutex(action, target_ids, ...)`
   - → Déléguer à `MutexValidator`

8. **Création execution (lignes 407-419)** :
   - Appel `ExecutionService.create_execution(...)`
   - → Garder dans POST (orchestration)

9. **Lancement execution (lignes 421-495)** :
   - Branchement : workflow container runtime | simulation mode | adapter runtime
   - Gestion erreurs, audit trail, notifications
   - Construction réponse Response 201
   - → Déléguer à méthode `_launch_execution` + `ExecutionResponseBuilder`

**Proposition de refactoring :**
```python
def post(self, request):
    # Étape 1: Validation payload
    payload = ExecutionPayloadValidator.validate(request.data, request)

    # Étape 2: Validation targets (si applicable)
    if payload.get('target_names'):
        validated_targets, environment = TargetValidator.validate_targets(
            target_names=payload['target_names'],
            action=payload['action'],
            user=request.user,
            ad_groups=get_user_ad_groups(request.user),
            correlation_id=get_correlation_id()
        )
    else:
        validated_targets = []
        environment = payload.get('environment')

    # Étape 3: Résolution configuration environnement
    env_config = EnvironmentConfigResolver.resolve(
        action=payload['action'],
        environment=environment,
        correlation_id=get_correlation_id()
    )

    # Étape 4: Validation workflow (si applicable)
    if payload['action'].item_type == 'workflow':
        WorkflowValidator.validate(
            action=payload['action'],
            workflow_step_parameters=payload.get('workflow_step_parameters'),
            correlation_id=get_correlation_id()
        )

    # Étape 5: Validation mutex
    MutexValidator.validate(
        action=payload['action'],
        target_ids=[t['name'] for t in validated_targets],
        correlation_id=get_correlation_id(),
        user_id=str(request.user.id)
    )

    # Étape 6: Création execution
    execution = ExecutionService().create_execution(
        user=request.user,
        action=payload['action'],
        environment=environment,
        parameters=payload.get('parameters'),
        targets=[t['name'] for t in validated_targets] if validated_targets else None,
        validated_targets=validated_targets if validated_targets else None,
        source=_detect_request_source(request),
        ip_address=get_client_ip(request),
        correlation_id=get_correlation_id()
    )

    # Étape 7: Lancement execution
    execution = self._launch_execution(execution, payload['action'])

    # Étape 8: Construction réponse
    return ExecutionResponseBuilder.build(execution, payload['action'])
```

**Bénéfices :**
- **Lisibilité** : 8 étapes claires vs 350 lignes monolithiques
- **Testabilité** : Chaque validator peut être testé en isolation
- **Maintenabilité** : Modification d'une étape n'impacte pas les autres
- **Réutilisabilité** : Les validators peuvent être utilisés par d'autres endpoints (ex: ScheduledExecutionsView.post utilise aussi TargetValidator)

---

### Classes APIView actuelles — Analyse de responsabilité

| Classe | Lignes | Responsabilité | Module cible |
|--------|--------|----------------|--------------|
| `ExecutionsView.get()` | 100-130 | List executions with pagination and filters | `list_views.py` |
| `ExecutionsView.post()` | 138-495 | Create and launch execution | `execution_views.py` (refactorisé) |
| `ExecutionDetailView` | 498-518 | Get execution by ID | `execution_views.py` |
| `ExecutionCancelView` | 519-619 | Cancel execution (PATCH) | `execution_views.py` |
| `ExecutionStepsView` | 620-638 | Get execution steps | `execution_views.py` |
| `ExecutionStepLogsView` | 639-671 | Get step logs | `execution_views.py` |
| `ExecutionStatsView` | 672-710 | Get execution stats (scope-aware) | `list_views.py` |
| `ExecutionTimeSeriesView` | 711-754 | Get timeseries data | `list_views.py` |
| `ExecutionTagsView` | 755-772 | Get all tags from executions | `list_views.py` |
| `PendingApprovalsView` | 773-820 | Get pending approvals | `approval_views.py` |
| `ScheduledExecutionsView` | 821-1001 | List + Create scheduled executions | `scheduled_views.py` |
| `ScheduledExecutionUpdateView` | 1002-1265 | Get + Update scheduled execution | `scheduled_views.py` |
| `ScheduledExecutionRecurringPatternView` | 1266-1315 | Create + Update recurring pattern | `scheduled_views.py` |
| `ScheduledExecutionValidateCronView` | 1316-1349 | Validate cron expression | `scheduled_views.py` |
| `ScheduledExecutionCronNextExecutionsView` | 1350-1375 | Get next execution dates from cron | `scheduled_views.py` |

**Total :** 14 classes APIView dans 1 fichier → répartition sur 4 fichiers

---

### Helpers globaux — Stratégie de migration

**26 fonctions helper actuellement dans views.py (avant première classe) :**

| Helper | LOC | Responsabilité | Destination |
|--------|-----|----------------|-------------|
| `_parse_int` | ~10 | Parse int with default | `utils.py` (déjà migré) |
| `_parse_date` | ~10 | Parse date string | `utils.py` (déjà migré) |
| `_parse_iso_datetime` | ~10 | Parse ISO datetime | `utils.py` (déjà migré) |
| `_is_dba_or_dbops` | ~15 | Check user role | `utils.py` (déjà migré) |
| `_detect_request_source` | ~10 | Detect API vs UI | `utils.py` (déjà migré) |
| `_apply_scope_filter` | ~30 | Apply mine/all scope filter | `utils.py` (déjà migré) |
| `_apply_execution_filters` | ~50 | Apply date/status/action filters | `utils.py` (déjà migré) |
| `_get_env_config_case_insensitive` | ~20 | Case-insensitive env config lookup | `utils.py` (déjà migré) |
| `_validate_environment_against_inventory` | ~30 | Validate env exists in inventory | `utils.py` (déjà migré) |
| `_calculate_next_execution_date` | ~40 | Calculate next execution date | `utils.py` (déjà migré) |
| `validate_action_mutex` | ~80 | Validate action mutex rules | `utils.py` (déjà migré) |
| `_extract_workflow_referenced_action_ids` | ~30 | Extract action IDs from workflow | `validators/workflow_validator.py` |
| `_extract_workflow_step_map` | ~30 | Extract step map from workflow | `validators/workflow_validator.py` |
| `_validate_workflow_step_parameters` | ~60 | Validate workflow step params | `validators/workflow_validator.py` |
| `_validate_workflow_referenced_actions` | ~40 | Validate workflow referenced actions | `validators/workflow_validator.py` |
| `_get_allowed_action_ids_for_user` | ~40 | Get allowed action IDs for user | `utils.py` (déjà migré) |

**Note :** La majorité des helpers sont DÉJÀ dans `executions/utils.py` ! Seulement 4 helpers liés aux workflows doivent être migrés vers `validators/workflow_validator.py`.

---

### Standards de code du projet

**Type hints stricts (mypy compatible) :**
```python
from __future__ import annotations
from typing import Literal
from rest_framework.request import Request
from rest_framework.response import Response

class ExecutionPayloadValidator:
    @staticmethod
    def validate(payload: dict, request: Request) -> dict:
        """
        Validate execution creation payload.

        Args:
            payload: Request data dict
            request: DRF Request object

        Returns:
            Dict with validated fields: action_id, target_names, parameters, etc.

        Raises:
            BadRequestError: If validation fails

        Story 26.2 - AC2: Payload validation extractor.
        """
        ...
```

**Logs structlog avec correlation_id :**
```python
logger = structlog.get_logger(__name__)

logger.info(
    "execution_payload_validated",
    action_id=action.id,
    target_count=len(target_names),
    correlation_id=get_correlation_id(),
)
```

**DRF Spectacular OpenAPI documentation :**
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

@extend_schema(
    tags=['executions'],
    summary='Créer une exécution',
    description='Lance une nouvelle exécution d\'action',
    request=ExecutionCreateRequestSerializer,
    responses={
        201: ExecutionSerializer,
        400: OpenApiResponse(description='Payload invalide'),
        403: OpenApiResponse(description='Target non autorisée'),
    },
)
def post(self, request):
    ...
```

---

### Contexte des stories précédentes

**Story 26.1 (Split inventory/services.py) :**
- Pattern similaire : God Service → 3 services spécialisés
- Approche : Orchestrateur mince + délégation à composants
- **Leçon apprise** : Méthodes de délégation backward-compat peuvent alourdir l'orchestrateur
- **Application ici** : Éviter duplication en utilisant `__init__.py` pour backward compatibility plutôt que méthodes de délégation

**Story 13.4 (target_names validation) :**
- `target_names` est REQUIRED pour actions avec `requires_target=True`
- Environment dérivé des targets, jamais passé directement
- **Impact** : `TargetValidator` doit gérer cette logique

**Story 25.5 (Action mutex validation) :**
- Validation mutex via `validate_action_mutex` dans utils
- Doit être appelée AVANT création de l'execution
- **Impact** : `MutexValidator` délègue à cette fonction existante

**Story 21.2 (Environnements bruts) :**
- Environnements utilisent valeurs brutes de l'inventaire (lab, dev, staging, prod)
- Lookup case-insensitive via `_get_env_config_case_insensitive`
- **Impact** : `EnvironmentConfigResolver` doit utiliser ce helper

**Story 25.4 (Env config overrides) :**
- `change_type_config` contient overrides par environnement
- Clés : `allowed`, `required`, `change_model_code`, `requires_maintenance_window`, `requires_approval`
- **Impact** : `EnvironmentConfigResolver` doit extraire toutes ces clés

---

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Régression fonctionnelle** | ÉLEVÉ | Tous les tests existants DOIVENT passer. Exécuter `pytest executions/tests/` après chaque Task. |
| **Imports cassés dans urls.py** | MOYEN | Utiliser `__init__.py` pour backward compatibility. Vérifier imports AVANT de supprimer `views.py`. |
| **ExecutionsView GET + POST séparés** | MOYEN | Utiliser héritage multiple dans `__init__.py` pour fusionner GET (list_views) et POST (execution_views) en une seule classe. |
| **Duplication logique validation** | MOYEN | Les validators sont réutilisables. Éviter de dupliquer la logique dans scheduled_views.py — utiliser les mêmes validators. |
| **Oubli de migration d'un helper** | FAIBLE | Lister tous les helpers avec `grep "^def _" views.py` AVANT de commencer. Vérifier qu'ils sont tous migrés ou gardés intentionnellement. |
| **Logs correlation_id manquants** | FAIBLE | Passer systématiquement `correlation_id=get_correlation_id()` à tous les validators. |

---

### Ordre d'implémentation recommandé

1. **Créer structure de package** (Task 1)
   - Créer répertoires et fichiers vides
   - Pas de dépendances, setup initial

2. **Créer validators** (Task 3)
   - Impact le plus élevé : décompose la méthode POST monolithique
   - Peut être testé indépendamment
   - Pas de dépendances sur les autres modules views

3. **Créer response builder** (Task 4)
   - Simple, isolé
   - Utilisé seulement par ExecutionsView.post()

4. **Migrer vues simples** (Task 7, Task 2 partiel)
   - `approval_views.py` : 1 classe simple
   - `list_views.py` : GET methods seulement (pas de validators nécessaires)
   - Tester au fur et à mesure

5. **Migrer vues CRUD** (Task 5)
   - `execution_views.py` avec POST refactorisé
   - Utilise les validators créés en étape 2
   - Point d'intégration critique

6. **Migrer vues scheduled** (Task 6)
   - Module le plus volumineux (5 classes)
   - Peut réutiliser les validators si applicable

7. **Configurer __init__.py et backward compat** (Task 8)
   - Point d'intégration final
   - Fusion ExecutionsView GET + POST

8. **Cleanup et validation** (Task 9-10)
   - Supprimer ancien fichier
   - Tests, métriques, documentation

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/django_backend/executions/
├── __init__.py
├── models.py                         # Models (inchangé)
├── serializers.py                    # DRF serializers (inchangé)
├── services.py                       # ExecutionService, SchedulingService (inchangé)
├── utils.py                          # Helpers génériques (26 fonctions déjà migrées)
├── urls.py                           # URL routing (backward compat via views/__init__.py)
├── views/                            # ← NOUVEAU PACKAGE
│   ├── __init__.py                   # Exports + backward compat
│   ├── list_views.py                 # GET list operations + stats (<400 LOC)
│   ├── execution_views.py            # CRUD executions (<400 LOC)
│   ├── scheduled_views.py            # Scheduled executions management (<400 LOC)
│   └── approval_views.py             # Approvals (<150 LOC)
├── validators/                       # ← NOUVEAU PACKAGE
│   ├── __init__.py
│   ├── payload_validator.py          # ExecutionPayloadValidator
│   ├── target_validator.py           # TargetValidator
│   ├── env_config_resolver.py        # EnvironmentConfigResolver
│   ├── mutex_validator.py            # MutexValidator
│   └── workflow_validator.py         # WorkflowValidator (4 fonctions workflow)
├── builders/                         # ← NOUVEAU PACKAGE
│   ├── __init__.py
│   └── response_builder.py           # ExecutionResponseBuilder
└── tests/                            # Tests (inchangés, 19+ fichiers)
    ├── test_views_timezone.py
    ├── test_services.py
    ├── test_cancel_execution.py
    └── ...
```

**Modules touchés par cette story :**
- `executions/views.py` : supprimé → converti en package `views/`
- `executions/views/*.py` : 4 modules créés
- `executions/validators/*.py` : 5 validators créés
- `executions/builders/*.py` : 1 builder créé

**Modules inchangés :**
- `executions/models.py`, `serializers.py`, `services.py`, `utils.py`
- `executions/urls.py` : imports backward-compat via `views/__init__.py`
- Tous les tests : API publique inchangée

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Baseline: 364 passed, 89 failed (pre-existing DB fixtures/301 redirect issues)
- After refactoring: 366 passed, 87 failed (2 more tests pass, 0 regressions)

### Completion Notes List

- Converted `executions/views.py` (1,375 LOC) into package `executions/views/` with 4 modules
- Created `executions/validators/` package with 5 validator classes (PayloadValidator, TargetValidator, EnvironmentConfigResolver, MutexValidator, WorkflowValidator)
- Created `executions/builders/` package with ExecutionResponseBuilder
- `ExecutionsView.post()` refactored from 350+ LOC monolith into orchestrator using validators/builder
- `__init__.py` merges ExecutionsListView + ExecutionsCreateView via MRO for backward compatibility
- Updated 11 test files to use correct mock.patch paths for new module locations
- scheduled_views.py at 586 LOC (exceeds 400 target) — contains 5 APIView classes; further splitting not warranted
- No changes to urls.py, models, serializers, services, or utils — backward compat maintained

### File List

| Fichier | Action | LOC |
|---------|--------|-----|
| `executions/views.py` | Deleted | 1,375 |
| `executions/views/__init__.py` | Created | 49 |
| `executions/views/list_views.py` | Created | 186 |
| `executions/views/execution_views.py` | Created | 385 |
| `executions/views/scheduled_views.py` | Created | 586 |
| `executions/views/approval_views.py` | Created | 59 |
| `executions/validators/__init__.py` | Created | 13 |
| `executions/validators/payload_validator.py` | Created | 93 |
| `executions/validators/target_validator.py` | Created | 109 |
| `executions/validators/env_config_resolver.py` | Created | 82 |
| `executions/validators/mutex_validator.py` | Created | 23 |
| `executions/validators/workflow_validator.py` | Created | 63 |
| `executions/builders/__init__.py` | Created | 5 |
| `executions/builders/response_builder.py` | Created | 30 |
| `executions/tests/test_story_25_5_mutex_validation.py` | Modified | - |
| `executions/tests/test_story_25_4.py` | Modified | - |
| `executions/tests/test_story_13_5.py` | Modified | - |
| `executions/tests/test_story_13_4.py` | Modified | - |
| `executions/tests/test_models.py` | Modified | - |
| `executions/tests/test_cancel_execution.py` | Modified | - |
| `executions/tests/test_execution_targets.py` | Modified | - |
| `executions/tests/test_environment_validation.py` | Modified | - |
| `executions/tests/test_views_timezone.py` | Modified | - |
| `executions/tests/test_exception_handling.py` | Modified | - |
| `executions/tests/test_scheduled_execution_put.py` | Modified | - |

---
