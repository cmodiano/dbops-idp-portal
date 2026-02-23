# Conformité SOLID — Guide des patterns IDP Portal

> **Périmètre :** Backend Django (`idp-portal/django_backend`) et Frontend React (`idp-portal/frontend`)
> **Référence :** Audit initial → `_bmad-output/planning-artifacts/solid-audit-report.md`
> **Epic 33 :** Corrections appliquées dans les stories 33.1 à 33.5

---

## Sommaire

1. [SRP — Single Responsibility Principle](#1-srp--single-responsibility-principle)
2. [OCP — Open/Closed Principle](#2-ocp--openclosed-principle)
3. [LSP — Liskov Substitution Principle](#3-lsp--liskov-substitution-principle)
4. [ISP — Interface Segregation Principle](#4-isp--interface-segregation-principle)
5. [DIP — Dependency Inversion Principle](#5-dip--dependency-inversion-principle)
6. [Anti-patterns référencés](#6-anti-patterns-référencés)

---

## 1. SRP — Single Responsibility Principle

> Un module, une classe ou une fonction ne doit avoir qu'une seule raison de changer.

### Pattern — Découpage en packages (backend)

Quand un fichier dépasse **500 LOC** avec plusieurs responsabilités, le découper en package.

#### Exemple : `executions/tasks.py` → `executions/tasks/` (Story 33.2)

Avant : un fichier `tasks.py` (~1 580 LOC) mélangeant retry, polling multi-plateforme, gate evaluation, broadcast WebSocket, audit.

Après :

```
executions/tasks/
├── __init__.py      # ré-exports Celery pour rétrocompatibilité : from .polling import *
├── retry.py         # retry workflow et backoff exponentiel
├── polling.py       # poll_aap_job_status, poll_tower_job_status, poll_azure_devops_run_status…
└── gates.py         # gate evaluation (GateEvaluator, check_gate_conditions)
```

**Règle :** `__init__.py` ne contient que des ré-exports, jamais de logique métier.

#### Exemple : `catalog/views.py` → `catalog/views/` (Story 33.3)

Avant : `views.py` (~1 100 LOC) concentrant 5 ViewSets distincts.

Après :

```
catalog/views/
├── __init__.py             # ré-exports urlconf : from .action_views import ActionViewSet …
├── _shared.py              # utilitaires partagés entre ViewSets
├── action_views.py         # ActionViewSet (CRUD admin actions)
├── catalog_views.py        # CatalogActionViewSet (lecture catalogue)
├── tags_views.py           # TagViewSet
└── business_rule_views.py  # BusinessRuleViewSet
```

**Cibles LOC :** chaque fichier ≤ 500 LOC backend, responsabilité unique.

### Pattern — Découpage en hooks et sous-composants (frontend)

Quand un composant React dépasse **700 LOC** ou mélange état, validation et rendu, extraire :

- Les hooks d'état dans `hooks/` (ex. `useActionFormState.ts`, `useActionFormValidation.ts`)
- Les sous-composants atomiques dans `components/admin/` (ex. `ImpactLevelsLegend.tsx`, `ActionFormCollapseSections.tsx`)

#### Exemple : `ActionForm.tsx` + `ActionWizard.tsx` (Story 33.5)

| Fichier | Avant | Après | Gain |
|---------|-------|-------|------|
| `ActionForm.tsx` | 778 LOC | ~485 LOC | −38 % |
| `ActionWizard.tsx` | 958 LOC | ~584 LOC | −39 % |

Hooks extraits : `useActionFormState`, `useActionFormValidation`.
Composants extraits : `ImpactLevelsLegend`, `ActionFormCollapseSections`, `ChangeTypeConfig`.

**Cibles LOC :** composants React ≤ 700 LOC, hooks ≤ 150 LOC.

### Anti-patterns SRP à éviter

| Anti-pattern | Correct |
|--------------|---------|
| ViewSet de 1 000+ LOC couvrant CRUD admin + lecture catalogue + tags | Séparer en modules dédiés dans un package `views/` |
| Composant React qui possède à la fois l'état, la validation et le rendu des formulaires | Extraire les hooks dans `hooks/`, les sections dans des composants atomiques |
| `__init__.py` contenant de la logique métier | `__init__.py` = ré-exports uniquement |

---

## 2. OCP — Open/Closed Principle

> Les entités logicielles doivent être ouvertes à l'extension mais fermées à la modification.

### Pattern — Registry d'adapters (Story 33.1)

Les adapters de plateformes s'enregistrent eux-mêmes via un décorateur. La factory interroge le registre sans connaître les implémentations.

#### `adapters/registry.py`

```python
from adapters.registry import AdapterRegistry

@AdapterRegistry.register("aap")
class AAPAdapter(BaseAdapter):
    ...

@AdapterRegistry.register("tower")
class TowerAdapter(BaseAdapter):
    ...
```

**Ajouter une nouvelle plateforme (ex. GitLab CI) = 1 fichier, 0 modification de la factory :**

```python
# adapters/gitlab_ci_adapter.py
from adapters.registry import AdapterRegistry
from adapters.base import BaseAdapter

@AdapterRegistry.register("gitlab_ci")
class GitLabCIAdapter(BaseAdapter):
    def trigger(self, ...): ...
    def get_status(self, ...): ...
```

Il suffit d'importer ce fichier (ex. dans `adapters/__init__.py` via `__all__`).

#### `services/registry.py`

Même pattern pour les services externes (Vault, Splunk, ServiceNow, Jira, Notification) :

```python
from services.registry import ServiceRegistry

@ServiceRegistry.register("vault")
class VaultService:
    ...
```

### Anti-patterns OCP à éviter

| Anti-pattern | Correct |
|--------------|---------|
| `if platform_type == "aap": ... elif platform_type == "tower": ...` dans la factory | Registry : `AdapterRegistry.get("aap")` |
| Ajouter une plateforme = modifier `adapters/__init__.py` | Ajouter un fichier `xxx_adapter.py` avec `@AdapterRegistry.register("xxx")` |
| Tâche Celery distincte `poll_xxx_job_status` par plateforme | Tâche générique qui délègue à l'adapter via le registre |

---

## 3. LSP — Liskov Substitution Principle

> Les sous-types doivent être substituables à leurs types de base sans altérer le comportement attendu.

### Conformité confirmée

L'audit Epic 33 a confirmé que les hiérarchies existantes respectent LSP :

- **`BaseAdapter`** : Toutes les sous-classes (`AAPAdapter`, `TowerAdapter`, `AzureDevOpsAdapter`, `GitHubActionsAdapter`, `TerraformAdapter`) implémentent le contrat complet : `trigger()`, `get_status()`, `get_job_logs()`, `cancel_execution()`. Aucune ne renforce les préconditions ni n'affaiblit les postconditions.
- **`OutputInterpreter`** : Les interpréteurs retournent un `NormalizedArtifact` conforme au type de retour déclaré.

### Règles pour les sous-classes

Lors de l'ajout d'un nouvel adapter ou interpréteur :

1. **Implémenter toutes les méthodes abstraites** — ne pas lever `NotImplementedError` dans les méthodes non optionnelles.
2. **Respecter les types de retour** — si `get_status()` retourne `ExecutionStatus`, toutes les sous-classes doivent retourner `ExecutionStatus`, pas `str`.
3. **Ne pas renforcer les préconditions** — si `BaseAdapter.trigger()` accepte `params: dict | None`, la sous-classe doit aussi l'accepter.
4. **Préserver les invariants** — si `BaseAdapter` garantit que `get_status()` ne lève jamais `ConnectionError` (mais retourne un statut d'erreur), les sous-classes doivent respecter ce contrat.

---

## 4. ISP — Interface Segregation Principle

> Les clients ne doivent pas dépendre d'interfaces qu'ils n'utilisent pas.

### Pattern — Props ciblées sur les sous-composants

Après le refactoring Story 33.5, les sous-composants reçoivent uniquement les props dont ils ont besoin :

**Avant (violation ISP) :**
```tsx
// ActionForm reçoit 15+ props et les passe toutes à chaque sous-composant
<ChangeTypeConfig
  action={action}
  platforms={platforms}
  engines={engines}
  integrations={integrations}
  profiles={profiles}
  // ... 10 autres props non utilisées par ChangeTypeConfig
/>
```

**Après (conforme) :**
```tsx
// ChangeTypeConfig reçoit uniquement ce dont elle a besoin
<ChangeTypeConfig
  changeTypeOptions={changeTypeOptions}
  selectedChangeType={formValues.change_type}
  onChangeTypeChange={handleChangeTypeChange}
/>
```

### Anti-patterns ISP à éviter

| Anti-pattern | Correct |
|--------------|---------|
| Composant qui dépend de 10+ hooks dont 7 ne sont utilisés que dans 1 sous-section | Extraire la sous-section en composant dédié avec ses propres hooks |
| Props "fourre-tout" passées transitivement de parent en enfant | Passer uniquement les valeurs et callbacks nécessaires |
| Hook retournant 20 valeurs quand le consommateur n'en utilise que 3 | Diviser en hooks spécialisés (`useFormState`, `useFormValidation`, `useFormSubmit`) |

---

## 5. DIP — Dependency Inversion Principle

> Dépendre des abstractions, pas des implémentations concrètes.

**Référence canonique :** [ADR-006 — Injection de dépendances (Option A)](decisions/adr-006-dependency-injection.md)

### Les 3 patterns Option A

#### Pattern 1 — Classes Python ordinaires : paramètre `__init__` optionnel

Pour `ContainerWorkflowRuntime`, `GateEvaluator`, `CatalogRBACService` et toute classe instanciée directement :

```python
class ContainerWorkflowRuntime:
    def __init__(
        self,
        execution: Execution,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self.execution_service = execution_service or ExecutionService()
```

**En test :**
```python
runtime = ContainerWorkflowRuntime(execution, execution_service=MockExecutionService())
```

Le fallback `or ServiceClass()` préserve la rétrocompatibilité : les appels sans argument continuent de fonctionner.

#### Pattern 2 — DRF ViewSets : attribut de classe + méthode surchargeable

Pour `ActionViewSet`, `CatalogActionViewSet`, `ProfileViewSet` et tout ViewSet DRF :

```python
class ActionViewSet(viewsets.ModelViewSet):
    _catalog_service_class: type[CatalogService] = CatalogService

    def get_catalog_service(self) -> CatalogService:
        return self._catalog_service_class()
```

**En test :**
```python
view = ActionViewSet()
view._catalog_service_class = MockCatalogService
response = view.list(request)
```

Cohérent avec les patterns DRF `get_queryset()` / `get_serializer_class()`.

#### Pattern 3 — Fonctions `@api_view` (niveau module) : factory callable

Pour les fonctions décorées `@api_view` dans `inventory/views.py`, `terraform_webhooks.py`, `github_webhooks.py` :

```python
# inventory/views.py — déclaré au niveau module
_inventory_service_factory = InventoryService

@api_view(['GET'])
def list_targets(request):
    inventory_service = _inventory_service_factory()
    ...
```

**En test :**
```python
import inventory.views as v
v._inventory_service_factory = lambda: MockInventoryService()
response = v.list_targets(mock_request)
```

### Module `core/di.py`

Helpers `get_xxx_service()` utilisables dans les contextes sans `self` (middleware, tâches Celery) et registre d'override pour les tests :

```python
from core.di import override_service, reset_services

# En test
override_service('catalog_service', lambda: MockCatalogService())
# ... appels ...
reset_services()
```

### Anti-patterns DIP à éviter

| Anti-pattern | Correct |
|--------------|---------|
| `self.service = CatalogService()` dans `__init__` sans paramètre optionnel | Pattern 1 : `self.service = service or CatalogService()` |
| `CatalogService()` direct dans une méthode de ViewSet | Pattern 2 : `self.get_catalog_service()` |
| `InventoryService()` direct dans une fonction `@api_view` | Pattern 3 : `_inventory_service_factory()` niveau module |
| Import `from services import ProfileService` suivi d'instanciation dans la vue | Utiliser `get_profile_service()` de `core/di.py` |

---

## 6. Anti-patterns référencés

Tableau condensé des violations corrigées dans l'Epic 33 :

| Principe | Fichier | Violation | Correction | Story |
|----------|---------|-----------|------------|-------|
| OCP | `adapters/__init__.py` | 6 `if/elif` pour dispatcher les plateformes | `AdapterRegistry` + `@register` | 33.1 |
| OCP | `services/__init__.py` | `if service_type == "vault"` … | `ServiceRegistry` + `@register` | 33.1 |
| SRP | `executions/tasks.py` (~1 580 LOC) | Retry + polling + gates + broadcast mélangés | Package `tasks/` : retry, polling, gates | 33.2 |
| SRP | `catalog/views.py` (~1 100 LOC) | 5 ViewSets dans un seul fichier | Package `views/` : 5 modules dédiés | 33.3 |
| DIP | Toutes les vues | `ExecutionService()` direct dans les méthodes | Patterns 1/2/3 + `core/di.py` | 33.4 |
| SRP / ISP | `ActionForm.tsx` (778 LOC) | Formulaire + état + validation + impact rules | Hooks `useActionForm*` + composants atomiques | 33.5 |
| SRP / ISP | `ActionWizard.tsx` (958 LOC) | Wizard + preview + remediation + ServiceNow mélangés | Hooks + sous-composants par étape | 33.5 |
| LSP | `BaseAdapter` | Conforme — aucune violation | — | — |
| ISP | Sous-composants admin | Props transitives non utilisées | Props ciblées après découpage SRP | 33.5 |
