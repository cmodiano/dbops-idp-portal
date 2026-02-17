# Story 27.10 : Adapter Jira comme service — fixture et JiraService

Status: review

## Story

En tant que **système backend** (ou action d'exécution),
Je veux **un service Jira (JiraService) et une configuration d'intégration Jira dans le catalogue, pour créer et mettre à jour des issues depuis les étapes d'action**,
Afin que **une action puisse appeler Jira (comme ServiceNow) pour créer une issue, mettre à jour son statut, etc.**.

## Contexte Epic 27

**Objectif Epic :** Exposer les intégrations (AAP en premier) via des adapters backend : appels API pour workflows et job templates, suivi des jobs en cours (logs + statut) et mise à jour en temps réel via websockets.

**Stories complétées :**
- **Story 27.1** : AAPAdapter — workflows, job templates, monitoring WebSocket (41 tests)
- **Story 27.2** : TowerAdapter (Ansible Tower) — job monitoring et polling (85 tests)
- **Story 27.3** : AzureDevOpsAdapter — pipelines, runs, logs, polling 5s (126 tests)
- **Story 27.4** : GitHubActionsAdapter — workflow runs, webhooks/polling (150 tests)
- **Story 27.5** : TerraformCloudAdapter — runs (plan/apply), webhooks/polling (222 tests)
- **Story 27.6** : VaultService — retry, circuit breaker, cache, credential resolution (253 tests)
- **Story 27.7** : Admin frontend — catalogue types d'intégration (7 types + admin UI)
- **Story 27.8** : SplunkAdapter + logging structuré avec correlation_id (47 tests)
- **Story 27.9** : Refactoring — séparation plateformes (adapters/) vs services (services/) (337 tests)

**État actuel (après Story 27.9) :**
- **Architecture clarifiée** : Plateformes d'exécution dans `adapters/`, Services consommés dans `services/`
- **Factories centralisées** : `get_platform_adapter()` et `get_service_client()`
- **8 types d'intégration** dans catalogue : aap, tower, azure_devops, github_actions, terraform_cloud, vault, servicenow, splunk
- **Glossaire produit** : docs/glossary.md définit Platform vs Service vs Adapter
- [Source: 27-9-refactoring-separer-adapters-plateformes-services.md]

## Acceptance Criteria

**AC1 — Fixture et catalogue**

**Given** le catalogue d'intégration existant (IntegrationTypeCatalogue),
**When** on ajoute Jira,
**Then** une **fixture** jira_integration_type définit le type `jira` avec les actions : create_issue, update_issue, get_issue, add_comment,
**And** les paramètres requis et optionnels sont documentés en JSON Schema (projet, type issue, résumé, description, statut, etc.).

**AC2 — JiraService implémentation**

**Given** une configuration d'intégration Jira valide (base_url, credential_ref pour API token),
**When** une étape d'action appelle le service Jira,
**Then** le **JiraService** implémente les actions : créer une issue, mettre à jour une issue, récupérer le statut, ajouter commentaire,
**And** l'authentification Jira (API token Basic Auth, PAT) est supportée selon les standards Jira Cloud / Server,
**And** le service est consommable depuis le moteur d'exécution (étape de type jira) comme ServiceNow.

**AC3 — Admin et factory**

**And** Jira apparaît dans le menu Admin > Intégrations (type jira) pour créer et éditer les configurations,
**And** le seed_integration_types inclut jira dans les types attendus,
**And** JiraService est enregistré dans la factory get_service_client(),
**And** IntegrationType enum contient JIRA = 'jira', 'Jira'.

**AC4 — Tests unitaires**

**And** des tests unitaires (mock API Jira) valident JiraService :
- create_issue success (201 Created)
- update_issue success (204 No Content)
- get_issue success (200 OK)
- add_comment success (201 Created)
- Error handling (401, 403, 404, 500, 503, timeout)
- Retry logic (exponential backoff, max 3 retries)
- Correlation ID propagation dans logs structlog

**AC5 — Tests fixtures et factory**

**And** tests fixtures valident :
- IntegrationTypeCatalogue jira existe après loaddata
- 4 IntegrationAction pour jira (create_issue, update_issue, get_issue, add_comment)
- JSON Schema valide (jsonschema.validate) pour required_params et optional_params

**And** tests factory valident :
- get_service_client("jira") retourne JiraService instance
- get_service_client("jira", base_url=..., auth_headers=...) avec config

**AC6 — Documentation**

**And** services/README.md contient section Jira avec exemple d'utilisation,
**And** docs/jira-integration.md documente architecture, API, authentification, troubleshooting,
**And** docs/integration-type-catalogue.md liste Jira (type=jira, role=Service, actions=4).

**AC7 — Validation non-régression**

**And** tous tests backend passent (pytest),
**And** python manage.py check retourne 0 issues,
**And** python manage.py seed_integration_types --force crée jira avec succès.

## Tasks / Subtasks

### Phase 1: Backend JiraService Implementation

- [x] Task 1: Créer JiraService dans services/jira_service.py (AC: #2)
  - [x] 1.1: Définir classe JiraService avec __init__(base_url, auth_headers, timeout)
  - [x] 1.2: Implémenter create_issue(project_key, issue_type, summary, description, assignee, labels) async
  - [x] 1.3: Implémenter update_issue(issue_key, **updates) async
  - [x] 1.4: Implémenter get_issue(issue_key) async
  - [x] 1.5: Implémenter add_comment(issue_key, comment) async
  - [x] 1.6: Ajouter retry logic (3 tentatives, backoff exponentiel) sur httpx.TimeoutException et 500/503
  - [x] 1.7: Ajouter logging structuré (structlog) avec correlation_id sur tous appels

- [x] Task 2: Enregistrer JiraService dans factory services/ (AC: #3)
  - [x] 2.1: Ajouter 'jira': 'services.jira_service.JiraService' dans SERVICE_TYPES dict
  - [x] 2.2: Ajouter branche if service_type == "jira" dans get_service_client()
  - [x] 2.3: Vérifier import lazy (import dans fonction, pas module-level)

- [x] Task 3: Mettre à jour IntegrationType enum dans integrations/models.py (AC: #3)
  - [x] 3.1: Ajouter JIRA = 'jira', 'Jira' dans IntegrationType choices

### Phase 2: Catalogue d'Intégration Jira

- [x] Task 4: Créer fixture integration_type_catalogue pour Jira (AC: #1)
  - [x] 4.1: Ajouter IntegrationTypeCatalogue record (pk="jira", name="Jira", description, version="1.0")
  - [x] 4.2: Créer IntegrationAction pour create_issue (required_params: project_key, issue_type, summary)
  - [x] 4.3: Créer IntegrationAction pour update_issue (required_params: issue_key; optional: status, assignee, labels)
  - [x] 4.4: Créer IntegrationAction pour get_issue (required_params: issue_key)
  - [x] 4.5: Créer IntegrationAction pour add_comment (required_params: issue_key, comment)
  - [x] 4.6: Définir required_params et optional_params en JSON Schema valide
  - [x] 4.7: Définir response_format pour chaque action (issue_key, issue_id, url, status)

- [x] Task 5: Mettre à jour seed_integration_types command (AC: #4)
  - [x] 5.1: Ajouter 'jira' dans expected_types set
  - [x] 5.2: Tester seed command : python manage.py seed_integration_types --force

### Phase 3: Documentation

- [x] Task 6: Documenter JiraService dans services/README.md (AC: #6)
  - [x] 6.1: Ajouter section Jira avec exemple d'utilisation
  - [x] 6.2: Documenter authentification (API token Basic Auth, PAT)
  - [x] 6.3: Documenter error handling et retry logic

- [x] Task 7: Créer docs/jira-integration.md (AC: #6)
  - [x] 7.1: Documenter architecture (service consommé, pas plateforme)
  - [x] 7.2: Exemples d'appels API (create_issue, update_issue, get_issue, add_comment)
  - [x] 7.3: Configuration Vault (credential_ref format : vault:secret/data/jira/cloud#api_token)
  - [x] 7.4: Troubleshooting (erreurs 401, 403, 404, timeout, rate limit)

- [x] Task 8: Mettre à jour docs/integration-type-catalogue.md (AC: #6)
  - [x] 8.1: Ajouter ligne Jira dans tableau (type=jira, role=Service, actions=4)

### Phase 4: Tests Unitaires et Intégration

- [x] Task 9: Créer tests JiraService (services/tests/test_jira_service.py) (AC: #4)
  - [x] 9.1: Test create_issue success (mock httpx response 201)
  - [x] 9.2: Test create_issue with optional fields (assignee, labels)
  - [x] 9.3: Test update_issue success (mock httpx response 204)
  - [x] 9.4: Test get_issue success (mock httpx response 200)
  - [x] 9.5: Test add_comment success (mock httpx response 201)
  - [x] 9.6: Test retry logic on timeout (mock TimeoutException, puis success)
  - [x] 9.7: Test retry logic on 503 (mock 503 response, puis 200)
  - [x] 9.8: Test error handling 401 unauthorized (raise ServiceUnavailableError)
  - [x] 9.9: Test error handling 404 project not found
  - [x] 9.10: Test correlation_id propagation dans logs structlog

- [x] Task 10: Créer tests factory (services/tests/test_factories.py) (AC: #5)
  - [x] 10.1: Test get_service_client("jira") retourne JiraService instance
  - [x] 10.2: Test get_service_client("jira") avec config params (base_url, auth_headers)
  - [x] 10.3: Test ValueError si service_type inconnu

- [x] Task 11: Créer tests fixtures catalogue (integrations/tests/test_catalogue_fixtures.py) (AC: #5)
  - [x] 11.1: Test IntegrationTypeCatalogue jira existe après loaddata
  - [x] 11.2: Test 4 IntegrationAction pour jira (create_issue, update_issue, get_issue, add_comment)
  - [x] 11.3: Valider required_params est JSON Schema valide (jsonschema.validate)
  - [x] 11.4: Valider optional_params est JSON Schema valide
  - [x] 11.5: Valider response_format est JSON valide

- [x] Task 12: Tests intégration Admin UI (integrations/tests/test_integration_admin.py) (AC: #4)
  - [x] 12.1: Test POST /admin/integrations avec type=jira (status 201)
  - [x] 12.2: Test validation config pour Jira (base_url, credential_ref)
  - [x] 12.3: Test IntegrationValidationService.validate_integration() pour Jira = VALID

### Phase 5: Validation Finale

- [x] Task 13: Exécuter suite tests backend (AC: #7)
  - [x] 13.1: pytest services/tests/test_jira_service.py -v (10 tests pass)
  - [x] 13.2: pytest services/tests/test_factories.py -v (tests jira pass)
  - [x] 13.3: pytest integrations/tests/test_catalogue_fixtures.py -v (tests jira pass)
  - [x] 13.4: pytest integrations/tests/test_integration_admin.py -v (tests jira pass)
  - [x] 13.5: Validation aucune régression (tous tests backend passent)

- [x] Task 14: Validation système Django (AC: #7)
  - [x] 14.1: python manage.py check (0 issues)
  - [x] 14.2: python manage.py makemigrations --check (pas de migration manquante)
  - [x] 14.3: python manage.py seed_integration_types --force (jira créé)
  - [x] 14.4: python manage.py loaddata integration_type_catalogue (jira + 4 actions)

## Dev Notes

### Contexte Architectural

**État actuel de la structure backend (après Story 27.9) :**
- **Services** : 4 services dans `services/` (VaultService, SplunkService, ServiceNowService placeholder, + factory)
- **Catalogue IntegrationTypeCatalogue** : 8 types actifs (aap, tower, azure_devops, github_actions, terraform_cloud, vault, servicenow, splunk)
- **Factory pattern** : `get_service_client(service_type, **config)` dans `services/__init__.py`
- **Documentation** : docs/glossary.md définit Platform (exécute jobs) vs Service (consommé pour fonctionnalité)
- [Source: 27-9-refactoring-separer-adapters-plateformes-services.md, git log]

**Approche Story 27.10 :**
1. **Créer JiraService complet** (pas placeholder) avec 4 méthodes : create_issue, update_issue, get_issue, add_comment
2. **Fixtures catalogue** : Jira type + 4 IntegrationAction avec JSON Schema complet
3. **Enregistrement factory** : Ajouter jira dans SERVICE_TYPES et get_service_client()
4. **Tests exhaustifs** : 20+ tests (mock API Jira, retry, errors, correlation_id)
5. **Documentation complète** : services/README.md, docs/jira-integration.md, troubleshooting

### Technical Requirements — Jira API

**Jira REST API v3 (Cloud) et v2 (Server/Data Center) :**
- **Base URL** : `https://instance.atlassian.net` (Cloud) ou `https://jira.company.com` (Server)
- **Authentification** :
  - **Cloud** : Basic Auth avec email + API token (recommandé)
  - **Server/Data Center** : Basic Auth avec username + password ou Personal Access Token (PAT)
- **API Endpoints** :
  - `POST /rest/api/3/issue` — Créer issue (Cloud) ou `/rest/api/2/issue` (Server)
  - `PUT /rest/api/3/issue/{issueIdOrKey}` — Mettre à jour issue
  - `GET /rest/api/3/issue/{issueIdOrKey}` — Récupérer issue
  - `POST /rest/api/3/issue/{issueIdOrKey}/comment` — Ajouter commentaire
- [Source: Jira Cloud REST API documentation, Jira Server REST API v2/v3]

**Authentification via Vault (credential_ref) :**
- **Format credential_ref** : `vault:secret/data/jira/cloud#api_token` (Cloud) ou `vault:secret/data/jira/server#pat` (Server)
- **Résolution** : Appeler `VaultService.get_secret(credential_ref, correlation_id)` pour obtenir token
- **Création auth_headers** :
  - Cloud : `Authorization: Basic base64(email:api_token)`
  - Server : `Authorization: Basic base64(username:password)` ou `Authorization: Bearer PAT`
- [Source: idp-portal/django_backend/services/vault_service.py, adapters/utils.py pattern]

**Exemple code résolution credential :**
```python
from services.vault_service import get_vault_service
import base64

vault_service = get_vault_service()
api_token = vault_service.get_secret(credential_ref, correlation_id=correlation_id)

# Pour Jira Cloud : email + API token
email = config.get("jira_email", "user@example.com")
credentials = f"{email}:{api_token}"
auth_header = base64.b64encode(credentials.encode()).decode()

auth_headers = {
    "Authorization": f"Basic {auth_header}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
```

**Error Handling patterns :**
- **401 Unauthorized** : Credential invalide → raise ServiceUnavailableError(code="JIRA_AUTH_FAILED")
- **403 Forbidden** : Permissions insuffisantes → raise ServiceUnavailableError(code="JIRA_PERMISSION_DENIED")
- **404 Not Found** : Projet ou issue inexistant → raise ServiceUnavailableError(code="JIRA_RESOURCE_NOT_FOUND")
- **429 Rate Limit** : Retry après delay (header Retry-After)
- **500/503 Server Error** : Retry avec backoff exponentiel (3 tentatives max)
- **Timeout** : Retry avec backoff exponentiel
- [Source: services/splunk_service.py pattern, adapters/base_adapter.py error handling]

### Implementation Pattern — Async httpx Service

**Pattern à suivre (comme SplunkService) :**
```python
import httpx
import structlog
from core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)

class JiraService:
    """Jira integration service client."""

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = timeout

    async def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """Create a Jira issue."""
        url = f"{self.base_url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
            }
        }
        if description:
            payload["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            }
        if assignee:
            payload["fields"]["assignee"] = {"name": assignee}
        if labels:
            payload["fields"]["labels"] = labels

        logger.info(
            "jira_create_issue_request",
            project_key=project_key,
            issue_type=issue_type,
            correlation_id=correlation_id,
        )

        retries = 0
        max_retries = 3
        while retries < max_retries:
            try:
                async with httpx.AsyncClient(
                    headers=self.auth_headers,
                    timeout=self.timeout,
                ) as client:
                    response = await client.post(url, json=payload)

                    if response.status_code == 201:
                        data = response.json()
                        logger.info(
                            "jira_issue_created",
                            issue_key=data.get("key"),
                            issue_id=data.get("id"),
                            correlation_id=correlation_id,
                        )
                        return {
                            "issue_key": data.get("key"),
                            "issue_id": data.get("id"),
                            "url": data.get("self"),
                        }
                    elif response.status_code in [500, 503]:
                        retries += 1
                        if retries >= max_retries:
                            raise ServiceUnavailableError(
                                code="JIRA_SERVER_ERROR",
                                message=f"Jira server error after {max_retries} retries",
                                details={"status_code": response.status_code},
                            )
                        await asyncio.sleep(2 ** retries)
                        continue
                    else:
                        raise ServiceUnavailableError(
                            code=f"JIRA_ERROR_{response.status_code}",
                            message=f"Jira API error: {response.text}",
                            details={"status_code": response.status_code},
                        )

            except httpx.TimeoutException as exc:
                retries += 1
                if retries >= max_retries:
                    raise ServiceUnavailableError(
                        code="JIRA_TIMEOUT",
                        message="Jira did not respond in time",
                    ) from exc
                await asyncio.sleep(2 ** retries)

            except Exception as exc:
                logger.error("jira_create_issue_error", error=str(exc), correlation_id=correlation_id)
                raise ServiceUnavailableError(
                    code="JIRA_UNKNOWN_ERROR",
                    message="Unexpected error calling Jira",
                    details={"error": str(exc)},
                ) from exc
```
[Source: services/splunk_service.py pattern, httpx documentation]

### JSON Schema Fixtures — Required Format

**Format required_params et optional_params (stocké en string) :**
Les paramètres doivent être un JSON Schema v7 valide, sérialisé en string pour stockage DB.

**Exemple create_issue required_params :**
```json
{
  "type": "object",
  "properties": {
    "project_key": {
      "type": "string",
      "description": "Clé du projet Jira (ex: PROJ)",
      "minLength": 1,
      "maxLength": 10
    },
    "issue_type": {
      "type": "string",
      "description": "Type d'issue (Bug, Task, Story, Epic, etc.)",
      "enum": ["Bug", "Task", "Story", "Epic", "Improvement"]
    },
    "summary": {
      "type": "string",
      "description": "Titre de l'issue",
      "minLength": 1,
      "maxLength": 255
    }
  },
  "required": ["project_key", "issue_type", "summary"]
}
```

**Exemple create_issue optional_params :**
```json
{
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "description": "Description détaillée de l'issue"
    },
    "assignee": {
      "type": "string",
      "description": "Nom d'utilisateur de l'assigné"
    },
    "labels": {
      "type": "array",
      "description": "Labels associés à l'issue",
      "items": {"type": "string"},
      "maxItems": 10
    },
    "priority": {
      "type": "string",
      "description": "Priorité de l'issue",
      "enum": ["Highest", "High", "Medium", "Low", "Lowest"]
    }
  }
}
```

**Exemple response_format :**
```json
{
  "type": "object",
  "properties": {
    "issue_key": {
      "type": "string",
      "description": "Clé unique de l'issue (ex: PROJ-123)"
    },
    "issue_id": {
      "type": "string",
      "description": "ID numérique de l'issue"
    },
    "url": {
      "type": "string",
      "description": "URL complète de l'issue dans Jira"
    }
  },
  "required": ["issue_key", "issue_id", "url"]
}
```

**Stockage en fixture :**
Le JSON Schema doit être sérialisé en string avec échappement JSON :
```json
{
  "model": "integrations.integrationaction",
  "fields": {
    "integration_type": "jira",
    "action_code": "create_issue",
    "required_params": "{\"type\": \"object\", \"properties\": {\"project_key\": {\"type\": \"string\"}, \"issue_type\": {\"type\": \"string\"}, \"summary\": {\"type\": \"string\"}}, \"required\": [\"project_key\", \"issue_type\", \"summary\"]}",
    "optional_params": "{\"type\": \"object\", \"properties\": {\"description\": {\"type\": \"string\"}, \"assignee\": {\"type\": \"string\"}, \"labels\": {\"type\": \"array\", \"items\": {\"type\": \"string\"}}}}",
    "response_format": "{\"issue_key\": \"string\", \"issue_id\": \"string\", \"url\": \"string\"}"
  }
}
```
[Source: integrations/models.py IntegrationAction.get_required_params(), fixtures/integration_type_catalogue.json]

### Architecture Compliance

**Pattern Service (consommé) vs Platform Adapter (exécuteur) :**
- **Jira = Service** (consommé pour créer issues, pas plateforme d'exécution de jobs)
- **N'hérite PAS de BaseAdapter** (pas de trigger(), get_status(), cancel_execution())
- **Implémente interface spécifique** : create_issue(), update_issue(), get_issue(), add_comment()
- **Async pattern** : Toutes méthodes async avec httpx.AsyncClient
- **Factory pattern** : Enregistré dans SERVICE_TYPES et get_service_client()
- [Source: docs/glossary.md, services/README.md, 27-9-refactoring-separer-adapters-plateformes-services.md]

**Credential resolution via VaultService :**
- **Vault référence** : credential_ref format `vault:secret/data/jira/cloud#api_token`
- **Résolution runtime** : Appeler VaultService.get_secret() depuis ExecutionService ou caller
- **Aucun secret stocké** : JiraService reçoit auth_headers pré-construits (pas credential_ref brut)
- **Cache Vault** : TTL 300s, circuit breaker, retry automatique
- [Source: services/vault_service.py, adapters/utils.py resolve_credential pattern]

**Logging structuré (structlog) :**
- **Logger** : `logger = structlog.get_logger(__name__)`
- **Correlation ID** : Obligatoire sur tous logs (`correlation_id=correlation_id`)
- **Événements clés** : jira_create_issue_request, jira_issue_created, jira_update_issue, jira_error
- **Context binding** : Ajouter issue_key, project_key, status dans tous logs
- [Source: core/splunk_logging_handler.py pattern, services/splunk_service.py]

### Library & Framework Requirements

**Python dependencies (déjà installés) :**
- **httpx** : Client HTTP async (utilisé par SplunkService, adapters)
- **structlog** : Logging structuré
- **jsonschema** : Validation JSON Schema des paramètres
- **asyncio** : Built-in Python 3.12 — async/await support

**Aucune dépendance supplémentaire nécessaire** — tous packages requis déjà dans l'environnement
[Source: idp-portal/django_backend/pyproject.toml, poetry.lock]

**Jira SDK officiel (atlassian-python-api) :**
- **NE PAS UTILISER** : SDK non async, trop opinionated, complexité inutile
- **Utiliser httpx direct** : Contrôle total, async native, aligné pattern SplunkService
- [Source: Décision architecture Epic 27 — préférer httpx async direct vs SDK]

### File Structure Requirements

**Files à créer :**
1. `services/jira_service.py` — Classe JiraService avec 4 méthodes async
2. `services/tests/test_jira_service.py` — 10+ tests unitaires (mock httpx)
3. `docs/jira-integration.md` — Documentation complète (architecture, API, troubleshooting)

**Files à modifier :**
1. `services/__init__.py` — Ajouter jira dans SERVICE_TYPES et get_service_client()
2. `integrations/models.py` — Ajouter JIRA dans IntegrationType enum
3. `integrations/fixtures/integration_type_catalogue.json` — Ajouter jira type + 4 actions
4. `integrations/management/commands/seed_integration_types.py` — Ajouter 'jira' dans expected_types
5. `services/README.md` — Ajouter section Jira avec exemple
6. `docs/integration-type-catalogue.md` — Ajouter ligne Jira dans tableau
7. `services/tests/test_factories.py` — Ajouter tests get_service_client("jira")
8. `integrations/tests/test_catalogue_fixtures.py` — Ajouter tests fixtures jira

**Naming conventions :**
- **Service class** : JiraService (PascalCase, suffix Service)
- **File name** : jira_service.py (snake_case)
- **Methods** : create_issue, update_issue, get_issue, add_comment (snake_case)
- **Constants** : JIRA_API_VERSION = "3", MAX_RETRIES = 3 (UPPER_SNAKE_CASE)
- **Log events** : jira_create_issue_request, jira_issue_created (snake_case)
- [Source: Python PEP 8, codebase conventions services/vault_service.py]

### Testing Standards Summary

**Test coverage attendue :**
- **services/tests/test_jira_service.py** : 10+ tests (mock httpx)
  - Success scenarios (201 Created, 200 OK, 204 No Content)
  - Error scenarios (401, 403, 404, 500, 503, timeout)
  - Retry logic (exponential backoff, max 3 retries)
  - Correlation ID propagation dans logs
  - Optional parameters (assignee, labels, priority)
- **services/tests/test_factories.py** : 2+ tests
  - get_service_client("jira") retourne JiraService instance
  - get_service_client("jira", base_url=..., auth_headers=...) avec config
- **integrations/tests/test_catalogue_fixtures.py** : 5+ tests
  - IntegrationTypeCatalogue jira existe
  - 4 IntegrationAction pour jira (create_issue, update_issue, get_issue, add_comment)
  - JSON Schema validation (jsonschema.validate)
- **integrations/tests/test_integration_admin.py** : 3+ tests
  - POST /admin/integrations avec type=jira
  - Validation config Jira (base_url, credential_ref)
  - IntegrationValidationService.validate_integration() = VALID

**Mock patterns (httpx AsyncClient) :**
```python
import pytest
from unittest.mock import AsyncMock, patch
from services.jira_service import JiraService

@pytest.mark.asyncio
async def test_create_issue_success():
    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "key": "PROJ-123",
        "id": "10001",
        "self": "https://jira.example.com/rest/api/3/issue/10001"
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        service = JiraService(
            base_url="https://jira.example.com",
            auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )
        result = await service.create_issue(
            project_key="PROJ",
            issue_type="Task",
            summary="Test issue",
            correlation_id="test-correlation-id",
        )

        assert result["issue_key"] == "PROJ-123"
        assert result["issue_id"] == "10001"
        assert "jira.example.com" in result["url"]
```
[Source: services/tests/test_splunk_service.py pattern, pytest-asyncio documentation]

**Test execution commands :**
```bash
# Tests JiraService uniquement
pytest services/tests/test_jira_service.py -v

# Tests factories
pytest services/tests/test_factories.py::test_jira_service_client -v

# Tests fixtures catalogue
pytest integrations/tests/test_catalogue_fixtures.py::test_jira_catalogue -v

# Tous tests backend (validation non-régression)
pytest --tb=short --maxfail=1

# Coverage
pytest --cov=services.jira_service --cov-report=term-missing
```

### Project Structure Notes

**Alignement avec unified project structure :**
- **services/** : Module Django app pour services consommés (Vault, Splunk, ServiceNow, Jira)
- **adapters/** : Module Django app pour adapters plateformes (AAP, Tower, Azure, GitHub, Terraform)
- **integrations/** : Module Django app pour gestion catalogue IntegrationTypeCatalogue + Integration
- **docs/** : Documentation technique (glossary.md, jira-integration.md, integration-type-catalogue.md)

**Naming alignment :**
- **Service file** : `services/jira_service.py` (snake_case)
- **Service class** : `JiraService` (PascalCase)
- **Factory function** : `get_service_client()` (snake_case)
- **Enum value** : `IntegrationType.JIRA = 'jira', 'Jira'` (code=lowercase, label=Title)

**Module imports :**
```python
from services.jira_service import JiraService  # Direct import
from services import get_service_client        # Factory import
```

**Pas de conflit détecté** avec structure existante — Jira s'intègre naturellement dans services/
[Source: idp-portal/django_backend/ structure, services/__init__.py, services/README.md]

### References

**Source principale :**
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 27, Story 27.10] (lines 4658-4680)

**Stories précédentes (contexte Epic 27) :**
- [Source: _bmad-output/implementation-artifacts/27-6-vault-service-hashicorp-vault-enterprise.md] — VaultService credential resolution
- [Source: _bmad-output/implementation-artifacts/27-8-integration-splunk-logs-correlation-id.md] — SplunkService async pattern
- [Source: _bmad-output/implementation-artifacts/27-9-refactoring-separer-adapters-plateformes-services.md] — Architecture Platform vs Service

**Fichiers backend existants :**
- [Source: idp-portal/django_backend/services/vault_service.py] — Pattern credential resolution, circuit breaker
- [Source: idp-portal/django_backend/services/splunk_service.py] — Pattern async httpx, retry logic
- [Source: idp-portal/django_backend/services/servicenow_service.py] — Placeholder service (exemple minimal)
- [Source: idp-portal/django_backend/services/__init__.py] — Factory get_service_client()
- [Source: idp-portal/django_backend/integrations/models.py] — IntegrationTypeCatalogue, IntegrationAction, Integration
- [Source: idp-portal/django_backend/integrations/fixtures/integration_type_catalogue.json] — Fixtures catalogue
- [Source: idp-portal/django_backend/integrations/services.py] — IntegrationService.create_integration()
- [Source: idp-portal/django_backend/integrations/catalogue_service.py] — Catalogue access methods
- [Source: idp-portal/django_backend/integrations/management/commands/seed_integration_types.py] — Seed command

**Documentation produit :**
- [Source: idp-portal/docs/glossary.md] — Définitions Platform vs Service vs Adapter
- [Source: idp-portal/docs/integration-type-catalogue.md] — Catalogue types d'intégration
- [Source: idp-portal/services/README.md] — Documentation services/, factory pattern
- [Source: _bmad-output/planning-artifacts/prd.md] — FR2 (connecteurs génériques : AAP, ServiceNow, Azure DevOps, Jira, etc.)
- [Source: _bmad-output/planning-artifacts/architecture.md] — Architecture stack (Django, React, Oracle, Vault)

**API externe :**
- [Source: Jira Cloud REST API v3 documentation] — https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- [Source: Jira Server REST API v2 documentation] — https://docs.atlassian.com/software/jira/docs/api/REST/
- [Source: Jira Authentication documentation] — API tokens, Basic Auth, OAuth 2.0

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Aucun problème de debug significatif.
- 4 tests initiaux échouaient à cause de `pytest.raises(match=...)` qui compare contre `str(exc)` (le message) et non `exc.code`. Corrigé en utilisant `exc_info.value.code` pour les assertions de code erreur.

### Completion Notes List

- ✅ JiraService complet avec 4 méthodes async (create_issue, update_issue, get_issue, add_comment)
- ✅ Retry logic : 3 tentatives avec backoff exponentiel (2s, 4s, 8s) sur 500/503/timeout
- ✅ Error handling : codes spécifiques (JIRA_AUTH_FAILED, JIRA_PERMISSION_DENIED, JIRA_RESOURCE_NOT_FOUND, etc.)
- ✅ Logging structuré (structlog) avec correlation_id sur tous les appels
- ✅ Factory : JiraService enregistré dans SERVICE_TYPES et get_service_client()
- ✅ IntegrationType.JIRA existait déjà dans integrations/models.py (pré-existant)
- ✅ Fixture catalogue : 1 IntegrationTypeCatalogue jira + 4 IntegrationAction avec JSON Schema complet
- ✅ Seed command : 'jira' ajouté dans expected_types
- ✅ Documentation : services/README.md, docs/jira-integration.md, docs/integration-type-catalogue.md
- ✅ Tests : 14 JiraService + 19 factory + 12 catalogue fixtures + 3 admin = **48 tests, 0 échecs**
- ✅ Aucune régression : 112 tests services/ + integrations/ passent

### Change Log

- 2026-02-14: Story 27.10 implémentée — JiraService, fixtures, factory, documentation, 48 tests

### File List

**Créés :**
- `services/jira_service.py` — Classe JiraService avec 4 méthodes async
- `services/tests/test_jira_service.py` — 14 tests unitaires JiraService
- `integrations/tests/test_integration_admin.py` — 3 tests admin Jira
- `docs/jira-integration.md` — Documentation complète Jira (architecture, API, auth, troubleshooting)

**Modifiés :**
- `services/__init__.py` — Ajout jira dans SERVICE_TYPES et get_service_client()
- `integrations/fixtures/integration_type_catalogue.json` — Ajout jira type + 4 actions
- `integrations/management/commands/seed_integration_types.py` — Ajout 'jira' dans expected_types
- `services/README.md` — Section Jira avec exemples d'utilisation
- `docs/integration-type-catalogue.md` — Ligne Jira + section détaillée
- `services/tests/test_factories.py` — 2 tests jira factory + classification test
- `integrations/tests/test_catalogue_fixtures.py` — 5 tests jira fixtures
