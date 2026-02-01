# Story 5.3 : Intégrations — token_url et structure flow (étapes + secrets par step) en JSON

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBOPS**,
je veux **pouvoir configurer une URL dédiée pour l'obtention du token et un flow d'étapes (auth + API) avec les secrets par étape en JSON**,
afin que **une même intégration puisse couvrir des cas comme « token seul » (AAP), « user/pass → token puis API » (API interne) sans one-size-fits-all rigide**.

## Contexte produit

Aujourd'hui une intégration a une seule `base_url` et un seul `credential_ref`. Pour une API interne qui exige : (1) POST user/pass sur une URL pour obtenir un token, (2) appels API sur une autre URL avec ce token, le modèle actuel est insuffisant. Cette story introduit `token_url` (optionnel) et une structure JSON décrivant les étapes du flow et les secrets utilisés par étape ; les adapters lisent cette config au lieu de se baser uniquement sur l'enum `auth_flow`.

## Acceptance Criteria

1. **AC1 — token_url**
   **Given** une intégration est créée ou mise à jour,
   **When** le champ `token_url` est fourni (optionnel),
   **Then** il est validé (URL valide http(s)) et persisté ; utilisé par les adapters pour l'étape « obtain_token » lorsque pertinent.

2. **AC2 — Colonne config (flow + secrets par step)**
   **Given** une migration est exécutée,
   **When** la table INTEGRATIONS est modifiée,
   **Then** une colonne `CONFIG` (CLOB ou JSON) stocke un objet JSON optionnel décrivant : une liste d'étapes (ex. `obtain_token`, `call_api`), chaque étape ayant une référence d'URL (`base_url` | `token_url`), une référence au secret (`credential_ref`) et les clés du secret utilisées pour cette étape (ex. `["username","password"]` ou `use_token_from_step`).

3. **AC3 — Modèles et API**
   **Given** le backend expose les intégrations,
   **When** un client crée ou met à jour une intégration,
   **Then** les modèles Pydantic et l'API acceptent `token_url` (optionnel) et `config` (optionnel, objet JSON) ; la réponse inclut ces champs (sans exposer de secret).

4. **AC4 — Adapters**
   **Given** une intégration a un `config` avec des étapes,
   **When** le moteur d'exécution appelle l'adapter (ex. AAP, ou futur adapter générique),
   **Then** l'adapter lit `config` (et `token_url` / `base_url`) pour déterminer les URLs et les clés de credentials par étape ; le comportement existant (auth_flow + base_url + credential_ref) reste supporté pour rétrocompatibilité si `config` est absent.

5. **AC5 — Rétrocompatibilité**
   **And** les intégrations existantes sans `token_url` ni `config` continuent de fonctionner (comportement actuel basé sur `auth_flow`).

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 2) — Migration et modèle de données
  - [x] 1.1 : Migration Flyway : ajouter colonne `TOKEN_URL` (VARCHAR2, nullable) et `CONFIG` (CLOB ou JSON, nullable) à INTEGRATIONS.
  - [x] 1.2 : Modèles Pydantic : ajouter `token_url` (optional) et `config` (optional, dict/JSON) à IntegrationCreate, IntegrationUpdate, IntegrationResponse ; validation URL pour token_url.

- [x] Task 2 (AC: 3) — API et repository
  - [x] 2.1 : Repository : lire/écrire token_url et config ; sérialiser config en JSON pour le CLOB si nécessaire.
  - [x] 2.2 : API : accepter et retourner token_url et config dans les payloads ; pas de secret dans config (uniquement refs et clés).

- [x] Task 3 (AC: 4, 5) — Adapters
  - [x] 3.1 : Si config présent : interpréter les étapes (obtain_token avec token_url + credential keys, call_api avec base_url + use_token_from_step ou credential keys).
  - [x] 3.2 : Si config absent : conserver le comportement actuel (auth_flow + base_url + credential_ref) pour AAP et autres adapters existants.

- [x] Task 4 — Tests
  - [x] 4.1 : Tests unitaires repository et API (création/édition avec token_url et config).
  - [x] 4.2 : Tests adapters : au moins un cas avec config (obtain_token + call_api) et un cas sans config (rétrocompatibilité).

## Dev Notes

### Contexte technique

- **Epic 5** : Dashboard & Activité (Phase 2). Les stories 5.1 et 5.2 ont livré le dashboard avec statistiques, activité récente et temps réel. La story 5.3 étend le modèle des intégrations (Epic 2 / 4) : token_url + structure config (flow d'étapes + secrets par step) pour supporter des APIs internes (user/pass → token puis API) sans coder en dur.
- **Position** : Story 5.3 ; dépendances livrées : 2.27 (backend intégrations), 2.28 (frontend admin intégrations), 4.9 (type libre, auth_flow, icône). La story 5.4 (JSON Schema validation du config) dépend de 5.3.
- **Problème résolu** : Une seule base_url et un seul credential_ref ne suffisent pas pour « basic_then_token » (POST sur URL A pour token, puis API sur URL B avec Bearer). token_url + config (étapes avec url_ref, credentials.keys, use_token_from_step) permet de décrire ce flow sans one-size-fits-all.

### Structure config (exemple)

```json
{
  "auth_flow": [
    {
      "step": "obtain_token",
      "url_ref": "token_url",
      "credentials": { "ref": "credential_ref", "keys": ["username", "password"] },
      "response_token_path": "access_token"
    },
    {
      "step": "call_api",
      "url_ref": "base_url",
      "credentials": { "use_token_from_step": 0 }
    }
  ]
}
```

À affiner en implémentation ; ne pas exposer de chemins Vault arbitraires (sécurité) : une seule ref au niveau intégration, dans config uniquement les clés du secret par étape.

### Architecture Compliance

- [Source: architecture.md] **Repository Pattern SQL brut** : integration_repository.py avec SQL via python-oracledb ; ajouter TOKEN_URL et CONFIG dans SELECT/INSERT/UPDATE.
- [Source: architecture.md] **Platform Adapter Pattern** : base_adapter.py (trigger, get_status, parse_callback) ; les adapters reçoivent l'intégration (ou ses champs) et lisent config/token_url pour déterminer URLs et credentials par étape.
- [Source: architecture.md] **Zero credential stocke** : NFR7 — config ne contient que credential_ref (référence) et keys ; pas de valeur de secret. Vault à l'exécution.
- [Source: architecture.md] **API format** : snake_case JSON, wrapper { "data": ... } / { "error": ... }. token_url et config dans les payloads intégrations.
- [Source: architecture.md] **Migrations** : Flyway, format V0XX__description_snake_case.sql ; identity columns ; cohérent avec V020, V024.

### Ce qui existe déjà

- **Backend** : Table INTEGRATIONS (V020, V024) : ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, CREATED_AT, UPDATED_AT. Modèles Pydantic integration.py (IntegrationCreate, IntegrationUpdate, IntegrationResponse) avec type str, auth_flow (AuthFlow enum). integration_repository.py : get_all, get_by_id, create, update, delete. API /api/v1/admin/integrations (GET, POST, PUT, DELETE).
- **Adapters** : base_adapter.py (trigger, get_status, parse_callback). aap_adapter.py utilise base_url, credentials (token ou username/password), auth_flow non lu directement — credentials viennent du moteur qui résout credential_ref via Vault. Pour 5.3 : moteur ou adapter doit passer integration (avec token_url, config) à l'adapter ; adapter lit config si présent.
- **Frontend** : Formulaire intégrations (type libre, auth_flow, icône) — Story 4.9. Pour 5.3 : ajouter champs token_url (Input URL) et config (éditeur JSON ou formulaire structuré selon choix UX) ; optionnel.

### Project Structure Notes

- **Backend** :
  - Nouvelle migration : `database/migrations/V0XX__integrations_token_url_config.sql` (TOKEN_URL, CONFIG CLOB).
  - Modifier : `app/models/integration.py` (token_url, config).
  - Modifier : `app/repositories/integration_repository.py` (colonnes TOKEN_URL, CONFIG ; sérialisation JSON pour CLOB).
  - Modifier : `app/api/v1/integrations.py` ou admin : payloads avec token_url, config.
  - Modifier : `app/adapters/base_adapter.py` si signature doit accepter integration complète ; ou `app/services/execution_service.py` pour résoudre config et passer URLs/credentials par étape à l'adapter.
  - Modifier : `app/adapters/aap_adapter.py` : si config présent, utiliser token_url + étapes ; sinon comportement actuel (auth_flow implicite via credentials).
- **Frontend** (optionnel pour 5.3 — peut être minimal) :
  - Modifier : types api (token_url?, config?) ; formulaire intégrations : champ token_url (optionnel), config (optionnel, TextArea JSON ou formulaire étapes).
- **Tests** : test_integration_repository.py (token_url, config) ; test_admin_api.py ou test_integration_api.py (POST/PUT avec token_url, config) ; test_aap_adapter.py ou execution_service : cas avec config, cas sans config.

### Référence stories précédentes

- **4.9 (intégrations type libre, flow, icône)** : Fichiers modifiés — integration.py (type str, AuthFlow), integration_repository.py (AUTH_FLOW), V024. Formulaire frontend : type Input, auth_flow Select, upload icône. Réutiliser même pattern pour token_url et config (champs optionnels).
- **2.27 / 2.28** : Backend CRUD intégrations, frontend admin liste + formulaire. Pas de token_url ni config à ce jour.
- **5.1, 5.2** : Dashboard ; pas de changement direct sur intégrations, mais contexte Epic 5.

### Testing Requirements

- Tests unitaires repository : create/update avec token_url et config (JSON) ; get_by_id retourne token_url et config.
- Tests API : POST /api/v1/admin/integrations avec token_url et config ; PUT avec config null (retrait) ; validation token_url (http/https uniquement).
- Tests adapters : mock intégration avec config (obtain_token + call_api) ; mock intégration sans config (comportement actuel AAP). Pas de régression sur 4.4 / 4.10.
- Rétrocompatibilité : intégrations existantes (AUTH_FLOW, pas de TOKEN_URL/CONFIG) continuent de fonctionner en exécution.

### Références

- [Source: _bmad-output/planning-artifacts/architecture.md] Repository pattern, adapter pattern, API format, migrations Flyway.
- [Source: _bmad-output/implementation-artifacts/4-9-integrations-type-libre-flow-upload-icone.md] Modèles Integration, AuthFlow, repository, formulaire.
- [Source: idp-portal/backend/app/models/integration.py] IntegrationCreate, IntegrationUpdate, IntegrationResponse, AuthFlow.
- [Source: idp-portal/backend/app/repositories/integration_repository.py] Colonnes actuelles, _row_to_integration_response.
- [Source: idp-portal/backend/app/adapters/aap_adapter.py] _get_auth_headers, trigger avec credentials.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- **2026-01-30** : Implémentation complète Story 5.3. Migration V026 (TOKEN_URL, CONFIG CLOB). Modèles Pydantic token_url + config + validation URL token_url. Repository : SELECT/INSERT/UPDATE avec _parse_config_clob pour CONFIG. execution_repository.get_action_with_integration : I.TYPE AS PLATFORM_TYPE, TOKEN_URL, CONFIG dans le dict integration. BaseAdapter + AAPAdapter : trigger(..., integration=...) ; AAPAdapter._resolve_credentials_from_config : obtain_token (POST token_url, keys, response_token_path) puis merge token dans credentials. execution_service : passage integration à adapter.trigger. Tests : test_integration_repository (row 11 cols, token_url/config, create with config), test_integration_api (fixtures token_url/config, POST/PUT token_url+config, token_url invalid 422, config null retract), test_aap_adapter (trigger with config obtain_token then launch, trigger without config unchanged), test_execution_service (assert_called_once_with integration=).

### File List

- idp-portal/database/migrations/V026__integrations_token_url_config.sql
- idp-portal/backend/app/models/integration.py
- idp-portal/backend/app/repositories/integration_repository.py
- idp-portal/backend/app/repositories/execution_repository.py
- idp-portal/backend/app/adapters/base_adapter.py
- idp-portal/backend/app/adapters/aap_adapter.py
- idp-portal/backend/app/services/execution_service.py
- idp-portal/backend/tests/unit/test_integration_repository.py
- idp-portal/backend/tests/unit/test_integration_api.py
- idp-portal/backend/tests/unit/test_aap_adapter.py
- idp-portal/backend/tests/unit/test_execution_service.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/5-3-token-url-et-structure-flow-integrations.md

## Senior Developer Review (AI)

**Date:** 2026-01-30
**Reviewer:** Claude Opus 4.5 (Code Review Workflow)
**Outcome:** ✅ APPROVED (after fixes)

### Issues Found & Fixed

| ID | Severity | Description | Fix Applied |
|----|----------|-------------|-------------|
| HIGH-1 | 🔴 HIGH | `_resolve_credentials_from_config` failed silently on token acquisition errors | Raises `PlatformError` with codes `AAP_TOKEN_URL_MISSING`, `AAP_TOKEN_NOT_IN_RESPONSE`, `AAP_TOKEN_ACQUISITION_FAILED` |
| HIGH-2 | 🔴 HIGH | No validation of `config` JSON structure (accepted any dict) | Added `validate_config_structure` validator in `IntegrationCreate` and `IntegrationUpdate` |
| MED-1 | 🟡 MEDIUM | Missing test for nested `response_token_path` (e.g., `data.access_token`) | Added `test_trigger_with_integration_config_nested_token_path` |
| MED-2 | 🟡 MEDIUM | `_parse_config_clob` failed silently on invalid JSON | Added logging with `integration_id` context |
| MED-3 | 🟡 MEDIUM | Missing test for UPDATE with `token_url` and `config` | Added `test_update_with_token_url_and_config` and `test_update_config_null_clears_config` |
| MED-4 | 🟡 MEDIUM | LOB read pattern inconsistency between repositories | Added `hasattr(clob_value, "read")` check in `_parse_config_clob` |

### Files Modified by Review

- `aap_adapter.py`: HIGH-1 fix — explicit error handling in `_resolve_credentials_from_config`
- `integration.py`: HIGH-2 fix — config structure validation
- `integration_repository.py`: MED-2, MED-4 fixes — logging and LOB handling
- `test_aap_adapter.py`: MED-1 fix + HIGH-1 tests — nested path + error scenarios
- `test_integration_repository.py`: MED-3 fix — UPDATE tests
- `test_integration_api.py`: HIGH-2 tests — config validation error cases

### Verification

All ACs validated:
- ✅ AC1: token_url validated http(s), persisted, used by adapter
- ✅ AC2: CONFIG CLOB with JSON structure validation
- ✅ AC3: API accepts/returns token_url and config
- ✅ AC4: Adapter reads config for obtain_token + call_api flow
- ✅ AC5: Rétrocompatibilité preserved (no config = legacy behavior)
