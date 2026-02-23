# Rapport d'audit SOLID — IDP Portal

**Date :** 2026-02-21  
**Périmètre :** Backend Django (idp-portal/django_backend), Frontend React (idp-portal/frontend)

---

## Résumé exécutif

| Principe | Statut initial | Sévérité initiale | Fichiers principaux concernés | Statut post-Epic 33 |
|----------|----------------|-------------------|-------------------------------|---------------------|
| **SRP** (Single Responsibility) | Écarts | Moyenne | `executions/tasks.py`, `catalog/views.py`, `ActionForm.tsx`, `ActionWizard.tsx`, `ExecutionWizard.tsx` | **Résolu ✅** (33.2, 33.3, 33.5) |
| **OCP** (Open/Closed) | Écarts | Haute | `adapters/__init__.py`, `services/__init__.py`, `executions/tasks.py` | **Résolu ✅** (33.1) |
| **LSP** (Liskov Substitution) | Conforme | — | Hiérarchies BaseAdapter, OutputInterpreter | **Conforme ✅** |
| **ISP** (Interface Segregation) | Écarts mineurs | Faible | `ActionForm.tsx`, `ProfileForm.tsx` | **Amélioré ✅** (33.5) |
| **DIP** (Dependency Inversion) | Écarts | Haute | Vues, `ContainerWorkflowRuntime`, `catalog/rbac_service.py` | **Résolu ✅** (33.4) |

---

## 1. SRP — Single Responsibility Principle

> Une classe ne doit avoir qu'une seule raison de changer.

### Violations identifiées

#### Backend

| Fichier | LOC | Problème | Responsabilités mélangées |
|---------|-----|----------|---------------------------|
| `executions/tasks.py` | ~1 580 | God object | Retry workflow, polling AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, gate evaluation, broadcast WebSocket, audit |
| `catalog/views.py` | ~1 100 | ViewSet monolithique | ActionViewSet (admin CRUD), CatalogViewSet (catalogue), tags endpoint, remediation rules, business rules |
| `executions/services.py` | ~1 120 | Service trop large | Création exécution, validation, statut, planification, annulation, intégrations multiples |
| `inventory/services.py` | ~934 | Déjà partiellement découpé (26-1) | Orchestration + résolution source + exécution requêtes + RBAC |

#### Frontend

| Fichier | LOC | Problème |
|---------|-----|----------|
| `ActionWizard.tsx` | 943 | Formulaire 3 étapes + validation + impact rules + change type + remediation + preview |
| `ActionForm.tsx` | 765 | Formulaire + validation + steps + impact rules + change type config + remediation |
| `ExecutionWizard.tsx` | 640 | Wizard exécution + formulaires dynamiques + inventaire + planification |
| `ExecutionTimeline.tsx` | 735 | Timeline + logs + états + remediation + détails étape |

### Points positifs

- `InventoryService` délègue à `InventorySourceResolver`, `InventoryQueryExecutor`, `InventoryRBACFilter` (Story 26-1).
- `RuleEngine` utilise `OutputInterpreterRegistry` et des interpréteurs dédiés.
- `ExecutionView` délègue à `ExecutionTimeline` vs `WorkflowExecutionGraph` selon `item_type`.

---

## 2. OCP — Open/Closed Principle

> Les entités logicielles doivent être ouvertes à l'extension mais fermées à la modification.

### Violations identifiées

#### `adapters/__init__.py` (lignes 41-66)

```python
if platform_type == "aap":
    from adapters.aap_adapter import AAPAdapter
    return AAPAdapter(**kwargs)
if platform_type == "tower":
    from adapters.tower_adapter import TowerAdapter
    return TowerAdapter(**kwargs)
# ... 5 plateformes en if/elif
```

**Problème :** Ajouter une nouvelle plateforme (ex. GitLab CI) impose de modifier ce fichier.

**Solution :** Registry pattern — les adapters s'enregistrent eux-mêmes ; la factory interroge le registre.

#### `services/__init__.py` (lignes 46-64)

Même pattern pour `VaultService`, `SplunkService`, `ServiceNowService`, `JiraService`, `NotificationService`.

#### `executions/tasks.py`

- 5 tâches Celery distinctes : `poll_aap_job_status`, `poll_tower_job_status`, `poll_azure_devops_run_status`, `poll_github_actions_run_status`, `poll_terraform_cloud_run_status`.
- Chaque nouvelle plateforme nécessite une nouvelle tâche + modification du dispatch.

**Solution :** Tâche générique `poll_platform_job_status(platform_type, ...)` qui délègue à l'adapter, ou registre de tâches de polling.

#### `executions/rule_engine.py`

- `policy_type` avec `if policy_type == "review_if_modified"` — acceptable si peu de types, mais extensible via registry.

### Points positifs

- `OutputInterpreterRegistry` : nouveaux interpréteurs via enregistrement, pas de modification du `RuleEngine`.
- `BaseAdapter` : interface commune pour tous les adapters.

---

## 3. LSP — Liskov Substitution Principle

> Les sous-types doivent être substituables à leurs types de base.

### Analyse

- **BaseAdapter** : Les sous-classes (`AAPAdapter`, `TowerAdapter`, etc.) respectent le contrat (trigger, get_status, get_job_logs, cancel_execution). Aucune violation détectée.
- **OutputInterpreter** : Les interpréteurs retournent un `NormalizedArtifact` conforme. OK.
- **Mixins** : `IntegrationVaultValidationMixin`, `_RateLimitEnabledMixin` — usage standard Django/DRF, pas de violation LSP évidente.

**Verdict :** Conforme.

---

## 4. ISP — Interface Segregation Principle

> Les clients ne doivent pas dépendre d'interfaces qu'ils n'utilisent pas.

### Violations mineures

- **ActionForm** : Utilise de nombreux hooks (`useEngines`, `usePlatformIntegrations`, `useServiceNowIntegrations`, etc.) et types. Le composant dépend de beaucoup d'interfaces. Réduire en extrayant des sous-composants avec des props plus ciblées.
- **ProfileForm / ProfileWizard** : Mélange actions, targets, environnements. Interfaces potentiellement trop larges.

### Points positifs

- `BaseAdapter` : Méthodes focalisées (trigger, get_status, get_job_logs, cancel_execution).
- `OutputInterpreter` : Une seule méthode `interpret()`.

---

## 5. DIP — Dependency Inversion Principle

> Dépendre des abstractions, pas des implémentations concrètes.

### Violations identifiées

#### Instanciation directe des services

| Service | Utilisé dans (exemples) |
|---------|-------------------------|
| `ProfileService()` | `profiles/views.py` (7×), `idp_auth/views.py`, `catalog/rbac_service.py`, `executions/utils.py`, `profiles/validation.py` |
| `ExecutionService()` | `executions/views/execution_views.py`, `executions/views/approval_views.py`, `executions/container_workflow_runtime.py`, `executions/tasks.py`, `catalog/views.py` |
| `CatalogService()` | `catalog/views.py` (15×) |
| `InventoryService()` | `inventory/views.py` (7×), `inventory/mapper.py`, `executions/validators/target_validator.py`, `executions/gate_evaluator.py`, `executions/utils.py`, `catalog/rbac_service.py` |

#### Conséquences

- **Tests :** Difficile de mocker les services sans monkey-patching.
- **Évolution :** Remplacer une implémentation (ex. `ProfileService` par une version avec cache) impose des changements partout.
- **Configuration :** Pas de moyen centralisé d'injecter des implémentations alternatives (ex. stub en dev).

#### Patterns observés

- `ContainerWorkflowRuntime.__init__` : `self.execution_service = ExecutionService()` — couplage fort.
- `CatalogRBACService` : `profile_service = ProfileService()`, `inventory_service = InventoryService()` — instanciation interne.
- `InventoryService` : Construit `InventorySourceResolver`, `InventoryQueryExecutor`, `InventoryRBACFilter` en interne — acceptable si ces dépendances sont stables.

### Points positifs

- `RuleEngine` : Accepte un `registry` optionnel en paramètre pour les tests.
- `WorkflowRuntime` : Utilise `get_platform_adapter()` au lieu d'importer directement les adapters.
- `get_service_client()` et `get_platform_adapter()` : Centralisation de la création (mais toujours des factories, pas d'injection).

---

## 6. Synthèse des actions recommandées

| Priorité | Principe | Action |
|----------|----------|--------|
| P1 | OCP | Remplacer les if/elif dans `adapters/__init__.py` et `services/__init__.py` par un registry pattern |
| P1 | DIP | Introduire l'injection de dépendances (au moins pour les services principaux : ProfileService, ExecutionService, CatalogService, InventoryService) |
| P2 | SRP | Découper `executions/tasks.py` — extraire les tâches de polling ou créer une tâche générique |
| P2 | SRP | Découper `catalog/views.py` — séparer ActionViewSet, CatalogViewSet, tags dans des modules distincts |
| P3 | SRP | Réduire `ActionForm.tsx` et `ActionWizard.tsx` — extraire des sous-composants (ImpactRulesEditor, ChangeTypeConfig, etc.) |
| P3 | ISP | Réduire les dépendances des formulaires en passant des props plus ciblées |

---

## Références

- Exploration initiale : agent transcript (mcp_task explore)
- Fichiers audités : `adapters/__init__.py`, `services/__init__.py`, `executions/tasks.py`, `catalog/views.py`, `executions/container_workflow_runtime.py`, `executions/rule_engine.py`, composants frontend listés ci-dessus

---

## 7. État post-corrections (Epic 33)

| Principe | Sévérité initiale | Statut post-Epic 33 | Story |
|----------|------------------|---------------------|-------|
| OCP (adapters, services) | Haute | **Résolu ✅** | 33.1 |
| SRP (tasks.py, views.py) | Moyenne | **Résolu ✅** | 33.2, 33.3 |
| DIP (vues, runtimes) | Haute | **Résolu ✅** | 33.4 |
| SRP (ActionForm, ActionWizard) | Moyenne | **Résolu ✅** | 33.5 |
| LSP | Conforme | **Conforme ✅** | — |
| ISP | Faible | **Amélioré ✅** | 33.5 |

### Patterns implémentés

| Pattern | Description | Fichiers clés |
|---------|-------------|---------------|
| Registry OCP | Décorateur `@AdapterRegistry.register` / `@ServiceRegistry.register` — plus aucun `if/elif` de dispatch | `adapters/registry.py`, `services/registry.py` |
| Package SRP backend | `executions/tasks.py` → `tasks/` (retry, polling, gates) ; `catalog/views.py` → `views/` (5 modules) | `executions/tasks/__init__.py`, `catalog/views/__init__.py` |
| DIP Option A Pattern 1 | Paramètre `__init__` optionnel avec fallback `or ServiceClass()` | `executions/container_workflow_runtime.py`, `executions/gate_evaluator.py`, `catalog/rbac_service.py` |
| DIP Option A Pattern 2 | Attribut `_xxx_service_class` + méthode `get_xxx_service()` sur ViewSets | `catalog/views/action_views.py`, `profiles/views.py` |
| DIP Option A Pattern 3 | Factory callable `_xxx_factory = ServiceClass` au niveau module | `inventory/views.py`, `executions/views/terraform_webhooks.py`, `executions/views/github_webhooks.py` |
| Module `core/di.py` | Helpers `get_xxx_service()` + registre d'override pour les tests | `core/di.py` |
| Hooks + sous-composants ISP/SRP | `useActionFormState`, `useActionFormValidation`, composants atomiques | `frontend/src/hooks/useActionFormState.ts`, `frontend/src/components/admin/ImpactLevelsLegend.tsx` |

### Référence documentation

- Guide SOLID : `idp-portal/django_backend/docs/solid-guidelines.md`
- Checklist PR : `idp-portal/django_backend/docs/standards/solid-checklist.md`
- ADR-006 DIP : `idp-portal/django_backend/docs/decisions/adr-006-dependency-injection.md`
