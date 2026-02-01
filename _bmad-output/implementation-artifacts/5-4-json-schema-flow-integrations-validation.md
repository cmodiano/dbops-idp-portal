# Story 5.4 : Intégrations — JSON Schema du flow et validation à la création/édition

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBOPS**,
je veux **que la structure du champ config (flow + secrets par step) soit définie par un JSON Schema et validée à la création/édition d'une intégration**,
afin que **les configurations invalides soient rejetées côté backend et que le contrat soit documenté**.

## Dépendance

- **Story 5.3** (token_url et structure flow en JSON) doit être livrée ; cette story formalise et valide le format du `config`. Les colonnes TOKEN_URL et CONFIG existent (migration V026), les modèles Pydantic acceptent déjà `config` (dict optionnel).

## Acceptance Criteria

1. **AC1 — JSON Schema du config**
   **Given** le backend expose la création/édition d'intégrations,
   **When** un JSON Schema est défini pour le champ `config`,
   **Then** il décrit : liste d'étapes (`auth_flow`), types d'étapes autorisés (ex. `obtain_token`, `call_api`), champs par étape (`url_ref`, `credentials.ref`, `credentials.keys` ou `use_token_from_step`), sans permettre de chemins Vault arbitraires saisis par l'utilisateur (whitelist ou structure fixe).

2. **AC2 — Validation à la création/édition**
   **Given** un client envoie POST ou PUT avec un champ `config` non vide,
   **When** la requête est traitée,
   **Then** le backend valide `config` contre le JSON Schema ; en cas d'échec, retourner 400 avec message d'erreur explicite (champ invalide ou structure non conforme).

3. **AC3 — Documentation**
   **And** le JSON Schema (ou un lien vers sa définition) est documenté (README ou doc API) pour que les consommateurs sachent quel format envoyer.

## Tasks / Subtasks

- [x] Task 1 (AC: 1) — Définir le JSON Schema
  - [x] 1.1 : Créer un fichier JSON Schema (ex. `integration_config_schema.json`) dans `backend/app/schemas/` ou `backend/schemas/` décrivant la structure du `config` (auth_flow array, étapes avec step, url_ref, credentials).
  - [x] 1.2 : Limiter les valeurs autorisées : `step` ∈ {obtain_token, call_api}, `url_ref` ∈ {base_url, token_url}, `credentials.ref` = string (référence au credential_ref de l'intégration, pas chemin Vault arbitraire), `credentials.keys` = array de strings, `credentials.use_token_from_step` = integer (index).

- [x] Task 2 (AC: 2) — Validation backend
  - [x] 2.1 : Lors de la validation Pydantic (IntegrationCreate/IntegrationUpdate), si `config` est fourni et non vide, valider contre le JSON Schema via `jsonschema.validate()` (librairie déjà en dépendance, utilisée dans `executions.py`).
  - [x] 2.2 : En cas d'échec : lever `InvalidStateError(code="INVALID_CONFIG", message=..., details={field, error})` pour retourner 400 avec message lisible.

- [x] Task 3 (AC: 3) — Documentation
  - [x] 3.1 : Documenter le schéma dans README ou doc API (référence au fichier, exemple de config valide).

- [x] Task 4 — Tests
  - [x] 4.1 : Tests unitaires : config valide accepté ; config invalide (étape inconnue, url_ref invalide, structure manquante) rejeté avec 400.

## Dev Notes

### Contexte technique

- **Epic 5** : Dashboard & Activité (Phase 2). La story 5.3 a livré token_url + config (flow d'étapes). La story 5.4 ajoute une validation stricte du format `config` via JSON Schema pour éviter des configurations corrompues ou malveillantes.
- **Problème résolu** : Actuellement `config` est un `dict | None` sans validation de structure. Un client pourrait envoyer un config avec des étapes invalides, des url_ref arbitraires ou des chemins Vault directs. Le JSON Schema restreint le format et protège contre ces cas.

### Structure config attendue (référence 5.3)

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

- `credentials.ref` : toujours `"credential_ref"` (référence au champ credential_ref de l'intégration) — pas de chemin Vault saisi par l'utilisateur.
- `credentials.keys` : noms des clés du secret à utiliser (ex. `["username","password"]`).
- `credentials.use_token_from_step` : index de l'étape dont le token doit être réutilisé.

### Architecture Compliance

- [Source: architecture.md] **API format** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": { "code", "message", "details" } }`. Erreur 400 via `InvalidStateError`.
- [Source: architecture.md] **Zero credential stocke** : NFR7 — config ne contient que credential_ref (référence) et keys ; pas de valeur de secret. Le schéma ne doit pas autoriser de chemin Vault arbitraire.
- [Source: executions.py] **Pattern jsonschema** : `_validate_parameters_against_schema()` — `jsonschema.validate(instance, schema)`, catch `ValidationError` → `InvalidStateError` avec field path et message. Réutiliser ce pattern.
- [Source: integration_repository.py] **Repository** : CONFIG déjà lu/écrit comme CLOB JSON. Pas de changement schema DB.

### Ce qui existe déjà

- **Backend** : `app/models/integration.py` — IntegrationCreate, IntegrationUpdate ont `config: dict | None`. Pas de validation de structure.
- **Backend** : `app/api/v1/integrations.py` — POST/PUT appellent `integration_repository.create/update` avec le payload Pydantic. La validation doit s'ajouter au niveau modèle (Pydantic `@field_validator` qui délègue à jsonschema) ou avant l'appel au repository.
- **Backend** : `app/api/v1/executions.py` — `_validate_parameters_against_schema()` : pattern complet jsonschema + InvalidStateError. À répliquer.
- **Dépendance** : `jsonschema>=4.20` déjà dans `pyproject.toml`.

### Project Structure Notes

- **Nouveau fichier** : `backend/app/schemas/integration_config_schema.json` (ou `backend/schemas/`) — JSON Schema draft-07.
- **Modifier** : `app/models/integration.py` — ajouter un `@field_validator("config")` sur IntegrationCreate et IntegrationUpdate qui, si config non vide, charge le schéma et appelle `jsonschema.validate()`. Ou module dédié `app/schemas/integration_config.py` qui expose `validate_integration_config(config: dict) -> None`.
- **Modifier** : `app/api/v1/integrations.py` — si validation dans le modèle Pydantic, aucun changement ; sinon appeler la validation avant create/update.
- **Documentation** : `idp-portal/README.md` ou doc API OpenAPI (description du champ config, lien vers le schéma).
- **Tests** : `tests/unit/test_integration_api.py` ou `test_integration_models.py` — config valide, config invalide (step inconnu, url_ref invalide, credentials mal formé).

### Référence stories précédentes

- **5.3** : token_url + config (structure flow). Fichiers : integration.py (token_url, config), integration_repository.py (TOKEN_URL, CONFIG), V026. Adapters lisent config. Pour 5.4 : ajouter validation AVANT persist ; pas de changement adapter.
- **4.1 / 4.3 (executions)** : `_validate_parameters_against_schema()` — pattern jsonschema. Réutiliser : load schema, validate, raise InvalidStateError avec détails.
- **4.9** : Validation Pydantic (type, auth_flow). Même principe : validator dans le modèle ou service dédié.

### Testing Requirements

- Config valide : POST/PUT avec config conforme au schéma → 201/200.
- Config invalide : step="unknown" → 400, message explicite.
- Config invalide : url_ref="vault/path" → 400 (enum base_url | token_url).
- Config invalide : credentials avec ref chemin arbitraire → rejet si schéma restreint.
- Config null ou {} : accepté (optionnel).
- Rétrocompatibilité : intégrations existantes sans config continuent de fonctionner.

### Références

- [Source: idp-portal/backend/app/api/v1/executions.py] `_validate_parameters_against_schema`, jsonschema.ValidationError → InvalidStateError.
- [Source: idp-portal/backend/app/models/integration.py] IntegrationCreate, IntegrationUpdate, config dict.
- [Source: _bmad-output/implementation-artifacts/5-3-token-url-et-structure-flow-integrations.md] Structure config, étapes, credentials.
- [Source: idp-portal/backend/app/core/exceptions.py] InvalidStateError(400).
- [JSON Schema draft-07] https://json-schema.org/draft-07/json-schema-release-notes.html

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- **Task 1** : Créé `backend/app/schemas/integration_config_schema.json` (draft-07) avec auth_flow, step enum (obtain_token, call_api), url_ref enum (base_url, token_url), credentials (ref const "credential_ref", keys, use_token_from_step). Pas de chemin Vault arbitraire.
- **Task 2** : Module `app/schemas/integration_config.py` avec `validate_integration_config(config)` ; chargement du schéma, `jsonschema.validate()`, levée de `InvalidStateError(INVALID_CONFIG, 400)` avec field/error. Appel dans POST et PUT `integrations.py` si config non vide. Ancien `@field_validator("config")` retiré de IntegrationCreate/IntegrationUpdate pour que les erreurs de config retournent 400 (et non 422).
- **Task 3** : Section "API Integrations — champ config" ajoutée dans `idp-portal/README.md` (référence au schéma, exemple de config valide).
- **Task 4** : Tests dans `test_integration_api.py` : config valide (full + empty acceptés), config invalide (step inconnu, url_ref invalide, auth_flow manquant, auth_flow pas une liste, step manquant, step invalide) → 400 INVALID_CONFIG ; PUT avec config invalide → 400. Anciens tests 5.3 (422) mis à jour en 400 INVALID_CONFIG.

### File List

- idp-portal/backend/app/schemas/__init__.py (new)
- idp-portal/backend/app/schemas/integration_config_schema.json (new)
- idp-portal/backend/app/schemas/integration_config.py (new)
- idp-portal/backend/app/api/v1/integrations.py (modified)
- idp-portal/backend/app/models/integration.py (modified — validators config retirés)
- idp-portal/README.md (modified)
- idp-portal/backend/tests/unit/test_integration_api.py (modified)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified)
- _bmad-output/implementation-artifacts/5-4-json-schema-flow-integrations-validation.md (modified)

### Change Log

- 2026-01-30 : Story 5.4 implémentée — JSON Schema du config, validation à la création/édition (400 INVALID_CONFIG), documentation README, tests unitaires.
- 2026-01-30 : Code review — 2 tests ajoutés (credentials.ref arbitraire → 400, auth_flow vide → 400) ; cache schéma thread-safe ; export `validate_integration_config` dans `schemas/__init__.py` ; doc API POST/PUT (400 INVALID_CONFIG) ; statut → done.
