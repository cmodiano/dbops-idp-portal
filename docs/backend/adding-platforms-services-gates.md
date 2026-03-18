# Guide pratique — Ajouter des plateformes, services et gates

**Date :** 2026-03-18

Ce guide fournit les instructions pas-a-pas pour etendre le systeme IDP-Portal en ajoutant de nouvelles plateformes d'execution, de nouveaux services externes ou de nouveaux gates de validation. Il decrit les JSON Schemas utilises et le systeme de capabilities qui expose automatiquement les extensions au frontend.

---

## Table des matieres

1. [Principes d'architecture](#principes-darchitecture)
2. [Ajouter une plateforme](#ajouter-une-plateforme)
3. [Ajouter un service](#ajouter-un-service)
4. [Ajouter un gate](#ajouter-un-gate)
5. [JSON Schemas — Reference](#json-schemas--reference)
6. [Systeme de capabilities](#systeme-de-capabilities)
7. [Checklist de validation](#checklist-de-validation)

---

## Principes d'architecture

Le backend utilise un **pattern Registry + Factory** qui permet d'ajouter de nouvelles implementations sans modifier le code existant (principe ouvert/ferme).

### Ce qu'il faut retenir

- **Aucun `if/elif`** dans le code de dispatch — tout passe par les registries
- **Enregistrement a l'import** — les definitions sont enregistrees au demarrage de Django, en contexte mono-thread
- **Double registry** pour les services — une factory (implementation) + une definition (metadonnees). Les deux doivent rester synchronises
- **JSON Schema draft-07** — tous les schemas de configuration suivent cette specification
- **Le frontend ne contient aucune logique metier** — il consomme les schemas exposes par l'API `/api/v1/capabilities/` et genere les formulaires dynamiquement

### Vue d'ensemble des registries

| Registry | Module | Cle | Ce qu'il contient |
|----------|--------|-----|-------------------|
| `adapter_registry` | `adapters/__init__.py` | `platform_type` | Factory des clients d'execution |
| `platform_registry` | `platforms/registry.py` | `code` | Metadonnees de plateforme (schemas, alias, config) |
| `service_registry` | `services/__init__.py` | `service_type` | Factory des clients de service |
| `service_definition_registry` | `services/__init__.py` | `code` | Metadonnees de service (operations, schemas) |
| `gate_registry` | `executions/gates/registry.py` | `gate_type` | Definitions des gates (strategies, schemas) |
| `workflow_step_registry` | `capabilities/step_definitions.py` | `code` | Types de steps workflow |

---

## Ajouter une plateforme

Ajouter une plateforme necessite deux enregistrements : un **adapter** (implementation technique) et une **PlatformDefinition** (metadonnees exposees au frontend).

### Etape 1 — Creer le client adapter

Creer le fichier `adapters/<nom_plateforme>/client.py` :

```python
# adapters/my_platform/client.py
from adapters.base_adapter import ITriggerableAdapter

class MyPlatformAdapter(ITriggerableAdapter):
    """Client d'execution pour My Platform."""

    def __init__(self, base_url: str, auth_headers: dict, timeout: float | None = None, **kwargs):
        self.base_url = base_url
        self.auth_headers = auth_headers
        self.timeout = timeout

    async def trigger(self, **kwargs) -> dict:
        """Lance une execution sur la plateforme distante."""
        # Implementer l'appel API
        return {"platform_job_id": "...", "status": "pending", "url": "..."}

    async def get_status(self, platform_job_id: str, **kwargs) -> dict:
        """Recupere le statut d'une execution en cours."""
        return {"status": "running", "progress": 50}

    async def get_job_logs(self, platform_job_id: str, **kwargs) -> dict:
        """Recupere les logs d'execution."""
        return {
            "content": "...",
            "format": "text",
            "timestamp": "...",
            "complete": False,
            "job_status": "running",
        }
```

Si la plateforme supporte l'annulation, heriter de `BaseAdapter` (qui combine `ITriggerableAdapter` + `ICancellableAdapter`) :

```python
from adapters.base_adapter import BaseAdapter

class MyPlatformAdapter(BaseAdapter):
    # ... memes methodes + :
    async def cancel_execution(self, platform_job_id: str, **kwargs) -> None:
        """Annule une execution en cours."""
        ...
```

Si la plateforme supporte le health check, implementer aussi `IHealthCheckable` :

```python
from adapters.base_adapter import BaseAdapter, IHealthCheckable

class MyPlatformAdapter(BaseAdapter, IHealthCheckable):
    # ... memes methodes + :
    async def health_check(self, **kwargs) -> dict:
        """Verifie la connectivite et la sante de la plateforme."""
        return {"status": "healthy", "version": "1.0"}
```

### Etape 2 — Creer la factory et enregistrer l'adapter

Dans `adapters/__init__.py` :

```python
def _factory_my_platform(base_url, auth_headers, timeout=None, **kwargs):
    from adapters.my_platform.client import MyPlatformAdapter
    return MyPlatformAdapter(base_url, auth_headers, timeout, **kwargs)

# Enregistrer avec une queue Celery dediee
adapter_registry.register("my_platform", _factory_my_platform, queue="my_platform")
```

> **Note :** L'import est **lazy** (dans la factory) pour eviter les circular imports.

### Etape 3 — Enregistrer la PlatformDefinition

Dans `platforms/registry.py` :

```python
from platforms.definitions import PlatformDefinition

platform_registry.register(PlatformDefinition(
    code="my_platform",
    display_name="My Platform",
    aliases=frozenset(),                      # Alias optionnels pour retrocompatibilite
    icon="my_platform",                       # Correspond a une icone dans le frontend
    connector_type="my_platform",             # Type de connecteur
    action_platform_code="My Platform",       # Valeur stockee en BD — doit correspondre a INTEGRATION_TYPE_CATALOGUE
    supports_health_check=True,
    runtime_kwargs_required=("api_key",),     # Parametres obligatoires au runtime
    runtime_kwargs_optional={                 # Parametres optionnels avec valeurs par defaut
        "timeout": 30,
    },
    action_config_schema={                    # JSON Schema pour la configuration des actions
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "title": "ID du projet",
                "description": "Identifiant du projet sur la plateforme",
            },
            "job_type": {
                "type": "string",
                "enum": ["build", "deploy", "test"],
                "title": "Type de job",
            },
        },
        "required": ["project_id"],
    },
    runtime_config_schema={                   # JSON Schema de la configuration runtime
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "title": "Cle API",
                "description": "Cle d'authentification pour My Platform",
            },
        },
        "required": ["api_key"],
    },
    health_check_policy={
        "endpoint": "/api/v2/health",
        "timeout_seconds": 10,
    },
))
```

### Etape 4 — Configurer la queue Celery (si nouvelle queue)

Dans `docker-compose.yml`, ajouter la queue au worker Celery :

```yaml
celery-worker:
  command: celery -A idp_backend worker -Q default,aap,azure,github,terraform,my_platform
```

### Etape 5 — Creer la migration SQL

Si la plateforme necessite un enregistrement en base (table `INTEGRATION_TYPE_CATALOGUE`), creer une migration Flyway dans `database/migrations/` :

```sql
-- V<n>__add_integration_type_my_platform.sql
INSERT INTO INTEGRATION_TYPE_CATALOGUE (CODE, DISPLAY_NAME, PLATFORM_TYPE)
VALUES ('MY_PLATFORM', 'My Platform', 'my_platform');
```

### Champs de PlatformDefinition — Reference

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `code` | `str` | Oui | Identifiant canonique unique (ex: `'aap'`, `'github_actions'`) |
| `display_name` | `str` | Oui | Nom affiche dans l'UI |
| `aliases` | `frozenset[str]` | Non | Alias pour retrocompatibilite (ex: `{'azuredevops'}` → resolu vers `'azure_devops'`) |
| `icon` | `str` | Oui | Identifiant de l'icone frontend |
| `connector_type` | `str` | Oui | Type de connecteur (mapping ServiceNow) |
| `action_platform_code` | `str` | Oui | Valeur stockee en BD — doit correspondre a `INTEGRATION_TYPE_CATALOGUE` |
| `supports_health_check` | `bool` | Oui | Active le health check sur les integrations de cette plateforme |
| `runtime_kwargs_required` | `tuple[str, ...]` | Non | Kwargs obligatoires au runtime (ex: `("owner", "repo")` pour GitHub) |
| `runtime_kwargs_optional` | `dict[str, object]` | Non | Kwargs optionnels avec valeurs par defaut |
| `action_config_schema` | `dict` | Non | JSON Schema draft-07 pour la configuration des actions |
| `runtime_config_schema` | `dict` | Non | JSON Schema de la configuration runtime |
| `health_check_policy` | `dict` | Non | Politique de health check (endpoint, timeout) |

### Plateformes existantes

| Code | Display Name | Aliases | Kwargs requis |
|------|-------------|---------|---------------|
| `aap` | Ansible Automation Platform | — | — |
| `tower` | Ansible Tower | — | — |
| `azure_devops` | Azure DevOps | `azuredevops` | — |
| `github_actions` | GitHub Actions | — | `owner`, `repo` |
| `terraform_cloud` | Terraform Cloud | `terraform` | `organization` |

---

## Ajouter un service

Un service represente un systeme externe consomme pendant l'execution d'un workflow (ex: Vault, ServiceNow, Jira). L'ajout necessite un **double enregistrement** obligatoire : factory + definition.

### Etape 1 — Creer le client service

Creer `services/<nom_service>/client.py` :

```python
# services/my_service/client.py

class MyServiceClient:
    """Client pour interagir avec My Service."""

    def __init__(self, base_url: str, token: str, **kwargs):
        self.base_url = base_url
        self.token = token

    def create_item(self, name: str, description: str = "") -> dict:
        """Cree un element dans My Service."""
        # Implementer l'appel API
        return {"id": "...", "name": name, "status": "created"}

    def get_item(self, item_id: str) -> dict:
        """Recupere un element par son identifiant."""
        return {"id": item_id, "name": "...", "status": "active"}
```

### Etape 2 — Enregistrer la factory et la definition

Dans `services/__init__.py` :

```python
from services.definitions import ServiceDefinition, ServiceOperationDefinition

# 1. Factory (import lazy)
def _factory_my_service(**config):
    from services.my_service.client import MyServiceClient
    return MyServiceClient(**config)

# 2. Definition avec les operations
_my_service_def = ServiceDefinition(
    code="my_service",
    display_name="My Service",
    requires_integration=True,           # True = necessite un enregistrement Integration en BD
    supports_health_check=True,
    operation_defs=(
        ServiceOperationDefinition(
            code="create_item",
            label="Creer un element",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "title": "Nom",
                        "description": "Nom de l'element a creer",
                        "minLength": 1,
                    },
                    "description": {
                        "type": "string",
                        "title": "Description",
                        "description": "Description optionnelle",
                        "default": "",
                    },
                },
                "required": ["name"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": ["created", "error"]},
                },
            },
            ui_hints={},
        ),
        ServiceOperationDefinition(
            code="get_item",
            label="Recuperer un element",
            input_schema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "title": "Identifiant",
                        "description": "ID de l'element",
                    },
                },
                "required": ["item_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
            ui_hints={},
        ),
    ),
)

# 3. DOUBLE ENREGISTREMENT — les deux sont OBLIGATOIRES
service_registry.register("my_service", _factory_my_service)
service_definition_registry.register(_my_service_def)
```

> **Important :** Si un service est present dans un seul des deux registries, l'application **ne demarre pas**. L'assertion guard dans `services/__init__.py` verifie la synchronisation au demarrage.

### Champs de ServiceDefinition — Reference

| Champ | Type | Description |
|-------|------|-------------|
| `code` | `str` | Identifiant unique du service (ex: `'vault'`, `'servicenow'`) |
| `display_name` | `str` | Nom affiche dans l'UI |
| `requires_integration` | `bool` | `True` = necessite un enregistrement Integration en BD avec credentials |
| `operation_defs` | `tuple[ServiceOperationDefinition, ...]` | Operations supportees par le service |
| `supports_health_check` | `bool` | Active le health check pour les integrations de ce service |

### Champs de ServiceOperationDefinition — Reference

| Champ | Type | Description |
|-------|------|-------------|
| `code` | `str` | Code de l'operation (ex: `'create_change'`, `'get_secret'`) |
| `label` | `str` | Libelle affiche dans l'UI |
| `input_schema` | `dict` | JSON Schema draft-07 des parametres d'entree |
| `output_schema` | `dict` | JSON Schema de la reponse |
| `ui_hints` | `dict` | Indices de rendu pour le frontend (ex: champs caches, widgets speciaux) |

### Services existants

| Code | Display Name | Necessite integration | Operations |
|------|-------------|----------------------|------------|
| `vault` | HashiCorp Vault | Oui | `get_secret` |
| `splunk` | Splunk | Oui | — (health check uniquement) |
| `servicenow` | ServiceNow | Oui | `create_change`, `update_change`, `close_change`, `get_change_status`, `cancel_change` |
| `jira` | Jira | Oui | `create_issue`, `update_issue`, `get_issue` |
| `notification` | Notification | Non | `send_email`, `send_teams`, `notify_execution_event` |

---

## Ajouter un gate

Un gate est une condition de validation entre les etapes d'un workflow. Il bloque l'execution jusqu'a ce que la condition soit satisfaite. Deux modes existent :

- **Auto-evaluation** — le systeme verifie periodiquement la condition (ex: fenetre de maintenance ouverte)
- **Resolution manuelle** — un utilisateur approuve via l'API REST `/approve/`

### Etape 1 — Creer la strategie

Dans `executions/gates/strategies.py` (ou un nouveau fichier) :

```python
# Gate auto-evalue
from executions.gates.definitions import GateEvaluationContext

class MyGateEvaluationStrategy:
    """Evalue automatiquement la condition personnalisee."""

    def evaluate(self, ctx: GateEvaluationContext) -> tuple[bool, dict]:
        """
        Retourne:
            - (True, details) si la condition est satisfaite → le gate laisse passer
            - (False, details) si la condition n'est pas satisfaite → le gate bloque
        """
        is_satisfied = self._check_condition(ctx)
        return is_satisfied, {
            "checked_at": "...",
            "reason": "Condition satisfaite" if is_satisfied else "En attente",
        }

    def _check_condition(self, ctx: GateEvaluationContext) -> bool:
        # Logique metier specifique
        config = ctx.gate_config  # Configuration du gate (definie par config_schema)
        targets = ctx.targets     # Cibles de l'execution
        return True
```

Pour un gate a **resolution manuelle** :

```python
from executions.gates.definitions import GateEvaluationContext

class MyGateResolutionStrategy:
    """Valide une approbation soumise par un utilisateur."""

    def resolve(self, ctx: GateEvaluationContext) -> tuple[bool, dict]:
        """Appelee quand un utilisateur approuve via POST /approve/."""
        return True, {"approved_by": ctx.user_id, "approved_at": "..."}
```

### Etape 2 — Enregistrer le gate

Dans `executions/gates/registry.py` :

```python
from executions.gates.definitions import GateDefinition
from executions.gates.strategies import MyGateEvaluationStrategy

gate_registry.register(GateDefinition(
    gate_type="my_gate",                    # Identifiant du gate
    condition_type="my_condition_met",      # Type de condition (utilise comme cle interne)
    display_name="Mon gate personnalise",   # Nom affiche dans l'UI
    category="custom",                      # Categorie semantique
    config_schema={                         # JSON Schema de la configuration
        "type": "object",
        "properties": {
            "threshold": {
                "type": "integer",
                "title": "Seuil",
                "description": "Seuil minimal pour valider la condition",
                "minimum": 0,
                "default": 80,
            },
        },
    },
    supports_timeout=True,                  # Permet de configurer un timeout_hours
    requires_manual_resolution=False,       # False = auto-evalue, True = approbation manuelle
    evaluation_strategy=MyGateEvaluationStrategy(),  # Instance de la strategie
    resolution_strategy=None,               # None pour auto-evaluation
))
```

### Exposition automatique dans l'API capabilities

Les gates enregistres sont **automatiquement** exposes comme variants du step type `gate` via le `variants_builder`. Aucune modification supplementaire n'est necessaire — le frontend les decouvre via `GET /api/v1/capabilities/workflow-steps/`.

### Champs de GateDefinition — Reference

| Champ | Type | Description |
|-------|------|-------------|
| `gate_type` | `str` | Identifiant du gate (ce que l'utilisateur configure) |
| `condition_type` | `str` | Identifiant de la condition au runtime |
| `display_name` | `str` | Nom affiche dans l'UI |
| `category` | `str` | Categorie semantique (maintenance, approval, custom...) |
| `config_schema` | `dict` | JSON Schema draft-07 de la configuration du gate |
| `supports_timeout` | `bool` | `True` = le champ `timeout_hours` est configurable |
| `requires_manual_resolution` | `bool` | `True` = resolution via endpoint `/approve/`, `False` = auto-evaluation periodique |
| `evaluation_strategy` | `GateEvaluationStrategy \| None` | Strategie d'auto-evaluation (obligatoire si `requires_manual_resolution=False`) |
| `resolution_strategy` | `GateResolutionStrategy \| None` | Strategie de resolution manuelle (obligatoire si `requires_manual_resolution=True`) |

### Gates existants

| `gate_type` | `condition_type` | Mode | Strategie |
|-------------|-----------------|------|-----------|
| `maintenance_window` | `maintenance_window` | Auto-evaluation | `MaintenanceWindowEvaluationStrategy` |
| `approval` | `approval_granted` | Manuel | Resolution via `/approve/` |

---

## JSON Schemas — Reference

Tous les JSON Schemas utilisent la specification **JSON Schema draft-07** et sont valides par la bibliotheque Python `jsonschema`.

### Ou les schemas sont-ils utilises ?

| Emplacement | Qui le definit | Format | Utilise par |
|-------------|---------------|--------|-------------|
| `PlatformDefinition.action_config_schema` | Code Python | JSON Schema | Frontend (formulaires action) + Backend (validation) |
| `PlatformDefinition.runtime_config_schema` | Code Python | JSON Schema | Frontend (formulaires integration) |
| `ServiceOperationDefinition.input_schema` | Code Python | JSON Schema | Frontend (formulaires operation) + Backend (validation) |
| `ServiceOperationDefinition.output_schema` | Code Python | JSON Schema | Documentation + validation reponse |
| `GateDefinition.config_schema` | Code Python | JSON Schema | Frontend (configuration gate dans workflow builder) |
| `ACTIONS_CATALOG.PARAMETERS_SCHEMA` | Base de donnees | JSON Schema | Frontend (`useDynamicForm`) + Backend (validation execution) |
| `INTEGRATION_ACTIONS.PARAMETERS_SCHEMA` | Base de donnees | JSON Schema | Frontend + Backend |

### Structure d'un JSON Schema

```json
{
  "type": "object",
  "properties": {
    "nom_du_champ": {
      "type": "string",
      "title": "Libelle affiche dans le formulaire",
      "description": "Texte d'aide contextuelle",
      "default": "valeur_par_defaut",
      "enum": ["option1", "option2"],
      "minLength": 1,
      "maxLength": 255,
      "pattern": "^[a-z]+$"
    },
    "champ_numerique": {
      "type": "integer",
      "title": "Nombre maximum",
      "minimum": 1,
      "maximum": 1000,
      "default": 100
    },
    "champ_booleen": {
      "type": "boolean",
      "title": "Activer le mode debug",
      "default": false
    },
    "champ_date": {
      "type": "string",
      "format": "date",
      "title": "Date planifiee"
    }
  },
  "required": ["nom_du_champ"]
}
```

### Types supportes

| Type JSON Schema | Composant frontend | Notes |
|-----------------|-------------------|-------|
| `"string"` | `<Input>` | Champ texte libre |
| `"string"` + `"enum"` | `<Select>` | Dropdown avec options fixes |
| `"string"` + `"format": "date"` | `<DatePicker>` | Selecteur de date |
| `"string"` + `"format": "date-time"` | `<DatePicker showTime>` | Selecteur date + heure |
| `"integer"` | `<InputNumber step={1}>` | Nombre entier |
| `"number"` | `<InputNumber>` | Nombre decimal |
| `"boolean"` | `<Switch>` | Interrupteur vrai/faux |
| `"array"` | `<Select mode="tags">` | Saisie multiple |

### Extensions IDP (hors standard JSON Schema)

Le systeme definit des extensions proprietaires pour les champs d'inventaire :

```json
{
  "target_db": {
    "type": "string",
    "source": "inventory",
    "inventory_type": "databases",
    "inventory_value_column": "db_name",
    "description": "Base de donnees cible"
  }
}
```

| Extension | Valeurs | Description |
|-----------|---------|-------------|
| `source` | `"inventory"` | Marque le champ comme dropdown alimente par l'inventaire |
| `inventory_type` | `"databases"` \| `"servers"` \| `"instances"` | Type de ressource dans l'inventaire |
| `inventory_value_column` | ex: `"db_name"` | Colonne utilisee comme valeur dans le dropdown |

### Proprietes utilisees pour le rendu UI

| Propriete | Effet frontend |
|-----------|---------------|
| `title` | Libelle du champ dans le formulaire |
| `description` | Texte d'aide sous le champ |
| `default` | Valeur pre-remplie |
| `enum` | Options du dropdown |
| `minimum` / `maximum` | Bornes pour `InputNumber` |
| `minLength` / `maxLength` | Contraintes de longueur pour `Input` |
| `pattern` | Regex de validation |
| `ui_widget` | Widget de rendu specifique (ex: `"environment_condition"`) |

---

## Systeme de capabilities

Le systeme de capabilities est le mecanisme central qui expose les metadonnees des registries au frontend via l'API REST.

### Endpoints

#### `GET /api/v1/capabilities/integrations/`

Retourne les plateformes et services derives des registries backend :

```json
{
  "data": {
    "platforms": [
      {
        "code": "aap",
        "display_name": "Ansible Automation Platform",
        "aliases": [],
        "icon": "aap",
        "connector_type": "aap",
        "action_platform_code": "AAP",
        "supports_health_check": true,
        "action_config_schema": { "type": "object", "properties": { ... } },
        "runtime_config_schema": { ... },
        "health_check_policy": { ... }
      }
    ],
    "services": [
      {
        "code": "servicenow",
        "display_name": "ServiceNow",
        "credential_mode": "integration",
        "operations": [
          {
            "code": "create_change",
            "label": "Creer un change",
            "input_schema": { ... },
            "output_schema": { ... },
            "ui_hints": {}
          }
        ],
        "supports_health_check": true,
        "supports_service_call": true
      }
    ]
  }
}
```

#### `GET /api/v1/capabilities/workflow-steps/`

Retourne les types de steps workflow avec leurs variants :

```json
{
  "data": {
    "step_types": [
      {
        "code": "platform",
        "label": "Executer",
        "category": "execution",
        "config_schema": {},
        "constraints": { "requires_integration": true, "required_fields": [...] }
      },
      {
        "code": "gate",
        "label": "Attendre",
        "category": "control",
        "config_schema": {},
        "constraints": { ... },
        "variants": [
          {
            "code": "maintenance_window",
            "label": "Fenetre de maintenance",
            "config_schema": { ... }
          },
          {
            "code": "approval",
            "label": "Approbation",
            "config_schema": { ... }
          }
        ]
      }
    ],
    "common_schema": {
      "properties": {
        "condition": {
          "type": "object",
          "title": "Condition d'environnement",
          "ui_widget": "environment_condition"
        }
      }
    }
  }
}
```

### Flux d'exposition

```
Enregistrement (import-time)              API capabilities              Frontend
┌─────────────────────────┐       ┌──────────────────────┐       ┌────────────────────┐
│ platform_registry       │──────►│ GET /capabilities/   │──────►│ capabilities_      │
│ service_def_registry    │       │   integrations/      │       │   service.ts       │
│ gate_registry           │──────►│ GET /capabilities/   │──────►│ useDynamicForm     │
│ workflow_step_registry  │       │   workflow-steps/    │       │ renderFieldInput   │
└─────────────────────────┘       └──────────────────────┘       └────────────────────┘
```

Quand vous ajoutez un nouveau gate, service ou plateforme via les registries, il est **automatiquement** expose dans l'API capabilities. Le frontend le decouvre et genere les formulaires sans aucune modification du code frontend.

---

## Checklist de validation

### Nouvelle plateforme

- [ ] Client adapter cree dans `adapters/<nom>/client.py` avec `trigger()`, `get_status()`, `get_job_logs()`
- [ ] Factory ajoutee dans `adapters/__init__.py` (import lazy)
- [ ] Adapter enregistre via `adapter_registry.register(...)`
- [ ] `PlatformDefinition` enregistree dans `platforms/registry.py`
- [ ] `action_config_schema` et `runtime_config_schema` definis (JSON Schema draft-07)
- [ ] Queue Celery configuree si nouvelle queue
- [ ] Migration SQL Flyway pour `INTEGRATION_TYPE_CATALOGUE` (si necessaire)
- [ ] Tests unitaires pour le client adapter
- [ ] Verification : `GET /api/v1/capabilities/integrations/` retourne la nouvelle plateforme

### Nouveau service

- [ ] Client service cree dans `services/<nom>/client.py`
- [ ] Factory ajoutee dans `services/__init__.py` (import lazy)
- [ ] `ServiceDefinition` avec les `ServiceOperationDefinition` definie
- [ ] `input_schema` et `output_schema` definis pour chaque operation (JSON Schema draft-07)
- [ ] **Double enregistrement** : `service_registry.register(...)` ET `service_definition_registry.register(...)`
- [ ] Verification : l'assertion guard passe au demarrage (les deux registries sont synchronises)
- [ ] Tests unitaires pour le client service
- [ ] Verification : `GET /api/v1/capabilities/integrations/` retourne le nouveau service avec ses operations

### Nouveau gate

- [ ] Strategie creee (evaluation ou resolution) dans `executions/gates/strategies.py`
- [ ] `GateDefinition` enregistree dans `executions/gates/registry.py`
- [ ] `config_schema` defini (JSON Schema draft-07)
- [ ] Tests unitaires pour la strategie
- [ ] Verification : `GET /api/v1/capabilities/workflow-steps/` retourne le nouveau gate comme variant du step `gate`

---

## Voir aussi

- [Architecture d'extension](development-extensibility.md) — Reference technique complete des registries
- [Architecture frontend schema-driven](../frontend/schema-driven-architecture.md) — Comment le frontend consomme les schemas
- [Guide JSON Schemas](../frontend/json-schemas-guide.md) — Flux `parameters_schema` → formulaire dynamique
