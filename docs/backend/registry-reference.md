# Référence rapide des registries

**Date :** 2026-03-16

Tableau synthétique de tous les registries du backend IDP-Portal. Pour le guide complet avec procédures d'extension, voir [development-extensibility.md](development-extensibility.md).

---

## Registries principaux

| Registry | Module | Singleton | Clé | Module d'enregistrement | Thread-safe |
|----------|--------|-----------|-----|------------------------|-------------|
| `AdapterRegistry` | `adapters/registry.py` | `adapter_registry` | `platform_type` (str) | `adapters/__init__.py` | Non* |
| `PlatformRegistry` | `platforms/registry.py` | `platform_registry` | `code` (str) | `platforms/registry.py` | Non* |
| `ServiceRegistry` | `services/registry.py` | `service_registry` | `service_type` (str) | `services/__init__.py` | Non* |
| `ServiceDefinitionRegistry` | `services/definitions.py` | `service_definition_registry` | `code` (str) | `services/__init__.py` | Non* |
| `GateDefinitionRegistry` | `executions/gates/definitions.py` | `gate_registry` | `gate_type` (str) | `executions/gates/registry.py` | Non* |

## Registries complémentaires

| Registry | Module | Singleton | Clé | Module d'enregistrement | Thread-safe |
|----------|--------|-----------|-----|------------------------|-------------|
| `StepHandlerRegistry` | `executions/app/handlers/registry.py` | `step_handler_registry` | `step_type` (str) | Même fichier | Non* |
| `OutputInterpreterRegistry` | `executions/interpreters/registry.py` | Via `get_instance()` | `step_type` (str) | `executions/interpreters/__init__.py` | **Oui** (Lock) |
| `OutputSchemaRegistry` | `output_schemas/registry.py` | `schema_registry` | Clé composite | ORM Django | **Oui** (Lock + version) |

\* Enregistrement à l'import des modules (mono-thread) — pas de support pour l'enregistrement dynamique multi-thread.

---

## Éléments enregistrés

### Adapters (AdapterRegistry)

| `platform_type` | Queue Celery | Factory |
|-----------------|-------------|---------|
| `aap` | `aap` | `_factory_aap` |
| `tower` | `aap` | `_factory_tower` |
| `azure_devops` | `azure` | `_factory_azure_devops` |
| `github_actions` | `github` | `_factory_github_actions` |
| `terraform_cloud` | `terraform` | `_factory_terraform_cloud` |

### Plateformes (PlatformRegistry)

| Code | `action_platform_code` | Aliases | Health Check |
|------|----------------------|---------|-------------|
| `aap` | `AAP` | — | Oui |
| `tower` | `Tower` | — | Oui |
| `azure_devops` | `Azure DevOps` | `azuredevops` | Oui |
| `github_actions` | `GitHub Actions` | — | Oui |
| `terraform_cloud` | `Terraform` | `terraform` | Oui |

### Services (ServiceRegistry + ServiceDefinitionRegistry)

| `service_type` | `requires_integration` | Health Check | Opérations |
|---------------|----------------------|-------------|-----------|
| `vault` | Oui | Oui | `get_secret` |
| `splunk` | Oui | Oui | — |
| `servicenow` | Oui | Oui | `create_change`, `update_change`, `close_change`, `get_change_status`, `cancel_change` |
| `jira` | Oui | Oui | `create_issue`, `update_issue`, `get_issue` |
| `notification` | Non | Non | `send_email`, `send_teams`, `notify_execution_event` |

### Gates (GateDefinitionRegistry)

| `gate_type` | `condition_type` | Mode | Timeout |
|-------------|-----------------|------|---------|
| `maintenance_window` | `maintenance_window` | Auto-évaluation | Oui |
| `approval` | `approval_granted` | Manuel | Oui |

### Step Handlers (StepHandlerRegistry)

| `step_type` | Handler Class |
|-------------|--------------|
| `service_call` | `ServiceCallHandler` |
| `http_request` | `HttpRequestHandler` |
| `evaluation` | `EvaluationHandler` |
| `gate` | `GateHandler` |

> `'platform'` absent — géré via child executions.

### DI Services (core/di.py)

| Getter | Service | Module source |
|--------|---------|---------------|
| `get_profile_service()` | `ProfileService` | `profiles.services` |
| `get_execution_service()` | `ExecutionService` | `executions.services` |
| `get_catalog_service()` | `CatalogService` | `catalog.services` |
| `get_inventory_service()` | `InventoryService` | `inventory.services` |

---

*Référence créée dans le cadre de la Story 87-4.*
