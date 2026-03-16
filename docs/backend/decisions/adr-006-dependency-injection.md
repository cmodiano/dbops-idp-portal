# ADR-006 : Injection de dépendances pour les services principaux (Option A)

**Date :** 2026-02-21
**Statut :** Accepté
**Décideurs :** Équipe IDP Portal (Story 33.4 — Conformité SOLID / DIP)

## Contexte

L'audit SOLID (epic 33) a identifié plusieurs violations du **Dependency Inversion Principle** : les
vues, runtimes et services du backend instancient directement leurs dépendances
(`ProfileService()`, `ExecutionService()`, `CatalogService()`, `InventoryService()`).

Cela empêche les tests unitaires d'isoler les composants : les tests qui veulent vérifier la logique
d'une vue doivent soit accéder à la base Oracle (inexistante en CI), soit recourir au
monkey-patching fragile des imports.

### Consommateurs concernés (scope de la story 33.4)

| Pattern | Consommateurs |
|---------|--------------|
| Classes Python ordinaires | `ContainerWorkflowRuntime`, `GateEvaluator`, `CatalogRBACService` |
| DRF ViewSets | `ProfileViewSet`, `ActionViewSet`, `CatalogActionViewSet` |
| DRF APIViews | `ExecutionsCreateView`, `ExecutionCancelView`, `ApproveExecutionView`, `RejectExecutionView` |
| `@api_view` (module level) | `inventory/views.py` (×7), `terraform_webhooks.py`, `github_webhooks.py` |

## Décision

Adopter l'**Option A** : injection légère sans framework, fondée sur trois patterns
complémentaires selon le type de consommateur.

### Pattern 1 — Classes Python ordinaires : paramètre `__init__` optionnel

```python
class ContainerWorkflowRuntime:
    def __init__(
        self,
        execution: Execution,
        execution_service: ExecutionService | None = None,
    ) -> None:
        self.execution_service = execution_service or ExecutionService()
```

Le fallback `or ServiceClass()` préserve la rétrocompatibilité : les appels existants sans
argument continuent de fonctionner.

### Pattern 2 — DRF ViewSets / APIViews : attribut de classe + méthode surchargeable

```python
class ActionViewSet(viewsets.ModelViewSet):
    _catalog_service_class: type[CatalogService] = CatalogService

    def get_catalog_service(self) -> CatalogService:
        return self._catalog_service_class()
```

Dans les tests, surcharger `view._catalog_service_class = MockCatalogService` avant l'appel.
Cohérent avec le pattern `get_queryset()` / `get_serializer_class()` de DRF.

### Pattern 3 — Fonctions `@api_view` (niveau module) : factory callable

```python
# inventory/views.py — niveau module
_inventory_service_factory = InventoryService

@api_view(['GET'])
def list_targets(request):
    inventory_service = _inventory_service_factory()
    ...
```

Dans les tests :
```python
import inventory.views as v
v._inventory_service_factory = lambda: MockInventoryService()
```

### Module `core/di.py` (nouveau)

Fournit des helpers `get_xxx_service()` utilisables dans les contextes où l'injection directe
n'est pas possible (middleware, tâches Celery hors scope de la story) et un registre
d'override pour les tests :

```python
from core.di import override_service, reset_services
override_service('catalog_service', lambda: MockCatalogService())
# ... test ...
reset_services()
```

## Conséquences

### Positives
- Les tests peuvent injecter des mocks **sans monkey-patching** des imports.
- Rétrocompatibilité totale : aucun test existant modifié.
- Aucune dépendance externe ajoutée.
- Cohérent avec les patterns DRF existants (`get_queryset`, `get_serializer_class`).
- Ouvre la voie à l'introduction de Protocoles/ABCs en story 33.6.

### Négatives
- Légère duplication : chaque ViewSet/APIView répète `_xxx_service_class` + `get_xxx_service()`.
  Acceptable pour éviter l'over-engineering ; une classe mixin pourrait être introduite en 33.6.
- Les fichiers hors scope (tâches Celery, utils, validateurs) conservent l'instanciation directe ;
  à traiter dans la story 33.6.

### Neutres
- `core/di.py` est optionnel pour les vues mais utile pour les contextes sans `self`.

## Alternatives Considérées

### Alternative 1 : Framework DI externe (Dependency Injector, injector, pinject)

- **Description :** Configurer un container IoC, déclarer les bindings, utiliser les décorateurs
  `@inject`.
- **Raison du rejet :** Over-engineering pour un projet sans couche applicative complexe.
  Introduce une dépendance externe, une courbe d'apprentissage, et rend le code moins lisible
  pour les nouveaux contributeurs.

### Alternative 2 : `override_settings(SERVICES=...)`

- **Description :** Stocker les classes de services dans `settings.py` et les charger via
  `django.conf.settings`.
- **Raison du rejet :** Contourne le type-checking (perd la résolution statique des types).
  Fragile : les attributs de classe DRF chargés au démarrage (ex. `THROTTLE_RATES`) ne
  bénéficient pas de `override_settings` (voir MEMORY.md — `SimpleRateThrottle`).

### Alternative 3 : Protocoles/ABCs + container de services

- **Description :** Définir des interfaces `ProfileServiceProtocol`, etc., et un container
  centralisé injecté en WSGI startup.
- **Raison du rejet :** Prévu en story 33.6. Prématuré avant validation des patterns d'injection
  légers introduits ici.

## Références

- Story 33.4 : `_bmad-output/implementation-artifacts/33-4-dip-injection-dependances-services.md`
- Audit SOLID : `_bmad-output/planning-artifacts/solid-audit-report.md`
- Epic 33 : `_bmad-output/planning-artifacts/epic-33-conformite-solid.md`
- `core/di.py` : module d'injection créé dans cette story
- DRF patterns : `get_queryset()`, `get_serializer_class()` — même philosophie de surcharge
