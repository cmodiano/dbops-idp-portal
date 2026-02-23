# Checklist SOLID — IDP Portal

> **Objectif :** Vérifier la conformité SOLID avant chaque PR. S'assurer que les patterns établis dans l'Epic 33 sont maintenus.
> **Usage :** Cocher les items applicables avant de soumettre une Pull Request.
> **Référence :** [Guide SOLID complet](../solid-guidelines.md) — [ADR-006 DIP](../decisions/adr-006-dependency-injection.md)

---

## 1. SRP — Single Responsibility (Responsabilité Unique)

| Item | ✅ Conforme | ❌ Non-conforme |
|------|------------|----------------|
| **Backend : fichier ≤ 500 LOC** | `catalog/views/action_views.py` : 320 LOC, 1 ViewSet | `catalog/views.py` : 1 100 LOC, 5 ViewSets mélangés |
| **Backend : une responsabilité par module** | `executions/tasks/polling.py` : uniquement le polling multi-plateforme | `executions/tasks.py` : retry + polling + gates + broadcast |
| **Backend : `__init__.py` = ré-exports uniquement** | `catalog/views/__init__.py` : `from .action_views import ActionViewSet` | `executions/tasks/__init__.py` contenant 200 LOC de logique métier |
| **Frontend : composant ≤ 700 LOC** | `ChangeTypeConfig.tsx` : ~120 LOC, 1 panneau de configuration | `ActionForm.tsx` avant Story 33.5 : 778 LOC, formulaire + état + validation |
| **Frontend : hooks dans `hooks/`** | `hooks/useActionFormState.ts` : état du formulaire uniquement | `ActionForm.tsx` gérant l'état interne sans hook dédié |
| **Frontend : sous-composants atomiques** | `ImpactLevelsLegend.tsx` : affichage des niveaux d'impact | `ActionWizard.tsx` contenant le rendu de 3 étapes + preview + remediation |

---

## 2. OCP — Open/Closed (Ouvert/Fermé)

| Item | ✅ Conforme | ❌ Non-conforme |
|------|------------|----------------|
| **Aucun `if/elif` ajouté pour dispatcher une nouvelle plateforme** | `AdapterRegistry.get("gitlab_ci")` — 0 modification de la factory | `if platform_type == "aap": ... elif platform_type == "tower": ...` dans `adapters/__init__.py` |
| **Nouvel adapter = 1 fichier avec `@AdapterRegistry.register`** | `@AdapterRegistry.register("gitlab_ci")` dans `gitlab_ci_adapter.py` | Ajouter `from adapters.gitlab_ci_adapter import GitLabCIAdapter` + `elif` dans la factory |
| **Nouveau service externe = `@ServiceRegistry.register`** | `@ServiceRegistry.register("pagerduty")` dans `pagerduty_service.py` | `if service_type == "pagerduty":` dans `services/__init__.py` |
| **`OutputInterpreterRegistry` pour les interpréteurs de résultats** | `OutputInterpreterRegistry.get_instance().register("terraform", TerraformInterpreter())` | `if platform == "terraform":` dans `rule_engine.py` |

---

## 3. DIP — Dependency Inversion (Inversion de dépendances)

| Item | ✅ Conforme | ❌ Non-conforme |
|------|------------|----------------|
| **Aucun `ServiceClass()` direct dans les vues DRF — utiliser `get_xxx_service()`** | `service = self.get_catalog_service()` dans `ActionViewSet` | `service = CatalogService()` directement dans une méthode de vue |
| **ViewSets : attribut de classe `_xxx_service_class` + méthode `get_xxx_service()`** | `_catalog_service_class: type[CatalogService] = CatalogService` | Instanciation directe `CatalogService()` sans indirection |
| **Aucun `ServiceClass()` direct dans les classes — utiliser paramètre `__init__` optionnel** | `self.execution_service = execution_service or ExecutionService()` | `self.execution_service = ExecutionService()` sans paramètre optionnel |
| **Fonctions `@api_view` : factory callable niveau module** | `_inventory_service_factory = InventoryService` au niveau module | `service = InventoryService()` interne à la fonction décorée |
| **Tests : injection de mocks sans monkey-patching d'imports** | `view._catalog_service_class = MockCatalogService` | `with patch('catalog.views.CatalogService') as mock:` (fragile) |

---

## 4. ISP — Interface Segregation (Ségrégation d'interface)

| Item | ✅ Conforme | ❌ Non-conforme |
|------|------------|----------------|
| **Sous-composants avec props minimales** | `<ChangeTypeConfig changeTypeOptions={opts} onChange={cb} />` | `<ChangeTypeConfig action={action} platforms={platforms} engines={engines} integrations={integrations} profiles={profiles} .../>` (10+ props non utilisées) |
| **Hooks de formulaire dans `hooks/`** | `useActionFormValidation` : expose uniquement `errors`, `validate`, `clearError` | Un seul hook `useActionForm` retournant 20+ valeurs dont 15 inutilisées par le consommateur |
| **Props passées = props utilisées** | Chaque prop d'un composant est consommée dans son JSX | Props "de transit" passées 3 niveaux pour atteindre un sous-sous-composant |

---

## 5. LSP — Liskov Substitution (Substitution de Liskov)

| Item | ✅ Conforme | ❌ Non-conforme |
|------|------------|----------------|
| **Nouvel adapter implémente toutes les méthodes abstraites de `BaseAdapter`** | `GitLabCIAdapter` implémente `trigger`, `get_status`, `get_job_logs`, `cancel_execution` | `GitLabCIAdapter.cancel_execution()` lève `NotImplementedError` (méthode non optionnelle) |
| **Types de retour respectés** | `get_status()` retourne `ExecutionStatus` dans toutes les sous-classes | Une sous-classe retourne `str` au lieu de `ExecutionStatus` |
| **Préconditions non renforcées** | `BaseAdapter.trigger(params: dict | None)` → sous-classe accepte aussi `None` | Sous-classe exige `params: dict` (non-None), contrat plus strict |

---

## Références

- [Guide SOLID complet](../solid-guidelines.md)
- [ADR-006 — Injection de dépendances (Option A)](../decisions/adr-006-dependency-injection.md)
- [Checklist nouvel endpoint DRF](endpoint-checklist.md)
- [Pre-PR security checklist](../security/pre-pr-checklist.md)
