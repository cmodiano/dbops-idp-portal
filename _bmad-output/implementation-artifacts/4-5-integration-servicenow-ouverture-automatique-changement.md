# Story 4.5: Intégration ServiceNow — ouverture automatique de changement

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a système,
I want ouvrir automatiquement un changement ServiceNow lorsqu'une étape de l'action le requiert,
So that la conformité du changement est assurée sans intervention manuelle.

## Acceptance Criteria

1. **AC1 — Création changement ServiceNow conditionnel**
   **Given** une action définit une étape "ouverture changement ServiceNow" pour l'environnement Production (type="servicenow" dans EXECUTION_STEPS),
   **When** l'exécution atteint cette étape et le moteur d'exécution (Story 4.3) appelle `servicenow_service.create_change(execution_data, environment)`,
   **Then** le service ServiceNow envoie une requête POST vers l'API ServiceNow `/api/now/table/change_request` avec les métadonnées (action name, environment, parameters, user, correlation_id),
   **And** le servicenow_change_id (sys_id du changement créé) est retourné et stocké dans EXECUTIONS.SERVICENOW_CHANGE_ID et EXECUTION_STEPS.OUTPUT,
   **And** FR16 est satisfaite.

2. **AC2 — Changement pré-approuvé (automated change model)**
   **Given** l'action spécifie un modèle de changement pré-approuvé (change_model_code dans ACTION_CATALOG),
   **When** le changement ServiceNow est créé avec ce modèle,
   **Then** ServiceNow retourne status "Approved" immédiatement (changement pré-approuvé CAB),
   **And** l'EXECUTION_STEP passe en statut "completed" immédiatement,
   **And** l'exécution continue à l'étape suivante sans attente,
   **And** le change_number (ex: CHG0030123) est affiché dans la timeline.

3. **AC3 — Changement nécessitant approbation CAB**
   **Given** l'action ne spécifie pas de modèle pré-approuvé OU ServiceNow retourne status "Pending Approval",
   **When** le changement est en attente d'approbation,
   **Then** l'EXECUTION_STEP reste en statut "running" avec output "Approbation CAB en cours",
   **And** la timeline affiche badge "En attente approbation" avec le change_number cliquable (lien vers ServiceNow),
   **And** l'exécution est suspendue (pas d'étape suivante) jusqu'à callback ServiceNow ou polling détecte approbation.

4. **AC4 — Timeout et retry ServiceNow**
   **Given** l'API ServiceNow ne répond pas dans les 30 secondes (NFR19),
   **When** le timeout est atteint,
   **Then** le service tente un retry avec backoff exponentiel (1 tentative supplémentaire après 5s),
   **And** si le retry échoue → l'EXECUTION_STEP passe en statut "failed" avec error_message "ServiceNow timeout — changement non créé",
   **And** l'exécution globale passe en statut "failed",
   **And** FR16 et NFR19 sont satisfaites.

5. **AC5 — Isolation et traçabilité**
   **And** servicenow_service.py encapsule tous les appels ServiceNow (client REST httpx async),
   **And** les credentials ServiceNow sont récupérés via Vault runtime (credential_ref depuis INTEGRATIONS),
   **And** le correlation_id est propagé dans les appels ServiceNow (header X-Request-ID),
   **And** chaque appel ServiceNow est loggué avec structlog (correlation_id, execution_id, change_number),
   **And** les erreurs ServiceNow lèvent ServiceNowError(IdpError) avec code et message explicites.

## Tasks / Subtasks

- [ ] Task 1 — Service ServiceNow et client REST (AC: 1, 2, 4, 5)
  - [ ] 1.1 Créer `services/servicenow_service.py` : classe `ServiceNowService` avec méthode `async def create_change(execution_id, action_name, environment, parameters, user, correlation_id, change_model_code=None) -> dict`. Retourne `{"change_id": "sys_id", "change_number": "CHG0030123", "status": "approved" | "pending_approval"}`.
  - [ ] 1.2 Client HTTP httpx async : `httpx.AsyncClient(timeout=30.0)` pour appels ServiceNow. Endpoint POST `/api/now/table/change_request`. Headers : `{"Content-Type": "application/json", "Authorization": "Basic {base64(username:password)}", "X-Request-ID": correlation_id}`. Body changement : `{"short_description": f"[IDP] {action_name} - {environment}", "description": f"Execution automatique IDP - Correlation ID: {correlation_id}\nAction: {action_name}\nEnvironnement: {environment}\nParametres: {json.dumps(parameters)}\nUtilisateur: {user}", "requested_by": user, "assignment_group": "DBOPS", "category": "Database", "u_change_model": change_model_code, "u_correlation_id": correlation_id}`.
  - [ ] 1.3 Credentials Vault : injecter `vault_service` via Depends. Récupérer credentials ServiceNow via `vault_service.get_secret(integration.credential_ref)` où integration.platform_type="servicenow". Format credentials : `{"username": "...", "password": "..."}`. Encoder en Base64 pour Basic Auth.
  - [ ] 1.4 Parsing réponse ServiceNow : extraire `result.sys_id` → change_id, `result.number` → change_number, `result.approval` → status ("approved" si "approved", sinon "pending_approval"). Si champs absents → lever ServiceNowError(code="SERVICENOW_INVALID_RESPONSE", message="Réponse ServiceNow invalide").
  - [ ] 1.5 Timeout et retry : timeout 30s via `httpx.Timeout(30.0)`. Retry 1 fois avec backoff 5s : `await asyncio.sleep(5)` puis retry. Si timeout 2x → lever ServiceNowError(code="SERVICENOW_TIMEOUT", message="ServiceNow timeout — changement non créé"). Loguer avec structlog chaque tentative.

- [ ] Task 2 — Intégration dans le moteur d'exécution (AC: 1, 2, 3)
  - [ ] 2.1 Modifier `services/execution_service.py` (Story 4.3) : ajouter traitement étape type="servicenow". Méthode `async def _execute_servicenow_step(execution_id, step, action, environment, parameters, user, correlation_id)`.
  - [ ] 2.2 Logique étape ServiceNow : vérifier si action définit change_model_code (depuis ACTIONS_CATALOG.CHANGE_MODEL_CODE ou action config JSON). Appeler `servicenow_service.create_change(...)`. Si status "approved" → update step status "completed" + output `{"change_id": ..., "change_number": ..., "status": "approved"}`, continuer étapes suivantes. Si status "pending_approval" → update step status "running" + output `{"change_id": ..., "change_number": ..., "status": "pending_approval", "message": "Approbation CAB en cours"}`, suspendre exécution (ne pas passer à l'étape suivante).
  - [ ] 2.3 Stockage change_id : après création changement, update EXECUTIONS.SERVICENOW_CHANGE_ID via `execution_repository.update_execution(execution_id, servicenow_change_id=change_id)`. Ajouter colonne SERVICENOW_CHANGE_ID VARCHAR2(50) dans table EXECUTIONS si pas déjà existante (migration SQL).
  - [ ] 2.4 Gestion erreurs ServiceNow : si `servicenow_service.create_change()` lève ServiceNowError → catch → update step status "failed" + error_message, update execution status "failed", loguer error avec structlog, skip remaining steps.

- [ ] Task 3 — Migration base de données (AC: 2)
  - [ ] 3.1 Créer migration SQL (si colonne SERVICENOW_CHANGE_ID pas déjà présente dans EXECUTIONS) : `V026__add_servicenow_change_id.sql`. Ajouter colonne SERVICENOW_CHANGE_ID VARCHAR2(50) NULL dans EXECUTIONS. Index sur SERVICENOW_CHANGE_ID pour recherche.
  - [ ] 3.2 Modifier ACTIONS_CATALOG (si pas déjà fait) : ajouter colonne CHANGE_MODEL_CODE VARCHAR2(50) NULL pour stocker le code modèle changement pré-approuvé. Alternative : stocker dans ACTIONS_CATALOG.CONFIG CLOB JSON sous `"change_model_code": "..."`.
  - [ ] 3.3 Exécuter migration via `run_migrations.sh` (Flyway) et vérifier schéma Oracle.

- [ ] Task 4 — Modèles Pydantic et Repository (AC: 1, 2)
  - [ ] 4.1 Modifier `models/execution.py` : ajouter `servicenow_change_id: str | None` dans ExecutionResponse. Ajouter `change_model_code: str | None` dans ActionResponse (si pas déjà présent).
  - [ ] 4.2 Modifier `repositories/execution_repository.py` : ajouter paramètre `servicenow_change_id` dans `update_execution()`. SQL : `UPDATE EXECUTIONS SET SERVICENOW_CHANGE_ID = :change_id WHERE ID = :execution_id`.
  - [ ] 4.3 Créer `models/servicenow.py` : ServiceNowChangeRequest (short_description, description, requested_by, assignment_group, category, u_change_model, u_correlation_id), ServiceNowChangeResponse (sys_id, number, approval, state).

- [ ] Task 5 — Exception ServiceNow (AC: 5)
  - [ ] 5.1 Modifier `core/exceptions.py` : créer `class ServiceNowError(IdpError)` avec codes : SERVICENOW_TIMEOUT, SERVICENOW_AUTH_ERROR, SERVICENOW_INVALID_RESPONSE, SERVICENOW_UNAVAILABLE. Status HTTP 502 Bad Gateway.
  - [ ] 5.2 Handler global dans `main.py` : ajouter `@app.exception_handler(ServiceNowError)` retourne HTTP 502 avec `{"error": {"code": ..., "message": ..., "details": {...}}}`.

- [ ] Task 6 — Configuration ServiceNow (AC: 5)
  - [ ] 6.1 Variables ENV : ajouter `SERVICENOW_BASE_URL` (ex: https://desjardins.service-now.com), `SERVICENOW_TIMEOUT` (défaut 30), `SERVICENOW_RETRY_COUNT` (défaut 1). Validation au démarrage : SERVICENOW_BASE_URL requis.
  - [ ] 6.2 Intégration ServiceNow dans table INTEGRATIONS (Story 2.27) : créer ligne avec PLATFORM_TYPE="servicenow", BASE_URL (depuis ENV ou config), CREDENTIAL_REF (chemin Vault pour username/password ServiceNow). Si integration ServiceNow non configurée → servicenow_service lève ServiceNowError au runtime.

- [ ] Task 7 — Frontend timeline affichage changement (AC: 2, 3)
  - [ ] 7.1 Modifier `ExecutionTimeline.tsx` (Story 4.6 à venir OU créer version basique ici) : si EXECUTION_STEP type="servicenow" et output contient change_number → afficher badge "Changement ServiceNow: {change_number}" avec icône ✓ (approved) ou ⏳ (pending_approval). Lien cliquable vers ServiceNow : `{SERVICENOW_BASE_URL}/nav_to.do?uri=change_request.do?sys_id={change_id}`.
  - [ ] 7.2 Badge "En attente approbation" : si status="running" et output.status="pending_approval" → afficher badge orange "En attente approbation CAB" avec tooltip "Le changement ServiceNow doit être approuvé avant de continuer". Polling côté frontend toutes les 30s pour GET /api/v1/executions/{id}/steps et détecter changement status.

- [ ] Task 8 — Tests unitaires et intégration (AC: tous)
  - [ ] 8.1 Tests ServiceNowService : create_change succès (approved), create_change pending approval, timeout + retry, ServiceNow 401 (auth error), ServiceNow invalid response, credentials Vault. Mock httpx avec pytest-httpx ou respx.
  - [ ] 8.2 Tests ExecutionService étape ServiceNow : étape servicenow approved (continue), étape servicenow pending (suspend), ServiceNowError (fail execution). Mock servicenow_service.
  - [ ] 8.3 Tests intégration : flow complet create execution → execute servicenow step → mock ServiceNow API → update EXECUTIONS.SERVICENOW_CHANGE_ID. Vérifier correlation_id propagé, credentials Vault appelés.
  - [ ] 8.4 Tests repository : update_execution avec servicenow_change_id, query EXECUTIONS avec change_id.
  - [ ] 8.5 Tests frontend (optionnel Story 4.6) : ExecutionTimeline affichage badge changement, lien ServiceNow, badge "En attente approbation".

## Dev Notes

### Contexte métier

- **FR16** : Le système ouvre automatiquement un changement ServiceNow pour les actions en Production (ou selon configuration action). Cette story implémente l'intégration ServiceNow complète avec support changements pré-approuvés et approbation CAB.
- **NFR19** : L'API ServiceNow a une tolérance de 30 secondes de latence. Le service gère timeout avec retry.
- **Epic 4** : DBA exécute une action de bout en bout via le wizard et suit la progression étape par étape en temps réel via la timeline. L'intégration ServiceNow est une étape critique du workflow d'exécution, garantissant la conformité change management.
- **Change Management** : ServiceNow est le système de référence pour la conformité SOC1. Chaque action en Production (ou selon règles) nécessite un changement ServiceNow. Les modèles de changement pré-approuvés ("automated change model") permettent exécution immédiate sans attente CAB.

### Patterns à respecter

- **Service Pattern** : ServiceNowService avec injection Depends (vault_service). Pattern établi dans inventory_service.py (Story 4.2), vault_service.py (Story 4.2bis), execution_service.py (Story 4.3). [Source: architecture.md, Story 4.2/4.2bis/4.3]
- **Client HTTP async** : httpx.AsyncClient avec timeout 30s, retry avec backoff. Pattern établi dans inventory_service.py (Story 4.2). [Source: architecture.md, inventory_service.py]
- **Error Hierarchy** : ServiceNowError(IdpError) avec code et message. Handler global dans main.py. Pattern établi dans VaultError (Story 4.2bis), PlatformError (Story 4.3). [Source: core/exceptions.py, architecture.md]
- **Logging** : structlog JSON avec correlation_id propagé. `logger.info("servicenow_change_created", change_id=..., change_number=..., correlation_id=...)`. [Source: architecture.md, execution_service.py]
- **Credentials Vault** : Runtime uniquement, jamais persistés. Pattern établi dans vault_service.py (Story 4.2bis). [Source: architecture.md, NFR7]
- **Repository Pattern** : SQL brut via python-oracledb dans execution_repository.py. Pattern établi dans Story 4.3. [Source: architecture.md, execution_repository.py]

### Ce qui existe déjà

- **Backend** : execution_service.py (Story 4.3) avec orchestration étapes, traitement type="vault" et type="platform". À étendre avec type="servicenow". vault_service.py (Story 4.2bis) pour récupérer credentials ServiceNow. execution_repository.py (Story 4.3) avec update_execution(). [Source: Story 4.3, 4.2bis]
- **Tables** : EXECUTIONS (Story 4.3) avec colonnes ID, ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS, STARTED_AT, COMPLETED_AT. EXECUTION_STEPS avec STEP_ORDER, STEP_NAME, STEP_TYPE, STATUS, OUTPUT, ERROR_MESSAGE. INTEGRATIONS (Story 2.27) avec PLATFORM_TYPE, BASE_URL, CREDENTIAL_REF. [Source: Story 4.3, 2.27]
- **Frontend** : ExecutionWizard (Story 4.1) pour soumission exécution. Timeline temps réel sera Story 4.6 (pas encore créée) — cette story peut créer version basique affichage étape ServiceNow. [Source: Story 4.1]
- **Erreurs** : IdpError hierarchy dans core/exceptions.py (VaultError, PlatformError). Handler global dans main.py. [Source: core/exceptions.py, main.py]

### Références techniques

- **ServiceNow API** : Table API REST `/api/now/table/change_request`. Authentification : Basic Auth (username/password). POST créer changement : body JSON avec fields short_description, description, requested_by, assignment_group, category, u_change_model (code modèle pré-approuvé). Réponse : `{"result": {"sys_id": "...", "number": "CHG0030123", "approval": "approved" | "not requested", ...}}`. [Source: ServiceNow REST API docs]
- **Modèles changement pré-approuvés** : ServiceNow "Change Models" permettent automatisation. Si u_change_model spécifié et configuré comme "automated" → approval automatique, status "Approved" immédiatement. Si absent ou "manual" → approval="not requested", nécessite approbation CAB. [Source: ServiceNow Change Management docs]
- **httpx async** : `async with httpx.AsyncClient(timeout=30.0) as client: response = await client.post(url, json=body, auth=..., headers=...)`. Auth : `auth=httpx.BasicAuth(username, password)`. Timeout : `httpx.Timeout(30.0)`. Retry : catch `httpx.TimeoutException`, `await asyncio.sleep(5)`, retry. [Source: httpx docs]
- **Correlation ID propagation** : Header `X-Request-ID: {correlation_id}` dans appels ServiceNow. ServiceNow fields custom `u_correlation_id` pour traçabilité. [Source: architecture.md]
- **structlog context** : `structlog.contextvars.bind_contextvars(correlation_id=...)` lie correlation_id au contexte async. Tous les logs incluent automatiquement correlation_id. [Source: structlog docs, execution_service.py]

### Modèles de changement ServiceNow

ServiceNow supporte plusieurs types de changements :

- **Standard Change** : Changement récurrent pré-approuvé (ex: patching mensuel). Code modèle pré-défini dans ServiceNow (ex: "STD-DB-PATCH"). Si action spécifie ce code → approval automatique.
- **Normal Change** : Changement nécessitant approbation CAB. Si action ne spécifie pas de modèle OU modèle non "automated" → approval="not requested", nécessite workflow d'approbation.
- **Emergency Change** : Changement urgent (hors scope MVP, Phase 2).

**Mapping IDP → ServiceNow :**

- Action.change_model_code (ex: "STD-DB-BACKUP") → ServiceNow field u_change_model
- Si change_model_code absent OU modèle non pré-approuvé → Normal Change → pending approval
- Si modèle pré-approuvé → Standard Change → approved immédiatement

### ServiceNow API request/response examples

**Créer changement pré-approuvé :**
```
POST https://desjardins.service-now.com/api/now/table/change_request
Headers:
  Content-Type: application/json
  Authorization: Basic dXNlcjpwYXNz
  X-Request-ID: 123e4567-e89b-12d3-a456-426614174000
Body:
{
  "short_description": "[IDP] Create PDB - Production",
  "description": "Execution automatique IDP - Correlation ID: 123e4567-e89b-12d3-a456-426614174000\nAction: Create PDB\nEnvironnement: Production\nParametres: {\"pdb_name\": \"NEWPDB\", \"size\": \"10GB\"}\nUtilisateur: marc.dupont",
  "requested_by": "marc.dupont",
  "assignment_group": "DBOPS",
  "category": "Database",
  "u_change_model": "STD-DB-CREATE-PDB",
  "u_correlation_id": "123e4567-e89b-12d3-a456-426614174000"
}
Response 201:
{
  "result": {
    "sys_id": "abc123def456",
    "number": "CHG0030123",
    "approval": "approved",
    "state": "2"
  }
}
```

**Créer changement nécessitant approbation :**
```
POST https://desjardins.service-now.com/api/now/table/change_request
Headers: (same as above)
Body:
{
  "short_description": "[IDP] Major schema migration - Production",
  "description": "...",
  "requested_by": "marc.dupont",
  "assignment_group": "DBOPS",
  "category": "Database",
  "u_correlation_id": "..."
}
Response 201:
{
  "result": {
    "sys_id": "xyz789abc123",
    "number": "CHG0030124",
    "approval": "not requested",
    "state": "-5"
  }
}
```

### Project Structure Notes

- **Nouveau backend** : `services/servicenow_service.py` (nouvelle classe ServiceNowService), `models/servicenow.py` (Pydantic models ServiceNow).
- **Modifier backend** : `services/execution_service.py` (ajouter traitement type="servicenow"), `repositories/execution_repository.py` (ajouter update_execution servicenow_change_id), `core/exceptions.py` (ServiceNowError), `main.py` (handler ServiceNowError), `core/config.py` (variables ENV ServiceNow).
- **Nouveau tests** : `tests/unit/test_servicenow_service.py` (tests unitaires ServiceNowService), `tests/unit/test_servicenow_integration.py` (tests intégration flow ServiceNow).
- **Migration SQL** : `database/migrations/V026__add_servicenow_change_id.sql` (si colonne pas déjà présente).
- **Modifier frontend (optionnel Story 4.6)** : `ExecutionTimeline.tsx` (affichage badge changement ServiceNow). Si Story 4.6 pas encore créée, créer version basique affichage étape.

### Architecture Compliance

- **Stack** : FastAPI 0.115+, Python 3.12+, httpx async, structlog, python-oracledb 3.4.1. [Source: architecture.md]
- **API** : ServiceNow Table API REST. Authentification Basic Auth. Timeout 30s, retry 1x avec backoff 5s (NFR19). [Source: architecture.md, NFR19]
- **Performance** : Timeout 30s ServiceNow (NFR19). Pas de retry infini, max 2 tentatives. Async non-bloquant pour ne pas impacter catalogue. [Source: architecture.md, NFR19]
- **Sécurité** : Credentials ServiceNow depuis Vault runtime, jamais persistés. Correlation_id propagé pour audit trail. [Source: architecture.md, NFR7]
- **Conformité** : ServiceNow comme système de référence change management SOC1. Chaque changement tracé avec correlation_id, user, action, environment. [Source: architecture.md, NFR SOC1]

### Library/Framework Requirements

- **httpx 0.27+** : Client HTTP async pour appels ServiceNow API. Déjà installé (Story 4.2, 4.3, 4.4). [Source: architecture.md]
- **structlog** : Logging structuré JSON avec correlation_id. Déjà installé (Story 4.3). [Source: architecture.md]
- **python-oracledb 3.4.1** : Repository SQL brut pour update EXECUTIONS.SERVICENOW_CHANGE_ID. Déjà installé (Story 4.3). [Source: architecture.md]
- **Pydantic v2** : Modèles validation API (ServiceNowChangeRequest, ServiceNowChangeResponse). Déjà installé. [Source: architecture.md]

### File Structure Requirements

- **Nouveau backend** : `app/services/servicenow_service.py` (classe ServiceNowService), `app/models/servicenow.py` (Pydantic models).
- **Modifier backend** : `app/services/execution_service.py` (traitement type="servicenow"), `app/repositories/execution_repository.py` (update_execution servicenow_change_id), `app/core/exceptions.py` (ServiceNowError), `app/main.py` (handler ServiceNowError), `app/core/config.py` (variables ENV ServiceNow).
- **Nouveau tests** : `tests/unit/test_servicenow_service.py` (tests ServiceNowService), `tests/integration/test_servicenow_integration.py` (tests flow complet).
- **Migration SQL** : `database/migrations/V026__add_servicenow_change_id.sql` (colonne SERVICENOW_CHANGE_ID si pas déjà présente).
- **Modifier frontend (optionnel)** : `frontend/src/components/execution/ExecutionTimeline.tsx` (affichage badge changement). Si Story 4.6 pas créée, créer version basique.

### Testing Requirements

- **Backend** : Tests unitaires servicenow_service (create_change approved/pending/timeout/auth error/invalid response, credentials Vault). Tests execution_service étape servicenow (approved continue, pending suspend, error fail). Tests intégration flow complet (execution → servicenow step → mock API → update EXECUTIONS). Pattern mock httpx avec pytest-httpx ou respx. Réutiliser patterns test_execution_service.py (Story 4.3), test_vault_service.py (Story 4.2bis). [Source: tests/unit/test_execution_service.py, test_vault_service.py]
- **Patterns** : Mock httpx.AsyncClient avec `httpx_mock.add_response(json=...)`, test async avec `@pytest.mark.asyncio async def test_...()`. Test erreurs avec `pytest.raises(ServiceNowError) as exc_info: ...`, vérifier exc_info.value.code. Test timeout avec `httpx_mock.add_exception(httpx.TimeoutException)`. [Source: pytest-httpx docs]

### Previous Story Intelligence

- **Story 4.3 (Moteur d'exécution)** : Créé execution_service.py avec orchestration étapes, traitement type="vault" et type="platform". BaseAdapter interface, factory get_platform_adapter(). Gestion erreurs VaultError, PlatformError. Le moteur itère sur EXECUTION_STEPS et exécute chaque type. À étendre avec type="servicenow". [Source: 4-3-moteur-execution-et-facade-api.md]
- **Story 4.2bis (Vault)** : vault_service.py avec get_secret(credential_ref), VaultError. Les credentials ServiceNow sont récupérés via Vault runtime. Pattern client service async avec injection Depends. [Source: 4-2bis-connecteur-hashicorp-vault.md]
- **Story 4.2 (Inventaire)** : inventory_service.py avec client HTTP httpx async, timeout 30s, retry avec backoff. Pattern cache TTLCache. Réutiliser même pattern client HTTP pour ServiceNow. [Source: 4-2-donnees-inventaire-pour-formulaires-dynamiques.md]
- **Story 2.27 (Intégrations)** : Table INTEGRATIONS avec PLATFORM_TYPE="servicenow", BASE_URL (ServiceNow instance URL), CREDENTIAL_REF (chemin Vault pour username/password ServiceNow). integration_repository.py SQL brut. [Source: 2-27-backend-integrations-plateformes-distantes.md]

### Git Intelligence Summary

- **Derniers commits** : Pattern service async établi (execution_service, inventory_service, vault_service). Pattern client HTTP httpx async avec timeout/retry (inventory_service). Pattern erreurs hierarchy IdpError (VaultError, PlatformError, ServiceUnavailableError). Réutiliser mêmes patterns pour ServiceNowService.
- **Code existant** : execution_service.py avec orchestration étapes (_execute_vault_step, _execute_platform_step). À étendre avec _execute_servicenow_step. vault_service.py avec get_secret() pour credentials. execution_repository.py avec update_execution() pour SERVICENOW_CHANGE_ID. core/exceptions.py avec IdpError hierarchy. main.py avec exception handlers.

### Latest Tech Information

- **ServiceNow Table API** : ServiceNow expose REST API `/api/now/table/{table_name}` pour CRUD sur tables ServiceNow. Table `change_request` pour changements. Authentification Basic Auth (username/password). POST créer changement : body JSON avec fields ServiceNow. Réponse : `{"result": {...}}`. [Source: ServiceNow REST API docs 2026-01]
- **httpx 0.27.x** : Client HTTP async moderne pour Python. Async context manager, timeout, auth (BasicAuth), retry manuel. Exception `httpx.TimeoutException` pour timeout. [Source: httpx docs]
- **pytest-httpx** : Plugin pytest pour mock httpx.AsyncClient. `httpx_mock.add_response(json=...)` mock réponse HTTP. `httpx_mock.add_exception(httpx.TimeoutException)` mock timeout. Compatible pytest async avec pytest-asyncio. [Source: pytest-httpx docs]
- **ServiceNow Change Models** : ServiceNow "Change Models" permettent pré-approbation changements récurrents. Configuration ServiceNow Admin : créer modèle (ex: "STD-DB-CREATE-PDB") avec approval="automated". Si changement créé avec u_change_model spécifié → approval automatique. [Source: ServiceNow Change Management docs]

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — Service Pattern (ServiceNowService), client HTTP httpx async, timeout 30s (NFR19), retry avec backoff, credentials Vault runtime, correlation_id propagation, erreurs hierarchy IdpError/ServiceNowError.
- **PRD** : [Source: planning-artifacts/prd.md] — FR16 (ouverture changement ServiceNow automatique), NFR19 (tolérance 30s ServiceNow), conformité SOC1, ServiceNow système de référence change management.
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.5 acceptance criteria complets, dépendances Story 4.3 (moteur exécution orchestration), 4.2bis (Vault credentials), 2.27 (intégrations ServiceNow).

### References

- [Source: planning-artifacts/architecture.md] — Service Pattern, client HTTP httpx async, timeout/retry, credentials Vault, correlation_id, erreurs hierarchy.
- [Source: planning-artifacts/epics.md] — Story 4.5 requirements complets, dépendances 4.3/4.2bis/2.27.
- [Source: 4-3-moteur-execution-et-facade-api.md] — execution_service.py orchestration étapes, traitement type="vault"/"platform", BaseAdapter interface.
- [Source: 4-2bis-connecteur-hashicorp-vault.md] — vault_service.get_secret(), VaultError, factory get_vault_service().
- [Source: 4-2-donnees-inventaire-pour-formulaires-dynamiques.md] — inventory_service.py client HTTP httpx async, timeout 30s, retry backoff.
- [Source: 2-27-backend-integrations-plateformes-distantes.md] — Table INTEGRATIONS, CREDENTIAL_REF, integration_repository.
- [Source: idp-portal/backend/app/services/execution_service.py] — Pattern service async, orchestration étapes, gestion erreurs.
- [Source: idp-portal/backend/app/core/exceptions.py] — IdpError, VaultError, PlatformError hierarchy.
- [Source: idp-portal/backend/app/repositories/execution_repository.py] — Pattern repository SQL brut, update_execution().
- [Source: ServiceNow REST API docs] — ServiceNow Table API `/api/now/table/change_request`, authentification Basic Auth, create change request.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
