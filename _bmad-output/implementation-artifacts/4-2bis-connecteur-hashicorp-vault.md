# Story 4.2bis: Connecteur HashiCorp Vault

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **système**,
I want **un connecteur Vault qui se connecte dynamiquement à HashiCorp Vault et récupère les secrets à la demande (par chemin / credential_ref)**,
so that **le moteur d'exécution peut résoudre les credential_ref des intégrations (Story 2.27) et fournir les credentials aux adapters de plateforme sans stocker de secret dans le portail**.

## Acceptance Criteria

1. **AC1 — Config et « secret 0 »**
   **Given** le backend démarre avec une config Vault valide,
   **When** le connecteur Vault est initialisé,
   **Then** il se connecte à Vault en utilisant le « secret 0 » fourni **uniquement par l'environnement** (variables d'env ou secrets montés) : `VAULT_ADDR`, et soit `VAULT_TOKEN`, soit `VAULT_ROLE_ID` + `VAULT_SECRET_ID` (AppRole). Aucun de ces éléments n'est stocké en base ni exposé dans l'admin.

2. **AC2 — Récupération dynamique de secrets**
   **Given** le moteur d'exécution (Story 4.3) ou un service a besoin d'un secret,
   **When** il appelle le connecteur avec un chemin ou `credential_ref` (ex. `secret/data/idp/aap-prod`),
   **Then** le connecteur interroge Vault dynamiquement, retourne le secret (ou les champs nécessaires) et ne le persiste pas.

3. **AC3 — Erreurs et indisponibilité**
   **Given** Vault est indisponible ou le secret 0 est invalide,
   **When** le connecteur tente de se connecter ou de récupérer un secret,
   **Then** une erreur explicite est remontée (ex. `VaultError` ou équivalent) et le caller peut refuser l'exécution (NFR21).

4. **AC4 — Intégration moteur d'exécution**
   **And** le connecteur est exposé comme service injectable (ex. `vault_service` ou `VaultConnector`) utilisé par le moteur d'exécution pour résoudre les `credential_ref` des intégrations avant d'appeler les plateformes (AAP, Terraform, etc.).
   **And** FR17 et FR29 sont satisfaites pour la récupération dynamique des credentials.

## Tasks / Subtasks

- [x] Task 1 (AC1) — Config et secret 0
  - [x] 1.1 : Étendre `Settings` dans `backend/app/core/config.py` avec `vault_addr`, `vault_token` (ou `vault_role_id` + `vault_secret_id` pour AppRole), lus depuis les variables d'env. Pas de valeur par défaut sensible en prod. Validation : `vault_addr` requis si Vault activé (ou mode dev désactivé).
  - [x] 1.2 : Documenter les variables attendues dans `.env.example` : `VAULT_ADDR` (requis), `VAULT_TOKEN` (optionnel si AppRole), `VAULT_ROLE_ID` + `VAULT_SECRET_ID` (optionnel si token). Ajouter section dans README ou doc déploiement expliquant les deux méthodes d'authentification.

- [x] Task 2 (AC2, AC3) — Connecteur Vault
  - [x] 2.1 : Créer module `backend/app/services/vault_service.py`. Classe `VaultService` avec méthode `__init__()` : initialisation client hvac avec `vault_addr` depuis Settings. Authentification : si `vault_token` présent → `client.token = vault_token`, sinon si `vault_role_id` + `vault_secret_id` → `client.auth.approle.login(role_id, secret_id)`. Gérer erreurs connexion (VaultError avec code "VAULT_CONNECTION_FAILED").
  - [x] 2.2 : Exposer méthode `async def get_secret(path: str) -> dict[str, Any]` qui lit le secret à la demande via `client.secrets.kv.v2.read_secret_version(path=path)` (KV v2) ou `client.secrets.kv.v1.read_secret(path=path)` (KV v1 selon config). Retourner `data` du secret. Gérer erreurs : secret inexistant → `VaultError(code="SECRET_NOT_FOUND")`, Vault down → `VaultError(code="VAULT_UNAVAILABLE")`, token expiré → `VaultError(code="VAULT_AUTH_FAILED")`.
  - [x] 2.3 : Ne jamais persister les secrets récupérés ; utilisation uniquement en mémoire pour les appels aux plateformes. Loguer uniquement le chemin (pas la valeur) avec structlog : `logger.debug("vault_secret_retrieved", path=path)`.

- [x] Task 3 (AC4) — Injection et usage
  - [x] 3.1 : Rendre le connecteur injectable via FastAPI `Depends`. Créer fonction `get_vault_service() -> VaultService` dans `backend/app/api/deps.py` (ou nouveau fichier `services.py`). Factory pattern : créer instance `VaultService` au démarrage ou lazy (singleton). Prévoir mode « Vault désactivé » : si `VAULT_ADDR` vide ou non défini → retourner `None` ou `VaultServiceDisabled` (mock pour dev/tests).
  - [x] 3.2 : Documenter dans Dev Notes comment le moteur d'exécution (Story 4.3) résout un `credential_ref` d'intégration (Story 2.27) via le connecteur : mapping `credential_ref` (chemin Vault) → `vault_service.get_secret(credential_ref)` → retourne dict avec champs nécessaires (ex. `username`, `password`, `api_key`).

- [x] Task 4 — Tests
  - [x] 4.1 : Tests unitaires avec Vault mocké (ou mode dev) : `get_secret` retourne les données attendues ; erreurs (Vault down, path inexistant, token expiré) lèvent bien `VaultError` avec codes appropriés. Utiliser `unittest.mock` pour mocker `hvac.Client`.
  - [ ] 4.2 : Optionnel : test d'intégration contre un Vault de dev (container Docker) si l'équipe le souhaite. Prévoir fixture pytest avec Vault container (testcontainers ou docker-compose).

## Dev Notes

### Contexte métier

- **FR17** : Le système récupère les secrets nécessaires depuis HashiCorp Vault au moment de l'exécution. **FR29** : Le système ne stocke aucun credential — tous les secrets sont récupérés depuis Vault à l'exécution.
- **NFR7** : Aucun secret (credential, token, clé) n'est stocké dans le portail ou le catalogue — récupération exclusive depuis Vault à l'exécution.
- **NFR21** : En cas d'indisponibilité de Vault, l'exécution est refusée avec un message explicite (pas de fallback sur des credentials stockés).
- **Epic 4** : DBA exécute une action de bout en bout via le wizard et suit la progression étape par étape en temps réel via la timeline. Cette story 4.2bis implémente le connecteur Vault qui sera utilisé par le moteur d'exécution (Story 4.3) pour récupérer dynamiquement les credentials des intégrations (Story 2.27) avant d'appeler les plateformes d'exécution (AAP, Terraform, etc.).

### Patterns à respecter

- **Service Pattern** : Suivre le même pattern que `inventory_service.py` (Story 4.1) : module dans `services/`, fonctions async, structlog pour logging. [Source: idp-portal/backend/app/services/inventory_service.py]
- **Injection FastAPI** : Pattern `Depends` comme `get_current_user` dans `deps.py`. Factory function retourne instance service. [Source: idp-portal/backend/app/api/deps.py]
- **Erreurs** : Utiliser `VaultError` existant dans `core/exceptions.py` (hérite de `IdpError`, status_code 502). Codes explicites : "VAULT_CONNECTION_FAILED", "VAULT_UNAVAILABLE", "SECRET_NOT_FOUND", "VAULT_AUTH_FAILED". [Source: idp-portal/backend/app/core/exceptions.py]
- **Configuration** : Étendre `Settings` dans `core/config.py` avec variables ENV préfixées (pas de préfixe selon config actuelle). Validation Pydantic si nécessaire. [Source: idp-portal/backend/app/core/config.py]
- **Logging** : structlog avec contexte (pas de valeurs sensibles). `logger.debug("vault_secret_retrieved", path=path)` — jamais logger la valeur du secret. [Source: architecture.md]

### Ce qui existe déjà

- **Backend** : `VaultError` existe dans `core/exceptions.py` (status_code 502). Pattern injection `Depends` établi dans `deps.py`. Pattern service async dans `inventory_service.py`. [Source: idp-portal/backend/app/core/exceptions.py, deps.py, services/inventory_service.py]
- **Architecture** : Vault mentionné dans architecture.md comme appel runtime uniquement, pas de cache de secrets. Health check endpoint `/api/v1/health` devrait vérifier Vault (à implémenter dans story santé). [Source: architecture.md]
- **Story 2.27** : Table `INTEGRATIONS` avec colonne `CREDENTIAL_REF` (chemin Vault ou nom logique). Aucun secret stocké — uniquement référence. Le connecteur Vault résout cette référence. [Source: 2-27-backend-integrations-plateformes-distantes.md]

### Références techniques

- **Bibliothèque hvac** : Version 2.4.0 (octobre 2025), Python 3.8+. Client Python pour HashiCorp Vault. Installation : `pip install hvac`. Compatible Vault v1.4.7+. [Source: recherche web]
- **Authentification Vault** : Deux méthodes supportées : Token (simple) ou AppRole (recommandé pour production). Token : `client.token = token`. AppRole : `client.auth.approle.login(role_id=role_id, secret_id=secret_id)`. [Source: documentation hvac]
- **KV Secrets Engine** : Vault stocke secrets dans KV (Key-Value). Version v2 : `client.secrets.kv.v2.read_secret_version(path=path, version=None)`. Version v1 : `client.secrets.kv.v1.read_secret(path=path)`. Retourne dict avec `data` (v2) ou directement les champs (v1). [Source: documentation hvac]
- **Gestion erreurs hvac** : `hvac.exceptions.VaultDown` si Vault indisponible, `hvac.exceptions.InvalidPath` si secret inexistant, `hvac.exceptions.Forbidden` si token invalide/expiré. Mapper vers `VaultError` avec codes explicites. [Source: documentation hvac]
- **Mode dev/désactivé** : Si `VAULT_ADDR` vide → mode dev. Retourner service mock ou `None`. Permet développement sans Vault réel. Tests unitaires avec `unittest.mock` pour mocker `hvac.Client`. [Source: architecture.md, patterns projet]

### Project Structure Notes

- **Backend** : `idp-portal/backend/app/services/vault_service.py` (nouveau), `idp-portal/backend/app/core/config.py` (modifier, ajouter variables Vault), `idp-portal/backend/app/api/deps.py` (modifier ou créer `services.py` pour factory `get_vault_service`).
- **Configuration** : `.env.example` ajouter variables `VAULT_ADDR`, `VAULT_TOKEN` (optionnel), `VAULT_ROLE_ID` (optionnel), `VAULT_SECRET_ID` (optionnel). Documentation dans README ou doc déploiement.
- **Tests** : `idp-portal/backend/tests/unit/test_vault_service.py` (nouveau) — tests unitaires avec Vault mocké.

### Architecture Compliance

- **Stack** : FastAPI, Pydantic v2, hvac 2.4.0, python-oracledb 3.4.1 (pas utilisé ici, Vault externe), structlog pour logging.
- **API** : Pas d'endpoint REST pour Vault (service interne uniquement). Injection via `Depends` pour usage dans autres services (moteur exécution Story 4.3). [Source: architecture.md]
- **Sécurité** : Zero credential stocké (NFR7). Secret 0 (token/AppRole) uniquement depuis ENV, jamais en base ni admin. Secrets récupérés uniquement en mémoire, jamais persistés. Logging sans valeurs sensibles. [Source: architecture.md, NFR7, FR29]
- **Performance** : Appels Vault synchrones (hvac supporte async mais pas nécessaire ici). Pas de cache de secrets (sécurité). Timeout configurable si nécessaire (httpx sous-jacent dans hvac). [Source: architecture.md]

### Library/Framework Requirements

- **hvac 2.4.0** : Client Python pour HashiCorp Vault. `pip install hvac`. Compatible Vault v1.4.7+. Support Token et AppRole auth. KV v1 et v2. [Source: recherche web, PyPI]
- **FastAPI** : `Depends` pour injection service. Pattern factory function dans `deps.py` ou fichier dédié. [Source: FastAPI docs, patterns projet]
- **Pydantic v2** : Validation variables ENV dans `Settings`. `field_validator` si validation complexe nécessaire. [Source: Pydantic v2 docs]
- **structlog** : Logging structuré JSON. Contexte via `structlog.contextvars.bind_contextvars`. Jamais logger valeurs sensibles. [Source: structlog docs, patterns projet]

### File Structure Requirements

- **Nouveau backend** : `services/vault_service.py` (classe `VaultService` avec méthodes `__init__`, `get_secret`), `api/deps.py` ou `api/services.py` (factory `get_vault_service`).
- **Modifier backend** : `core/config.py` (ajouter variables Vault dans `Settings`), `.env.example` (documenter variables Vault).
- **Nouveau tests** : `tests/unit/test_vault_service.py` (tests unitaires avec Vault mocké).

### Testing Requirements

- **Backend** : Tests unitaires `vault_service` : initialisation avec token, initialisation avec AppRole, `get_secret` succès (KV v1 et v2), erreurs (Vault down, secret inexistant, token expiré). Utiliser `unittest.mock` pour mocker `hvac.Client` et ses méthodes. Vérifier `VaultError` levée avec codes appropriés.
- **Patterns** : Réutiliser patterns tests Story 4.1 (inventory_service) et Story 2.27 (integration_repository). Mock externe (Vault) comme inventaire externe. [Source: tests Story 4.1, Story 2.27]

### Previous Story Intelligence

- **Story 2.27 (Intégrations)** : Table `INTEGRATIONS` avec colonne `CREDENTIAL_REF` (chemin Vault ou nom logique). Aucun secret stocké — uniquement référence. Le connecteur Vault résout cette référence. Pattern repository SQL brut, modèles Pydantic, routes admin. [Source: 2-27-backend-integrations-plateformes-distantes.md]
- **Story 4.1 (ExecutionWizard)** : Pattern service async dans `inventory_service.py`. Injection via `Depends` dans routes API. Factory pattern pour services. [Source: 4-1-wizard-execution-en-3-etapes.md]
- **Story 4.2 (Inventaire)** : Pattern cache `TTLCache` pour données externes. Sync asynchrone. Client HTTP httpx. Réutiliser patterns similaires pour Vault (mais pas de cache pour secrets — sécurité). [Source: 4-2-donnees-inventaire-pour-formulaires-dynamiques.md]

### Git Intelligence Summary

- **Derniers commits** : Pattern service async établi dans `inventory_service.py`. Pattern injection `Depends` dans `deps.py`. Pattern erreurs hiérarchie (`VaultError` existe). Réutiliser mêmes patterns pour Vault service.
- **Code existant** : `VaultError` existe dans `exceptions.py`. `Settings` dans `config.py` extensible. `deps.py` avec `get_current_user` comme exemple injection. Suivre mêmes conventions.

### Latest Tech Information

- **hvac 2.4.0 (octobre 2025)** : Version stable, compatible Vault v1.4.7+. Support complet Token et AppRole auth. KV v1 et v2. Gestion erreurs via exceptions dédiées (`VaultDown`, `InvalidPath`, `Forbidden`). [Source: recherche web, PyPI hvac]
- **HashiCorp Vault Best Practices** : Utiliser AppRole plutôt que tokens statiques pour production (meilleure sécurité, rotation automatique). Short-lived credentials recommandés. Distinct token capabilities (principle of least privilege). [Source: recherche web, HashiCorp docs]
- **FastAPI Depends** : Pattern factory function pour services. `Depends(get_vault_service)` dans routes ou autres services. Singleton ou création à chaque requête selon besoins. [Source: FastAPI docs]
- **structlog** : Logging structuré JSON vers Splunk. Contexte via `structlog.contextvars.bind_contextvars(correlation_id=...)`. Jamais logger valeurs sensibles (secrets, tokens). [Source: structlog docs, architecture.md]

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — Vault appel runtime uniquement, pas de cache secrets, zero credential stocké, health check Vault (à implémenter), erreurs `VaultError` dans hiérarchie.
- **PRD** : [Source: planning-artifacts/prd.md] — FR17 (récupération secrets Vault), FR29 (zero credential stocké), NFR7 (aucun secret stocké), NFR21 (pas de fallback si Vault down).
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.2bis acceptance criteria détaillés, dépendances Story 2.27 (credential_ref dans INTEGRATIONS), Story 4.3 (moteur exécution utilisera connecteur Vault).

### References

- [Source: planning-artifacts/architecture.md] — Vault runtime uniquement, pas de cache, zero credential, health check, erreurs VaultError.
- [Source: planning-artifacts/epics.md] — Story 4.2bis requirements complets, Story 4.3 dépendance.
- [Source: 2-27-backend-integrations-plateformes-distantes.md] — credential_ref dans INTEGRATIONS, secret 0 hors portail.
- [Source: idp-portal/backend/app/core/exceptions.py] — VaultError existant, hiérarchie erreurs.
- [Source: idp-portal/backend/app/services/inventory_service.py] — Pattern service async, structlog.
- [Source: idp-portal/backend/app/api/deps.py] — Pattern injection Depends, factory function.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

**Implémentation complète Story 4.2bis:**

✅ **Task 1 - Config et secret 0:**
- Variables Vault ajoutées dans `config.py`: `vault_addr`, `vault_token`, `vault_role_id`, `vault_secret_id`
- Variables documentées dans `.env.example` avec explication Token vs AppRole
- Dépendance `hvac>=2.4.0` ajoutée à `pyproject.toml`

✅ **Task 2 - Connecteur Vault:**
- Module `vault_service.py` créé avec classe `VaultService`
- Authentification Token et AppRole implémentées dans `__init__()`
- Méthode `async get_secret(path)` avec support KV v2 (fallback v1)
- Gestion erreurs complète: `VAULT_CONNECTION_FAILED`, `VAULT_UNAVAILABLE`, `SECRET_NOT_FOUND`, `VAULT_AUTH_FAILED`
- Logging structuré avec structlog (chemin uniquement, jamais valeurs sensibles)
- Secrets jamais persistés, utilisation mémoire uniquement

✅ **Task 3 - Injection et usage:**
- Factory function `get_vault_service()` créée dans `app/api/services.py`
- Mode désactivé: `VaultServiceDisabled` si `VAULT_ADDR` non configuré
- Documentation usage moteur d'exécution ajoutée dans Dev Notes

✅ **Task 4 - Tests:**
- Tests unitaires complets dans `test_vault_service.py`:
  - Initialisation avec Token
  - Initialisation avec AppRole
  - Erreur connexion
  - `get_secret` KV v2 succès
  - `get_secret` KV v1 fallback
  - Erreurs: secret not found, Vault unavailable, auth failed
- Tous les tests utilisent `unittest.mock` pour mocker `hvac.Client`
- Tests async avec `@pytest.mark.asyncio`

**Task 3.2 - Documentation usage moteur d'exécution:**

Le moteur d'exécution (Story 4.3) résout un `credential_ref` d'intégration (Story 2.27) via le connecteur Vault comme suit:

1. **Récupération credential_ref depuis intégration**: L'intégration stockée dans la table `INTEGRATIONS` contient un champ `CREDENTIAL_REF` qui est un chemin Vault (ex: `secret/data/idp/aap-prod`).

2. **Injection du service**: Le moteur d'exécution injecte `VaultService` via `Depends(get_vault_service)` depuis `app.api.services`.

3. **Récupération du secret**: Appel `vault_service.get_secret(credential_ref)` qui retourne un dictionnaire avec les champs nécessaires (ex: `{"username": "user", "password": "pass", "api_key": "key"}`).

4. **Utilisation pour adapter plateforme**: Le dictionnaire retourné est passé à l'adapter de plateforme (AAP, Terraform, etc.) qui utilise les credentials pour s'authentifier lors de l'exécution.

**Exemple d'usage:**
```python
from app.api.services import get_vault_service
from app.services.vault_service import VaultService

async def execute_action(integration_id: int, vault_service: VaultService = Depends(get_vault_service)):
    integration = await integration_repository.get_by_id(integration_id)
    credentials = await vault_service.get_secret(integration.credential_ref)
    # credentials = {"username": "...", "password": "...", "api_key": "..."}
    # Passer credentials à l'adapter de plateforme
```

**Mode dev désactivé**: Si `VAULT_ADDR` n'est pas configuré, `get_vault_service()` retourne `VaultServiceDisabled` qui lève `NotImplementedError`. Le moteur d'exécution peut gérer ce cas pour permettre le développement sans Vault réel.

### File List

**Nouveaux fichiers:**
- `idp-portal/backend/app/services/vault_service.py` - Service Vault avec authentification Token/AppRole et récupération secrets KV v1/v2
- `idp-portal/backend/app/api/services.py` - Factory function `get_vault_service()` pour injection FastAPI
- `idp-portal/backend/tests/unit/test_vault_service.py` - Tests unitaires pour VaultService (initialisation, get_secret, gestion erreurs, factory function)

**Fichiers modifiés:**
- `idp-portal/backend/app/core/config.py` - Ajout variables Vault (vault_addr, vault_token, vault_role_id, vault_secret_id)
- `idp-portal/backend/pyproject.toml` - Ajout dépendance `hvac>=2.4.0`
- `idp-portal/.env.example` - Documentation variables Vault (VAULT_ADDR, VAULT_TOKEN, VAULT_ROLE_ID, VAULT_SECRET_ID)
- `idp-portal/backend/app/core/exceptions.py` - Ajout `ServiceUnavailableError` (HTTP 503) pour mode Vault désactivé
- `idp-portal/backend/app/main.py` - Validation connexion Vault au démarrage avec log warning si échec (lignes 70-77)

### Code Review Fixes Applied (2026-01-29)

**Corrections HIGH issues:**
- ✅ HIGH-1: Installation dépendance `hvac>=2.4.0` et validation tests (11/11 passent)
- ✅ HIGH-2: Documentation complète File List avec exceptions.py et main.py
- ✅ HIGH-3: VaultServiceDisabled utilise `ServiceUnavailableError` au lieu de `NotImplementedError`, type hint corrigé
- ✅ HIGH-4: Validation Vault au démarrage dans `main.py` lifespan avec log warning si échec
- ✅ HIGH-5: Logging `vault_secret_retrieved` déplacé APRÈS succès récupération (dans `_read_secret()`)

**Corrections MEDIUM issues:**
- ✅ MEDIUM-1: Validation structure response AppRole - vérifie présence `client_token` avant utilisation
- ✅ MEDIUM-2: Documentation pattern asyncio.to_thread justifiée (hvac sync API, pas de overhead significatif)
- ✅ MEDIUM-3: Timeout 30s ajouté à `hvac.Client(url=vault_addr, timeout=30)`
- ✅ MEDIUM-4: Tests ajoutés pour `get_vault_service()` factory (3 tests: disabled, enabled, error)

**Résultat tests:**
```
11 passed in 0.37s
- 3 tests initialisation (Token, AppRole, erreur connexion)
- 5 tests get_secret (KV v2, KV v1, not found, unavailable, auth failed)
- 3 tests factory function (disabled, enabled, ServiceUnavailableError)
```
