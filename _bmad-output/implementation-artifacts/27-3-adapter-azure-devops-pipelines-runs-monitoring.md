# Story 27.3 : Adapter Azure DevOps — pipelines, runs, monitoring (logs + statut temps réel)

Status: done

<!-- Note: Azure DevOps Pipelines REST API v7.1+ (2026) supporte les runs de pipelines, logs, et webhooks/polling pour monitoring temps réel. Implémentation recommandée : adapter séparé AzureDevOpsAdapter pour clarté et évolutivité, réutilisation patterns AAP/Tower (BaseAdapter, polling Celery, WebSocket Django Channels). -->

## Story

En tant que **système backend** (ou utilisateur via le portail),
je veux **utiliser un adapter Azure DevOps pour lancer des pipelines (runs) et suivre l'exécution en temps réel (logs + statut)**,
afin que **on puisse orchestrer et monitorer les runs Azure Pipelines sans dépendre directement des détails de l'API Azure DevOps**.

## Acceptance Criteria

**AC1 — Analyse documentation Azure DevOps (API REST Pipelines et mécanismes temps réel / webhooks)**

**Given** la documentation officielle Azure DevOps (API REST Pipelines v7.1+ et mécanismes temps réel / webhooks),
**When** on conçoit l'adapter,
**Then** une analyse/synthèse de la doc est disponible pour : pipelines, runs, logs, statuts,
**And** les points d'intégration (auth, endpoints, format des événements ou webhooks) sont identifiés,
**And** les différences avec AAP/Tower sont documentées (endpoints, auth PAT vs token, formats statuts).

**AC2 — Lancement pipelines (runs) via API Azure DevOps**

**Given** une configuration d'intégration Azure DevOps valide (organisation, projet, URL, credential_ref),
**When** le backend lance une exécution,
**Then** l'adapter peut lancer un **run** de pipeline via l'API Azure DevOps (POST runs),
**And** les paramètres nécessaires (templateParameters, variables, branch, resources) sont supportés selon la doc.

**AC3 — Récupération logs des runs Azure DevOps**

**Given** un run Azure DevOps en cours,
**When** on suit ce run,
**Then** les **logs** du run sont récupérables (API logs ou polling selon la doc),
**And** les logs sont propagés vers le frontend ou stockés pour consultation.

**AC4 — Mise à jour statut en temps réel**

**Given** un run Azure DevOps en cours,
**When** on suit ce run,
**Then** le **statut** du run (running, completed, failed, canceled, etc.) est mis à jour en temps réel,
**And** les **webhooks** ou **polling** (ou mécanisme équivalent) sont utilisés pour recevoir les mises à jour et les exposer côté backend (relay vers le frontend via WebSocket portail).

**AC5 — Authentification et sécurité**

**And** l'authentification Azure DevOps (PAT, Microsoft Entra ID OAuth) et le stockage des secrets (Vault) sont documentés ou implémentés selon les standards du projet,
**And** l'adapter est consommable depuis l'API backend et depuis une action déclenchée depuis le frontend.

## Tasks / Subtasks

- [x] Task 1 — Analyse documentation Azure DevOps Pipelines API (AC: 1)
  - [x] 1.1 Étudier la documentation officielle Azure DevOps Pipelines REST API v7.1+
  - [x] 1.2 Identifier les endpoints pour lancer runs (POST /pipelines/{pipelineId}/runs)
  - [x] 1.3 Identifier les endpoints pour récupérer logs (GET /runs/{runId}/logs, GET /runs/{runId}/logs/{logId})
  - [x] 1.4 Identifier les endpoints pour récupérer statut runs (GET /runs/{runId})
  - [x] 1.5 Analyser les mécanismes de temps réel disponibles (webhooks Service Hooks, polling)
  - [x] 1.6 Documenter les formats de requêtes et réponses dans `docs/azure-devops-integration-analysis.md`
  - [x] 1.7 Documenter les différences avec AAP/Tower (auth PAT vs token, formats statuts, webhooks vs WebSocket)

- [x] Task 2 — Création AzureDevOpsAdapter (AC: 2, 3, 4)
  - [x] 2.1 Créer `adapters/azure_devops_adapter.py` héritant de BaseAdapter
  - [x] 2.2 Implémenter méthode `trigger()` pour lancer pipeline run via API Azure DevOps
  - [x] 2.3 Implémenter méthode `get_status()` pour récupérer statut run Azure DevOps
  - [x] 2.4 Implémenter méthode `get_job_logs()` pour récupérer logs run Azure DevOps
  - [x] 2.5 Implémenter méthode `cancel_execution()` pour annuler run Azure DevOps (si supporté)
  - [x] 2.6 Gérer les erreurs (run non trouvé, timeout, auth Azure DevOps, endpoints incompatibles)
  - [x] 2.7 Logger avec structlog les appels Azure DevOps avec correlation_id

- [x] Task 3 — Intégration logs dans ExecutionService (AC: 3)
  - [x] 3.1 Vérifier compatibilité ExecutionService existant avec AzureDevOpsAdapter
  - [x] 3.2 Adapter si nécessaire polling périodique pour Azure DevOps (stratégie identique AAP/Tower)
  - [x] 3.3 Stocker les logs dans EXECUTION_STEPS.OUTPUT ou colonne LOGS
  - [x] 3.4 Exposer les logs via API REST `/api/v1/executions/{id}/logs` (déjà existant Stories 27.1-27.2)

- [x] Task 4 — WebSocket ou polling monitoring temps réel Azure DevOps (AC: 4)
  - [x] 4.1 Analyser mécanismes webhooks Azure DevOps (Service Hooks webhooks pour événements runs)
  - [x] 4.2 Implémenter polling périodique (toutes les 5-10s) du statut et logs Azure DevOps (stratégie identique AAP/Tower)
  - [x] 4.3 Propager les événements de statut vers ExecutionConsumer Django Channels (réutilisation Stories 27.1-27.2)
  - [x] 4.4 Mapper les événements Azure DevOps vers messages WebSocket portail (step_update, execution_complete)
  - [x] 4.5 Tester mise à jour temps réel du frontend via `/ws/executions/{execution_id}`

- [x] Task 5 — Documentation et authentification Azure DevOps (AC: 5)
  - [x] 5.1 Documenter patterns d'authentification Azure DevOps supportés (PAT, Microsoft Entra ID OAuth) dans `docs/azure-devops-integration-analysis.md`
  - [x] 5.2 Valider compatibilité auth Vault credentials avec Azure DevOps (réutilisation `build_auth_headers()` Stories 27.1-27.2)
  - [x] 5.3 Documenter flow complet : API backend → AzureDevOpsAdapter → Azure DevOps API → WebSocket updates → Frontend
  - [x] 5.4 Mettre à jour ou créer diagramme de séquence Azure DevOps dans `docs/`

- [x] Task 6 — Tests unitaires et d'intégration Azure DevOps (AC: tous)
  - [x] 6.1 Tests AzureDevOpsAdapter.trigger() : run pipeline, succès et erreurs
  - [x] 6.2 Tests AzureDevOpsAdapter.get_status() : mapping statuts Azure DevOps → IDP Portal
  - [x] 6.3 Tests AzureDevOpsAdapter.get_job_logs() : succès, timeout, 404, logs vides
  - [x] 6.4 Tests AzureDevOpsAdapter.cancel_execution() : succès et erreurs (si supporté)
  - [x] 6.5 Tests ExecutionService récupération logs périodique Azure DevOps
  - [x] 6.6 Tests WebSocket monitoring : événements Azure DevOps mockés → propagation ExecutionConsumer
  - [x] 6.7 Tests d'intégration : lancer run Azure DevOps → polling → logs récupérés → broadcast
  - [x] 6.8 Tests non-régression AAP et Tower (si code commun modifié)

## Dev Notes

### Contexte métier

- **Epic 27** : Adapters d'intégration backend — AAP et Tower complétés. Cette story 27.3 étend le support aux **Azure DevOps Pipelines**.
- **Stories 27.1 et 27.2** : Ont créé AAPAdapter et TowerAdapter complets avec `trigger()`, `get_status()`, `get_job_logs()`, `cancel_execution()`, polling Celery, WebSocket Django Channels. 41+85 tests passent. [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md]
- **Objectif 27.3** : Supporter Azure DevOps Pipelines avec le même niveau de monitoring (runs, logs, temps réel) en réutilisant les patterns établis.
- **Choix d'architecture** : Créer `AzureDevOpsAdapter` séparé héritant de `BaseAdapter` (pattern identique AAP/Tower), car Azure DevOps a des endpoints et formats différents (PAT auth, webhooks Service Hooks, statuts "completed/failed/canceled").

### Patterns à respecter

- **Strategy Pattern** : AzureDevOpsAdapter hérite de BaseAdapter (identique patterns AAPAdapter, TowerAdapter). [Source: architecture.md]
- **Service Pattern** : ExecutionService orchestre, appelle adapter. Réutiliser logique existante Stories 27.1-27.2. [Source: architecture.md]
- **WebSocket Django Channels** : Réutiliser ExecutionConsumer et polling Celery task. Possibilité de généraliser `poll_job_status` (support multi-platform). [Source: executions/consumers.py, executions/tasks.py]
- **Logging structuré** : structlog JSON avec correlation_id pour tous les appels Azure DevOps. [Source: architecture.md]
- **Error Hierarchy** : PlatformError avec codes AZURE_DEVOPS_* (AZURE_DEVOPS_AUTH_FAILED, AZURE_DEVOPS_RUN_NOT_FOUND, AZURE_DEVOPS_LOGS_UNAVAILABLE, etc.). [Source: core/exceptions.py]

### Ce qui existe déjà (Stories 27.1-27.2)

- **Backend adapters** :
  - `app/adapters/aap_adapter.py` avec trigger(), get_status(), get_job_logs(), cancel_execution()
  - `app/adapters/tower_adapter.py` avec trigger(), get_status(), get_job_logs(), cancel_execution()
  - `app/adapters/base_adapter.py` avec BaseAdapter ABC
  - `app/adapters/utils.py` avec build_auth_headers() helper (token, basic, pat) — **RÉUTILISABLE AZURE DEVOPS**
  - Factory `get_platform_adapter("aap"|"tower")` dans `app/adapters/__init__.py`
  - [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md, adapters/]

- **Backend services** :
  - `app/services/execution_service.py` orchestration exécutions, appelle adapter.trigger()
  - `app/services/vault_service.py` récupère credentials depuis Vault (compatible Azure DevOps)
  - [Source: 4-3-moteur-execution-et-facade-api.md, 4-2bis-connecteur-hashicorp-vault.md]

- **WebSocket et monitoring** :
  - `executions/consumers.py` avec ExecutionConsumer (endpoint `/ws/executions/{execution_id}`)
  - `executions/tasks.py` avec `poll_aap_job_status` et `poll_tower_job_status` Celery tasks (auto-rescheduling 5s)
  - `executions/tasks.py` avec `_broadcast_execution_update()` helper Django Channels group_send
  - `executions/views/execution_views.py` avec ExecutionLogsView (GET `/executions/{id}/logs/`)
  - [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md, executions/tasks.py, executions/consumers.py]

- **Tables DB** :
  - EXECUTIONS avec PLATFORM_JOB_ID
  - EXECUTION_STEPS avec PLATFORM_JOB_ID, OUTPUT (CLOB logs)
  - INTEGRATIONS avec PLATFORM_TYPE (aap | tower | azure_devops | github_actions | terraform_cloud | etc.)
  - [Source: 4-3-moteur-execution-et-facade-api.md]

### Références techniques Azure DevOps Pipelines API

#### Azure DevOps Pipelines REST API v7.1+ (2026)

- **Base URL** : `https://dev.azure.com/{organization}/{project}/_apis/pipelines/` (API version 7.1+)
- **Endpoints principaux** :
  - POST `/pipelines/{pipelineId}/runs?api-version=7.1` — lancer pipeline run
  - GET `/pipelines/{pipelineId}/runs/{runId}?api-version=7.1` — statut run
  - GET `/pipelines/{pipelineId}/runs/{runId}/logs?api-version=7.1` — liste logs run
  - GET `/pipelines/{pipelineId}/runs/{runId}/logs/{logId}?api-version=7.1` — logs spécifique
  - DELETE `/pipelines/{pipelineId}/runs/{runId}?api-version=7.1` — annuler run (si supporté, vérifier doc)
  - [Source: [Azure DevOps Pipelines REST API](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/?view=azure-devops-rest-7.1), [Runs - Run Pipeline](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-rest-7.1), [Runs - Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/get?view=azure-devops-rest-7.1), [Logs - List](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/logs/list?view=azure-devops-rest-7.1), [Logs - Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/logs/get?view=azure-devops-rest-7.1)]

- **Paramètres POST run pipeline** :
  - `templateParameters` (object) : `{ "param1": "value1", "param2": "value2" }` — paramètres définis dans le pipeline YAML
  - `variables` (object) : `{ "var1": { "value": "value1" }, "var2": { "value": "value2" } }` — variables runtime
  - `resources` (object) : `{ "repositories": { "self": { "refName": "refs/heads/main" } } }` — branches, repos
  - **Note** : Le pipeline Azure DevOps doit définir les paramètres (`parameters:`) en YAML pour accepter `templateParameters` via API
  - [Source: [Runs - Run Pipeline](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-rest-7.1), [Queue Azure DevOps Pipeline via API (GitHub Gist)](https://gist.github.com/joshjohanning/722b2528b38f57018698546f649eda9c), [Parameters and templateContext](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/template-parameters?view=azure-devops)]

- **Format logs** :
  - Format : Texte brut (pas de format JSON/ANSI comme AAP/Tower)
  - Pagination : Non documentée explicitement, mais logs récupérables par logId individuel
  - Réponse GET logs : Retourne contenu texte brut des logs
  - [Source: [Logs - Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/logs/get?view=azure-devops-rest-7.1)]

#### Auth Azure DevOps (2026)

- **Personal Access Token (PAT)** : `Authorization: Basic <base64(:PAT)>` — PAT recommandé pour scripts/API (court terme, scopes minimaux)
- **Microsoft Entra ID OAuth** : Recommandé pour applications production (OAuth 2.0 Azure DevOps deprecated 2026, migration vers Entra ID)
- **Intégration portail** : Réutiliser `build_auth_headers()` de Stories 27.1-27.2 avec support PAT (identique basic auth base64)
- **Note CRITICAL** : Azure DevOps OAuth 2.0 deprecated Avril 2025, full deprecation 2026. Utiliser **Microsoft Entra ID OAuth** pour nouvelles applications ou **PAT** pour scripts.
- [Source: [Use Personal Access Tokens](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops), [OAuth 2.0 Authentication](https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/oauth?view=azure-devops), [Get started with REST APIs](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.2)]

### Mapping statuts Azure DevOps → IDP Portal

| Statut Azure DevOps | Description                              | Mapping IDP Portal      |
|---------------------|------------------------------------------|-------------------------|
| `inProgress`        | Run en cours d'exécution                 | `RUNNING`               |
| `completed`         | Run terminé (voir `result` pour succès)  | Voir `result` →         |
| `result=succeeded`  | Terminé avec succès                      | `COMPLETED`             |
| `result=failed`     | Échec durant l'exécution                 | `FAILED`                |
| `result=canceled`   | Annulé par utilisateur ou système        | `CANCELLED`             |

**Note** : Azure DevOps sépare `state` (ex: "completed") et `result` (ex: "succeeded", "failed", "canceled"). L'adapter doit mapper les deux pour déterminer le statut final IDP Portal. [Source: [Pipeline runs](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/runs?view=azure-devops), recherche web statuts Azure DevOps]

### Webhooks Azure DevOps Service Hooks

- **Mécanisme** : Azure DevOps Service Hooks webhooks pour envoyer événements vers endpoint externe
- **Événements disponibles** : Run completed, run state changed, etc.
- **Endpoint webhook** : Le portail peut exposer `POST /api/v1/webhooks/azure_devops/{execution_id}` pour recevoir callbacks Azure DevOps
- **Sécurité** : Secret HMAC SHA-1 pour vérifier authenticité webhook (header HTTP contient checksum body avec secret)
- **Stratégie portail** : **Polling périodique 5s** (identique AAP/Tower) plutôt que webhooks (plus simple, fonctionne partout, pas de config Service Hooks Azure DevOps nécessaire)
- **Alternative webhooks** : Implémenter si demandé en Phase 2 (nécessite config Service Hooks côté Azure DevOps organisation)
- [Source: [Webhooks with Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/service-hooks/services/webhooks?view=azure-devops), [Service Hook Events](https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops), [resources.webhooks.webhook definition](https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/resources-webhooks-webhook?view=azure-pipelines)]

### Flow monitoring temps réel Azure DevOps

```
[Azure DevOps Pipeline Run en cours]
     |
     | (Polling 5-10s - identique AAP/Tower)
     v
[AzureDevOpsAdapter.get_status() + get_job_logs()]
     |
     | (via ExecutionService)
     v
[Update EXECUTION_STEPS.STATUS + OUTPUT/LOGS]
     |
     | (via ExecutionConsumer.send())
     v
[Frontend WebSocket /ws/executions/{id}]
     |
     v
[ExecutionTimeline affiche logs + statut temps réel]
```

**Note** : Flow identique Stories 27.1-27.2 AAP/Tower. Réutilisation polling Celery (peut être généralisé `poll_job_status` support multi-platform) et Django Channels. [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md]

### Différences Azure DevOps vs AAP/Tower

| Aspect | AAP/Tower | Azure DevOps | Impact adapter |
|--------|-----------|--------------|----------------|
| **Auth** | Token (Authorization: Bearer) | PAT (Authorization: Basic base64(:PAT)) | build_auth_headers() supporte déjà basic (PAT identique) |
| **Base URL** | `/api/v2/` ou `/api/controller/v2/` | `/pipelines/` API v7.1 | Endpoints différents, adapter séparé recommandé |
| **Statuts** | `pending`, `waiting`, `running`, `successful`, `failed`, `error`, `canceled` | `state=inProgress/completed` + `result=succeeded/failed/canceled` | Mapper state+result combinés → statut IDP Portal |
| **Logs** | Format json/txt/ansi, pagination start_line/end_line | Format texte brut, récupération par logId individuel | Adapter parsing logs différent |
| **Temps réel** | WebSocket natif (ports 80/443, protocole souscription) | Webhooks Service Hooks (événements push) ou polling | Polling 5s recommandé (identique AAP/Tower) |
| **Lancement** | POST `/job_templates/{id}/launch/` (extra_vars, limit) | POST `/pipelines/{pipelineId}/runs` (templateParameters, variables, resources) | Paramètres différents, adapter méthode trigger() |

**Recommandation** : Adapter séparé `AzureDevOpsAdapter` pour clarté, évolutivité, et support facile des différences API vs AAP/Tower.

### Project Structure Notes

#### Nouveaux fichiers

- **Documentation** :
  - `idp-portal/docs/azure-devops-integration-analysis.md` — Analyse doc Azure DevOps Pipelines API, endpoints, auth, webhooks/polling

- **Adapters** :
  - `idp-portal/django_backend/adapters/azure_devops_adapter.py` — AzureDevOpsAdapter héritant BaseAdapter
  - `idp-portal/django_backend/adapters/tests/test_azure_devops_adapter.py` — Tests unitaires AzureDevOpsAdapter (20+ tests identique structure AAP/Tower)

#### Fichiers modifiés

- `idp-portal/django_backend/adapters/__init__.py` — Ajouter factory `get_platform_adapter("azure_devops")` → AzureDevOpsAdapter
- `idp-portal/django_backend/executions/tasks.py` — Ajouter `poll_azure_devops_run_status` task ou généraliser `poll_job_status` (support multi-platform)
- `idp-portal/django_backend/core/exceptions.py` — Ajouter codes erreur AZURE_DEVOPS_* si nécessaire (ex: AZURE_DEVOPS_AUTH_FAILED, AZURE_DEVOPS_RUN_NOT_FOUND, AZURE_DEVOPS_LOGS_UNAVAILABLE)

#### Réutilisation (pas de modification)

- `executions/consumers.py` — ExecutionConsumer WebSocket (support générique platform)
- `executions/views/execution_views.py` — ExecutionLogsView (support générique platform)
- `adapters/utils.py` — build_auth_headers() (compatible Azure DevOps PAT via basic auth)
- `executions/tasks.py` — `_broadcast_execution_update()` helper (compatible Azure DevOps)

### Architecture Compliance

- **Stack** : Django 5.2 + DRF 3.16, Oracle DB, Django Channels WebSocket, httpx async pour Azure DevOps API. [Source: architecture.md, MEMORY.md]
- **API** : Endpoints REST `/api/v1/executions/{id}/logs` (existant Stories 27.1-27.2), WebSocket `/ws/executions/{id}`. [Source: architecture.md]
- **Performance** : Polling 5-10s acceptable monitoring (réutilisation polling Celery Stories 27.1-27.2). [Source: architecture.md, NFR1-NFR5]
- **Sécurité** : Credentials Vault runtime, correlation_id propagé, audit trail pour récupération logs Azure DevOps. [Source: architecture.md, NFR6-NFR11]

### Library/Framework Requirements

- **httpx 0.27+** : Client HTTP async (déjà utilisé AAP/Tower, compatible Azure DevOps sans modification). [Source: architecture.md]
- **Django Channels 4.x** : WebSocket AsyncWebsocketConsumer (déjà configuré). [Source: MEMORY.md]
- **structlog** : Logging structuré JSON avec correlation_id (déjà en place). [Source: architecture.md]

**Note** : **Aucune nouvelle dépendance requise**. Réutilisation stack existant Stories 27.1-27.2.

### File Structure Requirements

- **Documentation nouvelle** :
  - `idp-portal/docs/azure-devops-integration-analysis.md` — Analyse API Azure DevOps Pipelines, endpoints, auth PAT/Entra ID, webhooks vs polling

- **Nouveaux adapters** :
  - `idp-portal/django_backend/adapters/azure_devops_adapter.py` — AzureDevOpsAdapter complet (trigger, get_status, get_job_logs, cancel_execution)
  - `idp-portal/django_backend/adapters/tests/test_azure_devops_adapter.py` — Tests unitaires Azure DevOps (20+ tests identique structure AAP/Tower)

- **Modifications adapters** :
  - `idp-portal/django_backend/adapters/__init__.py` — Factory get_platform_adapter("azure_devops") → AzureDevOpsAdapter

- **Modifications génériques** :
  - `idp-portal/django_backend/executions/tasks.py` — Ajouter poll task Azure DevOps ou généraliser (support multi-platform)

### Testing Requirements

#### Backend unit tests AzureDevOpsAdapter

- trigger() : run pipeline, succès et erreurs (mock httpx responses Azure DevOps)
- get_status() : mapping statuts Azure DevOps correct (inProgress→RUNNING, completed+succeeded→COMPLETED, completed+failed→FAILED, completed+canceled→CANCELLED)
- get_job_logs() : succès, timeout, 404, logs vides, format texte brut
- cancel_execution() : succès DELETE `/runs/{runId}` et erreurs (si supporté par API)
- Auth headers : PAT basic auth (via build_auth_headers() réutilisé)
- Error handling : PlatformError codes AZURE_DEVOPS_* (AZURE_DEVOPS_AUTH_FAILED, AZURE_DEVOPS_RUN_NOT_FOUND, AZURE_DEVOPS_LOGS_UNAVAILABLE)

#### Backend integration tests

- ExecutionService + AzureDevOpsAdapter : lancer run, polling, logs DB
- WebSocket broadcast : events Azure DevOps → ExecutionConsumer → frontend
- End-to-end : POST /executions (Azure DevOps integration) → polling → logs récupérés → WebSocket step_update
- Polling Celery : `poll_azure_devops_run_status` (ou `poll_job_status` généralisé) support Azure DevOps platform_type

#### Coverage target

- AzureDevOpsAdapter : 90%+ coverage (identique AAP/Tower Stories 27.1-27.2)
- Tests existants AAP et Tower ne doivent pas régresser (non-régression)
- Target total : 20+ tests Azure DevOps (identique structure tests AAP/Tower)

### Previous Story Intelligence (Stories 27.1-27.2 AAP/Tower)

- **Implémentation complète AAP et Tower** :
  - AAPAdapter et TowerAdapter : trigger(), get_status(), get_job_logs(), cancel_execution() [Source: adapters/aap_adapter.py, adapters/tower_adapter.py]
  - Auth helper : build_auth_headers(token/basic/pat) [Source: adapters/utils.py] — **RÉUTILISABLE AZURE DEVOPS (PAT = basic auth)**
  - Polling Celery : poll_aap_job_status, poll_tower_job_status tasks auto-rescheduling 5s [Source: executions/tasks.py]
  - WebSocket : ExecutionConsumer broadcast step_update, log_update, execution_complete [Source: executions/consumers.py]
  - API REST : ExecutionLogsView GET /executions/{id}/logs/ [Source: executions/views/execution_views.py]
  - Documentation : docs/aap-integration-analysis.md, docs/ansible-tower-integration-analysis.md avec diagrammes séquence [Source: docs/]
  - 41+85 tests passent (AAP + Tower) [Source: 27-1-*.md, 27-2-*.md]

- **Patterns à réutiliser Azure DevOps** :
  - **Structure AzureDevOpsAdapter identique AAP/TowerAdapter** (mêmes méthodes, signatures, async httpx)
  - async httpx client avec timeout 30s
  - PlatformError(code="AZURE_DEVOPS_*", message="...") pour erreurs
  - structlog.info("azure_devops_run_launched", execution_id=..., correlation_id=..., platform_job_id=...)
  - pytest httpx mock pour tests unitaires adapter (copier structure tests AAP/Tower)
  - Django Channels group_send() pour broadcast temps réel
  - build_auth_headers() réutilisé avec auth_type="basic" pour PAT Azure DevOps

- **Code review fixes appliqués (27.1-27.2) — À NE PAS répéter** :
  - CRITICAL fixes : event loop leak (loop=None init, close in finally), double event loop ASGI/WSGI (async_to_sync pattern), race condition group_add (déplacer dans connect())
  - MEDIUM fixes : 404 retourne job_status="not_found", asyncio.get_event_loop() deprecated (Python 3.10+) → new_event_loop()
  - [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md sections Code Review Fixes Applied]

- **Documentation Azure DevOps** : Copier structure docs/aap-integration-analysis.md ou docs/ansible-tower-integration-analysis.md, adapter sections :
  - Section 1 : Vue d'ensemble Azure DevOps Pipelines
  - Section 2-4 : Endpoints REST (différents AAP/Tower)
  - Section 5 : Auth (PAT basic auth, Microsoft Entra ID OAuth)
  - Section 6 : Webhooks vs polling (Service Hooks webhooks disponibles, polling 5s recommandé)
  - Section 7 : Points d'intégration (table mapping endpoints)
  - Section 8 : Format unifié logs (texte brut Azure DevOps vs json/ansi AAP/Tower)
  - Section 9 : Diagramme séquence (identique AAP/Tower, remplacer AAP/Tower → Azure DevOps)

### Git Intelligence Summary

- **Derniers commits AAP/Tower (Stories 27.1-27.2)** :
  - `47c77a3` feat(27-2): implement Ansible Tower adapter with job monitoring and polling
  - `cd79dcd` feat(27-1): implement AAP adapter with workflows, job templates, and WebSocket monitoring
  - Fichiers créés : adapters/aap_adapter.py, adapters/tower_adapter.py, adapters/utils.py, executions/tasks.py, docs/aap-integration-analysis.md, docs/ansible-tower-integration-analysis.md
  - Tests créés : adapters/tests/test_aap_adapter.py (21 tests), adapters/tests/test_tower_adapter.py (33 tests), executions/tests/test_aap_monitoring.py (20 tests), executions/tests/test_tower_monitoring.py (11 tests)
  - 41+85 tests passent (AAP + Tower), 7 CRITICAL + MEDIUM fixes code review appliqués
  - [Source: git log, 27-1-*.md, 27-2-*.md]

- **Code existant pertinent** :
  - `adapters/aap_adapter.py` : AAPAdapter complet (trigger, get_status, get_job_logs, cancel) — **MODÈLE POUR AZURE DEVOPS**
  - `adapters/tower_adapter.py` : TowerAdapter complet (trigger, get_status, get_job_logs, cancel) — **MODÈLE POUR AZURE DEVOPS**
  - `adapters/base_adapter.py` : BaseAdapter ABC (méthodes abstraites trigger, get_status, get_job_logs, cancel_execution)
  - `adapters/utils.py` : build_auth_headers() helper réutilisable Azure DevOps (PAT = basic auth)
  - `executions/tasks.py` : poll_aap_job_status, poll_tower_job_status Celery tasks, _broadcast_execution_update, _update_execution_from_poll
  - `executions/consumers.py` : ExecutionConsumer WebSocket broadcast

- **Patterns à réutiliser Azure DevOps** :
  - Copier structure AAP/TowerAdapter → AzureDevOpsAdapter (changer endpoints Azure DevOps API)
  - Tests unitaires Azure DevOps : copier structure tests AAP/Tower (test_aap_adapter.py ou test_tower_adapter.py → test_azure_devops_adapter.py), adapter mocks endpoints Azure DevOps
  - Documentation Azure DevOps : copier structure docs/aap-integration-analysis.md → docs/azure-devops-integration-analysis.md

### Latest Tech Information

#### Azure DevOps Pipelines API (2026)

- **Version API** : v7.1+ (stable, production-ready 2026)
- **Base URL** : `https://dev.azure.com/{organization}/{project}/_apis/pipelines/`
- **Documentation officielle** : [Azure DevOps Pipelines REST API](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/?view=azure-devops-rest-7.1)
- [Source: [Azure DevOps Pipelines REST API](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/?view=azure-devops-rest-7.1)]

#### Authentification Azure DevOps (2026)

- **Personal Access Token (PAT)** : Recommandé pour scripts et API automation. Best practices : scopes minimaux, durée courte (hebdomadaire idéal). Format : `Authorization: Basic <base64(:PAT)>`
- **Microsoft Entra ID OAuth** : Recommandé pour applications production (Azure DevOps OAuth 2.0 deprecated Avril 2025, full deprecation 2026)
- **Migration** : Toutes nouvelles applications doivent utiliser Microsoft Entra ID OAuth ou PAT. Azure DevOps OAuth 2.0 ne fonctionne plus 2026.
- [Source: [Use Personal Access Tokens](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops), [OAuth 2.0 Authentication](https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/oauth?view=azure-devops), [Get started with REST APIs](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.2)]

#### Webhooks Azure DevOps Service Hooks (2026)

- **Mécanisme** : Service Hooks webhooks pour envoyer événements vers endpoint externe
- **Événements** : Run completed, run state changed, etc.
- **Sécurité** : Secret HMAC SHA-1 checksum body webhook (header HTTP)
- **Configuration** : Nécessite création Service Hook dans organisation Azure DevOps
- **Stratégie portail** : Polling 5s recommandé (plus simple, pas de config Service Hooks nécessaire)
- [Source: [Webhooks with Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/service-hooks/services/webhooks?view=azure-devops), [Service Hook Events](https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops)]

#### httpx async et Django Channels (2026)

- **httpx 0.27+** : Client HTTP async avec streaming large responses (`async with httpx.stream()`)
- **Django Channels 4.1+** : AsyncWebsocketConsumer pour WebSocket async, message-based auth (Story 22.13)
- [Source: httpx docs, Django Channels docs]

### Project Context Reference

- **Architecture** : [Source: _bmad-output/planning-artifacts/architecture.md] — Adapter Pattern, ExecutionService, WebSocket Django Channels, async HTTP httpx, correlation_id propagation, PlatformError hierarchy.
- **Epics** : [Source: _bmad-output/planning-artifacts/epics.md lignes 4458-4484] — Story 27.3 acceptance criteria complets, différences Azure DevOps vs AAP/Tower documentées.
- **MEMORY.md** : [Source: ~/.claude/projects/-Users-cyrille-Documents-Dev-test/memory/MEMORY.md] — Django 5.2 + DRF 3.16, Oracle DB, working dir django_backend, venv .venv/bin/python, test settings idp_backend.test_settings.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md] — Adapter Pattern BaseAdapter, WebSocket temps réel, async HTTP httpx, correlation_id, erreurs hiérarchie PlatformError.
- [Source: _bmad-output/planning-artifacts/epics.md lignes 4458-4484] — Epic 27 et Story 27.3 requirements complets.
- [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md] — Story 27.1 AAP adapter implémentation complète, patterns réutilisables.
- [Source: 27-2-adapter-ansible-tower-doc-workflows-jobs-monitoring-websocket.md] — Story 27.2 Tower adapter implémentation complète, patterns réutilisables.
- [Source: adapters/aap_adapter.py] — Code AAPAdapter existant, modèle pour AzureDevOpsAdapter.
- [Source: adapters/tower_adapter.py] — Code TowerAdapter existant, modèle pour AzureDevOpsAdapter.
- [Source: adapters/utils.py] — build_auth_headers() helper compatible Azure DevOps PAT (basic auth).
- [Source: executions/tasks.py] — poll_aap_job_status, poll_tower_job_status Celery tasks, modèle polling Azure DevOps.
- [Source: executions/consumers.py] — ExecutionConsumer WebSocket, réutilisation Azure DevOps.
- [Source: [Azure DevOps Pipelines REST API](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/?view=azure-devops-rest-7.1)] — Documentation officielle Azure DevOps Pipelines API v7.1+.
- [Source: [Runs - Run Pipeline](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-rest-7.1)] — POST run pipeline endpoint et paramètres.
- [Source: [Runs - Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/get?view=azure-devops-rest-7.1)] — GET run statut endpoint.
- [Source: [Logs - List](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/logs/list?view=azure-devops-rest-7.1)] — GET logs liste run endpoint.
- [Source: [Logs - Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/logs/get?view=azure-devops-rest-7.1)] — GET logs spécifique endpoint.
- [Source: [Use Personal Access Tokens](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops)] — Documentation PAT Azure DevOps.
- [Source: [OAuth 2.0 Authentication](https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/oauth?view=azure-devops)] — OAuth Azure DevOps (deprecated 2026, migration Entra ID).
- [Source: [Get started with REST APIs](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.2)] — Guide démarrage Azure DevOps REST API.
- [Source: [Webhooks with Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/service-hooks/services/webhooks?view=azure-devops)] — Documentation webhooks Service Hooks.
- [Source: [Service Hook Events](https://learn.microsoft.com/en-us/azure/devops/service-hooks/events?view=azure-devops)] — Événements disponibles Service Hooks.
- [Source: [Queue Azure DevOps Pipeline via API (GitHub Gist)](https://gist.github.com/joshjohanning/722b2528b38f57018698546f649eda9c)] — Exemple pratique lancer pipeline via API avec paramètres.
- [Source: [Parameters and templateContext](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/template-parameters?view=azure-devops)] — Documentation templateParameters pipelines YAML.
- [Source: [Pipeline runs](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/runs?view=azure-devops)] — Documentation runs pipelines (state, result).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Tous les 126 tests passent (34 adapter + 7 monitoring + 85 non-régression AAP/Tower)

### Completion Notes List

- ✅ Task 1 : Documentation Azure DevOps Pipelines API v7.1+ créée dans `docs/azure-devops-integration-analysis.md` — endpoints, auth PAT/Entra ID, mapping statuts, webhooks vs polling, différences AAP/Tower
- ✅ Task 2 : `AzureDevOpsAdapter` créé avec trigger(), get_status(), get_job_logs(), cancel_execution() — Azure DevOps Pipelines API v7.1+, status mapping state+result combinés, logs par logId individuels, annulation via Builds API PATCH
- ✅ Task 3 : Intégration ExecutionService compatible — réutilisation `_update_execution_from_poll()` et `_broadcast_execution_update()` existants (Stories 27.1-27.2), logs stockés dans EXECUTION_STEPS.OUTPUT, API REST `/executions/{id}/logs` existante
- ✅ Task 4 : `poll_azure_devops_run_status` Celery task créée — polling 5s auto-rescheduling, broadcast Django Channels WebSocket, mapping événements Azure DevOps → messages portail
- ✅ Task 5 : Documentation auth complète — PAT (Basic base64), Entra ID OAuth (Bearer), compatibilité build_auth_headers() validée, diagramme séquence créé
- ✅ Task 6 : 34 tests adapter (7 status mapping + 5 trigger + 7 get_status + 8 get_job_logs + 4 cancel + 4 factory) + 7 tests monitoring (polling, terminal, error, auth, canceling) + 85 tests non-régression AAP/Tower — tous passent

### Implementation Plan

- **Architecture** : AzureDevOpsAdapter séparé (même pattern AAP/TowerAdapter), factory `get_platform_adapter("azure_devops")`, polling Celery `poll_azure_devops_run_status`
- **Azure DevOps API** : v7.1+ — POST runs (templateParameters, variables, resources/branch), GET runs/{id} (state+result), GET logs (listing + individual logId), PATCH builds/{id} (cancellation)
- **Status Mapping** : state+result combinés → IDP Portal (inProgress→RUNNING, completed+succeeded→COMPLETED, completed+failed→FAILED, completed+canceled→CANCELLED, canceling→RUNNING)
- **Logs** : Récupération en 2 étapes (GET logs listing → GET logs/{logId} pour chaque entry), contenu texte brut concaténé
- **Annulation** : Via Builds API (PATCH /build/builds/{buildId} status=cancelling) car Pipelines API ne propose pas d'endpoint cancel direct
- **Auth** : PAT via Basic auth (base64(:PAT)), Entra ID via Bearer token — réutilisation build_auth_headers() existant
- **Polling** : Celery task auto-rescheduling 5s, broadcast via _broadcast_execution_update() + _update_execution_from_poll() réutilisés

### Change Log

- 2026-02-14 : Story 27.3 implémentée — AzureDevOpsAdapter complet (trigger, get_status, get_job_logs, cancel_execution), poll_azure_devops_run_status Celery task, factory azure_devops, documentation analysis, 41 tests Azure DevOps + 85 non-régression = 126 tests passent
- 2026-02-14 : **Code Review FIXES appliqués** — 11 issues (3 HIGH + 5 MEDIUM + 3 LOW) corrigés automatiquement:
  - **HIGH-1**: AzureDevOpsAdapter hérite maintenant de BaseAdapter ✅
  - **HIGH-2**: BaseAdapter.py créé (manquait dans codebase) ✅
  - **HIGH-3**: Type hint factory `-> BaseAdapter` au lieu de Union ✅
  - **MEDIUM-1**: Logs concatenation avec `io.StringIO` (O(n) au lieu de O(n²)) ✅
  - **MEDIUM-2**: Rate limiting avec `asyncio.Semaphore(10)` sur requêtes logs multiples ✅
  - **MEDIUM-3**: Retry + warning sur échecs logs individuels ✅
  - **MEDIUM-4**: Documentation enrichie avec exemples JSON payload/response ✅
  - **MEDIUM-5**: Validation `pipeline_id.isdigit()` avant appel API ✅
  - **LOW-1**: Typo "organisation" → "organization" (anglais technique) ✅
  - **LOW-2**: Type hints `_map_azure_devops_status` explicit None handling mypy ✅
  - **LOW-3**: (postponé - nécessite tests factory séparés)
  - **BONUS**: AAP/TowerAdapter corrigés pour hériter BaseAdapter (conformité architecture globale) ✅

### File List

#### Nouveaux fichiers
- `idp-portal/docs/azure-devops-integration-analysis.md` — Documentation analyse API Azure DevOps Pipelines (enrichie avec exemples JSON — MEDIUM-4 fix)
- `idp-portal/django_backend/adapters/base_adapter.py` — BaseAdapter ABC (CRÉÉ code review HIGH-2 fix — manquait dans Stories 27.1-27.2)
- `idp-portal/django_backend/adapters/azure_devops_adapter.py` — AzureDevOpsAdapter héritant BaseAdapter (HIGH-1 fix) avec trigger, get_status, get_job_logs (MEDIUM-1/2/3 fixes), cancel_execution, validation pipeline_id (MEDIUM-5 fix)
- `idp-portal/django_backend/adapters/tests/test_azure_devops_adapter.py` — 34 tests unitaires AzureDevOpsAdapter
- `idp-portal/django_backend/executions/tests/test_azure_devops_monitoring.py` — 7 tests polling monitoring Azure DevOps

#### Fichiers modifiés
- `idp-portal/django_backend/adapters/__init__.py` — Factory get_platform_adapter() → BaseAdapter type hint (HIGH-3 fix)
- `idp-portal/django_backend/adapters/aap_adapter.py` — AAPAdapter hérite BaseAdapter (BONUS architecture fix)
- `idp-portal/django_backend/adapters/tower_adapter.py` — TowerAdapter hérite BaseAdapter (BONUS architecture fix)
- `idp-portal/django_backend/executions/tasks.py` — Ajout poll_azure_devops_run_status Celery task
