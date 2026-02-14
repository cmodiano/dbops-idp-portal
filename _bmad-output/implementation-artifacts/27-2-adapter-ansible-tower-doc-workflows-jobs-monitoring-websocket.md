# Story 27.2 : Adapter Ansible Tower — analyse doc, workflows, job templates, monitoring (logs + statut via websocket)

Status: review

<!-- Note: Ansible Tower/AWX partage l'API v2 avec AAP (AWX est l'upstream de AAP Controller). Implémentation recommandée : adapter séparé TowerAdapter pour clarté et évolutivité, ou réutilisation AAPAdapter avec variant si API strictement identique. -->

## Story

En tant que **système backend** (ou utilisateur via le portail),
je veux **utiliser un adapter Ansible Tower pour lancer des workflows / job templates et suivre l'exécution des jobs en temps réel (logs + statut)**,
afin que **on puisse orchestrer et monitorer les runs Ansible sur des déploiements Tower (open source / upstream) sans dépendre directement des détails de l'API Tower**.

## Acceptance Criteria

**AC1 — Analyse documentation Ansible Tower (API REST et mécanismes temps réel)**

**Given** la documentation officielle Ansible Tower (API REST v2 et mécanismes temps réel / événements),
**When** on conçoit l'adapter,
**Then** une analyse/synthèse de la doc est disponible pour : workflows, job templates, jobs, logs, statuts,
**And** les points d'intégration (auth, endpoints, format des événements) sont identifiés,
**And** les différences éventuelles avec l'API AAP sont documentées (compatibilité upstream).

**AC2 — Lancement workflows et job templates via API Tower**

**Given** une configuration d'intégration Ansible Tower valide (URL, credential_ref),
**When** le backend lance une exécution,
**Then** l'adapter peut lancer un **workflow job** (workflow) et un **job** (job template) via l'API Tower,
**And** les paramètres nécessaires (extra_vars, limit, etc.) sont supportés selon la doc Tower.

**AC3 — Récupération logs des jobs Tower**

**Given** un job Tower en cours,
**When** on suit ce job,
**Then** les **logs** du job sont récupérables (streaming ou polling selon la doc),
**And** les logs sont propagés vers le frontend ou stockés pour consultation.

**AC4 — Mise à jour statut en temps réel**

**Given** un job Tower en cours,
**When** on suit ce job,
**Then** le **statut** du job (running, success, failed, etc.) est mis à jour en temps réel,
**And** les **websockets** (ou mécanisme équivalent côté Tower) sont utilisés pour recevoir les mises à jour et les exposer côté backend (ou relay vers le frontend selon l'architecture).

**AC5 — Authentification et sécurité**

**And** l'authentification Tower (token, OAuth, etc.) et le stockage des secrets (Vault) sont documentés ou implémentés selon les standards du projet,
**And** l'adapter est consommable depuis l'API backend et depuis une action déclenchée depuis le frontend.

## Tasks / Subtasks

- [x] Task 1 — Analyse documentation Ansible Tower/AWX (AC: 1)
  - [x] 1.1 Étudier la documentation officielle Ansible Tower / AWX API v2
  - [x] 1.2 Identifier les endpoints pour lancer workflow jobs et job templates
  - [x] 1.3 Identifier les endpoints pour récupérer logs et statut des jobs
  - [x] 1.4 Analyser les mécanismes de temps réel disponibles (websockets, polling, webhooks)
  - [x] 1.5 Documenter les différences avec AAP API (endpoints AAP 2.5+ `/api/controller/v2/` vs Tower `/api/v2/`, formats)
  - [x] 1.6 Documenter les formats de requêtes et réponses dans `docs/ansible-tower-integration-analysis.md`

- [x] Task 2 — Création TowerAdapter (ou réutilisation AAPAdapter avec variant) (AC: 2, 3, 4)
  - [x] 2.1 **Option A (Adapter séparé - RECOMMANDÉ)** : Créer `adapters/tower_adapter.py` héritant de BaseAdapter
  - [x] 2.1bis **Option B (Variant AAP)** : N/A — Option A retenue (adapter séparé)
  - [x] 2.2 Implémenter méthode `trigger()` pour lancer job_template et workflow_job via API Tower
  - [x] 2.3 Implémenter méthode `get_status()` pour récupérer statut job Tower
  - [x] 2.4 Implémenter méthode `get_job_logs()` pour récupérer logs stdout Tower
  - [x] 2.5 Implémenter méthode `cancel_execution()` pour annuler job Tower
  - [x] 2.6 Gérer les erreurs (job non trouvé, timeout, auth Tower, endpoints incompatibles)
  - [x] 2.7 Logger avec structlog les appels Tower avec correlation_id

- [x] Task 3 — Intégration logs dans ExecutionService (AC: 3)
  - [x] 3.1 Vérifier compatibilité ExecutionService existant avec TowerAdapter
  - [x] 3.2 Adapter si nécessaire polling périodique pour Tower (si différences vs AAP)
  - [x] 3.3 Stocker les logs dans EXECUTION_STEPS.OUTPUT ou colonne LOGS
  - [x] 3.4 Exposer les logs via API REST `/api/v1/executions/{id}/logs` (déjà existant Story 27.1)

- [x] Task 4 — WebSocket monitoring temps réel Tower (AC: 4)
  - [x] 4.1 Analyser mécanismes websocket Tower (identique AAP : ports 80/443, protocole souscription groups)
  - [x] 4.2 Implémenter polling périodique (toutes les 5-10s) du statut et logs Tower (identique stratégie AAP)
  - [x] 4.3 Propager les événements de statut vers ExecutionConsumer Django Channels (réutilisation Story 27.1)
  - [x] 4.4 Mapper les événements Tower vers messages WebSocket portail (step_update, execution_complete)
  - [x] 4.5 Tester mise à jour temps réel du frontend via `/ws/executions/{execution_id}`

- [x] Task 5 — Documentation et authentification Tower (AC: 5)
  - [x] 5.1 Documenter patterns d'authentification Tower supportés (token, basic, OAuth) dans `docs/ansible-tower-integration-analysis.md`
  - [x] 5.2 Valider compatibilité auth Vault credentials avec Tower (réutilisation `build_auth_headers()` Story 27.1)
  - [x] 5.3 Documenter flow complet : API backend → TowerAdapter → Tower API → WebSocket updates → Frontend
  - [x] 5.4 Mettre à jour ou créer diagramme de séquence Tower dans `docs/` (peut réutiliser diagramme AAP si identique)

- [x] Task 6 — Tests unitaires et d'intégration Tower (AC: tous)
  - [x] 6.1 Tests TowerAdapter.trigger() : job_template et workflow_job, succès et erreurs
  - [x] 6.2 Tests TowerAdapter.get_status() : mapping statuts Tower → IDP Portal (identique AAP)
  - [x] 6.3 Tests TowerAdapter.get_job_logs() : succès, timeout, 404, logs vides
  - [x] 6.4 Tests ExecutionService récupération logs périodique Tower
  - [x] 6.5 Tests WebSocket monitoring : événements Tower mockés → propagation ExecutionConsumer
  - [x] 6.6 Tests d'intégration : lancer job Tower → polling → logs récupérés → broadcast
  - [x] 6.7 Tests non-régression AAP (si code commun modifié)

## Dev Notes

### Contexte métier

- **Epic 27** : Adapters d'intégration backend — AAP en premier. Cette story 27.2 étend le support aux déploiements **Ansible Tower / AWX** (open source / upstream).
- **Story 27.1** : A créé l'adapter AAP complet avec `trigger()`, `get_status()`, `get_job_logs()`, `cancel_execution()`, polling Celery, WebSocket Django Channels. 41 tests passent. [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md]
- **Objectif 27.2** : Supporter Ansible Tower (version open source en amont d'AAP Controller) et AWX (projet upstream) avec le même niveau de monitoring (workflows, job templates, logs, temps réel).
- **Choix d'architecture** :
  - **Option A (RECOMMANDÉE)** : Créer `TowerAdapter` séparé héritant de `BaseAdapter`, car Tower/AWX peuvent avoir des endpoints ou comportements différents d'AAP (notamment AAP 2.5+ breaking change endpoints).
  - **Option B (factorisation)** : Étendre `AAPAdapter` pour supporter Tower comme variant via config (ex: `platform_type="tower"` vs `"aap"`), si API Tower strictement compatible AAP.
  - **Recommandation finale** : **Option A** pour clarté architecture, évolutivité et support facile des différences AAP 2.5+ vs Tower.

### Patterns à respecter

- **Strategy Pattern** : TowerAdapter hérite de BaseAdapter (identique pattern AAPAdapter). [Source: architecture.md]
- **Service Pattern** : ExecutionService orchestre, appelle adapter. Réutiliser logique existante Story 27.1. [Source: architecture.md]
- **WebSocket Django Channels** : Réutiliser ExecutionConsumer et polling Celery task. Possibilité de généraliser `poll_aap_job_status` → `poll_job_status` (support multi-platform). [Source: executions/consumers.py, executions/tasks.py]
- **Logging structuré** : structlog JSON avec correlation_id pour tous les appels Tower. [Source: architecture.md]
- **Error Hierarchy** : PlatformError avec codes TOWER_* (TOWER_AUTH_FAILED, TOWER_JOB_NOT_FOUND, TOWER_LOGS_UNAVAILABLE, etc.). [Source: core/exceptions.py]

### Ce qui existe déjà (Story 27.1)

- **Backend adapters** :
  - `app/adapters/aap_adapter.py` avec trigger(), get_status(), get_job_logs(), cancel_execution()
  - `app/adapters/base_adapter.py` avec BaseAdapter ABC
  - `app/adapters/utils.py` avec build_auth_headers() helper (token, basic, pat) — **RÉUTILISABLE POUR TOWER**
  - Factory `get_platform_adapter("aap")` dans `app/adapters/__init__.py`
  - [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, adapters/aap_adapter.py]

- **Backend services** :
  - `app/services/execution_service.py` orchestration exécutions, appelle adapter.trigger()
  - `app/services/vault_service.py` récupère credentials depuis Vault (compatible Tower)
  - [Source: 4-3-moteur-execution-et-facade-api.md, 4-2bis-connecteur-hashicorp-vault.md]

- **WebSocket et monitoring** :
  - `executions/consumers.py` avec ExecutionConsumer (endpoint `/ws/executions/{execution_id}`)
  - `executions/tasks.py` avec `poll_aap_job_status` Celery task (auto-rescheduling 5s)
  - `executions/tasks.py` avec `_broadcast_execution_update()` helper Django Channels group_send
  - `executions/views/execution_views.py` avec ExecutionLogsView (GET `/executions/{id}/logs/`)
  - [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md, executions/tasks.py, executions/consumers.py]

- **Tables DB** :
  - EXECUTIONS avec PLATFORM_JOB_ID
  - EXECUTION_STEPS avec PLATFORM_JOB_ID, OUTPUT (CLOB logs)
  - INTEGRATIONS avec PLATFORM_TYPE (aap | tower | servicenow | etc.)
  - [Source: 4-3-moteur-execution-et-facade-api.md]

### Références techniques Ansible Tower / AWX

#### Ansible Tower vs AWX vs AAP

- **AWX** : Projet open source upstream (communautaire), développement actif GitHub [ansible/awx](https://github.com/ansible/awx). Version actuelle : 24.x+ (2026). [Source: [AWX GitHub](https://github.com/ansible/awx)]
- **Ansible Tower** : Version commerciale supportée par Red Hat (ancêtre d'AAP Controller). Dernière version majeure : Tower 3.8.6 avant migration vers AAP. [Source: [Tower User Guide](https://docs.ansible.com/ansible-tower/latest/html/userguide/workflow_templates.html)]
- **AAP (Ansible Automation Platform)** : Successeur commercial de Tower. AAP Controller = ancien Tower. AAP 2.4 et antérieurs utilisent `/api/v2/`, AAP 2.5+ utilise `/api/controller/v2/` (breaking change). [Source: [AAP 2.5 breaking change](https://knowledge.broadcom.com/external/article/394498/ansible-automation-platformansible-tower.html)]
- **Relation** : AWX upstream → Ansible Tower (commercial) → AAP Controller (nouveau nom commercial). AWX et Tower partagent API v2 identique. [Source: [Ansible Collaborative FAQ](https://www.ansible.com/products/awx-project/faq)]

#### API Tower / AWX v2

- **Base URL** : `{base_url}/api/v2/` (ex: `https://tower.example.com/api/v2/` ou `https://awx.example.com/api/v2/`)
- **Endpoints principaux** (identiques AAP API v2) :
  - POST `/api/v2/job_templates/{id}/launch/` — lancer job template
  - POST `/api/v2/workflow_job_templates/{id}/launch/` — lancer workflow job
  - GET `/api/v2/jobs/{id}/` — statut job
  - GET `/api/v2/workflow_jobs/{id}/` — statut workflow job
  - GET `/api/v2/jobs/{id}/stdout/` — logs job template (format txt, ansi, json)
  - GET `/api/v2/workflow_jobs/{id}/stdout/` — logs workflow job
  - POST `/api/v2/jobs/{id}/cancel/` — annuler job
  - GET `/api/v2/job_events/` — événements granulaires jobs (optionnel)
  - [Source: [Tower API Reference Guide](https://docs.ansible.com/ansible-tower/latest/html/towerapi/api_ref.html), [AWX API Reference](https://docs.ansible.com/projects/awx/en/latest/rest_api/api_ref.html)]

- **Paramètres launch** :
  - `extra_vars` (string JSON) : `{"extra_vars": "{\"foo\": \"bar\"}"}`
  - `limit` (string) : hôtes/groupes cibles séparés par virgule
  - `inventory`, `credential`, `job_tags`, `skip_tags`, `job_type`, `verbosity`
  - **Note** : "Prompt on Launch" doit être activé sur le template Tower pour accepter `extra_vars` via API
  - [Source: [Tower API Reference](https://docs.ansible.com/ansible-tower/latest/html/towerapi/api_ref.html)]

- **Format logs stdout** (identique AAP) :
  - Formats supportés : `?format=txt` (texte brut), `ansi` (ANSI codes couleur), `html`, `json`
  - Pagination : `?start_line=X&end_line=Y`
  - Réponse format=json : `{"range": {"start": 0, "end": 1024, "absolute_end": 5000}, "content": "...", "content_type": "text/plain"}`
  - [Source: docs/aap-integration-analysis.md section 4]

#### Différences AAP 2.5+ vs Tower / AWX

- **AAP 2.4 et antérieurs** : Endpoints `/api/v2/*` (identiques Tower/AWX)
- **AAP 2.5+** : Endpoints changés `/api/v2/*` → `/api/controller/v2/*` (breaking change)
- **Tower / AWX** : Conservent `/api/v2/*` endpoints (pas de changement prévu)
- **Impact adapter** : Si déploiement cible est AAP 2.5+, l'adapter doit supporter les deux formats endpoints
- **Recommandation** : Config `api_path_prefix` dans Integration.config JSON :
  - `"/api/v2"` pour Tower/AWX et AAP <2.5
  - `"/api/controller/v2"` pour AAP 2.5+
  - [Source: [Broadcom Knowledge Base - AAP 2.5 breaking change](https://knowledge.broadcom.com/external/article/394498/ansible-automation-platformansible-tower.html)]

#### WebSocket Tower / AWX

- **Endpoint WebSocket** : `ws://<host>/websocket/` ou `wss://<host>/websocket/` (identique AAP)
- **Ports** : 80/443 (HTTP/HTTPS) pour streaming live playbook activity et events
- **Auth** : Token inclus dans URL ou header de connexion
- **Architecture** : django-channels + Redis (wsrelay daemon)
- **Protocole souscription** (identique AAP) :
  ```json
  {
    "groups": {
      "jobs": ["status_changed", "summary"],
      "job_events": [<job_id>],
      "workflow_events": [<workflow_job_id>]
    }
  }
  ```
- **Types événements** : `status_changed`, `summary`, `job_events`, `workflow_events`
- **Rate limit** : ~200 événements/seconde par client (configurable `MAX_WEBSOCKET_EVENT_RATE`)
- **Stratégie portail** : **Polling périodique 5s** (identique AAP Story 27.1) plutôt que websocket natif Tower (plus simple, fonctionne partout)
- [Source: [Tower Troubleshooting - Websocket](https://docs.ansible.com/ansible-tower/latest/html/administration/troubleshooting.html), docs/aap-integration-analysis.md section 6]

#### Auth Tower / AWX

- **Basic Auth** : `Authorization: Basic <base64(username:password)>` (stateless)
- **Bearer Token** : `Authorization: Bearer <token>` (créé via POST `/api/v2/tokens/`)
- **OAuth2** : Supporté (identique AAP)
- **Personal Access Token (PAT)** : Supporté
- **Intégration portail** : Réutiliser `build_auth_headers()` de Story 27.1 (compatible Tower)
- [Source: [Tower API Reference](https://docs.ansible.com/ansible-tower/latest/html/towerapi/api_ref.html), adapters/utils.py]

### Mapping statuts Tower → IDP Portal

| Statut Tower/AWX | Description                              | Mapping IDP Portal      |
|------------------|------------------------------------------|-------------------------|
| `pending`        | Job créé, pas encore en file             | `SUBMITTED`             |
| `waiting`        | En file d'attente                        | `SUBMITTED`             |
| `running`        | En cours d'exécution                     | `RUNNING`               |
| `successful`     | Terminé avec succès                      | `COMPLETED`             |
| `failed`         | Échec durant l'exécution                 | `FAILED`                |
| `error`          | Erreur système (pas erreur playbook)     | `FAILED`                |
| `canceled`       | Annulé par utilisateur ou système        | `CANCELLED`             |

**Note** : Mapping identique AAP (Story 27.1). [Source: docs/aap-integration-analysis.md section 3.3]

### Flow monitoring temps réel Tower

```
[Tower Job running]
     |
     | (Polling 5-10s - identique AAP)
     v
[TowerAdapter.get_status() + get_job_logs()]
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

**Note** : Flow identique Story 27.1 AAP. Réutilisation polling Celery `poll_aap_job_status` (peut être généralisé `poll_job_status` support multi-platform) et Django Channels. [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md]

### Options d'implémentation

#### Option A : Adapter séparé TowerAdapter (RECOMMANDÉ)

**Avantages** :
- Séparation claire Tower vs AAP (futures évolutions indépendantes)
- Facilite tests et debugging spécifiques Tower
- Permet gestion différences subtiles API (ex: formats réponse, codes erreur, AAP 2.5+ breaking change)
- Conformité pattern Strategy (un adapter par plateforme)
- Support facile AAP 2.5+ vs Tower (endpoints différents)

**Inconvénients** :
- Code dupliqué si Tower API strictement identique AAP (acceptable pour clarté)

**Implémentation** :
```python
# adapters/tower_adapter.py
class TowerAdapter(BaseAdapter):
    """Adapter Ansible Tower / AWX API v2."""

    async def trigger(self, integration: dict, action_config: dict, execution_id: int, ...) -> dict:
        # POST /api/v2/job_templates/{id}/launch/
        # Logique identique AAPAdapter (réutiliser code ou copier)
        endpoint = f"{self.base_url}/api/v2/job_templates/{template_id}/launch/"
        # ...

    async def get_status(self, integration: dict, platform_job_id: str, resource_type: str) -> dict:
        # GET /api/v2/jobs/{id}/ ou /api/v2/workflow_jobs/{id}/
        # Identique AAP
        # ...

    async def get_job_logs(self, integration: dict, platform_job_id: str, resource_type: str) -> dict:
        # GET /api/v2/jobs/{id}/stdout/
        # Identique AAP
        # ...

    async def cancel_execution(self, integration: dict, platform_job_id: str, resource_type: str) -> dict:
        # POST /api/v2/jobs/{id}/cancel/
        # Identique AAP
        # ...
```

**Factory update** :
```python
# adapters/__init__.py
def get_platform_adapter(platform_type: str, integration: dict) -> BaseAdapter:
    if platform_type == "aap":
        return AAPAdapter(integration)
    elif platform_type == "tower":
        return TowerAdapter(integration)
    # ...
```

#### Option B : AAPAdapter avec variant Tower

**Avantages** :
- Évite duplication code si Tower API strictement identique AAP
- Un seul adapter à maintenir

**Inconvénients** :
- Complexité conditionnelle dans le code (if platform_type == "tower" ...)
- Coupling AAP et Tower dans un même fichier
- Risque régression si divergence future API (notamment AAP 2.5+ endpoints)
- Difficulté support AAP 2.5+ vs Tower (endpoints différents)

**Implémentation** :
```python
# adapters/aap_adapter.py (étendu)
class AAPAdapter(BaseAdapter):
    """Adapter AAP / Tower API v2."""

    def __init__(self, integration: dict):
        self.platform_type = integration.get("platform_type", "aap")  # "aap" | "tower"
        config = integration.get("config", {})
        aap_version = config.get("aap_version", "2.4")

        # Déterminer api_prefix selon plateforme et version
        if self.platform_type == "tower":
            self.api_prefix = "/api/v2"
        elif self.platform_type == "aap" and aap_version >= "2.5":
            self.api_prefix = "/api/controller/v2"
        else:
            self.api_prefix = "/api/v2"

    async def trigger(self, ...):
        endpoint = f"{self.base_url}{self.api_prefix}/job_templates/{id}/launch/"
        # ...
```

**Recommandation finale** : **Option A (TowerAdapter séparé)** pour :
- Clarté architecture et évolutivité
- Support facile AAP 2.5+ breaking change vs Tower
- Tests et debugging indépendants
- Conformité pattern Strategy

### Project Structure Notes

#### Nouveaux fichiers (si Option A - TowerAdapter séparé RECOMMANDÉ)

- **Documentation** :
  - `idp-portal/docs/ansible-tower-integration-analysis.md` — Analyse doc Tower/AWX, différences AAP, endpoints, auth, websocket

- **Adapters** :
  - `idp-portal/django_backend/adapters/tower_adapter.py` — TowerAdapter héritant BaseAdapter
  - `idp-portal/django_backend/adapters/tests/test_tower_adapter.py` — Tests unitaires TowerAdapter (21+ tests identique AAP)

#### Fichiers modifiés

- `idp-portal/django_backend/adapters/__init__.py` — Ajouter factory `get_platform_adapter("tower")` → TowerAdapter
- `idp-portal/django_backend/executions/tasks.py` — Optionnel : généraliser `poll_aap_job_status` → `poll_job_status` (support multi-platform) si souhaité
- `idp-portal/django_backend/core/exceptions.py` — Ajouter codes erreur TOWER_* si différents AAP (ex: TOWER_AUTH_FAILED, TOWER_JOB_NOT_FOUND)

#### Réutilisation (pas de modification)

- `executions/consumers.py` — ExecutionConsumer WebSocket (support générique platform)
- `executions/views/execution_views.py` — ExecutionLogsView (support générique platform)
- `adapters/utils.py` — build_auth_headers() (compatible Tower sans modification)
- `executions/tasks.py` — `_broadcast_execution_update()` helper (compatible Tower)

### Architecture Compliance

- **Stack** : Django 5.2 + DRF 3.16, Oracle DB, Django Channels WebSocket, httpx async pour Tower API. [Source: architecture.md, MEMORY.md]
- **API** : Endpoints REST `/api/v1/executions/{id}/logs` (existant Story 27.1), WebSocket `/ws/executions/{id}`. [Source: architecture.md]
- **Performance** : Polling 5-10s acceptable monitoring (réutilisation polling Celery Story 27.1). [Source: architecture.md, NFR1-NFR5]
- **Sécurité** : Credentials Vault runtime, correlation_id propagé, audit trail pour récupération logs Tower. [Source: architecture.md, NFR6-NFR11]

### Library/Framework Requirements

- **httpx 0.27+** : Client HTTP async (déjà utilisé AAP, compatible Tower sans modification). [Source: architecture.md]
- **Django Channels 4.x** : WebSocket AsyncWebsocketConsumer (déjà configuré). [Source: MEMORY.md]
- **structlog** : Logging structuré JSON avec correlation_id (déjà en place). [Source: architecture.md]

**Note** : **Aucune nouvelle dépendance requise**. Réutilisation stack existant Story 27.1.

### File Structure Requirements

- **Documentation nouvelle** :
  - `idp-portal/docs/ansible-tower-integration-analysis.md` — Analyse API Tower/AWX, différences AAP 2.5+, endpoints, auth, websocket

- **Nouveaux adapters (Option A RECOMMANDÉ)** :
  - `idp-portal/django_backend/adapters/tower_adapter.py` — TowerAdapter complet (trigger, get_status, get_job_logs, cancel_execution)
  - `idp-portal/django_backend/adapters/tests/test_tower_adapter.py` — Tests unitaires Tower (21+ tests identique structure AAP)

- **Modifications adapters (Option B - si variant AAP)** :
  - `idp-portal/django_backend/adapters/aap_adapter.py` — Étendre pour supporter platform_type="tower"

- **Modifications génériques** :
  - `idp-portal/django_backend/adapters/__init__.py` — Factory get_platform_adapter("tower") → TowerAdapter
  - `idp-portal/django_backend/executions/tasks.py` — Optionnel : généraliser poll task (renommage `poll_job_status` support multi-platform)

### Testing Requirements

#### Backend unit tests TowerAdapter

- trigger() : job_template et workflow_job, succès et erreurs (mock httpx responses Tower)
- get_status() : mapping statuts Tower correct (pending/waiting→SUBMITTED, running→RUNNING, successful→COMPLETED, failed/error→FAILED, canceled→CANCELLED)
- get_job_logs() : succès, timeout, 404, logs vides, format json vs txt
- cancel_execution() : succès POST `/api/v2/jobs/{id}/cancel/` et erreurs
- Auth headers : basic, token, OAuth, PAT (via build_auth_headers() réutilisé)
- Error handling : PlatformError codes TOWER_* (TOWER_AUTH_FAILED, TOWER_JOB_NOT_FOUND, TOWER_LOGS_UNAVAILABLE)

#### Backend integration tests

- ExecutionService + TowerAdapter : lancer job, polling, logs DB
- WebSocket broadcast : events Tower → ExecutionConsumer → frontend
- End-to-end : POST /executions (Tower integration) → polling → logs récupérés → WebSocket step_update
- Polling Celery : `poll_aap_job_status` (ou `poll_job_status` généralisé) support Tower platform_type

#### Coverage target

- TowerAdapter : 90%+ coverage (identique AAP Story 27.1)
- Tests existants AAP ne doivent pas régresser (non-régression)
- Target total : 20+ tests Tower (identique structure 21 tests AAP)

### Previous Story Intelligence (Story 27.1 AAP)

- **Implémentation complète AAP** :
  - AAPAdapter : trigger(), get_status(), get_job_logs(), cancel_execution() [Source: adapters/aap_adapter.py]
  - Auth helper : build_auth_headers(token/basic/pat) [Source: adapters/utils.py] — **RÉUTILISABLE TOWER**
  - Polling Celery : poll_aap_job_status task auto-rescheduling 5s [Source: executions/tasks.py]
  - WebSocket : ExecutionConsumer broadcast step_update, log_update, execution_complete [Source: executions/consumers.py]
  - API REST : ExecutionLogsView GET /executions/{id}/logs/ [Source: executions/views/execution_views.py]
  - Documentation : docs/aap-integration-analysis.md avec diagramme séquence [Source: docs/aap-integration-analysis.md]
  - 41 tests passent (21 adapter + 20 monitoring) [Source: 27-1-*.md]

- **Patterns à réutiliser Tower** :
  - **Structure TowerAdapter identique AAPAdapter** (mêmes méthodes, signatures, async httpx)
  - async httpx client avec timeout 30s
  - PlatformError(code="TOWER_*", message="...") pour erreurs
  - structlog.info("tower_job_launched", execution_id=..., correlation_id=..., platform_job_id=...)
  - pytest httpx mock pour tests unitaires adapter (copier structure tests AAP)
  - Django Channels group_send() pour broadcast temps réel
  - build_auth_headers() réutilisé sans modification

- **Code review fixes appliqués (27.1) — À NE PAS répéter** :
  - CRITICAL fixes : event loop leak (loop=None init, close in finally), double event loop ASGI/WSGI (async_to_sync pattern), race condition group_add (déplacer dans connect())
  - MEDIUM fixes : 404 retourne job_status="not_found", asyncio.get_event_loop() deprecated (Python 3.10+) → new_event_loop()
  - [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md section Code Review Fixes Applied]

- **Documentation Tower** : Copier structure docs/aap-integration-analysis.md, adapter sections :
  - Section 1 : Vue d'ensemble Tower/AWX
  - Section 2-4 : Endpoints REST (identiques AAP sauf AAP 2.5+)
  - Section 5 : Auth (identique AAP)
  - Section 6 : WebSocket (identique AAP, polling recommandé)
  - Section 7 : Points d'intégration (table mapping endpoints)
  - Section 8 : Format unifié logs (identique AAP)
  - Section 9 : Diagramme séquence (identique AAP, remplacer AAP → Tower)

### Git Intelligence Summary

- **Dernier commit AAP (Story 27.1)** :
  - `cd79dcd` feat(27-1): implement AAP adapter with workflows, job templates, and WebSocket monitoring
  - Fichiers créés : adapters/aap_adapter.py (411 LOC), adapters/utils.py (85 LOC), executions/tasks.py (298 LOC), docs/aap-integration-analysis.md (274 LOC)
  - Tests créés : adapters/tests/test_aap_adapter.py (342 LOC, 21 tests), executions/tests/test_aap_monitoring.py (451 LOC, 20 tests)
  - 41 tests passent, 7 CRITICAL + MEDIUM fixes code review appliqués
  - [Source: git log, git show cd79dcd, 27-1-*.md]

- **Code existant pertinent** :
  - `adapters/aap_adapter.py` : AAPAdapter complet (trigger, get_status, get_job_logs, cancel) — **MODÈLE POUR TOWER**
  - `adapters/base_adapter.py` : BaseAdapter ABC (méthodes abstraites trigger, get_status, get_job_logs, cancel_execution)
  - `adapters/utils.py` : build_auth_headers() helper réutilisable Tower
  - `executions/tasks.py` : poll_aap_job_status Celery task, _broadcast_execution_update, _update_execution_from_poll
  - `executions/consumers.py` : ExecutionConsumer WebSocket broadcast

- **Patterns à réutiliser Tower** :
  - Copier structure AAPAdapter → TowerAdapter (changer endpoints si AAP 2.5+ config)
  - Tests unitaires Tower : copier structure tests AAP (test_aap_adapter.py → test_tower_adapter.py), adapter mocks endpoints Tower
  - Documentation Tower : copier structure docs/aap-integration-analysis.md → docs/ansible-tower-integration-analysis.md

### Latest Tech Information

#### Ansible Tower versions

- **Tower 3.8.6** : Dernière version majeure avant migration vers AAP Controller
- API v2 stable, endpoints `/api/v2/` standards (identiques AAP <2.5)
- [Source: [Tower User Guide](https://docs.ansible.com/ansible-tower/latest/html/userguide/workflow_templates.html)]

#### AWX (upstream open source)

- **Version actuelle** : 24.x+ (développement continu 2026)
- API identique Tower API v2 (`/api/v2/`)
- awx.awx collection Ansible : version 17.1.0 (install via `ansible-galaxy collection install awx.awx`)
- [Source: [AWX GitHub](https://github.com/ansible/awx), [awx.awx collection](https://docs.ansible.com/ansible/latest/collections/awx/awx/workflow_job_template_module.html)]

#### Compatibilité AAP vs Tower/AWX

- **AAP 2.4 et antérieurs** : API `/api/v2/` compatible Tower/AWX
- **AAP 2.5+ (2026)** : API changée `/api/v2/*` → `/api/controller/v2/*` (breaking change)
- **Tower / AWX** : Conservent `/api/v2/*` endpoints (pas de changement prévu)
- **Adapter doit supporter** : Les deux formats via config `api_path_prefix` dans Integration.config JSON
- [Source: [Broadcom AAP 2.5 breaking change](https://knowledge.broadcom.com/external/article/394498/ansible-automation-platformansible-tower.html)]

#### WebSocket Tower / AWX (2026)

- **Ports 80/443** : Streaming live playbook activity et events (identique AAP)
- **Protocole** : Identique AAP (souscription groups: jobs, job_events, workflow_events)
- **Implémentation portail** : **Polling Celery 5s** (identique AAP Story 27.1) plutôt que websocket natif (plus simple, fonctionne partout)
- [Source: [Tower Troubleshooting](https://docs.ansible.com/ansible-tower/latest/html/administration/troubleshooting.html), docs/aap-integration-analysis.md]

#### httpx async et Django Channels (2026)

- **httpx 0.27+** : Client HTTP async avec streaming large responses (`async with httpx.stream()`)
- **Django Channels 4.1+** : AsyncWebsocketConsumer pour WebSocket async, message-based auth (Story 22.13)
- [Source: httpx docs, Django Channels docs]

### Project Context Reference

- **Architecture** : [Source: _bmad-output/planning-artifacts/architecture.md] — Adapter Pattern, ExecutionService, WebSocket Django Channels, async HTTP httpx, correlation_id propagation, PlatformError hierarchy.
- **Epics** : [Source: _bmad-output/planning-artifacts/epics.md lignes 4430-4456] — Story 27.2 acceptance criteria complets, différences Tower vs AAP documentées.
- **MEMORY.md** : [Source: ~/.claude/projects/-Users-cyrille-Documents-Dev-test/memory/MEMORY.md] — Django 5.2 + DRF 3.16, Oracle DB, working dir django_backend, venv .venv/bin/python, test settings idp_backend.test_settings.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md] — Adapter Pattern BaseAdapter, WebSocket temps réel, async HTTP httpx, correlation_id, erreurs hiérarchie PlatformError.
- [Source: _bmad-output/planning-artifacts/epics.md lignes 4430-4456] — Epic 27 et Story 27.2 requirements complets.
- [Source: 27-1-adapter-aap-doc-workflows-jobs-monitoring-websocket.md] — Story 27.1 AAP adapter implémentation complète, patterns réutilisables Tower.
- [Source: adapters/aap_adapter.py] — Code AAPAdapter existant, modèle pour TowerAdapter.
- [Source: adapters/utils.py] — build_auth_headers() helper compatible Tower sans modification.
- [Source: executions/tasks.py] — poll_aap_job_status Celery task, modèle polling Tower.
- [Source: executions/consumers.py] — ExecutionConsumer WebSocket, réutilisation Tower.
- [Source: [Ansible Tower API Reference](https://docs.ansible.com/ansible-tower/latest/html/towerapi/api_ref.html)] — Documentation officielle Tower API v2.
- [Source: [AWX API Reference](https://docs.ansible.com/projects/awx/en/latest/rest_api/api_ref.html)] — Documentation AWX API (upstream).
- [Source: [AWX GitHub](https://github.com/ansible/awx)] — Projet open source upstream Tower, version 24.x+ 2026.
- [Source: [AAP 2.5 breaking change](https://knowledge.broadcom.com/external/article/394498/ansible-automation-platformansible-tower.html)] — Différences endpoints AAP 2.5+ (`/api/controller/v2/`) vs Tower (`/api/v2/`).
- [Source: [Tower WebSocket troubleshooting](https://docs.ansible.com/ansible-tower/latest/html/administration/troubleshooting.html)] — WebSocket ports 80/443 et configuration.
- [Source: [Tower Workflow Templates Guide](https://docs.ansible.com/ansible-tower/latest/html/userguide/workflow_templates.html)] — Documentation workflows Tower.
- [Source: [Configure AWX 2026](https://oneuptime.com/blog/post/2026-01-24-configure-ansible-tower-awx/view)] — Guide configuration AWX/Tower 2026.
- [Source: [Ansible AWX REST API Guide](https://medium.com/@claudio.domingos/ansible-awx-from-scratch-to-rest-api-part-6-of-8-328112dbe426)] — Guide pratique AWX REST API.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A

### Completion Notes List

- **Option A retenue** : TowerAdapter séparé (`tower_adapter.py`) pour clarté architecture et évolutivité AAP 2.5+ vs Tower
- **TowerAdapter** : 4 méthodes async (trigger, get_status, get_job_logs, cancel_execution) avec error codes TOWER_* et structlog correlation_id
- **Factory** : `get_platform_adapter("tower"|"aap")` dans `adapters/__init__.py` pour instanciation selon platform_type
- **Polling Celery** : `poll_tower_job_status` task auto-rescheduling 5s, miroir de poll_aap_job_status avec TowerAdapter
- **Réutilisation Story 27.1** : build_auth_headers(), ExecutionConsumer, _broadcast_execution_update(), _update_execution_from_poll(), ExecutionLogsView — tous compatibles Tower sans modification
- **Documentation** : `docs/ansible-tower-integration-analysis.md` — analyse complète Tower/AWX API v2, différences AAP 2.5+, auth, WebSocket, diagramme séquence
- **Tests** : 33 tests TowerAdapter (logs, status, trigger, cancel, factory, status mapping) + 11 tests monitoring Tower (polling running/terminal/error/cancel/basic auth/workflow) + 41 tests AAP non-régression = **85/85 tests passent**

### Implementation Plan

1. Créé `docs/ansible-tower-integration-analysis.md` avec analyse complète (Task 1, AC1)
2. Créé `adapters/tower_adapter.py` — TowerAdapter séparé avec TOWER_STATUS_MAP et error codes TOWER_* (Task 2, AC2/3/4)
3. Ajouté factory `get_platform_adapter()` dans `adapters/__init__.py` (Task 2)
4. ExecutionService compatible Tower via factory pattern — logs stockés EXECUTION_STEPS.OUTPUT via _update_execution_from_poll() (Task 3, AC3)
5. Créé `poll_tower_job_status` Celery task dans `executions/tasks.py` — polling 5s + broadcast Django Channels (Task 4, AC4)
6. Documentation auth (token, basic, OAuth, PAT) et diagramme séquence dans analyse doc (Task 5, AC5)
7. 33 tests adapter + 11 tests monitoring + 41 tests AAP non-régression = 85/85 (Task 6)

### File List

**Nouveaux fichiers :**
- `idp-portal/docs/ansible-tower-integration-analysis.md` — Analyse intégration Tower/AWX API v2
- `idp-portal/django_backend/adapters/tower_adapter.py` — TowerAdapter (trigger, get_status, get_job_logs, cancel_execution)
- `idp-portal/django_backend/adapters/tests/test_tower_adapter.py` — 33 tests unitaires TowerAdapter + factory
- `idp-portal/django_backend/executions/tests/test_tower_monitoring.py` — 11 tests monitoring Tower polling

**Fichiers modifiés :**
- `idp-portal/django_backend/adapters/__init__.py` — Ajout factory get_platform_adapter("tower"|"aap")
- `idp-portal/django_backend/executions/tasks.py` — Ajout poll_tower_job_status Celery task

## Change Log

- 2026-02-14: Story 27.2 implémentation complète — TowerAdapter séparé (Option A), poll_tower_job_status Celery, documentation Tower/AWX, factory adapter, 85/85 tests passent (33 adapter + 11 monitoring + 41 AAP non-régression)
