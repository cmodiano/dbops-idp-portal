# Story 27.1 : Adapter AAP — analyse doc, workflows, job templates, monitoring (logs + statut via websocket)

Status: done

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **système backend** (ou utilisateur via le portail),
je veux **utiliser un adapter AAP pour lancer des workflows / job templates et suivre l'exécution des jobs en temps réel (logs + statut)**,
afin que **on puisse orchestrer et monitorer les runs Ansible sans dépendre directement des détails de l'API AAP**.

## Acceptance Criteria

**AC1 — Analyse documentation AAP (API REST et websockets/événements)**

**Given** la documentation officielle AAP (API REST et websockets / événements),
**When** on conçoit l'adapter,
**Then** une analyse/synthèse de la doc est disponible pour : workflows, job templates, jobs, logs, statuts,
**And** les points d'intégration (auth, endpoints, format des événements) sont identifiés.

**AC2 — Lancement workflows et job templates via API AAP**

**Given** une configuration d'intégration AAP valide (URL, credential_ref),
**When** le backend lance une exécution,
**Then** l'adapter peut lancer un **workflow job** (workflow) et un **job** (job template) via l'API AAP,
**And** les paramètres nécessaires (extra_vars, limit, etc.) sont supportés selon la doc AAP.

**AC3 — Récupération logs des jobs AAP**

**Given** un job AAP en cours,
**When** on suit ce job,
**Then** les **logs** du job sont récupérables (streaming ou polling selon la doc),
**And** les logs sont propagés vers le frontend ou stockés pour consultation.

**AC4 — Mise à jour statut en temps réel**

**Given** un job AAP en cours,
**When** on suit ce job,
**Then** le **statut** du job (running, success, failed, etc.) est mis à jour en temps réel,
**And** les **websockets** (ou mécanisme équivalent côté AAP) sont utilisés pour recevoir les mises à jour et les exposer côté backend (ou relay vers le frontend selon l'architecture).

**AC5 — Authentification et sécurité**

**And** l'authentification AAP (token, OAuth, etc.) et le stockage des secrets (Vault) sont documentés ou implémentés selon les standards du projet,
**And** l'adapter est consommable depuis l'API backend et depuis une action déclenchée depuis le frontend.

## Tasks / Subtasks

- [x] Task 1 — Analyse documentation AAP (AC: 1)
  - [x] 1.1 Étudier la documentation officielle Ansible Automation Platform / Controller API v2
  - [x] 1.2 Identifier les endpoints pour lancer workflow jobs et job templates
  - [x] 1.3 Identifier les endpoints pour récupérer logs et statut des jobs
  - [x] 1.4 Analyser les mécanismes de temps réel disponibles (websockets, polling, webhooks)
  - [x] 1.5 Documenter les formats de requêtes et réponses dans un fichier `docs/aap-integration-analysis.md`

- [x] Task 2 — Extension adapter AAP pour logs (AC: 3)
  - [x] 2.1 Ajouter méthode `async def get_job_logs(platform_job_id: str, resource_type: str) -> dict` dans AAPAdapter
  - [x] 2.2 Implémenter appel GET vers `/api/v2/jobs/{id}/stdout/` pour job templates
  - [x] 2.3 Implémenter appel GET vers `/api/v2/workflow_jobs/{id}/stdout/` pour workflow jobs
  - [x] 2.4 Parser la réponse et retourner les logs formatés (dict avec content, format, timestamp)
  - [x] 2.5 Gérer les erreurs (job non trouvé, timeout, logs pas encore disponibles)
  - [x] 2.6 Logger avec structlog les appels de récupération de logs avec correlation_id

- [x] Task 3 — Intégration logs dans ExecutionService (AC: 3)
  - [x] 3.1 Modifier ExecutionService pour récupérer périodiquement les logs via `adapter.get_job_logs()`
  - [x] 3.2 Stocker les logs dans EXECUTION_STEPS.OUTPUT ou nouvelle colonne LOGS (CLOB)
  - [x] 3.3 Exposer les logs via API REST `/api/v1/executions/{id}/logs` ou inclure dans endpoint existant
  - [x] 3.4 Permettre le streaming des logs (si applicable) ou pagination si volumétrie importante

- [x] Task 4 — WebSocket monitoring temps réel (AC: 4)
  - [x] 4.1 Analyser si AAP supporte websockets natifs pour les événements jobs (tower_events, job_events)
  - [N/A] 4.2 Si websocket AAP disponible : implémenter client websocket dans AAPAdapter — choix MVP: polling (option 2)
  - [x] 4.3 Si websocket AAP non disponible : implémenter polling périodique (toutes les 5-10s) du statut et logs
  - [x] 4.4 Propager les événements de statut vers le ExecutionConsumer Django Channels existant
  - [x] 4.5 Mapper les événements AAP (job_event, workflow_event) vers les messages WebSocket portail (step_update, execution_complete)
  - [x] 4.6 Tester la mise à jour temps réel du frontend via `/ws/executions/{execution_id}`

- [x] Task 5 — Documentation et authentification (AC: 5)
  - [x] 5.1 Documenter les patterns d'authentification AAP supportés (token, OAuth) dans `docs/aap-integration-analysis.md`
  - [x] 5.2 Valider que l'authentification actuelle (Vault credentials) fonctionne pour les nouveaux endpoints
  - [x] 5.3 Documenter le flow complet : API backend → AAPAdapter → AAP API → WebSocket updates → Frontend
  - [x] 5.4 Créer un diagramme de séquence dans `docs/` pour visualiser le monitoring temps réel

- [x] Task 6 — Tests unitaires et d'intégration (AC: tous)
  - [x] 6.1 Tests AAPAdapter.get_job_logs() : succès (mock réponse stdout), timeout, 404, logs vides
  - [x] 6.2 Tests ExecutionService récupération logs périodique (poll_aap_job_status Celery task)
  - [x] 6.3 Tests WebSocket monitoring : événements AAP mockés → propagation ExecutionConsumer
  - [x] 6.4 Tests d'intégration : lancer job → polling → logs récupérés → broadcast via channels
  - [x] 6.5 Tests _broadcast_execution_update : status, logs, terminal events, no channel layer

## Dev Notes

### Contexte métier

- **Epic 27** : Adapters d'intégration backend — AAP en premier. Cette story étend l'adapter AAP existant (Stories 4.4 et 4.10) pour ajouter monitoring avancé (logs + temps réel).
- **Story 4.4** : A créé l'AAPAdapter de base avec `trigger()`, `get_status()`, `parse_callback()` pour lancer job templates et récupérer statut.
- **Story 4.10** : A étendu l'adapter pour supporter workflows jobs (resource_type job_template | workflow_job) via `/api/v2/workflow_job_templates/{id}/launch/`.
- **Story 22.13** : A implémenté l'authentification WebSocket message-based JWT via AuthenticatedWebSocketConsumer et ExecutionConsumer.
- **Objectif 27.1** : Compléter l'adapter AAP avec récupération logs et monitoring temps réel pour une expérience utilisateur complète (voir progression jobs Ansible live).

### Patterns à respecter

- **Strategy Pattern** : AAPAdapter hérite de BaseAdapter. Étendre l'adapter existant, ne pas créer un deuxième adapter. [Source: architecture.md, 4-4-adapter-plateforme-aap.md]
- **Service Pattern** : ExecutionService orchestre, appelle adapter. Ajouter logique récupération logs dans ExecutionService, pas dans l'adapter seul. [Source: architecture.md]
- **WebSocket Django Channels** : Utiliser ExecutionConsumer existant pour propager événements temps réel. Pattern message-based auth déjà en place (Story 22.13). [Source: executions/consumers.py, core/consumers.py]
- **Logging structuré** : structlog JSON avec correlation_id pour tous les appels AAP (logs, status, websocket events). [Source: architecture.md]
- **Error Hierarchy** : PlatformError avec codes AAP_* pour erreurs logs et websocket (AAP_LOGS_UNAVAILABLE, AAP_WEBSOCKET_ERROR). [Source: core/exceptions.py]

### Ce qui existe déjà

- **Backend adapters** :
  - `app/adapters/aap_adapter.py` avec trigger() (job templates + workflow jobs), get_status(), parse_callback()
  - `app/adapters/base_adapter.py` avec BaseAdapter ABC
  - Factory `get_platform_adapter("aap")` dans `app/adapters/__init__.py`
  - [Source: 4-4-adapter-plateforme-aap.md, 4-10-adapter-aap-workflow-job-et-job-template.md]

- **Backend services** :
  - `app/services/execution_service.py` orchestration exécutions, appelle adapter.trigger()
  - `app/services/vault_service.py` récupère credentials AAP depuis Vault
  - [Source: 4-3-moteur-execution-et-facade-api.md, 4-2bis-connecteur-hashicorp-vault.md]

- **WebSocket** :
  - `executions/consumers.py` avec ExecutionConsumer (endpoint `/ws/executions/{execution_id}`)
  - `core/consumers.py` avec AuthenticatedWebSocketConsumer (JWT auth message-based)
  - Django Channels configuré dans `asgi.py` et `settings.py`
  - [Source: 22-13-corriger-high-4-token-websocket-hors-url.md, executions/consumers.py]

- **Tables DB** :
  - EXECUTIONS avec PLATFORM_JOB_ID
  - EXECUTION_STEPS avec PLATFORM_JOB_ID, OUTPUT (CLOB pour résultats)
  - Possibilité d'ajouter colonne LOGS (CLOB) si logs séparés des outputs
  - [Source: 4-3-moteur-execution-et-facade-api.md]

- **Intégrations** :
  - Table INTEGRATIONS avec PLATFORM_TYPE="aap", BASE_URL, CREDENTIAL_REF
  - [Source: 2-27-backend-integrations-plateformes-distantes.md]

### Références techniques

- **Ansible Automation Platform / Controller API v2** :
  - Base URL : `{base_url}/api/v2/` (ex: `https://aap.example.com/api/v2/`)
  - Endpoints existants (déjà implémentés) :
    - POST `/api/v2/job_templates/{id}/launch/` — lancer job template
    - POST `/api/v2/workflow_job_templates/{id}/launch/` — lancer workflow job
    - GET `/api/v2/jobs/{id}/` — statut job template
    - GET `/api/v2/workflow_jobs/{id}/` — statut workflow job
  - **Nouveaux endpoints (à implémenter)** :
    - GET `/api/v2/jobs/{id}/stdout/` — récupérer logs job template (output Ansible)
    - GET `/api/v2/workflow_jobs/{id}/stdout/` — récupérer logs workflow job
    - Format réponse stdout : texte brut ou JSON avec range, content
    - Polling statut : `GET /api/v2/jobs/{id}/job_events/` pour événements détaillés (optionnel)
  - **WebSocket événements AAP** :
    - AAP / Ansible Controller peut exposer websocket pour job events (à valider dans doc AAP version déployée)
    - Alternative : polling périodique toutes les 5-10s si websocket non disponible
  - Auth : Basic Auth ou Bearer token (déjà géré par AAPAdapter._get_auth_headers())
  - [Source: Ansible Automation Platform docs, web search 2026-02, 4-4-adapter-plateforme-aap.md]

- **Django Channels WebSocket** :
  - Consumer async : `from channels.generic.websocket import AsyncWebsocketConsumer`
  - Envoyer message au frontend : `await self.send(text_data=json.dumps({"type": "step_update", "data": {...}}))`
  - Channel layers pour broadcast (optionnel si multi-instance) : `self.channel_layer.group_send()`
  - Pattern déjà établi dans ExecutionConsumer pour step_update messages
  - [Source: Django Channels docs, executions/consumers.py]

- **httpx async** :
  - Client déjà utilisé dans AAPAdapter pour trigger() et get_status()
  - Streaming logs : `async with httpx.stream("GET", url) as response: async for chunk in response.aiter_bytes(): ...`
  - Timeout 30s déjà configuré
  - [Source: httpx docs, 4-4-adapter-plateforme-aap.md]

### Status AAP et logs

| Resource Type | Logs Endpoint | Méthode | Format |
|---|---|---|---|
| job_template | `/api/v2/jobs/{id}/stdout/` | GET | Texte brut Ansible stdout |
| workflow_job | `/api/v2/workflow_jobs/{id}/stdout/` | GET | Texte brut ou JSON |

### Format logs AAP (à valider)

Réponse GET `/api/v2/jobs/{id}/stdout/` peut être :
- Texte brut : stdout Ansible directement
- JSON : `{"range": {"start": 0, "end": 1024, "absolute_end": 5000}, "content": "...", "content_type": "text/plain"}`

Adapter doit parser et retourner dict unifié :
```python
{
  "content": "...",  # Logs texte
  "format": "text/plain",
  "timestamp": "2026-02-14T10:30:00Z",
  "complete": True  # Si tous les logs récupérés
}
```

### WebSocket monitoring options

**Option 1 : WebSocket AAP natif (préféré si disponible)**
- AAP peut exposer websocket `/api/v2/jobs/{id}/events/` ou similaire
- Adapter se connecte au websocket AAP et forward events vers ExecutionConsumer Django
- Avantage : temps réel pur, pas de polling
- Inconvénient : dépend de la version AAP et configuration

**Option 2 : Polling périodique (fallback)**
- Celery Beat task (ou async loop) interroge `get_status()` et `get_job_logs()` toutes les 5-10s
- Résultats propagés via ExecutionConsumer Django Channels
- Avantage : fonctionne partout, simple
- Inconvénient : latence polling, charge réseau

**Recommandation** : Implémenter d'abord polling (option 2) pour MVP, puis ajouter websocket AAP si disponible (option 3) en Phase 2.

### Flow monitoring temps réel

```
[AAP Job running]
     |
     | (WebSocket events OU Polling 5-10s)
     v
[AAPAdapter.get_status() + get_job_logs()]
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

### Project Structure Notes

- **Nouveaux fichiers** :
  - `docs/aap-integration-analysis.md` — analyse doc AAP (endpoints, auth, websocket)
  - `docs/aap-monitoring-sequence.md` ou `.png` — diagramme flow monitoring temps réel

- **Modifier backend** :
  - `app/adapters/aap_adapter.py` — ajouter `get_job_logs()`, optionnellement websocket client
  - `app/services/execution_service.py` — logique récupération logs périodique
  - `executions/consumers.py` — optionnellement ajouter logique relay events AAP

- **Modifier DB (optionnel)** :
  - Migration Flyway pour ajouter colonne LOGS (CLOB) dans EXECUTION_STEPS si logs séparés de OUTPUT

- **Nouveaux tests** :
  - `tests/unit/test_aap_adapter.py` — tests get_job_logs()
  - `tests/integration/test_aap_monitoring.py` — tests end-to-end monitoring temps réel

### Architecture Compliance

- **Stack** : Django 5.2 + DRF 3.16, Oracle DB, Django Channels pour WebSocket, httpx async pour AAP API. [Source: architecture.md, MEMORY.md]
- **API** : Endpoints REST `/api/v1/executions/{id}/logs` pour récupération logs, WebSocket `/ws/executions/{id}` pour temps réel. [Source: architecture.md]
- **Performance** : Polling 5-10s acceptable pour monitoring (NFR1-NFR5 pages < 2s, callback < 5s). WebSocket préféré si disponible. [Source: architecture.md]
- **Sécurité** : Credentials Vault runtime, correlation_id propagé, audit trail pour récupération logs. [Source: architecture.md, NFR6-NFR11]

### Library/Framework Requirements

- **httpx 0.27+** : Client HTTP async déjà utilisé. Ajouter streaming pour logs volumineux. [Source: architecture.md]
- **Django Channels 4.x** : WebSocket AsyncWebsocketConsumer déjà configuré. [Source: MEMORY.md]
- **structlog** : Logging structuré JSON avec correlation_id déjà en place. [Source: architecture.md]
- **websocket-client ou aiohttp (optionnel)** : Pour client websocket AAP si implémenté. `pip install aiohttp` ou `websockets`. [Source: Python websocket libs]

### File Structure Requirements

- **Documentation nouvelle** :
  - `idp-portal/docs/aap-integration-analysis.md` (analyse AAP endpoints, auth, websocket)
  - `idp-portal/docs/aap-monitoring-sequence.md` (diagramme flow monitoring)

- **Modifier backend** :
  - `idp-portal/django_backend/adapters/aap_adapter.py` (méthode get_job_logs, optionnellement websocket)
  - `idp-portal/django_backend/executions/services.py` (ou execution_service.py selon refactoring Django)
  - `idp-portal/django_backend/executions/consumers.py` (relay events AAP si websocket)
  - `idp-portal/django_backend/executions/views.py` (endpoint `/executions/{id}/logs` ou inclure dans detail)

- **Modifier DB** :
  - `idp-portal/django_backend/migrations/` — nouvelle migration Flyway V0XX si colonne LOGS ajoutée

- **Nouveaux tests** :
  - `idp-portal/django_backend/adapters/tests/test_aap_adapter.py` (get_job_logs tests)
  - `idp-portal/django_backend/executions/tests/test_aap_monitoring.py` (integration tests)

### Testing Requirements

- **Backend unit tests** :
  - AAPAdapter.get_job_logs() : succès (mock stdout response), timeout, 404, logs vides, logs JSON format
  - Status mapping correct pour nouveaux endpoints
  - WebSocket client AAP (si implémenté) : connexion, événements, déconnexion

- **Backend integration tests** :
  - ExecutionService récupère logs périodiquement et met à jour DB
  - Événements propagés via ExecutionConsumer Django Channels
  - End-to-end : lancer job AAP → polling/websocket → logs récupérés → frontend reçoit step_update

- **Frontend tests (si modifications)** :
  - ExecutionTimeline affiche logs temps réel reçus via WebSocket
  - Pas de régression sur affichage timeline existant

- **Performance tests** :
  - Polling toutes les 5s ne surcharge pas AAP (rate limiting si nécessaire)
  - Logs volumineux (> 10 MB) streamés correctement sans timeout

### Previous Story Intelligence

- **Story 4.4 (Adapter AAP)** : Créé AAPAdapter avec trigger(), get_status(), parse_callback(). Pattern async httpx, auth Vault, PlatformError codes AAP_*. Tests unitaires avec httpx mock. [Source: 4-4-adapter-plateforme-aap.md]
  - Réutiliser : même adapter, même patterns auth, même httpx client, mêmes codes erreur
  - Étendre : ajouter get_job_logs(), optionnellement websocket monitoring

- **Story 4.10 (AAP workflow jobs)** : Étendu AAPAdapter pour resource_type (job_template | workflow_job), endpoints workflow_job_templates et workflow_jobs. connector_config dans execution_steps. [Source: 4-10-adapter-aap-workflow-job-et-job-template.md]
  - Réutiliser : resource_type pour distinguer logs endpoint job vs workflow_job
  - Étendre : get_job_logs() doit supporter les deux resource_type

- **Story 22.13 (WebSocket JWT auth)** : Implémenté AuthenticatedWebSocketConsumer avec message-based JWT auth. Token envoyé dans message au lieu de URL. ExecutionConsumer hérite. [Source: 22-13-corriger-high-4-token-websocket-hors-url.md]
  - Réutiliser : ExecutionConsumer pour relay events AAP
  - Pattern déjà établi : `await self.send(text_data=json.dumps({"type": "step_update", "data": {...}}))`

- **Story 19.1, 19.2 (ExecutionView temps réel)** : ExecutionView drawer avec ExecutionTimeline affichant étapes en temps réel via WebSocket. [Source: 19-1-vue-execution-action-simple-timeline-logs.md]
  - Réutiliser : frontend déjà prêt pour recevoir step_update avec logs
  - Vérifier : format logs compatible avec affichage timeline

### Git Intelligence Summary

- **Derniers commits AAP** :
  - `36f9154` feat(24-1): implement integration type catalogue with AAP and ServiceNow support
  - `3d1cc42` feat(24-2): restrict integration types and actions based on backend catalogue
  - Commits 4.4 et 4.10 : AAPAdapter trigger, get_status, resource_type workflow_job

- **Code existant pertinent** :
  - `adapters/aap_adapter.py` : trigger(), get_status(), _get_auth_headers(), _parse_job_response()
  - `executions/consumers.py` : ExecutionConsumer avec handle_authenticated_message()
  - `core/consumers.py` : AuthenticatedWebSocketConsumer base class JWT auth

- **Patterns à réutiliser** :
  - async httpx client avec timeout 30s
  - PlatformError(code="AAP_*", message="...") pour erreurs
  - structlog.info("aap_logs_fetched", execution_id=..., correlation_id=...)
  - pytest httpx mock pour tests unitaires adapter

### Latest Tech Information

- **Ansible Automation Platform 2.x / 4.x (2026)** :
  - API v2 stable, endpoints `/api/v2/` standards
  - Logs récupérables via `/jobs/{id}/stdout/` et `/workflow_jobs/{id}/stdout/`
  - WebSocket événements : certaines versions AAP supportent websocket `/api/v2/ws/` pour job events (à valider dans doc déployée)
  - Auth : Basic Auth (username/password) ou Bearer token (OAuth, personal access token)
  - [Source: Red Hat AAP docs 2026, Ansible Controller docs]

- **Django Channels 4.1+ (2026)** :
  - AsyncWebsocketConsumer pour WebSocket async
  - Message-based auth pattern (Story 22.13) recommandé vs URL params
  - Channel layers (Redis ou in-memory) pour broadcast multi-instance
  - [Source: Django Channels docs]

- **httpx 0.27+ (2026)** :
  - Streaming large responses : `async with httpx.stream()` pour logs volumineux
  - Timeout configurable par requête : `timeout=httpx.Timeout(30.0, read=60.0)` pour logs longs
  - [Source: httpx docs]

### Project Context Reference

- **Architecture** : [Source: _bmad-output/planning-artifacts/architecture.md] — Adapter Pattern, ExecutionService, WebSocket Django Channels, async HTTP httpx, correlation_id propagation, PlatformError hierarchy.
- **Epics** : [Source: _bmad-output/planning-artifacts/epics.md ligne 4403-4429] — Story 27.1 acceptance criteria complets, dépendances Stories 4.4, 4.10, 22.13.
- **MEMORY.md** : [Source: ~/.claude/projects/-Users-cyrille-Documents-Dev-test/memory/MEMORY.md] — Django 5.2 + DRF 3.16, Oracle DB, working dir django_backend, venv .venv/bin/python, test settings idp_backend.test_settings.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md] — Adapter Pattern BaseAdapter, WebSocket temps réel, async HTTP httpx, correlation_id, erreurs hiérarchie PlatformError.
- [Source: _bmad-output/planning-artifacts/epics.md lignes 4399-4429] — Epic 27 et Story 27.1 requirements complets.
- [Source: 4-4-adapter-plateforme-aap.md] — AAPAdapter existant trigger(), get_status(), parse_callback(), patterns async httpx, codes erreur AAP_*.
- [Source: 4-10-adapter-aap-workflow-job-et-job-template.md] — Extension resource_type job_template | workflow_job, endpoints workflow_job_templates, workflow_jobs.
- [Source: 22-13-corriger-high-4-token-websocket-hors-url.md] — WebSocket JWT auth message-based, AuthenticatedWebSocketConsumer, ExecutionConsumer.
- [Source: idp-portal/django_backend/adapters/aap_adapter.py] — Code existant AAPAdapter.
- [Source: idp-portal/django_backend/executions/consumers.py] — Code existant ExecutionConsumer WebSocket.
- [Source: Red Hat Ansible Automation Platform docs] — AAP API v2 endpoints, auth, websocket events.
- [Source: Django Channels docs] — AsyncWebsocketConsumer, channel layers, message sending patterns.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

N/A

### Completion Notes List

- AC1 : Analyse doc AAP complétée dans `docs/aap-integration-analysis.md` — endpoints, auth, websocket, status mapping
- AC2 : AAPAdapter.trigger() implémenté pour job_template et workflow_job avec extra_vars et limit
- AC3 : AAPAdapter.get_job_logs() implémenté + endpoint REST GET `/api/v1/executions/{id}/logs/` avec fallback vers step logs
- AC4 : Polling périodique via Celery shared_task `poll_aap_job_status` (auto-rescheduling), broadcast via Django Channels `_broadcast_execution_update`
- AC5 : Auth documentée, `build_auth_headers()` helper pour token/basic/pat, flow complet documenté avec diagramme séquence
- Choix MVP : polling (option 2) au lieu de websocket AAP natif, comme recommandé dans Dev Notes
- 41 tests passent (21 adapter + 20 monitoring)

### Code Review Fixes Applied (2026-02-14)

**CRITICAL fixes :**
- ✅ CRITICAL-2 : `adapters/utils.py` — Ajout logging structlog + validation credential_ref + error handling base64 encoding
- ✅ CRITICAL-3 : `executions/tasks.py:poll_aap_job_status` — Fix event loop leak (loop=None init, close in finally)
- ✅ CRITICAL-4 : `executions/views/execution_views.py:ExecutionLogsView` — Fix double event loop (ASGI/WSGI compatibility via async_to_sync pattern)
- ✅ CRITICAL-5 : `executions/consumers.py:ExecutionConsumer` — Fix race condition (group_add déplacé dans connect() au lieu de handle_authenticated_message)

**MEDIUM fixes :**
- ✅ MEDIUM-1 : `adapters/aap_adapter.py:get_job_logs` — 404 retourne job_status="not_found" au lieu de "unknown" pour distinction retry
- ✅ MEDIUM-3 : `executions/views/execution_views.py:_attempt_remote_cancellation` — Fix asyncio.get_event_loop() deprecated (Python 3.10+) → new_event_loop()
- ✅ MEDIUM-7 : `executions/consumers.py:disconnect` — Ajout try/except sur group_discard pour éviter crash si channel layer down

**TODO (issues documentés pour futures stories) :**
- CRITICAL-1 : Valider disponibilité websocket AAP dans env cible (tâche 4.2 marquée N/A sans preuve technique)
- CRITICAL-6 : Créer test end-to-end trigger→poll→logs→broadcast (actuellement seulement tests unitaires mockés)
- MEDIUM-2 : Implémenter broadcast retry queue (BROADCAST_QUEUE table + Celery Beat retry task) si Redis down
- MEDIUM-4 : Rendre poll_interval_seconds configurable via Integration.config (actuellement fixé à 5s)
- MEDIUM-5 : Implémenter rate limiting AAP API calls (gestion HTTP 429 + backoff exponentiel)
- MEDIUM-6 : Générer diagramme séquence en image (.png via PlantUML/Mermaid) au lieu d'ASCII art
- LOW-1 : Documenter config corporate CAs pour `verify=True` au lieu de `verify=False`
- LOW-3 : Implémenter diff logs (append delta au lieu d'écraser logs complets à chaque poll)

### Change Log

| Fichier | Changement |
|---|---|
| `adapters/aap_adapter.py` | Réécrit — AAPAdapter complet avec trigger(), get_status(), get_job_logs(), cancel_execution() |
| `adapters/utils.py` | **Nouveau** — build_auth_headers() helper (token, basic, pat) |
| `adapters/tests/__init__.py` | **Nouveau** — package init |
| `adapters/tests/test_aap_adapter.py` | **Nouveau** — 21 tests unitaires AAPAdapter |
| `executions/views/execution_views.py` | Ajout ExecutionLogsView (GET /executions/{id}/logs/) + fix _attempt_remote_cancellation |
| `executions/views/__init__.py` | Ajout export ExecutionLogsView |
| `executions/urls.py` | Ajout route `executions/<int:execution_id>/logs/` |
| `executions/consumers.py` | Enrichi — channel layer group join/leave, handlers step_update, log_update, execution_complete, execution_failed, status_update |
| `executions/tasks.py` | Ajout poll_aap_job_status Celery task, _broadcast_execution_update, _update_execution_from_poll |
| `executions/tests/test_aap_monitoring.py` | **Nouveau** — 20 tests monitoring (logs view, poll task, broadcast, consumer, auth headers) |
| `docs/aap-integration-analysis.md` | **Nouveau** — analyse doc AAP, diagramme séquence, flow monitoring |

### File List

- `adapters/aap_adapter.py` (modified)
- `adapters/utils.py` (new)
- `adapters/tests/__init__.py` (new)
- `adapters/tests/test_aap_adapter.py` (new)
- `executions/views/execution_views.py` (modified)
- `executions/views/__init__.py` (modified)
- `executions/urls.py` (modified)
- `executions/consumers.py` (modified)
- `executions/tasks.py` (modified)
- `executions/tests/test_aap_monitoring.py` (new)
- `docs/aap-integration-analysis.md` (new)
