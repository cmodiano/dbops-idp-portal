# Guide de développement — Architecture d'extension et extensibilité

**Date :** 2026-03-16

Ce guide documente les mécanismes d'extension du backend IDP-Portal : les registries, l'injection de dépendances, et les procédures pas à pas pour ajouter un adapter, un service, un gate, une plateforme ou une intégration.

---

## Table des matières

1. [Vue d'ensemble de l'architecture d'extension](#vue-densemble-de-larchitecture-dextension)
2. [AdapterRegistry](#adapterregistry)
3. [PlatformRegistry](#platformregistry)
4. [ServiceRegistry + ServiceDefinitionRegistry](#serviceregistry--servicedefinitionregistry)
5. [GateDefinitionRegistry](#gatedefinitionregistry)
6. [StepHandlerRegistry](#stephandlerregistry)
7. [Registries secondaires](#registries-secondaires)
8. [Injection de dépendances (core/di.py)](#injection-de-dépendances-coredipy)
9. [Ajouter un adapter (nouvelle plateforme d'exécution)](#ajouter-un-adapter-nouvelle-plateforme-dexécution)
10. [Ajouter un service (nouvelle intégration)](#ajouter-un-service-nouvelle-intégration)
11. [Ajouter un gate (nouveau type de condition)](#ajouter-un-gate-nouveau-type-de-condition)
12. [Ajouter une plateforme (PlatformDefinition)](#ajouter-une-plateforme-platformdefinition)
13. [Ajouter une intégration (INTEGRATION_TYPE_CATALOGUE)](#ajouter-une-intégration-integration_type_catalogue)
14. [JSON Schemas](#json-schemas)

---

## Vue d'ensemble de l'architecture d'extension

Le backend IDP-Portal utilise un **pattern Registry + Factory** pour découpler les abstractions de leurs implémentations concrètes. Chaque type d'extension (plateforme d'exécution, service externe, gate de validation, etc.) dispose d'un registry dédié qui :

- **Enregistre** les implémentations au démarrage de l'application (à l'import des modules)
- **Résout** dynamiquement l'implémentation à utiliser selon un identifiant (clé de registre)
- **Instancie** l'implémentation via une factory function

Ce pattern élimine les blocs `if/elif` et permet d'ajouter de nouvelles implémentations sans modifier le code existant (principe ouvert/fermé).

### Les 5 registries principaux

| Registry | Module source | Singleton | Clé d'enregistrement | Rôle |
|----------|--------------|-----------|---------------------|------|
| `AdapterRegistry` | `adapters/registry.py` | `adapter_registry` | `platform_type` (str) | Factory des clients d'exécution (AAP, Azure DevOps, etc.) |
| `PlatformRegistry` | `platforms/registry.py` | `platform_registry` | `code` (str) | Métadonnées des plateformes (schémas, alias, config) |
| `ServiceRegistry` | `services/registry.py` | `service_registry` | `service_type` (str) | Factory des clients de services (Vault, ServiceNow, etc.) |
| `ServiceDefinitionRegistry` | `services/definitions.py` | `service_definition_registry` | `code` (str) | Métadonnées des services (opérations, schémas UI) |
| `GateDefinitionRegistry` | `executions/gates/definitions.py` | `gate_registry` | `gate_type` (str) | Définitions des gates (stratégies d'évaluation/résolution) |

### Registries complémentaires

| Registry | Module source | Singleton | Rôle |
|----------|--------------|-----------|------|
| `StepHandlerRegistry` | `executions/app/handlers/registry.py` | `step_handler_registry` | Dispatch des handlers de steps |
| `OutputInterpreterRegistry` | `executions/interpreters/registry.py` | Via `get_instance()` | Interprétation des sorties d'exécution |
| `OutputSchemaRegistry` | `output_schemas/registry.py` | `schema_registry` | Résolution des schémas de sortie (avec héritage) |

### Flux d'enregistrement

```
Démarrage Django
    └── Import des modules (__init__.py)
        ├── adapters/__init__.py → adapter_registry.register(...)
        ├── platforms/registry.py → platform_registry.register(...)
        ├── services/__init__.py → service_registry.register(...) + service_definition_registry.register(...)
        └── executions/gates/registry.py → gate_registry.register(...)
```

L'enregistrement s'effectue au moment de l'import des modules, en contexte mono-thread. Les registries qui supportent les accès concurrents (multi-thread) sont signalés explicitement.

---

## AdapterRegistry

**Module :** `adapters/registry.py`
**Singleton :** `adapter_registry` (importable depuis `adapters`)

### Rôle

Mappe un `platform_type` (ex : `'aap'`) vers une factory callable qui crée une instance d'adapter d'exécution. Gère aussi la queue Celery associée à chaque plateforme.

### Interface

```python
from adapters import adapter_registry

# Enregistrer un adapter
adapter_registry.register(
    platform_type: str,       # Identifiant unique (ex: 'aap')
    factory: Callable,         # Factory → BaseAdapter
    queue: str | None = None   # Queue Celery (ex: 'aap', 'azure')
)

# Obtenir la factory et créer une instance
adapter = adapter_registry.get(platform_type, **kwargs)  # → BaseAdapter

# Obtenir la queue Celery
queue = adapter_registry.get_queue(platform_type)  # → str (défaut: 'default')

# Lister les types enregistrés
types = adapter_registry.list_types()  # → list[str]

# Lister les queues uniques
queues = adapter_registry.list_queues()  # → list[str]

# Supprimer un enregistrement (tests)
adapter_registry.unregister(platform_type)
```

### Interface des adapters

Les adapters implémentent deux interfaces définies dans `adapters/base_adapter.py` :

- **`ITriggerableAdapter`** (ABC) — Interface obligatoire :
  - `async trigger(**kwargs) → dict` — Lance une exécution distante
  - `async get_status(platform_job_id, **kwargs) → dict` — Récupère le statut
  - `async get_job_logs(platform_job_id, **kwargs) → dict` — Récupère les logs

- **`ICancellableAdapter`** (ABC) — Interface optionnelle :
  - `async cancel_execution(platform_job_id, **kwargs) → None` — Annule une exécution

- **`BaseAdapter`** = `ITriggerableAdapter` + `ICancellableAdapter` — Utilisée par les adapters existants qui supportent l'annulation.

- **`IHealthCheckable`** (ABC, `integrations/health_check.py`, ré-exportée depuis `adapters.base_adapter`) — Interface optionnelle :
  - `async health_check(**kwargs) → dict` — Vérifie la connectivité et la santé de la plateforme
  - Les adapters implémentant cette interface seront appelés quand `PlatformDefinition.supports_health_check=True`
  - Le code appelant vérifie `isinstance(adapter, IHealthCheckable)` avant d'appeler `health_check()`

### Adapters enregistrés

| `platform_type` | Factory | Queue Celery | Notes |
|-----------------|---------|-------------|-------|
| `aap` | `_factory_aap` | `aap` | Ansible Automation Platform |
| `tower` | `_factory_tower` | `aap` | Partage la queue avec AAP. Paramètre additionnel : `ssl_verify: bool = False` |
| `azure_devops` | `_factory_azure_devops` | `azure` | Azure DevOps Pipelines |
| `github_actions` | `_factory_github_actions` | `github` | Requiert `owner` + `repo` |
| `terraform_cloud` | `_factory_terraform_cloud` | `terraform` | Requiert `organization` |

### Fonction publique

```python
from adapters import get_platform_adapter

adapter = get_platform_adapter(
    platform_type="aap",
    base_url="https://aap.example.com",
    auth_headers={"Authorization": "Bearer xxx"},
    timeout=30.0,
    **platform_kwargs  # Kwargs supplémentaires (ex: owner, repo pour GitHub)
)
```

Cette fonction délègue à `adapter_registry.get()` — aucun `if/elif` dans le code appelant.

---

## PlatformRegistry

**Module :** `platforms/registry.py`
**Singleton :** `platform_registry` (importable depuis `platforms`)

### Rôle

Registre des `PlatformDefinition` — source de vérité sur les plateformes supportées, leurs schémas de configuration et leurs comportements. Supporte la résolution d'alias (ex : `'azuredevops'` → `'azure_devops'`).

### Classe PlatformDefinition

Dataclass frozen définie dans `platforms/definitions.py` :

| Attribut | Type | Description |
|----------|------|-------------|
| `code` | `str` | Identifiant canonique (ex : `'aap'`) |
| `display_name` | `str` | Nom affiché (ex : `'Ansible Automation Platform'`) |
| `aliases` | `frozenset[str]` | Alias acceptés (ex : `{'azuredevops'}`) |
| `icon` | `str` | Identifiant de l'icône frontend |
| `connector_type` | `str` | Type de connecteur |
| `action_platform_code` | `str` | Valeur stockée en BD (ex : `'AAP'`) |
| `supports_health_check` | `bool` | Supporte le health check |
| `runtime_kwargs_required` | `tuple[str, ...]` | Kwargs obligatoires au runtime |
| `runtime_kwargs_optional` | `dict[str, object]` | Kwargs optionnels avec valeurs par défaut |
| `action_config_schema` | `dict` | JSON Schema de la config des actions |
| `runtime_config_schema` | `dict` | JSON Schema de la config runtime |
| `health_check_policy` | `dict` | Politique de health check |

### Interface

```python
from platforms import platform_registry

# Enregistrer une plateforme
platform_registry.register(definition: PlatformDefinition)

# Obtenir une définition (par code canonique)
definition = platform_registry.get("aap")  # → PlatformDefinition

# Résoudre un alias vers le code canonique
code = platform_registry.resolve_alias("azuredevops")  # → 'azure_devops'

# Recherche inverse par code BD
definition = platform_registry.get_by_action_platform_code("AAP")

# Vérifier l'existence
exists = platform_registry.is_registered("aap")  # → bool

# Lister les codes canoniques
types = platform_registry.list_types()  # → list[str]
```

### Plateformes enregistrées

| Code | Display Name | Aliases | `action_platform_code` | Health Check | Kwargs requis |
|------|-------------|---------|----------------------|-------------|--------------|
| `aap` | Ansible Automation Platform | — | `AAP` | Oui | — |
| `tower` | Ansible Tower | — | `Tower` | Oui | — |
| `azure_devops` | Azure DevOps | `azuredevops` | `Azure DevOps` | Oui | — |
| `github_actions` | GitHub Actions | — | `GitHub Actions` | Oui | `owner`, `repo` |
| `terraform_cloud` | Terraform Cloud | `terraform` | `Terraform` | Oui | `organization` |

---

## ServiceRegistry + ServiceDefinitionRegistry

**Modules :** `services/registry.py` + `services/definitions.py`
**Singletons :** `service_registry` (factories) + `service_definition_registry` (métadonnées)

### Rôle

Double registry — `ServiceRegistry` mappe `service_type → factory`, `ServiceDefinitionRegistry` mappe `service_type → ServiceDefinition` (métadonnées et opérations). Les deux registres **doivent rester synchronisés** : une assertion guard dans `services/__init__.py` vérifie l'alignement au démarrage.

### Classes clés

**`ServiceDefinition`** (dataclass frozen, `services/definitions.py`) :

| Attribut | Type | Description |
|----------|------|-------------|
| `code` | `str` | Identifiant (ex : `'vault'`) |
| `display_name` | `str` | Nom affiché (ex : `'HashiCorp Vault'`) |
| `requires_integration` | `bool` | Nécessite une intégration configurée |
| `operation_defs` | `tuple[ServiceOperationDefinition, ...]` | Opérations supportées |
| `supports_health_check` | `bool` | Supporte le health check |

Propriétés calculées :
- `operations → frozenset[str]` — Ensemble des codes d'opérations
- `supports_service_call → bool` — `True` si des opérations sont définies

**`ServiceOperationDefinition`** (dataclass frozen) :

| Attribut | Type | Description |
|----------|------|-------------|
| `code` | `str` | Code de l'opération (ex : `'create_change'`) |
| `label` | `str` | Libellé affiché (ex : `'Créer un change'`) |
| `input_schema` | `dict` | JSON Schema des paramètres d'entrée |
| `output_schema` | `dict` | JSON Schema de la réponse |
| `ui_hints` | `dict` | Indices de rendu UI |

### Interface ServiceRegistry

```python
from services import service_registry

service_registry.register(service_type: str, factory: Callable)
client = service_registry.get(service_type, **config)  # → instance du client
types = service_registry.list_types()  # → list[str]
service_registry.unregister(service_type)  # Tests uniquement
```

### Interface ServiceDefinitionRegistry

```python
from services import service_definition_registry

service_definition_registry.register(definition: ServiceDefinition)
definition = service_definition_registry.get(code)  # → ServiceDefinition
operations = service_definition_registry.get_allowed_operations(code)  # → frozenset[str]
is_free = service_definition_registry.is_credential_free(code)  # → bool
op_def = service_definition_registry.get_operation_def(service_code, operation_code)  # → ServiceOperationDefinition
```

### Services enregistrés

| `service_type` | Display Name | `requires_integration` | Health Check | Opérations |
|---------------|-------------|----------------------|-------------|-----------|
| `vault` | HashiCorp Vault | Oui | Oui | `get_secret` |
| `splunk` | Splunk | Oui | Oui | — (health check uniquement) |
| `servicenow` | ServiceNow | Oui | Oui | `create_change`, `update_change`, `close_change`, `get_change_status`, `cancel_change` |
| `jira` | Jira | Oui | Oui | `create_issue`, `update_issue`, `get_issue` |
| `notification` | Notification | **Non** | Non | `send_email`, `send_teams`, `notify_execution_event` |

### Assertion guard

```python
# services/__init__.py — exécuté à l'import
_registry_types = set(service_registry.list_types())
_definition_types = set(service_definition_registry.list_types())
assert _registry_types == _definition_types, (
    f"service_registry and service_definition_registry are out of sync. "
    f"service_registry-only: {_registry_types - _definition_types}, "
    f"service_definition_registry-only: {_definition_types - _registry_types}"
)
```

Si un service est enregistré dans un seul des deux registres, l'application **ne démarre pas**.

### Fonction publique

```python
from services import get_service_client

client = get_service_client("vault", base_url="https://vault.example.com", token="xxx")
```

---

## GateDefinitionRegistry

**Module :** `executions/gates/definitions.py` (classes) + `executions/gates/registry.py` (enregistrement)
**Singleton :** `gate_registry` (importable depuis `executions/gates`)

### Rôle

Registre des types de gates — conditions de validation inter-steps dans un workflow d'exécution. Indexation duale : par `gate_type` et par `condition_type`.

> **Contrainte Django :** Ce registry nécessite que Django soit initialisé avant l'import (les strategies font des requêtes ORM). Ne pas importer en dehors du contexte Django.

### Classe GateDefinition

Dataclass frozen :

| Attribut | Type | Description |
|----------|------|-------------|
| `gate_type` | `str` | Identifiant du gate (ex : `'maintenance_window'`) |
| `condition_type` | `str` | Type de condition (ex : `'maintenance_window_open'`) |
| `display_name` | `str` | Nom affiché |
| `category` | `str` | Catégorie sémantique |
| `config_schema` | `dict` | JSON Schema de la config |
| `supports_timeout` | `bool` | Si `timeout_hours` est configurable |
| `requires_manual_resolution` | `bool` | `True` = résolution via endpoint `/approve/` |
| `evaluation_strategy` | `GateEvaluationStrategy \| None` | Stratégie d'auto-évaluation |
| `resolution_strategy` | `GateResolutionStrategy \| None` | Stratégie de résolution manuelle |

### Protocoles (interfaces)

```python
# Auto-évaluation (ex : maintenance_window)
class GateEvaluationStrategy(Protocol):
    def evaluate(ctx: GateEvaluationContext) -> tuple[bool, dict]: ...

# Résolution manuelle (ex : approval)
class GateResolutionStrategy(Protocol):
    def resolve(ctx: GateEvaluationContext) -> tuple[bool, dict]: ...
```

Un gate utilise **l'un ou l'autre** (pas les deux) :
- **Auto-évaluation** : le système vérifie périodiquement la condition (ex : la fenêtre de maintenance est-elle ouverte ?)
- **Résolution manuelle** : un utilisateur approuve via l'API REST (`/approve/`)

### Interface

```python
from executions.gates import gate_registry

gate_registry.register(definition: GateDefinition)
definition = gate_registry.get(gate_type)  # → GateDefinition
definition = gate_registry.get_for_condition_type(condition_type)  # Index inversé
is_manual = gate_registry.is_manual_condition_type(condition_type)  # → bool
valid_types = gate_registry.get_valid_condition_types()  # → frozenset[str]
```

### Gates enregistrés

| `gate_type` | `condition_type` | Mode | Stratégie | `supports_timeout` |
|-------------|-----------------|------|-----------|-------------------|
| `maintenance_window` | `maintenance_window` | Auto | `MaintenanceWindowEvaluationStrategy` | Oui |
| `approval` | `approval_granted` | Manuel | — (`requires_manual_resolution=True`) | Oui |

---

## StepHandlerRegistry

**Module :** `executions/app/handlers/registry.py`
**Singleton :** `step_handler_registry`

### Rôle

Mappe un `step_type` vers une **classe** handler (pas une instance). Les handlers sont instanciés à la demande lors de l'exécution d'un step.

### Interface

```python
from executions.app.handlers.registry import step_handler_registry

step_handler_registry.register(step_type: str, handler_class: type)
handler_class = step_handler_registry.get(step_type)  # → type | None
types = step_handler_registry.list_types()  # → list[str]
exists = step_handler_registry.is_registered(step_type)  # → bool
```

### Handlers enregistrés

| `step_type` | Handler Class | Rôle |
|-------------|--------------|------|
| `service_call` | `ServiceCallHandler` | Appel d'un service (Vault, ServiceNow, Jira...) |
| `http_request` | `HttpRequestHandler` | Requête HTTP directe |
| `evaluation` | `EvaluationHandler` | Évaluation d'une expression/condition |
| `gate` | `GateHandler` | Évaluation d'un gate (délègue au `GateDefinitionRegistry`) |

> **Note :** `'platform'` est **intentionnellement absent** — les steps de type plateforme sont gérés via des **child executions** (exécution enfant déclenchée par l'adapter), pas via un handler direct.

### Rétrocompatibilité

Un shim dans `executions/step_handlers/registry.py` ré-exporte le registry depuis `executions/app/handlers/registry.py` (mis en place lors de la Story 85-4).

---

## Registries secondaires

### OutputInterpreterRegistry

**Module :** `executions/interpreters/registry.py`
**Singleton :** Via `OutputInterpreterRegistry.get_instance()` (thread-safe)

**Rôle :** Mappe un `step_type` vers une instance `OutputInterpreter` qui transforme et interprète les sorties brutes d'exécution.

**Thread-safety :** Utilise `threading.Lock` pour l'accès concurrent — le singleton et les opérations `register`/`get` sont protégés.

```python
from executions.interpreters.registry import OutputInterpreterRegistry

registry = OutputInterpreterRegistry.get_instance()
registry.register(step_type: str, interpreter: OutputInterpreter)
interpreter = registry.get(step_type)  # → OutputInterpreter | None
registered = registry.list_registered()  # → dict[str, type]
```

**Interpreters enregistrés :**

| `step_type` | Interpreter | Rôle |
|-------------|------------|------|
| `terraform_cloud` | `TerraformPlanInterpreter` | Interprétation des plans Terraform |
| `aap` | `AAPOutputInterpreter` | Interprétation des sorties AAP |

L'enregistrement s'effectue automatiquement à l'import du module `executions/interpreters/__init__.py`.

### OutputSchemaRegistry

**Module :** `output_schemas/registry.py`
**Singleton :** `schema_registry`

**Rôle :** Résolution des schémas de sortie avec cache mémoire et support d'héritage 1-niveau. Requiert l'ORM Django (requêtes sur le modèle `OutputSchema`).

**Thread-safety :** Utilise `threading.Lock` + versionnage interne pour éviter les écritures stales après invalidation.

```python
from output_schemas.registry import schema_registry

# Résolution par type
schema = schema_registry.get_action_schema(action_name)  # → dict | None
schema = schema_registry.get_integration_schema(integration_type, operation)
schema = schema_registry.get_platform_convention(convention_name)

# Invalidation du cache
schema_registry.invalidate()
```

**Héritage :** Un schéma peut hériter d'un autre (1 niveau). Lors de la résolution, les champs du schéma enfant sont mergés avec ceux du parent. Les variables de template sont remplacées.

---

## Injection de dépendances (core/di.py)

**Module :** `core/di.py`

### Rôle

Fournit une injection de dépendances légère (sans framework externe) pour les 4 services applicatifs principaux. Utilise des **lazy imports** pour éviter les circular imports.

### Design

- Pas de framework DI externe
- Imports paresseux (le module du service n'est importé qu'au premier appel)
- Override possible dans les tests sans `override_settings`

### Services disponibles

| Getter | Service retourné | Module source |
|--------|-----------------|---------------|
| `get_profile_service()` | `ProfileService` | `profiles.services` |
| `get_execution_service()` | `ExecutionService` | `executions.services` |
| `get_catalog_service()` | `CatalogService` | `catalog.services` |
| `get_inventory_service()` | `InventoryService` | `inventory.services` |

### Usage en production

```python
from core.di import get_execution_service

service = get_execution_service()
result = service.launch_execution(workflow_id=42)
```

### Usage dans les tests (override)

```python
from core.di import override_service, reset_services

def test_my_feature():
    mock_service = Mock()
    override_service('execution_service', lambda: mock_service)
    try:
        # Le code testé utilisera mock_service au lieu du vrai service
        result = some_function_that_uses_execution_service()
        mock_service.launch_execution.assert_called_once()
    finally:
        reset_services()  # Toujours nettoyer après le test
```

Les noms acceptés pour `override_service` : `'profile_service'`, `'execution_service'`, `'catalog_service'`, `'inventory_service'`.

---

## Ajouter un adapter (nouvelle plateforme d'exécution)

### Prérequis

- Comprendre l'interface `ITriggerableAdapter` (ou `BaseAdapter` si l'annulation est supportée)
- Connaître l'API de la plateforme cible

### Procédure

**Étape 1 — Créer le client adapter**

Créer `adapters/<platform>/client.py` avec une classe héritant de `ITriggerableAdapter` (ou `BaseAdapter` si l'annulation est supportée) :

```python
# adapters/my_platform/client.py
from adapters.base_adapter import ITriggerableAdapter

class MyPlatformAdapter(ITriggerableAdapter):
    def __init__(self, base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs):
        self.base_url = base_url
        self.auth_headers = auth_headers
        self.timeout = timeout

    async def trigger(self, **kwargs) -> dict:
        """Lance une exécution sur la plateforme."""
        # Implémenter l'appel API
        return {"platform_job_id": "...", "status": "pending", "url": "..."}

    async def get_status(self, platform_job_id: str, **kwargs) -> dict:
        """Récupère le statut d'une exécution."""
        return {"status": "running", "progress": 50}

    async def get_job_logs(self, platform_job_id: str, **kwargs) -> dict:
        """Récupère les logs d'exécution."""
        return {
            "content": "...",
            "format": "text",
            "timestamp": "...",
            "complete": False,
            "job_status": "running"
        }
```

**Étape 2 — Créer la factory function**

Dans `adapters/__init__.py`, ajouter la factory :

```python
def _factory_my_platform(base_url, auth_headers, timeout=None, **kwargs):
    from adapters.my_platform.client import MyPlatformAdapter
    return MyPlatformAdapter(base_url, auth_headers, timeout, **kwargs)
```

**Étape 3 — Enregistrer l'adapter**

Toujours dans `adapters/__init__.py` :

```python
adapter_registry.register("my_platform", _factory_my_platform, queue="my_platform")
```

**Étape 4 — Configurer la queue Celery** (si nouvelle queue)

Dans le `docker-compose.yml`, ajouter la queue dans la commande du worker Celery :

```yaml
celery-worker:
  command: celery -A idp_backend worker -Q default,aap,azure,github,terraform,my_platform
```

**Étape 5 (recommandé) — Ajouter une PlatformDefinition**

Voir la section [Ajouter une plateforme](#ajouter-une-plateforme-platformdefinition).

### Checklist

- [ ] Classe adapter créée avec les méthodes obligatoires (`trigger`, `get_status`, `get_job_logs`)
- [ ] Factory function ajoutée dans `adapters/__init__.py`
- [ ] Adapter enregistré via `adapter_registry.register(...)`
- [ ] Queue Celery configurée (si nouvelle queue)
- [ ] Tests unitaires pour le client adapter
- [ ] `PlatformDefinition` correspondante (recommandé)

---

## Ajouter un service (nouvelle intégration)

### Prérequis

- Comprendre le double registry (factory + définition)
- Savoir si le service nécessite une intégration configurée (`requires_integration`)

### Procédure

**Étape 1 — Créer le client service**

Créer `services/<service_type>/client.py` :

```python
# services/my_service/client.py
class MyServiceClient:
    def __init__(self, base_url: str, token: str, **kwargs):
        self.base_url = base_url
        self.token = token

    def my_operation(self, param1: str, param2: str) -> dict:
        """Exécute l'opération principale."""
        # Implémenter l'appel API
        return {"result": "..."}
```

**Étape 2 — Créer la factory et les définitions**

Dans `services/__init__.py` :

```python
# 1. Factory
def _factory_my_service(**config):
    from services.my_service.client import MyServiceClient
    return MyServiceClient(**config)

# 2. Définition des opérations
from services.definitions import ServiceDefinition, ServiceOperationDefinition

_my_service_def = ServiceDefinition(
    code="my_service",
    display_name="Mon Service",
    requires_integration=True,
    supports_health_check=True,
    operation_defs=(
        ServiceOperationDefinition(
            code="my_operation",
            label="Exécuter mon opération",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "string"}
                },
                "required": ["param1"]
            },
            output_schema={"type": "object"},
            ui_hints={}
        ),
    ),
)

# 3. Double enregistrement (OBLIGATOIRE)
service_registry.register("my_service", _factory_my_service)
service_definition_registry.register(_my_service_def)
```

> **Important :** Les deux enregistrements sont **obligatoires**. L'assertion guard vérifie la synchronisation au démarrage — si un service manque dans l'un des deux registres, l'application ne démarre pas.

**Étape 3 — Mettre à jour SERVICE_TYPES** (si nécessaire)

`SERVICE_TYPES` est calculé automatiquement depuis `service_definition_registry.list_types()`. Aucune action manuelle requise.

### Checklist

- [ ] Classe client service créée
- [ ] Factory function ajoutée
- [ ] `ServiceDefinition` avec les `ServiceOperationDefinition`
- [ ] Enregistré dans `service_registry` **ET** `service_definition_registry`
- [ ] Assertion guard passe (les deux registres sont synchronisés)
- [ ] Tests unitaires pour le client service

---

## Ajouter un gate (nouveau type de condition)

### Prérequis

- Comprendre les deux modes : auto-évaluation vs résolution manuelle
- Connaître le `GateEvaluationContext` qui sera fourni à la stratégie

### Procédure

**Étape 1 — Créer la stratégie**

Dans `executions/gates/strategies.py` (ou un nouveau fichier) :

```python
# Pour un gate auto-évalué
from executions.gates.definitions import GateEvaluationContext

class MyGateEvaluationStrategy:
    """Évalue automatiquement la condition."""

    def evaluate(self, ctx: GateEvaluationContext) -> tuple[bool, dict]:
        # True = condition satisfaite, le gate laisse passer
        # False = condition non satisfaite, le gate bloque
        is_satisfied = self._check_condition(ctx)
        details = {"checked_at": "...", "reason": "..."}
        return is_satisfied, details

    def _check_condition(self, ctx: GateEvaluationContext) -> bool:
        # Logique métier spécifique
        ...
```

Pour un gate à **résolution manuelle**, implémenter `GateResolutionStrategy` avec la méthode `resolve()`.

**Étape 2 — Enregistrer le gate**

Dans `executions/gates/registry.py` :

```python
from executions.gates.definitions import GateDefinition
from executions.gates.strategies import MyGateEvaluationStrategy

gate_registry.register(GateDefinition(
    gate_type="my_gate",
    condition_type="my_condition_met",
    display_name="Mon Gate",
    category="custom",
    config_schema={},          # JSON Schema de la config si nécessaire
    supports_timeout=True,
    requires_manual_resolution=False,
    evaluation_strategy=MyGateEvaluationStrategy(),
))
```

**Étape 3 — Mettre à jour le contexte** (si nécessaire)

Si le nouveau gate requiert des données supplémentaires dans le `GateEvaluationContext`, mettre à jour la dataclass dans `executions/gates/definitions.py`.

### Checklist

- [ ] Stratégie créée (évaluation ou résolution)
- [ ] `GateDefinition` enregistrée dans `gate_registry`
- [ ] `GateEvaluationContext` mis à jour si nécessaire
- [ ] Tests unitaires pour la stratégie
- [ ] Tests d'intégration avec le `GateHandler`

---

## Ajouter une plateforme (PlatformDefinition)

### Rôle

Une `PlatformDefinition` décrit les **métadonnées** d'une plateforme : ses schémas de configuration, ses alias, sa valeur en BD, ses kwargs de runtime. Elle est distincte de l'adapter (qui gère l'exécution).

### Procédure

Dans `platforms/registry.py` (directement dans le fichier, pas de `__init__` séparé) :

```python
from platforms.definitions import PlatformDefinition

_my_platform = PlatformDefinition(
    code="my_platform",                    # Identifiant canonique
    display_name="My Platform",            # Nom affiché
    aliases=frozenset({"myplat"}),         # Alias optionnels
    icon="my_platform",                    # Icône frontend
    connector_type="my_platform",          # Type de connecteur
    action_platform_code="My Platform",    # Valeur stockée en BD
    supports_health_check=True,
    runtime_kwargs_required=("api_key",),  # Kwargs obligatoires
    runtime_kwargs_optional={},            # Kwargs optionnels + défauts
    action_config_schema={                 # JSON Schema config actions
        "type": "object",
        "properties": {
            "project": {"type": "string"}
        }
    },
    runtime_config_schema={},
    health_check_policy={
        "endpoint": "/api/health",
        "timeout_seconds": 10
    },
)

platform_registry.register(_my_platform)
```

### Champs obligatoires

| Champ | Contrainte |
|-------|-----------|
| `code` | Unique, identifiant canonique |
| `display_name` | Non vide |
| `action_platform_code` | Doit correspondre à la valeur en BD (`INTEGRATION_TYPE_CATALOGUE`) |
| `icon` | Doit correspondre à un fichier icône existant dans le frontend |
| `connector_type` | Utilisé pour le mapping ServiceNow |

---

## Ajouter une intégration (INTEGRATION_TYPE_CATALOGUE)

### Rôle

Les intégrations sont les **enregistrements en base de données** qui définissent les types de connecteurs disponibles. Elles sont liées aux `PlatformDefinition` via `action_platform_code`.

### Procédure

**Étape 1 — Créer la migration SQL Flyway**

Créer `database/migrations/V<n>__add_integration_type_<name>.sql` :

```sql
-- Insérer le type d'intégration
INSERT INTO INTEGRATION_TYPE_CATALOGUE (CODE, DISPLAY_NAME, PLATFORM_TYPE)
VALUES ('MY_PLATFORM', 'My Platform', 'my_platform');

-- Insérer les actions associées
INSERT INTO INTEGRATION_ACTIONS (
    INTEGRATION_TYPE_CODE, ACTION_CODE, DISPLAY_NAME, PARAMETERS_SCHEMA
)
VALUES (
    'MY_PLATFORM',
    'run_job',
    'Exécuter un job',
    '{"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]}'
);
```

**Étape 2 — Vérifier la cohérence**

S'assurer qu'une `PlatformDefinition` correspondante existe dans `platform_registry` avec le même `action_platform_code`.

**Étape 3 — Tester**

Exécuter la migration et vérifier que :
- Le type d'intégration apparaît dans le catalogue
- Les actions sont disponibles
- La résolution `platform_registry.get_by_action_platform_code("MY_PLATFORM")` fonctionne

---

## JSON Schemas

### Où sont-ils utilisés ?

| Emplacement | Table BD | Colonne | Format | Usage |
|-------------|---------|---------|--------|-------|
| Paramètres d'actions | `ACTIONS_CATALOG` | `PARAMETERS_SCHEMA` | JSON Schema draft-07 | Génère les formulaires dynamiques frontend (`useDynamicForm`) |
| Config intégrations | `INTEGRATIONS` | `CONFIG` | Validé par le schéma de la plateforme | Configuration de connexion (URL, tokens) |
| Actions d'intégration | `INTEGRATION_ACTIONS` | (schema) | JSON Schema | Paramètres spécifiques d'une action d'intégration |
| Config actions plateformes | `PlatformDefinition.action_config_schema` | N/A (code) | JSON Schema | Validation côté backend via `jsonschema` |
| Config runtime plateformes | `PlatformDefinition.runtime_config_schema` | N/A (code) | JSON Schema | Validation de la config runtime de l'intégration |
| Opérations services | `ServiceOperationDefinition.input_schema` | N/A (code) | JSON Schema | Paramètres d'entrée des opérations de service |
| Gates | `GateDefinition.config_schema` | N/A (code) | JSON Schema | Configuration des conditions de gate |

### Format

Tous les JSON Schemas utilisent le format **JSON Schema draft-07**. La validation côté backend est effectuée par la bibliothèque Python `jsonschema`.

### Exemple

```json
{
  "type": "object",
  "properties": {
    "job_template_id": {
      "type": "integer",
      "title": "Job Template ID",
      "description": "Identifiant du template de job à exécuter"
    },
    "extra_vars": {
      "type": "object",
      "title": "Variables supplémentaires",
      "default": {}
    }
  },
  "required": ["job_template_id"]
}
```

### Côté frontend

Le hook `useDynamicForm` consomme les `PARAMETERS_SCHEMA` pour générer automatiquement les formulaires. Les propriétés `title`, `description`, `default`, `enum` et `type` sont interprétées pour le rendu. Voir la [documentation frontend](../frontend/architecture-consumption.md) (Story 87-2) pour les détails côté consommation.

---

*Guide créé dans le cadre de la Story 87-4 — Documentation développement et extensibilité.*
