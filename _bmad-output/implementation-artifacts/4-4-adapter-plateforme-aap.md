# Story 4.4: Adapter plateforme AAP (Ansible Automation Platform)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a système,
I want déclencher et suivre des exécutions sur AAP via un adapter dédié,
So that les actions basées AAP fonctionnent de bout en bout.

## Acceptance Criteria

1. **AC1 — Déclenchement via AAP API**
   **Given** une exécution cible la plateforme AAP (action.platform = "aap"),
   **When** le moteur d'exécution (Story 4.3) appelle `aap_adapter.trigger(parameters, credentials, correlation_id)`,
   **Then** l'adapter AAP envoie une requête POST vers l'API Tower AAP `/api/v2/job_templates/{id}/launch/` avec les extra_vars (parameters) et les credentials,
   **And** l'adapter retourne le platform_job_id (AAP job ID) en cas de succès,
   **And** FR18 est satisfaite.

2. **AC2 — Gestion erreur AAP indisponible**
   **Given** AAP est indisponible ou ne répond pas (timeout, erreur réseau),
   **When** le moteur tente de déclencher l'exécution via `aap_adapter.trigger()`,
   **Then** l'adapter lève une PlatformError avec code "AAP_UNAVAILABLE" et message explicite "Plateforme AAP indisponible",
   **And** l'EXECUTION_STEP passe en statut FAILED avec error_message (NFR17),
   **And** les autres exécutions ne sont pas impactées (NFR13).

3. **AC3 — Polling status job AAP**
   **Given** une exécution AAP a été déclenchée avec succès,
   **When** le moteur ou le système appelle `aap_adapter.get_status(platform_job_id)`,
   **Then** l'adapter interroge l'API Tower `/api/v2/jobs/{id}/` et retourne un dict avec status ("running" | "completed" | "failed" | "cancelled"), output (résultats job), error_message (si échec),
   **And** FR23 est satisfaite.

4. **AC4 — Parsing callback AAP**
   **Given** AAP envoie un callback webhook POST /api/v1/webhooks/aap/{execution_id} (lorsque le job se termine),
   **When** le backend appelle `aap_adapter.parse_callback(callback_data)`,
   **Then** l'adapter extrait et retourne platform_job_id, status, output, error_message depuis le payload AAP,
   **And** le callback est idempotent — un doublon ne corrompt pas l'état (NFR18),
   **And** FR23 est satisfaite.

5. **AC5 — Isolation et extensibilité**
   **And** l'AAPAdapter hérite de BaseAdapter (interface commune: trigger(), get_status(), parse_callback()),
   **And** l'AAPAdapter est enregistré dans le registre _ADAPTER_REGISTRY["aap"] via __init__.py,
   **And** l'ajout de l'adapter AAP ne modifie pas le moteur d'exécution (execution_service.py reste inchangé),
   **And** NFR22 est satisfaite (extensibilité sans refonte core).

## Tasks / Subtasks

- [x] Task 1 — Création AAPAdapter (AC: 1, 2, 5)
  - [x] 1.1 Créer `adapters/aap_adapter.py` : classe `AAPAdapter(BaseAdapter)` avec `__init__(platform_type, base_url)`. Injecter httpx.AsyncClient pour appels HTTP async.
  - [x] 1.2 Implémenter `async def trigger(parameters, credentials, correlation_id) -> str` : POST vers AAP `/api/v2/job_templates/{template_id}/launch/` avec headers auth (Basic ou Bearer selon credentials Vault), body extra_vars=parameters, timeout 30s. Retourner AAP job_id extrait de la réponse JSON. Loguer avec structlog : `logger.info("aap_trigger_started", template_id=..., correlation_id=...)`.
  - [x] 1.3 Gestion erreurs trigger : si AAP timeout/network error → catch httpx.TimeoutException / httpx.ConnectError → lever PlatformError(code="AAP_UNAVAILABLE", message="Plateforme AAP indisponible"). Si AAP retourne 400/401/403 → lever PlatformError(code="AAP_AUTH_ERROR", message="Authentification AAP échouée"). Si AAP retourne 404 → lever PlatformError(code="AAP_JOB_TEMPLATE_NOT_FOUND", message="Job template introuvable").
  - [x] 1.4 Extraction template_id : lire depuis parameters["job_template_id"] (fourni par l'action) OU déduire depuis integration.config JSON (si stocké dans INTEGRATIONS.CONFIG CLOB). Si template_id absent → lever ValueError("job_template_id requis pour AAP").

- [x] Task 2 — Implémentation get_status (AC: 3)
  - [x] 2.1 Implémenter `async def get_status(platform_job_id: str) -> dict` : GET vers AAP `/api/v2/jobs/{platform_job_id}/`. Mapper status AAP ("pending", "waiting", "running", "successful", "failed", "error", "canceled") vers status unifié ("running" | "completed" | "failed" | "cancelled"). Retourner dict : `{"status": ..., "output": job_results, "error_message": ...}`. Loguer avec structlog.
  - [x] 2.2 Gestion erreurs get_status : si AAP timeout/network → catch exception → retourner status "running" (assume job still in progress, retry later). Si AAP retourne 404 → lever PlatformError(code="AAP_JOB_NOT_FOUND", message="Job AAP introuvable").
  - [x] 2.3 Extraction output : lire AAP response JSON fields : status, result_traceback (si échec), job_explanation, artifacts (résultats Ansible). Mapper vers output dict pour EXECUTION_STEPS.OUTPUT CLOB.

- [x] Task 3 — Implémentation parse_callback (AC: 4)
  - [x] 3.1 Implémenter `async def parse_callback(callback_data: dict) -> dict` : extraire AAP webhook payload fields : job_id → platform_job_id, status → status mappé, result_traceback → error_message, artifacts → output. Retourner dict : `{"platform_job_id": ..., "status": ..., "output": ..., "error_message": ...}`.
  - [x] 3.2 Validation callback : si platform_job_id absent → lever PlatformError(code="AAP_INVALID_CALLBACK", message="Callback AAP invalide - job_id manquant"). Loguer callback reçu avec correlation_id si présent dans payload.
  - [x] 3.3 Idempotence : parse_callback doit être pure (pas d'état interne), le caller (webhooks.py endpoint) gère l'idempotence via EXECUTION_STEPS.PLATFORM_JOB_ID (update uniquement si status actuel != COMPLETED/FAILED).

- [x] Task 4 — Enregistrement adapter (AC: 5)
  - [x] 4.1 Modifier `adapters/__init__.py` : importer AAPAdapter, ajouter `"aap": AAPAdapter` dans _ADAPTER_REGISTRY. Pattern : `from app.adapters.aap_adapter import AAPAdapter`.
  - [x] 4.2 Modifier `adapters/__init__.py` : ajouter AAPAdapter dans __all__ pour export public.
  - [x] 4.3 Vérifier que `get_platform_adapter("aap", base_url)` retourne instance AAPAdapter.

- [x] Task 5 — Configuration et credentials (AC: 1)
  - [x] 5.1 AAP credentials depuis Vault : l'adapter reçoit credentials dict depuis vault_service.get_secret(integration.credential_ref). Format attendu : `{"username": "...", "password": "..."}` OU `{"token": "..."}` (Bearer token). Adapter détecte le type et configure httpx auth headers : Basic Auth (username/password) OU Bearer token.
  - [x] 5.2 AAP base_url : passé au constructeur via integration.base_url (depuis INTEGRATIONS.BASE_URL). Format : `https://aap.example.com`. Adapter construit URLs API : f"{self.base_url}/api/v2/job_templates/{template_id}/launch/".
  - [x] 5.3 Timeout et retry : trigger() et get_status() utilisent timeout 30s (httpx.Timeout(30.0)). Pas de retry automatique dans l'adapter (le moteur d'exécution gère retry si besoin). Si timeout atteint → lever PlatformError.

- [x] Task 6 — Tests unitaires (AC: tous)
  - [x] 6.1 Tests AAPAdapter trigger : succès (mock httpx POST retourne job_id), AAP timeout (lever PlatformError AAP_UNAVAILABLE), AAP 401 (lever PlatformError AAP_AUTH_ERROR), AAP 404 (lever PlatformError AAP_JOB_TEMPLATE_NOT_FOUND), template_id manquant (lever ValueError). Mock httpx.AsyncClient avec pytest-httpx ou respx.
  - [x] 6.2 Tests AAPAdapter get_status : succès (mock httpx GET retourne status completed), AAP timeout (retourner running), AAP 404 (lever PlatformError AAP_JOB_NOT_FOUND), status mapping (AAP "successful" → "completed", AAP "failed" → "failed", AAP "running" → "running").
  - [x] 6.3 Tests AAPAdapter parse_callback : succès (extraire platform_job_id, status, output), callback invalide (platform_job_id manquant → lever PlatformError), status mapping correct.
  - [x] 6.4 Tests factory get_platform_adapter("aap") : retourne instance AAPAdapter, passe base_url correctement.
  - [x] 6.5 Tests intégration (optionnel) : flow complet execution_service → aap_adapter.trigger → mock AAP API → parse_callback → update EXECUTION_STEPS. Utiliser MockAdapter ou real AAPAdapter avec httpx mock.

## Dev Notes

### Contexte métier

- **FR18** : Le système déclenche l'exécution sur la plateforme cible (AAP, GitHub Actions, Azure DevOps, Terraform) via une API. Cette story implémente l'adapter AAP pour FR18.
- **FR23** : Le système affiche le statut de chaque étape en temps réel via WebSocket. L'adapter AAP fournit get_status() pour polling et parse_callback() pour webhooks temps réel.
- **NFR13** : L'échec d'une exécution n'impacte pas les autres. L'adapter AAP lève des PlatformError isolées, gérées par execution_service.
- **NFR17** : En cas d'indisponibilité de plateforme externe, un message explicite est affiché. L'adapter AAP lève PlatformError avec codes et messages clairs.
- **NFR18** : Les callbacks webhooks sont idempotents. L'adapter parse_callback() est pure, le caller gère l'idempotence.
- **NFR22** : Le système permet d'ajouter de nouvelles plateformes sans modifier le code d'exécution. L'adapter AAP respecte le Strategy Pattern, enregistré dans _ADAPTER_REGISTRY sans toucher execution_service.
- **Epic 4** : DBA exécute une action de bout en bout via le wizard et suit la progression étape par étape en temps réel via la timeline. L'adapter AAP est le premier adapter plateforme réel (après MockAdapter), permettant les exécutions AAP end-to-end.

### Patterns à respecter

- **Strategy Pattern** : AAPAdapter implémente BaseAdapter avec trigger(), get_status(), parse_callback(). Factory get_platform_adapter("aap") retourne instance AAPAdapter. Pattern établi dans Story 4.3, architecture.md. [Source: architecture.md, base_adapter.py]
- **Service Pattern** : ExecutionService orchestre l'exécution, appelle adapter.trigger() pour l'étape platform. L'adapter ne connaît pas execution_service, communication unidirectionnelle. [Source: execution_service.py, architecture.md]
- **Error Hierarchy** : PlatformError(IdpError) avec code et message. Codes AAP : AAP_UNAVAILABLE, AAP_AUTH_ERROR, AAP_JOB_TEMPLATE_NOT_FOUND, AAP_JOB_NOT_FOUND, AAP_INVALID_CALLBACK. Handler global dans main.py convertit en JSON HTTP 502. [Source: core/exceptions.py, architecture.md]
- **Logging** : structlog JSON avec correlation_id propagé. `logger.info("aap_trigger_started", template_id=..., correlation_id=...)`, `logger.error("aap_trigger_failed", error=...)`. [Source: architecture.md, execution_service.py]
- **Async HTTP** : httpx.AsyncClient pour appels AAP API. Timeout 30s, async/await. Pattern établi dans inventory_service.py (Story 4.2). [Source: architecture.md, inventory_service.py]

### Ce qui existe déjà

- **Backend** : base_adapter.py (Story 4.3) avec BaseAdapter ABC, MockAdapter implémentation de référence. execution_service.py (Story 4.3) avec orchestration, appel adapter.trigger() pour étape platform. vault_service.py (Story 4.2bis) récupère credentials depuis Vault. [Source: Story 4.3, 4.2bis]
- **Tables** : EXECUTIONS (Story 4.3) avec PLATFORM_JOB_ID, EXECUTION_STEPS avec PLATFORM_JOB_ID. INTEGRATIONS (Story 2.27) avec PLATFORM_TYPE="aap", BASE_URL, CREDENTIAL_REF (chemin Vault). [Source: Story 4.3, 2.27]
- **Factory** : get_platform_adapter(platform_type, base_url) dans adapters/__init__.py, _ADAPTER_REGISTRY dict. register_adapter() pour extensibilité. [Source: adapters/__init__.py]
- **Erreurs** : PlatformError(IdpError) dans core/exceptions.py avec code, message, details. Handler global dans main.py. [Source: core/exceptions.py, main.py]
- **Tests** : test_base_adapter.py (Story 4.3) avec patterns tests adapter (async mock, pytest.mark.asyncio, ABC tests). [Source: tests/unit/test_base_adapter.py]

### Références techniques

- **Ansible Tower API** : AAP Tower REST API `/api/v2/`. Endpoints : POST `/api/v2/job_templates/{id}/launch/` (déclencher job), GET `/api/v2/jobs/{id}/` (status job). Authentification : Basic Auth (username/password) OU Bearer token. Body launch : `{"extra_vars": {...}}`. Response launch : `{"id": job_id, ...}`. Status job : "pending", "waiting", "running", "successful", "failed", "error", "canceled". [Source: Ansible Tower docs, web search 2026-01]
- **httpx async** : `async with httpx.AsyncClient(timeout=30.0) as client: response = await client.post(url, json=body, auth=..., headers=...)`. Auth : `auth=httpx.BasicAuth(username, password)` OU `headers={"Authorization": f"Bearer {token}"}`. Exceptions : httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError. [Source: httpx docs]
- **Strategy Pattern ABC** : `from abc import ABC, abstractmethod`. Classe AAPAdapter(BaseAdapter) hérite BaseAdapter (ABC). Implémenter toutes les méthodes abstraites (trigger, get_status, parse_callback). [Source: Python ABC docs, base_adapter.py]
- **structlog correlation ID** : `structlog.contextvars.bind_contextvars(correlation_id=correlation_id)` lie le correlation_id au contexte async. Tous les logs suivants incluent automatiquement correlation_id. [Source: structlog docs, execution_service.py]
- **pytest-httpx** : Mock httpx async client : `pip install pytest-httpx`, `def test_trigger(httpx_mock): httpx_mock.add_response(json={"id": 123})`. Alternative : `respx` library. [Source: pytest-httpx docs]

### Status AAP mapping

| AAP Status | Adapter Status | Description |
|---|---|---|
| "pending" | "running" | Job en attente dans la queue AAP |
| "waiting" | "running" | Job en attente de ressources/approbation |
| "running" | "running" | Job en cours d'exécution |
| "successful" | "completed" | Job terminé avec succès |
| "failed" | "failed" | Job échoué (playbook error) |
| "error" | "failed" | Job échoué (erreur système AAP) |
| "canceled" | "cancelled" | Job annulé par utilisateur |

### Credentials AAP format

L'adapter reçoit credentials depuis Vault via vault_service.get_secret(integration.credential_ref). Formats supportés :

**Format 1 : Basic Auth (username/password)**
```json
{
  "username": "tower_user",
  "password": "secret_password"
}
```
→ Adapter configure : `httpx.BasicAuth(username, password)`

**Format 2 : Bearer Token**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
→ Adapter configure : `headers={"Authorization": f"Bearer {token}"}`

L'adapter détecte automatiquement le format : si "token" présent → Bearer, sinon → Basic Auth.

### AAP API request examples

**Déclencher job template :**
```
POST https://aap.example.com/api/v2/job_templates/42/launch/
Headers:
  Content-Type: application/json
  Authorization: Basic dXNlcjpwYXNz  (ou Bearer token)
Body:
{
  "extra_vars": {
    "target_host": "db-prod-01",
    "operation": "backup"
  }
}
Response 201:
{
  "id": 12345,
  "type": "job",
  "url": "/api/v2/jobs/12345/",
  "status": "pending",
  ...
}
```

**Récupérer status job :**
```
GET https://aap.example.com/api/v2/jobs/12345/
Headers:
  Authorization: Basic dXNlcjpwYXNz
Response 200:
{
  "id": 12345,
  "status": "successful",
  "result_traceback": "",
  "job_explanation": "",
  "artifacts": {
    "backup_file": "/backups/db-prod-01-2026-01-29.tar.gz"
  },
  ...
}
```

### Project Structure Notes

- **Nouveau backend** : `adapters/aap_adapter.py` (nouvelle classe AAPAdapter).
- **Modifier backend** : `adapters/__init__.py` (ajouter AAPAdapter dans _ADAPTER_REGISTRY et __all__).
- **Nouveau tests** : `tests/unit/test_aap_adapter.py` (tests unitaires AAPAdapter).

### Architecture Compliance

- **Stack** : FastAPI 0.115+, Python 3.12+, httpx async, structlog, ABC Strategy Pattern. [Source: architecture.md]
- **API** : L'adapter n'expose pas d'endpoint, il est utilisé par execution_service. Webhooks AAP reçus via POST /api/v1/webhooks/aap/{execution_id} (endpoint à créer dans api/v1/webhooks.py ou réutiliser existant). [Source: architecture.md]
- **Performance** : Timeout 30s pour appels AAP (NFR19 ServiceNow tolerance 30s, même pattern). Pas de retry dans adapter (le moteur gère). [Source: architecture.md, NFR19]
- **Sécurité** : Credentials Vault jamais persistés, uniquement en mémoire pour appel AAP. Correlation_id propagé pour audit trail. [Source: architecture.md, NFR7]

### Library/Framework Requirements

- **httpx 0.27+** : Client HTTP async pour appels AAP API. `pip install httpx`. Async context manager, timeout, auth, exceptions. [Source: architecture.md]
- **structlog** : Logging structuré JSON avec correlation_id. Déjà installé (Story 4.3). [Source: architecture.md]
- **pytest-httpx OU respx** : Mock httpx client pour tests. `pip install pytest-httpx` OU `pip install respx`. [Source: pytest ecosystem]
- **Python 3.12+** : Type hints modernes (dict[str, Any], str | None). [Source: architecture.md]

### File Structure Requirements

- **Nouveau backend** : `app/adapters/aap_adapter.py` (classe AAPAdapter).
- **Modifier backend** : `app/adapters/__init__.py` (import AAPAdapter, ajouter à _ADAPTER_REGISTRY et __all__).
- **Nouveau tests** : `tests/unit/test_aap_adapter.py` (tests unitaires AAPAdapter trigger, get_status, parse_callback, factory).

### Testing Requirements

- **Backend** : Tests unitaires aap_adapter (trigger succès/timeout/auth error/404, get_status succès/timeout/404, parse_callback succès/invalide, factory registration). Pattern mock httpx avec pytest-httpx ou respx. Réutiliser patterns test_base_adapter.py (pytest.mark.asyncio, ABC tests, factory tests). [Source: tests/unit/test_base_adapter.py, pytest-httpx docs]
- **Patterns** : Mock httpx.AsyncClient avec `httpx_mock.add_response(json=...)`, test async avec `@pytest.mark.asyncio async def test_...()`. Test erreurs avec `pytest.raises(PlatformError) as exc_info: ...`, vérifier exc_info.value.code. [Source: pytest patterns]

### Previous Story Intelligence

- **Story 4.3 (Moteur d'exécution)** : Créé BaseAdapter interface, execution_service orchestration, factory get_platform_adapter(), MockAdapter implémentation de référence. Le moteur appelle adapter.trigger() pour étape platform, stocke platform_job_id dans EXECUTION_STEPS. Gestion erreurs VaultError, PlatformError. [Source: 4-3-moteur-execution-et-facade-api.md]
- **Story 4.2bis (Vault)** : vault_service.py avec get_secret(credential_ref), VaultError. Les credentials AAP sont récupérés via Vault runtime. [Source: 4-2bis-connecteur-hashicorp-vault.md]
- **Story 2.27 (Intégrations)** : Table INTEGRATIONS avec PLATFORM_TYPE="aap", BASE_URL (AAP Tower URL), CREDENTIAL_REF (chemin Vault pour auth AAP). integration_repository.py SQL brut. [Source: 2-27-backend-integrations-plateformes-distantes.md]

### Git Intelligence Summary

- **Derniers commits** : Pattern adapter strategy établi (BaseAdapter ABC, MockAdapter). Pattern service async (execution_service, inventory_service, vault_service). Pattern injection Depends. Hiérarchie erreurs IdpError (VaultError, PlatformError). Réutiliser mêmes patterns pour AAPAdapter.
- **Code existant** : base_adapter.py avec BaseAdapter ABC, trigger(), get_status(), parse_callback(). MockAdapter implémentation de référence montrant la structure attendue. execution_service.py appelle get_platform_adapter() et adapter.trigger(). Factory get_platform_adapter() dans __init__.py avec _ADAPTER_REGISTRY. Tests test_base_adapter.py avec patterns async mock.

### Latest Tech Information

- **Ansible Tower API v2** : Ansible Automation Platform (AAP) expose Tower API REST /api/v2/ pour déclencher jobs et récupérer status. Launch job : POST /api/v2/job_templates/{id}/launch/ avec extra_vars. Status job : GET /api/v2/jobs/{id}/. Authentification Basic Auth ou Bearer token. [Source: Ansible Tower docs, web search 2026-01]
- **httpx 0.27.x** : Client HTTP async moderne pour Python. Remplace requests (sync). Async context manager, timeout, auth (BasicAuth, Bearer), exceptions (TimeoutException, ConnectError). API similaire à requests mais async/await. [Source: httpx docs]
- **pytest-httpx** : Plugin pytest pour mock httpx.AsyncClient. `httpx_mock.add_response(json=...)` mock réponse HTTP. Compatible pytest async avec pytest-asyncio. [Source: pytest-httpx docs]
- **Strategy Pattern Python** : ABC (Abstract Base Class) avec @abstractmethod. Subclass doit implémenter toutes les méthodes abstraites. Factory function retourne instance de la bonne subclass. Pattern recommandé pour extensibilité plugins. [Source: Python ABC docs]

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — Strategy Pattern adapters (BaseAdapter, factory get_platform_adapter), Service Pattern orchestration (execution_service), async HTTP (httpx), correlation_id propagation, erreurs hiérarchie IdpError/PlatformError.
- **PRD** : [Source: planning-artifacts/prd.md] — FR18 (trigger plateforme API), FR23 (suivi temps réel status), NFR13 (isolation exécutions), NFR17 (erreur plateforme explicite), NFR18 (callbacks idempotents), NFR22 (extensibilité plugins).
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.4 acceptance criteria complets, dépendances Story 4.3 (moteur exécution, BaseAdapter), 4.2bis (Vault credentials), 2.27 (intégrations plateformes).

### References

- [Source: planning-artifacts/architecture.md] — Strategy Pattern BaseAdapter, Service Pattern, async HTTP httpx, correlation_id, erreurs hiérarchie.
- [Source: planning-artifacts/epics.md] — Story 4.4 requirements complets, dépendances 4.3/4.2bis/2.27.
- [Source: 4-3-moteur-execution-et-facade-api.md] — BaseAdapter interface, execution_service orchestration, MockAdapter référence.
- [Source: idp-portal/backend/app/adapters/base_adapter.py] — BaseAdapter ABC trigger(), get_status(), parse_callback(), MockAdapter implémentation.
- [Source: idp-portal/backend/app/adapters/__init__.py] — Factory get_platform_adapter(), _ADAPTER_REGISTRY, register_adapter().
- [Source: idp-portal/backend/app/services/execution_service.py] — Pattern service async, appel adapter.trigger(), gestion PlatformError.
- [Source: idp-portal/backend/app/core/exceptions.py] — PlatformError, IdpError hierarchy.
- [Source: idp-portal/backend/tests/unit/test_base_adapter.py] — Patterns tests adapter async mock pytest.
- [Source: Ansible Tower API docs] — AAP Tower REST API /api/v2/ job templates launch, status.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 33 AAPAdapter tests pass (31 + 2 added in code-review)
- All 47 adapter tests (base + aap) pass
- 726/740 backend tests pass (14 pre-existing failures unrelated to this story)

### Completion Notes List

- ✅ Task 1: Created AAPAdapter class inheriting BaseAdapter with trigger(), get_status(), parse_callback() methods
- ✅ Task 2: Implemented get_status() with AAP status mapping (pending/waiting/running → running, successful → completed, failed/error → failed, canceled → cancelled)
- ✅ Task 3: Implemented parse_callback() as pure function for idempotency (NFR18)
- ✅ Task 4: Registered AAPAdapter in _ADAPTER_REGISTRY["aap"] and __all__ exports
- ✅ Task 5: Implemented dual auth support (Basic Auth username/password OR Bearer token), 30s timeout
- ✅ Task 6: Created comprehensive test suite (31 tests covering all ACs)
- ✅ Code review 2026-01-29: 3 MEDIUM issues fixed — (1) Task 1.3: 400 → AAP_AUTH_ERROR, (2) Task 2.2: get_status() catches ConnectError and returns "running", (3) Added test_trigger_400_raises_auth_error and test_get_status_connect_error_returns_running. 33/33 tests pass.

### File List

**New files:**
- `idp-portal/backend/app/adapters/aap_adapter.py` — AAPAdapter implementation
- `idp-portal/backend/tests/unit/test_aap_adapter.py` — 31 unit tests

**Modified files:**
- `idp-portal/backend/app/adapters/__init__.py` — Added AAPAdapter import, registry entry, __all__ export
